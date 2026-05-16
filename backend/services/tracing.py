import os
from config import get_settings


def setup_tracing():
    """Configure LangSmith tracing. No-op if LANGSMITH_API_KEY is not set.

    Project name resolution (highest to lowest precedence):
      1. LANGSMITH_PROJECT env var (canonical name per langsmith SDK 0.3.42+)
      2. LANGCHAIN_PROJECT env var (legacy name, still respected by SDK)
      3. settings.langsmith_project (pydantic-settings default)
    """
    settings = get_settings()

    if not settings.langsmith_api_key:
        return

    # Determine project name from highest-precedence source.
    project = (
        os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or settings.langsmith_project
    )

    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = project
    # Also set canonical name for SDK's own env-var walker.
    os.environ["LANGSMITH_PROJECT"] = project
