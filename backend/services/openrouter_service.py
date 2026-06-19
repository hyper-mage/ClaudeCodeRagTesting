"""OpenRouter OAuth code→key exchange (Phase 10, KEY-01).

A single outbound httpx POST to OpenRouter's PKCE token endpoint. Mirrors the
synchronous httpx pattern in budget_service.fetch_model_context_length (the
established codebase norm for openrouter.ai calls inside async routers) — but
deliberately does NOT copy its swallow-into-logger.warning behavior.

SECURITY (Pitfall 1 / SEC-01 / T-10-04):
- The OpenRouter response body holds the freshly-minted sk-or-v1-… key. This
  module NEVER logs resp.text / resp.json() (or anything derived from the body).
- On a non-2xx response, raise_for_status() raises httpx.HTTPStatusError and we
  let it PROPAGATE — the keys.py router maps it to a generic 502. No blanket
  try/except that returns None and no logging of the error/response here.
"""
import httpx


def exchange_code(code: str, code_verifier: str) -> str:
    """Exchange an OAuth authorization code for an OpenRouter API key (PKCE S256).

    POSTs {code, code_verifier, code_challenge_method:"S256"} to OpenRouter's
    token endpoint and returns the plaintext key from the response body.

    Raises:
        httpx.HTTPStatusError: on any non-2xx response (the caller maps this to
            a generic HTTPException — the response body is never surfaced).
    """
    resp = httpx.post(
        "https://openrouter.ai/api/v1/auth/keys",
        json={
            "code": code,
            "code_verifier": code_verifier,
            "code_challenge_method": "S256",
        },
        timeout=15,
    )
    resp.raise_for_status()  # non-2xx → HTTPStatusError; caller wraps generically
    return resp.json()["key"]  # response body: {key, user_id?}
