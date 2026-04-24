from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import threads, chat, documents, folders
from services.tracing import setup_tracing
from config import get_settings

setup_tracing()

settings = get_settings()

app = FastAPI(title="Agentic RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(threads.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(folders.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
