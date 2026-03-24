from pydantic import BaseModel
from datetime import datetime


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
    created_at: datetime


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    mime_type: str
    status: str
    error_message: str | None
    chunk_count: int | None
    created_at: datetime
    updated_at: datetime
