import json
import logging
import httpx
from config import get_settings
from services.llm_service import get_llm_client

logger = logging.getLogger(__name__)

RERANK_PROMPT = """You are a relevance scorer. Given a search query and a document passage, rate how relevant the passage is to answering the query.

Score from 0.0 to 1.0 where:
- 0.0 = completely irrelevant
- 0.5 = somewhat relevant, tangentially related
- 1.0 = directly answers or is highly relevant to the query

Respond with ONLY a JSON object: {"score": <float>}"""


def rerank_with_llm(
    query: str,
    documents: list[dict],
    api_key: str | None = None,
    model: str | None = None,
    trace: bool = True,
) -> list[dict]:
    """Score each document's relevance to the query using the chat LLM.

    `api_key`/`model`/`trace`: per-request resolution (D-01/SEC-04). The aux model
    defaults to the single resolved turn `model` (D-02 — no distinct aux param);
    both fall through to owner `settings` when None.
    """
    settings = get_settings()
    client = get_llm_client(api_key=api_key, trace=trace)
    scored = []

    for doc in documents:
        try:
            response = client.chat.completions.create(
                model=model or settings.llm_model,
                messages=[
                    {"role": "system", "content": RERANK_PROMPT},
                    {"role": "user", "content": f"Query: {query}\n\nPassage: {doc['content'][:2000]}"},
                ],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            doc["rerank_score"] = float(data.get("score", 0.0))
        except Exception as e:
            logger.warning(f"LLM rerank failed for chunk {doc.get('id')}: {e}")
            doc["rerank_score"] = 0.0
        scored.append(doc)

    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored[:settings.rerank_top_k]


def rerank_with_api(query: str, documents: list[dict]) -> list[dict]:
    """Rerank using a dedicated rerank API (Jina, Cohere, etc.)."""
    settings = get_settings()
    response = httpx.post(
        f"{settings.rerank_base_url}/rerank",
        headers={
            "Authorization": f"Bearer {settings.rerank_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.rerank_model,
            "query": query,
            "documents": [doc["content"][:2000] for doc in documents],
            "top_n": settings.rerank_top_k,
        },
        timeout=30,
    )
    response.raise_for_status()
    results = response.json()["results"]

    scored = []
    for result in results:
        idx = result["index"]
        doc = documents[idx].copy()
        doc["rerank_score"] = result["relevance_score"]
        scored.append(doc)

    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored


def rerank(
    query: str,
    documents: list[dict],
    api_key: str | None = None,
    model: str | None = None,
    trace: bool = True,
) -> list[dict]:
    """Rerank documents using configured provider. Returns top-k reranked results.
    No-ops when reranking is disabled.

    `api_key`/`model`/`trace` forward only to the LLM provider (`rerank_with_llm`);
    the dedicated rerank-API provider (`rerank_with_api`) uses its own key and is
    intentionally left untouched (D-01)."""
    settings = get_settings()

    if not settings.rerank_enabled or not documents:
        return documents

    if settings.rerank_provider == "llm":
        return rerank_with_llm(query, documents, api_key=api_key, model=model, trace=trace)
    elif settings.rerank_provider == "api":
        return rerank_with_api(query, documents)
    else:
        logger.warning(f"Unknown rerank provider: {settings.rerank_provider}, skipping rerank")
        return documents
