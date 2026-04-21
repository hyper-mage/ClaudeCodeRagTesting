# Technology Stack

**Analysis Date:** 2026-04-03

## Languages

**Primary:**
- TypeScript ~5.9.3 - Frontend (React components, hooks, pages)
- Python 3.x - Backend (FastAPI services, routers, models)

**Secondary:**
- SQL - Supabase migrations (`supabase/migrations/`)

## Runtime

**Environment:**
- Node.js (version not pinned, no `.nvmrc` detected) - Frontend dev server and build
- Python with venv (`backend/venv/`) - Backend API server

**Package Manager:**
- npm - Frontend (`frontend/package.json`, `frontend/package-lock.json` present)
- pip - Backend (`backend/requirements.txt`)

## Frameworks

**Core:**
- React ^19.2.4 - Frontend UI framework
- FastAPI 0.115.12 - Backend API framework
- Vite ^6.4.1 - Frontend build tool and dev server
- Tailwind CSS ^4.2.2 - Utility-first CSS (via `@tailwindcss/vite` plugin)

**Testing:**
- No test framework detected in `frontend/package.json`
- `backend/tests/` directory exists (framework not determined from requirements.txt)

**Build/Dev:**
- Vite ^6.4.1 - Dev server with HMR, production bundler
- `@vitejs/plugin-react` ^4.7.0 - React Fast Refresh support
- TypeScript ~5.9.3 - Type checking (strict mode enabled)
- ESLint ^9.39.4 - Linting with flat config (`frontend/eslint.config.js`)
- uvicorn 0.34.2 - ASGI server for FastAPI

## Key Dependencies

**Critical (Frontend):**
- `@supabase/supabase-js` ^2.99.3 - Supabase client for auth, realtime, storage
- `react-router-dom` ^7.13.1 - Client-side routing
- `react-markdown` ^10.1.0 - Markdown rendering in chat responses
- `lucide-react` ^0.577.0 - Icon library
- `@tailwindcss/typography` ^0.5.19 - Prose styling for rendered markdown

**Critical (Backend):**
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

**Infrastructure:**
- `httpx` (transitive, used directly) - HTTP client for embedding API calls, web search, reranking

## Configuration

**Environment:**
- Single `.env` file at repo root, loaded by both frontend (via Vite `envDir: '..'`) and backend (via `python-dotenv`)
- Frontend reads `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` via `import.meta.env`
- Backend uses `pydantic-settings` (`backend/config.py`) to load all env vars into a `Settings` class
- Settings cached via `@lru_cache` on `get_settings()`

**Build:**
- `frontend/vite.config.ts` - Vite config with React plugin, Tailwind plugin, API proxy to `localhost:8000`
- `frontend/tsconfig.app.json` - TypeScript strict mode, target ES2023, bundler module resolution
- `frontend/eslint.config.js` - Flat ESLint config with typescript-eslint, react-hooks, react-refresh plugins

## TypeScript Configuration

**Strict mode:** Enabled with additional strictness flags:
- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`
- `noUncheckedSideEffectImports: true`
- `erasableSyntaxOnly: true`

**Target:** ES2023
**Module:** ESNext with bundler resolution
**JSX:** react-jsx (automatic runtime)

## Dev Server Setup

**Frontend:** `npm run dev` starts Vite on default port (5173) with proxy:
- `/api/*` requests proxied to `http://localhost:8000`

**Backend:** uvicorn serves FastAPI app on port 8000

**Scripts (frontend):**
- `dev` - Start Vite dev server
- `build` - TypeScript check + Vite production build
- `lint` - Run ESLint
- `preview` - Preview production build

## Platform Requirements

**Development:**
- Node.js (ES2023 target suggests Node 20+)
- Python 3.10+ (uses `X | None` union syntax)
- System dependencies for `docling` (PDF processing, may require additional native libs)

**Production:**
- Supabase project (Postgres + pgvector + Auth + Storage + Realtime)
- OpenAI API key or OpenRouter API key
- Optional: LangSmith API key, Tavily API key, reranking API key

---

*Stack analysis: 2026-04-03*
