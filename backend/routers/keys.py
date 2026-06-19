"""OpenRouter BYOK key endpoints (Phase 10, KEY-01 / KEY-03 / KEY-04).

Three handlers under /api/keys, all bound to the calling user via
Depends(get_user_id) (the JWT sub — Pitfall 2: the key is bound to auth.uid()
server-side, never to a value from the request body or the OpenRouter response):

  POST /openrouter/exchange  — exchange the OAuth code for a key, encrypt it,
                               upsert into user_api_keys; return {connected:True}.
  GET  /status               — masked-only connection state (no key, no ciphertext).
  DELETE ""                  — disconnect (delete the row); 204.

SECURITY (T-10-03 / T-10-04 / SEC-01):
- The exchanged sk-or-v1-… key is NEVER returned to the client — not plaintext,
  not ciphertext. Exchange returns {connected:True}; /status returns booleans +
  the masked tail + connected_at only; encrypted_key is never selected.
- A non-2xx from OpenRouter (httpx.HTTPStatusError) is caught and re-raised as a
  GENERIC HTTPException(502, <fixed string>). The OpenRouter response body holds
  the key, so we never echo resp.text / the exception into the detail and never
  add exc_info=True on the response.
- user_api_keys is reached ONLY via the service-role get_supabase() client (the
  Phase 9 SEC-02 lockdown REVOKEs SELECT from authenticated and keeps the table
  out of the Text-to-SQL allowlist — untouched here).
"""
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

from auth import get_user_id
from database import get_supabase
from models.schemas import ExchangeRequest, KeyStatusResponse
from services.crypto_service import encrypt_key
from services.openrouter_service import exchange_code

router = APIRouter(prefix="/api/keys", tags=["keys"])


@router.post("/openrouter/exchange")
async def exchange(body: ExchangeRequest, user_id: str = Depends(get_user_id)) -> dict:
    """Exchange the OAuth code for an OpenRouter key, encrypt + upsert it.

    The key lands server-side, is encrypted via the Phase 9 crypto_service, and
    is upserted (PK=user_id → one key per user; reconnect overwrites). NEVER
    returns the key. A 403/error from OpenRouter surfaces a generic 502.
    """
    try:
        key = exchange_code(body.code, body.code_verifier)
    except httpx.HTTPStatusError:
        # Pitfall 1 / SEC-01 / T-10-04: the OpenRouter response body can contain
        # the key — surface a FIXED, generic detail; never resp.text, never the
        # exception, never exc_info on the response.
        raise HTTPException(
            status_code=502,
            detail="Couldn't complete the OpenRouter connection.",
        )

    # Non-secret masked tail for the "Connected" display (in memory only).
    masked = "sk-or-v1-…" + key[-4:]

    get_supabase().table("user_api_keys").upsert(
        {
            "user_id": user_id,
            "provider": "openrouter",
            "encrypted_key": encrypt_key(key),
            "key_label": masked,
            "key_version": 1,
            # Set EXPLICITLY (Pitfall 4): ON CONFLICT DO UPDATE skips column
            # defaults, so reconnect re-stamps "connected since" only if we send it.
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()

    return {"connected": True}  # NEVER the key


@router.get("/status", response_model=KeyStatusResponse)
async def status(user_id: str = Depends(get_user_id)):
    """Masked-only connection state (KEY-03). Never selects/returns encrypted_key."""
    row = (
        get_supabase()
        .table("user_api_keys")
        .select("key_label, connected_at")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not row or not row.data:
        return {"connected": False}
    return {
        "connected": True,
        "masked_label": row.data["key_label"],
        "connected_at": row.data["connected_at"],
    }


@router.delete("", status_code=204)
async def disconnect(user_id: str = Depends(get_user_id)) -> None:
    """Disconnect — delete the calling user's key row (KEY-04)."""
    get_supabase().table("user_api_keys").delete().eq("user_id", user_id).execute()
