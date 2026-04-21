# Codebase Structure

**Analysis Date:** 2026-04-03

## Directory Layout

```
claude-code-agentic-rag-masterclass/
├── backend/                    # Python FastAPI backend
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Settings (pydantic-settings)
│   ├── database.py             # Supabase client factory
│   ├── auth.py                 # JWT verification middleware
│   ├── requirements.txt        # Python dependencies
│   ├── models/                 # Pydantic schemas
│   │   ├── __init__.py
│   │   └── schemas.py          # Request/response models
│   ├── routers/                # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── threads.py          # CRUD for chat threads
│   │   ├── chat.py             # SSE chat endpoint + tool definitions
│   │   └── documents.py        # Upload, list, delete documents
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── llm_service.py      # OpenAI client + streaming completions
│   │   ├── embedding_service.py # Text embedding via OpenAI API
│   │   ├── retrieval_service.py # Vector/keyword/hybrid search + RRF
│   │   ├── rerank_service.py   # LLM or API-based reranking
│   │   ├── ingestion_service.py # Document chunking + embedding pipeline
│   │   ├── parsing_service.py  # File-to-text extraction (docling)
│   │   ├── metadata_service.py # LLM-based document metadata extraction
│   │   ├── record_manager.py   # Content hashing + dedup + incremental diff
│   │   ├── sql_service.py      # Text-to-SQL execution via RPC
│   │   ├── web_search_service.py # Tavily web search integration
│   │   ├── subagent_service.py # Full-document analysis sub-agent
│   │   └── tracing.py         # LangSmith setup
│   ├── tests/                  # Test files
│   │   ├── test_record_manager.py
│   │   └── test_e2e_subagent.py
│   └── .models/                # Cached ML models for docling (git-ignored)
├── frontend/                   # React + Vite frontend
│   ├── index.html              # HTML entry point
│   ├── package.json            # Node dependencies
│   ├── vite.config.ts          # Vite config (proxy, plugins)
│   ├── tsconfig.json           # TypeScript config
│   ├── eslint.config.js        # ESLint config
│   └── src/
│       ├── main.tsx            # React DOM render entry
│       ├── App.tsx             # Router + layout + auth wrapper
│       ├── components/         # Reusable UI components
│       │   ├── ChatContainer.tsx   # Message list + input area
│       │   ├── ChatInput.tsx       # Message input box
│       │   ├── MessageBubble.tsx   # Single message display
│       │   ├── ThreadSidebar.tsx   # Thread list sidebar
│       │   ├── IconSidebar.tsx     # Navigation icon bar
│       │   ├── FileUpload.tsx      # Drag-and-drop file upload
│       │   ├── DocumentList.tsx    # Document list with status
│       │   └── ProtectedRoute.tsx  # Auth guard wrapper
│       ├── pages/              # Page-level components
│       │   ├── LoginPage.tsx       # Email/password login
│       │   ├── ChatPage.tsx        # Chat interface (threads + messages)
│       │   └── DocumentsPage.tsx   # Document management interface
│       ├── hooks/              # Custom React hooks
│       │   ├── useChat.ts          # Chat messaging + SSE streaming
│       │   └── useDocuments.ts     # Document CRUD + realtime updates
│       ├── contexts/           # React context providers
│       │   └── AuthContext.tsx     # Auth state + Supabase session
│       ├── lib/                # Utility modules
│       │   ├── api.ts              # Authenticated fetch wrapper
│       │   └── supabase.ts         # Supabase JS client init
│       └── assets/             # Static assets
├── supabase/                   # Database schema
│   └── migrations/             # SQL migration files (001-015)
│       ├── 001_create_threads.sql
│       ├── 002_create_messages.sql
│       ├── 005_create_documents.sql
│       ├── 006_create_document_chunks.sql
│       ├── 007_create_storage_bucket.sql
│       ├── 008_match_chunks_function.sql
│       ├── 013_add_fulltext_search.sql
│       ├── 014_keyword_search_function.sql
│       ├── 015_execute_readonly_query.sql
│       └── run_all_module2.sql     # Batch migration runner
├── .env                        # Environment variables (git-ignored)
├── CLAUDE.md                   # Project instructions for AI agents
├── PROGRESS.md                 # Module completion status
├── README.md                   # Project readme
└── .agent/plans/               # Implementation plans
```

## Directory Purposes

**`backend/`:**
- Purpose: Python FastAPI application
- Contains: API server, business logic, data access
- Key files: `main.py` (entry point), `config.py` (all settings), `auth.py` (JWT verification)

**`backend/routers/`:**
- Purpose: HTTP endpoint definitions grouped by resource
- Contains: One file per resource (threads, chat, documents)
- Key files: `chat.py` (most complex -- SSE streaming + tool loop)

**`backend/services/`:**
- Purpose: Business logic separated from HTTP concerns
- Contains: One service per capability (LLM, embeddings, retrieval, ingestion, parsing, etc.)
- Key files: `llm_service.py` (LLM client), `retrieval_service.py` (search pipeline), `ingestion_service.py` (document processing)

**`backend/models/`:**
- Purpose: Pydantic data models for request/response validation
- Contains: `schemas.py` with all models
- Key files: `schemas.py` (ThreadCreate, MessageCreate, DocumentMetadata, etc.)

**`backend/tests/`:**
- Purpose: Test files
- Contains: Unit and E2E tests
- Key files: `test_record_manager.py`, `test_e2e_subagent.py`

**`frontend/src/components/`:**
- Purpose: Reusable UI components
- Contains: All React components except page-level ones
- Key files: `ChatContainer.tsx`, `FileUpload.tsx`, `MessageBubble.tsx`

**`frontend/src/pages/`:**
- Purpose: Top-level page components (one per route)
- Contains: `LoginPage.tsx`, `ChatPage.tsx`, `DocumentsPage.tsx`

**`frontend/src/hooks/`:**
- Purpose: Custom React hooks encapsulating API + state logic
- Contains: `useChat.ts` (SSE streaming + message state), `useDocuments.ts` (CRUD + realtime)

**`frontend/src/contexts/`:**
- Purpose: React context providers for cross-component state
- Contains: `AuthContext.tsx` (user session management)

**`frontend/src/lib/`:**
- Purpose: Utility modules and client initialization
- Contains: `api.ts` (authenticated fetch), `supabase.ts` (Supabase client)

**`supabase/migrations/`:**
- Purpose: Database schema definitions applied to Supabase
- Contains: Numbered SQL migration files (001-015)
- Key files: `008_match_chunks_function.sql` (vector search RPC), `014_keyword_search_function.sql` (full-text RPC), `015_execute_readonly_query.sql` (text-to-SQL RPC)

## Key File Locations

**Entry Points:**
- `backend/main.py`: FastAPI app creation, router registration, CORS setup
- `frontend/src/main.tsx`: React DOM render
- `frontend/src/App.tsx`: Routes, auth provider, layout

**Configuration:**
- `backend/config.py`: All backend settings (LLM, embeddings, search, reranking, web search, chunking)
- `frontend/vite.config.ts`: Vite plugins, API proxy to backend
- `.env`: Environment variables (repo root, shared by both frontend and backend)

**Core Logic:**
- `backend/routers/chat.py`: Agentic chat loop with tool execution and SSE streaming
- `backend/services/ingestion_service.py`: Full document processing pipeline (parse, chunk, embed, store)
- `backend/services/retrieval_service.py`: Search pipeline (vector, keyword, hybrid, rerank)
- `backend/services/llm_service.py`: OpenAI client creation and streaming completion
- `backend/services/subagent_service.py`: Full-document analysis via isolated LLM call

**Auth:**
- `backend/auth.py`: JWT verification (JWKS or HS256)
- `frontend/src/contexts/AuthContext.tsx`: Session state management
- `frontend/src/components/ProtectedRoute.tsx`: Route guard

**Database Schema:**
- `supabase/migrations/001_create_threads.sql`: Threads table + RLS
- `supabase/migrations/002_create_messages.sql`: Messages table + RLS
- `supabase/migrations/005_create_documents.sql`: Documents table + RLS
- `supabase/migrations/006_create_document_chunks.sql`: Chunks table with vector column + IVFFlat index

## Naming Conventions

**Files:**
- Backend Python: `snake_case.py` (e.g., `llm_service.py`, `record_manager.py`)
- Frontend React components: `PascalCase.tsx` (e.g., `ChatContainer.tsx`, `MessageBubble.tsx`)
- Frontend hooks: `camelCase.ts` prefixed with `use` (e.g., `useChat.ts`, `useDocuments.ts`)
- Frontend utilities: `camelCase.ts` (e.g., `api.ts`, `supabase.ts`)
- SQL migrations: `NNN_descriptive_name.sql` (e.g., `008_match_chunks_function.sql`)

**Directories:**
- Backend: `snake_case` (e.g., `routers/`, `services/`, `models/`)
- Frontend: `camelCase` (e.g., `components/`, `contexts/`, `hooks/`, `lib/`)

## Where to Add New Code

**New API Endpoint:**
- Create or extend a router in `backend/routers/`
- Register new router in `backend/main.py` via `app.include_router()`
- Add Pydantic request/response models to `backend/models/schemas.py`
- Add `get_user_id` as a Depends for auth

**New Backend Service:**
- Create `backend/services/{service_name}.py`
- Import and use from routers or other services
- Add settings to `backend/config.py` `Settings` class if needed

**New Tool for Chat Agent:**
- Define tool JSON schema as constant in `backend/routers/chat.py` (follow `RETRIEVAL_TOOL` pattern)
- Add tool to the `tools` list in `send_message()` (conditionally if needed)
- Add handler in `execute_tool()` function
- Implement logic in a service file under `backend/services/`

**New Frontend Page:**
- Create `frontend/src/pages/{PageName}.tsx`
- Add route in `frontend/src/App.tsx` (wrap with `ProtectedRoute` + `AuthenticatedLayout`)

**New Frontend Component:**
- Create `frontend/src/components/{ComponentName}.tsx`

**New Custom Hook:**
- Create `frontend/src/hooks/use{HookName}.ts`

**New Database Table:**
- Create `supabase/migrations/{NNN}_{description}.sql`
- Include RLS policies (enable RLS, create select/insert/update/delete policies using `auth.uid() = user_id`)

**New RPC Function:**
- Create `supabase/migrations/{NNN}_{function_name}.sql`
- Use `CREATE OR REPLACE FUNCTION` with `LANGUAGE plpgsql`
- Call from backend via `db.rpc("function_name", params).execute()`

## Special Directories

**`backend/.models/`:**
- Purpose: Cached Hugging Face models for docling document parsing (layout detection, OCR, table extraction)
- Generated: Yes (downloaded on first use)
- Committed: No (git-ignored)

**`backend/venv/`:**
- Purpose: Python virtual environment
- Generated: Yes
- Committed: No (git-ignored)

**`frontend/dist/`:**
- Purpose: Vite production build output
- Generated: Yes (via `npm run build`)
- Committed: No (git-ignored)

**`frontend/node_modules/`:**
- Purpose: Node.js dependencies
- Generated: Yes (via `npm install`)
- Committed: No (git-ignored)

**`.agent/plans/`:**
- Purpose: Implementation plan documents for AI agents
- Generated: Yes (by AI agents)
- Committed: Yes

**`.planning/codebase/`:**
- Purpose: Codebase analysis documents (this file and others)
- Generated: Yes (by mapping agents)
- Committed: Yes

---

*Structure analysis: 2026-04-03*
