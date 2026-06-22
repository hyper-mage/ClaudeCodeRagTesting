"""SEC-01 secret-scrub primitive for backend logs + SSE-error payloads.

`scrub_secrets()` is the chokepoint that prevents a decrypted OpenRouter key
(`sk-or-…`) from crossing the backend → observability trust boundary (logs,
SSE error events, and — via plan 11-04's `_ScrubFilter` — exc_info tracebacks).

Mirrors the frontend redaction in frontend/src/lib/sentry.ts:31, but uses a
BROADER regex per D-11: the backend matches any `sk-or-` prefix (not just the
`sk-or-v1-` form the FE pins) so any future OpenRouter key prefix is caught too.
"""
import re

# Broadened backend form (D-11): catches sk-or-v1-… AND any future sk-or- prefix.
# Compiled once at module scope (mirror the FE OR_KEY constant).
_OR_KEY = re.compile(r"sk-or-[A-Za-z0-9_-]+")


def scrub_secrets(s: str) -> str:
    """Redact OpenRouter `sk-or-…` keys to `[redacted-key]`.

    Non-str values pass through unchanged so this is safe to apply blindly to
    arbitrary log/SSE fields (mirrors the sentry.ts `scrub` helper).
    """
    if not isinstance(s, str):
        return s
    return _OR_KEY.sub("[redacted-key]", s)
