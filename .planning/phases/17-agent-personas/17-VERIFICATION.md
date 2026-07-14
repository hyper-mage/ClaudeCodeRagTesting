---
phase: 17-agent-personas
verified: 2026-07-13T21:49:35Z
status: gaps_found
score: 1/5 must-haves verified (human UAT)
overrides_applied: 0
re_verification:
  # No previous VERIFICATION.md existed — initial verification via human UAT (17-11)
---

# Phase 17: Agent Personas Verification Report

**Phase Goal:** Users can switch the chat agent's persona per-thread and set a user-level default (board-game expert default + general assistant), both retaining full tool access, with the persona's system prompt resolved per request with no cross-user/thread bleed.
**Verified:** 2026-07-13T21:49:35Z (human UAT in running dev app, test creds `ragtest1@gmail.com`)
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

The backend persona engine is functionally correct and GREEN across all automated suites (waves 1–5): base+voice composition, per-turn resolver (thread pin → user default → Expert), `GET /api/personas`, thread/prefs write paths, and migration 035 applied to dev. Human UAT confirmed the **agent's voice actually changes** (Board-Game Expert answer vs. more-vanilla General Assistant answer) and that a **mid-thread switch applies on the next turn** (PERS-06). 

However, UAT surfaced a **display gap that blocks visual sign-off** on criteria 1, 3, and 4: the chat-header persona picker shows the placeholder "Select a persona" for any unpinned thread instead of reflecting the effective active persona, so the user cannot see which persona is live. The feature *works*; the UI does not *communicate* it.

### Observable Truths (ROADMAP Success Criteria)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| SC-1 | Select persona via chat picker; agent responds in it | ⚠ GAP | Voice change confirmed live (Expert answer to "How do you win Azul?"). BUT picker shows "Select a persona" instead of reflecting the active persona — user "doesn't know which one it is." Root cause: `frontend/src/pages/ChatPage.tsx:258` passes `threadPersona={activeThread?.persona ?? null}`; an unpinned thread has `persona = NULL` so the picker never displays the resolved default. |
| SC-2 | General Assistant vanilla + full tools; Expert is default | ⚠ PARTIAL | Effective default behaves as Expert; General Assistant answer read "more vanilla" (voice works). NOT verified: a tool call under General Assistant (tool card still appears). Picker-display gap also obscures which persona is default. |
| SC-3 | Set default persona in settings; new threads start with it | ⚠ GAP | Setting default = General Assistant made a new chat answer more vanilla (default IS applied backend-side), but the new-chat picker still shows "Select a persona" — same display gap as SC-1; the default is not visually reflected. |
| SC-4 | Persona persists across sessions / reopen | ○ UNTESTED | Not confirmable while the picker shows a blank placeholder — re-test after the display fix. |
| SC-5 | Per-request resolution, no cross-user/thread bleed | ⚠ PARTIAL | Mid-thread persona switch applies on the next turn (PERS-06 ✓ — per-request resolution confirmed). NOT tested: two concurrent users (cross-user bleed). |

**Score:** 1/5 fully verified (SC-5 mid-thread switch confirmed); SC-1/SC-3 blocked by the picker-display gap; SC-2/SC-4/SC-5-crossuser untested pending the display fix.

## Gaps

### Gap 1 — Chat persona picker does not reflect the effective active persona (blocks SC-1, SC-3, SC-4)

- **Requirement:** PERS-01, PERS-03, PERS-04, PERS-05
- **Symptom:** For a new/unpinned thread the header picker shows the placeholder "Select a persona" even though the backend resolves NULL → user default → Board-Game Expert. The user cannot tell which persona is active; setting a settings default also does not visually reflect in the new-chat picker.
- **Root cause:** `frontend/src/pages/ChatPage.tsx:258` — picker value is `activeThread?.persona ?? null`. The `/api/preferences` fetch at `ChatPage.tsx:103` reads theme only and never captures `default_persona`. The UI does not mirror the resolver's tier chain.
- **Fix approach (display-only, no auto-PATCH):** Capture `default_persona` from the `/api/preferences` fetch into state. Compute the picker's displayed value as `activeThread?.persona ?? userDefaultPersona ?? personas?.find(p => p.is_default)?.id` and pass that to `PersonaSelector`. Display fallback MUST NOT fire a PATCH — only an explicit user selection pins `thread.persona`. `PersonaOption` already carries `is_default` (from `GET /api/personas`, 17-06).
- **Re-test after fix:** SC-1 (picker shows Expert on new chat), SC-3 (picker shows chosen default on new chat), SC-4 (pin survives reload — now visible).

### Gap 2 — No Retry affordance on interrupted / failed responses (bundled enhancement, user-requested)

- **Requirement:** none (UX enhancement; not a PERS-0x requirement — bundled into gap-closure by user decision on 2026-07-13)
- **Symptom:** When a chat is interrupted ("[Response interrupted]") or fails (e.g. model switch mid-turn, provider error), the user must manually copy/paste and resend the last message. There is no one-click retry.
- **Fix approach:** Add a Retry action on interrupted/failed assistant turns that re-sends the last user message without manual copy/paste. Reuse the existing send path; preserve the last user message so Retry resubmits it. Mirror the existing error-state card pattern (Phase 16 `ToolCallCard` red failed state / the "pick a different model" error card already has a Retry button — extend that affordance to interrupted turns).

## Notes / Non-blocking observations

- **Environment (not a phase defect):** `openrouter_api_key` is empty while the chat model is `nvidia/nemotron-3-super-120b-a12b:free` (an OpenRouter model) — chat 500s ("model isn't available") until the user attaches an OpenRouter key or selects an OpenAI model (`openai_api_key` is set). BYOK/setup concern, tracked separately.
- All automated suites GREEN: backend 314 passed (17-07), frontend build + vitest 133/133 (17-10). The gaps are UX/display, not logic.

## Recommendation

Route to gap-closure: `/gsd-plan-phase 17 --gaps` → produces gap_closure plans for Gap 1 (picker display) and Gap 2 (Retry) → `/gsd-execute-phase 17 --gaps-only` → re-run the 17-11 UAT.
