import httpx
from config import get_settings


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts using configured embedding provider.
    Uses raw HTTP to avoid OpenAI SDK parsing issues with some providers."""
    settings = get_settings()
    response = httpx.post(
        f"{settings.embedding_base_url}/embeddings",
        headers={
            "Authorization": f"Bearer {settings.resolved_embedding_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.embedding_model,
            "input": texts,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return [item["embedding"] for item in data["data"]]
