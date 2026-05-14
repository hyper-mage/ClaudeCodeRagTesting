from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from routers import threads, chat, documents, folders
from services.tracing import setup_tracing
from config import get_settings
from limiter import limiter

setup_tracing()

settings = get_settings()

app = FastAPI(title="Agentic RAG API")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom 429 handler returning the D-06 JSON contract.

    slowapi's default handler returns plaintext (RESEARCH Pitfall 2);
    this override returns JSON + Retry-After header so frontend (Phase 8 PORT-02)
    can parse it with .json() and surface a graceful UI error.

    Window-seconds extraction: slowapi 0.1.9 exposes the `limits` library
    Granularity namedtuple at exc.limit.limit.GRANULARITY.seconds. If the
    attribute path proves brittle (RESEARCH Open Question 3), fallback to 60s
    — correct for the locked "20/minute" default and an acceptable safety
    floor for shorter windows.
    """
    try:
        retry_after = int(exc.limit.limit.GRANULARITY.seconds)
    except AttributeError:
        retry_after = 60
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limited",
            "detail": "Too many chat requests — slow down.",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


app.add_middleware(SlowAPIMiddleware)  # SEC-04: required for slowapi to enforce decorator-based limits in prod (Pitfall 1)

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
