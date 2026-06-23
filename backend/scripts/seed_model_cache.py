"""Deploy-time seed for the OpenRouter `model_cache` catalog (Phase 12, MODEL-01 / D-05).

Idempotently fetches the live OpenRouter catalog and upserts it into `model_cache`
keyed on `model_id` (re-running just re-upserts; NEVER delete-all — Pitfall 5). Mirrors
`seed_default_kb.py`'s shape: sys.path insert for backend imports, `get_supabase()`,
an idempotent `main()`, ENV_FILE-honored config, and progress prints.

BELT vs SUSPENDERS:
- This seed is the LATENCY optimization (the "belt"): it warms `model_cache` at deploy
  time so the very first user request is fast instead of paying the cold OpenRouter fetch.
- The CORRECTNESS guarantee (the "suspenders") is the FIRST-REQUEST POPULATE inside the
  router: `refresh_if_stale` populates an empty cache synchronously on the first read
  (D-05), so the catalog is never empty even if this seed never runs.

ENV targeting (Dual Supabase envs — project memory):
- `config.py` loads `.env` (dev) or `.env.prod` (prod) based on the `ENV_FILE` env var via
  python-dotenv at import. Running `ENV_FILE=.env.prod python -m scripts.seed_model_cache`
  seeds the PROD project; the default (`.env`) seeds dev. The seed targets whatever project
  the loaded settings/get_supabase() point at.

The parse + cache-row mapping is REUSED from `model_catalog_service` (`fetch_catalog` +
`_to_cache_row`) — this script does NOT re-implement free/paid tagging or the row shape.

Ops note (Open Q2): a `[deploy] release_command` in `fly.toml` running
`python -m scripts.seed_model_cache` is an available, idempotent optimization for a future
ops pass. It is intentionally NOT added in Phase 12 — the first-request populate (D-05) is
the correctness guarantee, so the seed stays a manual/optional warm-up.
"""

import os
import sys
from datetime import datetime, timezone

# Add backend directory to sys.path so imports work when run as a module / script.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_supabase
from services.model_catalog_service import _to_cache_row, fetch_catalog


def main() -> None:
    """Fetch the live OpenRouter catalog and idempotently upsert it into model_cache.

    Idempotent: keyed on model_id via on_conflict, so re-running re-upserts the same rows
    (no duplicates, no delete-all). Prints a seeded/updated count.
    """
    db = get_supabase()
    print("Seeding model_cache from the live OpenRouter catalog...")

    catalog = fetch_catalog()
    fetched_at = datetime.now(timezone.utc).isoformat()
    # Reuse the plan-01 row mapping (free/paid tag + trimmed serve fields + raw); skip
    # any upstream row missing an id (can't be a PK).
    cache_rows = [_to_cache_row(m, fetched_at) for m in catalog if m.get("id")]

    if not cache_rows:
        print("No models returned from the catalog — nothing to seed.")
        return

    # model_id-keyed upsert: NEVER delete-all (Pitfall 5); idempotent on re-run.
    db.table("model_cache").upsert(cache_rows, on_conflict="model_id").execute()
    print(f"Seeded/updated {len(cache_rows)} models into model_cache.")


if __name__ == "__main__":
    main()
