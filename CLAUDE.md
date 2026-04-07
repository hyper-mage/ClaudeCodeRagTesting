# CLAUDE.md

RAG app with chat (default) and document ingestion interfaces. Config via env vars, no admin UI.

## Stack
- Frontend: React + Vite + Tailwind + shadcn/ui
- Backend: Python + FastAPI
- Database: Supabase (Postgres, pgvector, Auth, Storage, Realtime)
- LLM: OpenAI (Module 1), OpenRouter (Module 2+)
- Observability: LangSmith

## Rules
- Python backend must use a `venv` virtual environment
- No LangChain, no LangGraph - raw SDK calls only
- Use Pydantic for structured LLM outputs
- All tables need Row-Level Security - users only see their own data
- Stream chat responses via SSE
- Use Supabase Realtime for ingestion status updates
- Module 2+ uses stateless completions - store and send chat history yourself
- Ingestion is manual file upload only - no connectors or automated pipelines

## Planning
- Save all plans to `.agent/plans/` folder
- Naming convention: `{sequence}.{plan-name}.md` (e.g., `1.auth-setup.md`, `2.document-ingestion.md`)
- Plans should be detailed enough to execute without ambiguity
- Each task in the plan must include at least one validation test to verify it works
- Assess complexity and single-pass feasibility - can an agent realistically complete this in one go?
- Include a complexity indicator at the top of each plan:
  - ✅ **Simple** - Single-pass executable, low risk
  - ⚠️ **Medium** - May need iteration, some complexity
  - 🔴 **Complex** - Break into sub-plans before executing

## Development Flow
1. **Plan** - Create a detailed plan and save it to `.agent/plans/`
2. **Build** - Execute the plan to implement the feature
3. **Validate** - Test and verify the implementation works correctly. Use browser testing where applicable via an appropriate MCP
4. **Iterate** - Fix any issues found during validation

## Test Credentials
- Email: `ragtest1@gmail.com`
- Password: `testpass123`

## Progress
Check PROGRESS.md for current module status. Update it as you complete tasks.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Board Game Knowledge Base RAG**

An agentic RAG application specialized for board games. It combines a pre-seeded default knowledge base of popular board games with user-uploaded private collections, providing intelligent chat that can search, compare, and recommend across the entire library. The agent uses Claude Code-inspired tooling (ls, tree, grep, glob, read) with transparent tool calls to navigate a hierarchical folder-based knowledge base stored in Supabase.

**Core Value:** The agent can intelligently search and reason across a structured board game knowledge base — finding rules, comparing mechanics, and recommending games — using the right tool for the job, transparently.

### Constraints

- **Tech Stack**: React+Vite+Tailwind frontend, Python+FastAPI backend, Supabase — established, no changes
- **No LangChain**: Raw OpenAI SDK calls only — project rule
- **Supabase-Only Storage**: All KB tools must work against Supabase tables/storage, not local filesystem
- **Docling Required**: PDF/DOCX/XLSX extraction must go through Docling to produce searchable markdown
- **RLS Enforced**: Default KB visible to all users, private uploads scoped by user_id
- **Context Budget**: Agent must manage context window carefully — smart chunking + scope controls
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- TypeScript ~5.9.3 - Frontend (React components, hooks, pages)
- Python 3.x - Backend (FastAPI services, routers, models)
- SQL - Supabase migrations (`supabase/migrations/`)
## Runtime
- Node.js (version not pinned, no `.nvmrc` detected) - Frontend dev server and build
- Python with venv (`backend/venv/`) - Backend API server
- npm - Frontend (`frontend/package.json`, `frontend/package-lock.json` present)
- pip - Backend (`backend/requirements.txt`)
## Frameworks
- React ^19.2.4 - Frontend UI framework
- FastAPI 0.115.12 - Backend API framework
- Vite ^6.4.1 - Frontend build tool and dev server
- Tailwind CSS ^4.2.2 - Utility-first CSS (via `@tailwindcss/vite` plugin)
- No test framework detected in `frontend/package.json`
- `backend/tests/` directory exists (framework not determined from requirements.txt)
- Vite ^6.4.1 - Dev server with HMR, production bundler
- `@vitejs/plugin-react` ^4.7.0 - React Fast Refresh support
- TypeScript ~5.9.3 - Type checking (strict mode enabled)
- ESLint ^9.39.4 - Linting with flat config (`frontend/eslint.config.js`)
- uvicorn 0.34.2 - ASGI server for FastAPI
## Key Dependencies
- `@supabase/supabase-js` ^2.99.3 - Supabase client for auth, realtime, storage
- `react-router-dom` ^7.13.1 - Client-side routing
- `react-markdown` ^10.1.0 - Markdown rendering in chat responses
- `lucide-react` ^0.577.0 - Icon library
- `@tailwindcss/typography` ^0.5.19 - Prose styling for rendered markdown
- `openai` 1.74.0 - OpenAI-compatible SDK for LLM chat completions and embeddings
- `supabase` 2.13.0 - Supabase Python client (database, storage, auth)
- `pydantic` 2.11.1 - Data validation and serialization for API models
- `pydantic-settings` 2.9.1 - Settings management from env vars
- `sse-starlette` 2.2.1 - Server-Sent Events for streaming chat responses
- `langsmith` 0.3.42 - LLM observability and tracing
- `docling` (unpinned) - Document parsing (PDF, DOCX, HTML, Markdown)
- `PyJWT` 2.10.1 - JWT token verification for Supabase auth
- `cryptography` 46.0.5 - Cryptographic operations for JWT (ES256 support)
- `python-dotenv` 1.1.0 - Environment variable loading from `.env`
- `httpx` (transitive, used directly) - HTTP client for embedding API calls, web search, reranking
## Configuration
- Single `.env` file at repo root, loaded by both frontend (via Vite `envDir: '..'`) and backend (via `python-dotenv`)
- Frontend reads `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` via `import.meta.env`
- Backend uses `pydantic-settings` (`backend/config.py`) to load all env vars into a `Settings` class
- Settings cached via `@lru_cache` on `get_settings()`
- `frontend/vite.config.ts` - Vite config with React plugin, Tailwind plugin, API proxy to `localhost:8000`
- `frontend/tsconfig.app.json` - TypeScript strict mode, target ES2023, bundler module resolution
- `frontend/eslint.config.js` - Flat ESLint config with typescript-eslint, react-hooks, react-refresh plugins
## TypeScript Configuration
- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`
- `noUncheckedSideEffectImports: true`
- `erasableSyntaxOnly: true`
## Dev Server Setup
- `/api/*` requests proxied to `http://localhost:8000`
- `dev` - Start Vite dev server
- `build` - TypeScript check + Vite production build
- `lint` - Run ESLint
- `preview` - Preview production build
## Platform Requirements
- Node.js (ES2023 target suggests Node 20+)
- Python 3.10+ (uses `X | None` union syntax)
- System dependencies for `docling` (PDF processing, may require additional native libs)
- Supabase project (Postgres + pgvector + Auth + Storage + Realtime)
- OpenAI API key or OpenRouter API key
- Optional: LangSmith API key, Tavily API key, reranking API key
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Use `snake_case.py` for all modules: `llm_service.py`, `record_manager.py`, `parsing_service.py`
- Services follow `{domain}_service.py` pattern: `embedding_service.py`, `retrieval_service.py`, `web_search_service.py`
- Routers named by resource: `chat.py`, `threads.py`, `documents.py`
- Test files use `test_{module}.py` prefix: `test_record_manager.py`, `test_e2e_subagent.py`
- Use `PascalCase.tsx` for React components: `ChatContainer.tsx`, `MessageBubble.tsx`, `FileUpload.tsx`
- Use `PascalCase.tsx` for pages: `ChatPage.tsx`, `LoginPage.tsx`, `DocumentsPage.tsx`
- Use `camelCase.ts` for hooks: `useChat.ts`, `useDocuments.ts`
- Use `camelCase.ts` for utilities: `api.ts`, `supabase.ts`
- Use `PascalCase.tsx` for contexts: `AuthContext.tsx`
- Use `snake_case` for all functions: `get_embeddings()`, `search_documents()`, `extract_metadata_safe()`
- Private helpers prefixed with underscore: `_get_converter()`, `_search_tavily()`, `_get_jwk_client()`
- Factory functions use `get_` prefix: `get_settings()`, `get_supabase()`, `get_llm_client()`
- Use `camelCase` for functions and handlers: `handleSubmit`, `loadMessages`, `sendMessage`
- React hooks use `use` prefix: `useChat`, `useDocuments`, `useAuth`
- Event handlers use `handle` prefix: `handleFile`, `handleDrop`, `handleDragOver`
- Use `snake_case`: `user_id`, `doc_id`, `content_hash`, `tool_calls_acc`
- Constants use `UPPER_SNAKE_CASE`: `RETRIEVAL_TOOL`, `SQL_TOOL`, `RERANK_PROMPT`, `QUERYABLE_SCHEMA`
- Module-level singletons use underscore prefix: `_converter = None`, `_jwk_client = None`
- Use `camelCase`: `isStreaming`, `threadId`, `fileInputRef`
- Constants use `UPPER_SNAKE_CASE`: `TOOL_LABELS`, `ACCEPTED_TYPES`
- Use `PascalCase` for interfaces: `Message`, `ToolEvent`, `Document`, `DocumentMetadata`
- Props interfaces named `Props` (component-local): see `MessageBubble.tsx`, `ChatContainer.tsx`, `FileUpload.tsx`
- Context types named `{Name}ContextType`: `AuthContextType`
- Use `PascalCase`: `DocumentMetadata`, `ThreadCreate`, `ThreadResponse`, `MessageCreate`
- Response models suffixed with `Response`: `ThreadResponse`, `MessageResponse`, `DocumentResponse`
- Create/input models suffixed with `Create`: `ThreadCreate`, `MessageCreate`
- Inheritance for extended responses: `ThreadWithMessages(ThreadResponse)`
## Code Style
- No formatter config file detected (no `pyproject.toml`, `setup.cfg`, `.flake8`, `ruff.toml`)
- De facto style: 4-space indentation, double quotes for strings
- Line length generally under 100 characters, some exceptions in long strings
- f-strings used throughout for string interpolation
- No Prettier config detected
- Single quotes for string literals
- 2-space indentation
- No semicolons at end of statements (inconsistent -- some files do, some don't; mostly absent)
- Arrow functions for component handlers and callbacks
- ESLint 9 flat config at `frontend/eslint.config.js`
- Plugins: `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, `typescript-eslint`
- TypeScript strict mode enabled in `frontend/tsconfig.app.json` with `noUnusedLocals` and `noUnusedParameters`
- No linting tool configured (no ruff, flake8, pylint, mypy config)
## Import Organization
## Error Handling
## Logging
- `logger.info()` for successful operations: file uploads, metadata extraction, search results
- `logger.warning()` for fallbacks: unknown search mode, failed optional operations
- `logger.error()` for failures: `exc_info=True` added for stack traces on important errors
## Comments
- Module-level docstrings for test files explaining purpose and usage
- Function docstrings on all service functions describing behavior and return values
- Inline comments for non-obvious logic (e.g., "rank is 0-indexed, +1 for 1-based")
- `# comment` on lines doing something unexpected (e.g., `pass  # Storage file may already be gone`)
## Function Design
- Use type hints on all Python function parameters and return values
- Use `str | None` union syntax (Python 3.10+), not `Optional[str]`
- Use `list[dict]` not `List[Dict]` (modern Python generics)
- FastAPI `Depends()` for dependency injection of `user_id` and `settings`
- Python services return `dict`, `list[dict]`, `str`, or Pydantic models
- TypeScript hooks return object destructuring: `{ messages, isStreaming, sendMessage, loadMessages }`
## Module Design
- No barrel file exports; all `__init__.py` files are empty
- Import directly from module: `from services.llm_service import stream_chat_completion`
- Default exports for React components: `export default function ChatContainer`
- Named exports for hooks: `export function useChat`
- Named exports for utilities: `export async function apiFetch`
- Named exports for context providers: `export function AuthProvider`, `export function useAuth`
## Configuration Pattern
## Database Access Pattern
## API Design Pattern
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- React SPA frontend communicates with Python FastAPI backend via REST + SSE
- Backend uses Supabase as combined database, auth, file storage, and realtime provider
- Chat uses an agentic tool-use loop: LLM decides which tools to call, backend executes them, feeds results back to LLM in a while-loop until no more tool calls
- Document ingestion is synchronous (inline processing on upload, no background workers)
- All LLM calls use raw OpenAI SDK (no LangChain/LangGraph) with OpenRouter as the default provider
- Stateless completions: full chat history is loaded from DB and sent with every request
## Layers
- Purpose: User interface for chat and document management
- Location: `frontend/src/`
- Contains: Pages, components, hooks, context providers, API client
- Depends on: Backend API (via `/api` proxy), Supabase JS client (auth + realtime)
- Used by: End users in browser
- Purpose: HTTP endpoints for threads, messages, and documents
- Location: `backend/routers/`
- Contains: `threads.py`, `chat.py`, `documents.py`
- Depends on: Auth middleware (`backend/auth.py`), database client (`backend/database.py`), services layer
- Used by: Frontend via fetch/SSE
- Purpose: Core business logic (LLM, embeddings, retrieval, ingestion, parsing)
- Location: `backend/services/`
- Contains: `llm_service.py`, `embedding_service.py`, `retrieval_service.py`, `ingestion_service.py`, `parsing_service.py`, `metadata_service.py`, `rerank_service.py`, `sql_service.py`, `web_search_service.py`, `subagent_service.py`, `record_manager.py`, `tracing.py`
- Depends on: External APIs (OpenRouter, OpenAI, Tavily), Supabase DB/Storage
- Used by: Routers
- Purpose: Postgres DB with pgvector, file storage, auth, realtime
- Location: `supabase/migrations/` (schema definitions)
- Contains: Tables (`threads`, `messages`, `documents`, `document_chunks`), RPC functions (`match_document_chunks`, `keyword_search_chunks`, `execute_readonly_query`), Storage bucket (`documents`)
- Depends on: Supabase hosted service
- Used by: Backend (via `supabase-py` service role client), Frontend (via `@supabase/supabase-js` anon client for auth + realtime only)
- Purpose: Centralized settings from environment variables
- Location: `backend/config.py`
- Contains: `Settings` class (pydantic-settings), `get_settings()` singleton
- Depends on: `.env` file at repo root
- Used by: All backend modules
## Data Flow
- Backend is stateless -- all state in Supabase DB
- Frontend state: React useState/useCallback hooks in `useChat` and `useDocuments`
- Auth state: `AuthContext` provider wrapping app, reads Supabase session
- No Redux/Zustand -- state is local to pages via hooks
## Key Abstractions
- Purpose: Define LLM-callable tools as OpenAI function-calling JSON schemas
- Location: `backend/routers/chat.py` (constants: `RETRIEVAL_TOOL`, `SQL_TOOL`, `WEB_SEARCH_TOOL`, `ANALYZE_DOCUMENT_TOOL`)
- Pattern: Tools are conditionally included based on user state (has documents?) and config (web search enabled?)
- Purpose: Type-safe configuration from env vars
- Location: `backend/config.py`
- Pattern: `pydantic_settings.BaseSettings` with `@lru_cache` on `get_settings()`. Supports separate providers for chat LLM vs embeddings.
- Purpose: Database and storage access
- Location: `backend/database.py` (backend, service role key), `frontend/src/lib/supabase.ts` (frontend, anon key)
- Pattern: Backend uses service role key (bypasses RLS for server-side operations). Frontend uses anon key (RLS-enforced, auth + realtime only).
- Purpose: Content-addressed deduplication and incremental updates
- Location: `backend/services/record_manager.py`
- Pattern: SHA-256 hashes at file level (duplicate detection) and chunk level (incremental diff). On re-upload of same filename: diff chunks, embed only new ones, re-parent surviving chunks.
- Purpose: Analyze entire documents (not just chunks) via isolated LLM call
- Location: `backend/services/subagent_service.py`
- Pattern: Resolves document by name, reassembles full text from chunks, runs non-streaming completion with dedicated system prompt. Triggered by `analyze_document` tool call.
## Entry Points
- Location: `backend/main.py`
- Triggers: `uvicorn backend.main:app` (or `uvicorn main:app` from `backend/` dir)
- Responsibilities: Creates FastAPI app, sets up CORS, includes routers, configures LangSmith tracing
- Location: `frontend/src/main.tsx` -> `frontend/src/App.tsx`
- Triggers: `npm run dev` (Vite dev server)
- Responsibilities: React app with BrowserRouter, AuthProvider, 3 routes (`/login`, `/`, `/documents`)
- Location: `supabase/migrations/001_create_threads.sql` through `015_execute_readonly_query.sql`
- Triggers: Applied manually via Supabase dashboard or `supabase db push`
- Responsibilities: Schema creation, RLS policies, RPC functions, storage bucket setup
## Error Handling
- Ingestion failures: caught in `process_document()`, document status set to `failed` with `error_message` in DB
- Chat SSE errors: caught in `event_generator()`, yielded as SSE `error` event with error message
- Auth failures: `HTTPException(401)` raised by `get_user_id()` dependency
- Tool execution failures: caught per-tool in `execute_tool()`, returned as JSON `{"error": ...}` to LLM for graceful handling
- Metadata extraction: `extract_metadata_safe()` wraps `extract_metadata()` with fallback to default `DocumentMetadata()`
- SQL execution: `execute_readonly_query` RPC validates query safety (SELECT-only, blocks dangerous keywords), returns error dict on failure
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
