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
    source_hint: str | None = None,
    scope_hint: dict | None = None,
) -> Generator[dict, None, None]:
    """Stream a chat completion with optional tool definitions.

    Yields dicts:
      {"type": "system_content", "content": "..."} first event with final system prompt
      {"type": "text_delta", "text": "..."} for text chunks
      {"type": "tool_call", "tool_calls": [...]} when model invokes a tool
      {"type": "done"} when streaming is complete

    `source_hint`: "default_kb" | "private" | "both" | None -- appended as routing guidance.
    `scope_hint`:  {"folder_hint": "..."} | {"source_hint": "..."} | None -- narrowing guidance.
    """
    settings = get_settings()
    client = get_llm_client()

    system_content = settings.system_prompt
    if tool_guide:
        system_content += "\n\n" + tool_guide

    # Source routing guidance (D-01, D-02) -- a hint, not a filter (Pitfall 4).
    if source_hint:
        if source_hint == "default_kb":
            system_content += (
                "\n\n## Source Routing\n"
                "Focus on the default Board Games knowledge base. The user is asking "
                "about pre-loaded board game content."
            )
        elif source_hint == "private":
            system_content += (
                "\n\n## Source Routing\n"
                "Focus on the user's private uploaded documents. Use search_documents "
                "and analyze_document for their personal files."
            )
        else:
            system_content += (
                "\n\n## Source Routing\n"
                "Search both the default Board Games KB and the user's private documents. "
                "Cast a wide net."
            )

    # Scope narrowing guidance (D-08, D-09). Source hints on scope are already
    # handled by the source_hint param above; only fold in folder_hint here.
    if scope_hint and "folder_hint" in scope_hint:
        system_content += (
            f"\n\n## Search Scope\n"
            f"The user wants to narrow search to: {scope_hint['folder_hint']}. "
            "When using kb_ls, kb_read, kb_grep, kb_glob, prefer paths containing this scope. "
            "For search_documents, include this as a topic filter."
        )

    # Emit the final system content so the caller can track token budget accurately.
    yield {"type": "system_content", "content": system_content}

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
