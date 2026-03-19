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

    # Frontend vars (read from VITE_ prefix env vars)
    vite_supabase_url: str = ""
    vite_supabase_anon_key: str = ""

    @property
    def supabase_url_resolved(self) -> str:
        return self.supabase_url or self.vite_supabase_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
