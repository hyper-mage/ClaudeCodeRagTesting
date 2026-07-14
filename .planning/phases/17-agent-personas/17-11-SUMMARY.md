---
phase: 17-agent-personas
plan: 11
subsystem: testing
tags: [uat, human-verification, personas, frontend]

# Dependency graph
requires:
  - phase: 17-10
    provides: persona pickers wired into chat header + settings
provides:
  - human UAT sign-off attempt for PERS-01..06 in the running dev app
  - two gaps recorded for gap-closure (picker display + Retry affordance)
affects: [17-gaps]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Human UAT of persona feature against the 5 ROADMAP success criteria"

key-files:
  created:
    - ".planning/phases/17-agent-personas/17-VERIFICATION.md (gaps_found)"
  modified: []

key-decisions:
  - "Phase NOT signed off — UAT found a picker-display gap blocking SC-1/SC-3/SC-4 visual confirmation."
  - "User elected to bundle the picker-display fix AND a Retry-button enhancement into Phase 17 gap-closure."

patterns-established: []

requirements-completed: []

# Metrics
duration: ~30min (interactive UAT)
completed: 2026-07-13
---

# Phase 17-11: End-to-End Persona UAT — Gaps Found

**Human UAT confirmed the persona voice genuinely changes and mid-thread switch applies next-turn (PERS-06), but the chat picker never displays the active persona — blocking visual sign-off on SC-1/SC-3/SC-4.**

## Performance

- **Duration:** ~30 min (interactive)
- **Completed:** 2026-07-13T21:49:35Z
- **Tasks:** 1 (checkpoint:human-verify)
- **Result:** gaps_found (not approved)

## What was verified (running dev app, `ragtest1@gmail.com`)

- **SC-5 / PERS-06 ✓** — Mid-conversation persona switch applies from the next turn (per-request resolution confirmed).
- **Voice works** — Board-Game Expert answered "How do you win Azul?" in expert style; after setting General Assistant as default, a new chat answered noticeably more vanilla (the resolver's tier chain is applied backend-side).

## Gaps found (→ gap-closure)

1. **Picker doesn't reflect the active persona** (PERS-01/03/04/05). The header picker shows "Select a persona" for unpinned threads instead of the resolved default (Expert or the user's default). Root cause `ChatPage.tsx:258` (`threadPersona={activeThread?.persona ?? null}`); `/api/preferences` fetch never captures `default_persona`. Full detail + fix approach in `17-VERIFICATION.md` Gap 1.
2. **No Retry on interrupted/failed turns** (UX enhancement, user-requested, bundled by decision). User must copy/paste + resend after "[Response interrupted]" or a model/provider error. Detail in `17-VERIFICATION.md` Gap 2.

## Not tested (blocked by the display gap — re-test after fix)

- SC-2 tool call under General Assistant (tool card still appears)
- SC-4 persona persistence across reload
- SC-5 two-user cross-user bleed

## Environment note (not a phase defect)

`openrouter_api_key` empty while chat model is `nvidia/...:free` (OpenRouter) — chat 500s until the user attaches an OpenRouter key or picks an OpenAI model (`openai_api_key` is set). BYOK setup, tracked separately.

## Next Phase Readiness

Phase 17 is NOT complete. Route: `/gsd-plan-phase 17 --gaps` (reads 17-VERIFICATION.md) → `/gsd-execute-phase 17 --gaps-only` → re-run this UAT.

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13 (UAT executed; gaps found)*
