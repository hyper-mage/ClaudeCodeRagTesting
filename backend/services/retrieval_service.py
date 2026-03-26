import json
import logging
from database import get_supabase
from config import get_settings
from services.embedding_service import get_embeddings
from services.rerank_service import rerank

logger = logging.getLogger(__name__)


def vector_search(user_id: str, query: str, top_k: int, metadata_filter: dict | None = None) -> list[dict]:
    """Vector similarity search via match_document_chunks RPC."""
    query_embedding = get_embeddings([query])[0]
    db = get_supabase()
    params = {
        "query_embedding": query_embedding,
        "match_count": top_k,
        "filter_user_id": user_id,
    }
    if metadata_filter:
        params["filter_metadata"] = json.dumps(metadata_filter)
    results = db.rpc("match_document_chunks", params).execute()
    return results.data


def keyword_search(user_id: str, query: str, top_k: int, metadata_filter: dict | None = None) -> list[dict]:
    """Full-text keyword search via keyword_search_chunks RPC."""
    db = get_supabase()
    params = {
        "search_query": query,
        "match_count": top_k,
        "filter_user_id": user_id,
    }
    if metadata_filter:
        params["filter_metadata"] = json.dumps(metadata_filter)
    results = db.rpc("keyword_search_chunks", params).execute()
    return results.data


def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    weights: list[float],
    k: int = 60,
) -> list[dict]:
    """Combine multiple ranked result lists using weighted RRF.

    For each document across all lists:
      rrf_score = sum(weight_i / (k + rank_i)) for each list where it appears.
    Documents appearing in multiple lists get boosted scores.
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for result_list, weight in zip(result_lists, weights):
        for rank, doc in enumerate(result_list):
            doc_id = doc["id"]
            rrf_score = weight / (k + rank + 1)  # rank is 0-indexed, +1 for 1-based
            scores[doc_id] = scores.get(doc_id, 0.0) + rrf_score
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    results = []
    for doc_id in sorted_ids:
        doc = doc_map[doc_id].copy()
        doc["rrf_score"] = scores[doc_id]
        results.append(doc)

    return results


def search_documents(
    user_id: str, query: str, top_k: int = 5, metadata_filter: dict | None = None
) -> list[dict]:
    """Search user's documents using configured search mode (vector, keyword, or hybrid).

    Pipeline: search -> RRF fusion (if hybrid) -> rerank (if enabled) -> top_k
    """
    settings = get_settings()
    mode = settings.search_mode

    # Fetch more candidates than final top_k for fusion/reranking
    candidate_k = max(top_k * 4, 20)

    if mode == "vector_only":
        results = vector_search(user_id, query, candidate_k, metadata_filter)
    elif mode == "keyword_only":
        results = keyword_search(user_id, query, candidate_k, metadata_filter)
    elif mode == "hybrid":
        vector_results = vector_search(user_id, query, candidate_k, metadata_filter)
        keyword_results = keyword_search(user_id, query, candidate_k, metadata_filter)
        results = reciprocal_rank_fusion(
            [vector_results, keyword_results],
            [settings.search_vector_weight, settings.search_keyword_weight],
            k=settings.search_rrf_k,
        )
        logger.info(
            f"Hybrid search: {len(vector_results)} vector + {len(keyword_results)} keyword "
            f"-> {len(results)} fused candidates"
        )
    else:
        logger.warning(f"Unknown search_mode '{mode}', falling back to vector_only")
        results = vector_search(user_id, query, candidate_k, metadata_filter)

    # Optional reranking
    results = rerank(query, results)

    # Final top_k trim
    return results[:top_k]
