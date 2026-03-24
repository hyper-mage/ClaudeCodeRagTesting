from database import get_supabase
from services.embedding_service import get_embeddings


def search_documents(user_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Search user's documents for relevant chunks using vector similarity."""
    query_embedding = get_embeddings([query])[0]
    db = get_supabase()
    results = db.rpc("match_document_chunks", {
        "query_embedding": query_embedding,
        "match_count": top_k,
        "filter_user_id": user_id,
    }).execute()
    return results.data
