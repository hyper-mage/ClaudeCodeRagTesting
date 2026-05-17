# Phase 8: Portfolio Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 08-portfolio-polish
**Areas discussed:** Demo user model, Graceful error surface, README strategy, Deploy-status badge, Tech-stack tables (developer-added)

---

## Gray-Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Demo user model | Shared seeded user vs anon ephemeral vs shared read-only — how Try demo works | ✓ |
| Graceful error surface | LLM error UX + tool-failure visibility + retry semantics | ✓ |
| README strategy | Augment / prepend / rewrite, diagram format, screenshots vs GIF | ✓ |
| Deploy-status badge | UptimeRobot ratio / shields.io / GH Actions / two-badge combo | ✓ |

**Developer add-on:** "list of technologies used, a link to the ones I use such as cf, fly, uptimerobot, supabase, etc, what they do, and how they are utilized in this project" — folded into README strategy area as Tech-stack tables.

---

## Demo User Model (PORT-01)

### Identity

| Option | Description | Selected |
|--------|-------------|----------|
| Shared seeded user | ONE pre-seeded user, shared password, button signs everyone in as that user. Simple; threads visible across visitors. | |
| Anon ephemeral user | Supabase anonymous auth — each click creates throwaway user. RLS isolates. Auto-cleanup via expiry. | ✓ |
| Shared + read-only mode | Shared user but UI disables uploads + thread create. Safest, cuts off upload demo. | |

**User's choice:** Anon ephemeral user
**Notes:** Cleanest RLS story; no shared mess; demos the full app honestly.

### Starter Content

| Option | Description | Selected |
|--------|-------------|----------|
| Public KB only, empty threads | Anon lands on empty chat, public KB available | |
| Public KB + seeded sample thread | Backend seeds 1–2 example threads per anon user | ✓ |
| Public KB + one private sample PDF | Auto-attach one private board-game PDF per anon user | ✓ |

**User's choice:** Both 2 and 3 — seeded threads AND a sample private PDF.
**Notes:** Exercises both the chat surface and the private-doc retrieval surface from the first click.

### Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Accept accumulation | No cleanup; revisit if free-tier limits bite | |
| Scheduled purge (7d TTL) | Cron / scheduled function deletes anon users > 7d | |
| Purge on next anon signin | Opportunistic cleanup on each new signin (7d TTL) | ✓ |

**User's choice:** Purge on next anon signin
**Notes:** Zero external scheduler; cost ≈ a few deletes per signin event.

---

## Graceful Error Surface (PORT-02)

### LLM Failure UX

| Option | Description | Selected |
|--------|-------------|----------|
| Inline error bubble | Failed turn renders as red bubble with Retry | |
| Toast notification | Floating toast; failed turn vanishes from thread | |
| Both: inline + toast | Inline bubble for context + toast for transient feedback | ✓ |

**User's choice:** Both
**Notes:** Maximum visibility; reviewer never wonders what happened.

### Tool-Level Failure UX

| Option | Description | Selected |
|--------|-------------|----------|
| Silent continue | Tool fails → Sentry/LangSmith capture; no UI indication | ✓ |
| Tool card shows failed state | Existing ToolCallCard renders failed state | |
| Inline subtle note + tool card | Card failed-state + small assistant-message note | |

**User's choice:** Silent continue
**Notes:** Per-tool try/except in chat.py already covers this. No UI work needed.

### Retry Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Resend last user message | Delete failed placeholder, re-POST | ✓ |
| Auto-retry once, then manual | First retry automatic with backoff | |
| No retry button — just error | User re-types | |

**User's choice:** Resend last user message
**Notes:** Simplest; user controls cadence; matches typical chat UX expectations.

---

## README Strategy (PORT-03)

### Disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Separate PORTFOLIO.md | New file; existing README untouched | |
| Prepend portfolio section | Portfolio content at top of existing README; course below divider | |
| Full portfolio rewrite, archive old README | Replace README; move course to docs/MASTERCLASS.md | ✓ |

**User's choice:** Full rewrite + archive
**Notes:** Strongest portfolio impression; course backstory preserved via link.

### Architecture Diagram

| Option | Description | Selected |
|--------|-------------|----------|
| Mermaid inline | GitHub renders natively; source-controlled | |
| PNG/SVG asset (Excalidraw or draw.io) | Hand-drawn; more polished; source file committed | ✓ |
| Both — Mermaid + linked PNG | Belt-and-suspenders | |

**User's choice:** PNG/SVG asset
**Notes:** Excalidraw vs draw.io left to researcher recommendation.

### Screenshots / Media

| Option | Description | Selected |
|--------|-------------|----------|
| Static screenshots only | 3–4 PNGs | |
| One animated GIF/MP4 | ~20s loop of full flow | |
| Screenshots + one GIF | Both | ✓ |

**User's choice:** Screenshots + hero GIF
**Notes:** Mobile drawer must appear in at least one screenshot to showcase Phase 06.1 work.

### Tech-Stack Tables (developer-added scope)

| Option | Description | Selected |
|--------|-------------|----------|
| Infra/services only | One table for third-party services; stack listed separately | |
| Full stack incl. frameworks | One big table covering everything | |
| Two tables: stack + services | Code stack table + services table with link + what + how-used | ✓ |

**User's choice:** Two tables
**Notes:** Services table answers the developer's verbatim ask: link + what + how-used columns for CF, Fly, Supabase, OpenRouter, Sentry, LangSmith, UptimeRobot, etc.

---

## Deploy-Status Badge (PORT-04)

| Option | Description | Selected |
|--------|-------------|----------|
| UptimeRobot uptime-ratio badge | Public SVG badge endpoint; reflects live Fly + CF health | |
| shields.io custom from UR API | Custom-colored shield scraping UR API | |
| GitHub Actions deploy workflow | CI badge — needs workflow | |
| Two badges — uptime + last-deploy | UR uptime badge + Fly/GH last-deploy badge | ✓ |

**User's choice:** Two badges
**Notes:** Most informative for a reviewer skimming the README header. Phase 7 carve-out (no public status page) does not contradict a single uptime % badge.

---

## Claude's Discretion

- Exact error-bubble component shape (extend `MessageBubble` vs sibling `ErrorMessageBubble`)
- Excalidraw vs draw.io for diagram authoring
- Hero GIF recording tool
- Sample-PDF candidate (board-game rulebook ≤2 MB)
- Sample-thread seed strategy (DB seed vs first-launch UI hint)

## Deferred Ideas

- Demo-mode UI gating (read-only chat for anon) — rejected; revisit on abuse
- Scheduled-cron purge — opportunistic purge sufficient
- Public UptimeRobot status page — Phase 7 carry-forward
- Auto-retry with backoff
- Anon → permanent account linking (`linkIdentity`)
- Backend Sentry SDK (Phase 7 carry-forward)
- Tool-failure user-visible note (rejected; reconsider on reviewer feedback)
