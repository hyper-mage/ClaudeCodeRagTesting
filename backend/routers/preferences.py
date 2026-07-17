"""User preferences endpoints (Phase 13, MODEL-05 / PREF-02).

Two handlers under /api/preferences, both bound to the calling user via
Depends(get_user_id) (the JWT sub — never a value from the request body):

  GET ""  — the user's resolved default_model + theme + favorite_models; a
            brand-new user with no row resolves to
            {"default_model": null, "theme": "dark", "favorite_models": []}.
  PUT ""  — a PARTIAL upsert (RESEARCH Pattern 2): only the fields the client
            actually sent are written, keyed on user_id (PK). A theme-only PUT
            must NOT clobber default_model or favorite_models and vice-versa
            (favorite_models is a whole-array replace when sent — Phase 15
            MODEL-08 / D-05).

SECURITY (T-13-02 / T-13-08):
- user_id is ALWAYS bound from Depends(get_user_id) (the JWT sub) and written
  into the upsert payload server-side; a user_id supplied in the body is never
  read (cross-user write mitigation).
- theme is validated by the Pydantic Literal on PreferencesUpdate, so an invalid
  value (e.g. "purple") is rejected with 422 before any DB call.

user_preferences is reached via the service-role get_supabase() client; own-row
RLS (migration 000032) is the isolation. This is the temporary write surface the
Phase 14 settings work builds on — kept minimal (no DELETE, no REVOKE here).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from auth import get_user_id
from database import get_supabase
from models.schemas import PreferencesResponse, PreferencesUpdate

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesResponse)
def get_preferences(user_id: str = Depends(get_user_id)):
    """Return the calling user's default_model + theme.

    A brand-new user with no row resolves to the safe defaults
    {"default_model": None, "theme": "dark"} via the maybe_single guard (never a
    406). theme falls back to "dark" if the stored value is somehow null.
    """
    row = (
        get_supabase()
        .table("user_preferences")
        .select("default_model, theme, favorite_models, default_persona")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not row or not row.data:
        return {
            "default_model": None,
            "theme": "dark",
            "favorite_models": [],
            "default_persona": None,
        }
    return {
        "default_model": row.data.get("default_model"),
        "theme": row.data.get("theme") or "dark",
        # Phase 15 MODEL-08: null-tolerant fallback mirrors the theme guard.
        "favorite_models": row.data.get("favorite_models") or [],
        # Phase 17 PERS-04: null when unset (resolver falls back to the system default).
        "default_persona": row.data.get("default_persona"),
    }


@router.put("", response_model=PreferencesResponse)
def update_preferences(
    body: PreferencesUpdate, user_id: str = Depends(get_user_id)
):
    """Partial-upsert the user's preferences (RESEARCH Pattern 2).

    Only the fields the client actually sent are written (model_dump with
    exclude_unset), so a theme-only PUT does not null default_model and a
    default_model-only PUT does not change theme. user_id is bound from the JWT
    (NEVER the body — T-13-02) and updated_at is set explicitly because
    ON CONFLICT DO UPDATE skips column defaults.
    """
    patch = body.model_dump(exclude_unset=True)
    patch["user_id"] = user_id
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()

    db = get_supabase()
    db.table("user_preferences").upsert(patch, on_conflict="user_id").execute()

    row = (
        db.table("user_preferences")
        .select("default_model, theme, favorite_models, default_persona")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not row or not row.data:
        return {
            "default_model": None,
            "theme": "dark",
            "favorite_models": [],
            "default_persona": None,
        }
    return {
        "default_model": row.data.get("default_model"),
        "theme": row.data.get("theme") or "dark",
        # Phase 15 MODEL-08: null-tolerant fallback mirrors the theme guard.
        "favorite_models": row.data.get("favorite_models") or [],
        # Phase 17 PERS-04: null when unset (resolver falls back to the system default).
        "default_persona": row.data.get("default_persona"),
    }
