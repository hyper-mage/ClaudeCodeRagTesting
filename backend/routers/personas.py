"""Persona catalog read endpoint (Phase 17, PERS-01 / D-07).

GET /api/personas — the ONE place the frontend reads the persona catalog from, so the
persona picker never hardcodes the list (D-07). The catalog is a CODE constant
(services.persona_service.PERSONAS), not a DB table: there is NO refresh, NO cache, and
NO DB read here — this router is a thin SEAM over list_personas() (mirrors the
models.py ↔ model_catalog_service.py split, but simpler — the persona catalog never
goes stale).

Security:
- Auth-gated via Depends(get_user_id) (codebase norm — every router in this app is
  auth-gated, T-17-15 → mitigate). The catalog is non-secret and per-user-agnostic.
- The wire shape is [{id, label, is_default}] only. The persona voice_block (the prompt
  text) is NEVER shipped to the client (A5 / T-17-14): list_personas() withholds it and
  PersonaResponse structurally omits it, so prompt text stays server-side.
"""
from fastapi import APIRouter, Depends

from auth import get_user_id
from models.schemas import PersonaResponse
from services.persona_service import list_personas

router = APIRouter(prefix="/api/personas", tags=["personas"])


@router.get("", response_model=list[PersonaResponse])
def get_personas(user_id: str = Depends(get_user_id)) -> list[dict]:
    """Return the curated persona catalog as [{id, label, is_default}].

    The catalog is a code constant (no DB, no refresh) — serve it directly from
    list_personas(). The voice_block (prompt text) is NEVER included in the wire
    shape (A5): it stays server-side, composed into the LLM system message only.
    """
    return list_personas()
