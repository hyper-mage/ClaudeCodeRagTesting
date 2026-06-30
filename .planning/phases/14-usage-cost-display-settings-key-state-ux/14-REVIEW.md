---
phase: 14-usage-cost-display-settings-key-state-ux
reviewed: 2026-06-30T02:48:36Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - backend/config.py
  - backend/models/schemas.py
  - backend/routers/chat.py
  - backend/routers/keys.py
  - backend/tests/test_error_surfacing.py
  - backend/tests/test_keys_balance.py
  - backend/tests/test_thread_usage_exposed.py
  - frontend/src/components/ChatContainer.tsx
  - frontend/src/components/ErrorMessageBubble.tsx
  - frontend/src/components/IconSidebar.tsx
  - frontend/src/components/MessageBubble.tsx
  - frontend/src/components/MobileTopBar.tsx
  - frontend/src/hooks/useChat.ts
  - frontend/src/hooks/useKeyStatus.ts
  - frontend/src/pages/ChatPage.tsx
  - frontend/src/pages/SettingsPage.tsx
findings:
  critical: 1
  warning: 2
  info: 4
  total: 7
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-30T02:48:36Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

This phase adds the `GET /api/keys/balance` server-side proxy, a `usage` read-path on `MessageResponse`, mid-stream 401/403 error branching in chat, and the frontend cost-display / tri-state key-state UX.

The phase's primary security focus — keeping the decrypted `sk-or-…` key off the wire and out of logs — is correctly handled for the **happy path and the provider-error (non-2xx) path** of `/api/keys/balance`, and the mid-stream error branching in `chat.py` is ordered correctly (`RateLimitError` before the `APIStatusError` 402/401/403/else cascade). The `MessageResponse.usage` read-path fix is correct and test-covered. Frontend correctly reads server-computed `is_low` without re-deriving cost or polling.

However, there is **one BLOCKER**: the balance handler parses the OpenRouter response *outside* its `try/except`, so an abnormal-but-realistic 2xx body produces an unhandled 500 whose traceback (logged with `exc_info` by Starlette's default handler) carries the decrypted key in stack-frame locals — directly defeating the T-14-02 "no exc_info on the balance path / key never reaches logs" guarantee and the "provider error → generic 502" contract. Two WARNINGs concern event-loop blocking and redundant external balance calls.

## Critical Issues

### CR-01: Balance proxy parses the provider response outside `try/except` — decrypted key can leak into a 500 traceback

**File:** `backend/routers/keys.py:126-147`
**Issue:**
The decrypted key is bound at line 126, but only `httpx.get(...)` + `resp.raise_for_status()` are wrapped in the `try/except httpx.HTTPError`. The response parsing and comparison are **outside** the protected block:

```python
key = decrypt_key(row.data["encrypted_key"])   # decrypted, in scope below
try:
    resp = httpx.get(... headers={"Authorization": f"Bearer {key}"} ...)
    resp.raise_for_status()
except httpx.HTTPError as e:
    logger.warning(f"balance fetch failed: {scrub_secrets(str(e))}")
    raise HTTPException(502, "Couldn't fetch the OpenRouter balance.")

data = resp.json().get("data", {})              # <-- outside try
remaining = data.get("limit_remaining")          # <-- outside try
is_low = remaining is not None and remaining < threshold   # <-- outside try
```

Three realistic provider responses raise here and are **not** `httpx.HTTPError`, so they escape as an unhandled exception:
- A 2xx with a non-JSON body → `resp.json()` raises `json.JSONDecodeError`.
- `{"data": null}` → `.get("data", {})` returns `None` (key present), then `None.get(...)` raises `AttributeError`.
- `limit_remaining` returned as a non-numeric type (e.g. a string) → `remaining < threshold` raises `TypeError`.

`backend/main.py` registers no generic exception handler, so the exception propagates to Starlette's `ServerErrorMiddleware`, which logs it with `exc_info`. The decrypted `key` local is in scope in the `balance()` frame at all three failure points, so the `sk-or-…` value lands in the logged traceback's stack-frame locals. The `_ScrubFilter` is only installed on root handlers at `routers.chat` import time and is not guaranteed to be attached to the handler that logs uncaught 500s (uvicorn's `uvicorn.error` logger typically does not propagate to root). This is exactly the T-14-02 leak vector the phase claims to prevent ("no exc_info on the balance path"), and it also bypasses the documented "provider error surfaces a fixed generic 502" contract. Note `decrypt_key()` at line 126 is itself unguarded too (corrupt ciphertext / rotated-out key → unhandled 500), though no plaintext is in scope at that point.

**Fix:** Pull the parsing into the protected block (and validate the numeric type), so every provider/parse failure maps to the scrubbed generic 502 and never reaches an `exc_info` traceback while the key is live:

```python
key = decrypt_key(row.data["encrypted_key"])
try:
    resp = httpx.get(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {key}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json().get("data") or {}
    remaining = data.get("limit_remaining")
    if remaining is not None and not isinstance(remaining, (int, float)):
        remaining = None
except (httpx.HTTPError, ValueError, TypeError, AttributeError) as e:
    logger.warning(f"balance fetch failed: {scrub_secrets(str(e))}")  # NO exc_info
    raise HTTPException(status_code=502, detail="Couldn't fetch the OpenRouter balance.")
finally:
    del key  # drop the plaintext from the frame ASAP

threshold = get_settings().low_balance_threshold_usd
is_low = remaining is not None and remaining < threshold
return BalanceResponse(connected=True, limit_remaining=remaining, is_low=is_low)
```

Also consider wrapping `decrypt_key()` in the same protective mapping. (The existing test suite does not cover the malformed-2xx path, so this gap is currently invisible to CI — adding a `test_balance_malformed_body` would lock the fix.)

## Warnings

### WR-01: Synchronous `httpx.get` inside the async `balance` handler blocks the event loop

**File:** `backend/routers/keys.py:128-132`
**Issue:** `balance()` is `async def`, but it calls the blocking, synchronous `httpx.get(..., timeout=15)`. A slow or hanging OpenRouter connection freezes the entire async worker for up to 15 seconds, stalling all concurrent requests on that worker — including in-flight SSE chat streams. This is an availability/robustness concern (distinct from throughput): one stuck provider call degrades unrelated users. The impact compounds with WR-02 (multiple simultaneous balance calls per page mount).
**Fix:** Use an async client so the await yields the loop, e.g.:

```python
async with httpx.AsyncClient(timeout=15) as client:
    resp = await client.get(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {key}"},
    )
    resp.raise_for_status()
```

(or wrap the sync call in `fastapi.concurrency.run_in_threadpool`). The test patches `httpx.get`, so switching to `AsyncClient` requires updating the test's patch target.

### WR-02: `useKeyStatus` fires duplicate `/api/keys/balance` calls from every mounted instance

**File:** `frontend/src/hooks/useKeyStatus.ts:39-95`
**Issue:** `useKeyStatus` holds per-component state with no shared cache/context. `IconSidebar` (desktop rail, `md:flex`) and `MobileTopBar` (`md:hidden`) are **both** mounted in the DOM on every page regardless of viewport, and `SettingsPage` adds a third instance. Each instance independently fires `GET /api/keys/status` *and* `GET /api/keys/balance` on mount and on every `notifyKeyStatusChanged()` broadcast. Because `/balance` proxies to OpenRouter server-side, navigating to Settings triggers ~3 simultaneous authenticated OpenRouter round-trips for the same data — multiplying the user's OpenRouter API usage and risking their key's own rate limits, and amplifying WR-01's event-loop blocking. (This is not a polling violation — it is on-demand — but it is redundant.)
**Fix:** Hoist the status/balance fetch into a shared context/provider (or a module-level cache with subscriber dedup) so the persistent dots and the Settings page read one fetched value, with a single `refresh`/`refreshBalance` per broadcast.

## Info

### IN-01: `SettingsPage` balance line ignores `balance.connected`, mislabeling a disconnected balance as "Pay-as-you-go"

**File:** `frontend/src/pages/SettingsPage.tsx:112-120`
**Issue:** The cascade treats `balance.limit_remaining === null` as "Pay-as-you-go — no limit set" without checking `balance.connected`. If the key row is deleted between the status fetch and the balance fetch (a narrow race), `/balance` returns `{connected:false, limit_remaining:null}` while the connected block still renders (driven by `status?.connected`), so the user sees "Pay-as-you-go — no limit set" for a key that is actually disconnected.
**Fix:** Gate the pay-as-you-go branch on `balance.connected === true && balance.limit_remaining === null`, and treat `connected === false` as the unavailable/disconnected case.

### IN-02: In-band SSE error with an empty `error` string is silently swallowed

**File:** `frontend/src/hooks/useChat.ts:260-272`
**Issue:** The error branch does `throw new Error(parsed.error)`. The `catch (parseErr)` re-throws only when `parseErr.message` is truthy. If the backend ever yields `{"error": ""}` (e.g. the generic `Exception` path at `chat.py:1262` when `str(e)` is empty), the thrown `Error("")` has a falsy `message` and is swallowed as if it were an unparseable line. The assistant placeholder then stays empty with no error bubble and no toast.
**Fix:** Detect the error branch explicitly (e.g. a sentinel/flag) rather than relying on `err.message` truthiness, or default an empty code to `'upstream_error'` before throwing.

### IN-03: Balance amounts rendered as raw floats

**File:** `frontend/src/pages/SettingsPage.tsx:118,128`
**Issue:** `Balance: ${balance.limit_remaining}` and `Balance low: ${balance.limit_remaining}` interpolate the raw number. OpenRouter can report a long-precision float (e.g. `4.873291...`), producing an awkward caption. This is an intentional "render as reported, never recompute" choice, but display *formatting* (not cost recomputation) would read cleaner.
**Fix:** Apply a display-only format, e.g. `${balance.limit_remaining.toFixed(2)}`, which does not violate the "no client recompute" rule (it is the same reported value, formatted).

### IN-04: New cost caption's light-mode color sits on a fixed-dark bubble surface

**File:** `frontend/src/components/MessageBubble.tsx:34` (and `:44-48`)
**Issue:** `CostLine` uses `text-gray-600 dark:text-gray-400`, chosen (per its comment) to avoid "gray-500 on white." But the assistant bubble it renders inside is `bg-gray-800` with no light-mode variant (line 44-48), so in light mode the caption is `text-gray-600` (#4b5563) on `bg-gray-800` (#1f2937) — low contrast. In the default dark theme this is fine; only the light-theme + assistant-bubble combination is affected. (The dark-only bubble surface itself is pre-existing.)
**Fix:** Either give the assistant bubble a light-mode surface token, or lighten the caption so it reads on the gray-800 bubble in both themes (e.g. `text-gray-300`).

---

_Reviewed: 2026-06-30T02:48:36Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
