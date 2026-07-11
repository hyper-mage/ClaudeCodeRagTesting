# Phase 16: Web Search Restoration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-11
**Phase:** 16-web-search-restoration
**Areas discussed:** When to web-search, Citation format, Failure UX, Search tuning

---

## When to web-search

| Option | Description | Selected |
|--------|-------------|----------|
| Fallback for external/current info | Prefer KB for rules/mechanics; web for info not in KB — prices, availability, expansions, BGG rankings, news | ✓ |
| Agent's free discretion | No strong steer; agent web-searches whenever it judges useful | |
| Only after a KB miss | Strict: web only fires when KB search returns nothing | |

**User's choice:** Fallback for external/current info
**Notes:** Encode as tool-selection/system-prompt guidance so the agent doesn't web-search rules already in the KB. Not strict "only after miss" — agent may go straight to web for inherently external queries.

---

## Citation format

| Option | Description | Selected |
|--------|-------------|----------|
| Inline links + Sources list | Inline [title](url) where used, plus short 'Sources:' list at end | ✓ |
| Inline links only | Just inline markdown links, no end list | |
| Sources list at end only | Plain prose, then numbered Sources list | |

**User's choice:** Inline links + Sources list
**Notes:** Update system prompt citation guidance (currently only "always cite your sources with URLs").

---

## Failure UX (WSRCH-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Tool card failed + brief note | Card shows failed; agent notes it couldn't reach web, answers best-effort | ✓ |
| Silent fallback | Agent answers from other sources, no mention | |
| Surface + don't fabricate | Agent declines web-dependent part rather than guessing | |

**User's choice:** Tool card failed + brief note
**Notes:** Builds on the existing graceful `{"error": ...}` return + `exc_info=True` log; ensure error surfaces to frontend tool card as failed state and agent acknowledges briefly.

---

## Search tuning

| Option | Description | Selected |
|--------|-------------|----------|
| Keep basic / 5 / answer-on | search_depth=basic, max_results=5, include_answer=true (current) | |
| Advanced depth | search_depth=advanced — better quality, more cost/latency | |
| Make depth env-configurable | Expose search_depth as a setting, default basic | ✓ |

**User's choice:** Make depth env-configurable
**Notes:** Add `web_search_depth` setting (default "basic") mirroring the `web_search_max_results` pattern; keep include_answer=true, max_results=5.

## Claude's Discretion

- Exact wording of system-prompt / tool-guide edits (must encode D-01 and D-02).
- Seam for the "couldn't reach web" acknowledgement (tool-result payload vs prompt guidance).
- Prod key rollout mechanics (Fly secret).

## Deferred Ideas

- Multiple/switchable web search providers (WSRCH-F1) — future milestone.
- Per-thread web-search on/off toggle (WSRCH-F2) — future milestone.
- Per-user BYOK web-search keys — explicitly out of scope.
