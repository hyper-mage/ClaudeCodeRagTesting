# Board Game Knowledge Base RAG

An agentic RAG application for board games. Ask it rules questions, compare mechanics, get recommendations. It searches a pre-seeded knowledge base of popular games plus any private documents you upload, using LLM-driven tool calls to navigate the library transparently (like Claude Code's `ls`, `grep`, `read` tools — visible in the chat UI).

**Live:** https://boardgame-rag-prod.pages.dev

---

## What It Does

- **Chat** — ask questions; the agent decides which tools to call (vector search, keyword search, SQL, web search, full-document analysis, KB explorer)
- **Upload** — drop in PDFs, DOCX, images, XLSX, HTML, Markdown; they're chunked, embedded, and searchable immediately
- **Default KB** — 10 popular board games pre-seeded; visible to all users
- **Private docs** — each user's uploads are isolated via RLS; only they can see them
- **Transparent tool calls** — every tool the agent uses is shown as a badge/card in chat

---

## Prerequisites

- Node.js 20+
- Python 3.10+
- A Supabase project (Postgres + pgvector + Auth + Storage + Realtime)
- OpenRouter API key (LLM + embeddings)
- Optional: LangSmith key (tracing), Tavily key (web search), reranking API key

---

## Local Setup

**1. Clone and configure**

```bash
git clone <repo>
cp .env.example .env   # fill in all values
```

Key `.env` vars:

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` / `VITE_SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` / `VITE_SUPABASE_ANON_KEY` | Public anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend service role key (bypasses RLS) |
| `OPENROUTER_API_KEY` | LLM + embeddings via OpenRouter |
| `LANGSMITH_API_KEY` | Observability (optional) |
| `TAVILY_API_KEY` | Web search tool (optional) |

**2. Apply database migrations**

Run all files in `supabase/migrations/` (001–015) in order via the Supabase SQL editor or `supabase db push`.

**3. Backend**

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**4. Frontend**

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`. API calls proxy to `http://localhost:8000`.

**5. Seed default KB** (optional — skip if using private docs only)

```bash
cd backend
python scripts/seed_default_kb.py
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | React + Vite + Tailwind + shadcn/ui | SPA with fast HMR; Tailwind for utility CSS; shadcn for accessible components |
| **Backend** | Python + FastAPI | Async-native; OpenAPI docs free; easy SSE with `sse-starlette` |
| **Database** | Supabase (Postgres + pgvector) | Vectors and relational data in one place; built-in RLS; no separate vector DB |
| **Auth** | Supabase Auth | JWT-based; anon key safe to ship to frontend; service role key stays on backend |
| **File storage** | Supabase Storage | Co-located with DB; RLS policies apply to buckets |
| **Realtime** | Supabase Realtime | Push ingestion status updates to frontend without polling |
| **LLM** | OpenRouter | Single API key for multiple models; easy model swaps |
| **Embeddings** | OpenRouter (Nemotron) | 2048-dim embeddings; called via raw HTTP (OpenAI SDK has parsing quirk with OpenRouter) |
| **Document parsing** | Docling | Handles PDF, DOCX, XLSX, HTML, images (OCR) → clean Markdown for chunking |
| **Observability** | LangSmith | Trace every LLM call and tool execution |
| **Frontend deploy** | Cloudflare Pages | Free tier; `_redirects` for SPA routing; fast CDN |
| **Backend deploy** | Fly.io | Docker-based; handles Docling native deps; free tier with auto-suspend |

---

## Architecture in 30 Seconds

```
Browser → CF Pages (React SPA)
             │
             └─ /api/* → Fly.io (FastAPI)
                              │
                    ┌─────────┼──────────┐
                    │         │          │
               Supabase   OpenRouter  Tavily
              (DB+auth+    (LLM +    (web search)
               storage)   embed)
```

Agent loop in `backend/routers/chat.py`:
1. Load full thread history from DB
2. Call LLM with tool definitions
3. If tool calls → execute → append results → loop
4. Stream final response via SSE

---

## Test Credentials (dev only)

Email: `ragtest1@gmail.com` / Password: `testpass123`
