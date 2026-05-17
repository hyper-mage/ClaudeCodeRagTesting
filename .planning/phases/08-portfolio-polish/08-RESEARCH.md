# Phase 8: Portfolio Polish - Research

**Researched:** 2026-05-17
**Domain:** Frontend polish + portfolio documentation + Supabase anonymous auth + opportunistic cleanup
**Confidence:** HIGH (locked decisions in CONTEXT.md + UI-SPEC.md remove almost all ambiguity; remaining unknowns verified via official docs and the installed `gotrue==2.12.4` source)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Demo User Model (PORT-01)**
- **D-01 — Identity:** Supabase **anonymous auth**. Every "Try demo" click invokes `supabase.auth.signInAnonymously()` and produces a throwaway anon user with its own `user_id`. RLS continues to isolate per-user data — no shared-account collisions, no shared-password leakage. Requires enabling anonymous sign-ins in the prod Supabase project's **Auth > Providers** panel.
- **D-02 — Starter content per anon user:** On first signin the anon user gets BOTH:
  1. **1–2 seeded sample chat threads** showing good queries (e.g. "Recommend a 2-player strategy game", "Compare Catan vs Carcassonne") — pre-rendered assistant turns OR queued user messages, planner to choose lightest impl.
  2. **One sample private PDF** auto-attached so the anon user immediately sees the private-doc-in-chat experience without uploading anything. Sample doc = **D&D 5e common-rules quick-reference guide** (cheat-sheet style: ability checks, saving throws, advantage/disadvantage, combat actions, conditions). Cross-genre on purpose — showcases that the agent retrieves over *whatever* the user uploads, not just the board-game corpus. Must be small (≤2 MB), sourced from a permissively licensed source (D&D 5e SRD is CC-BY 4.0 / OGL — researcher to confirm preferred source: WotC SRD PDF excerpt vs community CC quick-ref vs original markdown→PDF generated in-repo), and ingested via the standard pipeline so the demo exercises chunking + embeddings + retrieval honestly. README pitch can lean on this as a "cross-domain RAG" data point.
  - Public seeded KB (≥10 board games, `visibility='public'`) is already visible from Phase 3 — no extra work needed for that surface.
- **D-03 — Cleanup:** **Opportunistic purge on next anon signin.** When a new anon-signin lands, fire a backend cleanup that deletes anon users (and their threads, messages, documents, document_chunks, storage objects) created more than **7 days** ago. No external scheduler; cost ≈ a few deletes per signin event.
- **D-04 — Login page:** New "Try demo" CTA on `frontend/src/pages/LoginPage.tsx` rendered prominently above the email/password form.
- **D-05 — Demo-mode UI gating:** **Not added.** Anon users keep the full app (uploads, thread create, deletes) — RLS isolates their data.

**Graceful Error Surface (PORT-02)**
- **D-06 — LLM provider failure UX:** **Both inline + toast.** Failed assistant turn renders as a muted/red error bubble inside the chat thread with the failure reason. Simultaneously a toast appears for transient visibility. The error bubble carries a **Retry** button.
- **D-07 — Retry behavior:** Retry **re-sends the last user message** — deletes the failed assistant placeholder, re-POSTs to the same thread, streams a fresh attempt. No auto-retry / no backoff layer; user controls the cadence.
- **D-08 — Tool-level failure UX (rerank / web_search / analyze_document subagent):** **Silent continue.** Per-tool `try/except` in `backend/routers/chat.py` already returns `{error: ...}` JSON to the LLM and lets the loop proceed without that tool. Sentry (frontend, Phase 7) + LangSmith (backend, Phase 7) already capture these for the developer. **No user-visible indicator** when a non-critical tool fails — the agent still completes the turn.
- **D-09 — Error wording:** Generic + actionable, not technical. (Exact copy locked in UI-SPEC.md Copywriting Contract.)

**README Strategy (PORT-03)**
- **D-10 — README disposition:** **Full portfolio rewrite.** Replace repo-root `README.md` with the portfolio version. Move existing course/masterclass README to `docs/MASTERCLASS.md` and link to it from the new README.
- **D-11 — Required README sections (order):** Title + pitch → Live demo link → Badges row → Hero GIF → What it does → Tech tables → Architecture diagram → Screenshots gallery → Deploy command sequence → Link to docs/MASTERCLASS.md
- **D-12 — Architecture diagram format:** PNG/SVG asset authored in Excalidraw or draw.io. Source file committed to `docs/architecture.{excalidraw,drawio}` alongside `docs/architecture.png` (or `.svg`).
- **D-13 — Tech tables: TWO tables.** Table 1 — Code Stack (`Tech | Role`). Table 2 — Services / Infrastructure (`Service | Link | What it does | How this project uses it`).
- **D-14 — Screenshots + GIF:** Four+ screenshots + one hero GIF under `docs/screenshots/`. Required: login w/ Try-demo, chat w/ tool cards, documents w/ upload, mobile drawer. Hero GIF ~15–20 s at 1280×720.

**Deploy-Status + Uptime Badge (PORT-04)**
- **D-15 — Two badges in README:** (1) UptimeRobot public uptime-ratio badge (30-day window) — UR provides public SVG endpoint per monitor. (2) Last-deploy badge — Fly "deployed" static shield OR GitHub Actions workflow badge OR shields.io version/last-updated badge driven off git tag/commit date. Planner picks simplest path that doesn't require new CI infra.

### Claude's Discretion

- Exact error-bubble component shape (subclass of `MessageBubble` vs a separate `ErrorMessageBubble`) — planner to choose based on existing component patterns.
- Excalidraw vs draw.io — researcher to recommend based on the developer's existing tooling; both are acceptable.
- Hero GIF recording tool — any tool that produces a small (<5 MB) GIF or animated WebP is fine.
- Sample-PDF sourcing for the D&D 5e quick-ref (D-02) — researcher to pick the cleanest licensed source: (a) excerpt of official WotC SRD 5.1 (CC-BY 4.0), (b) existing community CC-licensed quick-reference card, or (c) original markdown→PDF generated in-repo at `data/sample-private-docs/dnd5e-quickref.md` rendered via Docling-compatible converter. Must include license attribution embedded in the PDF metadata and in `docs/CREDITS.md`.
- Sample-thread seed strategy (DB seed of `messages` rows vs first-launch UI hint) — planner to pick the simpler/cleaner option.

### Deferred Ideas (OUT OF SCOPE)

- **Demo-mode UI gating** (read-only chat for anon users) — explicitly rejected (D-05).
- **Scheduled-cron purge of anon users** — deferred in favor of opportunistic-on-signin (D-03).
- **Public UptimeRobot status page** — rejected in Phase 7.
- **Auto-retry with exponential backoff** on transient LLM errors — rejected (D-07).
- **Linking anon user → permanent account** on signup (`linkIdentity()`) — Supabase supports it; not in v1.1 scope.
- **Backend Sentry SDK** — still deferred (carried from Phase 7).
- **Tool-failure user-visible note** (per-tool warning in assistant message) — rejected (D-08).

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PORT-01 | Anonymous visitor can log in as a seeded demo user with one click on the login page ("Try demo" button), skipping signup — credentials are shared and documented | §Standard Stack / §Pattern 1 (anon auth flow) / §Pattern 2 (bootstrap endpoint) / §Pitfall 1 (JWT `aud` claim mismatch) / §Pitfall 6 (cleanup cascade order) — D-01..D-05 + UI-SPEC Surface 1 + Surface 3 |
| PORT-02 | LLM provider error renders a graceful error message; tool failures are silent backend-only | §Pattern 3 (error bubble + toast dual surface) / §Pattern 4 (retry re-send last user message) / §Pattern 5 (Sentry captureException for caught errors) / §Pitfall 3 (DB persists pre-error assistant row — duplicate-on-retry hazard) — D-06..D-09 + UI-SPEC Surface 2 |
| PORT-03 | README contains live URL, demo creds, architecture diagram, deploy sequence, screenshots/GIF, pitch | §Pattern 6 (README skeleton from D-11) / §Pattern 7 (Excalidraw recommended over drawio) / §Pattern 8 (ScreenToGif for hero GIF on Windows) / §Code Examples (badge markdown, sample tech tables) — D-10..D-14 |
| PORT-04 | README displays a deploy-status badge reflecting current deployment health | §Pattern 9 (shields.io UR ratio badge — exact URL pattern) / §Pattern 10 (last-deploy badge — recommend `last-commit` shields.io badge as zero-infra fallback) — D-15 |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

| Constraint | Source | Phase-8 implication |
|------------|--------|---------------------|
| Python backend must use a `venv` virtual environment | CLAUDE.md > Rules | Any new backend script (anon-cleanup, bootstrap endpoint) runs from `backend/venv`. |
| No LangChain / no LangGraph — raw SDK calls only | CLAUDE.md > Rules | Bootstrap endpoint uses `supabase-py` directly (already in use); no agent framework. |
| Use Pydantic for structured LLM outputs | CLAUDE.md > Rules | If bootstrap pre-generates sample assistant text we hand-write it as static content (no LLM call needed); if planner chooses to LLM-generate seed turns, route through `extract_metadata_safe` pattern. |
| All tables need Row-Level Security | CLAUDE.md > Rules | Anon users get the `authenticated` Postgres role with `auth.uid()` populated — existing RLS policies apply unchanged. Verified. |
| Stream chat responses via SSE | CLAUDE.md > Rules | Unchanged. Error path stays inside the existing SSE generator's `try/except`. |
| Use Supabase Realtime for ingestion status updates | CLAUDE.md > Rules | Sample-PDF seed for an anon user will use the standard `process_document` pipeline, so Realtime status updates fire automatically. |
| Module 2+ uses stateless completions — store and send chat history yourself | CLAUDE.md > Rules | Sample-thread seed must persist `messages` rows directly so on first chat the LLM sees them in history. |
| Ingestion is manual file upload only — no connectors or automated pipelines | CLAUDE.md > Rules | Sample PDF is bootstrapped server-side as a *seed* (analogous to `seed_default_kb.py` — public seed pattern). Same pattern, different `user_id` (anon's). Does not constitute a connector. |
| Plans saved to `.agent/plans/` | CLAUDE.md > Planning | Plans live in `.planning/phases/08-portfolio-polish/` per GSD convention; CLAUDE.md `.agent/plans/` is a separate dev-flow directory not used by GSD. No conflict. |
| Test credentials `ragtest1@gmail.com` / `testpass123` | CLAUDE.md > Test Credentials | Used for the "permanent-user login" path verification screenshot. Anon-user path uses no credentials. |

## Summary

Phase 8 is a polish-and-ship phase: four deliverables (PORT-01 anonymous demo, PORT-02 graceful chat errors, PORT-03 portfolio README, PORT-04 deploy/uptime badges) atop a fully-verified codebase from phases 1–7. CONTEXT.md and UI-SPEC.md lock essentially every visible-behavior decision — the research task is to **resolve external integration unknowns** (Supabase anon-auth wire shape, UptimeRobot badge URL, cleanup SQL/API path) and surface the one **CRITICAL pitfall** (the backend JWT verifier in `backend/auth.py` hard-codes `audience="authenticated"` and the project documentation for anon JWTs is ambiguous on the `aud` claim — must be empirically verified against a real anon JWT before the planner commits to "no backend changes for D-01").

There are no greenfield architectural decisions, no new frameworks, no library churn. Every paired-library choice already exists in the codebase (`@sentry/react`, `slowapi`, `supabase-js`, `supabase-py`, `lucide-react`, `react-router-dom`, the in-house `ToastProvider`). The work is small, mechanical, and well-scoped — but two integration seams (anon-JWT `aud` claim + cleanup cascade order) and one documentation-asset workflow (Excalidraw source + PNG export + git commit) carry implementation risk if mis-handled. Those are flagged explicitly below.

**Primary recommendation:** Plan PORT-01 and PORT-02 first (they're the load-bearing UI work). Slot PORT-03 (README rewrite) and PORT-04 (badges) into the same phase but as documentation tasks that depend on PORT-01/02 landing first (the screenshots and GIF need the new UI). For PORT-01: **verify the anon-JWT `aud` claim against the prod Supabase project before assuming `backend/auth.py` works unchanged** — this is the single most likely source of a deploy-breaking surprise.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `signInAnonymously()` call | Browser / Client | — | Supabase JS SDK call lives in the React tree (LoginPage), produces a JWT in browser session storage. Backend never initiates. |
| Anon-mode `is_anonymous` flag for UI gating | Browser / Client | — | Surfaced from the existing `User` object in `AuthContext`; no backend roundtrip needed. |
| `/api/demo/bootstrap` endpoint (cleanup + seed) | API / Backend | Database / Storage | Service-role operations (admin list/delete users, write to `documents`/`messages` tables) must happen server-side — anon JWT can't bypass RLS to seed system content. |
| Anonymous user cleanup (>7d purge) | API / Backend | Database / Storage | Same as above — `auth.admin.delete_user()` requires service role. Cascade-delete of child rows (documents, chunks, threads, messages, storage objects) happens via explicit SQL since FKs are NOT `ON DELETE CASCADE` to `auth.users`. |
| Sample-PDF ingestion for anon user | API / Backend | Database / Storage | Reuses existing `process_document()` pipeline; runs synchronously inside bootstrap endpoint. |
| Error bubble + toast UI | Browser / Client | — | Catches errors at the SSE-stream reader inside `useChat.ts`; UI-only. |
| Retry handler | Browser / Client | API / Backend | Browser re-POSTs `/api/threads/{id}/messages` with the last user content; backend treats it as a fresh send. |
| Sentry exception capture for chat errors | Browser / Client | — | `Sentry.captureException(err)` inside the catch block — `@sentry/react` global handlers don't auto-capture **caught** exceptions. |
| LangSmith tool-failure trace | API / Backend | — | Already auto-captured via `@traceable` on `send_message`; no Phase-8 work. |
| README + docs/ documentation | Documentation (file system) | — | Static markdown + image assets; no runtime tier. |
| UptimeRobot badge SVG | CDN / Static (UptimeRobot SVG endpoint) | — | External SVG served by UptimeRobot or shields.io; README embeds via markdown image syntax. |
| Last-deploy badge | CDN / Static (shields.io endpoint) | — | shields.io `last-commit` against GitHub repo — zero infrastructure. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@supabase/supabase-js` | `^2.99.3` (installed); `signInAnonymously` available since `v2.43.x` `[VERIFIED: frontend/package.json + npm registry]` | Anon auth + anon user session lifecycle | Already used everywhere else for auth; `signInAnonymously()` is a 1-line call that fits the existing `signInWithPassword` adjacent in LoginPage. |
| `gotrue` (Python, transitive via `supabase` 2.13.0) | `2.12.4` `[VERIFIED: backend/venv/Lib/site-packages/gotrue-2.12.4.dist-info/]` | `auth.admin.list_users()` + `auth.admin.delete_user()` for the cleanup loop | Already installed (transitive). `User.is_anonymous: bool = False` field exists on the Pydantic model; `User.created_at: datetime` exists. Pagination via `page: int, per_page: int` arguments. |
| `@sentry/react` | `^10.53.1` `[VERIFIED: frontend/package.json]` | `Sentry.captureException(err)` inside the new chat-error catch block | Already initialized in `frontend/src/lib/sentry.ts` with PII scrub. Auto-captures only **uncaught** errors; **caught** errors (the chat error path) need explicit `captureException`. |
| `lucide-react` | `^0.577.0` `[VERIFIED: frontend/package.json]` | `AlertCircle` (error bubble) + `RotateCw` (retry button) + `Sparkles` (try-demo CTA, optional) | Already used in `IconSidebar`, `MobileTopBar`, `FileUpload`. No new icon-set dependency. |
| In-house `ToastProvider` | `frontend/src/contexts/ToastContext.tsx` `[VERIFIED: file exists, supports `error` variant with red ramp, `aria-live="polite"`, `role="status"`, 4s auto-dismiss]` | Toast for chat error | UI-SPEC Surface 2 explicitly mandates reuse — no new toast library. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Existing `backend/scripts/seed_default_kb.py` pattern | n/a (template, not a library) | Per-anon-user sample-doc seeder | Copy/adapt to a new `backend/scripts/seed_anon_demo_content.py` OR inline into the `/api/demo/bootstrap` endpoint. Same `hash_content` + storage upload + `process_document` pipeline; user_id is the anon's UUID instead of `SYSTEM_USER_ID`. |
| `slowapi` (already in `backend/requirements.txt` 0.1.9) | `0.1.9` `[VERIFIED: requirements.txt]` | Rate limit the `/api/demo/bootstrap` endpoint | Same `Limiter` instance already on `app.state.limiter`. Suggested cap: `"5/minute"` per IP (anon-bootstrap doesn't have a user_id yet — IP key is appropriate for this single endpoint, contrary to D-04 of Phase 6 which forbade IP-keying for `/api/chat`). |
| Excalidraw (web app, no install) | n/a — use [excalidraw.com](https://excalidraw.com) `[CITED: https://excalidraw.com]` | Architecture diagram authoring | Hand-drawn aesthetic preferred for portfolio polish; exports PNG + saves `.excalidraw` JSON for git. |
| ScreenToGif (Windows native, free) | latest stable `[CITED: https://www.screentogif.com]` | Hero GIF capture | Built-in editor for frame-trim + color-palette reduction → keeps file under 5 MB. Confirmed available on Windows (current dev platform). |
| shields.io | n/a — static SVG endpoint | UptimeRobot badge + last-deploy badge | No install. Markdown `![alt](https://img.shields.io/...)`. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Excalidraw | draw.io (diagrams.net) `[CITED: https://app.diagrams.net]` | draw.io is more precision-oriented (snap-to-grid, vendor stencils, layers); Excalidraw is faster for portfolio sketches and has stronger 2026 mindshare in dev portfolios. **Recommendation: Excalidraw** — fits the polish-not-precision goal, simpler file format (.excalidraw JSON), one-click PNG export. Either works; do not block on the choice. |
| ScreenToGif | Kap (macOS-only) / LICEcap (cross-platform) | Kap is Mac-only — irrelevant on Windows. LICEcap is older and lacks the frame editor that lets us hit the <5 MB target. **Stick with ScreenToGif on Windows.** |
| shields.io UR ratio badge | UptimeRobot's own per-monitor "Public Badge" feature (badge.uptimerobot.com) | The native UR badge is also a public SVG URL, but enabling it on the dashboard exposes a per-monitor public read URL. UptimeRobot's docs are sparse on whether this discloses additional dashboard data. **Recommendation: use shields.io endpoint** — better-known URL pattern, no UR account-side configuration, doesn't risk side-effects on the existing monitor config from Phase 7. |
| GitHub Actions workflow status badge | shields.io `last-commit` badge | This repo has **no `.github/workflows/` directory** `[VERIFIED: ls .github/ failed]`. Standing up a CI workflow just to get a badge is over-engineering for Phase 8 scope. **Recommendation: shields.io `last-commit` badge** — `![last commit](https://img.shields.io/github/last-commit/{owner}/{repo})` — zero infrastructure, accurately reflects "when did this codebase last change", which is the spirit of D-15. If a CI workflow lands later (separate phase), swap to the workflow-status badge. |
| Tabyltop CC-SRD (D&D 5e quick-ref source) | Original markdown handwritten in-repo at `data/sample-private-docs/dnd5e-quickref.md` | Tabyltop's repo `[CITED: https://github.com/Tabyltop/CC-SRD]` has full SRD as markdown/JSON/HTML but **no condensed quick-reference cheat sheet** — only full SRD. To get a ≤2 MB quick-ref we'd have to excerpt anyway. **Recommendation: option (c) from CONTEXT.md** — handwrite ~500-line `dnd5e-quickref.md` covering ability checks / saving throws / advantage / actions / conditions, with the required CC-BY 4.0 attribution. Docling ingests `.md` directly, so a PDF render is **not required** (eliminates one step). |
| PDF for the sample doc | Markdown ingested directly | Docling already handles `.md` natively (`backend/services/parsing_service.py` supports it; `seed_default_kb.py` uploads markdown with `content-type: text/markdown`). **Recommendation: ship as `.md`** — same retrieval surface, smaller file, simpler authoring, no PDF toolchain. README pitch can still say "auto-attached D&D 5e quick-reference"; format is not user-visible. |

**Installation:**
```bash
# No new npm dependencies
# No new pip dependencies
# Both anon-auth and graceful-error work uses libraries already on the lockfile.
```

**Version verification:**
```bash
npm view @supabase/supabase-js version
# 2.105.4 — current; installed ^2.99.3 covers signInAnonymously (added v2.43.x).
# No upgrade needed.
```

## Architecture Patterns

### System Architecture Diagram

```
                       ┌──────────────────────────────────────────┐
                       │  Visitor's browser (Cloudflare Pages SPA)│
                       └──────────────┬───────────────────────────┘
                                      │
                         [Click "Try the demo"]
                                      │
              ┌───────────────────────▼─────────────────────────┐
              │ supabase.auth.signInAnonymously()               │ ← @supabase/supabase-js
              │ → returns Session + anon User w/ is_anonymous=t │
              └───────────────────────┬─────────────────────────┘
                                      │
                              [Session JWT in localStorage]
                                      │
              ┌───────────────────────▼─────────────────────────┐
              │ POST /api/demo/bootstrap  (with anon JWT)       │
              └───────────────────────┬─────────────────────────┘
                                      │
                  ┌───────────────────┴──────────────────┐
                  │                                      │
                  ▼ Fly backend                          ▼ Fly backend
        ┌────────────────────┐                  ┌──────────────────────────┐
        │ Cleanup (best-     │                  │ Seed for THIS user:      │
        │ effort, async):    │                  │   1. upload sample md    │
        │  for each anon     │                  │      to Supabase Storage │
        │  user older than   │                  │   2. insert documents row│
        │  7d → cascade-     │                  │   3. process_document()  │
        │  delete child rows │                  │      → chunks + embeds   │
        │  → auth.admin.     │                  │   4. insert sample       │
        │  delete_user(id)   │                  │      thread + 1 msg pair │
        └─────────┬──────────┘                  └────────┬─────────────────┘
                  │                                      │
                  └──────────────┬───────────────────────┘
                                 ▼
                       ┌───────────────────────┐
                       │ navigate('/')         │ ← browser
                       └─────────┬─────────────┘
                                 ▼
                  Visitor lands in chat w/ seeded thread + PDF.
                  Anon-mode "Demo" pill visible in sidebar/topbar.

                  ⟦ Chat happy path: unchanged from Phase 1–7 ⟧

                  ⟦ Chat error path: ⟧
                  ─────────────────────────────────────
                  SSE stream fails inside useChat.sendMessage
                  →   useChat catch block:
                        a) replace empty assistant placeholder with
                           {role:'error', content:'<locked copy>'}
                        b) showToast('<locked copy>', 'error')
                        c) Sentry.captureException(err)    ← MUST add
                  →   ErrorMessageBubble renders w/ Retry button
                  →   User clicks Retry:
                        a) remove error bubble from messages[]
                        b) sendMessage(lastUserMessage.content)
                        c) backend treats it as a fresh POST
                           (BEWARE: previous assistant row was
                            committed at chat.py:564 BEFORE the error
                            — so the new POST creates a *second*
                            assistant row; planner must address)
                  ─────────────────────────────────────
```

### Recommended Project Structure

```
.
├── README.md                              # PORT-03 — full rewrite
├── docs/                                  # NEW directory
│   ├── MASTERCLASS.md                     # archived course README (D-10)
│   ├── CREDITS.md                         # CC-BY 4.0 attribution for D&D 5e SRD
│   ├── architecture.excalidraw            # source file
│   ├── architecture.png                   # exported asset (referenced by README)
│   └── screenshots/
│       ├── 01-login-try-demo.png
│       ├── 02-chat-tool-cards.png
│       ├── 03-documents-upload.png
│       ├── 04-mobile-drawer.png
│       └── 05-hero.gif                    # 1280×720, ≤5 MB
├── data/
│   ├── default-kb/                        # existing 10 board games
│   └── sample-private-docs/               # NEW
│       └── dnd5e-quickref.md              # handwritten ≤500 lines + CC-BY attribution
├── backend/
│   ├── routers/
│   │   ├── ...existing
│   │   └── demo.py                        # NEW — /api/demo/bootstrap
│   ├── services/
│   │   └── demo_service.py                # NEW — cleanup + seed logic
│   └── scripts/
│       └── ...existing (no new script needed if logic lives in service)
└── frontend/
    └── src/
        ├── pages/LoginPage.tsx            # MODIFY — Try-demo CTA + bootstrap call
        ├── hooks/useChat.ts               # MODIFY — error catch → bubble + toast + Sentry
        ├── contexts/AuthContext.tsx       # MODIFY — surface isAnon
        ├── components/
        │   ├── ErrorMessageBubble.tsx     # NEW — recommended sibling component
        │   ├── ChatContainer.tsx          # MODIFY — wire onRetry, anon empty-state copy
        │   ├── IconSidebar.tsx            # MODIFY — Demo pill above LogOut
        │   └── MobileTopBar.tsx           # MODIFY — Demo pill in right slot
        └── lib/api.ts                     # no change
```

### Pattern 1: Anonymous Sign-In + Bootstrap (PORT-01)

**What:** One-click anonymous identity creation + opportunistic cleanup of stale anon data + per-user starter-content seed, all triggered by clicking "Try the demo".

**When to use:** On every "Try the demo" click. Bootstrap is idempotent — a returning anon (session restored from localStorage) does NOT re-bootstrap; the LoginPage only fires it when `signInAnonymously()` is what created the session.

**Frontend flow (LoginPage handler):**
```typescript
// Source: combines official Supabase JS docs + existing LoginPage.handleSubmit pattern
// CITED: https://supabase.com/docs/guides/auth/auth-anonymous
async function handleTryDemo() {
  setLoading(true)
  setError('')
  try {
    const { data, error } = await supabase.auth.signInAnonymously()
    if (error) throw error
    if (!data.session) throw new Error('No session returned')

    // Bootstrap: seed sample content + opportunistic cleanup
    await apiFetch('/api/demo/bootstrap', { method: 'POST' })

    navigate('/', { replace: true })
  } catch (err) {
    setError("Couldn't start the demo. Please try again.")  // locked copy per UI-SPEC
  } finally {
    setLoading(false)
  }
}
```

**Backend flow (`/api/demo/bootstrap`):**
```python
# Source: combines existing seed_default_kb.py pattern + Supabase docs cleanup SQL
# CITED: https://supabase.com/docs/guides/auth/auth-anonymous (cleanup SQL)
# VERIFIED: gotrue-2.12.4 admin API signatures
from fastapi import APIRouter, Depends, BackgroundTasks
from auth import get_user_id
from limiter import limiter
from services.demo_service import seed_anon_user_content, purge_stale_anon_users

router = APIRouter(prefix="/api/demo", tags=["demo"])

@router.post("/bootstrap")
@limiter.limit("5/minute")  # rate limit per IP — anon abuse mitigation (locked in CONTEXT D-03 spirit)
async def bootstrap(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id),
):
    """Seed sample content for the calling anon user + opportunistically purge >7d anon users."""
    # 1. Idempotency check — if user already has a seeded doc, skip seed (re-login returning anon)
    seeded = seed_anon_user_content(user_id)  # returns True if seeded, False if already exists

    # 2. Cleanup runs in background — never blocks signin
    background_tasks.add_task(purge_stale_anon_users, retention_days=7)

    return {"seeded": seeded}
```

**Cleanup function pattern (in `services/demo_service.py`):**
```python
# Source: Supabase docs cleanup SQL pattern adapted to gotrue admin API.
# CITED: https://supabase.com/docs/guides/auth/auth-anonymous#automatic-cleanup
# VERIFIED: gotrue _sync/gotrue_admin_api.py — list_users(page, per_page), delete_user(id)
# VERIFIED: gotrue/types.py — User.is_anonymous: bool, User.created_at: datetime
from datetime import datetime, timezone, timedelta
from database import get_supabase

def purge_stale_anon_users(retention_days: int = 7) -> int:
    """Best-effort delete of anon users older than retention_days, cascading child rows.

    Returns the count deleted. Swallows per-user errors so one bad row doesn't
    abort the loop. Logs failures.
    """
    db = get_supabase()
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = 0

    # Pagination — anon users on a portfolio site stay small; one page usually covers it.
    page = 1
    while True:
        users = db.auth.admin.list_users(page=page, per_page=100)
        if not users:
            break
        for u in users:
            if u.is_anonymous and u.created_at < cutoff:
                try:
                    _cascade_delete_user_data(db, u.id)
                    db.auth.admin.delete_user(u.id)  # hard delete
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to purge anon user {u.id}: {e}")
        if len(users) < 100:
            break
        page += 1
    return deleted

def _cascade_delete_user_data(db, user_id: str) -> None:
    """Delete user-owned rows BEFORE deleting the auth.users row.

    Existing migrations do NOT have ON DELETE CASCADE on user_id → auth.users(id),
    so explicit ordered delete is mandatory.
    """
    # Storage objects first (file system side effect)
    try:
        objs = db.storage.from_('documents').list(f"{user_id}/")
        if objs:
            paths = [f"{user_id}/{o['name']}" for o in objs]
            db.storage.from_('documents').remove(paths)
    except Exception as e:
        logger.warning(f"storage remove failed for {user_id}: {e}")

    # DB rows — child-first to satisfy FK constraints
    db.table('document_chunks').delete().eq('user_id', user_id).execute()
    db.table('documents').delete().eq('user_id', user_id).execute()
    db.table('folders').delete().eq('user_id', user_id).execute()
    db.table('messages').delete().eq('user_id', user_id).execute()
    db.table('threads').delete().eq('user_id', user_id).execute()
```

**Seed function pattern:**
```python
def seed_anon_user_content(user_id: str) -> bool:
    """Idempotently seed sample PDF + sample thread for an anon user.
    Returns True if seeded, False if user already had seed content.
    """
    db = get_supabase()

    # Idempotency: skip if any document or thread already exists for this user
    existing_doc = db.table('documents').select('id').eq('user_id', user_id).limit(1).execute()
    if existing_doc.data:
        return False  # already bootstrapped

    # Seed the D&D 5e quick-ref markdown (mirrors seed_default_kb.py shape)
    file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data',
                             'sample-private-docs', 'dnd5e-quickref.md')
    with open(file_path, 'rb') as f:
        file_bytes = f.read()
    # ... [hash_content + storage upload + insert documents row + process_document]
    # (Exact body mirrors backend/scripts/seed_default_kb.py:91-134, scoped to `user_id`
    #  and visibility='private')

    # Seed sample thread with one user/assistant message pair
    thread = db.table('threads').insert({
        'user_id': user_id,
        'title': 'Welcome to the demo',
    }).execute()
    thread_id = thread.data[0]['id']

    db.table('messages').insert([
        {
            'thread_id': thread_id,
            'user_id': user_id,
            'role': 'user',
            'content': 'What 2-player strategy games do you have in the library?',
        },
        {
            'thread_id': thread_id,
            'user_id': user_id,
            'role': 'assistant',
            'content': (
                "I can search across both the seeded board game library and the D&D 5e "
                "quick-reference that's auto-attached to your account. Want me to start with "
                "two-player strategy picks like **Catan** or **Carcassonne**, or compare "
                "mechanics across the library?"
            ),
            'tools_used': None,
        },
    ]).execute()
    return True
```

### Pattern 2: Anon-Mode `isAnon` Surface in AuthContext

**What:** Surface `is_anonymous` from the Supabase `User` object so UI components can branch on it.

```typescript
// Source: existing AuthContext.tsx pattern + Supabase User type
// VERIFIED: gotrue/types.py shows is_anonymous: bool = False (Python; same field on JS User type)
interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  isAnon: boolean              // NEW
  signOut: () => Promise<void>
}

// inside AuthProvider:
const isAnon = user?.is_anonymous ?? false
return (
  <AuthContext.Provider value={{ user, session, loading, isAnon, signOut }}>
    {children}
  </AuthContext.Provider>
)
```

### Pattern 3: Error Bubble + Toast (PORT-02)

**What:** Dual-surface error rendering — persistent inline bubble + ephemeral toast — fired from a single catch point in `useChat.sendMessage`.

**Recommended component shape:** New sibling component `ErrorMessageBubble.tsx` (NOT a third role on `MessageBubble`). Rationale: `MessageBubble` already branches on `role` for layout (`justify-end` / `justify-start`) and content rendering (markdown vs plain text); adding a third branch with structurally different content (icon + body + button) bloats one component for negligible code savings vs. a focused 40-line sibling.

```typescript
// frontend/src/components/ErrorMessageBubble.tsx — NEW
// Source: bespoke; visual contract from UI-SPEC Surface 2
import { AlertCircle, RotateCw } from 'lucide-react'

interface Props {
  onRetry: () => void
  isRetryDisabled: boolean
}

export default function ErrorMessageBubble({ onRetry, isRetryDisabled }: Props) {
  return (
    <div className="flex justify-start mb-4" role="alert">
      <div className="max-w-[85%] md:max-w-[70%] px-4 py-3 rounded-lg bg-red-950/40 border border-red-700 text-gray-100">
        <div className="flex items-start gap-2 mb-3">
          <AlertCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm leading-[1.5]">
            The assistant ran into a problem. Try again, or rephrase your question.
          </p>
        </div>
        <button
          type="button"
          onClick={onRetry}
          disabled={isRetryDisabled}
          className="inline-flex items-center gap-1 px-3 py-2.5 md:py-1.5 rounded text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RotateCw size={14} />
          Retry
        </button>
      </div>
    </div>
  )
}
```

**Wiring in `useChat.ts`:**
```typescript
// Modify the catch block at useChat.ts:188-195
import { useToast } from '../contexts/ToastContext'
import { Sentry } from '../lib/sentry'

// inside useChat:
const { showToast } = useToast()
const lastUserMessageRef = useRef<string>('')  // remember for retry

// inside sendMessage, just before sendMessage's main try:
lastUserMessageRef.current = content

// REPLACE the existing catch block (L188-195):
} catch (err) {
  if (err instanceof DOMException && err.name === 'AbortError') return
  console.error('Chat error:', err)
  Sentry.captureException(err)                    // NEW — Sentry doesn't auto-capture caught errors
  showToast("The assistant didn't respond. Tap the message to retry.", 'error')
  // Replace empty assistant placeholder with an error sentinel (NOT a delete)
  setMessages(prev =>
    prev.map(m =>
      m.id === assistantId
        ? { ...m, role: 'error' as const, content: '__chat_error__' }
        : m
    )
  )
}

// NEW callback:
const retryLastUserMessage = useCallback(() => {
  if (isStreaming) return
  if (!lastUserMessageRef.current) return
  // Remove error sentinel(s)
  setMessages(prev => prev.filter(m => m.role !== 'error'))
  sendMessage(lastUserMessageRef.current)
}, [isStreaming, sendMessage])

return { messages, setMessages, isStreaming, sendMessage, loadMessages, cancel, retryLastUserMessage }
```

**Wiring in `ChatContainer.tsx`:** add a render branch that picks `ErrorMessageBubble` over `MessageBubble` when `msg.role === 'error'` and threads through `onRetry={retryLastUserMessage}` from props.

### Pattern 4: Anon-Mode "Demo" Badge

**What:** A small amber pill rendered when `useAuth().isAnon === true`. Three render sites: desktop `IconSidebar` (above Sign Out), drawer `IconNavRow` (same), mobile `MobileTopBar` (right slot replacing the existing spacer).

**Component (inline JSX, no separate file needed):**
```tsx
// Locked classes from UI-SPEC:
<span
  aria-label="Demo account"
  title="You're using a temporary demo account. Data is cleared after 7 days."
  className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30"
>
  Demo
</span>
```

### Pattern 5: README skeleton (PORT-03 D-11)

**File:** `README.md` at repo root — full rewrite per D-10.

**Skeleton (sections in locked order):**
```markdown
# Board Game Knowledge Base RAG

A production-deployed agentic RAG that searches and reasons over a board-game knowledge base — with Claude-Code-inspired tooling (ls / tree / grep / glob / read), transparent tool-call cards, and cross-domain retrieval over user-uploaded private docs.

**[Try the demo (no signup) →](https://boardgame-rag-prod.pages.dev)**

[![Uptime](https://img.shields.io/uptimerobot/ratio/m{MONITOR_ID})](https://boardgame-rag-prod.pages.dev)
[![Last commit](https://img.shields.io/github/last-commit/{owner}/{repo})](https://github.com/{owner}/{repo}/commits/main)

![Hero](docs/screenshots/05-hero.gif)

## What it does

(≤6 lines)

## Code Stack

| Tech | Role |
|------|------|
| React 19 + TypeScript + Vite + Tailwind 4 | SPA frontend with HMR + strict types |
| FastAPI + Python 3.11 | Backend API + SSE streaming |
| pgvector + ltree (Supabase Postgres) | Vector retrieval + folder-tree KB |
| OpenAI SDK (raw, no LangChain) | LLM chat completions + embeddings |
| Docling | PDF / DOCX / HTML / Markdown parsing |
| Pydantic + pydantic-settings | Typed config + structured LLM outputs |
| Server-Sent Events (`sse-starlette`) | Token-by-token streaming + tool-call events |
| slowapi | Per-user rate limit on `/api/chat` |
| `@sentry/react` | Frontend error capture (prod only) |
| `langsmith` | Backend trace observability |

## Services / Infrastructure

| Service | Link | What it does | How this project uses it |
|---------|------|--------------|--------------------------|
| Cloudflare Pages | [pages.cloudflare.com](https://pages.cloudflare.com) | Static frontend hosting + global CDN | Hosts the Vite SPA at `boardgame-rag-prod.pages.dev`; SPA deep-link routing via `_redirects` |
| Fly.io | [fly.io](https://fly.io) | Container hosting w/ auto-suspend | Hosts the FastAPI backend at `boardgame-rag-prod.fly.dev`; free-tier suspend on idle |
| Supabase | [supabase.com](https://supabase.com) | Postgres + pgvector + Auth + Storage + Realtime | DB schema (with RLS), JWT auth (incl. anonymous sign-ins for the demo button), object storage for uploads, Realtime for ingestion status |
| OpenRouter | [openrouter.ai](https://openrouter.ai) | LLM gateway w/ unified API | Routes chat completions through `openai/gpt-oss-120b:free` by default; one-env-var swap to paid models |
| Sentry | [sentry.io](https://sentry.io) | Frontend error tracking w/ source maps | Captures uncaught frontend errors + chat error path; PII-scrubbed (no JWTs, no email) |
| LangSmith | [smith.langchain.com](https://smith.langchain.com) | LLM trace observability | Captures every chat tool-call chain to project `boardgame-rag-prod` |
| UptimeRobot | [uptimerobot.com](https://uptimerobot.com) | Uptime monitoring | Pings `/api/health` and SPA root every 5 min; OBS-04 side effect keeps Supabase project alive |
| GitHub | [github.com](https://github.com) | Source hosting | Repo + last-commit badge |

## Architecture

![Architecture](docs/architecture.png)

[Edit in Excalidraw](docs/architecture.excalidraw)

## Screenshots

(grid)

## Deploy

```bash
# Backend
docker build -t boardgame-rag-prod .
flyctl deploy

# Frontend
cd frontend && npm run build && npx wrangler pages deploy dist
```

## Built for

The capstone for the [AI Automators Claude Code Masterclass](https://www.theaiautomators.com/). See [docs/MASTERCLASS.md](docs/MASTERCLASS.md) for course context.
```

### Pattern 6: Architecture diagram nodes

**Excalidraw nodes to draw (left-to-right, top-down):**

```
Browser ──→  Cloudflare Pages CDN  ──→  React SPA
                                            │
                                            │ /api/* (XHR + SSE)
                                            ▼
                                  Fly.io  (boardgame-rag-prod)
                                     FastAPI + Docling
                                            │
                ┌───────────────────────────┼───────────────────────────┐
                │                           │                           │
                ▼                           ▼                           ▼
       Supabase (Postgres        OpenRouter (LLM             Optional: Tavily
       + pgvector + Auth         gateway — gpt-oss          (web search tool
       + Storage + Realtime)     :free default)              for explore_kb)
                │
                └─→ auth.users, threads, messages, documents,
                    document_chunks, folders, storage.documents/

       Observability fan-out:
            • Sentry (frontend errors, source maps)
            • LangSmith (backend traces, project=boardgame-rag-prod)
            • UptimeRobot (5-min ping → /api/health + SPA root)
```

### Anti-Patterns to Avoid

- **Calling `signInAnonymously()` without the `is_anonymous` guard on `/api/demo/bootstrap`.** A permanent user calling the endpoint should be a no-op (or 403). The endpoint MUST verify the JWT shows `is_anonymous=true` before seeding — otherwise a permanent user could accidentally get a sample D&D PDF jammed into their library every login.
- **`Sentry.setUser({...})` with the anon user_id.** The Phase 7 PII contract says no user attachment. Reset to anonymous on every signin: do not change Sentry user attachment in Phase 8.
- **Using shadcn `<Toaster />` or installing `sonner`/`react-hot-toast`.** UI-SPEC explicitly forbids new toast libs; the existing `ToastProvider` covers the use case.
- **Generating sample assistant text with an LLM call inside the bootstrap endpoint.** Adds cost + latency to the demo signin. Hard-code a static welcome message in the seed function instead.
- **Skipping the storage-object delete in the cleanup cascade.** Storage objects under `documents/{user_id}/` will outlive the auth row and leak free-tier storage. Delete the storage prefix BEFORE deleting the DB rows.
- **Treating the bootstrap call as blocking-for-cleanup.** Cleanup is opportunistic and slow (paginated `list_users`); run it via `BackgroundTasks` so the demo signin returns in <2 s even when cleanup has work to do.
- **Storing the last-user-message in component state.** Use a `useRef` instead — React state captures stale closures inside the catch block; a ref is always current.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Anonymous user creation | Custom guest-user table + UUID generation | `supabase.auth.signInAnonymously()` | Already produces a real `auth.users` row with the same JWT shape as a permanent user — your RLS policies, JWT verifier, and frontend hooks work unchanged. |
| Bulk anon-user delete | Raw `delete from auth.users` over psycopg | `supabase.auth.admin.delete_user(id)` | The auth API also cleans up auth-side state (identities, sessions, refresh tokens) that a raw DB delete leaves orphaned. |
| Per-anon-user starter doc seeding | Custom uploader script | `backend/scripts/seed_default_kb.py` shape, scoped to anon user_id + `visibility='private'` | The existing seed already handles `hash_content` dedup, storage upload, document row insert, and the full ingestion pipeline call. |
| Toast UI | Build a new toast primitive | `frontend/src/contexts/ToastContext.tsx` (already exists) | Supports `error` variant with red ramp, `aria-live="polite"`, `role="status"`, 4 s auto-dismiss. UI-SPEC explicitly mandates reuse. |
| Uptime badge SVG | Custom SVG endpoint or HTML page | shields.io endpoint: `https://img.shields.io/uptimerobot/ratio/{monitor-id}` | Public, cacheable, no API key in the URL, no own infrastructure. |
| Last-deploy badge | New GitHub Actions workflow just for the badge | shields.io `last-commit` badge | Repo has no `.github/workflows/`; standing up CI to get a badge is over-engineering. `last-commit` accurately reflects "how stale is this code". |
| Architecture diagram authoring | Inline SVG hand-written in HTML | Excalidraw web app | Whiteboard aesthetic fits portfolio polish; saves `.excalidraw` JSON (text → git-friendly) + exports PNG/SVG in one click. |
| Hero GIF | ffmpeg + custom palette tuning | ScreenToGif | Built-in frame editor + palette optimizer hits the <5 MB target without manual color-table tuning. |

**Key insight:** Every piece of the Phase-8 puzzle has a "blessed" off-the-shelf answer. The phase is mostly **wiring + content authoring**, not building.

## Runtime State Inventory

> Phase 8 is not a rename/refactor phase. It introduces new state but does not move existing state. Inventory skipped per researcher protocol.

Nothing to inventory — phase only adds new tables-row-types (anon `auth.users` rows + their seeded threads/messages/docs/chunks/storage objects) and new files (README + docs/). It does not rename or move existing identifiers.

## Common Pitfalls

### Pitfall 1: 🔴 CRITICAL — Anon JWT `aud` claim mismatch with backend verifier

**What goes wrong:** `backend/auth.py:42` hard-codes `audience="authenticated"` in `jwt.decode()`. Per the Supabase JWT Claims reference, anonymous user JWTs may have **`aud="anon"`** instead — which would make every anon API request 401 against the prod backend, breaking PORT-01 end-to-end.

**Why it happens:** Sources disagree. The official auth-anonymous guide says anon users "use the authenticated role" (a Postgres role concept). The JWT fields reference document says `aud="anon"` for anon users (a JWT claim concept). These are not the same thing — the Postgres role determines table access; the JWT `aud` claim determines what the JWT verifier accepts. **The two might or might not match.**

**How to avoid:**
1. **Before writing any plan task**, the planner MUST empirically verify by:
   ```javascript
   // In browser console against dev or prod Supabase project (with anon sign-ins enabled):
   const { data } = await supabase.auth.signInAnonymously()
   const jwt = data.session.access_token
   console.log(JSON.parse(atob(jwt.split('.')[1])))  // decode payload
   ```
   Look at `aud` and `role` claims.
2. If `aud === "authenticated"` → no `backend/auth.py` change needed. Proceed.
3. If `aud === "anon"` → modify `backend/auth.py` to accept both audiences:
   ```python
   payload = jwt.decode(
       token, signing_key, algorithms=[alg],
       audience=["authenticated", "anon"],  # accept both
       leeway=30,
   )
   ```
   PyJWT supports an audience list `[CITED: https://pyjwt.readthedocs.io/]`.

**Warning signs:** Every `/api/threads` or `/api/threads/{id}/messages` request from an anon user returns `401 {"detail": "Invalid token"}` in the network tab while the same requests from a permanent user succeed.

### Pitfall 2: 🔴 CRITICAL — `auth.users` cascade-delete is NOT configured

**What goes wrong:** Calling `db.auth.admin.delete_user(anon_user_id)` fails with a foreign-key violation because `threads`, `messages`, `documents`, `document_chunks`, `folders` all `REFERENCES auth.users(id)` **without `ON DELETE CASCADE`** `[VERIFIED: grep across supabase/migrations/]`. Storage objects under `documents/{user_id}/` also outlive the auth row.

**Why it happens:** The original schema was written assuming users live forever. The cascade was never added because cascade-delete is risky for permanent users (one bad delete nukes everything).

**How to avoid:** Mandatory child-first ordered delete. See `_cascade_delete_user_data()` in Pattern 1. Order matters — `document_chunks` references `documents`, so chunks first. Storage uses its own RLS-protected bucket — explicit list + remove.

**Warning signs:** First anon-cleanup run errors with `update or delete on table "users" violates foreign key constraint "threads_user_id_fkey" on table "threads"`. Or: free-tier Supabase storage quota fills up because objects were never removed.

### Pitfall 3: 🟠 MEDIUM — Retry creates duplicate assistant row in DB

**What goes wrong:** `backend/routers/chat.py:564` inserts the assistant placeholder row into `messages` **before** the LLM call. When the LLM stream fails mid-way, the row exists with `content=''` (or `content="[An error occurred while generating the response]"` per the existing finally block). When the user clicks Retry, the frontend POSTs a fresh send → backend inserts a **second** assistant row. The thread now has: user msg → empty/error assistant msg → fresh assistant msg. On thread reload, the user sees the error placeholder PLUS the successful retry, which looks broken.

**Why it happens:** The chat handler is designed for one-shot sends. Retry was not a Phase 6 concern.

**How to avoid (two acceptable strategies — planner picks):**

**Strategy A — Backend cleanup before retry (recommended):** On the retry POST, the frontend includes a header or query param (e.g. `?retry=true`) and the backend deletes the most recent assistant row for the thread before inserting the new placeholder. Small backend change in `chat.py:564`-ish:
```python
if request.query_params.get('retry') == 'true':
    last_asst = db.table('messages').select('id').eq('thread_id', thread_id) \
        .eq('user_id', user_id).eq('role', 'assistant').order('created_at', desc=True) \
        .limit(1).execute()
    if last_asst.data:
        db.table('messages').delete().eq('id', last_asst.data[0]['id']).execute()
```

**Strategy B — Frontend cleanup via DELETE endpoint:** Frontend calls `DELETE /api/threads/{thread_id}/messages/{message_id}` (new endpoint) for the failed placeholder, then POSTs the retry. Two roundtrips instead of one — slower.

**Recommendation:** Strategy A. One backend change, no new endpoint.

**Warning signs:** Reloading the thread after a successful retry shows an empty assistant bubble above the successful response.

### Pitfall 4: 🟠 MEDIUM — Sentry doesn't auto-capture caught exceptions

**What goes wrong:** The default `@sentry/react` global handlers (`browserTracingIntegration`, etc.) capture **uncaught** errors and **unhandled** promise rejections. The chat-error path is in an explicit `try/catch` — Sentry sees `console.error('Chat error:', err)` as a console breadcrumb but **not as an event**. The failure never lands as a discrete error in the Sentry dashboard.

**Why it happens:** This is by design — Sentry doesn't want to capture every caught error in a normal app because most are intentional.

**How to avoid:** Add an explicit `Sentry.captureException(err)` call inside the new catch block. The PII scrub in `lib/sentry.ts` `beforeSend` still runs.
```typescript
import { Sentry } from '../lib/sentry'  // existing module
// inside the catch block:
Sentry.captureException(err)
```

**Warning signs:** Sentry dashboard shows zero events after multiple chat failures in prod, but the LangSmith trace shows the upstream LLM 429.

### Pitfall 5: 🟡 LOW — Bootstrap endpoint MUST be rate-limited per IP

**What goes wrong:** A malicious script calls `signInAnonymously` + `/api/demo/bootstrap` in a loop. Each call seeds a sample PDF (~200 KB chunks + embeddings) → blows Supabase storage + embedding API costs.

**Why it happens:** No identity check beyond a valid JWT, and anon JWTs are free to create.

**How to avoid:**
1. Supabase already enforces a default of **30 anon signins per hour per IP** `[CITED: https://supabase.com/docs/guides/auth/auth-anonymous]`. This is the first defense.
2. Add `@limiter.limit("5/minute")` to `/api/demo/bootstrap` — even though the existing limiter key extracts `user_id` for `/api/chat`, we can use slowapi's default IP-based key for this single endpoint by NOT relying on `request.state.user_id`. (Or define a new key function that returns the user_id since by this point the JWT IS validated and represents a real anon user — IP-keying is also fine since anon-spam attacks are IP-bound.)
3. Bootstrap is idempotent per user_id (the seed function checks for existing docs) — replays from the same anon are no-ops.

**Warning signs:** Supabase storage usage spikes in the dashboard without corresponding signins in the auth log.

### Pitfall 6: 🟡 LOW — `is_anonymous` IS a column on `auth.users` (despite some docs saying it's "just a JWT claim")

**What goes wrong:** One web source (the Phase-8 web search) implied `is_anonymous` is only a JWT claim, not a DB column. A planner might then look for it in `user_metadata` and not find it.

**Why it happens:** Misreading of Supabase docs that emphasize the JWT-claim-side for RLS purposes.

**How to avoid:** Trust the **official auth-anonymous mdx file** `[CITED: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/auth-anonymous.mdx]` which contains: `delete from auth.users where is_anonymous is true and created_at < now() - interval '30 days';`. The `is_anonymous` field is both:
- A real column on `auth.users` (filterable via SQL).
- A JWT claim copied from that column at token-mint time (queryable via `auth.jwt()->>'is_anonymous'` in RLS).
- A field on the `gotrue` Python `User` model: `is_anonymous: bool = False` `[VERIFIED: gotrue/types.py]`.

All three views agree.

### Pitfall 7: 🟡 LOW — `audience` param to `jwt.decode()` accepts a list

Related to Pitfall 1: if the planner DOES need to accept both `"authenticated"` and `"anon"` audiences, PyJWT's `decode()` accepts either a string OR a list — `audience=["authenticated", "anon"]` is valid `[CITED: https://pyjwt.readthedocs.io/en/stable/api.html#jwt.decode]`. A planner who assumes string-only will write a more invasive try/except chain unnecessarily.

### Pitfall 8: 🟡 LOW — Excalidraw `.excalidraw` files are JSON; commit alongside PNG

**What goes wrong:** Committing only the exported `.png` leaves no editable source — next round of polish requires redrawing from scratch.

**How to avoid:** Always commit BOTH `docs/architecture.excalidraw` (the JSON source — re-importable into excalidraw.com) AND `docs/architecture.png` (the asset README references). Same applies to `.drawio` if that's the chosen tool.

### Pitfall 9: 🟡 LOW — `BackgroundTasks` doesn't run on Fly suspend

**What goes wrong:** If Fly is about to auto-suspend (`auto_stop_machines="suspend"` per Phase 4 D-11), a request that schedules a long-running `BackgroundTasks` may have its background task killed when the machine suspends after the response returns.

**Why it happens:** Fly's suspend trigger is based on inbound request activity, not background work. Background tasks fire AFTER the response is sent, so the request that scheduled them no longer counts as "active".

**How to avoid:** Keep the cleanup task small. Limit `purge_stale_anon_users` to at most one page (100 users) per call — if there's more work, the next signin picks it up. Don't run an unbounded loop.

## Code Examples

### Example 1: Sign in anonymously (JS)

```typescript
// Source: official Supabase JS docs
// CITED: https://supabase.com/docs/reference/javascript/auth-signinanonymously
import { supabase } from '../lib/supabase'

const { data, error } = await supabase.auth.signInAnonymously()
if (error) {
  // surface inline error in UI
}
// data.session.access_token contains the anon JWT
// data.user.is_anonymous === true
// data.user.id is a real UUID — usable as user_id everywhere
```

### Example 2: SQL cleanup pattern (reference — we won't use raw SQL, but the field semantics confirm gotrue admin API behavior)

```sql
-- Source: official Supabase docs
-- CITED: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/auth-anonymous.mdx
delete from auth.users
where is_anonymous is true and created_at < now() - interval '7 days';
```

### Example 3: Python cleanup via admin API (what we'll actually ship)

See `purge_stale_anon_users` in Pattern 1.

### Example 4: shields.io UptimeRobot 7d ratio badge

```markdown
[![Uptime 7d](https://img.shields.io/uptimerobot/ratio/7/m803088267-XXXXXXXXXX)](https://boardgame-rag-prod.fly.dev)
```

Where the monitor key `m803088267-XXXXXXXXXX` is obtained from UptimeRobot dashboard → monitor → **Settings tab → Public Stats** → enable; the URL exposed is the per-monitor public ID. The first segment `m803088267` matches the existing Phase-7 monitor ID `803088267` `[VERIFIED: .planning/phases/07-observability-baseline/07-05-SUMMARY.md]`. The hex suffix is generated on enabling the public stats setting. **Verify with the user before publishing the badge URL** — some monitor IDs do not have a public-stats hex assigned by default.

### Example 5: shields.io last-commit badge

```markdown
[![Last commit](https://img.shields.io/github/last-commit/{owner}/{repo})](https://github.com/{owner}/{repo}/commits/main)
```

Zero infrastructure. Updates automatically. Reflects the spirit of D-15 ("how recent is this code") without standing up a workflow just for the badge.

### Example 6: GitHub Actions workflow status badge (alternative for if a workflow lands)

```markdown
![CI](https://github.com/{owner}/{repo}/actions/workflows/{file}.yml/badge.svg?branch=main)
```

Per GitHub docs `[CITED: https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/monitoring-workflows/adding-a-workflow-status-badge]`. Only use if a workflow exists. Not recommended for Phase 8 since the project has zero workflows today.

### Example 7: CC-BY 4.0 attribution boilerplate for the D&D sample doc

```markdown
<!-- top of data/sample-private-docs/dnd5e-quickref.md -->
# D&D 5e Quick Reference

> This work includes material taken from the System Reference Document 5.1 ("SRD 5.1") by Wizards of the Coast LLC and available at https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is licensed under the Creative Commons Attribution 4.0 International License available at https://creativecommons.org/licenses/by/4.0/legalcode.

## Ability Checks
[handwritten ~500 lines of cheat-sheet style content...]
```

Also add the same attribution to `docs/CREDITS.md`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Demo via shared `demo@example.com` / `demopass123` Supabase Auth user | Per-visitor `signInAnonymously()` | Supabase shipped anon sign-ins (~v2.43, mid-2024) | RLS-isolated demo data, no shared-password leakage, no clutter on a shared account, no friction (no email field). |
| Hand-rolled toast primitive | Reuse in-house `ToastProvider` | Phase 06.x (added when the upload flow needed user feedback) | Established team primitive — sonner/react-hot-toast not needed. |
| `console.error` swallow of chat failures | Inline bubble + toast + `Sentry.captureException` | Phase 8 | Failures land as discrete Sentry events, not just breadcrumbs. User gets recovery affordance. |
| GitHub Actions workflow status badge as the "deploy" badge | shields.io `last-commit` badge | Phase 8 (initial portfolio drop with zero CI) | Avoids stand-up-a-workflow-just-for-the-badge anti-pattern. Promote to workflow-status badge IF a CI workflow lands later. |
| draw.io diagrams.net for architecture diagrams | Excalidraw | Phase 8 | Faster, simpler, JSON source format → cleaner git diffs; whiteboard aesthetic fits portfolio polish over precision engineering docs. |

**Deprecated/outdated:**
- **PDF sample doc for Docling.** Docling ingests `.md` natively. Generating a PDF for `dnd5e-quickref` adds toolchain (pandoc / weasyprint) without functional gain. Use markdown directly.
- **Per-monitor UptimeRobot native badge** vs shields.io — both work, but shields.io has better-known URL semantics and fewer UR-account-side surprises.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Anon JWT `aud` claim is `"authenticated"`, not `"anon"` — `backend/auth.py` works unchanged | Pitfall 1 | 🔴 CRITICAL — every anon API call returns 401; demo flow broken end-to-end. **MUST be empirically verified BEFORE any plan task is committed** (see Pitfall 1 for the 3-line verification recipe). |
| A2 | `gotrue==2.12.4` admin API `list_users(page, per_page)` returns `List[User]` directly (not `{users, total}`) | Pattern 1 | 🟡 LOW — verified empirically in installed package source; if Supabase ever changes the shape on upgrade, planner spots it on first run. |
| A3 | Supabase free-tier default anon-signin rate limit (30/hour/IP) is sufficient to prevent abuse for a portfolio site | Pitfall 5 | 🟡 LOW — if abuse is observed, add Cloudflare Turnstile or tighten the dashboard rate limit. |
| A4 | UptimeRobot per-monitor "Public Stats" URL (the hex segment in `m{id}-{hex}`) is enabled by default on the existing Phase-7 monitor 803088267 | Pattern 9 + Example 4 | 🟡 LOW — if not enabled, planner enables it once via UR dashboard (Settings tab → Public Stats toggle). |
| A5 | Sample-PDF sourcing decision (handwritten `.md` not excerpt of SRD PDF) is acceptable to the user | Alternatives Considered | 🟢 NONE — CONTEXT D-02 explicitly allows option (c). Recommendation is within Claude's-Discretion. |
| A6 | Last-deploy badge as `shields.io/github/last-commit` is acceptable to the user as "deploy-status badge or equivalent" per PORT-04 | Alternatives Considered + Example 5 | 🟡 LOW — strictly speaking it's a "last-commit" badge, not a "deploy" badge. Mitigation: README footnote ("Badge tracks last source commit; deployments are CD via Fly + CF push-to-deploy"). |
| A7 | Excalidraw is the right pick over draw.io for the developer's workflow | Alternatives Considered + Pattern 6 | 🟡 LOW — D-12 puts the choice in Claude's Discretion; either works. |
| A8 | `BackgroundTasks` reliably completes after the response on Fly even with `auto_stop_machines="suspend"` for short tasks (≤2 s) | Pitfall 9 | 🟡 LOW — Fly suspend has a grace period (~30 s) after last request. Cleanup is bounded to one page (≤100 users) so well under grace. If observed unreliable, move cleanup to a separate explicit `/api/demo/purge` endpoint hit by a UR monitor on a daily cadence — but that adds complexity rejected in D-03. |

**Empty rows mean nothing was assumed for that area.**

## Open Questions (RESOLVED — dispatched to plan tasks: Q1→08-00 T1, Q2→08-07 T1, Q3→08-07 T2)

1. **Does the existing prod Supabase project have anonymous sign-ins enabled?** — RESOLVED: gated to Plan 08-00 Task 1 (human-action checkpoint enables the toggle + empirically captures an anon JWT to decide auth.py audience widening).
   - What we know: D-01 requires it; Phase 6 verified Supabase Auth URL config but not this toggle specifically.
   - What's unclear: Whether the toggle has been flipped at any point.
   - Recommendation: Plan task should verify (and flip if needed) via Supabase Dashboard → Auth → Providers → "Allow anonymous sign-ins" toggle, before the first plan iteration runs the verification recipe in Pitfall 1.

2. **Has the UptimeRobot monitor 803088267 "Public Stats" toggle been enabled?** — RESOLVED: gated to Plan 08-07 Task 1 (human-action checkpoint enables Public Stats + curl-verifies the shields.io uptime-ratio badge SVG).
   - What we know: Monitor exists, public stats badge requires the toggle.
   - What's unclear: Default state.
   - Recommendation: Plan task asserts the badge URL renders a non-default SVG by curl-ing it during plan verification.

3. **What `owner/repo` does GitHub host this code under?** (for the `last-commit` badge URL) — RESOLVED: gated to Plan 08-07 Task 2 (human-action checkpoint confirms repo visibility + captures owner/repo slug, with fallback to a static `version` badge if private).
   - What we know: `git remote -v` will resolve it.
   - What's unclear: Whether it's public or private — `last-commit` badge requires public repos.
   - Recommendation: Plan task includes `git remote get-url origin` resolution + verification that the repo is public-readable.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build + npm scripts | ✓ | v24.15.0 `[VERIFIED]` | — |
| Python | Backend service work + test runs | ✓ | 3.10.5 `[VERIFIED]` | — |
| `@supabase/supabase-js` (incl. `signInAnonymously`) | PORT-01 frontend | ✓ | ^2.99.3 installed; method shipped in v2.43.x `[VERIFIED: package.json + npm registry + Supabase blog]` | — |
| `gotrue` Python admin API | PORT-01 cleanup loop | ✓ | 2.12.4 (transitive from supabase 2.13.0) `[VERIFIED: installed package]` | — |
| `@sentry/react` `captureException` | PORT-02 error path | ✓ | ^10.53.1 already wired in `frontend/src/lib/sentry.ts` `[VERIFIED]` | — |
| `ToastProvider` in-house primitive | PORT-02 toast surface | ✓ | exists at `frontend/src/contexts/ToastContext.tsx` `[VERIFIED]` | — |
| `slowapi` | rate-limit on `/api/demo/bootstrap` | ✓ | 0.1.9 `[VERIFIED: requirements.txt]` | — |
| `excalidraw.com` (web app, no install) | PORT-03 diagram authoring | ✓ | n/a — browser tool | If unavailable: `app.diagrams.net` (draw.io) as documented in Alternatives Considered. |
| ScreenToGif (Windows) | PORT-03 hero GIF capture | unknown — not installed at probe time | — | If not installed: install from https://www.screentogif.com (free, single .exe). Alternative: native Windows Snipping Tool's screen recording outputs MP4 → ffmpeg to GIF. |
| Browser screenshot tool (Win+Shift+S) | PORT-03 static screenshots | ✓ (Windows native) | n/a | — |
| GitHub repo (public) | PORT-04 `last-commit` badge | unknown — verify `git remote -v` and repo visibility | — | If repo is private: switch to a static `[![Version](https://img.shields.io/badge/version-v1.1-blue)]` badge. |
| UptimeRobot monitor 803088267 | PORT-04 uptime badge | ✓ live `[VERIFIED: 07-05-SUMMARY.md]` | n/a | — |
| `excalidraw` source committed to `docs/` | PORT-03 architecture diagram source-of-truth | ✗ (not created yet — that IS the plan task) | — | Author during plan execution. |
| Sample-PDF source markdown | PORT-01 anon seed | ✗ (not created yet — that IS a plan task) | — | Author during plan execution. ~500-line cheat sheet, handwritten with CC-BY 4.0 attribution. |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** ScreenToGif (Windows install); D&D quick-ref markdown (write during execution); architecture diagram (author during execution); `last-commit` repo public state (verify or swap to static badge).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio 0.23.8 `[VERIFIED: backend/requirements.txt + pytest.ini]` |
| Config file | `backend/pytest.ini` (testpaths=tests, asyncio_mode=auto, strict markers) |
| Quick run command | `cd backend && venv/Scripts/python -m pytest tests/test_demo_service.py tests/test_chat_retry.py -x` (after Wave 0 stubs land) |
| Full suite command | `cd backend && venv/Scripts/python -m pytest -ra --strict-markers` |
| Frontend test framework | **None detected** `[VERIFIED: frontend/package.json has no vitest/jest/jasmine]` |
| Frontend manual verification | Browser DevTools + deployed UAT checklist (mirrors Phase 06.1 P02 pattern) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| PORT-01 | `signInAnonymously()` returns valid session w/ `is_anonymous=true` | manual-only | (browser DevTools — verify in JS console after clicking Try demo) | n/a (frontend) |
| PORT-01 | `/api/demo/bootstrap` seeds 1 doc + 1 thread for the calling anon user (idempotent: second call returns `{seeded: false}`) | unit (mock supabase client) | `pytest tests/test_demo_service.py::test_seed_idempotent -x` | ❌ Wave 0 |
| PORT-01 | `/api/demo/bootstrap` rejects (403/skip) a permanent user | unit | `pytest tests/test_demo_service.py::test_seed_skips_permanent_user -x` | ❌ Wave 0 |
| PORT-01 | `purge_stale_anon_users` deletes only anon users with `created_at < cutoff` (mock `list_users`) | unit | `pytest tests/test_demo_service.py::test_purge_filters_correctly -x` | ❌ Wave 0 |
| PORT-01 | `_cascade_delete_user_data` calls deletes in child-first order | unit (mock client w/ call recorder) | `pytest tests/test_demo_service.py::test_cascade_order -x` | ❌ Wave 0 |
| PORT-01 | Backend `auth.py` accepts an anon JWT (post-Pitfall-1 verification) | integration (live JWT from dev project) | `pytest tests/test_auth_anon.py -x -m integration` | ❌ Wave 0 |
| PORT-01 | Frontend `AuthContext.isAnon` reflects `user.is_anonymous` | manual-only | (browser — log out, click Try demo, check sidebar Demo pill renders) | n/a (frontend) |
| PORT-02 | Error bubble renders when SSE stream fails | manual-only OR e2e w/ mock SSE | (browser — `flyctl machine stop` for 30s, send a chat, observe error bubble + toast) | n/a (no frontend test framework) |
| PORT-02 | Toast renders with `error` variant when SSE stream fails | manual-only | (browser — same drill) | n/a |
| PORT-02 | Retry button re-sends the last user message and removes the error bubble | manual-only | (browser — same drill + click Retry, observe new SSE stream + bubble removed) | n/a |
| PORT-02 | Retry button is disabled while `isStreaming` is true | manual-only | (browser — slow-net throttle, observe disabled state) | n/a |
| PORT-02 | Backend prevents duplicate assistant rows on retry (Pitfall 3 strategy A) | integration | `pytest tests/test_chat_retry.py::test_retry_replaces_assistant_row -x` | ❌ Wave 0 |
| PORT-02 | Tool-level failures (rerank, web_search) stay silent in the UI | smoke (existing behavior; verify no regression) | (browser — observe a search w/ rerank misconfigured, confirm no error bubble fires) | n/a |
| PORT-03 | `README.md` contains all 10 required D-11 sections | grep | `grep -q "## Code Stack" README.md && grep -q "## Services / Infrastructure" README.md && grep -q "## Architecture" README.md && [ -f docs/architecture.png ]` (script) | ❌ Wave 0 (just a bash one-liner — fine to add as a verification step in plan, not a pytest file) |
| PORT-03 | `docs/MASTERCLASS.md` exists and `README.md` links to it | grep | `test -f docs/MASTERCLASS.md && grep -q "docs/MASTERCLASS.md" README.md` | n/a |
| PORT-03 | Hero GIF < 5 MB | file size | `[ $(stat -c%s docs/screenshots/05-hero.gif) -lt 5242880 ]` | n/a |
| PORT-04 | Both badges render (HTTP 200 SVG) | curl | `curl -fsSI https://img.shields.io/uptimerobot/ratio/7/m803088267-XXXX | head -1 ; curl -fsSI https://img.shields.io/github/last-commit/{owner}/{repo} | head -1` | n/a (script step in plan) |

### Sampling Rate

- **Per task commit:** `cd backend && venv/Scripts/python -m pytest tests/test_demo_service.py tests/test_chat_retry.py -x` (the two new files), plus any `test_health.py` / `test_chat_cap.py` / `test_rate_limit.py` that the change might affect.
- **Per wave merge:** `cd backend && venv/Scripts/python -m pytest -ra --strict-markers` (full backend suite).
- **Phase gate:** Full backend suite green + manual UAT checklist (~15 items, mirrors Phase 06.1 P02 12-point UAT) green on deployed CF Pages URL.

### Wave 0 Gaps

- [ ] `backend/tests/test_demo_service.py` — covers seed idempotency, permanent-user-skip, purge filter, cascade order.
- [ ] `backend/tests/test_chat_retry.py` — covers Pitfall-3 fix (duplicate assistant row prevention).
- [ ] `backend/tests/test_auth_anon.py` (integration, optional) — covers anon JWT acceptance, marked `@pytest.mark.integration` and skipped in default runs.
- [ ] A bash one-liner verification script (or pytest entry) checking that `README.md` contains the 10 D-11 sections + `docs/architecture.png` exists + `docs/MASTERCLASS.md` exists.

*(Frontend gets no automated tests because the project has no frontend test framework — manual UAT mirrors the Phase 06.1 P02 pattern. The Phase-8 plan should NOT introduce vitest in this phase — it's scope creep and the UAT pattern is already proven.)*

## Security Domain

`security_enforcement` is enabled (default — `.planning/config.json` does not set it false).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | All new state (anon users + their data) lives behind existing RLS policies; no new trust boundaries introduced. |
| V2 Authentication | yes | Supabase Auth (`signInAnonymously` is part of the existing auth surface); JWT verification in `backend/auth.py` reused. **Pitfall 1 must be resolved before claiming this is satisfied.** |
| V3 Session Management | yes | Supabase manages session lifetime (localStorage token + refresh). Anon sessions follow the same JWT-expiry rules as permanent. |
| V4 Access Control | yes | RLS on every user-scoped table; `auth.uid()` populates the anon's user_id; existing per-user isolation policies apply unchanged. Bootstrap endpoint guard: reject permanent users (anti-abuse). |
| V5 Input Validation | yes | Pydantic on the existing FastAPI routes; new `/api/demo/bootstrap` has no body (POST with empty body) so validation surface is small. Path/query params unused. |
| V6 Cryptography | partial | JWT verification continues to use PyJWT (ES256/HS256 — Phase 1 standard); no new crypto in Phase 8. |
| V7 Errors & Logging | yes | Existing `logger.error(..., exc_info=True)` pattern + LangSmith trace + Sentry. New Sentry `captureException(err)` for chat error path. PII scrub in `sentry.ts beforeSend` already strips JWTs + email. |
| V11 Business Logic | yes | Cleanup runs in background — must NOT block the bootstrap response (DoS mitigation); rate-limited per-IP to prevent spam-bootstrap attacks (cost control). |
| V12 Files & Resources | yes | Storage cascade-delete prevents quota leak; new sample-doc upload validated by Docling parser (existing validation). |
| V14 Configuration | yes | Anon-signin toggle is a Supabase Dashboard config; documented in plan + verified at execution. |

### Known Threat Patterns for {React + FastAPI + Supabase + anon-auth}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Anon-signup spam → cost blowout (embeddings, storage) | Denial of Service | Supabase default 30/hour/IP anon-signin rate limit + slowapi `5/minute` on `/api/demo/bootstrap` + idempotent seed (replays no-op) |
| Anon-JWT confusion (mistakenly treating anon as permanent) | Elevation of Privilege | `is_anonymous` claim check on `/api/demo/bootstrap`; UI Demo pill prevents reviewer-side confusion |
| Cleanup loop deletes wrong users | Tampering / Integrity | Tight filter (`u.is_anonymous AND u.created_at < cutoff`); per-user try/except so a bad row never cascades; cap at one page (≤100) per call |
| Stale storage objects orphaned after `auth.users` delete | Resource leak | Explicit child-first delete in `_cascade_delete_user_data` (storage prefix removed BEFORE auth row) |
| Sentry leaks anon user UUID via auto-attached user context | Information Disclosure | Existing `beforeSend` strips `event.user` to `{ip_address: '{{auto}}'}` — anon UUID never reaches Sentry |
| Retry storm DoS the LLM provider | DoS | User-driven retry (no auto), button disabled during `isStreaming`, existing slowapi 20/minute cap on `/api/chat` still applies |
| Sample-doc upload contains malicious content | Tampering | Sample doc is committed to the repo (`data/sample-private-docs/dnd5e-quickref.md`) — under developer control, not user input |

## Sources

### Primary (HIGH confidence)

- **Installed package source** — `gotrue-2.12.4` (`backend/venv/Lib/site-packages/gotrue/`)
  - `_sync/gotrue_admin_api.py:114` — `list_users(page, per_page) -> List[User]`
  - `_sync/gotrue_admin_api.py:166` — `delete_user(id, should_soft_delete=False) -> None`
  - `types.py` — `User.is_anonymous: bool = False`, `User.created_at: datetime`, `User.aud: str`
- **Existing codebase files** (all verified by Read):
  - `backend/auth.py:42` — `audience="authenticated"` hard-coded (Pitfall 1 trigger)
  - `backend/routers/chat.py:564` — assistant row inserted before LLM call (Pitfall 3 trigger)
  - `backend/routers/chat.py:386-461` — per-tool try/except pattern (D-08 already implemented)
  - `frontend/src/contexts/ToastContext.tsx` — full ToastProvider w/ `error` variant, 4s auto-dismiss
  - `frontend/src/lib/sentry.ts` — Sentry init w/ PII scrub + `consoleLoggingIntegration`
  - `frontend/src/hooks/useChat.ts:188-195` — the catch block to replace
  - `frontend/package.json` — `@supabase/supabase-js ^2.99.3`, `@sentry/react ^10.53.1`
  - `backend/requirements.txt` — pinned versions
  - `supabase/migrations/*.sql` — `REFERENCES auth.users(id)` WITHOUT `ON DELETE CASCADE` (Pitfall 2 evidence)
- **CONTEXT.md + UI-SPEC.md** — all locked decisions D-01..D-15 + visual contract
- **Official Supabase docs**:
  - https://supabase.com/docs/guides/auth/auth-anonymous (anon auth setup, JWT claim, SQL cleanup, RLS pattern)
  - https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/auth-anonymous.mdx (verbatim SQL cleanup confirming `is_anonymous` is a column)
  - https://supabase.com/docs/reference/javascript/auth-signinanonymously (JS API signature)
  - https://supabase.com/docs/reference/python/auth-admin-listusers + auth-admin-deleteuser (Python admin API)
  - https://supabase.com/docs/guides/auth/jwt-fields (JWT claims — source of the `aud="anon"` vs `aud="authenticated"` ambiguity)
- **Supabase official blog** — https://supabase.com/blog/anonymous-sign-ins (`signInAnonymously` overview + linking pattern)

### Secondary (MEDIUM confidence — official source + independent verification)

- **shields.io UptimeRobot badge** — https://shields.io/badges/uptime-robot-ratio-7-days + the existing Phase-7 monitor ID `803088267` from `07-05-SUMMARY.md`
- **shields.io GitHub last-commit badge** — https://shields.io/badges (general endpoint badge spec)
- **GitHub Actions workflow status badge** — https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/monitoring-workflows/adding-a-workflow-status-badge
- **D&D 5e SRD 5.1 CC-BY 4.0** — https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf + attribution boilerplate verified
- **Tabyltop CC-SRD** — https://github.com/Tabyltop/CC-SRD (alternative source, not recommended; full SRD only, no quick-ref)
- **Excalidraw** — https://excalidraw.com (verified as web-app, exports PNG, saves JSON)
- **ScreenToGif** — https://github.com/NickeManarin/ScreenToGif (Windows-native, free, frame editor + palette tuning)
- **@sentry/react ErrorBoundary + captureException** — https://docs.sentry.io/platforms/javascript/guides/react/usage/

### Tertiary (LOW confidence — single-source web search, kept for awareness)

- **Anon JWT `aud="anon"` vs `aud="authenticated"`** — Supabase JWT Claims Reference page lists `aud="anon"` for anon users, while the auth-anonymous guide implies they "use the authenticated role". **MUST VERIFY EMPIRICALLY** per Pitfall 1. This is the single biggest uncertainty in the research.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library version verified against installed package or package.json.
- Architecture patterns: HIGH — all patterns map to existing code paths; planner can copy/adapt directly.
- Pitfalls: MEDIUM-HIGH — Pitfalls 1, 2, 3 are concrete and verifiable; Pitfall 9 (Fly background tasks) is informed-speculation and may not bite.
- Validation architecture: HIGH — pytest is the only test framework, all unit-test targets are mock-able, manual UAT pattern is proven from Phase 06.1.

**Research date:** 2026-05-17
**Valid until:** 2026-06-15 (30 days; Phase-8 surface is stable — Supabase anon-auth is GA, UptimeRobot badge format unchanged, no library churn expected in the window).
