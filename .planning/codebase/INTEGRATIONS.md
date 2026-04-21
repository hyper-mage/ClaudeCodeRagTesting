# External Integrations

**Analysis Date:** 2026-04-03

## APIs & External Services

**LLM / Chat Completions:**
- OpenRouter (default) or any OpenAI-compatible API - Chat completions, tool calls, streaming
  - SDK/Client: `openai` Python SDK with configurable `base_url`
  - Auth: `LLM_API_KEY` env var (falls back to `OPENAI_API_KEY`)
  - Base URL: `LLM_BASE_URL` (default: `https://openrouter.ai/api/v1`)
  - Model: `LLM_MODEL` env var
  - Implementation: `backend/services/llm_service.py` - `get_llm_client()` creates an `OpenAI` client with custom base_url
  - Wrapped with LangSmith tracing when `LANGSMITH_API_KEY` is set

**Embeddings:**
- OpenAI (default) or any OpenAI-compatible embedding API
  - SDK/Client: Raw `httpx` POST requests (NOT the OpenAI SDK)
  - Auth: `EMBEDDING_API_KEY` env var (falls back to `OPENAI_API_KEY`)
  - Base URL: `EMBEDDING_BASE_URL` (default: `https://api.openai.com/v1`)
  - Model: `EMBEDDING_MODEL` (default: `text-embedding-3-small`)
  - Dimensions: `EMBEDDING_DIMENSIONS` (default: 1536)
  - Implementation: `backend/services/embedding_service.py` - direct HTTP calls to `/embeddings` endpoint

**Web Search (Optional):**
- Tavily Search API - Web search for RAG augmentation
  - SDK/Client: Raw `httpx` POST requests
  - Auth: `WEB_SEARCH_API_KEY` env var
  - Endpoint: `https://api.tavily.com/search`
  - Implementation: `backend/services/web_search_service.py`
  - Enabled only when `WEB_SEARCH_API_KEY` is set (checked via `settings.web_search_enabled`)
  - Config: `WEB_SEARCH_PROVIDER` (only "tavily" supported), `WEB_SEARCH_MAX_RESULTS` (default: 5)

**Reranking (Optional):**
- LLM-based reranking (uses the chat LLM to score relevance) OR
- Dedicated rerank API (Jina, Cohere, etc.)
  - SDK/Client: OpenAI SDK (LLM mode) or raw `httpx` (API mode)
  - Auth: `RERANK_API_KEY` env var (for API mode)
  - Implementation: `backend/services/rerank_service.py`
  - Config: `RERANK_ENABLED` (default: false), `RERANK_PROVIDER` ("llm" or "api"), `RERANK_MODEL`, `RERANK_TOP_K` (default: 5)

**Observability:**
- LangSmith - LLM tracing and monitoring
  - SDK/Client: `langsmith` Python package, `langsmith.wrappers.wrap_openai`
  - Auth: `LANGSMITH_API_KEY` env var
  - Implementation: `backend/services/tracing.py` - sets `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` env vars
  - Project name: `LANGCHAIN_PROJECT` (default: "rag-masterclass")
  - Also uses `@traceable` decorator in `backend/services/subagent_service.py`

## Data Storage

**Database:**
- Supabase (hosted PostgreSQL with pgvector extension)
  - Connection: `SUPABASE_URL` env var
  - Client (backend): `supabase` Python SDK with service role key (`backend/database.py`)
  - Client (frontend): `@supabase/supabase-js` with anon key (`frontend/src/lib/supabase.ts`)
  - Auth keys: `SUPABASE_SERVICE_ROLE_KEY` (backend, full access), `VITE_SUPABASE_ANON_KEY` (frontend, RLS-restricted)

**Database Schema (15 migrations in `supabase/migrations/`):**
- `threads` - Chat conversation threads (user-scoped)
- `messages` - Chat messages within threads
- `documents` - Uploaded document metadata (status tracking, metadata JSONB)
- `document_chunks` - Chunked document text with vector embeddings
- pgvector extension enabled for similarity search
- Full-text search index on document_chunks

**RPC Functions:**
- `match_document_chunks` - Vector similarity search (used by `backend/services/retrieval_service.py`)
- `keyword_search_chunks` - Full-text keyword search (used by `backend/services/retrieval_service.py`)
- `execute_readonly_query` - Safe read-only SQL execution for text-to-SQL feature (used by `backend/services/sql_service.py`)

**Row-Level Security:** All tables have RLS - users only see their own data

**File Storage:**
- Supabase Storage - Document file storage
  - Bucket: `documents`
  - Created in migration `007_create_storage_bucket.sql`
  - Upload/download via `db.storage.from_("documents")` in `backend/services/ingestion_service.py`

**Caching:**
- None (no Redis, no in-memory caching beyond Python's `@lru_cache` on settings)

## Authentication & Identity

**Auth Provider:**
- Supabase Auth (built-in)
  - Frontend: `supabase.auth.getSession()` for session management (`frontend/src/lib/api.ts`)
  - Backend: JWT verification in `backend/auth.py`
  - Supports both HS256 (legacy) and ES256 (newer) JWT algorithms
  - ES256 verification uses JWKS endpoint: `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`
  - HS256 verification uses `SUPABASE_JWT_SECRET` env var
  - Token passed as `Authorization: Bearer <token>` header
  - FastAPI dependency: `get_user_id()` extracts user ID from JWT `sub` claim

**Auth Flow:**
1. Frontend authenticates with Supabase Auth (login/signup)
2. Frontend gets JWT access token from session
3. Frontend sends token in Authorization header to backend API
4. Backend verifies JWT and extracts `user_id` via `backend/auth.py`

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, no error tracking service)

**Logs:**
- Python `logging` module (standard library)
- Used throughout backend services with `logger = logging.getLogger(__name__)`
- No structured logging framework

**LLM Tracing:**
- LangSmith (optional, enabled when `LANGSMITH_API_KEY` is set)
- OpenAI client wrapped with `wrap_openai` for automatic trace capture
- `@traceable` decorator for custom spans (e.g., `subagent_document_analysis`)

## CI/CD & Deployment

**Hosting:**
- Not configured (no Dockerfile, no deployment config detected)

**CI Pipeline:**
- None detected (no `.github/workflows/`, no CI config)

## Environment Configuration

**Required env vars:**
- `SUPABASE_URL` or `VITE_SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Backend database access
- `SUPABASE_JWT_SECRET` - JWT verification (for HS256 projects)
- `VITE_SUPABASE_URL` - Frontend Supabase URL
- `VITE_SUPABASE_ANON_KEY` - Frontend Supabase anon key
- `OPENAI_API_KEY` - Fallback API key for LLM and embeddings
- `LLM_MODEL` - Model identifier for chat completions

**Optional env vars:**
- `LLM_BASE_URL` - Custom LLM endpoint (default: OpenRouter)
- `LLM_API_KEY` - Separate LLM API key (overrides `OPENAI_API_KEY`)
- `EMBEDDING_BASE_URL` - Custom embedding endpoint (default: OpenAI)
- `EMBEDDING_API_KEY` - Separate embedding API key
- `EMBEDDING_MODEL` - Embedding model (default: `text-embedding-3-small`)
- `EMBEDDING_DIMENSIONS` - Embedding vector size (default: 1536)
- `LANGSMITH_API_KEY` - Enable LangSmith tracing
- `LANGCHAIN_PROJECT` - LangSmith project name (default: "rag-masterclass")
- `WEB_SEARCH_API_KEY` - Enable Tavily web search tool
- `WEB_SEARCH_MAX_RESULTS` - Max web search results (default: 5)
- `RERANK_ENABLED` - Enable reranking (default: false)
- `RERANK_PROVIDER` - "llm" or "api" (default: "llm")
- `RERANK_API_KEY` - API key for external reranker
- `RERANK_MODEL` - Reranker model name
- `RERANK_TOP_K` - Results after reranking (default: 5)
- `SEARCH_MODE` - "hybrid", "vector_only", or "keyword_only" (default: "hybrid")
- `CHUNK_SIZE` - Text chunk size (default: 1000)
- `CHUNK_OVERLAP` - Chunk overlap (default: 200)
- `SYSTEM_PROMPT` - Custom system prompt for chat
- `SQL_MAX_ROWS` - Max rows from SQL queries (default: 50)

**Secrets location:**
- `.env` file at repo root (gitignored)

## Document Processing Pipeline

**Supported file types:**
- Plain text (`.txt`) - Direct UTF-8 decode, no parsing library
- PDF (`.pdf`) - Parsed via `docling` DocumentConverter
- DOCX (`.docx`) - Parsed via `docling` DocumentConverter
- HTML (`.html`) - Parsed via `docling` string converter
- Markdown (`.md`) - Parsed via `docling` string converter

**Implementation:** `backend/services/parsing_service.py`
- Lazy-initializes `docling` DocumentConverter (heavy initialization)
- Uses local `.models/` directory for PDF pipeline artifacts
- Binary formats written to temp files for processing

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Realtime

**Supabase Realtime:**
- Used for ingestion status updates (document processing progress)
- Frontend subscribes to Supabase Realtime channels
- Backend updates document status in database, which triggers Realtime events

---

*Integration audit: 2026-04-03*
