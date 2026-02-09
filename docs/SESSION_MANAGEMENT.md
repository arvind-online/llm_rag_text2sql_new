# Multi-User Session Management Implementation

## Overview

The session management system enables **proper multi-user support** with:
- ✅ **Isolated memory** per user session
- ✅ **Cached schema** per session (avoids DB introspection per query)
- ✅ **Thread-safe** concurrent request handling
- ✅ **Automatic session expiry** after 30 minutes of inactivity

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Request Flow with Sessions                │
└─────────────────────────────────────────────────────────────┘

User Request: {query: "Show users", session_id: "abc123"}
    │
    ├─→ FastAPI /query endpoint (main.py)
    │
    ├─→ run_query(query, context, session_id)  [graph.py]
    │
    ├─→ execute_sql(state) 
    │   │
    │   ├─→ get_session_manager().get_or_create_session(session_id)
    │   │       │
    │   │       └─→ Returns UserSession {
    │   │               session_id: "abc123",
    │   │               cached_schema: None (first time),
    │   │               query_history: [],
    │   │               created_at: timestamp,
    │   │               last_accessed: timestamp
    │   │           }
    │   │
    │   └─→ sql_agent.query(query, session)
    │       │
    │       ├─→ generate_sql(query, session)
    │       │   │
    │       │   ├─→ Check session.cached_schema
    │       │   │   If None: Fetch from DB and cache it ✅
    │       │   │   If exists: Reuse cached schema ⚡
    │       │   │
    │       │   └─→ Build history from session.query_history
    │       │
    │       └─→ _save_query_context(session, query, sql, results)
    │           └─→ Appends to session.query_history ✅
    │
    └─→ Return result with session_id
```

---

## Key Components

### 1. UserSession (session_manager.py)

```python
@dataclass
class UserSession:
    session_id: str
    cached_schema: Optional[str] = None       # ← Cached DB schema
    query_history: list[QueryContext] = []    # ← Conversation history
    created_at: float
    last_accessed: float
    max_history: int = 5
```

### 2. SessionManager (session_manager.py)

Thread-safe singleton that manages all sessions:

```python
class SessionManager:
    def get_or_create_session(session_id: Optional[str]) -> UserSession
    def get_session(session_id: str) -> Optional[UserSession]
    def delete_session(session_id: str) -> bool
    def get_active_session_count() -> int
    def _cleanup_expired() -> None  # Automatic cleanup
```

---

## API Changes

### QueryRequest (models.py)

```python
class QueryRequest(BaseModel):
    query: str
    context: Optional[str] = None
    session_id: Optional[str] = None  # ← NEW!
```

### POST /query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show all users",
    "session_id": "my-session-123"  # ← Optional
  }'
```

**Behavior:**
- If `session_id` is provided: Use that session
- If `session_id` is `null`: Auto-generate a new UUID
- Follow-up queries with same `session_id` share memory & cached schema

---

## New Endpoints

### GET /sessions/status

Check active sessions:

```bash
curl http://localhost:8000/sessions/status
```

**Response:**
```json
{
  "active_sessions": 3,
  "ttl_seconds": 1800
}
```

### DELETE /sessions/{session_id}

Delete a specific session:

```bash
curl -X DELETE http://localhost:8000/sessions/my-session-123
```

**Response:**
```json
{
  "success": true,
  "message": "Session my-session-123 deleted"
}
```

---

## Benefits vs Previous Implementation

| Aspect | Before | After |
|--------|--------|-------|
| **Multi-user support** | ❌ Single global memory | ✅ Isolated per session |
| **Schema fetching** | ❌ DB query every request | ✅ Cached per session |
| **Memory isolation** | ❌ All users share history | ✅ Separate history per user |
| **Thread safety** | ❌ Not thread-safe | ✅ Thread-safe with locks |
| **Memory cleanup** | ❌ Grows forever | ✅ Auto-expires after 30min |

---

## Token Optimization Impact

### Schema Caching

**Before:**
```
Query 1: Fetch schema from DB (100ms) → Send to LLM (2000 tokens)
Query 2: Fetch schema from DB (100ms) → Send to LLM (2000 tokens)
Query 3: Fetch schema from DB (100ms) → Send to LLM (2000 tokens)
```

**After:**
```
Query 1: Fetch schema from DB (100ms) → Cache it → Send to LLM (2000 tokens)
Query 2: Use cached schema (0ms) → Send to LLM (2000 tokens)
Query 3: Use cached schema (0ms) → Send to LLM (2000 tokens)
```

**Savings:** Eliminates DB introspection latency (not token usage - LLM still needs schema)

---

## Testing

### Manual Test - Single Session

```bash
# First query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show all users", "session_id": "test-1"}'

# Follow-up query (uses memory)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many of them?", "session_id": "test-1"}'
```

### Manual Test - Multi-User

```bash
# User 1
curl -X POST http://localhost:8000/query \
  -d '{"query": "Show products", "session_id": "user-1"}'

# User 2 (different session)
curl -X POST http://localhost:8000/query \
  -d '{"query": "Show orders", "session_id": "user-2"}'

# User 1 follow-up (knows about products)
curl -X POST http://localhost:8000/query \
  -d '{"query": "Count them", "session_id": "user-1"}'

# User 2 follow-up (knows about orders)
curl -X POST http://localhost:8000/query \
  -d '{"query": "Count them", "session_id": "user-2"}'
```

### Automated Test

```bash
python3 test_memory.py
```

Tests:
1. Single user session with follow-ups
2. Multi-user session isolation
3. Schema caching verification

---

## Configuration

### Session TTL

Default: 30 minutes (1800 seconds)

To change, modify `session_manager.py`:

```python
# Initialize with custom TTL
_session_manager = SessionManager(ttl_seconds=3600)  # 1 hour
```

### Max History per Session

Default: 5 queries

To change, modify `session_manager.py`:

```python
@dataclass
class UserSession:
    ...
    max_history: int = 10  # Keep more history
```

---

## Important Note: LLM Token Behavior

> ⚠️ **Schema is still sent on every LLM request**
> 
> The schema caching **does not reduce LLM token usage** because LLMs are stateless - each API call must include the full context.
> 
> **What it DOES save:**
> - ✅ Database introspection time
> - ✅ Server-side processing
> - ✅ Memory correctness across users
> 
> **What it DOESN'T save:**
> - ❌ LLM input tokens (schema must be sent each time)

---

## Production Considerations

### For Production Use

Consider using **Redis** instead of in-memory storage:

```python
from langchain.memory import RedisChatMessageHistory

class SessionManager:
    def __init__(self):
        self.redis_url = "redis://localhost:6379"
    
    def get_session(self, session_id):
        return RedisChatMessageHistory(
            session_id=session_id,
            url=self.redis_url,
            ttl=1800
        )
```

Benefits:
- ✅ Survives server restarts
- ✅ Scales across multiple instances
- ✅ Built-in TTL support

---

## Migration from Previous Version

### No Breaking Changes!

Old code continues to work:
```python
# Without session_id (auto-generates one)
result = run_query("Show users")  # ✅ Works

# With session_id (explicit)
result = run_query("Show users", session_id="user-123")  # ✅ Also works
```

The API is backward compatible.
