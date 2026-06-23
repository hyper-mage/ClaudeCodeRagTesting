"""OpenRouter model-catalog read endpoint (Phase 12, MODEL-01 / MODEL-04 / MODEL-07).

GET /api/models[?free_only=true] — the ONE place the frontend reads the catalog from.
The frontend NEVER calls OpenRouter directly (Success Criterion #1); it reads this
backend route, which serves from the `model_cache` table and lazily refreshes it.

This router is a thin SEAM that composes the plan 12-01 pure functions — it does NOT
reimplement free/paid tagging, per-Mtok math, popularity, or the refresh logic:

  refresh_if_stale(db)      — serve-or-refresh the model_cache rows; never empty (D-05);
                              serve-stale-on-failure (D-04). Read-triggered, 24h TTL (D-03).
  build_model_response(row) — tag is_free + per-Mtok hints + null-safe context_length +
                              curated popularity, retaining raw pricing (D-10 / D-11).

Security:
- Auth-gated via Depends(get_user_id) (codebase norm, A4). The catalog is non-secret and
  per-user-agnostic, but every router in this app is auth-gated (T-12-V4-03 → accept).
- `free_only` is typed `bool` in the signature → FastAPI coerces/rejects non-bool input;
  no raw string flows into a query (T-12-V5-03). The filter runs SERVER-SIDE (D-02) so the
  client never recomputes is_free.
- Reads via the service-role get_supabase() client; model_cache RLS is global-read +
  service-role-write (migration 030), so server-side writes during refresh are allowed.
"""
from fastapi import APIRouter, Depends

from auth import get_user_id
from database import get_supabase
from models.schemas import ModelResponse
from services.model_catalog_service import build_model_response, refresh_if_stale

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=list[ModelResponse])
def list_models(
    free_only: bool = False,
    user_id: str = Depends(get_user_id),
) -> list[dict]:
    """Serve the full model catalog (or only the free models when ?free_only=true).

    Composes the plan-01 helpers over the model_cache rows:
      1. refresh_if_stale(db) — serve-or-refresh; never empty (D-05); serve stale on a
         fetch failure (D-04). An empty cache populates synchronously on this first read.
      2. build_model_response(row) per row — render-ready fields, raw pricing retained.
      3. If free_only, drop the non-free rows SERVER-SIDE (D-02) — the client never
         recomputes is_free.
    """
    db = get_supabase()
    rows = refresh_if_stale(db)
    models = [build_model_response(row) for row in rows]
    if free_only:
        models = [m for m in models if m["is_free"]]
    return models
