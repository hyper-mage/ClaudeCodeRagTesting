import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from auth import get_user_id

logger = logging.getLogger(__name__)
from database import get_supabase
from config import get_settings
from models.schemas import MessageCreate
from services.llm_service import stream_chat_completion
from services.sql_service import get_queryable_schema, execute_sql
from services.web_search_service import search_web
from services.kb_tools_service import kb_ls, kb_tree, kb_read, kb_grep, kb_glob

try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f

router = APIRouter(prefix="/api/threads", tags=["chat"])


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

Always start with kb_tree or kb_ls to orient yourself before reading or searching."""


def _build_args_preview(fn_name: str, fn_args: dict) -> str:
    """Build a human-readable args preview string for tool card display."""
    parts = []
    for key, value in fn_args.items():
        if isinstance(value, str):
            parts.append(f'{key}="{value}"')
        else:
            parts.append(f"{key}={value}")
    return " ".join(parts)[:200]


def execute_tool(fn_name: str, fn_args: dict, user_id: str) -> str:
    """Dispatch a tool call to the appropriate service and return JSON result."""
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

    elif fn_name == "analyze_document":
        from services.subagent_service import run_document_analysis
        result = run_document_analysis(
            user_id=user_id,
            document_name=fn_args["document_name"],
            analysis_query=fn_args["query"],
        )
        return json.dumps({"tool": "analyze_document", **result})

    elif fn_name == "kb_ls":
        result = kb_ls(user_id=user_id, path=fn_args["path"])
        return json.dumps({"tool": "kb_ls", "output": result})

    elif fn_name == "kb_tree":
        result = kb_tree(
            user_id=user_id,
            path=fn_args.get("path", ""),
            depth=fn_args.get("depth", 2),
        )
        return json.dumps({"tool": "kb_tree", "output": result})

    elif fn_name == "kb_read":
        result = kb_read(
            user_id=user_id,
            path=fn_args["path"],
            lines=fn_args.get("lines"),
        )
        return json.dumps({"tool": "kb_read", "output": result})

    elif fn_name == "kb_grep":
        result = kb_grep(
            user_id=user_id,
            pattern=fn_args["pattern"],
            mode=fn_args.get("mode", "keyword"),
            path=fn_args.get("path"),
        )
        return json.dumps({"tool": "kb_grep", "output": result})

    elif fn_name == "kb_glob":
        result = kb_glob(user_id=user_id, pattern=fn_args["pattern"])
        return json.dumps({"tool": "kb_glob", "output": result})

    else:
        return json.dumps({"error": f"Unknown tool: {fn_name}"})


@router.post("/{thread_id}/messages")
@traceable(name="chat_send_message")
async def send_message(
    thread_id: str,
    body: MessageCreate,
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

    # Store user message
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
    messages = [{"role": m["role"], "content": m["content"]} for m in history.data]

    async def event_generator():
        full_content = ""
        tools_used_acc = []
        assistant_msg_id = None
        try:
            # Build tools list based on availability
            settings = get_settings()

            # KB navigation tools -- always available (default KB always exists)
            tools = [KB_LS_TOOL, KB_TREE_TOOL, KB_READ_TOOL, KB_GREP_TOOL, KB_GLOB_TOOL]

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

            while True:
                tool_call_happened = False

                for event in stream_chat_completion(current_messages, tools=tools, tool_guide=TOOL_SELECTION_GUIDE if tools else None):
                    if event["type"] == "text_delta":
                        full_content += event["text"]
                        yield {
                            "event": "content_delta",
                            "data": json.dumps({"text": event["text"]}),
                        }
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

                            # Build args preview for display
                            args_preview = _build_args_preview(fn_name, fn_args)

                            # Accumulate tool event for persistence
                            tool_entry = {
                                "tool": fn_name,
                                "args_preview": args_preview,
                                "call_id": tc["id"],
                                "status": "running",
                            }
                            if fn_name == "analyze_document":
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
                                    **({"subagent": True} if fn_name == "analyze_document" else {}),
                                }),
                            }

                            tool_result = execute_tool(fn_name, fn_args, user_id)

                            current_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": tool_result,
                            })

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
                                    **({"subagent": True} if fn_name == "analyze_document" else {}),
                                }),
                            }

                if not tool_call_happened:
                    break

            # Update assistant message with final content
            db.table("messages").update({
                "content": full_content,
                "tools_used": tools_used_acc if tools_used_acc else None,
            }).eq("id", assistant_msg_id).execute()

            # Auto-generate title from first message
            if not thread.data.get("title"):
                title = body.content[:50] + ("..." if len(body.content) > 50 else "")
                db.table("threads").update({"title": title}).eq("id", thread_id).execute()

            yield {
                "event": "done",
                "data": json.dumps({
                    "message_id": assistant_msg_id,
                    "content": full_content,
                }),
            }
        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            if assistant_msg_id:
                try:
                    db.table("messages").update({
                        "content": "[An error occurred while generating the response]",
                    }).eq("id", assistant_msg_id).execute()
                except Exception:
                    pass  # Best-effort cleanup
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
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
