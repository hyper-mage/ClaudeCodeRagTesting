# Coding Conventions

**Analysis Date:** 2026-04-03

## Naming Patterns

**Files (Python backend):**
- Use `snake_case.py` for all modules: `llm_service.py`, `record_manager.py`, `parsing_service.py`
- Services follow `{domain}_service.py` pattern: `embedding_service.py`, `retrieval_service.py`, `web_search_service.py`
- Routers named by resource: `chat.py`, `threads.py`, `documents.py`
- Test files use `test_{module}.py` prefix: `test_record_manager.py`, `test_e2e_subagent.py`

**Files (TypeScript frontend):**
- Use `PascalCase.tsx` for React components: `ChatContainer.tsx`, `MessageBubble.tsx`, `FileUpload.tsx`
- Use `PascalCase.tsx` for pages: `ChatPage.tsx`, `LoginPage.tsx`, `DocumentsPage.tsx`
- Use `camelCase.ts` for hooks: `useChat.ts`, `useDocuments.ts`
- Use `camelCase.ts` for utilities: `api.ts`, `supabase.ts`
- Use `PascalCase.tsx` for contexts: `AuthContext.tsx`

**Functions (Python):**
- Use `snake_case` for all functions: `get_embeddings()`, `search_documents()`, `extract_metadata_safe()`
- Private helpers prefixed with underscore: `_get_converter()`, `_search_tavily()`, `_get_jwk_client()`
- Factory functions use `get_` prefix: `get_settings()`, `get_supabase()`, `get_llm_client()`

**Functions (TypeScript):**
- Use `camelCase` for functions and handlers: `handleSubmit`, `loadMessages`, `sendMessage`
- React hooks use `use` prefix: `useChat`, `useDocuments`, `useAuth`
- Event handlers use `handle` prefix: `handleFile`, `handleDrop`, `handleDragOver`

**Variables (Python):**
- Use `snake_case`: `user_id`, `doc_id`, `content_hash`, `tool_calls_acc`
- Constants use `UPPER_SNAKE_CASE`: `RETRIEVAL_TOOL`, `SQL_TOOL`, `RERANK_PROMPT`, `QUERYABLE_SCHEMA`
- Module-level singletons use underscore prefix: `_converter = None`, `_jwk_client = None`

**Variables (TypeScript):**
- Use `camelCase`: `isStreaming`, `threadId`, `fileInputRef`
- Constants use `UPPER_SNAKE_CASE`: `TOOL_LABELS`, `ACCEPTED_TYPES`

**Types/Interfaces (TypeScript):**
- Use `PascalCase` for interfaces: `Message`, `ToolEvent`, `Document`, `DocumentMetadata`
- Props interfaces named `Props` (component-local): see `MessageBubble.tsx`, `ChatContainer.tsx`, `FileUpload.tsx`
- Context types named `{Name}ContextType`: `AuthContextType`

**Pydantic Models (Python):**
- Use `PascalCase`: `DocumentMetadata`, `ThreadCreate`, `ThreadResponse`, `MessageCreate`
- Response models suffixed with `Response`: `ThreadResponse`, `MessageResponse`, `DocumentResponse`
- Create/input models suffixed with `Create`: `ThreadCreate`, `MessageCreate`
- Inheritance for extended responses: `ThreadWithMessages(ThreadResponse)`

## Code Style

**Formatting (Python):**
- No formatter config file detected (no `pyproject.toml`, `setup.cfg`, `.flake8`, `ruff.toml`)
- De facto style: 4-space indentation, double quotes for strings
- Line length generally under 100 characters, some exceptions in long strings
- f-strings used throughout for string interpolation

**Formatting (TypeScript):**
- No Prettier config detected
- Single quotes for string literals
- 2-space indentation
- No semicolons at end of statements (inconsistent -- some files do, some don't; mostly absent)
- Arrow functions for component handlers and callbacks

**Linting (TypeScript):**
- ESLint 9 flat config at `frontend/eslint.config.js`
- Plugins: `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, `typescript-eslint`
- TypeScript strict mode enabled in `frontend/tsconfig.app.json` with `noUnusedLocals` and `noUnusedParameters`

**Linting (Python):**
- No linting tool configured (no ruff, flake8, pylint, mypy config)

## Import Organization

**Python backend pattern (observed consistently):**
1. Standard library imports (`json`, `logging`, `uuid`, `os`, `hashlib`)
2. Third-party imports (`fastapi`, `openai`, `httpx`, `jwt`, `pydantic`)
3. Local imports (`config`, `database`, `services.*`, `models.*`, `auth`)

Example from `backend/routers/chat.py`:
```python
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from auth import get_user_id
from database import get_supabase
from config import get_settings
from models.schemas import MessageCreate
from services.llm_service import stream_chat_completion
```

**Note:** No path aliases. Backend imports are relative to the `backend/` directory (it is the working directory when running). No `__init__.py` barrel exports -- all `__init__.py` files are empty.

**Conditional/lazy imports used for optional dependencies:**
```python
try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f
```

**TypeScript frontend pattern:**
1. Third-party imports (`react`, `react-router-dom`, `react-markdown`, `lucide-react`)
2. Local imports (`../lib/supabase`, `../contexts/AuthContext`, `./MessageBubble`)

No path aliases configured. All imports use relative paths (`../`, `./`).

## Error Handling

**Python backend patterns:**

1. **FastAPI HTTPException for client errors:**
```python
raise HTTPException(status_code=401, detail="Missing authorization token")
raise HTTPException(status_code=404, detail="Thread not found")
raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
```

2. **Try/except with status update for async processing:**
```python
try:
    # processing logic
    db.table("documents").update({"status": "completed"}).eq("id", doc_id).execute()
except Exception as e:
    db.table("documents").update({
        "status": "failed",
        "error_message": str(e),
    }).eq("id", doc_id).execute()
    raise
```

3. **Safe wrapper pattern for non-critical operations:**
```python
def extract_metadata_safe(text: str) -> DocumentMetadata:
    try:
        result = extract_metadata(text)
        return result
    except Exception as e:
        logger.warning(f"Metadata extraction failed, using defaults: {e}")
        return DocumentMetadata()
```

4. **Silent exception swallowing for cleanup/optional operations:**
```python
try:
    db.storage.from_("documents").remove([doc.data["storage_path"]])
except Exception:
    pass  # Storage file may already be gone
```

5. **SSE error events for streaming responses:**
```python
except Exception as e:
    yield {"event": "error", "data": json.dumps({"error": str(e)})}
```

6. **Service-level error returns (not exceptions) for tool results:**
```python
return {"success": False, "error": str(e), "rows": [], "row_count": 0}
```

**TypeScript frontend patterns:**

1. **Try/catch with error state:**
```typescript
try {
    // operation
} catch (err: unknown) {
    setError(err instanceof Error ? err.message : 'An error occurred')
} finally {
    setLoading(false)
}
```

2. **Error throw on non-ok HTTP responses:**
```typescript
if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
}
```

## Logging

**Framework (Python):** Standard library `logging` module

**Pattern:**
```python
logger = logging.getLogger(__name__)
```

**When to log:**
- `logger.info()` for successful operations: file uploads, metadata extraction, search results
- `logger.warning()` for fallbacks: unknown search mode, failed optional operations
- `logger.error()` for failures: `exc_info=True` added for stack traces on important errors

**Frontend:** Uses `console.error()` for caught exceptions only. No structured logging framework.

## Comments

**When to Comment:**
- Module-level docstrings for test files explaining purpose and usage
- Function docstrings on all service functions describing behavior and return values
- Inline comments for non-obvious logic (e.g., "rank is 0-indexed, +1 for 1-based")
- `# comment` on lines doing something unexpected (e.g., `pass  # Storage file may already be gone`)

**Docstring style (Python):**
```python
def stream_chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> Generator[dict, None, None]:
    """Stream a chat completion with optional tool definitions.

    Yields dicts:
      {"type": "text_delta", "text": "..."} for text chunks
      {"type": "tool_call", "tool_calls": [...]} when model invokes a tool
      {"type": "done"} when streaming is complete
    """
```

**No JSDoc/TSDoc used on the frontend side.**

## Function Design

**Size:** Most functions are 10-40 lines. Larger functions (like `send_message` in `backend/routers/chat.py`) contain nested async generators.

**Parameters:**
- Use type hints on all Python function parameters and return values
- Use `str | None` union syntax (Python 3.10+), not `Optional[str]`
- Use `list[dict]` not `List[Dict]` (modern Python generics)
- FastAPI `Depends()` for dependency injection of `user_id` and `settings`

**Return Values:**
- Python services return `dict`, `list[dict]`, `str`, or Pydantic models
- TypeScript hooks return object destructuring: `{ messages, isStreaming, sendMessage, loadMessages }`

## Module Design

**Exports (Python):**
- No barrel file exports; all `__init__.py` files are empty
- Import directly from module: `from services.llm_service import stream_chat_completion`

**Exports (TypeScript):**
- Default exports for React components: `export default function ChatContainer`
- Named exports for hooks: `export function useChat`
- Named exports for utilities: `export async function apiFetch`
- Named exports for context providers: `export function AuthProvider`, `export function useAuth`

## Configuration Pattern

**Backend uses singleton settings via `@lru_cache`:**
```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**All config from environment variables via `pydantic_settings.BaseSettings` at `backend/config.py`.** Access via `get_settings()` -- never read `os.environ` directly in service code.

**Frontend uses `import.meta.env.VITE_*` variables** initialized once in `frontend/src/lib/supabase.ts`.

## Database Access Pattern

**All database access goes through the Supabase Python client:**
```python
db = get_supabase()
result = db.table("documents").select("*").eq("user_id", user_id).execute()
```

**Use method chaining** for queries. Always filter by `user_id` for data ownership.

**Use `maybe_single()` when the record might not exist** (returns None instead of error):
```python
thread = db.table("threads").select("*").eq("id", thread_id).eq("user_id", user_id).maybe_single().execute()
if not thread.data:
    raise HTTPException(status_code=404, detail="Thread not found")
```

**Use `single()` when the record must exist** (raises error if missing).

## API Design Pattern

**Routers use `APIRouter` with prefix and tags:**
```python
router = APIRouter(prefix="/api/threads", tags=["threads"])
```

**All endpoints require authentication via `user_id: str = Depends(get_user_id)`.**

**Response models declared via `response_model=` parameter on route decorators** where applicable, but some endpoints return raw dicts.

**Streaming responses use `EventSourceResponse` from `sse_starlette`** with custom event types: `content_delta`, `tool_event`, `done`, `error`.

---

*Convention analysis: 2026-04-03*
