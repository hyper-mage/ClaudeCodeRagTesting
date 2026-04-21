# Architecture

**Analysis Date:** 2026-04-03

## Pattern Overview

**Overall:** Client-Server with Agentic RAG backend (tool-use loop)

**Key Characteristics:**
- React SPA frontend communicates with Python FastAPI backend via REST + SSE
- Backend uses Supabase as combined database, auth, file storage, and realtime provider
- Chat uses an agentic tool-use loop: LLM decides which tools to call, backend executes them, feeds results back to LLM in a while-loop until no more tool calls
- Document ingestion is synchronous (inline processing on upload, no background workers)
- All LLM calls use raw OpenAI SDK (no LangChain/LangGraph) with OpenRouter as the default provider
- Stateless completions: full chat history is loaded from DB and sent with every request

## Layers

**Frontend (React SPA):**
- Purpose: User interface for chat and document management
- Location: `frontend/src/`
- Contains: Pages, components, hooks, context providers, API client
- Depends on: Backend API (via `/api` proxy), Supabase JS client (auth + realtime)
- Used by: End users in browser

**API Layer (FastAPI Routers):**
- Purpose: HTTP endpoints for threads, messages, and documents
- Location: `backend/routers/`
- Contains: `threads.py`, `chat.py`, `documents.py`
- Depends on: Auth middleware (`backend/auth.py`), database client (`backend/database.py`), services layer
- Used by: Frontend via fetch/SSE

**Services Layer:**
- Purpose: Core business logic (LLM, embeddings, retrieval, ingestion, parsing)
- Location: `backend/services/`
- Contains: `llm_service.py`, `embedding_service.py`, `retrieval_service.py`, `ingestion_service.py`, `parsing_service.py`, `metadata_service.py`, `rerank_service.py`, `sql_service.py`, `web_search_service.py`, `subagent_service.py`, `record_manager.py`, `tracing.py`
- Depends on: External APIs (OpenRouter, OpenAI, Tavily), Supabase DB/Storage
- Used by: Routers

**Data Layer (Supabase):**
- Purpose: Postgres DB with pgvector, file storage, auth, realtime
- Location: `supabase/migrations/` (schema definitions)
- Contains: Tables (`threads`, `messages`, `documents`, `document_chunks`), RPC functions (`match_document_chunks`, `keyword_search_chunks`, `execute_readonly_query`), Storage bucket (`documents`)
- Depends on: Supabase hosted service
- Used by: Backend (via `supabase-py` service role client), Frontend (via `@supabase/supabase-js` anon client for auth + realtime only)

**Configuration:**
- Purpose: Centralized settings from environment variables
- Location: `backend/config.py`
- Contains: `Settings` class (pydantic-settings), `get_settings()` singleton
- Depends on: `.env` file at repo root
- Used by: All backend modules

## Data Flow

**Chat Message Flow (Agentic Tool Loop):**

1. User sends message via `ChatInput` component
2. `useChat` hook POSTs to `/api/threads/{thread_id}/messages` and reads SSE stream
3. `chat.py` router stores user message in `messages` table
4. Router loads full thread history from `messages` table
5. `stream_chat_completion()` sends history + system prompt + tool definitions to LLM
6. **Tool loop begins** (while True):
   - If LLM returns `text_delta` events, they are yielded as SSE `content_delta`
   - If LLM returns `tool_call`, router executes the tool via `execute_tool()`:
     - `search_documents` -> `retrieval_service.search_documents()`
     - `query_database` -> `sql_service.execute_sql()`
     - `web_search` -> `web_search_service.search_web()`
     - `analyze_document` -> `subagent_service.run_document_analysis()`
   - Tool results appended to message list, loop continues with another LLM call
   - If no tool calls, loop breaks
7. Final assistant content stored in `messages` table
8. SSE `done` event sent with `message_id`

**Document Ingestion Flow:**

1. User selects file via `FileUpload` component
2. `useDocuments` hook POSTs multipart form to `/api/documents/upload`
3. `documents.py` router:
   a. Computes SHA-256 hash of file content (`record_manager.hash_content()`)
   b. Checks for exact duplicate (same hash, same user) -- returns early if found
   c. Checks for same-filename previous version (incremental update candidate)
   d. Uploads file to Supabase Storage at `{user_id}/{doc_id}/{filename}`
   e. Creates `documents` record with status `pending`
   f. Calls `process_document()` or `process_document_incremental()`:
      - Downloads file from storage
      - Parses text via `parsing_service.extract_text()` (docling for PDF/DOCX/HTML/MD, direct decode for .txt)
      - Extracts metadata via LLM (`metadata_service.extract_metadata_safe()`)
      - Chunks text with recursive character splitting (`ingestion_service.chunk_text()`)
      - Generates embeddings in batches of 100 (`embedding_service.get_embeddings()`)
      - Inserts chunks with embeddings into `document_chunks` table
      - Updates document status to `completed`
4. Supabase Realtime pushes status changes to frontend via `useDocuments` hook subscription

**Retrieval Pipeline:**

1. `retrieval_service.search_documents()` called with user query
2. Based on `search_mode` config:
   - `vector_only`: embed query, call `match_document_chunks` RPC (cosine similarity)
   - `keyword_only`: call `keyword_search_chunks` RPC (PostgreSQL full-text search with `ts_rank_cd`)
   - `hybrid`: run both, combine via Reciprocal Rank Fusion (RRF)
3. Optional reranking (`rerank_service.rerank()`):
   - `llm` provider: scores each chunk with LLM (0.0-1.0 relevance)
   - `api` provider: calls external rerank API (Jina, Cohere)
4. Return top-k results

**State Management:**
- Backend is stateless -- all state in Supabase DB
- Frontend state: React useState/useCallback hooks in `useChat` and `useDocuments`
- Auth state: `AuthContext` provider wrapping app, reads Supabase session
- No Redux/Zustand -- state is local to pages via hooks

## Key Abstractions

**Tool Definitions:**
- Purpose: Define LLM-callable tools as OpenAI function-calling JSON schemas
- Location: `backend/routers/chat.py` (constants: `RETRIEVAL_TOOL`, `SQL_TOOL`, `WEB_SEARCH_TOOL`, `ANALYZE_DOCUMENT_TOOL`)
- Pattern: Tools are conditionally included based on user state (has documents?) and config (web search enabled?)

**Settings Singleton:**
- Purpose: Type-safe configuration from env vars
- Location: `backend/config.py`
- Pattern: `pydantic_settings.BaseSettings` with `@lru_cache` on `get_settings()`. Supports separate providers for chat LLM vs embeddings.

**Supabase Client:**
- Purpose: Database and storage access
- Location: `backend/database.py` (backend, service role key), `frontend/src/lib/supabase.ts` (frontend, anon key)
- Pattern: Backend uses service role key (bypasses RLS for server-side operations). Frontend uses anon key (RLS-enforced, auth + realtime only).

**Record Manager:**
- Purpose: Content-addressed deduplication and incremental updates
- Location: `backend/services/record_manager.py`
- Pattern: SHA-256 hashes at file level (duplicate detection) and chunk level (incremental diff). On re-upload of same filename: diff chunks, embed only new ones, re-parent surviving chunks.

**Sub-Agent:**
- Purpose: Analyze entire documents (not just chunks) via isolated LLM call
- Location: `backend/services/subagent_service.py`
- Pattern: Resolves document by name, reassembles full text from chunks, runs non-streaming completion with dedicated system prompt. Triggered by `analyze_document` tool call.

## Entry Points

**Backend Server:**
- Location: `backend/main.py`
- Triggers: `uvicorn backend.main:app` (or `uvicorn main:app` from `backend/` dir)
- Responsibilities: Creates FastAPI app, sets up CORS, includes routers, configures LangSmith tracing

**Frontend App:**
- Location: `frontend/src/main.tsx` -> `frontend/src/App.tsx`
- Triggers: `npm run dev` (Vite dev server)
- Responsibilities: React app with BrowserRouter, AuthProvider, 3 routes (`/login`, `/`, `/documents`)

**Database Migrations:**
- Location: `supabase/migrations/001_create_threads.sql` through `015_execute_readonly_query.sql`
- Triggers: Applied manually via Supabase dashboard or `supabase db push`
- Responsibilities: Schema creation, RLS policies, RPC functions, storage bucket setup

## Error Handling

**Strategy:** Exception-based with status-tracking for async operations

**Patterns:**
- Ingestion failures: caught in `process_document()`, document status set to `failed` with `error_message` in DB
- Chat SSE errors: caught in `event_generator()`, yielded as SSE `error` event with error message
- Auth failures: `HTTPException(401)` raised by `get_user_id()` dependency
- Tool execution failures: caught per-tool in `execute_tool()`, returned as JSON `{"error": ...}` to LLM for graceful handling
- Metadata extraction: `extract_metadata_safe()` wraps `extract_metadata()` with fallback to default `DocumentMetadata()`
- SQL execution: `execute_readonly_query` RPC validates query safety (SELECT-only, blocks dangerous keywords), returns error dict on failure

## Cross-Cutting Concerns

**Logging:** Python `logging` module, loggers per module (`logging.getLogger(__name__)`). No structured logging or external log aggregation.

**Validation:** Pydantic models for request/response schemas (`backend/models/schemas.py`). LLM metadata extraction validated through `DocumentMetadata.model_validate()`. SQL queries validated server-side in the `execute_readonly_query` RPC function.

**Authentication:** Supabase Auth (JWT-based). Frontend uses `@supabase/supabase-js` for login/session. Backend verifies JWT in `backend/auth.py` using JWKS (asymmetric) or shared secret (symmetric). Every API endpoint depends on `get_user_id()` for auth. All DB tables have RLS policies scoping data to `auth.uid() = user_id`.

**Observability:** LangSmith tracing via `langsmith` SDK. Setup in `backend/services/tracing.py`. OpenAI client wrapped with `wrap_openai()` for automatic trace capture. Key functions decorated with `@traceable`.

**API Proxying:** Vite dev server proxies `/api` to `http://localhost:8000` (`frontend/vite.config.ts`). Frontend never calls backend directly -- always through `/api` prefix.

---

*Architecture analysis: 2026-04-03*
