from openai import OpenAI
from config import get_settings
from typing import Generator

try:
    from langsmith.wrappers import wrap_openai
except ImportError:
    wrap_openai = None


def get_openai_client() -> OpenAI:
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    if wrap_openai and settings.langsmith_api_key:
        client = wrap_openai(client)
    return client


def create_thread(client: OpenAI) -> str:
    thread = client.beta.threads.create()
    return thread.id


def add_message_to_thread(client: OpenAI, thread_id: str, content: str) -> str:
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content,
    )
    return message.id


def stream_run(client: OpenAI, thread_id: str) -> Generator[str, None, None]:
    """Stream a run on the thread. Yields text deltas."""
    with client.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=_get_or_create_assistant(client),
    ) as stream:
        for event in stream:
            if event.event == "thread.message.delta":
                for block in event.data.delta.content or []:
                    if block.type == "text" and block.text and block.text.value:
                        yield block.text.value


_assistant_id: str | None = None


def _get_or_create_assistant(client: OpenAI) -> str:
    global _assistant_id
    if _assistant_id:
        return _assistant_id

    # Check for existing assistant
    assistants = client.beta.assistants.list(limit=1)
    if assistants.data:
        _assistant_id = assistants.data[0].id
        return _assistant_id

    # Create a new one
    assistant = client.beta.assistants.create(
        name="RAG Masterclass Assistant",
        instructions="You are a helpful assistant. Answer questions clearly and concisely.",
        model="gpt-4o",
    )
    _assistant_id = assistant.id
    return _assistant_id
