"""Phase 16 Wave 0 scaffold — web-search restoration contract (RED until plan 16-02).

Encodes the full WSRCH-01..04 + D-04 + D-03-backend contract for the restored
`web_search` tool. These tests FAIL/ERROR against current code and are the RED
baseline the Wave 2 backend fix (plan 16-02) turns GREEN:

  - WSRCH-01: `_search_tavily` must send `Authorization: Bearer <key>` (header-only,
              NO `api_key` in the JSON body) and read `search_depth` from settings.
  - WSRCH-02: `search_web` fail-closed gating (already correct — verified here).
  - WSRCH-03/D-02: `system_prompt` carries the inline-links + "Sources:" guidance.
  - WSRCH-04: graceful `{"error": ...}` + `logger.error(..., exc_info=True)` on failure,
              AND the chat.py `tool_result_is_error` classifier (D-03 backend half).
  - D-04: `search_depth` read from `settings.web_search_depth`, not hardcoded "basic".

Mocking convention (project has NO HTTP mocking library): monkeypatch the module
symbol + unittest.mock.MagicMock, mirroring tests/test_error_surfacing.py.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

from services import web_search_service


# ---------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------

def _canned_tavily_body() -> dict:
    """A minimal Tavily 200 response body (content→snippet mapping source)."""
    return {"answer": "A", "results": [{"title": "T", "url": "U", "content": "C"}]}


def _fake_settings(key: str = "tvly-test-key", max_results: int = 5,
                   depth: str = "advanced") -> SimpleNamespace:
    """Fake settings isolating the transport assertions from the not-yet-added
    Settings.web_search_depth field. `web_search_enabled` derives from the key."""
    return SimpleNamespace(
        web_search_provider="tavily",
        web_search_api_key=key,
        web_search_max_results=max_results,
        web_search_depth=depth,
        web_search_enabled=bool(key),
    )


def _install_capturing_post(monkeypatch, body: dict | None = None, raise_exc: Exception | None = None):
    """Monkeypatch services.web_search_service.httpx.post with a capturing fake.

    Records the url/headers/json/timeout kwargs and the call count; returns a
    MagicMock response whose .raise_for_status() is a no-op and whose .json()
    yields a canned Tavily body. If `raise_exc` is set, the fake raises instead.
    """
    captured: dict = {"calls": 0}

    def fake_post(url, *args, **kwargs):
        captured["calls"] += 1
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        captured["json"] = kwargs.get("json")
        captured["timeout"] = kwargs.get("timeout")
        if raise_exc is not None:
            raise raise_exc
        resp = MagicMock()
        resp.raise_for_status = MagicMock()  # no-op → 200 path
        resp.json = MagicMock(return_value=body if body is not None else _canned_tavily_body())
        return resp

    monkeypatch.setattr("services.web_search_service.httpx.post", fake_post)
    return captured


# ---------------------------------------------------------------------
# WSRCH-01 — Bearer auth transport + result mapping
# ---------------------------------------------------------------------

def test_tavily_bearer_auth(monkeypatch):
    """WSRCH-01: _search_tavily posts the key in an `Authorization: Bearer` header,
    NOT as an `api_key` body field; body carries query/max_results/include_answer
    and search_depth from settings. RED today (code sends `api_key` in the body,
    no header, and hardcodes search_depth)."""
    captured = _install_capturing_post(monkeypatch)
    settings = _fake_settings(depth="advanced")

    web_search_service._search_tavily("catan price", settings)

    headers = captured.get("headers") or {}
    assert headers.get("Authorization") == "Bearer tvly-test-key"

    body = captured.get("json") or {}
    assert "api_key" not in body  # header-only auth — no key in the body
    assert body.get("query") == "catan price"
    assert body.get("include_answer") is True
    assert body.get("max_results") == settings.web_search_max_results
    assert body.get("search_depth") == settings.web_search_depth


def test_tavily_maps_results(monkeypatch):
    """WSRCH-01: a 200 body maps to {answer, results:[{title,url,snippet}]}
    (Tavily `content` → `snippet` rename preserved)."""
    _install_capturing_post(
        monkeypatch,
        body={"answer": "A", "results": [{"title": "T", "url": "U", "content": "C"}]},
    )
    settings = _fake_settings()

    result = web_search_service._search_tavily("q", settings)

    assert result == {"answer": "A", "results": [{"title": "T", "url": "U", "snippet": "C"}]}


# ---------------------------------------------------------------------
# WSRCH-02 — fail-closed gating
# ---------------------------------------------------------------------

def test_gating_fail_closed(monkeypatch):
    """WSRCH-02: with no key (web_search_enabled False), search_web returns the
    config error and NEVER calls httpx.post; with a key set, the tavily path runs."""
    captured = _install_capturing_post(monkeypatch)

    disabled = _fake_settings(key="")  # web_search_enabled False
    monkeypatch.setattr("services.web_search_service.get_settings", lambda: disabled)
    out = web_search_service.search_web("x")
    assert out == {"error": "Web search not configured", "results": []}
    assert captured["calls"] == 0  # fail-closed — no external call

    enabled = _fake_settings(key="tvly-test-key")  # web_search_enabled True
    monkeypatch.setattr("services.web_search_service.get_settings", lambda: enabled)
    web_search_service.search_web("x")
    assert captured["calls"] == 1  # tavily path taken


# ---------------------------------------------------------------------
# WSRCH-03 / D-02 — citation guidance in the system prompt
# ---------------------------------------------------------------------

def test_system_prompt_citation_guidance(monkeypatch):
    """WSRCH-03 / D-02: system_prompt specifies inline markdown-link citations and a
    trailing "Sources:" list. RED today — the prompt only says "cite ... with URLs".

    Isolate from any ambient SYSTEM_PROMPT env override (a local .env may set a minimal
    prompt) so this pins the shipped config default, not a deployment's runtime prompt.
    `import config` first so load_dotenv has already populated os.environ before we drop
    the override; monkeypatch restores it after the test."""
    import config  # ensures load_dotenv has run before we remove the override
    monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
    prompt = config.Settings().system_prompt
    assert "Sources:" in prompt
    assert "inline" in prompt.lower()


# ---------------------------------------------------------------------
# WSRCH-04 — graceful failure + logging, and the tool-result error classifier
# ---------------------------------------------------------------------

def test_graceful_failure_logs(monkeypatch):
    """WSRCH-04: when httpx.post raises, _search_tavily returns {"error":..,"results":[]}
    WITHOUT propagating, and logs via logger.error(..., exc_info=True)."""
    req = httpx.Request("POST", "https://api.tavily.com/search")
    resp = httpx.Response(401, request=req)
    exc = httpx.HTTPStatusError("401 Unauthorized", request=req, response=resp)
    _install_capturing_post(monkeypatch, raise_exc=exc)

    fake_logger = MagicMock()
    monkeypatch.setattr("services.web_search_service.logger", fake_logger)
    settings = _fake_settings()

    result = web_search_service._search_tavily("q", settings)  # must not raise

    assert "error" in result
    assert result["results"] == []
    assert fake_logger.error.called
    assert fake_logger.error.call_args.kwargs.get("exc_info") is True


def test_tool_result_error_status():
    """WSRCH-04 / D-03 backend half: the chat.py pure classifier `tool_result_is_error`
    returns True for a JSON string carrying an "error" key (→ tool_entry status "error",
    is_error=true on the SSE event) and False for a normal result. RED today — the helper
    is extracted by plan 16-02 Task 3, so this LOCAL import ERRORs (ImportError) until then."""
    from routers.chat import tool_result_is_error  # 16-02 Task 3 extracts this
    assert tool_result_is_error(json.dumps({"error": "Web search not configured", "results": []})) is True
    assert tool_result_is_error(json.dumps({"answer": "A", "results": [{"title": "T"}]})) is False


# ---------------------------------------------------------------------
# D-04 — search_depth is read from settings (not hardcoded "basic")
# ---------------------------------------------------------------------

def test_search_depth_passed(monkeypatch):
    """D-04: with settings.web_search_depth == "advanced", the posted body carries
    search_depth "advanced" — proving it is read from settings, not hardcoded "basic"."""
    captured = _install_capturing_post(monkeypatch)
    settings = _fake_settings(depth="advanced")

    web_search_service._search_tavily("q", settings)

    body = captured.get("json") or {}
    assert body.get("search_depth") == "advanced"
