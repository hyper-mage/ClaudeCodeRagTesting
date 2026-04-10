"""KB navigation tools for the agentic RAG chat loop.

Provides 5 tools (kb_ls, kb_tree, kb_read, kb_grep, kb_glob) that let the
agent navigate and search the hierarchical knowledge base stored in Supabase.
All queries use the service role client and manually filter visibility to
return public content + user-owned content.
"""

import json
import re
import logging

from database import get_supabase
from config import get_settings

logger = logging.getLogger(__name__)

BOARD_GAMES_ROOT_ID = "a0000000-0000-0000-0000-000000000001"


def _resolve_folder_by_path(db, user_id: str, path: str) -> dict | None:
    """Resolve a human-readable path to a folder or document ID.

    Paths use two virtual roots:
    - "Board Games/..." for the public default KB
    - "My Documents/..." for the user's private uploads

    Returns {"type": "folder", "id": ...} or {"type": "document", "id": ..., "folder_id": ...}
    or None if not found.
    """
    path = path.strip("/").strip()
    if not path:
        return None

    segments = path.split("/")
    first_segment = segments[0]

    # Detect if the last segment is a file (has extension)
    last_segment = segments[-1]
    is_file = "." in last_segment and len(last_segment.split(".")[-1]) <= 5

    folder_segments = segments[:-1] if is_file else segments
    file_segment = last_segment if is_file else None

    # Determine starting folder
    if first_segment.lower() == "board games":
        root_id = BOARD_GAMES_ROOT_ID
        walk_segments = folder_segments[1:]  # skip "Board Games"
    elif first_segment.lower() == "my documents":
        # Find user's private root folders
        root_id = None
        walk_segments = folder_segments[1:]  # skip "My Documents"
    else:
        return None

    # Walk the folder tree using name + parent_id
    current_folder_id = root_id

    if root_id is None and len(walk_segments) > 0:
        # For "My Documents", find the first segment among user's private root folders
        result = (
            db.table("folders")
            .select("id, name")
            .eq("user_id", user_id)
            .eq("visibility", "private")
            .is_("parent_id", "null")
            .ilike("name", walk_segments[0])
            .execute()
        )
        if not result.data:
            return None
        current_folder_id = result.data[0]["id"]
        walk_segments = walk_segments[1:]

    if root_id is None and len(folder_segments) <= 1 and not is_file:
        # "My Documents" root itself — virtual, no single folder ID
        return {"type": "virtual_root", "id": "my_documents"}

    for segment in walk_segments:
        result = (
            db.table("folders")
            .select("id, name")
            .eq("parent_id", current_folder_id)
            .ilike("name", segment)
            .execute()
        )
        if not result.data:
            return None
        current_folder_id = result.data[0]["id"]

    if file_segment:
        # Resolve document within the folder
        query = (
            db.table("documents")
            .select("id, filename, folder_id")
            .eq("status", "completed")
            .ilike("filename", file_segment)
        )
        if current_folder_id is None:
            # Root-level private file (My Documents/somefile.pdf with no subfolder)
            query = query.is_("folder_id", "null").eq("user_id", user_id)
        else:
            query = query.eq("folder_id", current_folder_id).or_(f"user_id.eq.{user_id},visibility.eq.public")
        result = query.execute()
        if not result.data:
            return None
        return {
            "type": "document",
            "id": result.data[0]["id"],
            "folder_id": result.data[0]["folder_id"],
        }

    return {"type": "folder", "id": current_folder_id}


def _build_display_path(db, folder_id: str | None, filename: str | None = None) -> str:
    """Build a human-readable display path by walking parent_id chain."""
    if folder_id is None:
        return filename or ""

    parts = []
    current_id = folder_id
    visited = set()

    while current_id and current_id not in visited:
        visited.add(current_id)
        result = (
            db.table("folders")
            .select("name, parent_id")
            .eq("id", current_id)
            .execute()
        )
        if not result.data:
            break
        parts.append(result.data[0]["name"])
        current_id = result.data[0]["parent_id"]

    parts.reverse()
    path = "/".join(parts)
    if filename:
        path = f"{path}/{filename}"
    return path


def kb_ls(user_id: str, path: str) -> str:
    """List files and subfolders at the given KB path.

    Returns subfolder names with trailing / and files with size in KB.
    """
    db = get_supabase()

    # Handle root listing
    if not path or path.strip("/") == "":
        return "Board Games/\nMy Documents/"

    resolved = _resolve_folder_by_path(db, user_id, path)

    if resolved is None:
        return json.dumps({"error": f"Path not found: {path}"})

    if resolved["type"] == "virtual_root" and resolved["id"] == "my_documents":
        # List user's private root folders + unfiled documents
        folders_result = (
            db.table("folders")
            .select("name")
            .eq("user_id", user_id)
            .eq("visibility", "private")
            .is_("parent_id", "null")
            .order("name")
            .execute()
        )
        docs_result = (
            db.table("documents")
            .select("filename, file_size")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .is_("folder_id", "null")
            .order("filename")
            .execute()
        )
        lines = []
        for f in (folders_result.data or []):
            lines.append(f"{f['name']}/")
        for d in (docs_result.data or []):
            size_kb = (d.get("file_size") or 0) // 1024
            lines.append(f"{d['filename']}  ({size_kb} KB)")
        return "\n".join(lines) if lines else "(empty folder)"

    if resolved["type"] != "folder":
        return json.dumps({"error": f"Not a folder: {path}"})

    folder_id = resolved["id"]

    # Get child folders
    folders_result = (
        db.table("folders")
        .select("name")
        .eq("parent_id", folder_id)
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .order("name")
        .execute()
    )

    # Get documents in folder
    docs_result = (
        db.table("documents")
        .select("filename, file_size")
        .eq("folder_id", folder_id)
        .eq("status", "completed")
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .order("filename")
        .execute()
    )

    lines = []
    for f in (folders_result.data or []):
        lines.append(f"{f['name']}/")
    for d in (docs_result.data or []):
        size_kb = (d.get("file_size") or 0) // 1024
        lines.append(f"{d['filename']}  ({size_kb} KB)")

    return "\n".join(lines) if lines else "(empty folder)"


def kb_tree(user_id: str, path: str = "", depth: int = 2) -> str:
    """Return a hierarchical tree view of the KB with depth-limited indentation."""
    db = get_supabase()

    if not path or path.strip("/") == "":
        # Show both roots
        board_games_tree = _build_tree(db, user_id, BOARD_GAMES_ROOT_ID, "Board Games", depth)
        my_docs_tree = _build_my_documents_tree(db, user_id, depth)
        return f"{board_games_tree}\n{my_docs_tree}"

    resolved = _resolve_folder_by_path(db, user_id, path)
    if resolved is None:
        return json.dumps({"error": f"Path not found: {path}"})

    if resolved["type"] == "virtual_root" and resolved["id"] == "my_documents":
        return _build_my_documents_tree(db, user_id, depth)

    if resolved["type"] != "folder":
        return json.dumps({"error": f"Not a folder: {path}"})

    folder_name = path.rstrip("/").split("/")[-1]
    return _build_tree(db, user_id, resolved["id"], folder_name, depth)


def _build_tree(db, user_id: str, folder_id: str, folder_name: str, depth: int) -> str:
    """Build a tree string for a folder using BFS up to depth levels."""
    lines = [f"{folder_name}/"]
    _tree_recursive(db, user_id, folder_id, "", depth, 0, lines)
    return "\n".join(lines)


def _tree_recursive(db, user_id: str, folder_id: str, prefix: str, max_depth: int, current_depth: int, lines: list[str]) -> None:
    """Recursively build tree lines with box-drawing characters."""
    if current_depth >= max_depth:
        return

    # Get child folders
    folders_result = (
        db.table("folders")
        .select("id, name")
        .eq("parent_id", folder_id)
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .order("name")
        .execute()
    )
    child_folders = folders_result.data or []

    # Get documents
    docs_result = (
        db.table("documents")
        .select("filename")
        .eq("folder_id", folder_id)
        .eq("status", "completed")
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .order("filename")
        .execute()
    )
    docs = docs_result.data or []

    items = [(f["name"], "folder", f["id"]) for f in child_folders] + \
            [(d["filename"], "file", None) for d in docs]

    for i, (name, item_type, item_id) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        child_prefix = prefix + ("    " if is_last else "\u2502   ")

        if item_type == "folder":
            lines.append(f"{prefix}{connector}{name}/")
            _tree_recursive(db, user_id, item_id, child_prefix, max_depth, current_depth + 1, lines)
        else:
            lines.append(f"{prefix}{connector}{name}")


def _build_my_documents_tree(db, user_id: str, depth: int) -> str:
    """Build tree for the My Documents virtual root."""
    lines = ["My Documents/"]

    # Get user's private root folders
    folders_result = (
        db.table("folders")
        .select("id, name")
        .eq("user_id", user_id)
        .eq("visibility", "private")
        .is_("parent_id", "null")
        .order("name")
        .execute()
    )
    root_folders = folders_result.data or []

    # Get unfiled documents
    docs_result = (
        db.table("documents")
        .select("filename")
        .eq("user_id", user_id)
        .eq("status", "completed")
        .is_("folder_id", "null")
        .order("filename")
        .execute()
    )
    unfiled_docs = docs_result.data or []

    items = [(f["name"], "folder", f["id"]) for f in root_folders] + \
            [(d["filename"], "file", None) for d in unfiled_docs]

    for i, (name, item_type, item_id) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        child_prefix = "    " if is_last else "\u2502   "

        if item_type == "folder":
            lines.append(f"{connector}{name}/")
            _tree_recursive(db, user_id, item_id, child_prefix, depth, 1, lines)
        else:
            lines.append(f"{connector}{name}")

    if not items:
        lines.append("\u2514\u2500\u2500 (empty)")

    return "\n".join(lines)


def kb_read(user_id: str, path: str, lines: str | None = None) -> str:
    """Read a document's full text, optionally returning a specific line range.

    Reassembles content from chunks ordered by chunk_index.
    Auto-truncates at 200 lines with a continuation hint.
    """
    db = get_supabase()
    resolved = _resolve_folder_by_path(db, user_id, path)

    if resolved is None:
        return json.dumps({"error": f"Document not found: {path}"})
    if resolved["type"] != "document":
        return json.dumps({"error": f"Not a document: {path}"})

    doc_id = resolved["id"]

    # Reassemble full text from chunks with visibility filter
    result = (
        db.table("document_chunks")
        .select("content")
        .eq("document_id", doc_id)
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .order("chunk_index")
        .execute()
    )
    if not result.data:
        return json.dumps({"error": f"No content found for: {path}"})

    full_text = "\n\n".join(chunk["content"] for chunk in result.data)
    all_lines = full_text.split("\n")
    total = len(all_lines)

    if lines:
        # Parse line range "start-end" (1-indexed)
        parts = lines.split("-")
        start = max(1, int(parts[0]))
        end = min(total, int(parts[1])) if len(parts) > 1 else min(total, start + 49)
        selected = all_lines[start - 1:end]
        numbered = [f"{start + i:>5} | {line}" for i, line in enumerate(selected)]
        output = "\n".join(numbered)
        if end < total:
            output += f"\n[Lines {start}-{end} of {total}. Use lines=\"{end + 1}-{min(end + 200, total)}\" to continue.]"
        return output

    # No line range — auto-truncate at 200
    if total > 200:
        numbered = [f"{i + 1:>5} | {line}" for i, line in enumerate(all_lines[:200])]
        output = "\n".join(numbered)
        output += f"\n[Truncated at line 200 of {total}. Use lines=\"201-{min(400, total)}\" to continue reading.]"
        return output

    numbered = [f"{i + 1:>5} | {line}" for i, line in enumerate(all_lines)]
    return "\n".join(numbered)


def kb_grep(user_id: str, pattern: str, mode: str = "keyword", path: str | None = None) -> str:
    """Search KB content via regex or keyword mode.

    regex mode: Uses PostgreSQL ~* operator via kb_grep_regex RPC.
    keyword mode: Uses existing keyword_search_chunks RPC with tsvector.
    """
    db = get_supabase()

    if mode == "regex":
        # Resolve optional path scope to ltree
        search_path = None
        if path:
            resolved = _resolve_folder_by_path(db, user_id, path)
            if resolved and resolved["type"] == "folder":
                # Get the ltree path for this folder
                folder_result = (
                    db.table("folders")
                    .select("path")
                    .eq("id", resolved["id"])
                    .execute()
                )
                if folder_result.data:
                    search_path = folder_result.data[0]["path"]

        try:
            result = db.rpc("kb_grep_regex", {
                "pattern": pattern,
                "filter_user_id": user_id,
                "search_path": search_path,
                "match_limit": 20,
            }).execute()
        except Exception as e:
            return json.dumps({"error": f"Regex search failed: {str(e)}"})

        if not result.data:
            return f"No matches for pattern: {pattern}"

        # Format ripgrep-style output with context
        output_lines = []
        match_count = 0
        for row in result.data:
            if match_count >= 50:
                output_lines.append(f"[... truncated at 50 match groups]")
                break

            display_path = _build_display_path(db, row.get("folder_path"), row["filename"])
            if not display_path:
                display_path = row["filename"]

            content_lines = row["content"].split("\n")
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                return json.dumps({"error": f"Invalid regex pattern: {pattern}"})

            for line_num, line in enumerate(content_lines, 1):
                if regex.search(line):
                    match_count += 1
                    # Add 1 line of context above if available
                    if line_num > 1:
                        output_lines.append(f"{display_path}:{line_num - 1}: {content_lines[line_num - 2]}")
                    output_lines.append(f"{display_path}:{line_num}: {line}")
                    # Add 1 line of context below if available
                    if line_num < len(content_lines):
                        output_lines.append(f"{display_path}:{line_num + 1}: {content_lines[line_num]}")
                    output_lines.append("")  # blank separator

        return "\n".join(output_lines).rstrip() if output_lines else f"No matches for pattern: {pattern}"

    else:
        # Keyword mode — use existing keyword_search_chunks RPC
        try:
            result = db.rpc("keyword_search_chunks", {
                "search_query": pattern,
                "match_count": 20,
                "filter_user_id": user_id,
            }).execute()
        except Exception as e:
            return json.dumps({"error": f"Keyword search failed: {str(e)}"})

        if not result.data:
            return f"No matches for: {pattern}"

        # Format results with document context
        output_lines = []
        for row in result.data:
            doc_id = row["document_id"]
            # Look up document filename and folder
            doc_result = (
                db.table("documents")
                .select("filename, folder_id")
                .eq("id", doc_id)
                .execute()
            )
            if doc_result.data:
                doc = doc_result.data[0]
                display_path = _build_display_path(db, doc.get("folder_id"), doc["filename"])
                snippet = row["content"][:200].replace("\n", " ")
                output_lines.append(f"{display_path} (chunk {row['chunk_index']}, rank {row['rank']:.3f}):")
                output_lines.append(f"  {snippet}")
                output_lines.append("")

        return "\n".join(output_lines).rstrip() if output_lines else f"No matches for: {pattern}"


def kb_glob(user_id: str, pattern: str) -> str:
    """Find files matching a glob pattern across the KB.

    Uses kb_glob_match RPC which converts glob to LIKE pattern.
    """
    db = get_supabase()

    try:
        result = db.rpc("kb_glob_match", {
            "glob_pattern": pattern,
            "filter_user_id": user_id,
            "match_limit": 50,
        }).execute()
    except Exception as e:
        return json.dumps({"error": f"Glob search failed: {str(e)}"})

    if not result.data:
        return f"No files matching: {pattern}"

    lines = [row["full_path"] for row in result.data]
    return "\n".join(lines)
