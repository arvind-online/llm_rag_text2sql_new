# Quick Start: Testing Session Management

## Prerequisites

Make sure your services are running:
```bash
# Terminal 1: Backend
python3 main.py

# Terminal 2: Frontend (if needed)
cd ui && npm run dev
```

---

## Test 1: Basic Session Usage

### Without session_id (auto-generates)
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show all users"}'
```

### With explicit session_id
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show all users",
    "session_id": "test-session-1"
  }'
```

---

## Test 2: Follow-up Queries (Memory Test)

```bash
# First query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show all users",
    "session_id": "memory-test"
  }'

# Follow-up using pronoun "them"
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How many of them are there?",
    "session_id": "memory-test"
  }'

# Another follow-up
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me the active ones",
    "session_id": "memory-test"
  }'
```

**Expected:** Each follow-up correctly understands context from previous queries.

---

## Test 3: Multi-User Isolation

```bash
# User 1: Ask about products
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show all products",
    "session_id": "user-1"
  }'

# User 2: Ask about orders (different topic!)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show all orders",
    "session_id": "user-2"
  }'

# User 1 follow-up (should know about products)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How many of them cost more than $100?",
    "session_id": "user-1"
  }'

# User 2 follow-up (should know about orders)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How many of them were placed this week?",
    "session_id": "user-2"
  }'
```

**Expected:** User 1's "them" refers to products, User 2's "them" refers to orders.

---

## Test 4: Check Session Status

```bash
# See active sessions
curl http://localhost:8000/sessions/status
```

**Example response:**
```json
{
  "active_sessions": 3,
  "ttl_seconds": 1800
}
```

---

## Test 5: Delete a Session

```bash
# Delete specific session
curl -X DELETE http://localhost:8000/sessions/test-session-1
```

**Expected:**
```json
{
  "success": true,
  "message": "Session test-session-1 deleted"
}
```

---

## Test 6: Automated Tests

Run the comprehensive test suite:

```bash
python3 test_memory.py
```

This will run:
1. ✅ Single user session with follow-ups
2. ✅ Multi-user session isolation
3. ✅ Schema caching verification

---

## What to Look For

### ✅ Success Indicators

1. **Follow-ups work:** "How many of them?" correctly understands context
2. **Sessions isolated:** Different users don't interfere
3. **Schema cached:** First query of each session fetches schema, rest reuse it
4. **No errors:** All queries return valid responses

### ❌ Failure Indicators

1. "I don't know what you're referring to" (memory not working)
2. Wrong context (sessions not isolated)
3. Errors about missing session_id
4. Database connection errors

---

## Troubleshooting

### Issue: "Session not found"
**Solution:** Session expired (30min TTL). Use a new session_id.

### Issue: Follow-ups don't understand context
**Check:**
```bash
# Verify session has history
curl http://localhost:8000/sessions/status
```

### Issue: Different users see each other's history
**Problem:** Not using different session_ids!
**Solution:** Ensure each user has unique session_id.

---

## Advanced: Testing Schema Caching

Enable SQL query debugging to see caching in action:

1. Set in `.env`:
   ```
   SHOW_SQL_QUERIES=true
   ```

2. Make requests:
   ```bash
   # First query - schema fetched
   curl -X POST http://localhost:8000/query \
     -d '{"query": "Show users", "session_id": "cache-test"}'
   
   # Second query - schema cached (check logs)
   curl -X POST http://localhost:8000/query \
     -d '{"query": "Count users", "session_id": "cache-test"}'
   ```

3. Check server logs - you should see DB introspection only on first query!

---

## Clean Up

After testing, delete all sessions:

```bash
curl -X DELETE http://localhost:8000/sessions/test-session-1
curl -X DELETE http://localhost:8000/sessions/memory-test
curl -X DELETE http://localhost:8000/sessions/user-1
curl -X DELETE http://localhost:8000/sessions/user-2
curl -X DELETE http://localhost:8000/sessions/cache-test
```

Or wait 30 minutes - they'll auto-expire! ⏱️
