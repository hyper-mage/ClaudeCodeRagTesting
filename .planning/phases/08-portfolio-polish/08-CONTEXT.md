---
phase: "08"
slug: portfolio-polish
created: 2026-05-17
requirements:
  - PORT-01
  - PORT-02
  - PORT-03
  - PORT-04
---

# Phase 8: Portfolio Polish - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

A reviewer who cold-visits the public Cloudflare Pages URL can: (a) try the full app in one click via an anonymous "Try demo" button — no signup, with starter content pre-seeded; (b) experience graceful, in-context failure messaging if the LLM provider errors or tools fail; (c) read a portfolio-grade `README.md` at the repo root that pitches the project, lists the live URL + tech stack + service inventory + architecture diagram + screenshots + a hero GIF + a deploy-status + uptime badge.

In scope: anonymous Supabase auth + Try-demo flow, anon-user starter-content seeding (1–2 sample threads + 1 sample private PDF), opportunistic anon-cleanup-on-signin, inline-bubble + toast error UX on chat failures, manual retry button, full README rewrite with course README archived to `docs/MASTERCLASS.md`, Excalidraw/draw.io architecture asset, screenshots + one hero GIF under `docs/`, UptimeRobot uptime ratio badge + last-deploy badge in README.

Out of scope (deferred): backend Sentry SDK, public UptimeRobot status page, demo-user scheduled-purge cron, demo-mode UI gating (uploads remain enabled for anon since RLS isolates them).

</domain>

<decisions>
## Implementation Decisions

### Demo User Model (PORT-01)

- **D-01 — Identity:** Supabase **anonymous auth**. Every "Try demo" click invokes `supabase.auth.signInAnonymously()` and produces a throwaway anon user with its own `user_id`. RLS continues to isolate per-user data — no shared-account collisions, no shared-password leakage. Requires enabling anonymous sign-ins in the prod Supabase project's **Auth > Providers** panel.
- **D-02 — Starter content per anon user:** On first signin the anon user gets BOTH:
  1. **1–2 seeded sample chat threads** showing good queries (e.g. "Recommend a 2-player strategy game", "Compare Catan vs Carcassonne") — pre-rendered assistant turns OR queued user messages, planner to choose lightest impl.
  2. **One sample private PDF** auto-attached so the anon user immediately sees the private-doc-in-chat experience without uploading anything. Sample doc must be a board-game rulebook (genre-consistent), small (≤2 MB), and ingested via the standard pipeline so the demo exercises chunking + embeddings + retrieval honestly.
  - Public seeded KB (≥10 board games, `visibility='public'`) is already visible from Phase 3 — no extra work needed for that surface.
- **D-03 — Cleanup:** **Opportunistic purge on next anon signin.** When a new anon-signin lands, fire a backend cleanup that deletes anon users (and their threads, messages, documents, document_chunks, storage objects) created more than **7 days** ago. No external scheduler; cost ≈ a few deletes per signin event. Acceptable since RLS already isolates users, so an orphan never affects anyone else.
- **D-04 — Login page:** New "Try demo" CTA on `frontend/src/pages/LoginPage.tsx` rendered prominently above the email/password form. Copy must make clear it's a no-signup ephemeral demo. README documents this path; no shared credentials needed (anon auth has none).
- **D-05 — Demo-mode UI gating:** **Not added.** Anon users keep the full app (uploads, thread create, deletes) — RLS isolates their data. Keeps the demo honest and exercises every code path a real user would hit.

### Graceful Error Surface (PORT-02)

- **D-06 — LLM provider failure UX:** **Both inline + toast.** Failed assistant turn renders as a muted/red error bubble inside the chat thread with the failure reason. Simultaneously a toast appears for transient visibility. The error bubble carries a **Retry** button.
- **D-07 — Retry behavior:** Retry **re-sends the last user message** — deletes the failed assistant placeholder, re-POSTs to the same thread, streams a fresh attempt. No auto-retry / no backoff layer; user controls the cadence.
- **D-08 — Tool-level failure UX (rerank / web_search / analyze_document subagent):** **Silent continue.** Per-tool `try/except` in `backend/routers/chat.py` already returns `{error: ...}` JSON to the LLM and lets the loop proceed without that tool. Sentry (frontend, Phase 7) + LangSmith (backend, Phase 7) already capture these for the developer. **No user-visible indicator** when a non-critical tool fails — the agent still completes the turn.
- **D-09 — Error wording:** Generic + actionable, not technical. "The model didn't respond — try again, or rephrase your question." (Exact copy TBD by planner; do not leak provider names or HTTP codes.)

### README Strategy (PORT-03)

- **D-10 — README disposition:** **Full portfolio rewrite.** Replace repo-root `README.md` with the portfolio version. Move existing course/masterclass README to `docs/MASTERCLASS.md` and link to it from the new README ("Built as the capstone for the AI Automators Claude Code Masterclass — see [docs/MASTERCLASS.md](docs/MASTERCLASS.md) for course context").
- **D-11 — Required README sections (order):**
  1. Project title + one-line pitch
  2. **Live demo link** + "Try demo (no signup)" callout
  3. **Badges row:** UptimeRobot uptime-ratio badge + last-deploy badge (per D-15)
  4. Hero GIF (~15–20 s of full flow)
  5. **What it does** — short pitch (≤6 lines)
  6. **Tech tables** (per D-13)
  7. **Architecture diagram** (linked PNG/SVG per D-12)
  8. Screenshots gallery
  9. **Deploy command sequence** — `docker build` → `flyctl deploy` → CF Pages deploy (or push-to-deploy note)
  10. Link to `docs/MASTERCLASS.md` for course backstory
- **D-12 — Architecture diagram format:** **PNG/SVG asset.** Authored in **Excalidraw or draw.io** (developer's choice; researcher to recommend based on existing workflow). Source file (`.excalidraw` or `.drawio`) committed to `docs/architecture.{excalidraw,drawio}` alongside exported `docs/architecture.png` (or `.svg`). README references the exported asset.
- **D-13 — Tech tables: TWO tables.** Cleanest information architecture.
  - **Table 1 — Code Stack:** React, TypeScript, Tailwind, shadcn/ui, Vite, FastAPI, Python, pgvector, Docling, OpenAI SDK. Columns: `Tech | Role`. No how-used column (kept simple).
  - **Table 2 — Services / Infrastructure:** Cloudflare Pages, Fly.io, Supabase, OpenRouter, Sentry, LangSmith, UptimeRobot, GitHub. Columns: `Service | Link | What it does | How this project uses it`. Each row's `Link` is the service marketing/product page (clickable in README markdown). This table answers the developer's bonus ask verbatim.
- **D-14 — Screenshots + GIF:** Four+ static screenshots + one hero GIF, all under `docs/screenshots/`.
  - Required screenshots: (a) login page with "Try demo" CTA visible, (b) chat with tool-call cards expanded mid-response, (c) documents page with folder tree + an upload in progress, (d) mobile drawer open over chat (showcases the 06.1 mobile work).
  - Hero GIF: ~15–20 s loop — Try demo → land in chat → ask a query → tool cards fire → streaming answer. Recorded at 1280×720 or similar. Tooling left to planner (e.g. ScreenToGif, Kap, or gif export from screen recording).

### Deploy-Status + Uptime Badge (PORT-04)

- **D-15 — Two badges in README:**
  1. **Uptime badge:** UptimeRobot public uptime-ratio badge (30-day window) — UR provides a public SVG endpoint per monitor; reflects live prod Fly + CF Pages health using the monitors already provisioned in Phase 7. (Note: Phase 7 rejected a *public status page*; a single uptime % badge is a narrower surface and does not contradict that decision.)
  2. **Last-deploy badge:** Either a Fly "deployed" static shield (if no CI workflow exists at planning time) OR a GitHub Actions workflow-status badge if/when a deploy workflow lands. Planner to pick the simpler option that doesn't require new CI infra in this phase. If neither is clean, fall back to a `version` or `last-updated` shields.io badge driven off git tag or commit date.

### Claude's Discretion

- Exact error-bubble component shape (subclass of `MessageBubble` vs a separate `ErrorMessageBubble`) — planner to choose based on existing component patterns.
- Excalidraw vs draw.io — researcher to recommend based on the developer's existing tooling; both are acceptable.
- Hero GIF recording tool — any tool that produces a small (<5 MB) GIF or animated WebP is fine; specifics deferred to plan execution.
- Sample-PDF candidate (must be a real public-domain or original board-game rulebook ≤2 MB) — researcher to source 2–3 candidates.
- Sample-thread seed strategy (DB seed of `messages` rows vs first-launch UI hint) — planner to pick the simpler/cleaner option.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + requirements
- `.planning/ROADMAP.md` — Phase 8 success criteria (lines 152–159) and PORT-01..04 mapping (Coverage Map)
- `.planning/REQUIREMENTS.md` — PORT-01 (Try demo + creds doc), PORT-02 (graceful errors), PORT-03 (portfolio README), PORT-04 (deploy badge)

### Prior phase contexts (reuse + constraints)
- `.planning/phases/07-observability-baseline/07-CONTEXT.md` — Sentry + UptimeRobot monitor IDs and the "no public status page" carve-out that frames the badge decision (D-15); LangSmith routing pattern; PII scrub rules apply to any new anon-related logging
- `.planning/phases/06.1-mobile-responsive-chat-layout/06.1-CONTEXT.md` — mobile drawer pattern needed for screenshot (d)
- `.planning/phases/06-prod-wiring-auth-cors-rate-limiting-cost-caps/06-CONTEXT.md` — Supabase Auth URL config pattern (anon auth must be enabled in same Auth panel); slowapi rate-limiter still applies to anon sessions
- `.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-CONTEXT.md` — CF Pages env var injection pattern, `_redirects` SPA routing
- `.planning/phases/04-deploy-backend-to-fly-io/04-CONTEXT.md` — Fly secret + deploy pattern; informs the last-deploy badge (D-15)
- `.planning/phases/03-prod-supabase-project/03-CONTEXT.md` — public KB seed pattern + `visibility='public'` RLS surface that anon users will read

### Codebase entry points the plan touches
- `frontend/src/pages/LoginPage.tsx` — add "Try demo" CTA + `signInAnonymously()` call (D-01, D-04)
- `frontend/src/hooks/useChat.ts:189–194` — current `console.error` swallow point; replace with error-bubble dispatch (D-06)
- `frontend/src/components/MessageBubble.tsx` — extend or sibling-render for error variant (D-06)
- `frontend/src/components/ChatContainer.tsx` — host the toast surface (D-06)
- `frontend/src/contexts/AuthContext.tsx` — must surface `is_anonymous` flag so UI/backend can branch when needed
- `backend/routers/chat.py:386–451` — existing per-tool `try/except`; verify all return `{error: ...}` JSON consistently (D-08)
- `backend/scripts/seed_default_kb.py` — analog for the per-anon-user seeder (D-02)
- `backend/auth.py` — JWT verification must accept anon JWTs (anon role tokens still have `sub` claim)
- `supabase/migrations/` — may need a new migration for anon-cleanup helper function or trigger (planner decides)
- `README.md` (repo root) — full rewrite target (D-10/D-11/D-13)
- `docs/` — new directory for `MASTERCLASS.md`, `architecture.{excalidraw,drawio}` + `architecture.png`, `screenshots/`

### External references researcher must consult
- Supabase Anonymous Sign-Ins docs — `https://supabase.com/docs/guides/auth/auth-anonymous` (anon auth setup + RLS implications + rate-limit + linking-to-permanent recommendations)
- UptimeRobot public badge endpoint — `https://uptimerobot.com/dashboard#mySettings` Public API key + per-monitor SVG badge URL pattern
- shields.io endpoint badge spec — for the last-deploy fallback

[Every ref above has a full relative path. Sample-PDF source and badge URL specifics resolved during research/planning.]

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useChat.ts` already maintains a `messages` array with optimistic assistant placeholder + removes-on-error — extending it to instead *replace* the placeholder with an `error` variant message is a 5-line change.
- `MessageBubble.tsx` already renders per-role variants; an `error` role/variant slots in naturally.
- `ToolCallCard.tsx` already renders tool status and could surface `failed` for D-08 if the user ever revisits that decision (currently locked silent).
- `backend/scripts/seed_default_kb.py` is the working template for the anon-user starter-PDF seeder — same `record_manager.hash_content` + `process_document` pipeline, just scoped to a user_id instead of `SYSTEM_USER_ID`.
- Supabase Realtime is already wired in `useDocuments` — sample-PDF ingestion progress will appear automatically for the anon user.

### Established Patterns
- **Per-tool try/except in `chat.py`** already exists for every external tool call — D-08 (silent continue) confirms this is the intended pattern; no refactor needed.
- **Env-driven CF Pages config** (Phase 5) is how `VITE_*` vars land in the SPA; any new frontend env var for the badge or demo flow follows the same Production-scope-only convention.
- **RLS-first data model** (every phase) — adding anon users requires zero new RLS work because `auth.uid()` is the same primitive whether the JWT is permanent or anonymous.
- **Course README → docs/ archive pattern** is novel for this repo; D-10 establishes it.

### Integration Points
- Anon-signin → backend cleanup hook: simplest is a backend endpoint (e.g. `POST /api/demo/bootstrap`) called by `LoginPage.tsx` immediately after `signInAnonymously()` resolves. That endpoint runs both: (1) cleanup of >7d anon users (D-03), and (2) seeding the new user's sample PDF + sample thread(s) (D-02). Planner can split or combine.
- Error-bubble + toast: add a lightweight toast primitive if none exists (project does not currently use shadcn `<Toaster />` — confirm during research). Otherwise reuse what's there.
- Badge endpoints: README is static markdown; badges are external SVG URLs — no build-time integration needed.

</code_context>

<specifics>
## Specific Ideas

- Developer explicitly asked for: **"list of technologies used, a link to the ones I use such as cf, fly, uptimerobot, supabase, etc, what they do, and how they are utilized in this project"** — captured verbatim in D-13 as Table 2 (Services / Infrastructure) with columns `Service | Link | What it does | How this project uses it`. This is a non-negotiable section of the new README.
- "Try demo" must be a one-click experience — no email, no password, no captcha. (Supabase anon auth supports this; rate-limit configurable in Auth settings.)
- Mobile drawer (Phase 06.1) must appear in at least one screenshot — it's a differentiating polish item that reviewers should see.

</specifics>

<deferred>
## Deferred Ideas

- **Demo-mode UI gating** (read-only chat for anon users) — explicitly rejected (D-05). Re-evaluate only if abuse becomes a real cost issue.
- **Scheduled-cron purge of anon users** (GitHub Action / Supabase scheduled function) — deferred in favor of opportunistic-on-signin (D-03). Promote if signin frequency is too low to keep cleanup current.
- **Public UptimeRobot status page** — rejected in Phase 7; revisit if portfolio reviewers ask for transparent SLA history.
- **Auto-retry with exponential backoff** on transient LLM errors — rejected (D-07). User-driven retry only.
- **Linking anon user → permanent account** on signup — Supabase supports `linkIdentity()` post-signup; nice future enhancement so a visitor who likes the demo can preserve their threads. Not in v1.1 scope.
- **Backend Sentry SDK** — still deferred (carried from Phase 7).
- **Tool-failure user-visible note** (per-tool warning in assistant message) — rejected (D-08). Re-add only if reviewer feedback says agent answers feel mysteriously thin.

</deferred>

---

*Phase: 08-portfolio-polish*
*Context gathered: 2026-05-17*
