# Phase 8: Portfolio Polish — Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 22 new/modified files
**Analogs found:** 19 / 22 (3 with no analog — new asset types)

> Consumed by `gsd-planner`. Per-file "copy this from here" map for Phase 8. Lock decisions from CONTEXT.md D-01..D-15 + UI-SPEC + RESEARCH already constrain WHAT each file does; this doc constrains HOW each file is shaped — by reference to existing analogs.

---

## File Classification

| New/Modified File | New/Mod | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|---------|------|-----------|----------------|---------------|
| `frontend/src/components/ErrorMessageBubble.tsx` | NEW | component (chat) | render-only | `frontend/src/components/MessageBubble.tsx` | exact (role + flow) |
| `frontend/src/components/DemoPill.tsx` | NEW (recommended) | component (presentation) | render-only | `frontend/src/components/IconSidebar.tsx` (active-pill style) | role-match |
| `frontend/src/pages/LoginPage.tsx` | MOD | page | form submit + auth call | self (existing `handleSubmit`) | exact (same file) |
| `frontend/src/hooks/useChat.ts` | MOD | hook | SSE stream + state mutation | self (existing catch L188–199) | exact (same file) |
| `frontend/src/components/MessageBubble.tsx` | MOD (optional — only if planner picks "extend" path) | component | render-only | self | exact (same file) |
| `frontend/src/components/ChatContainer.tsx` | MOD | container component | render + callback wiring | self | exact (same file) |
| `frontend/src/components/IconSidebar.tsx` | MOD | nav component | render + conditional | self (line 29–36 LogOut block) | exact (same file) |
| `frontend/src/components/MobileTopBar.tsx` | MOD | nav component | render + conditional | self (line 32 right spacer) | exact (same file) |
| `frontend/src/contexts/AuthContext.tsx` | MOD | context provider | derive + expose flag | self | exact (same file) |
| `frontend/src/contexts/ToastContext.tsx` | NO CHANGE (verified exists, already supports `'error'` variant) | context provider | render + auto-dismiss | n/a — reuse | n/a |
| `backend/routers/demo.py` | NEW | router | request-response + background-task | `backend/routers/threads.py` (router skeleton) + `backend/routers/chat.py` (slowapi decorator + Request param) | role-match (combine both) |
| `backend/services/demo_service.py` | NEW (recommended split) | service | DB CRUD + storage delete + admin auth | `backend/scripts/seed_default_kb.py` (seed pipeline) + `backend/routers/documents.py:132–155` (storage + DB cascade delete) | role-match |
| `backend/scripts/seed_anon_user.py` | OPTIONAL (only if planner extracts; else logic lives in `demo_service.py`) | script | one-off seeder | `backend/scripts/seed_default_kb.py` | exact (role + flow) |
| `backend/main.py` | MOD | app entry | router registration | self (lines 64–67) | exact (same file) |
| `backend/routers/chat.py` | MOD | router (SSE) | request-response + SSE + DB insert | self (lines 467–571) | exact (same file) |
| `backend/auth.py` | MOD (probable — `aud` claim widened) | middleware (JWT verify) | request-response | self (line 42 `audience="authenticated"`) | exact (same file) |
| `backend/tests/test_auth_anon.py` | NEW | test | unit + integration | `backend/tests/test_rate_limit.py` (FastAPI stand-in app pattern) | role-match |
| `backend/tests/test_demo_bootstrap.py` | NEW | test | integration (mocked db) | `backend/tests/test_health.py` (mocked supabase chain) + `backend/tests/test_seed_default_kb.py` (constants assertions) | role-match |
| `backend/tests/test_anon_cleanup.py` | NEW | test | unit (mocked db) | `backend/tests/test_health.py` (`_build_mock_db_chain`) | role-match |
| `backend/tests/test_chat_retry.py` | NEW | test | integration (mocked db + stream) | `backend/tests/test_chat_cap.py` (TestClient + mock_stream_chat_completion) | role-match |
| `data/sample-private-docs/dnd5e-quickref.md` | NEW | asset (markdown) | static | `data/default-kb/*.md` (existing seed corpus) | exact (asset type) |
| `docs/MASTERCLASS.md` | NEW (moved from current `README.md`) | doc | static | self (current `README.md`) | n/a — move op |
| `docs/CREDITS.md` | NEW | doc | static | no analog (new convention) | NO ANALOG |
| `docs/architecture.excalidraw` + `docs/architecture.png` | NEW | asset (diagram) | static | no analog | NO ANALOG |
| `docs/screenshots/*.png` + `docs/hero.gif` | NEW | asset (image) | static | no analog | NO ANALOG |
| `README.md` | MOD (full rewrite) | doc | static | self (current — but rewritten) | n/a — rewrite |

---

## Pattern Assignments

### `frontend/src/components/ErrorMessageBubble.tsx` (NEW · component · render-only)

**Analog:** `frontend/src/components/MessageBubble.tsx` (lines 1–82). UI-SPEC Surface 2 mandates a structurally different element (icon + body + button) — recommended sibling component, not a third branch of `MessageBubble`.

**Imports pattern** (mirror `MessageBubble.tsx:1–4`):
```typescript
import { AlertCircle, RotateCw } from 'lucide-react'
// NO ReactMarkdown — error copy is locked plain text (UI-SPEC Copywriting)
// NO ToolCallCard — error bubbles never carry tool events
```

**Container shape** (copy + mutate from `MessageBubble.tsx:17–24`):
```typescript
// MessageBubble.tsx:17-24 — copy the left-aligned outer flex wrapper
<div className="flex justify-start mb-4">
  <div
    role="alert"  // NEW — accessibility per UI-SPEC § Accessibility
    className="max-w-[85%] md:max-w-[70%] px-4 py-3 rounded-lg bg-red-950/40 border border-red-700 text-gray-100"
  >
    {/* icon + body + retry */}
  </div>
</div>
```

Width override `max-w-[85%] md:max-w-[70%]` is UI-SPEC-locked (mobile expansion). Plain `max-w-[70%]` in `MessageBubble.tsx:19` is desktop-only.

**Retry button pattern** (mirror the existing `bg-blue-600` accent — see `LoginPage.tsx:69` for the same hover/disabled tokens):
```typescript
// LoginPage.tsx:67-72 — same accent + disabled treatment
<button
  type="button"
  onClick={onRetry}
  disabled={isStreaming}  // UI-SPEC Surface 2 — Retry disabled while streaming
  className="inline-flex items-center gap-1 px-3 py-2.5 md:py-1.5 rounded text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
>
  <RotateCw size={14} />
  Retry
</button>
```

**Props interface** (mirror `MessageBubble.tsx:6–10` shape):
```typescript
interface Props {
  onRetry: () => void
  isStreaming: boolean
}
```

---

### `frontend/src/components/DemoPill.tsx` (NEW recommended · component · render-only)

**Analog:** there is no existing pill component — the closest visual analog is the active-nav-button pattern in `IconSidebar.tsx:17` (`bg-gray-800 text-white` rounded). Build the pill as a tiny presentational component to dedupe across three render locations (IconSidebar desktop, MobileTopBar, IconNavRow drawer).

**Imports + shape:**
```typescript
import { useAuth } from '../contexts/AuthContext'

export default function DemoPill() {
  const { isAnon } = useAuth()  // NEW field — see AuthContext.tsx mod below
  if (!isAnon) return null
  return (
    <span
      role="status"
      aria-label="Demo account"
      title="You're using a temporary demo account. Data is cleared after 7 days."
      className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30"
    >
      Demo
    </span>
  )
}
```

Color tokens (`amber-500/15`, `amber-300`, `amber-500/30`) are UI-SPEC § Color-locked — do not improvise.

---

### `frontend/src/pages/LoginPage.tsx` (MOD · page · auth flow)

**Analog:** self — `handleSubmit` at lines 20–39 is the exact pattern to copy for `handleTryDemo`. The page already has `loading`/`error` state hooks (lines 10–11) that the new CTA reuses.

**Imports — add:** `apiFetch` and nothing else.
```typescript
// LoginPage.tsx:1-4 — existing
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { useAuth } from '../contexts/AuthContext'
// ADD:
import { apiFetch } from '../lib/api'
```

**`handleTryDemo` (mirror `handleSubmit` shape at L20–39):**
```typescript
// Pattern source: LoginPage.tsx:20-39 (handleSubmit)
const handleTryDemo = async () => {
  setError('')
  setLoading(true)
  try {
    const { data, error } = await supabase.auth.signInAnonymously()
    if (error) throw error
    if (!data.session) throw new Error('No session returned')
    await apiFetch('/api/demo/bootstrap', { method: 'POST' })
    navigate('/', { replace: true })
  } catch {
    // UI-SPEC Copywriting Contract — locked copy, no provider name, no HTTP code
    setError("Couldn't start the demo. Please try again.")
  } finally {
    setLoading(false)
  }
}
```

**CTA placement** (insert BEFORE the existing `<form>` at L47; copy the existing button styling at L66–72 exactly except for the `py-3` bump UI-SPEC § Spacing mandates):
```typescript
// Mirror L66-72 button class but py-3 (≥44px touch) + use locked copy
<button
  type="button"
  onClick={handleTryDemo}
  disabled={loading}
  className="w-full py-3 bg-blue-600 hover:bg-blue-700 rounded font-semibold disabled:opacity-50"
>
  {loading ? 'Setting up your demo…' : 'Try the demo'}
</button>
<p className="text-xs text-gray-500 mt-2 text-center">
  No signup. Your demo session expires after 7 days.
</p>
<div className="my-6 border-t border-gray-800 relative">
  <span className="absolute -top-2 left-1/2 -translate-x-1/2 bg-gray-950 px-2 text-xs text-gray-500">
    or sign in with email
  </span>
</div>
```

**Error rendering:** already covered — existing `{error && <p className="text-red-400 text-sm">{error}</p>}` at L65 displays both paths' errors.

---

### `frontend/src/hooks/useChat.ts` (MOD · hook · SSE catch-block extension)

**Analog:** self — the catch block at lines 188–199 is the single dispatch point for chat-error UI. RESEARCH Pitfall 3 + UI-SPEC Surface 2 lock the new behavior.

**Imports — add:**
```typescript
// useChat.ts:1-2 — existing
import { useState, useCallback, useRef } from 'react'
import { apiFetch, apiStream } from '../lib/api'
// ADD:
import * as Sentry from '@sentry/react'   // Pattern 5 in RESEARCH — caught errors need explicit captureException
import { useToast } from '../contexts/ToastContext'
```

**`Message` type — add `'error'` role:**
```typescript
// useChat.ts:23-28 — extend role union
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'error'   // ADD 'error'
  content: string
  toolsUsed?: ToolEvent[]
}
```

**Catch-block rewrite** (replace `useChat.ts:188–199`):
```typescript
// useChat.ts:188-199 — existing catch swallows with console.error
} catch (err) {
  if (err instanceof DOMException && err.name === 'AbortError') {
    return
  }
  console.error('Chat error:', err)
  Sentry.captureException(err)  // RESEARCH §Standard Stack — caught errs need explicit capture

  // Replace the empty assistant placeholder with an error bubble (UI-SPEC Surface 2)
  setMessages(prev => prev.map(m =>
    m.id === assistantId
      ? { ...m, role: 'error' as const, content: "The assistant ran into a problem. Try again, or rephrase your question." }
      : m
  ))

  // Locked toast copy per UI-SPEC Copywriting Contract
  showToast("The assistant didn't respond. Tap the message to retry.", 'error')
}
```

**New `retryLastUserMessage` callback** (add alongside `sendMessage`/`cancel` at L201):
```typescript
const retryLastUserMessage = useCallback(() => {
  // UI-SPEC Surface 2 § Retry behavior (D-07)
  if (isStreaming) return
  const lastUser = [...messages].reverse().find(m => m.role === 'user')
  if (!lastUser) return
  setMessages(prev => prev.filter(m => m.role !== 'error'))
  void sendMessage(lastUser.content)
}, [messages, isStreaming, sendMessage])
```

**Hook-return signature update** (mirror `useChat.ts:207`):
```typescript
return { messages, setMessages, isStreaming, sendMessage, loadMessages, cancel, retryLastUserMessage }
```

**Backend retry coordination:** the new `sendMessage` call must hit `/api/threads/{id}/messages?retry=true` (or POST body flag) so `chat.py` can delete the pre-failure assistant row (see `backend/routers/chat.py` MOD below — RESEARCH §Pitfall 3 duplicate-row hazard).

---

### `frontend/src/components/ChatContainer.tsx` (MOD · container · onRetry plumbing)

**Analog:** self. Two minimal changes:

1. **Anon-user empty-state copy** (replace `ChatContainer.tsx:32`):
   ```typescript
   // Existing: <p>Send a message to start the conversation.</p>
   // UI-SPEC locks anon-specific copy; non-anon stays unchanged.
   <p>
     {isAnon
       ? "Ask me about the board games in the library, or about the sample D&D 5e quick-reference that's already attached."
       : "Send a message to start the conversation."}
   </p>
   ```
   `isAnon` arrives via `useAuth()` (new field).

2. **Render `ErrorMessageBubble` for `role === 'error'` messages** (replace `ChatContainer.tsx:35–37` map):
   ```typescript
   {messages.map(msg => (
     msg.role === 'error'
       ? <ErrorMessageBubble key={msg.id} onRetry={onRetry} isStreaming={isStreaming} />
       : <MessageBubble key={msg.id} role={msg.role} content={msg.content} toolsUsed={msg.toolsUsed} />
   ))}
   ```

3. **Add `onRetry` prop** to the `Props` interface (mirror `ChatContainer.tsx:20–24` shape):
   ```typescript
   interface Props {
     messages: Message[]
     onSend: (content: string) => void
     isStreaming: boolean
     onRetry: () => void   // ADD
   }
   ```

---

### `frontend/src/components/IconSidebar.tsx` (MOD · two render locations)

**Analog:** self — insert `<DemoPill />` immediately above the LogOut button block at both `IconSidebar.tsx:29-36` (desktop) and `IconNavRow` at L85-93 (mobile drawer row).

```typescript
// IconSidebar.tsx:29-36 — desktop
<div className="flex-1" />
<DemoPill />          {/* ADD — renders null if !isAnon */}
<button onClick={signOut} ...>...</button>

// IconSidebar.tsx:85-93 — drawer IconNavRow (mirror)
<div className="flex-1" />
<DemoPill />          {/* ADD */}
<button onClick={handleSignOut} ...>...</button>
```

No other change.

---

### `frontend/src/components/MobileTopBar.tsx` (MOD · right-slot swap)

**Analog:** self — replace the dead spacer at `MobileTopBar.tsx:32`:

```typescript
// MobileTopBar.tsx:32 — existing: <div className="h-11 w-11" />
// Replace with DemoPill wrapped in same-sized container so layout stays balanced:
<div className="h-11 w-11 flex items-center justify-center">
  <DemoPill />
</div>
```

When `!isAnon`, `DemoPill` returns `null` — the wrapper still occupies the slot, preserving title centering.

---

### `frontend/src/contexts/AuthContext.tsx` (MOD · expose `isAnon`)

**Analog:** self.

**`AuthContextType` extension** (mirror `AuthContext.tsx:5–10`):
```typescript
interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  signOut: () => Promise<void>
  isAnon: boolean   // ADD — derived from user.is_anonymous
}
```

**Provider value update** (mirror `AuthContext.tsx:38–42`):
```typescript
const isAnon = user?.is_anonymous ?? false
return (
  <AuthContext.Provider value={{ user, session, loading, signOut, isAnon }}>
    {children}
  </AuthContext.Provider>
)
```

Supabase `User` type already has `is_anonymous: boolean` since `@supabase/supabase-js v2.43.x` (RESEARCH §Standard Stack — VERIFIED).

---

### `backend/routers/demo.py` (NEW · router · POST /api/demo/bootstrap)

**Analog:** `backend/routers/threads.py:1–7` for the router skeleton; `backend/routers/chat.py:467–475` for the `@limiter.limit(...)` + `request: Request` parameter pattern.

**Imports + router skeleton** (mirror `threads.py:1–6`):
```python
# Source: threads.py:1-6 (router skeleton) + chat.py:1-7 (limiter import)
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from auth import get_user_id
from database import get_supabase
from limiter import limiter
from services.demo_service import seed_anon_user_content, purge_stale_anon_users

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/demo", tags=["demo"])
```

**POST endpoint** (mirror `chat.py:467–475` for limiter+Request, `threads.py:23–30` for the simple insert-and-return shape):
```python
# Source: chat.py:467-475 (slowapi decorator + Request param) + threads.py:23-30 (POST shape)
@router.post("/bootstrap")
@limiter.limit("5/minute")   # Anon-abuse mitigation; per-IP keying acceptable (RESEARCH §Standard Stack)
async def bootstrap(
    request: Request,                       # REQUIRED by slowapi (RESEARCH Pitfall 1)
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id),
):
    """Seed sample content for the calling anon user + opportunistically purge >7d anon users."""
    seeded = seed_anon_user_content(user_id)
    background_tasks.add_task(purge_stale_anon_users, retention_days=7)
    return {"seeded": seeded}
```

**Error handling:** does not require explicit `try/except` — failures bubble up as 500s (FastAPI default). RESEARCH Pitfall 6 covers cascade-delete safety inside the service.

---

### `backend/services/demo_service.py` (NEW · service · seed + purge)

**Analog (seed):** `backend/scripts/seed_default_kb.py:91–134` for the upload → insert documents row → `process_document(doc_id, user_id)` pipeline. Same pattern, `user_id` is the anon's UUID instead of `SYSTEM_USER_ID`, `visibility='private'`.

**Analog (purge):** `backend/routers/documents.py:132–155` for the storage-remove + DB-delete cascade, but iterated across multiple users via `auth.admin.list_users()`.

**Imports** (mirror `seed_default_kb.py:1–20`):
```python
# Source: seed_default_kb.py:1-20
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from database import get_supabase
from services.record_manager import hash_content, check_duplicate
from services.ingestion_service import process_document

logger = logging.getLogger(__name__)
SAMPLE_DOC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample-private-docs", "dnd5e-quickref.md"
)
```

**Seed function shape** (copy & adapt `seed_default_kb.py:91–134`):
```python
# Source: seed_default_kb.py:91-134 — drop SYSTEM_USER_ID + BOARD_GAMES_FOLDER_ID; use anon's user_id
def seed_anon_user_content(user_id: str) -> bool:
    db = get_supabase()
    # Idempotency: skip if user already has any document
    existing = db.table("documents").select("id").eq("user_id", user_id).limit(1).execute()
    if existing.data:
        return False

    with open(SAMPLE_DOC_PATH, "rb") as f:
        file_bytes = f.read()

    content_hash = hash_content(file_bytes)
    if check_duplicate(user_id, content_hash):
        return False

    doc_id = str(uuid.uuid4())
    filename = "dnd5e-quickref.md"
    storage_path = f"{user_id}/{doc_id}/{filename}"
    db.storage.from_("documents").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "text/markdown"},
    )
    db.table("documents").insert({
        "id": doc_id,
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path,
        "file_size": len(file_bytes),
        "mime_type": "text/markdown",
        "status": "pending",
        "content_hash": content_hash,
        "folder_id": None,
        "visibility": "private",       # Per-user anon doc; NOT public like the default KB
    }).execute()
    process_document(doc_id, user_id)

    # Optional: seed sample thread(s) per CONTEXT D-02 — simplest impl = direct messages.insert
    # See chat.py:491-496 for the messages-row shape.
    return True
```

**Purge function shape** (mirror `documents.py:132–155` cascade pattern + iterate via gotrue admin API):
```python
# Source: documents.py:147-155 (storage remove + delete) wrapped in a loop over admin.list_users()
def purge_stale_anon_users(retention_days: int = 7) -> int:
    db = get_supabase()
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = 0
    page = 1
    while True:
        users = db.auth.admin.list_users(page=page, per_page=100)
        if not users:
            break
        for u in users:
            if u.is_anonymous and u.created_at < cutoff:
                try:
                    _cascade_delete_user_data(db, u.id)
                    db.auth.admin.delete_user(u.id)
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to purge anon user {u.id}: {e}")
        if len(users) < 100:
            break
        page += 1
    return deleted

def _cascade_delete_user_data(db, user_id: str) -> None:
    # Mirror documents.py:148-152 (storage remove with try/except), then ordered DB deletes
    try:
        objs = db.storage.from_("documents").list(f"{user_id}/")
        if objs:
            paths = [f"{user_id}/{o['name']}" for o in objs]
            db.storage.from_("documents").remove(paths)
    except Exception as e:
        logger.warning(f"storage remove failed for {user_id}: {e}")
    # Child-first FK order (RESEARCH Pitfall 6)
    db.table("document_chunks").delete().eq("user_id", user_id).execute()
    db.table("documents").delete().eq("user_id", user_id).execute()
    db.table("folders").delete().eq("user_id", user_id).execute()
    db.table("messages").delete().eq("user_id", user_id).execute()
    db.table("threads").delete().eq("user_id", user_id).execute()
```

---

### `backend/main.py` (MOD · register demo router)

**Analog:** self — add one import + one `include_router` line.

```python
# main.py:9 — add 'demo' to the routers import
from routers import threads, chat, documents, folders, demo
# main.py:67 — add include below the others
app.include_router(demo.router)
```

That's the entire change. No other refactor.

---

### `backend/routers/chat.py` (MOD · retry-aware: delete prior failed assistant row)

**Analog:** self — the existing assistant-row insert at `chat.py:563–571` is where the duplicate-on-retry hazard originates (RESEARCH Pitfall 3). On retry, the frontend re-POSTs to `/api/threads/{id}/messages?retry=true`; the handler must delete the most-recent assistant row for this thread (which is the failed/empty one) before inserting the new placeholder.

**Pattern — add a query-param + a guarded delete BEFORE the existing insert at L491:**
```python
# chat.py:467-475 — extend signature
async def send_message(
    request: Request,
    thread_id: str,
    body: MessageCreate,
    retry: bool = False,                # ADD — Query() automatically; bool conversion via FastAPI
    user_id: str = Depends(get_user_id),
):
    db = get_supabase()
    # ... existing thread-ownership check at L478-488 ...

    if retry:
        # Delete the prior failed assistant row (it has empty content + no tool_calls).
        # Pattern: mirror documents.py:155 simple delete shape, scoped by thread + role + emptiness.
        db.table("messages").delete().eq("thread_id", thread_id).eq("user_id", user_id).eq("role", "assistant").eq("content", "").execute()
        # NOTE: the prior user message (which triggered the failure) is preserved — the frontend
        # passes the SAME user content as `body.content`. Inserting it again would duplicate the
        # user turn. Skip the user-insert at chat.py:491-496 on retry by guarding it the same way.

    # Existing L491-496: user-message insert — guard with `if not retry`:
    if not retry:
        db.table("messages").insert({...}).execute()    # (existing shape, unchanged)

    # ... rest of handler unchanged ...
```

Validation test must assert exactly one assistant row exists in `messages` for the thread after retry (see `test_chat_retry.py` below).

---

### `backend/auth.py` (MOD probable · anon-JWT `aud` claim acceptance)

**Analog:** self.

**Pitfall:** `auth.py:42` hard-codes `audience="authenticated"`. RESEARCH §Summary flags this as the SINGLE most likely deploy-breaker for PORT-01. Empirical verification required: capture a real anon JWT from the prod Supabase project, decode it (e.g. jwt.io), and check the `aud` claim:
- If `aud == "authenticated"`: no change needed.
- If `aud == "anon"` or absent: widen to `audience=["authenticated", "anon"]`.

**Change (only if verification mandates):**
```python
# auth.py:38-44 — existing decode call
payload = jwt.decode(
    token,
    signing_key,
    algorithms=[alg],
    audience=["authenticated", "anon"],   # WIDENED — accept both permanent and anon JWTs
    leeway=30,
)
```

PyJWT accepts a list for `audience`; semantic: token's `aud` must match at least one entry.

---

### `backend/tests/test_auth_anon.py` (NEW · test)

**Analog:** `backend/tests/test_rate_limit.py:44–108` for the FastAPI stand-in app pattern with a stubbed `get_user_id` dep. Use this to validate that an anon-shaped JWT (mocked) passes `get_user_id` without raising 401.

**Imports** (mirror `test_rate_limit.py:1–7`):
```python
import pytest
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from unittest.mock import patch
```

**Test pattern** (mirror `test_rate_limit.py:209–239` stand-in-app TestClient usage):
```python
def test_anon_jwt_accepted_by_get_user_id():
    """Anon JWT (audience='authenticated' OR ['authenticated','anon']) passes auth.get_user_id."""
    # Patch jwt.decode to simulate an anon JWT payload
    fake_payload = {"sub": "anon-uuid-1234", "aud": "authenticated", "role": "authenticated"}
    with patch("auth.jwt.decode", return_value=fake_payload), \
         patch("auth.jwt.get_unverified_header", return_value={"alg": "HS256"}):
        from auth import get_user_id
        from fastapi import HTTPException
        # Build minimal request stub (mirror test_rate_limit.py mock_request_with_user)
        ...
        assert get_user_id(req, settings) == "anon-uuid-1234"
```

**RLS isolation stub:** assert anon `user_id` (a real UUID like `auth.uid()` would emit) flows through and is used as the filter for downstream `.eq("user_id", user_id)` queries — re-use `documents.py` test patterns.

---

### `backend/tests/test_demo_bootstrap.py` (NEW · test)

**Analog:** `backend/tests/test_health.py:12–82` for the `_build_mock_db_chain` + `patch("main.get_supabase", ...)` pattern. `backend/tests/test_seed_default_kb.py:42–62` for the file-exists + constants assertions.

**Test 1 — file exists** (mirror `test_seed_default_kb.py:46–50`):
```python
def test_sample_doc_file_exists():
    from services.demo_service import SAMPLE_DOC_PATH
    assert os.path.exists(SAMPLE_DOC_PATH), f"Missing sample doc: {SAMPLE_DOC_PATH}"
```

**Test 2 — bootstrap calls seed + schedules cleanup** (mirror `test_health.py:26–32` TestClient + patched supabase):
```python
def test_bootstrap_endpoint_calls_seed_and_schedules_purge():
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient
    from main import app
    from auth import get_user_id

    app.dependency_overrides[get_user_id] = lambda: "anon-uuid"
    with patch("routers.demo.seed_anon_user_content", return_value=True) as m_seed, \
         patch("routers.demo.purge_stale_anon_users") as m_purge:
        resp = TestClient(app).post("/api/demo/bootstrap")
    assert resp.status_code == 200
    assert resp.json() == {"seeded": True}
    m_seed.assert_called_once_with("anon-uuid")
    # purge runs in BackgroundTasks → asserted via task scheduling, not direct call here
    app.dependency_overrides.clear()
```

**Test 3 — idempotency on repeat call** (asserts `seed_anon_user_content` returns `False` second time): mock `db.table("documents").select(...).execute()` to return `data=[{"id": "x"}]` on the second call.

---

### `backend/tests/test_anon_cleanup.py` (NEW · test)

**Analog:** `backend/tests/test_health.py:12–24` for the mocked supabase chain pattern.

**Test pattern** (mirror `test_health.py:_build_mock_db_chain`):
```python
def test_purge_deletes_old_anon_users_only():
    from unittest.mock import MagicMock, patch
    from datetime import datetime, timezone, timedelta
    from services.demo_service import purge_stale_anon_users

    old_user = MagicMock(id="old-uuid", is_anonymous=True,
                         created_at=datetime.now(timezone.utc) - timedelta(days=8))
    new_user = MagicMock(id="new-uuid", is_anonymous=True,
                         created_at=datetime.now(timezone.utc) - timedelta(hours=1))
    permanent_user = MagicMock(id="perm-uuid", is_anonymous=False,
                               created_at=datetime.now(timezone.utc) - timedelta(days=30))

    mock_db = MagicMock()
    mock_db.auth.admin.list_users.side_effect = [
        [old_user, new_user, permanent_user],
        [],  # second page empty → loop exits
    ]
    with patch("services.demo_service.get_supabase", return_value=mock_db):
        deleted = purge_stale_anon_users(retention_days=7)
    assert deleted == 1
    mock_db.auth.admin.delete_user.assert_called_once_with("old-uuid")
```

**Test 2 — cascade order** (mirror `test_health.py:54–82` shape assertions): assert `db.table("document_chunks").delete()...` called BEFORE `db.table("documents").delete()...`, etc.

---

### `backend/tests/test_chat_retry.py` (NEW · test)

**Analog:** `backend/tests/test_chat_cap.py:32–90` for the full TestClient + `mock_stream_chat_completion` + monkeypatched `get_supabase` pattern.

**Test pattern** (mirror `test_chat_cap.py:32–90`):
```python
def test_retry_deletes_prior_failed_assistant_row(mock_stream_chat_completion, mock_user_id, monkeypatch):
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from unittest.mock import MagicMock
    from main import app

    fake_db = MagicMock()
    # Track the delete call:
    delete_chain = fake_db.table.return_value.delete.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value
    fake_thread = MagicMock(data={"id": "t1", "user_id": mock_user_id, "title": "x"})
    fake_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = fake_thread
    fake_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "asst-2"}])

    monkeypatch.setattr("routers.chat.get_supabase", lambda: fake_db)
    app.dependency_overrides[get_user_id] = lambda: mock_user_id

    client = TestClient(app)
    # POST with retry=true query param
    with client.stream("POST", "/api/threads/t1/messages?retry=true",
                       json={"content": "same user message"},
                       headers={"Authorization": "Bearer fake"}) as resp:
        assert resp.status_code == 200
        list(resp.iter_lines())  # drain

    # The delete-prior-assistant chain must have been called exactly once
    delete_chain.execute.assert_called_once()
    app.dependency_overrides.clear()
```

---

### `data/sample-private-docs/dnd5e-quickref.md` (NEW · asset)

**Analog:** `data/default-kb/*.md` (catan.md, ticket-to-ride.md, etc.) — same markdown format. Just authored content with CC-BY 4.0 attribution block at the top per CONTEXT D-02.

**Shape guidance:** ≤500 lines, ≤2 MB, sections covering Ability Checks / Saving Throws / Advantage & Disadvantage / Combat Actions / Conditions. License footer:
```markdown
---
*Adapted from the System Reference Document 5.1 ("SRD 5.1") by Wizards of the Coast LLC, available at https://dnd.wizards.com/resources/systems-reference-document. Used under the Creative Commons Attribution 4.0 International License (CC-BY-4.0).*
```

---

### `docs/MASTERCLASS.md` (NEW · doc · move from current README.md)

**Analog:** the existing `README.md` (full content). Operation is a move — preserve every word, then prepend a one-line "Originally the repo root README for the AI Automators Claude Code Masterclass course" header.

---

### `docs/CREDITS.md` (NEW · doc · NO ANALOG)

**No analog in repo.** Use RESEARCH §Code Examples shape (not available in this repo — first credits file). Required content per CONTEXT D-02 + UI-SPEC: license attribution for D&D 5e SRD content + any other third-party assets (icons via lucide-react MIT, etc.).

---

### `docs/architecture.{excalidraw,png}` (NEW · asset · NO ANALOG)

**No analog.** Excalidraw recommended (RESEARCH §Standard Stack). Commit BOTH the source `.excalidraw` JSON and the exported `.png` so reviewers see the asset in README and contributors can edit the source.

---

### `docs/screenshots/*.png` + `docs/hero.gif` (NEW · asset · NO ANALOG)

**No analog.** First image assets in `docs/`. Capture from production CF Pages URL per CONTEXT D-14: (a) login w/ Try-demo CTA, (b) chat with tool cards expanded, (c) documents page with upload in progress, (d) mobile drawer open. Hero GIF via ScreenToGif on Windows (RESEARCH §Standard Stack — VERIFIED).

---

### `README.md` (MOD · full rewrite · NO STRUCTURAL ANALOG)

**Analog:** the existing `README.md` provides ONLY the "Tech Stack" table shape (lines 24–32) which the new Table 1 (Code Stack) can mirror with two columns instead of two. Everything else (live demo, badges, hero, services table, architecture, screenshots, deploy sequence, link to MASTERCLASS) is new structure.

**Section order locked by CONTEXT D-11:**
1. Title + 1-line pitch
2. Live demo link + "Try demo (no signup)" callout
3. Badges row (UptimeRobot + last-commit shields.io)
4. Hero GIF (`![](docs/hero.gif)`)
5. What it does (≤6 lines)
6. **Tech tables** (TWO tables — D-13)
7. Architecture diagram (`![](docs/architecture.png)`)
8. Screenshots gallery
9. Deploy command sequence
10. Link to `docs/MASTERCLASS.md`

**Badge URL patterns** (RESEARCH §Pattern 9, §Pattern 10):
```markdown
![Uptime](https://img.shields.io/uptimerobot/ratio/m{MONITOR_ID}-{KEY})
![Last commit](https://img.shields.io/github/last-commit/{owner}/{repo})
```

**Existing tech-table shape to copy** (lines 24–32 — keep two-column structure, narrow content):
```markdown
| Tech | Role |
|------|------|
| React + TypeScript + Tailwind + Vite | Frontend SPA |
| Python + FastAPI | Backend API |
| Supabase (Postgres + pgvector) | Database + Auth + Storage + Realtime |
| Docling | Document parsing |
| OpenAI SDK | Raw LLM calls (no LangChain) |
```

**Second table (Services)** — new shape, per CONTEXT D-13 verbatim from developer ask: `Service | Link | What it does | How this project uses it`.

---

## Shared Patterns

### Authentication (frontend → backend)

**Source:** `frontend/src/lib/api.ts:5–16` (`buildHeaders` injects `Authorization: Bearer ${token}`)
**Apply to:** Any new frontend → backend call in Phase 8. The new `apiFetch('/api/demo/bootstrap', ...)` call inherits this automatically.
**No new pattern needed** — just use `apiFetch` / `apiStream`.

### Authentication (backend — JWT verification)

**Source:** `backend/auth.py:17–53` (`get_user_id` dependency)
**Apply to:** Every new backend route in Phase 8 — both `demo.py` and the retry path in `chat.py` use `Depends(get_user_id)`.
**Phase-8 caveat:** verify anon JWT acceptance (see `backend/auth.py` MOD above).

### Error Handling (backend service layer)

**Source:** `backend/routers/documents.py:148–152` for storage-remove `try/except` + log-and-continue
```python
try:
    db.storage.from_("documents").remove([doc.data["storage_path"]])
except Exception:
    pass  # Storage file may already be gone
```
**Apply to:** `services/demo_service.py` `_cascade_delete_user_data` — same shape; per-user failures must not abort the loop. Mirror also at `services/demo_service.py` purge loop (`logger.warning` per RESEARCH §Code Examples).

### Error Handling (FastAPI routes)

**Source:** `backend/routers/threads.py:33–55` (`HTTPException(status_code=404, detail=...)`)
**Apply to:** any 4xx/5xx the new `demo.py` needs to raise. Phase 8 expects minimal use — bootstrap is idempotent + best-effort.

### Rate Limiting (decorator + Request param)

**Source:** `backend/routers/chat.py:467–475`
```python
@router.post("/{thread_id}/messages")
@limiter.limit(get_settings().chat_rate_limit)
async def send_message(
    request: Request,                            # REQUIRED — slowapi reads .state
    ...
):
```
**Apply to:** `backend/routers/demo.py` `bootstrap` endpoint — same shape with `@limiter.limit("5/minute")` (per-IP since no `user_id` available pre-anon-signin; acceptable per RESEARCH §Standard Stack).

### Idempotency check pattern

**Source:** `backend/scripts/seed_default_kb.py:99–103` (content-hash check via `record_manager.check_duplicate`) and `backend/services/record_manager.py:15–28`
**Apply to:** `services/demo_service.py::seed_anon_user_content` — same `check_duplicate` call + early-return shape.

### Test mock-db chain pattern

**Source:** `backend/tests/test_health.py:12–24` (`_build_mock_db_chain`)
**Apply to:** all new Phase-8 tests — same `MagicMock` chain shape so test/code coupling stays consistent. For chat-route tests, also use `mock_stream_chat_completion` fixture from `conftest.py:75–127`.

### Test stand-in FastAPI app pattern

**Source:** `backend/tests/test_rate_limit.py:44–108` (`_build_minimal_limited_app`)
**Apply to:** `test_auth_anon.py` and `test_chat_retry.py` when isolating route behavior from heavy DB/LLM deps.

### Logging

**Source:** `backend/routers/documents.py:52, 57, 96, 294` and `backend/services/embedding_service.py` patterns
**Apply to:** `services/demo_service.py` — `logger.info` for successful purge/seed counts; `logger.warning` for per-user failures; `logger.error(..., exc_info=True)` for unexpected exceptions per CLAUDE.md conventions.

### React component file shape

**Source:** `frontend/src/components/MessageBubble.tsx` (default export, local `Props` interface, no semicolons, single quotes, 2-space indent)
**Apply to:** `ErrorMessageBubble.tsx` + `DemoPill.tsx`.

### React hook export pattern

**Source:** `frontend/src/hooks/useChat.ts` (named export, returns object with `useCallback`-wrapped functions)
**Apply to:** `useChat.ts` MOD — extend the returned object with `retryLastUserMessage` while preserving named-export shape.

### Toast usage pattern

**Source:** `frontend/src/contexts/ToastContext.tsx:42–49` (`showToast(message, variant)`) — already supports `'error'` variant with red ramp + `aria-live="polite"`.
**Apply to:** `useChat.ts` catch block — `showToast("...", 'error')`. No `ToastProvider` changes required (verified mounted at app root per UI-SPEC § Toast primitive).

---

## No Analog Found

Files with no close match in the codebase (planner should use RESEARCH.md patterns or create greenfield):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `docs/CREDITS.md` | doc | static | First credits file in repo — establishes new convention |
| `docs/architecture.{excalidraw,png}` | asset (diagram) | static | First diagram asset — Excalidraw workflow new to repo |
| `docs/screenshots/*.png` + `docs/hero.gif` | asset (image) | static | First image assets in `docs/` |

---

## Metadata

**Analog search scope:** `frontend/src/**`, `backend/routers/**`, `backend/services/**`, `backend/scripts/**`, `backend/tests/**`, `backend/*.py`, `data/default-kb/**`, repo-root docs.
**Files scanned:** ~50 source files + 4 test analogs + 1 seed script + 1 README.
**Pattern extraction date:** 2026-05-17.
**Key observation:** all Phase-8 patterns have ≥1 exact or role-match analog except the documentation/asset deliverables (CREDITS, diagram, screenshots, GIF). Frontend additions are minimal — almost every change extends an existing component/hook. Backend adds 1 router + 1 service + 1 sample doc + 4 tests, every one of which mirrors a Phase 1-7 analog cleanly. Two integration seams need careful planner attention: (a) `backend/auth.py` `aud` claim (anon JWT) — empirical verification mandatory; (b) `backend/routers/chat.py` retry deletion — must guard against duplicate user-row insertion (covered in pattern above).
