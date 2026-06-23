"""Phase 12 — OpenRouter model-catalog cache: pure tagging/pricing/popularity
functions + the lazy refresh-if-stale orchestration (MODEL-02/03/04/07).

This module mirrors `budget_service`'s posture: side-effect-free pure functions for
the genuinely-new reasoning (defensive pricing parse, free/paid tagging, curated
popularity), plus one I/O helper (`fetch_catalog`) and one orchestrator
(`refresh_if_stale`) that the `GET /api/models` router composes.

Design notes (from 12-RESEARCH.md, verified against the live OpenRouter API):
- The catalog endpoint `https://openrouter.ai/api/v1/models` is PUBLIC — it returns
  HTTP 200 with no Authorization header (and even with an invalid bearer). We send NO
  auth header so the catalog never couples to owner-key availability (the "never empty"
  guarantee, D-05). We also never log the response body (no secret to leak, but we keep
  the same no-log-body hygiene as `openrouter_service.exchange_code`).
- ALL pricing values are STRINGS in per-token USD (e.g. gpt-4o-mini prompt
  "0.00000015" → $0.15/Mtok). Per-Mtok = float(str) * 1_000_000, but ONLY via a guarded
  parse — a `-1` sentinel (openrouter/auto etc.) and any missing/malformed value must
  yield None and NEVER raise (D-11, T-12-V5-01).
- Free rule (verified, zero contradictions across 340 live models):
  is_free = id.endswith(":free") OR (pricing.prompt == "0" AND pricing.completion == "0").
- Refresh is read-triggered with a 24h TTL (D-03 — NO scheduler; Fly suspend kills
  timers). On a stale/empty cache we fetch + upsert keyed on model_id (NEVER delete-all,
  Pitfall 5) then re-select. On a fetch failure we serve the existing stale rows (D-04).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

CATALOG_URL = "https://openrouter.ai/api/v1/models"


# =============================================================================
# I/O: fetch the public catalog (mirrors budget_service.fetch_model_context_length)
# =============================================================================
def fetch_catalog() -> list[dict]:
    """GET the full OpenRouter model catalog.

    The endpoint is PUBLIC — no Authorization header is sent (do NOT couple the
    catalog to an owner key; that would break the "never empty" guarantee, D-05).
    Raises on a non-2xx (caller decides whether to serve stale, D-04). The response
    body is never logged.
    """
    resp = httpx.get(CATALOG_URL, timeout=10)
    resp.raise_for_status()
    return resp.json().get("data", [])


# =============================================================================
# Pure functions: defensive pricing / free-or-paid / popularity (D-10, D-11)
# =============================================================================
def price_per_mtok(per_token: object) -> float | None:
    """Guarded per-token-USD → per-Mtok conversion.

    Returns None for anything that is not a parseable, non-negative decimal string:
      - non-str input (None, dict, list, int) → None
      - non-numeric string → None
      - the `-1` sentinel (variable-priced routers, e.g. openrouter/auto) → None

    NEVER raises and NEVER does a blind float() (D-11). Live data is plain decimal
    strings (no scientific notation), so float() inside try/except is safe.
    """
    if not isinstance(per_token, str):
        return None
    try:
        value = float(per_token)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return round(value * 1_000_000, 4)


def tag_is_free(model: dict) -> bool:
    """Free/paid tag per the verified rule.

    is_free = id.endswith(":free") OR (pricing.prompt == "0" AND pricing.completion == "0").

    Every field access is guarded via .get() so a model with no `pricing` key, or with
    None sub-values, returns False instead of raising (T-12-V5-01). The `-1` sentinel is
    naturally NOT free (it is neither ":free" nor "0").
    """
    if str(model.get("id", "")).endswith(":free"):
        return True
    pricing = model.get("pricing") or {}
    return pricing.get("prompt") == "0" and pricing.get("completion") == "0"


def popularity_for(model_id: str, popular: list[str]) -> tuple[int | None, str]:
    """Curated popularity: rank = position in the ordered POPULAR_MODELS list.

    Returns (index, "curated") when present; (None, "curated") when absent — a model
    that is not in the curated list degrades gracefully to a null rank (D-08/D-09). The
    source is always "curated" in Phase 12; a future AA-integration phase overwrites the
    rank and flips source to "artificialanalysis" with no reshape (D-08).
    """
    try:
        return popular.index(model_id), "curated"
    except ValueError:
        return None, "curated"


def build_model_response(model: dict) -> dict:
    """Compose a render-ready catalog entry from a raw OpenRouter model row.

    Accepts either a raw OpenRouter model object (keyed `id`/`pricing`/`context_length`)
    or a cached `model_cache` row (keyed `model_id`/`pricing`/`context_length`); resolves
    the id from whichever is present. Computes is_free + per-Mtok hints + null-safe
    context_length + curated popularity, and RETAINS the raw pricing strings (D-10).

    Never raises on a malformed/partial row — missing fields surface as None/False.
    """
    settings = get_settings()
    model_id = str(model.get("id") or model.get("model_id") or "")

    pricing = model.get("pricing") or {}
    # Normalize so tag_is_free / id-suffix checks work on either input shape.
    normalized = {"id": model_id, "pricing": pricing}

    ctx = model.get("context_length")
    context_length = ctx if isinstance(ctx, int) else None

    rank, source = popularity_for(model_id, settings.POPULAR_MODELS)

    return {
        "id": model_id,
        "name": model.get("name"),
        "context_length": context_length,
        "is_free": tag_is_free(normalized),
        "price_per_mtok_prompt": price_per_mtok(pricing.get("prompt")),
        "price_per_mtok_completion": price_per_mtok(pricing.get("completion")),
        "popularity_rank": rank,
        "popularity_source": source,
        "pricing": pricing,
    }


# =============================================================================
# Orchestration: lazy refresh-if-stale on read (D-03/D-04/D-05, Pitfall 5)
# =============================================================================
def _parse_ts(value: object) -> datetime | None:
    """Parse a Postgres/ISO timestamp string into an aware datetime; None if unparseable."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    # Postgres often emits a trailing 'Z'; fromisoformat (3.10) needs +00:00.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_stale(rows: list[dict], ttl_seconds: int) -> bool:
    """True when the cache is empty OR its newest fetched_at is older than the TTL.

    An empty cache is always stale (forces the first-request populate path, D-05). A
    TTL of 0 forces every read stale (the injectable knob MODEL-04 tests use). A row
    with an unparseable/absent fetched_at is treated as stale (fail toward freshness).
    """
    if not rows:
        return True
    timestamps = [_parse_ts(r.get("fetched_at")) for r in rows]
    newest = max((t for t in timestamps if t is not None), default=None)
    if newest is None:
        return True
    age_seconds = (datetime.now(timezone.utc) - newest).total_seconds()
    return age_seconds > ttl_seconds


def _to_cache_row(model: dict, fetched_at: str) -> dict:
    """Map a raw OpenRouter model object to a `model_cache` row (PK = model_id).

    Stores the trimmed serve-time fields + raw pricing (D-10) and the full raw object so
    future fields need no re-fetch. `is_free` is precomputed so the router can do a
    SQL-side `?free_only` filter (D-02). `fetched_at` is shared across the batch and
    restamped on every successful refresh.
    """
    ctx = model.get("context_length")
    return {
        "model_id": str(model.get("id") or ""),
        # Coalesce a missing/empty upstream name to the model_id (mirrors the same
        # `str(model.get("id") or "")` used for model_id above). This is the primary
        # CR-01 fix: defense-in-depth so the served `name` is NEVER NULL — one nameless
        # upstream model can no longer fail the whole batch upsert and empty the cache,
        # even after migration 031 relaxes the column to nullable (T-12-V5-01, D-05).
        "name": model.get("name") or str(model.get("id") or ""),
        "context_length": ctx if isinstance(ctx, int) else None,
        "pricing": model.get("pricing") or {},
        "is_free": tag_is_free(model),
        "raw": model,
        "fetched_at": fetched_at,
    }


def refresh_if_stale(db) -> list[dict]:
    """Serve the model_cache rows, lazily refreshing from OpenRouter when stale.

    Flow (D-03/D-04/D-05):
      1. Select all rows + compute the newest fetched_at.
      2. Within TTL and non-empty → return rows as-is (no fetch).
      3. Stale or empty → fetch the catalog, upsert keyed on model_id (NEVER delete-all,
         Pitfall 5), restamp fetched_at, and re-select.
      4. If the fetch (or write) fails → log a body-free warning and return the existing
         rows (serve stale, availability > freshness, D-04). NEVER raises.

    TTL is read via get_settings() at call time so tests can monkeypatch it.
    Advisory-lock herd control is intentionally omitted: the upsert is idempotent on
    model_id, so a rare concurrent double-fetch is merely wasteful, not incorrect (A2).
    """
    ttl_seconds = get_settings().model_cache_ttl_seconds
    rows = db.table("model_cache").select("*").execute().data or []

    if not _is_stale(rows, ttl_seconds):
        return rows

    try:
        catalog = fetch_catalog()
        fetched_at = datetime.now(timezone.utc).isoformat()
        cache_rows = [_to_cache_row(m, fetched_at) for m in catalog if m.get("id")]
        # WR-01: NEVER issue a blind upsert([]). An empty catalog (upstream returned
        # nothing, or every row was filtered out for lacking an id) must not wipe or
        # no-op-churn the table — serve the existing rows and log a DISTINCT warning so
        # this is not confused with the generic fetch-failure path below.
        if not cache_rows:
            logger.warning(
                "model_cache refresh got an empty catalog, serving stale (%d rows)", len(rows)
            )
            return rows
        db.table("model_cache").upsert(cache_rows, on_conflict="model_id").execute()
        return db.table("model_cache").select("*").execute().data or []
    except Exception as exc:
        # WR-02: distinguish the cold-cache failure (rows == []) from the serve-stale
        # path. We cannot serve rows we never fetched, so we still return `rows` (== []),
        # but the log must be HONEST about it rather than claiming "serving stale".
        if not rows:
            logger.warning(
                "model_cache refresh failed on an EMPTY cache, returning empty catalog: %s",
                type(exc).__name__,
            )
        else:
            logger.warning("model_cache refresh failed, serving stale: %s", type(exc).__name__)
        return rows
