# Walkthrough: Switchable Groq / Ollama LLM Support

## What Changed (7 files, commit `505cca5`)

### [config.py](config.py)
- Added `llm_provider` setting: `"groq"` (default) or `"ollama"`
- Added `ollama_base_url`: default `http://localhost:11434` (supports remote URLs)
- Added `ollama_model`: default `llama3`
- Added `get_llm()` factory function: returns `ChatGroq` or `ChatOllama` based on provider

### Agent files (same change pattern × 4)
- [router.py](agents/router.py)
- [combiner.py](agents/combiner.py)
- [rag_agent.py](agents/rag_agent.py)
- [text2sql_agent.py](agents/text2sql_agent.py)

**Changes in each:**
- Removed `from langchain_groq import ChatGroq`
- Added `from config import get_llm`
- Replaced `self.llm = ChatGroq(model=..., api_key=..., temperature=...)` → `self.llm = get_llm()`

### [.env.example](.env.example)
Added configuration placeholders:
```env
LLM_PROVIDER=groq
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

### [requirements.txt](requirements.txt)
Added `langchain-ollama==0.3.3`

---

## How to Switch Between Providers

### Use Groq (Default - Cloud-based)
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
```

### Use Local Ollama
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

### Use Remote Ollama Server
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://your-gpu-server:11434
OLLAMA_MODEL=llama3.1:70b
```

---

## Design Pattern: Central LLM Factory

Instead of each agent importing and instantiating `ChatGroq` directly, we now use a **central factory function**:

```python
# config.py
def get_llm():
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.llm_model,
            api_key=settings.groq_api_key,
            temperature=settings.llm_temperature,
        )
```

This keeps the provider logic centralized and makes all agents automatically support any LLM provider we add in the future.

---

## Installation

Install the new dependency:
```bash
pip install langchain-ollama
```

---

## Validation

- ✅ All 5 Python files pass `python3 -m py_compile`
- ✅ Committed to `feature/ollama` branch (commit `505cca5`)
- ✅ 7 files changed, 51 insertions, 30 deletions

---

## Testing

### 1. Test with Groq (existing behavior)
```bash
# In .env
LLM_PROVIDER=groq

# Restart server
python3 main.py
```

### 2. Test with local Ollama
```bash
# Make sure Ollama is running
ollama serve

# In .env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3

# Restart server
python3 main.py
```

### 3. Verify switching works
- Make a query with Groq
- Stop server, change to Ollama in `.env`
- Restart server and make the same query
- Both should work seamlessly

---

## Benefits

1. **Flexibility**: Switch between cloud (Groq) and local (Ollama) LLMs
2. **Privacy**: Can use fully local LLMs with Ollama
3. **Cost Control**: Use local models to reduce API costs
4. **Remote Ollama**: Can leverage GPU servers for heavy models
5. **Future-proof**: Easy to add more providers (e.g., OpenAI, Anthropic)
