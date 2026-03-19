import os
from config import get_settings


def setup_tracing():
    """Configure LangSmith tracing. No-op if LANGSMITH_API_KEY is not set."""
    settings = get_settings()

    if not settings.langsmith_api_key:
        return

    # Set env vars that LangSmith SDK reads
    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
