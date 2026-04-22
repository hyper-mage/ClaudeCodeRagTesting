"""Token budget management, source routing, and scope parsing (Phase 6).

This module is intentionally side-effect free and free of project internals --
it is consumed by the chat event generator (Plan 02) to enforce a context-window
budget and to infer query intent for agent tool routing.

Design notes:
- Token counting uses tiktoken's `cl100k_base` encoding -- a reasonable cross-model
  approximation per D-07. Budget math adds a safety margin to absorb 5-15% variance
  for non-OpenAI models (Claude, Mistral) accessed via OpenRouter.
- Truncation follows D-06 (oldest tool-result pairs first). Pitfall 3 from research
  requires removing the paired (assistant tool_call + tool result) messages
  together; we never leave an orphaned `role=tool` message.
- Source routing (D-01/D-02) is a keyword heuristic -- no LLM call -- and defaults
  to "both" when ambiguous.
- Scope parsing (D-08/D-09) is per-message / stateless.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx
import tiktoken

logger = logging.getLogger(__name__)

# Module-level singleton -- tiktoken encodings are expensive to construct (~100ms)
# and safe to share across threads.
_encoding = tiktoken.get_encoding("cl100k_base")

# Per-message role/separator overhead. Matches OpenAI cookbook recommendation.
_PER_MESSAGE_OVERHEAD = 4
_REPLY_PRIMING = 2


# =============================================================================
# Token counting
# =============================================================================
def count_tokens(text: str) -> int:
    """Count tokens in a plain string using cl100k_base.

    Returns 0 for empty/None input.
    """
    if not text:
        return 0
    return len(_encoding.encode(text))


def count_message_tokens(messages: list[dict]) -> int:
    """Count tokens for a list of chat messages.

    Accounts for:
      - `_PER_MESSAGE_OVERHEAD` tokens per message (role/separators)
      - message `content` tokens
      - serialized `tool_calls` tokens (assistant messages with tool_calls)
      - `_REPLY_PRIMING` tokens added once at the end for reply priming

    An empty list returns just the reply priming tokens.
    """
    total = 0
    for msg in messages:
        total += _PER_MESSAGE_OVERHEAD
        content = msg.get("content") or ""
        if content:
            total += count_tokens(content)
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            try:
                total += count_tokens(json.dumps(tool_calls, default=str))
            except (TypeError, ValueError):
                # Fall back to repr so malformed tool_calls don't crash the budget.
                total += count_tokens(repr(tool_calls))
    total += _REPLY_PRIMING
    return total


# =============================================================================
# Model context length lookup
# =============================================================================
def fetch_model_context_length(model_id: str, api_key: str) -> Optional[int]:
    """Query OpenRouter `/api/v1/models` for a model's context_length.

    Returns None on any failure (network error, model not found, API error).
    Callers should fall back to `settings.model_context_length` when None.
    """
    try:
        resp = httpx.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        for model in data:
            if model.get("id") == model_id:
                ctx = model.get("context_length")
                if isinstance(ctx, int) and ctx > 0:
                    return ctx
                return None
        return None
    except Exception as e:
        logger.warning(f"fetch_model_context_length failed for {model_id}: {e}")
        return None


# =============================================================================
# TokenBudget
# =============================================================================
def _is_tool_call_assistant(msg: dict) -> bool:
    return msg.get("role") == "assistant" and bool(msg.get("tool_calls"))


def _is_tool_result(msg: dict) -> bool:
    return msg.get("role") == "tool"


def _is_plain_history(msg: dict) -> bool:
    """True for chat-history messages that are NOT part of a tool-call exchange."""
    role = msg.get("role")
    if role == "user":
        return True
    if role == "assistant" and not msg.get("tool_calls"):
        return True
    return False


class TokenBudget:
    """Track token usage across system prompt, chat history, and tool-result pairs.

    Categories tracked separately so truncation can preferentially drop oldest
    tool-result pairs (D-06) while preserving system prompt and chat history.

    Usage:
        budget = TokenBudget(
            context_length=settings.model_context_length,
            response_reserve=settings.response_reserve_tokens,
            safety_margin=settings.budget_safety_margin,
            tool_schema_tokens=settings.tool_schema_tokens,
        )
        budget.set_system(system_prompt)
        budget.set_history(chat_history_messages)
        budget.add_tool_result_pair(assistant_msg, tool_msg)  # per tool round-trip
        if budget.is_over():
            messages = budget.truncate_oldest_tool_results(messages)
    """

    def __init__(
        self,
        context_length: int,
        response_reserve: int = 4096,
        safety_margin: float = 0.05,
        tool_schema_tokens: int = 0,
    ):
        self.context_length = context_length
        self.response_reserve = response_reserve
        self.safety_margin = safety_margin
        self.tool_schema_tokens = tool_schema_tokens

        self._system_tokens = 0
        self._history_tokens = 0
        # List of (pair_id, assistant_tokens, tool_tokens, assistant_call_ids)
        self._tool_result_pairs: list[tuple[int, int, int, list[str]]] = []
        self._pair_counter = 0

    # ---- Properties ----
    @property
    def available(self) -> int:
        """Total tokens we can safely consume, after margin/reserve/tool schemas."""
        usable = int(self.context_length * (1.0 - self.safety_margin))
        return usable - self.response_reserve - self.tool_schema_tokens

    @property
    def used(self) -> int:
        pairs_total = sum(a + t for _, a, t, _ in self._tool_result_pairs)
        return self._system_tokens + self._history_tokens + pairs_total

    @property
    def remaining(self) -> int:
        return self.available - self.used

    def is_over(self) -> bool:
        return self.used > self.available

    # ---- Mutators ----
    def set_system(self, content: str) -> None:
        self._system_tokens = count_tokens(content or "")

    def set_history(self, messages: list[dict]) -> None:
        """Count only plain chat-history messages (user / assistant without tool_calls).

        Tool-call assistant messages and tool results are tracked separately via
        `add_tool_result_pair` so they can be truncated independently.
        """
        history_only = [m for m in messages if _is_plain_history(m)]
        self._history_tokens = count_message_tokens(history_only)

    def add_tool_result_pair(self, assistant_msg: dict, tool_msg: dict) -> None:
        """Record a tool-call round-trip (assistant with tool_calls + tool result).

        We track the call ids on the assistant message so `truncate_oldest_tool_results`
        can remove the matching pair from a messages list without ambiguity.
        """
        a_tokens = count_message_tokens([assistant_msg])
        t_tokens = count_message_tokens([tool_msg])
        call_ids = [
            tc.get("id")
            for tc in (assistant_msg.get("tool_calls") or [])
            if tc.get("id")
        ]
        self._tool_result_pairs.append((self._pair_counter, a_tokens, t_tokens, call_ids))
        self._pair_counter += 1

    def truncate_oldest_tool_results(self, messages: list[dict]) -> list[dict]:
        """Remove the oldest tool-result pair from both the budget and `messages`.

        Per Pitfall 3 (research): we must remove the paired assistant+tool messages
        together. We match on the `tool_call_id` on the tool message against the
        assistant's recorded call ids. Chat history messages are never removed here.

        Returns the filtered messages list (also mutates budget state).
        """
        if not self._tool_result_pairs:
            return list(messages)

        _, _, _, call_ids = self._tool_result_pairs.pop(0)
        if not call_ids:
            return list(messages)

        # Remove the assistant message whose tool_calls contain ANY of these ids,
        # and any tool-role message whose tool_call_id is in this set.
        call_id_set = set(call_ids)
        new_messages: list[dict] = []
        for m in messages:
            if _is_tool_call_assistant(m):
                m_call_ids = {tc.get("id") for tc in (m.get("tool_calls") or [])}
                if m_call_ids & call_id_set:
                    continue  # drop the assistant tool-call message
            if _is_tool_result(m) and m.get("tool_call_id") in call_id_set:
                continue  # drop the paired tool result
            new_messages.append(m)
        return new_messages


# =============================================================================
# Source routing (D-01, D-02)
# =============================================================================
_PRIVATE_SIGNALS = (
    "my document",
    "my documents",
    "my upload",
    "my uploads",
    "uploaded",
    "my file",
    "my files",
    "my notes",
    "my collection",
    "my pdf",
)

# A rough set of board game references that suggest the default KB.
_DEFAULT_KB_SIGNALS = (
    "catan",
    "monopoly",
    "chess",
    "risk",
    "ticket to ride",
    "pandemic",
    "scrabble",
    "clue",
    "settlers",
    "board game",
    "board games",
    "game of",
    "rules of",
)


def infer_source_scope(user_message: str, has_private_docs: bool) -> str:
    """Classify a user message into "default_kb" | "private" | "both".

    Per D-01 (invisible routing) and D-02 (default to both when ambiguous):

    - If the user has no private docs, we always return "default_kb".
    - If private-only signals are present AND no default-KB signals, return "private".
    - If mixed signals (private + default-KB mentions), return "both".
    - Otherwise return "both" when the user has private docs, else "default_kb".

    This is a keyword heuristic and is consumed as a HINT, not a hard filter --
    the LLM still has access to all tools. See Pitfall 4.
    """
    if not user_message:
        return "default_kb" if not has_private_docs else "both"

    if not has_private_docs:
        return "default_kb"

    msg_lower = user_message.lower()
    has_private_signal = any(sig in msg_lower for sig in _PRIVATE_SIGNALS)
    has_default_signal = any(sig in msg_lower for sig in _DEFAULT_KB_SIGNALS)

    if has_private_signal and not has_default_signal:
        return "private"
    if has_private_signal and has_default_signal:
        return "both"
    return "both"


# =============================================================================
# Scope parsing (D-08, D-09)
# =============================================================================
# Stateless: every message is re-evaluated -- no persistence across turns.
_SOURCE_HINT_PRIVATE = ("my uploads", "my documents", "my files", "my collection")
_SOURCE_HINT_DEFAULT = ("default kb", "default knowledge base", "board games only")

_SCOPE_PATTERNS = [
    re.compile(r"only\s+search\s+([^\n.,?!]+)", re.IGNORECASE),
    re.compile(r"search\s+in\s+([^\n.,?!]+)", re.IGNORECASE),
    re.compile(r"look\s+in\s+([^\n.,?!]+)", re.IGNORECASE),
    re.compile(r"just\s+(?:in\s+)?([^\n.,?!]+)", re.IGNORECASE),
    re.compile(r"search\s+([A-Z][^\n.,?!]*/[^\n.,?!]*)", re.IGNORECASE),
]


def _clean_hint(raw: str) -> str:
    """Trim trailing filler words like 'only' / 'please' from an extracted hint."""
    cleaned = raw.strip().rstrip("/").strip()
    trailing_fillers = ("only", "please", "folder", "directory")
    changed = True
    while changed:
        changed = False
        for filler in trailing_fillers:
            lowered = cleaned.lower()
            if lowered.endswith(" " + filler):
                cleaned = cleaned[: -(len(filler) + 1)].rstrip()
                changed = True
    return cleaned


def parse_scope_hint(user_message: str) -> dict:
    """Parse natural-language scope narrowing from a user message.

    Returns:
        {"source_hint": "private"}   -- user said "my uploads"/"my documents"/etc.
        {"source_hint": "default_kb"} -- user said "default kb"/"board games only"
        {"folder_hint": "<name>"}    -- user said "only search X" / "look in X"
                                        / gave a folder path like "Board Games/Catan/"
        {}                           -- no scope hint detected

    Source and folder hints are mutually exclusive in the return shape -- source
    hints win when both are present because they are more explicit. Per D-09, no
    state is persisted; callers must re-run this on every turn.
    """
    if not user_message:
        return {}

    msg_lower = user_message.lower()

    # Source hints first -- they are the most explicit.
    if any(sig in msg_lower for sig in _SOURCE_HINT_PRIVATE):
        return {"source_hint": "private"}
    if any(sig in msg_lower for sig in _SOURCE_HINT_DEFAULT):
        return {"source_hint": "default_kb"}

    # Folder-path style: anything containing "/".
    path_match = re.search(r"([A-Za-z][A-Za-z0-9 _-]*/[A-Za-z0-9 _/-]*)", user_message)
    if path_match:
        folder = _clean_hint(path_match.group(1))
        if folder:
            return {"folder_hint": folder}

    # "only search X" / "look in X" / "search in X" / "just X"
    for pattern in _SCOPE_PATTERNS:
        match = pattern.search(user_message)
        if match:
            hint = _clean_hint(match.group(1))
            if hint:
                return {"folder_hint": hint}

    return {}
