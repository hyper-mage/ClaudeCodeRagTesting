# Phase 11: Per-Request Key + Model Resolution (chat-loop seam) - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 11 (6 MODIFY backend, 1 NEW migration, 4 NEW/EXTEND tests)
**Analogs found:** 11 / 11 (every seam has an in-repo analog — this is a wiring phase, not greenfield)

> **Orienting note for the planner:** Almost every "analog" here is the file's *own current owner-key form*. This phase threads two explicit params (`api_key`, `model`) — plus a `trace: bool` — through call sites that today read global `settings`. Copy the existing shape; add params; never rewrite. The cross-cutting analogs (decrypt, empty-row guard, scrub regex, additive migration, config field + test) come from Phases 9/10 and are reused verbatim.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/services/llm_service.py` | service | streaming / request-response | its own `get_llm_client()` + `stream_chat_completion()` (current owner-key form) | exact (self) |
| `backend/routers/chat.py` | route / controller | streaming (SSE) + event-driven | its own `send_message`/`event_generator` + `keys.py:79` empty-row guard | exact (self) |
| `backend/config.py` | config | n/a | existing `chat_max_iterations` / `key_encryption_secret` fields + `resolved_llm_api_key` property | exact (self) |
| `backend/services/rerank_service.py` | service | request-response (per-doc CRUD scoring) | its own `rerank_with_llm()` (current owner-key form) | exact (self) |
| `backend/services/subagent_service.py` | service | request-response (non-streaming completion) | its own `run_document_analysis()` (current owner-key form) | exact (self) |
| `backend/services/explorer_service.py` | service | event-driven (multi-iteration tool loop) | its own `run_exploration()` + `_summarize_findings()` (current owner-key form) | exact (self) |
| `supabase/migrations/20240301000029_*.sql` | migration | n/a (additive nullable column) | `20240301000024_add_tools_used_to_messages.sql` + `028_add_connected_at` | exact |
| `backend/tests/test_key_model_resolution.py` | test | n/a | `test_crypto_service.py` (monkeypatch + cache_clear) + `conftest.mock_stream_chat_completion` | role-match |
| `backend/tests/test_langsmith_gate.py` | test | n/a | `test_tracing.py` + `llm_service.get_llm_client` wrap-block | role-match |
| `backend/tests/test_error_surfacing.py` | test | n/a | `conftest.mock_stream_chat_completion` + `sentry.ts` regex | role-match |
| `backend/tests/test_usage_capture.py` | test | n/a | `conftest.mock_stream_chat_completion` (extend with `usage` event) | role-match |
| `backend/tests/test_config.py` (EXTEND) | test | n/a | `test_config.py:5-47` (default + env-override pairs) | exact |

---

## Pattern Assignments

### `backend/services/llm_service.py` (service, streaming)

**Analog:** its own current form (`llm_service.py:11-20` client; `35-150` stream).

**Imports pattern** (lines 1-8) — keep as-is; the `wrap_openai` ImportError fallback is exactly what the trace-gate needs:
```python
from openai import OpenAI
from config import get_settings
from typing import Generator

try:
    from langsmith.wrappers import wrap_openai
except ImportError:
    wrap_openai = None
```

**Client construction — the trace-gate seam** (lines 11-20, current): add `api_key` + `trace` params; only wrap when `trace` is True (D-10). This is the SEC-04 + SEC-01 lever and it is purely additive (no module-level client, no `@lru_cache` here — keep it that way):
```python
def get_llm_client() -> OpenAI:                                  # ← add (api_key: str | None = None, trace: bool = True)
    settings = get_settings()
    client = OpenAI(
        api_key=settings.resolved_llm_api_key,                   # ← api_key or settings.resolved_llm_api_key
        base_url=settings.llm_base_url,
    )
    if wrap_openai and settings.langsmith_api_key:               # ← AND `trace` — skip wrap for user keys (D-10)
        client = wrap_openai(client)
    return client
```
> `get_embedding_client()` (lines 23-32) is ingestion/embedding-only — **do NOT thread the chat key into it.** Leave untouched (parallels `metadata_service` staying out of scope).

**Stream signature + model read** (lines 35-54, 100-108): add `api_key` + `model` params; pass them down. Today `model` comes from `settings.llm_model` at line 101 and the client is built arg-less at line 54:
```python
settings = get_settings()
client = get_llm_client()                                        # ← get_llm_client(api_key=api_key, trace=trace)
...
kwargs = {
    "model": settings.llm_model,                                # ← model or settings.llm_model
    "messages": full_messages,
    "stream": True,
}
```

**Usage-capture restructure — Pattern 4 / D-04** (lines 113-150, current): the `return` at **line 148** discards the trailing `usage` chunk. Drain to stream end; capture `chunk.usage` whenever present; yield a `usage` event before `done`. Copy the existing chunk loop, replace the early `return`:
```python
for chunk in stream:
    choice = chunk.choices[0] if chunk.choices else None
    if not choice:
        continue
    ...
    if choice.finish_reason == "tool_calls":
        yield {"type": "tool_call", "tool_calls": list(tool_calls_acc.values())}
        return                                                   # ← REMOVE: drain instead; capture chunk.usage; usage rides the LAST chunk (often choices==[])
yield {"type": "done"}                                           # ← yield {"type":"usage", "usage": _usage_to_dict(usage_obj)} first if captured
```
> Note: the `if not choice: continue` at lines 115-116 will **skip** the trailing usage-only chunk (where `choices == []`). The usage capture MUST read `chunk.usage` BEFORE the `continue`, not after.

**402/429 catch — Pattern 5 / D-12:** lives in `chat.py` (the caller), not here. `subagent_service.py:4` already imports `openai` and catches `openai.APITimeoutError` (line 145) — mirror that import + catch-order style in chat.py.

---

### `backend/routers/chat.py` (route, streaming SSE + event-driven)

**Analog:** its own `send_message`/`event_generator` (470-908) + `keys.py:79-93` (empty-row guard) + `subagent_service.py:138-153` (typed `openai` catch).

**Empty-row guard for the key read — Pattern 1 / Example 3** (mirror `keys.py:79-88` exactly): the resolution block's fail-closed branch IS this guard. Copy the `if not row or not row.data:` shape — it is proven green in Phase 10:
```python
# keys.py:79-88 (PROVEN) — copy this guard shape into _resolve_key_and_model
row = (
    get_supabase()
    .table("user_api_keys")
    .select("key_label, connected_at")                          # ← resolution selects "encrypted_key"
    .eq("user_id", user_id)
    .maybe_single()
    .execute()
)
if not row or not row.data:
    return {"connected": False}                                 # ← resolution: this is the elif-demo / else-refuse fork
```

**Decrypt path** (`crypto_service.decrypt_key`, Phase 9 — `crypto_service.py:40-42`): in-memory, per-request. Call it inside the `if row.data:` branch; drop the plaintext after passing to `get_llm_client`:
```python
api_key = decrypt_key(row.data["encrypted_key"])               # short-lived local — never logged/traced/returned
```

**Resolution block placement** — slots into `event_generator` **before the budget build at line 581** and the assistant-row insert at 600. The thread row is already a `SELECT *` (line 480-487) so `thread.data.get("model")` is a safe absent-key read (Pattern 2 / D-03 — no extra query, no `42703`):
```python
thread = (
    db.table("threads")
    .select("*")                                                # ← SELECT * — thread.data.get("model") is absent-key-safe pre-P13
    .eq("id", thread_id).eq("user_id", user_id)
    .maybe_single().execute()
)
```

**Budget lookup — Pitfall 1 (the easy-to-miss fifth owner-key read)** (lines 588-597, current): switch BOTH args to the resolved values:
```python
if settings.llm_base_url and "openrouter" in settings.llm_base_url:
    dynamic_length = fetch_model_context_length(
        settings.llm_model, settings.resolved_llm_api_key       # ← fetch_model_context_length(model, api_key)
    )
    ...
    logger.info(f"Using dynamic context length {dynamic_length} for {settings.llm_model}")  # ← {model}
```

**Threading into `stream_chat_completion`** (lines 620-626, current call): add `api_key=`, `model=`, `trace=`:
```python
for event in stream_chat_completion(
    current_messages,
    tools=tools,
    tool_guide=TOOL_SELECTION_GUIDE if tools else None,
    source_hint=source_scope,
    scope_hint=scope_hint if scope_hint else None,             # ← add api_key=api_key, model=model, trace=(not is_user_key)
):
```

**Threading into aux dispatch (D-01)** — the two sub-agent dispatch sites pass `user_id`/`query` today; add `api_key=`/`model=`:
- `run_exploration(...)` call at **lines 696-700** (inside `_drive`)
- `run_document_analysis(...)` call at **lines 761-765** (inside `_drive_doc`)
- `execute_tool(fn_name, fn_args, user_id)` at **line 797** → must forward key+model into `search_documents` → `rerank` (the rerank path)

**SSE error scrub — Pitfall 2 / D-11** (lines 905-908, current — this is the leak site): route `str(e)` through `scrub_secrets()`. Prefer the structured fixed-copy helper (`_sse_error`) for 402/429/no_api_key:
```python
yield {
    "event": "error",
    "data": json.dumps({"error": str(e)}),                     # ← json.dumps({"error": scrub_secrets(str(e))}) — str(e) can echo sk-or-…
}
```

**Done event — usage + mode signal (D-04/D-08)** (lines 889-895, current): extend the payload (the recommended low-FE-touch path — `useChat.ts:185` keys only on `message_id` and ignores extra keys):
```python
yield {
    "event": "done",
    "data": json.dumps({
        "message_id": assistant_msg_id,
        "content": full_content,                                # ← add "usage": turn_usage, "mode": mode (if "demo")
    }),
}
```

**Usage persistence** — mirror the existing assistant-row update at lines 879-882 (it already writes `content` + `tools_used`; add the new `usage` column):
```python
db.table("messages").update({
    "content": full_content,
    "tools_used": tools_used_acc if tools_used_acc else None,  # ← add "usage": turn_usage or None
}).eq("id", assistant_msg_id).execute()
```

**402/429 catch — Pattern 5 / D-12** (wrap the `stream_chat_completion` loop): mirror `subagent_service.py:4,145` (`import openai` + `except openai.APITimeoutError`). Catch `RateLimitError` (429) **before** the generic `APIStatusError`, then branch on `.status_code == 402` (no 402 subclass exists).

---

### `backend/config.py` (config)

**Analog:** existing `chat_max_iterations` field (line 111) + `key_encryption_secret` (line 23) + `resolved_llm_api_key` property (lines 134-136).

**Field pattern** — add two fields next to the existing chat/BYOK fields. Copy the bool-default + comment style of `rerank_enabled: bool = False` (line 73) and the env-doc style of `key_encryption_secret`:
```python
# existing analogs to copy:
rerank_enabled: bool = False                                   # ← demo_fallback_enabled: bool = False  (env-driven, OFF in dev AND prod — D-09)
llm_model: str = ""                                            # ← demo_fallback_model: str = "meta-llama/llama-3.3-70b-instruct:free"  (D-06; executor re-confirms a live :free slug)
```

**Property pattern** (lines 134-136) — the resolution helper is *conceptually* a per-request analog of this property, but it MUST NOT live on `Settings` and MUST NOT be `@lru_cache`'d (Pitfall 8 — caching a key-bearing value = cross-tenant bleed). Keep `resolved_llm_api_key` as the **owner-only** fallback the demo branch reads:
```python
@property
def resolved_llm_api_key(self) -> str:                         # ← demo branch reads THIS; user branch never touches it
    return self.llm_api_key or self.openai_api_key
```

**Dual-env** — already handled by the `ENV_FILE` switch at lines 6-9; the two new env vars (`DEMO_FALLBACK_ENABLED`, `DEMO_FALLBACK_MODEL`) ride the same `.env` / `.env.prod` mechanism. No new loading code.

---

### `backend/services/rerank_service.py` (service, per-doc scoring)

**Analog:** its own `rerank_with_llm()` (lines 19-43).

**Current owner-key form** (lines 19-34) — add `api_key`/`model` params to `rerank()` (line 77) and `rerank_with_llm()` (line 19), thread them to the client + the `create(model=...)` call:
```python
def rerank_with_llm(query: str, documents: list[dict]) -> list[dict]:   # ← add api_key=, model=
    settings = get_settings()
    client = get_llm_client()                                   # ← get_llm_client(api_key=api_key, trace=trace)
    ...
    response = client.chat.completions.create(
        model=settings.llm_model,                               # ← model or settings.llm_model
        messages=[...],
        response_format={"type": "json_object"},
    )
```
> Caller is `search_documents` (invoked from `chat.py:execute_tool` line 797). The key+model must reach `rerank()` from there. `rerank_with_api()` (line 46) uses a *separate* dedicated rerank provider key — leave it untouched.

---

### `backend/services/subagent_service.py` (service, non-streaming completion)

**Analog:** its own `run_document_analysis()` (lines 53-163).

**Current owner-key form** (lines 137-144): add `api_key`/`model` to the entry signature (line 54), thread to the client + `create`:
```python
client = get_llm_client()                                       # ← get_llm_client(api_key=api_key, trace=trace)
try:
    response = client.chat.completions.create(
        model=settings.llm_model,                               # ← model or settings.llm_model
        messages=messages,
        max_tokens=settings.subagent_max_tokens,
        timeout=settings.subagent_timeout,
    )
except openai.APITimeoutError:                                  # existing typed-catch style — mirror for 402/429 in chat.py
    ...
```
> This file ALREADY imports `openai` (line 4) and catches a typed exception (line 145) — it is the in-repo reference for the chat.py 402/429 catch pattern.

---

### `backend/services/explorer_service.py` (service, multi-iteration tool loop)

**Analog:** its own `run_exploration()` (lines 203-329) + `_summarize_findings()` (lines 103-200).

**Three owner-key read sites to thread** — the executor must catch ALL of them (Pitfall 4):
- `client = get_llm_client()` — **line 218** (loop client) → `get_llm_client(api_key=, trace=)`
- `model=settings.llm_model` in the loop `create` — **line 239**
- `model=settings.llm_model` in `_summarize_findings._try` — **line 136**

```python
# line 218 (entry) — client built once for the whole exploration loop
client = get_llm_client()                                       # ← get_llm_client(api_key=api_key, trace=trace)
...
# line 237-242 (loop iteration)
response = client.chat.completions.create(
    model=settings.llm_model,                                  # ← model
    messages=messages, tools=tool_schemas,
    timeout=settings.explorer_timeout,
)
...
# line 134-140 (_summarize_findings._try) — thread `model` in via closure or param
return client.chat.completions.create(
    model=settings.llm_model,                                  # ← model
    messages=summary_messages, timeout=settings.explorer_timeout, **model_kwargs,
)
```
> `run_exploration` + `run_document_analysis` are dispatched from `chat.py` via the `asyncio.to_thread` queue drivers (`_drive` line 694, `_drive_doc` line 759). The resolved `api_key`/`model` must be captured into those closures.

---

### `supabase/migrations/20240301000029_add_usage_to_messages.sql` (migration, additive nullable)

**Analog:** `20240301000024_add_tools_used_to_messages.sql` (the closest — same table, additive nullable JSONB) + `028_add_connected_at_to_user_api_keys.sql` (the rationale/comment style + "next free number" reasoning).

**`tools_used` migration — copy this exactly** (whole file):
```sql
-- Add tools_used JSONB column to messages table for persisting tool call card data.
-- ...
ALTER TABLE messages ADD COLUMN tools_used JSONB DEFAULT NULL;
```
New file: `ALTER TABLE messages ADD COLUMN IF NOT EXISTS usage JSONB DEFAULT NULL;` (or split token/cost columns — Claude's Discretion). Store the summed OpenRouter `usage` dict (incl. `cost`).

**Why these are the right analogs:**
- `024` proves the additive-nullable-JSONB-on-`messages` shape — no backfill, old rows keep `NULL`, Phase 14 tolerates null (D-04).
- `028` documents the **"next free number"** discipline (025/026/027/028 already applied to dev+prod — see MEMORY: prod has 025-028). **029 is the next free number.** Use the `IF NOT EXISTS` guard like 028 (line 28) for idempotent replay (see MEMORY `reference_supabase_migration_history_repair`).
- The `messages` RLS (migration 002) is unchanged — additive column inherits existing policies.

---

### `backend/tests/test_key_model_resolution.py` + `test_langsmith_gate.py` + `test_error_surfacing.py` + `test_usage_capture.py` (NEW tests)

**Analogs:** `test_crypto_service.py:11-20` (monkeypatch + `get_settings.cache_clear()`), `conftest.py:75-126` (`mock_stream_chat_completion`), `test_config.py:5-47` (default/env-override pairs), `sentry.ts:31` (scrub regex), `tracing.py` + `llm_service.get_llm_client` (wrap-gate).

**Settings monkeypatch + cache-clear (MANDATORY for any config-touching test)** — copy `test_crypto_service.py:11-20`. Because `get_settings()` is `@lru_cache`'d (config.py:147-149), every `monkeypatch.setenv(...)` for `DEMO_FALLBACK_*` MUST be followed by `get_settings.cache_clear()`:
```python
key = Fernet.generate_key().decode()
monkeypatch.setenv("KEY_ENCRYPTION_SECRET", key)
from config import get_settings
get_settings.cache_clear()                                      # ← REQUIRED after every setenv on a cached settings field
from services import crypto_service
ct = crypto_service.encrypt_key("sk-or-v1-example")
```

**Config default/env-override pair (extend `test_config.py`)** — copy `test_config.py:35-47` verbatim for `demo_fallback_enabled` (default False) + `demo_fallback_model` (default the `:free` slug):
```python
def test_key_encryption_secret_default():
    from config import Settings
    s = Settings()
    assert s.key_encryption_secret == ""                       # ← demo_fallback_enabled is False / demo_fallback_model is the :free slug

def test_key_encryption_secret_env_override(monkeypatch):
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", "abc")
    from config import Settings
    s = Settings()
    assert s.key_encryption_secret == "abc"                    # ← DEMO_FALLBACK_ENABLED=true / DEMO_FALLBACK_MODEL=… override
```
> Use bare `Settings()` (not `get_settings()`) for the default test as `test_config.py` does — avoids the cache entirely.

**Stream-mock fixture (extend in `conftest.py` for D-04)** — `mock_stream_chat_completion` (conftest.py:75-126) today emits only `system_content`/`tool_call`/`text_delta`. Add an option to append a trailing `{"type":"usage","usage":{…}}` event so usage-capture/summing tests can drive it. Copy the `_set_events` / `_default_tool_call_event` controller shape (lines 82-117).

**LangSmith gate test** — `test_tracing.py` covers `setup_tracing`; the new gate test asserts on `get_llm_client(trace=False)` NOT applying `wrap_openai`. Monkeypatch/inspect `llm_service.wrap_openai` (a module global, line 6) and assert the returned client is the bare `OpenAI` instance when `trace=False`.

**Scrub regex test** — assert `scrub_secrets("…sk-or-v1-ABC123…")` redacts. The regex source-of-truth is `sentry.ts:31` (`/sk-or-v1-[A-Za-z0-9_-]+/g`), **broadened on the backend to `sk-or-[A-Za-z0-9_-]+`** per D-11.

---

## Shared Patterns

### Decryption (Phase 9, reused verbatim)
**Source:** `backend/services/crypto_service.py:40-42`
**Apply to:** `chat.py` resolution block only.
```python
def decrypt_key(ciphertext: str) -> str:
    """Decrypt a Fernet token, trying each configured master key in order; returns plaintext."""
    return _multifernet().decrypt(ciphertext.encode()).decode()
```
In-memory, per-request. Raises `RuntimeError` if `KEY_ENCRYPTION_SECRET` unset (crypto_service.py:29) — let it propagate to the chat error path (which scrubs).

### Service-role DB access (read keys / write usage)
**Source:** `backend/routers/keys.py:79-86`, `backend/database.py:get_supabase()`
**Apply to:** the `user_api_keys` read AND the `messages` usage write.
- Read: `get_supabase().table("user_api_keys").select("encrypted_key").eq("user_id", user_id).maybe_single().execute()` — service-role bypasses RLS; the empty-row guard (`if not row or not row.data`) IS the fail-closed fork.
- Write: mirror the existing `db.table("messages").update({...}).eq("id", assistant_msg_id).execute()` at `chat.py:879-882`.
- **Do NOT** undo Phase 9 SEC-02 lockdown (REVOKE + FROM-allowlist) — `user_api_keys` stays out of the Text-to-SQL tool.

### Secret scrub (mirror frontend Sentry)
**Source:** `frontend/src/lib/sentry.ts:31-33`
**Apply to:** every `str(e)` reaching an SSE-error payload OR a log line in `chat.py` (and any service that logs an OpenRouter error).
```typescript
const OR_KEY = /sk-or-v1-[A-Za-z0-9_-]+/g          // FE form
const scrub = (s) => typeof s === 'string' ? s.replace(OR_KEY, '[redacted-key]') : s
```
Backend Python equivalent (D-11, **broadened** to catch any `sk-or-` prefix):
```python
import re
_OR_KEY = re.compile(r"sk-or-[A-Za-z0-9_-]+")
def scrub_secrets(s: str) -> str:
    return _OR_KEY.sub("[redacted-key]", s) if isinstance(s, str) else s
```
Prefer fixed-copy structured errors (`no_api_key` / `rate_limit` / `payment_required`) over `str(e)` entirely on the known-error paths.

### LangSmith trace gate (D-10)
**Source:** `backend/services/llm_service.py:18-19` (the existing conditional wrap) + `backend/services/tracing.py` (wiring context)
**Apply to:** `get_llm_client()` only — gate keyed on `trace: bool` (= `not is_user_key`). User-key calls skip the wrapper; owner/demo calls keep it.
```python
if trace and wrap_openai and settings.langsmith_api_key:       # ← add `trace` to the existing two-condition guard
    client = wrap_openai(client)
```

### Counter-bounded sub-agent loop (context, not modified)
**Source:** `explorer_service.py:232` / `chat.py:616` (`while iteration < settings.*_max_iterations`)
**Relevance:** each loop iteration is an LLM call on the resolved key — amplifies request count per turn, which is why free-model 429 caps (Pitfall 11) matter. The loop STRUCTURE is unchanged; only the client/model inside it are threaded.

### Frontend in-band SSE error consumption (no FE plumbing needed)
**Source:** `frontend/src/hooks/useChat.ts:185-197`
**Relevance:** the `done` path keys only on `parsed.message_id` (line 185) and ignores extra keys → extend `done` with `usage`/`mode` for free (D-08). The error path throws on `parsed.error !== undefined` (line 192) → the structured `no_api_key`/`rate_limit`/`payment_required` codes reuse it with zero new event types.

---

## No Analog Found

*(none — every seam has an in-repo analog)*

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | This is a wiring phase; all five categories (decrypt, typed errors, usage object, per-request client, scrub regex) already exist in-repo or in the OpenAI SDK. |

**Two items are NEW code with only a *conceptual* analog (planner should note):**
- `_resolve_key_and_model()` helper — no single existing function does three-tier model + fail-closed key. Compose it from: the `keys.py:79` empty-row guard + `crypto_service.decrypt_key` + `settings.resolved_llm_api_key` property + `thread.data.get("model")` absent-key read. It must NOT be a `Settings` method and must NOT be cached (Pitfall 8).
- The drain-and-accumulate `usage` restructure in `stream_chat_completion` — the existing chunk loop is the skeleton, but removing the `tool_calls` early-return + summing across iterations is new control flow (Pattern 4 / A4 — accumulate defensively, treat `cost` as authoritative, tolerate missing token sub-fields).

## Metadata

**Analog search scope:** `backend/services/` (llm, rerank, subagent, explorer, crypto, budget, tracing), `backend/routers/` (chat, keys), `backend/config.py`, `backend/database.py`, `backend/tests/` (conftest, test_config, test_crypto_service), `supabase/migrations/` (002, 024, 028), `frontend/src/lib/sentry.ts`, `frontend/src/hooks/useChat.ts`
**Files scanned:** 18 read in full or targeted-section; ~24 test files enumerated for fixture conventions
**Pattern extraction date:** 2026-06-22
