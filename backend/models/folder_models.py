"""Pydantic models for folder API request and response payloads."""
from pydantic import BaseModel


class FolderCreate(BaseModel):
    name: str
    parent_id: str | None = None


class FolderRename(BaseModel):
    name: str


class FolderMove(BaseModel):
    new_parent_id: str | None = None  # None = move to user root


class FolderResponse(BaseModel):
    id: str
    name: str
    path: str
    parent_id: str | None
    visibility: str
    created_at: str
    updated_at: str
