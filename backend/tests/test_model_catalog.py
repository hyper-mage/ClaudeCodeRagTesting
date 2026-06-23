"""Phase 12 Plan 01 — pure model-catalog logic + refresh-if-stale (MODEL-02/03/04/07).

Wave 0 (written BEFORE services.model_catalog_service exists). On first run these
FAIL RED at the in-function `from services.model_catalog_service import ...` (the
module / its symbols do not yet exist). They go GREEN once Task 2 ships the service.

Coverage map (node IDs bound to 12-VALIDATION.md):
  - tag_is_free / -1 sentinel / defensive parse ........ MODEL-02 (T-12-V5-01 defensive)
  - price_per_mtok / context_length null-safe .......... MODEL-07
  - popularity_for from POPULAR_MODELS index ........... MODEL-03 (D-06/D-07/D-08/D-09)
  - refresh_if_stale: stale / within-TTL / serve-stale . MODEL-04 (D-01/D-03/D-04/D-05)

Test norms mirrored from the codebase:
  - imports happen INSIDE each test body (so import errors surface as RED, not collection
    errors, and so monkeypatch of get_settings is fresh per test)
  - supabase chain mocked via MagicMock().table(...).select(...).execute().data
    (same shape used in test_keys_status.py / test_demo_bootstrap.py)
  - TTL injected by monkeypatching the setting (no freezegun/time-machine dep)
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_FIXTURE = Path(__file__).parent / "fixtures" / "openrouter_models_sample.json"


def _fixture_models() -> list[dict]:
    return json.loads(_FIXTURE.read_text())["data"]


def _by_id(model_id: str) -> dict:
    for m in _fixture_models():
        if m["id"] == model_id:
            return m
    raise AssertionError(f"fixture missing model {model_id}")


# ---------------------------------------------------------------------
# MODEL-02 — free / paid tagging (verified decision matrix)
# ---------------------------------------------------------------------
def test_free_by_suffix():
    """A model id ending `:free` → tag_is_free True."""
    from services.model_catalog_service import tag_is_free
    assert tag_is_free(_by_id("meta-llama/llama-3.3-70b-instruct:free")) is True


def test_free_by_zero_price():
    """pricing.prompt=='0' AND completion=='0' (no :free suffix) → True."""
    from services.model_catalog_service import tag_is_free
    model = {"id": "vendor/zero-priced", "pricing": {"prompt": "0", "completion": "0"}}
    assert tag_is_free(model) is True


def test_sentinel_not_free():
    """openrouter/auto with prompt '-1' → tag_is_free False AND price_per_mtok None."""
    from services.model_catalog_service import price_per_mtok, tag_is_free
    auto = _by_id("openrouter/auto")
    assert tag_is_free(auto) is False
    assert price_per_mtok(auto["pricing"]["prompt"]) is None
    assert price_per_mtok(auto["pricing"]["completion"]) is None


def test_pricing_parse_guards():
    """Missing pricing key / None / non-numeric string → None, no exception raised."""
    from services.model_catalog_service import price_per_mtok, tag_is_free
    # price_per_mtok defensive across hostile inputs
    assert price_per_mtok(None) is None
    assert price_per_mtok("not-a-number") is None
    assert price_per_mtok({}) is None
    assert price_per_mtok([]) is None
    # tag_is_free must not raise on a model with no pricing key at all
    assert tag_is_free({"id": "test/missing-pricing-edge"}) is False
    # pricing present but a sub-value is None
    assert tag_is_free({"id": "x/y", "pricing": {"prompt": None, "completion": None}}) is False


# ---------------------------------------------------------------------
# MODEL-07 — per-Mtok math + null-safe context_length
# ---------------------------------------------------------------------
def test_price_per_mtok():
    """'0.00000015' → 0.15; '0.0000006' → 0.60 (× 1e6)."""
    from services.model_catalog_service import price_per_mtok
    assert price_per_mtok("0.00000015") == 0.15
    assert price_per_mtok("0.0000006") == 0.60


def test_context_length_nullsafe():
    """A model with context_length absent → surfaced as None, no KeyError;
    a model with it present → surfaced as the int."""
    from services.model_catalog_service import build_model_response
    edge = build_model_response(_by_id("test/missing-pricing-edge"))
    assert edge["context_length"] is None
    mini = build_model_response(_by_id("openai/gpt-4o-mini"))
    assert mini["context_length"] == 128000
    # build_model_response composes the verified per-Mtok hints + is_free + raw pricing
    assert mini["is_free"] is False
    assert mini["price_per_mtok_prompt"] == 0.15
    assert mini["price_per_mtok_completion"] == 0.60
    assert mini["pricing"] == _by_id("openai/gpt-4o-mini")["pricing"]
    # the -1 sentinel row surfaces no price
    auto = build_model_response(_by_id("openrouter/auto"))
    assert auto["price_per_mtok_prompt"] is None
    assert auto["price_per_mtok_completion"] is None


# ---------------------------------------------------------------------
# MODEL-03 — curated popularity tagging (D-06/D-07/D-08/D-09)
# ---------------------------------------------------------------------
def test_popularity_tagging():
    """id at POPULAR_MODELS index 1 → (1, 'curated'); id absent → (None, 'curated')."""
    from services.model_catalog_service import popularity_for
    popular = ["vendor/most-popular", "vendor/second", "vendor/third"]
    assert popularity_for("vendor/second", popular) == (1, "curated")
    assert popularity_for("vendor/most-popular", popular) == (0, "curated")
    assert popularity_for("vendor/not-listed", popular) == (None, "curated")


# ---------------------------------------------------------------------
# MODEL-04 — refresh-if-stale orchestration (D-01/D-03/D-04/D-05)
# ---------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stub_db(initial_rows: list[dict]):
    """A MagicMock supabase client whose model_cache select returns `initial_rows`,
    and whose upsert(...).execute() replaces what the *next* select returns.

    The production refresh path is: select all → (stale?) → fetch + upsert → re-select.
    We model that by swapping the select payload after an upsert lands.
    """
    state = {"rows": list(initial_rows)}

    select_result = MagicMock()

    def _select_data():
        return list(state["rows"])

    # .table(...).select("*").execute().data  -> current state["rows"]
    type(select_result).data = property(lambda self: _select_data())

    table = MagicMock()
    table.select.return_value.execute.return_value = select_result

    def _upsert(payload, *a, **kw):
        # payload may be a list of row dicts; replace state so the re-select sees fresh rows
        rows = payload if isinstance(payload, list) else [payload]
        state["rows"] = rows
        up = MagicMock()
        up.execute.return_value = MagicMock(data=rows)
        return up

    table.upsert.side_effect = _upsert

    db = MagicMock()
    db.table.return_value = table
    db._state = state  # expose for assertions
    return db


def test_refresh_when_stale(monkeypatch):
    """Empty cache (and TTL=0) → fetch invoked, rows upserted, fresh model present."""
    import services.model_catalog_service as svc

    # Force stale: TTL=0 means any age (incl. empty cache) is stale.
    monkeypatch.setattr(svc, "get_settings", lambda: MagicMock(model_cache_ttl_seconds=0))

    fetch_calls = {"n": 0}

    def _fetch():
        fetch_calls["n"] += 1
        return _fixture_models()

    monkeypatch.setattr(svc, "fetch_catalog", _fetch)

    db = _stub_db([])  # empty cache → stale → must populate
    rows = svc.refresh_if_stale(db)

    assert fetch_calls["n"] == 1, "stale cache must trigger exactly one fetch"
    returned_ids = {r["model_id"] if "model_id" in r else r["id"] for r in rows}
    assert "openai/gpt-4o-mini" in returned_ids
    assert len(rows) == len(_fixture_models())


def test_serve_cached_within_ttl(monkeypatch):
    """Fresh fetched_at within TTL → fetch NOT invoked, cached rows returned."""
    import services.model_catalog_service as svc

    monkeypatch.setattr(svc, "get_settings", lambda: MagicMock(model_cache_ttl_seconds=86400))

    fetch_calls = {"n": 0}

    def _fetch():
        fetch_calls["n"] += 1
        return _fixture_models()

    monkeypatch.setattr(svc, "fetch_catalog", _fetch)

    fresh_rows = [
        {"model_id": "openai/gpt-4o-mini", "name": "x", "fetched_at": _now_iso()},
    ]
    db = _stub_db(fresh_rows)
    rows = svc.refresh_if_stale(db)

    assert fetch_calls["n"] == 0, "within-TTL cache must NOT trigger a fetch"
    assert {r["model_id"] for r in rows} == {"openai/gpt-4o-mini"}


def test_serve_stale_on_fetch_failure(monkeypatch):
    """Stale rows present + fetch raises → existing rows returned, no exception (D-04)."""
    import services.model_catalog_service as svc

    monkeypatch.setattr(svc, "get_settings", lambda: MagicMock(model_cache_ttl_seconds=0))

    def _boom():
        raise RuntimeError("openrouter unreachable")

    monkeypatch.setattr(svc, "fetch_catalog", _boom)

    stale_rows = [
        {"model_id": "openai/gpt-4o-mini", "name": "x",
         "fetched_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()},
    ]
    db = _stub_db(stale_rows)
    rows = svc.refresh_if_stale(db)  # must NOT raise

    assert {r["model_id"] for r in rows} == {"openai/gpt-4o-mini"}, "must serve the stale rows"
