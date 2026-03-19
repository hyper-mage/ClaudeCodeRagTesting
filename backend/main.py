from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import threads, chat
from services.tracing import setup_tracing

setup_tracing()

app = FastAPI(title="Agentic RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(threads.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
