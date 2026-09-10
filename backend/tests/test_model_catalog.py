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


# ---------------------------------------------------------------------
# CR-01 / VERIFICATION truth #5 — a nameless upstream model must NOT
# empty/stall the cache (constraint-aware regression, closes WR-03)
# ---------------------------------------------------------------------
def _constraint_aware_stub_db(initial_rows: list[dict]):
    """Like `_stub_db`, but the upsert MIMICS the live `name TEXT NOT NULL` posture:
    any row whose `name` is None/empty raises, simulating a Postgres NOT NULL violation.

    This is the harness WR-03 demands — the route test's mock DB enforces NO constraint,
    so a nameless upstream model silently passes there. Here a nameless row that reaches
    the upsert WITHOUT the coalesce would blow up the whole batch (exactly CR-01).
    """
    state = {"rows": list(initial_rows)}

    select_result = MagicMock()
    type(select_result).data = property(lambda self: list(state["rows"]))

    table = MagicMock()
    table.select.return_value.execute.return_value = select_result

    def _upsert(payload, *a, **kw):
        rows = payload if isinstance(payload, list) else [payload]
        for r in rows:
            # The live model_cache.name was NOT NULL pre-031; an empty name is the CR-01 trip.
            if r.get("name") in (None, ""):
                raise RuntimeError(
                    "null value in column \"name\" violates not-null constraint"
                )
        state["rows"] = rows
        up = MagicMock()
        up.execute.return_value = MagicMock(data=rows)
        return up

    table.upsert.side_effect = _upsert

    db = MagicMock()
    db.table.return_value = table
    db._state = state
    return db


def test_nameless_model_coalesces_to_model_id(monkeypatch):
    """A nameless upstream model (id present, no `name`) must persist with
    name == its model_id (NOT None) and NEVER fail the batch upsert (CR-01).

    Driven over the constraint-aware stub (which rejects a null name like the live DB
    did pre-031), so without the `_to_cache_row` coalesce this test FAILS RED."""
    import services.model_catalog_service as svc

    monkeypatch.setattr(svc, "get_settings", lambda: MagicMock(model_cache_ttl_seconds=0))
    monkeypatch.setattr(svc, "fetch_catalog", _fixture_models)

    db = _constraint_aware_stub_db([])  # cold/empty cache → stale → must populate
    rows = svc.refresh_if_stale(db)  # must NOT raise on the nameless row

    assert rows, "cold cache + nameless upstream model must NOT yield an empty catalog"
    by_id = {r["model_id"]: r for r in rows}
    assert "vendor/nameless-edge" in by_id, "the nameless model must persist, not nuke the batch"
    assert by_id["vendor/nameless-edge"]["name"] == "vendor/nameless-edge", (
        "a missing upstream name must coalesce to the model_id, never NULL"
    )


def test_empty_catalog_guard_serves_stale(monkeypatch, caplog):
    """A fetch returning an empty catalog (or all rows filtered out) over a NON-empty
    stale cache must NOT issue a blind `upsert([])` — the existing stale rows are
    returned unchanged and a DISTINCT empty-catalog warning is logged (WR-01)."""
    import logging
    import services.model_catalog_service as svc

    monkeypatch.setattr(svc, "get_settings", lambda: MagicMock(model_cache_ttl_seconds=0))
    monkeypatch.setattr(svc, "fetch_catalog", lambda: [])  # upstream returns nothing

    stale_rows = [
        {"model_id": "openai/gpt-4o-mini", "name": "x",
         "fetched_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()},
    ]
    db = _stub_db(stale_rows)

    with caplog.at_level(logging.WARNING):
        rows = svc.refresh_if_stale(db)

    # The blind upsert([]) must NOT have been issued.
    db.table.return_value.upsert.assert_not_called()
    # The existing stale rows survive unchanged.
    assert {r["model_id"] for r in rows} == {"openai/gpt-4o-mini"}
    # A DISTINCT empty-catalog warning — not the generic "serving stale" failure message.
    assert any("empty catalog" in rec.message for rec in caplog.records), (
        f"expected a distinct empty-catalog warning, got: {[r.message for r in caplog.records]}"
    )


def test_empty_and_failed_distinct_warning(monkeypatch, caplog):
    """A COLD/empty cache + a fetch that RAISES must log a DISTINCT 'empty cache + fetch
    failed → returning empty' warning rather than the misleading generic 'serving stale'
    (you cannot serve rows you never fetched) — WR-02. Still returns [] without raising."""
    import logging
    import services.model_catalog_service as svc

    monkeypatch.setattr(svc, "get_settings", lambda: MagicMock(model_cache_ttl_seconds=0))

    def _boom():
        raise RuntimeError("openrouter unreachable")

    monkeypatch.setattr(svc, "fetch_catalog", _boom)

    db = _stub_db([])  # cold/empty cache
    with caplog.at_level(logging.WARNING):
        rows = svc.refresh_if_stale(db)  # must NOT raise

    assert rows == [], "a cold cache + failed fetch returns empty (cannot serve unfetched rows)"
    msgs = " ".join(rec.message for rec in caplog.records).lower()
    assert "empty" in msgs, (
        f"empty-and-failed must log a distinct honest warning, got: {[r.message for r in caplog.records]}"
    )


def test_fetch_catalog_sends_no_auth_header(monkeypatch):
    """fetch_catalog must send NO Authorization header / no auth in headers — locking the
    'never couple the catalog to an owner key' decision (D-05, WR-05, T-12-V5-03)."""
    import services.model_catalog_service as svc

    captured = {}

    def _fake_get(url, *a, **kw):
        captured["url"] = url
        captured["headers"] = kw.get("headers") or {}
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"data": []}
        return resp

    monkeypatch.setattr(svc.httpx, "get", _fake_get)
    svc.fetch_catalog()

    headers = captured["headers"]
    lower_keys = {k.lower() for k in headers}
    assert "authorization" not in lower_keys, f"fetch_catalog must NOT send auth: {headers}"
    # No bearer/api-key smuggled under any header value either.
    joined = " ".join(str(v) for v in headers.values()).lower()
    assert "bearer" not in joined and "sk-or-" not in joined, f"no key in headers: {headers}"


def test_negative_ttl_rejected_loudly():
    """A negative MODEL_CACHE_TTL_SECONDS must fail Settings validation loudly
    (pydantic ValidationError) rather than silently hammering upstream (WR-04, T-12-V5-04)."""
    from pydantic import ValidationError
    from config import Settings

    with pytest.raises(ValidationError):
        Settings(model_cache_ttl_seconds=-1)


# ---------------------------------------------------------------------
# --- AA-index popularity (quick 260910-lcm) ---
# The live OpenRouter catalog ships benchmarks.artificial_analysis.intelligence_index
# inside each model object (already persisted under model_cache.raw by _to_cache_row),
# so popularity_rank can self-update every 24h with no migration and no extra fetch.
# AA is now PRIMARY (capped at AA_RANK_LIMIT); POPULAR_MODELS is the FALLBACK, offset
# below the AA ranks so the two form one continuous ordering (DD-4).
# ---------------------------------------------------------------------
def test_intelligence_index_both_shapes():
    """The AA reader accepts BOTH input shapes: a raw catalog object (benchmarks at the
    top level) and a `model_cache` row (benchmarks nested under `raw`)."""
    from services.model_catalog_service import intelligence_index

    raw_shape = {
        "id": "a/b",
        "benchmarks": {"artificial_analysis": {"intelligence_index": 52.8}},
    }
    assert intelligence_index(raw_shape) == 52.8

    cache_row_shape = {
        "model_id": "a/b",
        "raw": {"benchmarks": {"artificial_analysis": {"intelligence_index": 52.8}}},
    }
    assert intelligence_index(cache_row_shape) == 52.8


def test_intelligence_index_defensive():
    """Every malformed/absent/wrong-typed benchmarks shape → None, NEVER a raise.

    An unhandled exception here would 500 the whole GET /api/models (the reader runs
    per row inside build_model_response) and blank the model picker — T-LCM-01.
    `design_arena` is a real empty LIST upstream, so a list where a dict is expected is
    not hypothetical. `bool` must NOT be accepted even though it subclasses int.
    """
    from services.model_catalog_service import intelligence_index

    hostile = [
        {},
        {"benchmarks": None},
        {"benchmarks": []},
        {"benchmarks": "nope"},
        {"benchmarks": {"design_arena": []}},
        {"benchmarks": {"artificial_analysis": []}},
        {"benchmarks": {"artificial_analysis": {"intelligence_index": None}}},
        {"benchmarks": {"artificial_analysis": {"intelligence_index": "52.8"}}},
        {"benchmarks": {"artificial_analysis": {"intelligence_index": True}}},
    ]
    for model in hostile:
        assert intelligence_index(model) is None, f"expected None for {model}"


def test_aa_ranking_orders_by_index_desc():
    """Highest intelligence_index → rank 0, descending from there."""
    from services.model_catalog_service import aa_ranking

    def _row(model_id: str, score: float) -> dict:
        return {
            "id": model_id,
            "benchmarks": {"artificial_analysis": {"intelligence_index": score}},
        }

    rows = [_row("a/low", 10.0), _row("a/high", 50.0), _row("a/mid", 30.0)]
    assert aa_ranking(rows) == {"a/high": 0, "a/mid": 1, "a/low": 2}


def test_aa_ranking_tiebreak_is_model_id_asc():
    """Ties in intelligence_index break on model_id ASC (DD-3).

    Real ties exist upstream (two entries at 53.4). Without a deterministic tiebreak the
    Popular section reshuffles between page loads, so the SAME dict must come back even
    when the input row order is reversed.
    """
    from services.model_catalog_service import aa_ranking

    def _row(model_id: str) -> dict:
        return {
            "id": model_id,
            "benchmarks": {"artificial_analysis": {"intelligence_index": 42.0}},
        }

    rows = [_row("z/model"), _row("a/model")]
    expected = {"a/model": 0, "z/model": 1}
    assert aa_ranking(rows) == expected
    assert aa_ranking(list(reversed(rows))) == expected, "ordering must be input-order stable"


def test_aa_ranking_excludes_batch_variants():
    """`:batch` twins carry an identical score and would consume half the ranked slots."""
    from services.model_catalog_service import aa_ranking

    def _row(model_id: str) -> dict:
        return {
            "id": model_id,
            "benchmarks": {"artificial_analysis": {"intelligence_index": 53.4}},
        }

    ranks = aa_ranking([_row("a/x"), _row("a/x:batch")])
    assert "a/x" in ranks
    assert "a/x:batch" not in ranks


def test_aa_ranking_respects_limit():
    """The ordering is CAPPED (DD-4) so the frontend's uncapped Popular section
    (ModelSelector.tsx:198 filters on rank != null) stays bounded."""
    from services.model_catalog_service import aa_ranking

    rows = [
        {
            "id": f"v/m{i:02d}",
            "benchmarks": {"artificial_analysis": {"intelligence_index": float(100 - i)}},
        }
        for i in range(20)
    ]
    ranks = aa_ranking(rows, limit=12)
    assert len(ranks) == 12
    assert sorted(ranks.values()) == list(range(12))


def test_aa_ranking_skips_unscored_and_malformed():
    """Unscored / None / non-dict / empty-id rows are skipped, and nothing raises."""
    from services.model_catalog_service import aa_ranking

    rows = [
        {"id": "a/scored", "benchmarks": {"artificial_analysis": {"intelligence_index": 20.0}}},
        {"id": "a/unscored"},
        None,
        "not-a-dict",
        {"id": "", "benchmarks": {"artificial_analysis": {"intelligence_index": 99.0}}},
        {"model_id": "a/row-shape", "raw": {"benchmarks": {"artificial_analysis": {"intelligence_index": 30.0}}}},
    ]
    ranks = aa_ranking(rows)  # must NOT raise
    assert ranks == {"a/row-shape": 0, "a/scored": 1}


def test_popularity_for_aa_wins_over_curated():
    """A model carrying an AA rank takes it, with source 'artificialanalysis', even when
    it is ALSO pinned in the curated list."""
    from services.model_catalog_service import popularity_for

    assert popularity_for("vendor/top", ["vendor/top"], aa_ranks={"vendor/top": 0}) == (
        0,
        "artificialanalysis",
    )


def test_popularity_for_curated_offset_below_aa():
    """Curated ranks are OFFSET by len(aa_ranks) so AA and curated form ONE continuous
    ordering instead of colliding at rank 0 (DD-4)."""
    from services.model_catalog_service import popularity_for

    aa_ranks = {"x/1": 0, "x/2": 1}
    popular = ["vendor/most-popular", "vendor/second"]
    assert popularity_for("vendor/second", popular, aa_ranks=aa_ranks) == (3, "curated")
    assert popularity_for("vendor/not-listed", popular, aa_ranks=aa_ranks) == (None, "curated")


def test_popularity_for_default_arg_is_unchanged():
    """DD-1 guard: the new param is an OPTIONAL keyword. A two-positional-arg call keeps
    byte-identical pre-change behavior (offset 0, source 'curated')."""
    from services.model_catalog_service import popularity_for

    popular = ["vendor/most-popular", "vendor/second", "vendor/third"]
    assert popularity_for("vendor/second", popular) == (1, "curated")


def test_build_model_response_threads_aa_ranks():
    """build_model_response forwards aa_ranks into popularity_for (DD-2); omitting it
    keeps today's curated-only behavior."""
    from services.model_catalog_service import build_model_response

    row = {
        "model_id": "a/high",
        "name": "A High",
        "pricing": {"prompt": "0.000001", "completion": "0.000002"},
        "raw": {"benchmarks": {"artificial_analysis": {"intelligence_index": 50.0}}},
    }

    ranked = build_model_response(row, aa_ranks={"a/high": 0})
    assert ranked["popularity_rank"] == 0
    assert ranked["popularity_source"] == "artificialanalysis"

    unranked = build_model_response(row)
    assert unranked["popularity_source"] == "curated"
