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
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

from auth import get_user_id
from config import get_settings
from database import get_supabase
from models.schemas import BalanceResponse, ExchangeRequest, KeyStatusResponse
from services.crypto_service import decrypt_key, encrypt_key
from services.log_scrub import scrub_secrets
from services.openrouter_service import exchange_code

logger = logging.getLogger(__name__)

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


@router.get("/balance", response_model=BalanceResponse)
async def balance(user_id: str = Depends(get_user_id)) -> BalanceResponse:
    """Server-side OpenRouter balance proxy (COST-02 / COST-03, T-14-01..04).

    Reads the stored key (service-role client, bound to the JWT sub), decrypts it
    IN MEMORY for this request only, and proxies OpenRouter GET /api/v1/key. Returns
    ONLY {connected, limit_remaining, is_low} — never the sk-or-… key, never the raw
    provider body (T-14-01/03). is_low is computed server-side from the configurable
    threshold (T-14-04); a null limit_remaining (pay-as-you-go) is never low (D-04).
    A provider error surfaces a fixed generic 502 with a scrubbed log line and NO
    exc_info (which could capture the outbound Bearer header — T-14-02).
    """
    row = (
        get_supabase()
        .table("user_api_keys")
        .select("encrypted_key")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not row or not isinstance(row.data, dict) or not row.data.get("encrypted_key"):
        # No connected key → report disconnected; make NO outbound OpenRouter call.
        return BalanceResponse(connected=False)

    # Decrypt in-memory for this request only — never stored, returned, or logged.
    key = decrypt_key(row.data["encrypted_key"])
    try:
        resp = httpx.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        # NO exc_info — the traceback could capture the Bearer header (T-14-02).
        logger.warning(f"balance fetch failed: {scrub_secrets(str(e))}")
        raise HTTPException(
            status_code=502,
            detail="Couldn't fetch the OpenRouter balance.",
        )

    data = resp.json().get("data", {})
    remaining = data.get("limit_remaining")
    threshold = get_settings().low_balance_threshold_usd
    is_low = remaining is not None and remaining < threshold
    # Return ONLY the derived non-secret fields — never resp.json()/resp.text/data.label.
    return BalanceResponse(connected=True, limit_remaining=remaining, is_low=is_low)


@router.delete("", status_code=204)
async def disconnect(user_id: str = Depends(get_user_id)) -> None:
    """Disconnect — delete the calling user's key row (KEY-04)."""
    get_supabase().table("user_api_keys").delete().eq("user_id", user_id).execute()
