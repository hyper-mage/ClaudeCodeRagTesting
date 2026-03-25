import json
from database import get_supabase
from services.embedding_service import get_embeddings


def search_documents(user_id: str, query: str, top_k: int = 5, metadata_filter: dict | None = None) -> list[dict]:
    """Search user's documents for relevant chunks using vector similarity."""
    query_embedding = get_embeddings([query])[0]
    db = get_supabase()
    params = {
        "query_embedding": query_embedding,
        "match_count": top_k,
        "filter_user_id": user_id,
    }
    if metadata_filter:
        # supabase-py passes RPC params as JSON — ensure nested JSONB is serialized
        params["filter_metadata"] = json.dumps(metadata_filter)
    results = db.rpc("match_document_chunks", params).execute()
    return results.data
