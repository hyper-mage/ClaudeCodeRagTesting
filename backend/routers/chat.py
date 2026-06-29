import json
import logging
import openai
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse
from auth import get_user_id
from limiter import limiter

logger = logging.getLogger(__name__)
from database import get_supabase
from config import get_settings
from models.schemas import MessageCreate
from services.llm_service import stream_chat_completion
from services.sql_service import get_queryable_schema, execute_sql
from services.web_search_service import search_web
from services.kb_tools_service import kb_ls, kb_tree, kb_read, kb_grep, kb_glob
from services.crypto_service import decrypt_key
from services.log_scrub import scrub_secrets
from services.budget_service import (
    TokenBudget,
    infer_source_scope,
    parse_scope_hint,
    fetch_model_context_length,
)


# --- SEC-01 log scrub filter (closes the exc_info traceback leak path) -------
# A message-string scrub at the call site alone is INSUFFICIENT: a decrypted
# `sk-or-…` key sitting in a stack-frame local of an `exc_info=True` traceback
# still reaches the log sink (RESEARCH Open Q2 / Pitfall 2). This filter scrubs
# the FORMATTED record — both `record.getMessage()` AND the exc_info traceback
# (rendered into `record.exc_text`, with `exc_info` cleared so the sink never
# re-formats the raw traceback / stack-frame locals).
class _ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # (a) Scrub the rendered message; rewrite msg + clear args so the sink
        #     cannot re-interpolate an un-scrubbed value.
        try:
            scrubbed_msg = scrub_secrets(record.getMessage())
        except Exception:
            scrubbed_msg = scrub_secrets(str(record.msg))
        record.msg = scrubbed_msg
        record.args = None
        # (b) Scrub the exc_info traceback (where a stack-frame local key hides),
        #     render it into exc_text, and clear exc_info so the handler renders
        #     the scrubbed text instead of re-formatting the raw exception.
        if record.exc_info:
            try:
                formatted = logging.Formatter().formatException(record.exc_info)
            except Exception:
                formatted = ""
            record.exc_text = scrub_secrets(formatted)
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = scrub_secrets(record.exc_text)
        return True


def _install_scrub_filter() -> None:
    """Install _ScrubFilter where it actually SEES routers.chat records.

    chat.py logs via getLogger(__name__) == 'routers.chat' (NOT a descendant of
    'backend'; logger filters are NOT inherited across the hierarchy). HANDLER
    filters DO run on records propagated up to the root, so attach to the ROOT
    logger's handler(s); ALSO attach directly to the 'routers.chat' logger as a
    belt for the no-root-handler case. Do NOT attach only to getLogger('backend').
    """
    root = logging.getLogger()
    for _h in root.handlers:
        if not any(isinstance(f, _ScrubFilter) for f in _h.filters):
            _h.addFilter(_ScrubFilter())
    chat_logger = logging.getLogger("routers.chat")
    if not any(isinstance(f, _ScrubFilter) for f in chat_logger.filters):
        chat_logger.addFilter(_ScrubFilter())


_install_scrub_filter()


def _sse_error(code: str, detail: str) -> dict:
    """Build a structured SSE error event (D-12 / Example 1).

    `detail` is FIXED copy (no str(e)) on known paths; scrub anyway as
    defense-in-depth so no `sk-or-…` value can ever ride the payload.
    """
    return {
        "event": "error",
        "data": json.dumps({"error": code, "detail": scrub_secrets(detail)}),
    }

def _mark_error_row(db, assistant_msg_id) -> None:
    """Best-effort: stamp the orphan assistant placeholder with an error notice.

    Mirrors the prior inline cleanup so every error branch (429/402/upstream/
    generic) leaves the same recoverable row. Swallows its own failures.
    """
    if not assistant_msg_id:
        return
    try:
        db.table("messages").update({
            "content": "[An error occurred while generating the response]",
        }).eq("id", assistant_msg_id).execute()
    except Exception:
        pass  # Best-effort cleanup

def _accumulate_usage(turn_usage: dict, event_usage: dict) -> None:
    """Sum an OpenRouter usage dict into the running turn accumulator (D-08 / A4).

    Summed across EVERY tool-loop iteration of the turn. `cost` is the
    authoritative field; token sub-fields are tolerated when absent. The
    reported numbers are persisted as-is — never recomputed client/locally.
    """
    if not event_usage:
        return
    for field in ("prompt_tokens", "completion_tokens", "total_tokens", "cost"):
        val = event_usage.get(field)
        if val is None:
            continue
        turn_usage[field] = turn_usage.get(field, 0) + val


def _safe_thread_model(thread_row: dict | None) -> str | None:
    """Read thread.model off the EXISTING SELECT * row (D-03 / Pattern 2).

    The `model` column does not exist until P13 — reading it off the already-
    fetched row is an absent-KEY read (None), NOT a DB query (no 42703).
    """
    return thread_row.get("model") if thread_row else None


def _safe_user_default_model(db, user_id: str) -> str | None:
    """Read user_preferences.default_model, tolerating the absent P13 table.

    The user_preferences table does not exist until P13 → the query raises
    (PostgREST APIError, Postgres 42P01 relation-does-not-exist). Swallow it and
    fall through to the next model tier (D-03). ZERO P13 schema created here.
    """
    try:
        r = (
            db.table("user_preferences")
            .select("default_model")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return r.data.get("default_model") if r and r.data else None
    except Exception as e:  # APIError 42P01 (relation does not exist) pre-P13
        logger.debug(f"user_preferences not available (pre-P13): {scrub_secrets(str(e))}")
        return None


def _resolve_key_and_model(
    db, user_id: str, thread_row: dict | None, body
) -> tuple[str | None, str, str, bool]:
    """Resolve the per-request (api_key, model, mode, is_user_key) — SEC-04/DEMO-03/D-03.

    Module-level (NOT a Settings method) and NOT @lru_cache'd (Pitfall 8: a cache
    would bleed one user's key/model into another's turn). Called once per turn.

    MODEL — three-tier, each tier tolerant of the absent P13 schema (D-03):
        body.model? → thread_row.model? → user_preferences.default_model?
                    → settings.llm_model (owner default — always present)

    KEY — fail-closed three-branch (NEVER a fail-open one-liner):
        if a user_api_keys row exists → decrypt in-memory → ("user", is_user_key=True)
        elif settings.demo_fallback_enabled → owner key + free demo model → ("demo", False)
        else → (None, model, "no_key", False) ; caller refuses with a structured error.
    """
    settings = get_settings()

    # MODEL tier — fall through on absent P13 schema (D-03).
    model = (
        getattr(body, "model", None)              # optional per-message override (future)
        or _safe_thread_model(thread_row)         # thread.model — column may not exist yet
        or _safe_user_default_model(db, user_id)  # user_preferences.default_model — table may not exist
        or settings.llm_model                     # owner default — always present
    )

    # KEY tier — fail-closed three-branch. Read the user's stored key via the
    # service-role client using the empty-row guard from keys.py:79-88.
    row = (
        db.table("user_api_keys")
        .select("encrypted_key")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    # Empty-row guard (keys.py:79-88). maybe_single() returns a dict-or-None .data;
    # defensively require a dict (a list/None means "no key row" → fall through).
    if row and isinstance(row.data, dict) and row.data.get("encrypted_key"):
        # Decrypt in-memory, this turn only. The plaintext is a short-lived local —
        # never stashed in a closure that outlives the turn, never returned to the FE.
        api_key = decrypt_key(row.data["encrypted_key"])
        return api_key, model, "user", True

    if settings.demo_fallback_enabled:
        # Owner-key fallback is PINNED to a free model (D-06): the cost bound comes
        # from the MODEL, not from who's eligible (D-05).
        return (
            settings.resolved_llm_api_key,
            settings.demo_fallback_model or model,
            "demo",
            False,
        )

    # Fail-closed refusal (DEMO-03): NO key, NO LLM call — caller yields no_api_key.
    return None, model, "no_key", False

try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f

router = APIRouter(prefix="/api/threads", tags=["chat"])


# SEC-05 cap-hit graceful notice — markdown-italic so chat UI styles it as a meta-note.
# Per Phase 6 D-10 (verbatim wording from CONTEXT.md).
CAP_HIT_NOTICE = (
    "\n\n_I hit the tool-call limit ({n}) before finishing this answer. "
    "Try narrowing the question or breaking it into steps._"
)


RETRIEVAL_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Search the user's uploaded documents for relevant information. "
            "Optionally filter by document_type or topic to narrow results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "document_type": {
                    "type": "string",
                    "enum": [
                        "technical_documentation",
                        "meeting_notes",
                        "research_paper",
                        "tutorial",
                        "email",
                        "general",
                    ],
                    "description": "Filter by document type, e.g. 'tutorial' or 'meeting_notes'",
                },
                "topic": {
                    "type": "string",
                    "description": "Filter by document topic",
                },
            },
            "required": ["query"],
        },
    },
}

SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "query_database",
        "description": (
            "Query the user's structured data using SQL. Use this for questions about "
            "their conversation history, document metadata, upload statistics, or any "
            "question that requires counting, filtering, or aggregating structured data. "
            "Always use standard PostgreSQL syntax. Only SELECT queries are allowed.\n\n"
            "SCHEMA:\n" + get_queryable_schema()
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": (
                        "A PostgreSQL SELECT query. RLS automatically filters to the "
                        "current user's data — do NOT add user_id filters."
                    ),
                },
            },
            "required": ["sql"],
        },
    },
}

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use this when the user's uploaded "
            "documents don't contain the answer, or when the question is about recent "
            "events, external facts, or topics not covered by the user's documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — be specific and concise",
                },
            },
            "required": ["query"],
        },
    },
}

ANALYZE_DOCUMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "analyze_document",
        "description": (
            "Analyze an entire uploaded document in depth. Use this when the user asks "
            "about a specific document by name - for example, to summarize it, extract "
            "key points, compare sections, or answer detailed questions that require "
            "reading the whole document rather than searching for specific passages."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "document_name": {
                    "type": "string",
                    "description": "The filename of the document to analyze (e.g. 'report.pdf')",
                },
                "query": {
                    "type": "string",
                    "description": "What to analyze or answer about the document",
                },
            },
            "required": ["document_name", "query"],
        },
    },
}


KB_LS_TOOL = {
    "type": "function",
    "function": {
        "name": "kb_ls",
        "description": (
            "List files and subfolders in a knowledge base folder. "
            "Use this to see what's inside a specific folder."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": 'Folder path, e.g. "Board Games/Catan/" or "My Documents/"',
                },
            },
            "required": ["path"],
        },
    },
}

KB_TREE_TOOL = {
    "type": "function",
    "function": {
        "name": "kb_tree",
        "description": (
            "Show the hierarchical tree structure of the knowledge base. "
            "Use this first to understand the overall KB layout before diving into specific folders."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": 'Root path for tree view. Empty string or "/" shows entire KB.',
                    "default": "",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many levels deep to show. Default 2.",
                    "default": 2,
                },
            },
            "required": [],
        },
    },
}

KB_READ_TOOL = {
    "type": "function",
    "function": {
        "name": "kb_read",
        "description": (
            "Read the full content of a document in the knowledge base. "
            "Use this to get the actual text of a specific file. "
            "Supports optional line range for partial reads."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": 'Document path, e.g. "Board Games/Catan/rules.md"',
                },
                "lines": {
                    "type": "string",
                    "description": 'Optional line range, e.g. "1-50" or "100-200". Omit to read entire document.',
                },
            },
            "required": ["path"],
        },
    },
}

KB_GREP_TOOL = {
    "type": "function",
    "function": {
        "name": "kb_grep",
        "description": (
            "Search document content for specific text patterns. "
            "Use 'keyword' mode for natural language terms (full-text search) "
            "or 'regex' mode for exact pattern matching (POSIX regex). "
            "Returns matched lines with surrounding context and file paths."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern -- a word/phrase for keyword mode, or a POSIX regex for regex mode",
                },
                "mode": {
                    "type": "string",
                    "enum": ["keyword", "regex"],
                    "description": "Search mode: 'keyword' for full-text search, 'regex' for pattern matching. Default: keyword.",
                    "default": "keyword",
                },
                "path": {
                    "type": "string",
                    "description": 'Optional folder path to scope search, e.g. "Board Games/Catan/"',
                },
            },
            "required": ["pattern"],
        },
    },
}

KB_GLOB_TOOL = {
    "type": "function",
    "function": {
        "name": "kb_glob",
        "description": (
            "Find files matching a glob pattern across the knowledge base. "
            "Use * for any characters, ? for single character. "
            "Example: 'Board Games/*/rules.md' finds all game rule files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": 'Glob pattern, e.g. "Board Games/*/rules.md" or "*.md"',
                },
            },
            "required": ["pattern"],
        },
    },
}

EXPLORE_KB_TOOL = {
    "type": "function",
    "function": {
        "name": "explore_kb",
        "description": (
            "Spawn an explorer sub-agent for complex, multi-step exploration of the knowledge base. "
            "Use when a single tool call cannot answer the question -- for example: "
            "(1) summarizing an entire folder's contents, "
            "(2) finding cross-references across multiple games, "
            "(3) recommending games similar to one mentioned by the user. "
            "DO NOT use for simple lookups -- kb_ls, kb_read, kb_grep are faster. "
            "When using mode='find_similar', resolve the seed game in `query` first "
            "(e.g. 'Find games similar to Catan. Focus on trading and resource management.')."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["deep_search", "summarize", "find_similar"],
                    "description": (
                        "deep_search: multi-step search across the KB. "
                        "summarize: produce a synthesis of a folder's contents. "
                        "find_similar: find games with mechanics similar to a given game."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": "The question or task for the explorer. Be specific; include any folder paths or game names.",
                },
            },
            "required": ["mode", "query"],
        },
    },
}

TOOL_SELECTION_GUIDE = """## Tool Selection Guide

**Orientation** -- Understand KB structure first:
- kb_tree: See the folder hierarchy (start here for new topics)
- kb_ls: List contents of a specific folder

**Find files** -- Locate documents by name or pattern:
- kb_glob: Match file patterns (e.g., "Board Games/*/rules.md")
- kb_ls: Browse a known folder

**Find content** -- Search inside documents:
- kb_grep: Exact text or regex patterns across all documents
- search_documents: Semantic similarity search (meaning-based)

**Read content** -- Get document text:
- kb_read: Raw document text (full or line range)
- analyze_document: LLM-powered deep analysis of a document

**External** -- Information outside the KB:
- web_search: Current web information
- query_database: Metadata, stats, conversation history (SQL)

**Deep exploration** -- Multi-step KB traversal (use sparingly):
- explore_kb (mode='summarize'): coherent synthesis of a folder's contents
- explore_kb (mode='find_similar'): cross-reference games with similar mechanics (resolve seed game in the query)
- explore_kb (mode='deep_search'): broad multi-step search when one tool isn't enough

Always start with kb_tree or kb_ls to orient yourself before reading or searching."""


_SCOPED_TOOLS = (
    "search_documents",
    "kb_ls",
    "kb_tree",
    "kb_read",
    "kb_grep",
    "kb_glob",
)


def _build_args_preview(fn_name: str, fn_args: dict, source_scope: str | None = None) -> str:
    """Build a human-readable args preview string for tool card display.

    When `source_scope` is provided and the tool is scope-relevant, the preview is
    prefixed with `scope:<scope>` so the frontend tool card can surface routing.
    """
    parts = []
    if source_scope and fn_name in _SCOPED_TOOLS:
        parts.append(f"scope:{source_scope}")
    for key, value in fn_args.items():
        if isinstance(value, str):
            parts.append(f'{key}="{value}"')
        else:
            parts.append(f"{key}={value}")
    return " ".join(parts)[:200]


def execute_tool(
    fn_name: str,
    fn_args: dict,
    user_id: str,
    api_key: str | None = None,
    model: str | None = None,
    trace: bool = True,
) -> str:
    """Dispatch a tool call to the appropriate service and return JSON result.

    The resolved per-request key/model (SEC-04) are threaded into search_documents
    so its rerank step uses the SAME key/model as the turn, never the owner default.
    """
    settings = get_settings()

    if fn_name == "search_documents":
        from services.retrieval_service import search_documents
        metadata_filter = {}
        if "document_type" in fn_args:
            metadata_filter["document_type"] = fn_args["document_type"]
        if "topic" in fn_args:
            metadata_filter["topic"] = fn_args["topic"]
        try:
            results = search_documents(
                user_id=user_id,
                query=fn_args["query"],
                metadata_filter=metadata_filter or None,
                api_key=api_key,
                model=model,
                trace=trace,
            )
            return json.dumps({
                "tool": "search_documents",
                "search_mode": settings.search_mode,
                "reranked": settings.rerank_enabled,
                "results": results,
            })
        except Exception as e:
            logger.error(f"search_documents failed: {e}", exc_info=True)
            return json.dumps({"tool": "search_documents", "error": str(e)})

    elif fn_name == "query_database":
        result = execute_sql(user_id=user_id, query=fn_args["sql"])
        return json.dumps({"tool": "query_database", **result})

    elif fn_name == "web_search":
        result = search_web(query=fn_args["query"])
        return json.dumps({"tool": "web_search", **result})

    elif fn_name == "kb_ls":
        try:
            result = kb_ls(user_id=user_id, path=fn_args["path"])
            return json.dumps({"tool": "kb_ls", "output": result})
        except Exception as e:
            logger.error(f"kb_ls failed: {e}", exc_info=True)
            return json.dumps({"tool": "kb_ls", "error": str(e)})

    elif fn_name == "kb_tree":
        try:
            result = kb_tree(
                user_id=user_id,
                path=fn_args.get("path", ""),
                depth=fn_args.get("depth", 2),
            )
            return json.dumps({"tool": "kb_tree", "output": result})
        except Exception as e:
            logger.error(f"kb_tree failed: {e}", exc_info=True)
            return json.dumps({"tool": "kb_tree", "error": str(e)})

    elif fn_name == "kb_read":
        try:
            result = kb_read(
                user_id=user_id,
                path=fn_args["path"],
                lines=fn_args.get("lines"),
            )
            return json.dumps({"tool": "kb_read", "output": result})
        except Exception as e:
            logger.error(f"kb_read failed: {e}", exc_info=True)
            return json.dumps({"tool": "kb_read", "error": str(e)})

    elif fn_name == "kb_grep":
        try:
            result = kb_grep(
                user_id=user_id,
                pattern=fn_args["pattern"],
                mode=fn_args.get("mode", "keyword"),
                path=fn_args.get("path"),
            )
            return json.dumps({"tool": "kb_grep", "output": result})
        except Exception as e:
            logger.error(f"kb_grep failed: {e}", exc_info=True)
            return json.dumps({"tool": "kb_grep", "error": str(e)})

    elif fn_name == "kb_glob":
        try:
            result = kb_glob(user_id=user_id, pattern=fn_args["pattern"])
            return json.dumps({"tool": "kb_glob", "output": result})
        except Exception as e:
            logger.error(f"kb_glob failed: {e}", exc_info=True)
            return json.dumps({"tool": "kb_glob", "error": str(e)})

    else:
        return json.dumps({"error": f"Unknown tool: {fn_name}"})


@router.post("/{thread_id}/messages")
@traceable(name="chat_send_message")
@limiter.limit(get_settings().chat_rate_limit)  # SEC-04: per-user 20/minute on /api/chat (decorator placed ADJACENT to fn so slowapi sees raw signature; #2128)
async def send_message(
    request: Request,                            # SEC-04: REQUIRED by slowapi (RESEARCH Pitfall 1)
    thread_id: str,
    body: MessageCreate,
    retry: bool = Query(False),                  # PORT-02 / T-08-03: retry-aware dedup hook
    user_id: str = Depends(get_user_id),
):
    db = get_supabase()

    # Verify thread belongs to user
    thread = (
        db.table("threads")
        .select("*")
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Phase 8 PORT-02 / T-08-03 / RESEARCH Pitfall 3 — retry cleanup.
    # On retry, the prior failed turn left an orphan assistant row in messages
    # (empty content, or the "[An error occurred...]" / "[Response interrupted]"
    # placeholder set by the chat handler's except/finally blocks). Delete the
    # most-recent assistant row for this thread+user BEFORE inserting the new
    # placeholder so the thread doesn't accumulate orphan rows on reload.
    #
    # supabase-py 2.13.0 does NOT support .delete().order().limit() chained
    # (postgrest SyncFilterRequestBuilder lacks order/limit on the delete path).
    # Fallback: SELECT id of latest assistant row, then DELETE by id.
    # Scope guards: thread_id + user_id + role='assistant' prevent cross-user
    # or cross-thread deletion even if the JWT/path were tampered with (the
    # thread-ownership check above already proved the thread belongs to user).
    if retry:
        prior = (
            db.table("messages")
            .select("id")
            .eq("thread_id", thread_id)
            .eq("user_id", user_id)
            .eq("role", "assistant")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if prior.data:
            db.table("messages").delete().eq("id", prior.data[0]["id"]).execute()
            logger.info(
                f"Retry cleanup: deleted prior assistant row {prior.data[0]['id']} "
                f"for thread {thread_id}, user {user_id}"
            )

    # Store user message
    # PORT-02 / T-08-03: on retry the original user message is preserved from
    # the prior failed send (frontend re-sends the SAME content). Skip the
    # insert to avoid duplicating the user turn in the thread.
    if not retry:
        db.table("messages").insert({
            "thread_id": thread_id,
            "user_id": user_id,
            "role": "user",
            "content": body.content,
        }).execute()

    # Load all messages for this thread
    history = (
        db.table("messages")
        .select("role, content")
        .eq("thread_id", thread_id)
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    # T-13-NOTICE-HISTORY (Pitfall 3): keep ONLY user/assistant turns in the LLM
    # context. Persisted 'notice' rows (the at-send deprecation line, D-06) are a
    # FE-render/persistence artifact — they must never flow back into the model on
    # this or any future turn.
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history.data
        if m["role"] in ("user", "assistant")
    ]

    async def event_generator():
        full_content = ""
        tools_used_acc = []
        assistant_msg_id = None
        turn_usage: dict = {}  # summed OpenRouter usage across all tool-loop iterations
        try:
            # Build tools list based on availability
            settings = get_settings()

            # KB navigation tools -- always available (default KB always exists)
            tools = [KB_LS_TOOL, KB_TREE_TOOL, KB_READ_TOOL, KB_GREP_TOOL, KB_GLOB_TOOL, EXPLORE_KB_TOOL]

            # Document-specific tools -- only when user has completed documents
            doc_check = (
                db.table("documents")
                .select("id")
                .eq("user_id", user_id)
                .eq("status", "completed")
                .limit(1)
                .execute()
            )
            if doc_check.data:
                tools.append(RETRIEVAL_TOOL)
                tools.append(ANALYZE_DOCUMENT_TOOL)

            tools.append(SQL_TOOL)
            if settings.web_search_enabled:
                tools.append(WEB_SEARCH_TOOL)

            # --- Source routing + scope parsing (Phase 6) -----------------------
            user_latest = body.content
            has_private_docs = bool(doc_check.data)
            source_scope = infer_source_scope(user_latest, has_private_docs)
            scope_hint = parse_scope_hint(user_latest)
            if scope_hint.get("source_hint"):
                source_scope = scope_hint["source_hint"]

            # --- Per-request key + model resolution (SEC-04/DEMO-03/D-03) --------
            # Resolve ONCE per turn, fail-closed. mode=="no_key" → refuse with a
            # structured SSE error and make NO LLM call (DEMO-03). The decrypted
            # key (when mode=="user") is a short-lived local — threaded straight
            # into the call sites below, never stashed in a closure beyond the turn.
            api_key, model, mode, is_user_key = _resolve_key_and_model(
                db, user_id, thread.data, body
            )
            if mode == "no_key":
                # Fail-closed: clean up the orphan placeholder is unnecessary (none
                # created yet — the assistant row insert is below the budget block).
                yield _sse_error(
                    "no_api_key",
                    "Connect your OpenRouter account to chat.",
                )
                return

            # --- Deprecated-pin fallback (SC#4 / D-06, Open Question 2) -----------
            # If the thread is pinned to a model that is no longer in the Phase 12
            # model_cache, degrade gracefully: persist a role 'notice' line (D-06),
            # then OVERRIDE the turn's model to the default so the call runs on the
            # fallback instead of crashing. _resolve_key_and_model stays a pure
            # 3-tier resolver — the override lives here in the caller.
            thread_model = thread.data.get("model") if thread.data else None
            if thread_model:
                try:
                    # Read the live cache as a set of model_ids. Assumption A2: a
                    # mid-refresh / empty cache must NOT flag a valid pin as
                    # deprecated — only treat "absent" as deprecated when the cache
                    # actually has rows.
                    cache_rows = (
                        db.table("model_cache").select("model_id").execute()
                    )
                    cached_ids = {
                        r["model_id"]
                        for r in (cache_rows.data or [])
                        if isinstance(r, dict) and r.get("model_id")
                    }
                    if cached_ids and thread_model not in cached_ids:
                        # Pinned model is gone from the live cache → deprecated.
                        default_model = (
                            _safe_user_default_model(db, user_id)
                            or settings.llm_model
                        )
                        # Composed server-side from controlled strings, inserted
                        # as plain text (FE escapes on render) — no HTML (T-13-XSS).
                        # LOCKED UI-SPEC copy (Copywriting Contract).
                        db.table("messages").insert({
                            "thread_id": thread_id,
                            "user_id": user_id,
                            "role": "notice",
                            "content": (
                                f'Model "{thread_model}" is no longer available '
                                f"— using {default_model} instead."
                            ),
                        }).execute()
                        # OVERRIDE the resolved model for THIS turn (fallback).
                        model = default_model
                except Exception as e:  # T-13-CRASH: a cache-read error never crashes the turn
                    logger.warning(
                        f"model_cache deprecation check failed; skipping notice: "
                        f"{scrub_secrets(str(e))}"
                    )

            # --- Token budget (Phase 6) ------------------------------------------
            budget = TokenBudget(
                context_length=settings.model_context_length,
                response_reserve=settings.response_reserve_tokens,
                safety_margin=settings.budget_safety_margin,
                tool_schema_tokens=settings.tool_schema_tokens,
            )
            # Best-effort dynamic context length lookup (OpenRouter).
            if settings.llm_base_url and "openrouter" in settings.llm_base_url:
                dynamic_length = fetch_model_context_length(model, api_key)
                if dynamic_length and dynamic_length > 0:
                    budget.context_length = dynamic_length
                    logger.info(
                        f"Using dynamic context length {dynamic_length} for {model}"
                    )

            # Create assistant message early for incremental tool persistence
            assistant_msg = db.table("messages").insert({
                "thread_id": thread_id,
                "user_id": user_id,
                "role": "assistant",
                "content": "",
                "tools_used": [],
            }).execute()
            assistant_msg_id = assistant_msg.data[0]["id"]

            current_messages = list(messages)

            # SEC-05 (Phase 6 D-08..D-11): counter-bounded loop with graceful cap-hit.
            # Mirrors explorer_service.py:232 architecture (NOT numeric value: 15 vs explorer's 6).
            iteration = 0
            cap_hit = False
            settings_local = get_settings()  # @lru_cache; safe to call inside the generator
            while iteration < settings_local.chat_max_iterations:
                iteration += 1
                tool_call_happened = False

                for event in stream_chat_completion(
                    current_messages,
                    tools=tools,
                    tool_guide=TOOL_SELECTION_GUIDE if tools else None,
                    source_hint=source_scope,
                    scope_hint=scope_hint if scope_hint else None,
                    api_key=api_key,
                    model=model,
                    trace=(not is_user_key),
                ):
                    if event["type"] == "system_content":
                        # Budget bookkeeping before LLM sees the messages.
                        budget.set_system(event["content"])
                        budget.set_history(current_messages)
                        if budget.is_over():
                            current_messages = budget.truncate_oldest_tool_results(current_messages)
                            logger.warning(
                                f"Budget exceeded, truncated oldest tool results. "
                                f"Remaining: {budget.remaining}"
                            )
                        continue
                    if event["type"] == "text_delta":
                        full_content += event["text"]
                        yield {
                            "event": "content_delta",
                            "data": json.dumps({"text": event["text"]}),
                        }
                    elif event["type"] == "usage":
                        # Sum the trailing OpenRouter usage across EVERY iteration
                        # (it can fire once per tool-loop pass). Persisted as-is.
                        _accumulate_usage(turn_usage, event.get("usage") or {})
                    elif event["type"] == "tool_call":
                        tool_call_happened = True

                        # Add assistant message with tool calls
                        current_messages.append({
                            "role": "assistant",
                            "tool_calls": event["tool_calls"],
                        })

                        for tc in event["tool_calls"]:
                            fn_name = tc["function"]["name"]
                            fn_args = json.loads(tc["function"]["arguments"])

                            # Build args preview for display (includes scope indicator)
                            args_preview = _build_args_preview(fn_name, fn_args, source_scope=source_scope)

                            # Accumulate tool event for persistence
                            tool_entry = {
                                "tool": fn_name,
                                "args_preview": args_preview,
                                "call_id": tc["id"],
                                "status": "running",
                            }
                            is_subagent = fn_name in ("analyze_document", "explore_kb")
                            if is_subagent:
                                tool_entry["subagent"] = True
                            tools_used_acc.append(tool_entry)

                            # Emit tool_start SSE event
                            yield {
                                "event": "tool_event",
                                "data": json.dumps({
                                    "tool_event": True,
                                    "type": "tool_start",
                                    "tool": fn_name,
                                    "call_id": tc["id"],
                                    "args_preview": args_preview,
                                    **({"subagent": True} if is_subagent else {}),
                                }),
                            }

                            # Dispatch
                            if fn_name == "explore_kb":
                                import asyncio
                                from services.explorer_service import run_exploration

                                import queue as _queue
                                q: _queue.Queue = _queue.Queue()
                                SENTINEL = object()

                                def _drive():
                                    try:
                                        for ev in run_exploration(
                                            user_id=user_id,
                                            query=fn_args["query"],
                                            mode=fn_args.get("mode", "deep_search"),
                                            api_key=api_key,
                                            model=model,
                                            trace=(not is_user_key),
                                        ):
                                            q.put(ev)
                                    except Exception as ex:
                                        q.put({"type": "error", "error": str(ex)})
                                    finally:
                                        q.put(SENTINEL)

                                task = asyncio.create_task(asyncio.to_thread(_drive))
                                final_result_dict = None
                                while True:
                                    sub_ev = await asyncio.to_thread(q.get)
                                    if sub_ev is SENTINEL:
                                        break
                                    if sub_ev.get("type") == "result":
                                        final_result_dict = sub_ev["result"]
                                        continue
                                    if sub_ev.get("type") == "error":
                                        final_result_dict = {
                                            "mode": fn_args.get("mode", "deep_search"),
                                            "query": fn_args["query"],
                                            "findings": [],
                                            "synthesis": f"Explorer failed: {sub_ev['error']}",
                                            "tools_used": [],
                                            "iterations": 0,
                                            "budget_exhausted": True,
                                        }
                                        continue
                                    # sub_iteration / sub_tool_start / sub_tool_result -> SSE sub_event row
                                    yield {
                                        "event": "tool_event",
                                        "data": json.dumps({
                                            "tool_event": True,
                                            "type": "sub_event",
                                            "subagent": True,
                                            "parent_call_id": tc["id"],
                                            "sub_event": sub_ev,
                                        }),
                                    }
                                await task
                                if final_result_dict is None:
                                    final_result_dict = {
                                        "mode": fn_args.get("mode", "deep_search"),
                                        "query": fn_args["query"],
                                        "findings": [],
                                        "synthesis": "Explorer produced no result.",
                                        "tools_used": [],
                                        "iterations": 0,
                                        "budget_exhausted": True,
                                    }
                                tool_result = json.dumps({"tool": "explore_kb", **final_result_dict})
                            elif fn_name == "analyze_document":
                                # Sub-agent with SSE alignment matching explore_kb (D-10/D-11/D-12).
                                import asyncio as _asyncio
                                import queue as _queue
                                from services.subagent_service import run_document_analysis

                                q2: _queue.Queue = _queue.Queue()
                                SENTINEL2 = object()

                                def _drive_doc():
                                    try:
                                        for ev in run_document_analysis(
                                            user_id=user_id,
                                            document_name=fn_args["document_name"],
                                            analysis_query=fn_args["query"],
                                            api_key=api_key,
                                            model=model,
                                            trace=(not is_user_key),
                                        ):
                                            q2.put(ev)
                                    except Exception as ex:
                                        q2.put({"type": "result", "result": {"error": str(ex)}})
                                    finally:
                                        q2.put(SENTINEL2)

                                task2 = _asyncio.create_task(_asyncio.to_thread(_drive_doc))
                                final_result_dict = None
                                while True:
                                    sub_ev = await _asyncio.to_thread(q2.get)
                                    if sub_ev is SENTINEL2:
                                        break
                                    if sub_ev.get("type") == "result":
                                        final_result_dict = sub_ev["result"]
                                        continue
                                    # sub_iteration / sub_tool_start / sub_tool_result -> SSE sub_event row
                                    yield {
                                        "event": "tool_event",
                                        "data": json.dumps({
                                            "tool_event": True,
                                            "type": "sub_event",
                                            "subagent": True,
                                            "parent_call_id": tc["id"],
                                            "sub_event": sub_ev,
                                        }),
                                    }
                                await task2
                                if final_result_dict is None:
                                    final_result_dict = {"error": "Document analysis produced no result."}
                                tool_result = json.dumps({"tool": "analyze_document", **final_result_dict})
                            else:
                                tool_result = execute_tool(
                                    fn_name,
                                    fn_args,
                                    user_id,
                                    api_key=api_key,
                                    model=model,
                                    trace=(not is_user_key),
                                )

                            current_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": tool_result,
                            })

                            # Track this tool round-trip in the budget so oldest pairs
                            # can be truncated first if we exceed the context window.
                            # The assistant tool_calls message is at current_messages[-2 - offset];
                            # we locate it by matching tool_call_id.
                            assistant_tc_msg = None
                            for m in reversed(current_messages[:-1]):
                                if m.get("role") == "assistant" and m.get("tool_calls"):
                                    tc_ids = {
                                        _tc.get("id")
                                        for _tc in (m.get("tool_calls") or [])
                                    }
                                    if tc["id"] in tc_ids:
                                        assistant_tc_msg = m
                                        break
                            if assistant_tc_msg is not None:
                                budget.add_tool_result_pair(
                                    assistant_tc_msg, current_messages[-1]
                                )

                            # Update accumulated tool entry with result
                            tool_output_preview = tool_result[:2000] if len(tool_result) > 2000 else tool_result
                            tool_entry["status"] = "complete"
                            tool_entry["output"] = tool_output_preview

                            # Persist tool events incrementally
                            db.table("messages").update({
                                "tools_used": tools_used_acc,
                            }).eq("id", assistant_msg_id).execute()

                            # Emit tool_result SSE event
                            yield {
                                "event": "tool_event",
                                "data": json.dumps({
                                    "tool_event": True,
                                    "type": "tool_result",
                                    "tool": fn_name,
                                    "call_id": tc["id"],
                                    "output": tool_output_preview,
                                    **({"subagent": True} if is_subagent else {}),
                                }),
                            }

                if not tool_call_happened:
                    break  # voluntary stop — main exit path
            else:
                # while-else: fires only when counter exhausts without `break`.
                # This is the CAP-HIT path. Mirrors explorer's exhaustion flag.
                cap_hit = True

            if cap_hit:
                notice = CAP_HIT_NOTICE.format(n=settings_local.chat_max_iterations)
                full_content += notice
                yield {
                    "event": "content_delta",
                    "data": json.dumps({"text": notice}),
                }
                logger.warning(
                    f"Chat loop hit max_iterations cap "
                    f"({settings_local.chat_max_iterations}) for user {user_id}, "
                    f"thread {thread_id}"
                )
                # LangSmith metadata tag — RESEARCH Pitfall 5: best-effort, non-fatal.
                try:
                    from langsmith.run_helpers import get_current_run_tree
                    run = get_current_run_tree()
                    if run is not None:
                        run.add_metadata({
                            "iteration_cap_hit": True,
                            "cap_value": settings_local.chat_max_iterations,
                        })
                except Exception as e:
                    logger.debug(f"LangSmith metadata tag failed (non-fatal): {e}")

            # Update assistant message with final content + summed usage (D-08).
            db.table("messages").update({
                "content": full_content,
                "tools_used": tools_used_acc if tools_used_acc else None,
                "usage": turn_usage or None,
            }).eq("id", assistant_msg_id).execute()

            # Auto-generate title from first message
            if not thread.data.get("title"):
                title = body.content[:50] + ("..." if len(body.content) > 50 else "")
                db.table("threads").update({"title": title}).eq("id", thread_id).execute()

            # done event — carry the summed usage; signal mode:"demo" so the FE
            # can surface the owner-key demo banner (Phase 15). useChat.ts:185
            # keys only on message_id, so extra keys are inert (D-08).
            done_payload = {
                "message_id": assistant_msg_id,
                "content": full_content,
            }
            if turn_usage:
                done_payload["usage"] = turn_usage
            if mode == "demo":
                done_payload["mode"] = "demo"
            yield {
                "event": "done",
                "data": json.dumps(done_payload),
            }
        except openai.RateLimitError as e:
            # 429 — model hit its rate limit (D-12). Distinct structured code so the
            # UI can disambiguate from a 402. RateLimitError IS an APIStatusError
            # subclass, so this MUST be caught BEFORE the APIStatusError branch.
            logger.warning(f"Chat rate-limited: {scrub_secrets(str(e))}", exc_info=True)
            _mark_error_row(db, assistant_msg_id)
            yield _sse_error(
                "rate_limit",
                "This model hit its rate limit. Wait a minute or pick another "
                "model / connect credits.",
            )
        except openai.APIStatusError as e:
            # 402 → payment_required (no 402 subclass exists; branch on status_code).
            # Use the TYPED exception + .status_code, never str(e) parsing (leak risk).
            if e.status_code == 402:  # APIStatusError always carries .status_code
                logger.warning(
                    f"Chat payment-required: {scrub_secrets(str(e))}", exc_info=True
                )
                _mark_error_row(db, assistant_msg_id)
                yield _sse_error(
                    "payment_required",
                    "This model needs credits. Connect your OpenRouter account or "
                    "add credits.",
                )
            elif e.status_code == 401:
                # 401 → no_api_key (SC#4 / D-09 backend half). A mid-stream 401 means
                # OpenRouter rejected the STORED key as invalid/revoked. Emit the SAME
                # structured code the pre-flight no-key path uses (chat.py:798-805) so the
                # FE [Reconnect] mapping is reused — without this it would fall to the
                # else → upstream_error generic dead-end Retry bubble that SC#4 forbids.
                logger.warning(
                    f"Chat unauthorized: {scrub_secrets(str(e))}", exc_info=True
                )
                _mark_error_row(db, assistant_msg_id)
                yield _sse_error(
                    "no_api_key",
                    "Connect your OpenRouter account to chat.",
                )
            elif e.status_code == 403:
                # 403 → forbidden, distinct from payment_required (402), no_api_key (401),
                # and the generic upstream_error (else). The SSE payload carries only the
                # structured CODE; the FE selects locked UI-SPEC copy from it.
                logger.warning(
                    f"Chat forbidden: {scrub_secrets(str(e))}", exc_info=True
                )
                _mark_error_row(db, assistant_msg_id)
                yield _sse_error(
                    "forbidden",
                    "The model provider refused this request. Try another model or "
                    "check your OpenRouter account.",
                )
            else:
                logger.error(
                    f"Chat upstream error: {scrub_secrets(str(e))}", exc_info=True
                )
                _mark_error_row(db, assistant_msg_id)
                yield _sse_error(
                    "upstream_error",
                    "The model provider returned an error. Try again or pick "
                    "another model.",
                )
        except Exception as e:
            # Defense in depth: scrub str(e) on the message string too (the
            # _ScrubFilter is the belt that also catches the exc_info traceback).
            logger.error(f"Chat error: {scrub_secrets(str(e))}", exc_info=True)
            _mark_error_row(db, assistant_msg_id)
            yield {
                "event": "error",
                "data": json.dumps({"error": scrub_secrets(str(e))}),
            }
        finally:
            # Handle client disconnect (GeneratorExit) -- clean up ghost messages
            if assistant_msg_id and not full_content:
                try:
                    db.table("messages").update({
                        "content": "[Response interrupted]",
                    }).eq("id", assistant_msg_id).execute()
                except Exception:
                    pass  # Best-effort cleanup

    return EventSourceResponse(event_generator())
