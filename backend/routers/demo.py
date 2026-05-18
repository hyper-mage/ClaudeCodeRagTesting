"""POST /api/demo/bootstrap — anon-user seed + cleanup dispatcher (PORT-01).

One endpoint, one job: when an anon user signs in for the first time, seed
their private library with a sample doc + welcome thread, then opportunistically
purge any anon users older than the retention threshold.

Design notes:
- @limiter.limit("5/minute") — anti-abuse mitigation per T-08-02
  (RESEARCH Pitfall 5). The shared limiter key_func resolves to user_id,
  which for anon users still meaningfully caps per-account abuse.
- Permanent-user calls are a SILENT no-op (return {"seeded": False}) rather
  than 403 — minimum friction during prod debugging + matches RESEARCH
  §Anti-Patterns recommendation. The endpoint is also harmless for permanent
  users (no DB writes happen) so explicit refusal would add no security value.
- Cleanup runs via BackgroundTasks AFTER the response is sent so the frontend
  is never blocked by purge latency.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from auth import get_user_id
from database import get_supabase
from limiter import limiter
from services.demo_service import purge_stale_anon_users, seed_anon_user_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/bootstrap")
@limiter.limit("5/minute")  # T-08-02: anon-abuse mitigation (RESEARCH Pitfall 5)
async def bootstrap(
    request: Request,                        # REQUIRED by slowapi (RESEARCH Pitfall 1)
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id),
) -> dict:
    """Seed sample content for the calling anon user + schedule a purge sweep.

    Returns {"seeded": bool}:
    - True  — anon user, freshly seeded.
    - False — either a permanent user (no-op) or an anon user who is already
              seeded (idempotency hit inside seed_anon_user_content).
    """
    db = get_supabase()

    # Permanent-user guard — silent no-op (T-08-02-PERM).
    user_response = db.auth.admin.get_user_by_id(user_id)
    if not getattr(user_response.user, "is_anonymous", False):
        logger.info(f"bootstrap: permanent user {user_id} — no-op")
        return {"seeded": False}

    # Synchronous seed (must complete before frontend navigates to /).
    seeded = seed_anon_user_content(user_id)

    # Background sweep — never blocks the response.
    background_tasks.add_task(purge_stale_anon_users, retention_days=7)

    return {"seeded": seeded}
