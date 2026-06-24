from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class DocumentMetadata(BaseModel):
    document_type: Literal[
        "technical_documentation",
        "meeting_notes",
        "research_paper",
        "tutorial",
        "email",
        "general",
    ] = "general"
    topic: str = ""
    keywords: list[str] = []
    summary: str = ""
    language: str = "en"


class ThreadCreate(BaseModel):
    title: str | None = None


class ThreadResponse(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    model: str | None = None  # Phase 13 — per-thread model pin (rides every thread read; null = default tier, D-05)


class ThreadWithMessages(ThreadResponse):
    messages: list["MessageResponse"]


# ----- User preferences + per-thread model (Phase 13, MODEL-05 / MODEL-06 / PREF-02) -----

class PreferencesResponse(BaseModel):
    """GET /api/preferences — the user's resolved preferences (MODEL-05 / PREF-02).

    theme is ALWAYS present on the wire (never None): the endpoint fills the
    'dark' default for a brand-new user with no row. default_model stays None
    when the user has not pinned one (null = owner default tier, D-05).
    """
    default_model: str | None = None
    theme: str = "dark"


class PreferencesUpdate(BaseModel):
    """PUT /api/preferences body — a PARTIAL update (RESEARCH Pattern 2).

    Both fields default to None so the endpoint's model_dump(exclude_unset=True)
    sends ONLY the keys the client actually provided — a theme-only body must NOT
    carry default_model (which would clobber the other field in the upsert).
    theme is a Literal so an invalid value (e.g. "purple") is rejected at
    validation time (422) before it can poison the stored row (T-13-01).
    """
    default_model: str | None = None
    theme: Literal["light", "dark"] | None = None


class ThreadModelUpdate(BaseModel):
    """PATCH /api/threads/{id} body — set or clear the per-thread model pin (MODEL-06).

    null is a DELIBERATE, explicit value (clears the pin back to the default tier,
    D-05). The PATCH endpoint writes model explicitly — it does NOT use
    exclude_unset (RESEARCH Pattern 3 caution), so {model: null} round-trips as a
    real clear rather than being skipped.
    """
    model: str | None = None


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    tools_used: list[dict] | None = None
    created_at: datetime


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    mime_type: str
    status: str
    error_message: str | None
    chunk_count: int | None
    content_hash: str | None = None
    metadata: dict | None = None
    created_at: datetime
    updated_at: datetime


# ----- OpenRouter BYOK key exchange (Phase 10) -----

class ExchangeRequest(BaseModel):
    """POST body for /api/keys/openrouter/exchange — the PKCE code + verifier.

    Accepting these only via a JSON body (never query params) keeps the code /
    code_verifier out of URLs/logs (T-10-07).
    """
    code: str
    code_verifier: str


class KeyStatusResponse(BaseModel):
    """GET /api/keys/status — masked-only connection state (KEY-03, T-10-03).

    Never carries the key: only a boolean, the non-secret masked tail, and the
    stored connected_at timestamp (typed `str` so it passes through as-is for
    frontend date formatting).
    """
    connected: bool
    masked_label: str | None = None
    connected_at: str | None = None


# ----- Model catalog (Phase 12, MODEL-01 / MODEL-07, D-10) -----

class ModelResponse(BaseModel):
    """One render-ready OpenRouter catalog entry served by GET /api/models (D-10).

    The backend does ALL the tagging/price math (via the plan 12-01 pure functions);
    the frontend RENDERS these fields and never recomputes free/paid status, per-Mtok
    hints, or popularity. The raw `pricing` strings are retained verbatim (D-10) so a
    future feature can re-derive other figures without a re-fetch.
    """
    id: str
    name: str | None = None
    context_length: int | None = None
    is_free: bool
    price_per_mtok_prompt: float | None = None
    price_per_mtok_completion: float | None = None
    popularity_rank: int | None = None
    popularity_source: str = "curated"
    pricing: dict


# ----- Explorer sub-agent (Phase 5) -----

class ExplorerFinding(BaseModel):
    """A single piece of evidence surfaced by the explorer sub-agent."""
    title: str = Field(max_length=120)
    path: str | None = None
    excerpt: str = Field(max_length=500)
    relevance: str = Field(max_length=200)


class ExplorerResult(BaseModel):
    """Structured result returned by the explorer sub-agent.

    Hard caps enforced by Pydantic so oversized output is rejected at
    validation time rather than silently truncated downstream.
    """
    mode: str = Field(pattern="^(deep_search|summarize|find_similar)$")
    query: str
    findings: list[ExplorerFinding] = Field(default_factory=list, max_length=8)
    synthesis: str = Field(max_length=2000)
    tools_used: list[str] = Field(default_factory=list)
    iterations: int = 0
    budget_exhausted: bool = False
