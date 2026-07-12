import httpx
import logging
from config import get_settings

logger = logging.getLogger(__name__)


def search_web(query: str) -> dict:
    """Search the web using the configured provider. Returns results with URLs and snippets."""
    settings = get_settings()

    if not settings.web_search_enabled:
        return {"error": "Web search not configured", "results": []}

    if settings.web_search_provider == "tavily":
        return _search_tavily(query, settings)
    else:
        return {"error": f"Unsupported provider: {settings.web_search_provider}", "results": []}


def _search_tavily(query: str, settings) -> dict:
    """Tavily search API — purpose-built for RAG."""
    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {settings.web_search_api_key}"},
            json={
                "query": query,
                "max_results": settings.web_search_max_results,
                "include_answer": True,
                "search_depth": settings.web_search_depth,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            })
        return {
            "answer": data.get("answer", ""),
            "results": results,
        }
    except Exception as e:
        logger.error(f"Tavily search failed: {e}", exc_info=True)
        return {"error": str(e), "results": []}
