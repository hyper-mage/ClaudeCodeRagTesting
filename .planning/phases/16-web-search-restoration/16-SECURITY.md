---
phase: 16
slug: web-search-restoration
status: verified
threats_total: 14
threats_closed: 14
threats_open: 0
asvs_level: 1
created: 2026-07-12
---

# Phase 16 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> State B audit (no prior SECURITY.md). Register authored at plan time — each declared
> mitigation was verified against the implemented code, not against plan intent.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| backend → Tavily (`api.tavily.com`) | Owner `tvly-` key crosses in an `Authorization: Bearer` header over HTTPS | Owner API key (secret), user query string |
| Tavily error / exception → SSE + logs | A failed search yields `str(e)` + `exc_info=True`; must not echo the key | Exception text (method+URL only), traceback |
| tool result → frontend tool card / DB | Mapped `{answer,results}` / `{error}` payload reaches the browser via the `tool_result` SSE event and is persisted to `messages.tools_used` | Output preview string + `is_error` flag |
| LLM tool-arg `query` → Tavily POST body | Query is a parameterized JSON body field, not concatenated into a URL/SQL/HTML sink | User-influenced query string |
| owner Tavily prod key → Fly secret store | Real `tvly-` key set as a Fly secret during ops verification | Secret (value hidden by Fly) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-16-01 | Information Disclosure | real key in a test fixture | mitigate | Synthetic tokens only — `test_web_search.py:36/90/129` uses `tvly-test-key`; `test_config.py:147` uses `tvly-ABC123def_-`. No real `tvly-`/`sk-or-` value committed. | closed |
| T-16-02 | Tampering | scrub coverage silently regresses | mitigate | Regression guard `test_scrub_secrets_redacts_tavily` present at `test_config.py:143-149`; asserts `tvly-` → `[redacted-key]`. | closed |
| T-16-03 | Information Disclosure | `tvly-` key in logs via `exc_info=True` | mitigate | Key rides the `Authorization` header only (`web_search_service.py:26`); `logger.error(f"…{e}", exc_info=True)` at `:49` echoes method+URL, not the header. Defense-in-depth: `scrub_secrets` extended with `_TAVILY_KEY` (`log_scrub.py:20,32`), applied via root+`routers.chat` `_ScrubFilter` on the exc_info path (`chat.py:35-78`). | closed |
| T-16-04 | Information Disclosure | `tvly-` key in the SSE error / tool-result payload | mitigate | Primary control verified: key never enters the tool_result string — it rides the header (`web_search_service.py:26`), no body `api_key`, and `str(e)` of an httpx exception carries no header. Returned dict is `{"error": str(e), "results": []}` (`:50`); SSE event carries `output` preview + `is_error` (`chat.py:1302-1303`). See Residual R-16-A (defense-in-depth scrub not on this channel — non-exploitable today). | closed |
| T-16-05 | Information Disclosure | owner key sent to the browser | accept→mitigated | Tool executes server-side only — `search_web` imported + dispatched in `execute_tool` (`chat.py:15,727`); key read from settings server-side, used only in the httpx header. Frontend receives mapped results/error, never the key. | closed |
| T-16-06 | Tampering / SSRF | user-controlled search URL | accept | Endpoint is the hardcoded constant `https://api.tavily.com/search` (`web_search_service.py:25`); only `query` is variable and is a JSON body param — no user-controlled URL, no SSRF sink. | closed |
| T-16-07 | Tampering | TLS downgrade / MITM | accept | Fixed `https://` endpoint (`web_search_service.py:25`); httpx verifies certs by default; no `verify=False` anywhere in the file. | closed |
| T-16-08 | Denial of Service | slow provider blocks the async SSE loop | accept | Bounded `timeout=30` on `httpx.post` (`web_search_service.py:33`); a timeout degrades to the graceful `{"error"}` path (`:48-50`). Sync-in-async re-architecture out of scope for a restoration. | closed |
| T-16-09 | Spoofing / Elevation (cost) | tool exposed without a configured key | mitigate | Fail-closed: `if settings.web_search_enabled: tools.append(WEB_SEARCH_TOOL)` (`chat.py:961-962`, uncommented) AND service re-guard `if not settings.web_search_enabled: return {"error":…}` (`web_search_service.py:12`). `web_search_enabled = bool(web_search_api_key)` (`config.py:199-200`). Unit-locked by `test_gating_fail_closed`. | closed |
| T-16-10 | Information Disclosure | key/secret rendered in the failed-state card | accept→mitigated upstream | Card renders only `parsed.output` + `is_error` (`useChat.ts:218`, `ToolCallCard.tsx:188-190`); the tool_result payload contains no key (T-16-04). Card adds no new data source. See Residual R-16-A. | closed |
| T-16-11 | Tampering (XSS) | error text injected into the DOM | accept | Output rendered as escaped text via React in `<pre>{output}</pre>` (`ToolCallCard.tsx:188-190`); no `dangerouslySetInnerHTML` anywhere in the component. | closed |
| T-16-12 | Information Disclosure | raw `tvly-` key leaked during secret-set / verification | mitigate | Key set only via `fly secrets set` (value hidden in `fly secrets list`); never echoed to chat/logs/SUMMARY (16-04-SUMMARY acceptance). `scrub_secrets` `tvly-` backstop in code (`log_scrub.py:20`). | closed |
| T-16-13 | Denial of Service | failure smoke leaves prod on an invalid key | mitigate | Failure smoke used a temporary invalid key, then the real key was restored + restarted; owner-confirmed **Deployed** (digest `feca87ad`, v36, both machines) before phase close (16-04-SUMMARY §Verification/Threat Surface). | closed |
| T-16-14 | Tampering | wrong app / environment targeted | mitigate | Prod app discovered via `fly status` (`boardgame-rag-prod`), not hardcoded; prod distinguished from dev via `.env.prod`; owner approved each command (16-04-SUMMARY §Accomplishments/Decisions). | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Residual Risks & Notes

**R-16-A — tool_result `output` reaches the SSE stream + DB unscrubbed (WR-03, from 16-REVIEW.md).**
`tool_output_preview = tool_result[:2000]` is emitted on the `tool_result` SSE event (`chat.py:1284,1302`) and persisted to `messages.tools_used` (`chat.py:1290-1292`) **without** passing through `scrub_secrets`, unlike the `_sse_error` and log chokepoints. This is **not exploitable for the phase's target secret**: the `tvly-` key rides the `Authorization` header only and is absent from any tool's `str(e)`, so no secret currently reaches this channel — T-16-04 and T-16-10 remain genuinely CLOSED on their declared scope. It is recorded as a residual because the defense-in-depth redaction the phase hardened has a gap on this one backend→client/DB channel: any *future* tool whose exception text embeds a secret would leak here silently. Recommended (non-blocking) hardening: route the preview through `scrub_secrets` before emit/persist. Classification: WARNING, not a BLOCKER (block_on: high; non-exploitable today).

**Related review findings (informational, outside this audit's mitigate/accept verification):** WR-01 (substring classifier `tool_result_is_error` — false pos/neg for non-web tools), WR-02 (`web_search`/`query_database` dispatch lacks a `KeyError` arg guard), IN-01 (`web_search_depth` comment lists `fast`/`ultra-fast` which Tavily rejects), IN-02 (env-fragile default test). None affect a Phase-16 declared threat disposition; logged for the next hardening pass.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-16-01 | T-16-05 | Tool runs server-side only; key stays in the httpx header, never sent to the browser. Verified in code (`chat.py:727`, `web_search_service.py:26`). | Plan author (16-02) | 2026-07-12 |
| AR-16-02 | T-16-06 | Endpoint is a hardcoded constant; only the `query` body param varies — no user-controlled URL / SSRF sink. Verified (`web_search_service.py:25`). | Plan author (16-02) | 2026-07-12 |
| AR-16-03 | T-16-07 | Fixed `https://` endpoint; httpx verifies certs by default; no `verify=False`. Verified (`web_search_service.py:25`). | Plan author (16-02) | 2026-07-12 |
| AR-16-04 | T-16-08 | `timeout=30` bound; timeout degrades to graceful `{"error"}`. Sync-in-async rework out of scope for a restoration. Verified (`web_search_service.py:33,48-50`). | Plan author (16-02) | 2026-07-12 |
| AR-16-05 | T-16-10 | Failed-state card renders only the output preview + `is_error`; payload carries no key. Verified (`ToolCallCard.tsx:188-190`). | Plan author (16-03) | 2026-07-12 |
| AR-16-06 | T-16-11 | Error text rendered as React-escaped text in `<pre>`; no `dangerouslySetInnerHTML`. Verified (`ToolCallCard.tsx:188-190`). | Plan author (16-03) | 2026-07-12 |
| AR-16-07 | R-16-A / T-16-04,10 | tool_result `output` bypasses `scrub_secrets` on the SSE/DB channel; non-exploitable today (no secret reaches this string). Accepted as a documented residual pending optional hardening. | Security auditor | 2026-07-12 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-12 | 14 | 14 | 0 | gsd-security-auditor |

**Method:** Each declared mitigation verified by grep/read against the implemented code (`web_search_service.py`, `config.py`, `routers/chat.py`, `log_scrub.py`, `useChat.ts`, `ToolCallCard.tsx`, `tests/test_web_search.py`, `tests/test_config.py`). `accept`/`accept→mitigated` rationales re-checked against the code; ops-disposition threats (T-16-12..14) verified against the 16-04 prod-verification evidence. No `## Threat Flags` section present in any SUMMARY → no unregistered flags. WR-03 assessed directly against `chat.py:1284,1290-1306`: primary control for T-16-04/T-16-10 holds; scrub gap recorded as residual R-16-A.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-12
