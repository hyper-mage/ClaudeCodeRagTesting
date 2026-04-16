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


class ThreadWithMessages(ThreadResponse):
    messages: list["MessageResponse"]


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
