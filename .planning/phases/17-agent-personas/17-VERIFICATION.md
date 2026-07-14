---
phase: 17-agent-personas
verified: 2026-07-14T09:05:00Z
status: human_needed
score: "gap-closure 2/2 closed (9 must-haves code-verified, build+142 tests green); 5/5 ROADMAP SCs need human UAT sign-off"
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 1/5 (human UAT)
  gaps_closed:
    - "Gap 1 — chat persona picker now DISPLAYS the effective active persona (thread pin → user default → system default) instead of the 'Select a persona' placeholder (17-12; SC-1/SC-3/SC-4 display, PERS-01/03/04/05)"
    - "Gap 2 — one-click Retry affordance on terminal interrupted assistant turns, reusing the existing retry:true send path (17-13); CR-01 data-loss BLOCKER fixed (Retry card gated to terminal row) and regression-tested"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "SC-1 visual — open a brand-new chat as a user with no pinned persona and no settings default"
    expected: "The header persona picker shows 'Board-Game Expert' (not 'Select a persona'), and the agent answers a board-game question in the expert voice"
    why_human: "Picker display is code-verified via component tests, but 'agent responds in the selected persona' (voice) is a live LLM behavior that cannot be asserted by code inspection"
  - test: "SC-2 tool call under General Assistant — pin General Assistant, then ask something that forces a tool call (e.g. 'search my documents for …')"
    expected: "A transparent tool-call card appears AND the answer reads more vanilla than the expert — confirming General Assistant retains FULL tool access"
    why_human: "Tools are structurally persona-independent in code (tools=tools and persona_voice=persona_voice are separate params, chat.py:1136/1143), but a real tool card firing under General Assistant was never observed in UAT"
  - test: "SC-3 visual — set the settings/account default persona to General Assistant, then open a new chat"
    expected: "The new-chat header picker reads 'General Assistant' and the reply is more vanilla"
    why_human: "Picker-shows-chosen-default is code-verified via test, but the settings→new-chat visual round-trip in the running app needs human confirmation"
  - test: "SC-4 reload persistence — pin a non-default persona on a thread, hard-reload the app, reopen that thread"
    expected: "The picker still shows the pinned persona after reload (persists across sessions)"
    why_human: "The component test asserts display of a pin already in thread data; actual cross-session reload persistence (DB round-trip → thread read) must be exercised live"
  - test: "SC-5 cross-user / cross-thread bleed — two concurrent users (or two threads) with different personas issuing turns at the same time"
    expected: "Each turn is answered in its OWN persona voice; no leakage of one user's/thread's persona into the other"
    why_human: "The per-turn non-cached resolver (_resolve_persona, chat.py:206/958) is code-verified, but concurrent no-bleed behavior requires a live two-actor test"
  - test: "Gap 2 live — interrupt a streaming response (or reload onto a persisted '[Response interrupted]' turn), then click Retry"
    expected: "A single Retry click re-sends the last user message with no copy/paste, the interrupted card disappears, and a fresh answer streams in"
    why_human: "Render + strip + resubmit are unit-tested, but the end-to-end interrupt→persist→reload→Retry loop against the live backend needs a human run"
---

# Phase 17: Agent Personas Verification Report

**Phase Goal:** Users can switch the chat agent's persona per-thread and set a user-level default (board-game expert default + general assistant), both retaining full tool access, with the persona's system prompt resolved per request with no cross-user/thread bleed.
**Verified:** 2026-07-14T09:05:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (17-12 picker display, 17-13 Retry + CR-01 fix)

## Goal Achievement

This is a **re-verification after gap closure**. The prior 17-VERIFICATION.md (status `gaps_found`, 1/5, human UAT 2026-07-13) reported two gaps. Both are now **CLOSED at the code level and are test-green**:

- **Gap 1** (picker showed the blank "Select a persona" placeholder) — closed by 17-12.
- **Gap 2** (no Retry affordance on interrupted turns) — closed by 17-13; a code review then found and fixed a data-loss BLOCKER (CR-01, commit `aff214f`) gating the Retry card to the terminal interrupted row only.

I independently re-ran the automated suite: **`npm run build` GREEN** and **`vitest run` = 142/142 GREEN** (both claims confirmed, not trusted). No debt markers in the modified files.

However, the **phase goal itself** is a set of visual/live behaviors (agent voice under each persona, picker display in the running app, cross-user concurrency, live interrupt→Retry loop). The gap-closure removed the display blocker that previously prevented visual sign-off, but the ROADMAP Success Criteria still require a **human UAT re-run** to be fully signed off. The code is correct — this is **not** `gaps_found`; it is `human_needed`.

### Observable Truths — ROADMAP Success Criteria (the contract)

| # | Success Criterion | Code Status | Final Sign-off | Evidence |
|---|-------------------|-------------|----------------|----------|
| SC-1 | Select persona via chat picker; agent responds in it | ✓ code-verified | ⧗ human UAT | Picker now displays the effective persona (`ChatPage.tsx:265` resolver-mirroring chain); SC-1 component test green. Voice-change was live-confirmed in prior UAT. Live re-check of new-chat display + persona voice remains. |
| SC-2 | General Assistant vanilla + FULL tools; Expert is default | ✓ code-verified | ⧗ human UAT | Tools are persona-independent: `stream_chat_completion(tools=tools, …, persona_voice=persona_voice)` are separate params (`chat.py:1136`/`1143`); comment `tools/tool_guide stay persona-independent (D-04)` (`chat.py:957`). A live tool card firing under General Assistant was never observed. |
| SC-3 | Set default persona in settings; new threads start with it | ✓ code-verified | ⧗ human UAT | `default_persona` captured from `GET /api/preferences` (`ChatPage.tsx:108/120`); picker shows chosen default (SC-3 test green). Backend applies default (prior UAT). Live settings→new-chat round-trip remains. |
| SC-4 | Persona persists across sessions / reopen | ✓ code-verified | ⧗ human UAT | Pin displayed on picker (SC-4 test green); backend PATCH persona + thread read shipped (17-07). Actual hard-reload persistence needs a live run. |
| SC-5 | Per-request resolution, no cross-user/thread bleed | ✓ code-verified | ⧗ human UAT | `_resolve_persona` runs per-turn, non-cached, inside `event_generator` (`chat.py:206`/`958`) — same scope as the key/model resolve (PERS-06 no-bleed). Mid-thread switch live-confirmed in prior UAT. Concurrent two-user bleed never tested. |

**ROADMAP score:** 5/5 code substrate verified & wired; 0/5 final visual sign-off this pass (all 5 routed to human UAT).

### Observable Truths — Gap-closure PLAN must-haves (fully code-verified this pass)

| # | Truth (source) | Status | Evidence |
|---|----------------|--------|----------|
| 1 | Unpinned thread picker DISPLAYS effective persona (Expert), not placeholder — SC-1 (17-12) | ✓ VERIFIED | `ChatPage.tsx:265` `activeThread?.persona ?? userDefaultPersona ?? personas?.find(p => p.is_default)?.id ?? null`; ChatPage.test.tsx SC-1 green |
| 2 | Settings default is DISPLAYED on new-chat picker — SC-3 (17-12) | ✓ VERIFIED | `default_persona` captured `ChatPage.tsx:108/120`; SC-3 test asserts 'General Assistant' trigger |
| 3 | Pinned persona displayed & survives thread read — SC-4 (17-12) | ✓ VERIFIED | SC-4 test asserts pinned 'general_assistant' shown |
| 4 | Display fallback NEVER fires a PATCH (display-only) — (17-12) | ✓ VERIFIED | `handleThreadPersonaChange` unchanged as sole PATCH path (`ChatPage.tsx:153-170`); no-PATCH test green (`ChatPage.test.tsx:411-424`) |
| 5 | Interrupted assistant turn shows one-click Retry — (17-13) | ✓ VERIFIED | `ChatContainer.tsx:187-223` interrupted card; test it A green |
| 6 | Retry resubmits last user msg via retry:true, no copy/paste — (17-13) | ✓ VERIFIED | `useChat.ts:390` `sendMessage(lastUser.content, { retry:true, … })`; hook test asserts `/api/threads/t1/messages?retry=true` + `content:'Q'` |
| 7 | Retry strips the interrupted assistant row from local state — (17-13) | ✓ VERIFIED | `useChat.ts:383-386` strip filter; hook test asserts row gone |
| 8 | Generic/typed error bubbles keep their Retry — no regression — (17-13) | ✓ VERIFIED | `ChatContainer.tsx:173-184` ErrorMessageBubble branch untouched; full suite 142/142 |
| 9 | CR-01: Retry card gated to TERMINAL interrupted row only (data-loss fix) | ✓ VERIFIED | `ChatContainer.tsx:189` `&& i === messages.length - 1`; regression test it D asserts non-terminal row shows NO Retry and the later good response survives |

**Gap-closure score:** 9/9 must-haves code-verified (both gaps closed).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/pages/ChatPage.tsx` | userDefaultPersona state + resolver-mirroring displayed picker value | ✓ VERIFIED | State L40; preferences capture L108/120; display chain L265; sole PATCH path L153-170 unchanged & wired at L266 |
| `frontend/src/hooks/useChat.ts` | exported INTERRUPTED_CONTENT + retry strip of interrupted row | ✓ VERIFIED | Export L55 (= backend `chat.py:1586` verbatim); strip L383-386; resubmit L390 |
| `frontend/src/components/ChatContainer.tsx` | terminal-gated interrupted Retry card wired to onRetry | ✓ VERIFIED | Import L13 (no re-hardcoded literal); branch L187-223 with `i === messages.length-1`; button `onClick={onRetry} disabled={isStreaming}` |
| `frontend/src/pages/ChatPage.test.tsx` | SC-1/3/4 display spec + no-PATCH invariant | ✓ VERIFIED | describe L361-425; 4 its green |
| `frontend/src/components/ChatContainer.test.tsx` | interrupted Retry render + CR-01 regression | ✓ VERIFIED | describe L441-510; it A–D green (it D = CR-01) |
| `frontend/src/hooks/useChat.test.tsx` | strip-and-resubmit spec | ✓ VERIFIED | it L345-372 green |
| `backend/routers/chat.py` | per-turn persona resolver (no-bleed) | ✓ VERIFIED | `_resolve_persona` L206; per-turn call L958; passed to completion L1143 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| ChatPage `/api/preferences` fetch | `userDefaultPersona` state | `setUserDefaultPersona(prefs.default_persona ?? null)` | ✓ WIRED | L108/120 |
| ChatPage render | ChatContainer `threadPersona` prop | resolver-mirroring chain | ✓ WIRED | L265 → consumed by PersonaSelector `value` L130 |
| ChatContainer interrupted card | `onRetry` (retryLastUserMessage) | `<button onClick={onRetry}>` | ✓ WIRED | L214; onRetry bound to `retryLastUserMessage` at ChatPage L260 |
| useChat retryLastUserMessage | `sendMessage(..., { retry:true })` | strip error+interrupted then resubmit | ✓ WIRED | L383-390 |
| ChatContainer sentinel | useChat `INTERRUPTED_CONTENT` | value import | ✓ WIRED | L13; literal appears 0× in ChatContainer.tsx |
| chat.py resolver | completion | `persona_voice=persona_voice`, tools separate | ✓ WIRED | L1143 (tools=tools L1136 independent) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Frontend production build type-checks | `npm run build` (`tsc -b && vite build`) | built in 4.20s, 2334 modules | ✓ PASS |
| Full frontend test suite | `npx vitest run` | 14 files, 142/142 passed | ✓ PASS |
| No debt markers in modified files | grep TBD/FIXME/XXX/HACK/PLACEHOLDER on the 3 changed source files | none found | ✓ PASS |
| Sentinel parity FE↔BE | grep `Response interrupted` | `useChat.ts:55` == `chat.py:1586` verbatim; 0× in ChatContainer.tsx | ✓ PASS |
| Persona voice actually changes; mid-thread switch applies next turn | live app | confirmed in PRIOR UAT (2026-07-13) | ✓ PASS (prior UAT) |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| PERS-01 | 17-01/03/04/06/09/10/12 | Chat-UI persona picker (mirrors model picker) | ✓ SATISFIED (code) | Picker shipped + now displays effective persona (17-12); component tests green |
| PERS-02 | 17-04/06/... | General Assistant vanilla + FULL tool access | ⧗ NEEDS HUMAN | Voice registry + persona-independent tools code-verified; live tool card under General Assistant unobserved |
| PERS-03 | 17-06/12/... | Board-game-expert is the default persona | ⧗ NEEDS HUMAN | is_default catalog row + picker default display code-verified; live new-chat visual pending |
| PERS-04 | 17-07/09/10/12 | Set default persona in settings | ✓ SATISFIED (code) | preferences.default_persona + DefaultPersonaSelector; captured & displayed |
| PERS-05 | 17-06/07/10/12 | Thread persona persists across sessions | ✓ SATISFIED (code) | PATCH persona + thread read; now visible; live reload pending |
| PERS-06 | 17-01/06/... | Per-request resolution, no cross-user/thread bleed | ⧗ NEEDS HUMAN | `_resolve_persona` per-turn non-cached code-verified; concurrent cross-user bleed untested |

All six declared requirement IDs (PERS-01…PERS-06) are present in the phase plans' `requirements:` frontmatter and mapped to Phase 17 in REQUIREMENTS.md. **No orphaned requirements.** REQUIREMENTS.md still lists PERS-02/03/06 as `Pending` — consistent with the outstanding human UAT (17-12-SUMMARY intentionally left `requirements-completed: []`).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No debt markers (TBD/FIXME/XXX) in modified files | ℹ️ Info | Blocker gate clear |
| `frontend/src/components/PersonaSelector.tsx` / ChatPage | — | WR-01: picker shows resolved default identically to a pin; no clear-to-default (onSelect can't send null to un-pin) | ⚠️ Warning (deferred) | UX asymmetry vs ModelSelector; feature still works. Deferred by decision (17-REVIEW). |
| `frontend/src/hooks/useChat.ts` | 400 | IN-03: `retryWithDemo` strips only `role==='error'`, not interrupted rows | ℹ️ Info | Latent inconsistency; currently harmless — the demo `[Use demo]` control never renders on the interrupted card |
| `frontend/src/pages/ChatPage.tsx` | 66 | Pre-existing lint (react-hooks/set-state-in-effect) on the OLD loadThreads effect | ℹ️ Info | Predates phase 17; tracked in deferred-items.md; build green |

### Human Verification Required

See the `human_verification` frontmatter block for the full list. Six live checks route to a UAT re-run:

1. **SC-1 visual** — new chat shows 'Board-Game Expert' + expert-voice answer.
2. **SC-2 tool call under General Assistant** — a tool card appears AND the answer is vanilla (full tool access retained).
3. **SC-3 visual** — settings default 'General Assistant' shows on a new chat.
4. **SC-4 reload persistence** — a pinned persona survives a hard reload.
5. **SC-5 cross-user/thread no-bleed** — two concurrent actors, different personas, no leakage.
6. **Gap 2 live Retry** — interrupt → reload → single Retry click re-sends and clears the card.

### Gaps Summary

**No code gaps.** The two prior gaps are closed and regression-tested; the CR-01 data-loss BLOCKER surfaced during code review is fixed (Retry card gated to the terminal interrupted row, with a dedicated regression test it D). Build is green and the full 142-test suite passes. The only thing standing between this phase and `passed` is a **human visual UAT re-run** of the five ROADMAP Success Criteria and the live interrupted-turn Retry loop — behaviors that are inherently visual/live/concurrent and cannot be certified by code inspection alone. Status is therefore `human_needed`, not `passed` and not `gaps_found`.

**Non-blocking / environment note (carried from prior verification):** `openrouter_api_key` may be empty while the chat model is an OpenRouter model — chat 500s until the user attaches an OpenRouter key or selects an OpenAI model. This is a BYOK setup concern, not a phase defect; ensure a working key/model is configured before the UAT run.

---

_Verified: 2026-07-14T09:05:00Z_
_Verifier: Claude (gsd-verifier)_
