from openai import OpenAI
from config import get_settings
from typing import Generator

try:
    from langsmith.wrappers import wrap_openai
except ImportError:
    wrap_openai = None


def get_llm_client() -> OpenAI:
    """Create OpenAI-compatible client for chat completions."""
    settings = get_settings()
    client = OpenAI(
        api_key=settings.resolved_llm_api_key,
        base_url=settings.llm_base_url,
    )
    if wrap_openai and settings.langsmith_api_key:
        client = wrap_openai(client)
    return client


def get_embedding_client() -> OpenAI:
    """Create OpenAI client for embeddings (may use different provider than chat)."""
    settings = get_settings()
    client = OpenAI(
        api_key=settings.resolved_embedding_api_key,
        base_url=settings.embedding_base_url,
    )
    if wrap_openai and settings.langsmith_api_key:
        client = wrap_openai(client)
    return client


def stream_chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_guide: str | None = None,
) -> Generator[dict, None, None]:
    """Stream a chat completion with optional tool definitions.

    Yields dicts:
      {"type": "text_delta", "text": "..."} for text chunks
      {"type": "tool_call", "tool_calls": [...]} when model invokes a tool
      {"type": "done"} when streaming is complete
    """
    settings = get_settings()
    client = get_llm_client()

    system_content = settings.system_prompt
    if tool_guide:
        system_content += "\n\n" + tool_guide

    # Prepend system prompt
    full_messages = [
        {"role": "system", "content": system_content},
        *messages,
    ]

    kwargs = {
        "model": settings.llm_model,
        "messages": full_messages,
        "stream": True,
    }
    if tools:
        kwargs["tools"] = tools

    stream = client.chat.completions.create(**kwargs, timeout=settings.llm_timeout)

    # Accumulate tool calls across chunks
    tool_calls_acc: dict[int, dict] = {}

    for chunk in stream:
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            continue

        delta = choice.delta

        # Text content
        if delta.content:
            yield {"type": "text_delta", "text": delta.content}

        # Tool call deltas
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {
                        "id": tc.id or "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                if tc.id:
                    tool_calls_acc[idx]["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        tool_calls_acc[idx]["function"]["name"] = tc.function.name
                    if tc.function.arguments:
                        tool_calls_acc[idx]["function"]["arguments"] += tc.function.arguments

        # Check for finish
        if choice.finish_reason == "tool_calls":
            yield {
                "type": "tool_call",
                "tool_calls": list(tool_calls_acc.values()),
            }
            return

    yield {"type": "done"}
