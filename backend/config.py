from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv

# Load .env from repo root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    openai_api_key: str = ""
    langsmith_api_key: str = ""
    langchain_tracing_v2: str = "true"
    langchain_project: str = "rag-masterclass"

    # CORS allowlist (comma-separated origins, e.g. "https://app.pages.dev,http://localhost:5173")
    cors_allowed_origins: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ALLOWED_ORIGINS env var into a list.

        Comma-separated, whitespace-stripped. When unset (empty string),
        falls back to ["http://localhost:5173"] so dev-local workflow is unchanged.
        Per D-01, D-02.
        """
        if not self.cors_allowed_origins.strip():
            return ["http://localhost:5173"]
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    # Chat LLM (OpenRouter default, works with any OpenAI-compatible API)
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    system_prompt: str = (
        "You are a helpful assistant with access to tools. Answer questions clearly and concisely. "
        "When using web search results, always cite your sources with URLs. "
        "When showing database query results, format them as markdown tables when appropriate. "
        "When a user asks about a specific document by name (e.g. summarize, extract key points, "
        "or answer detailed questions requiring the whole document), use the analyze_document tool "
        "instead of search_documents."
    )

    # Embeddings (separate provider — not all chat providers support embeddings)
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Search
    search_mode: str = "hybrid"  # "vector_only", "keyword_only", "hybrid"
    search_rrf_k: int = 60  # RRF constant (standard default)
    search_vector_weight: float = 1.0  # weight for vector results in RRF
    search_keyword_weight: float = 1.0  # weight for keyword results in RRF

    # Reranking (optional — disabled by default)
    rerank_enabled: bool = False
    rerank_provider: str = "llm"  # "llm" or "api"
    rerank_base_url: str = ""  # for api provider (Jina, Cohere, etc.)
    rerank_api_key: str = ""
    rerank_model: str = ""
    rerank_top_k: int = 5  # results to keep after reranking

    # Web Search (optional — tool only available when API key is set)
    web_search_provider: str = "tavily"
    web_search_api_key: str = ""
    web_search_max_results: int = 5

    # Sub-agent
    subagent_system_prompt: str = (
        "You are a document analysis specialist. You have been given the full text of a document "
        "and a specific question or task about it. Analyze the document thoroughly and provide "
        "a detailed, well-structured response. Reference specific parts of the document when relevant."
    )
    subagent_max_tokens: int = 4096
    subagent_max_context_chars: int = 100000  # safety limit for document size

    # Explorer sub-agent (Phase 5)
    explorer_system_prompt: str = (
        "You are the KB Explorer -- a specialist sub-agent for deep, multi-step "
        "knowledge-base traversal. You have the KB navigation tools: kb_tree, kb_ls, "
        "kb_glob, kb_grep, kb_read. Start with kb_tree to orient yourself, narrow with "
        "kb_ls/kb_glob, then read only what you need. Return focused, well-cited "
        "evidence as a structured summary. Do NOT return raw tool output. Stop "
        "exploring the moment you have enough to answer."
    )
    explorer_max_iterations: int = 6
    explorer_max_tool_calls: int = 10
    explorer_max_summary_chars: int = 3000
    explorer_timeout: int = 120

    # Token budget management (Phase 6)
    model_context_length: int = 128000  # fallback if OpenRouter lookup fails
    response_reserve_tokens: int = 4096  # reserved for LLM response
    budget_safety_margin: float = 0.05  # 5% safety margin on total budget
    tool_schema_tokens: int = 3000  # estimated tokens for all tool schemas (10 tools)

    # Timeouts (seconds)
    llm_timeout: int = 120  # streaming chat completion
    subagent_timeout: int = 90  # non-streaming subagent calls

    # Text-to-SQL
    sql_max_rows: int = 50  # max rows returned from user queries

    # Frontend vars (read from VITE_ prefix env vars)
    vite_supabase_url: str = ""
    vite_supabase_anon_key: str = ""

    @property
    def supabase_url_resolved(self) -> str:
        return self.supabase_url or self.vite_supabase_url

    @property
    def resolved_llm_api_key(self) -> str:
        return self.llm_api_key or self.openai_api_key

    @property
    def resolved_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.openai_api_key

    @property
    def web_search_enabled(self) -> bool:
        return bool(self.web_search_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
