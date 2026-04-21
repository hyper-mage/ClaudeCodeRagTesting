# Codebase Concerns

**Analysis Date:** 2026-04-03

## Tech Debt

**Synchronous Document Processing:**
- Issue: Document upload, parsing, chunking, embedding, and storage all happen synchronously in the HTTP request handler. Large files (PDFs, DOCX) block the request thread for the entire processing duration.
- Files: `backend/routers/documents.py` (lines 79-87), `backend/services/ingestion_service.py`
- Impact: Upload requests can timeout for large documents. The FastAPI server thread is blocked, reducing concurrency. The comment on line 78 acknowledges this: `"# Process document (synchronous for now)"`.
- Fix approach: Move `process_document()` and `process_document_incremental()` to a background task using FastAPI `BackgroundTasks`, Celery, or Python `asyncio.create_task()`. The Supabase Realtime subscription on the frontend already handles status updates, so the infrastructure for async processing is partially in place.

**New Supabase Client Per Request:**
- Issue: `get_supabase()` in `backend/database.py` creates a new Supabase client on every call. There is no connection pooling or client reuse.
- Files: `backend/database.py`
- Impact: Unnecessary overhead creating HTTP clients repeatedly. Under load, this could exhaust connections or slow responses.
- Fix approach: Cache the client instance using `@lru_cache` or a module-level singleton, similar to how `get_settings()` is cached.

**New LLM Client Per Call:**
- Issue: `get_llm_client()` and `get_embedding_client()` in `backend/services/llm_service.py` create a new OpenAI client on every invocation. No caching or reuse.
- Files: `backend/services/llm_service.py` (lines 11-19, 23-30)
- Impact: Repeated client instantiation overhead. The OpenAI SDK manages internal HTTP connection pools, but only if the client object is reused.
- Fix approach: Cache client instances with `@lru_cache` or module-level singletons.

**Unused `embedding_dimensions` Config:**
- Issue: `config.py` defines `embedding_dimensions: int = 1536` but this value is never referenced in application code. The actual vector dimensions are hardcoded in SQL migration functions (VECTOR(2048)). The config default (1536) also disagrees with the database schema (2048).
- Files: `backend/config.py` (line 36), `supabase/migrations/010_fix_vector_column.sql`, `supabase/migrations/012_add_document_metadata.sql`
- Impact: Misleading configuration. If someone relies on `embedding_dimensions` to change embedding models, nothing will actually change in the database. Dimension mismatch would cause silent failures.
- Fix approach: Either use `embedding_dimensions` dynamically in SQL function creation, or remove it from config and document that changing embedding models requires a migration.

**Full-Text Search Hardcoded to English:**
- Issue: The tsvector trigger and keyword search function both hardcode `'english'` as the text search configuration. Documents in other languages will have poor keyword search results.
- Files: `supabase/migrations/013_add_fulltext_search.sql` (line 7), `supabase/migrations/014_keyword_search_function.sql` (lines 24, 27)
- Impact: Non-English documents will not benefit from keyword search or hybrid search mode. The metadata extraction already detects language (`DocumentMetadata.language`), but this is not used for search.
- Fix approach: Store the detected language per chunk in metadata and use a dynamic text search configuration based on it, or accept the limitation and document it.

## Security Considerations

**Wildcard CORS Policy:**
- Risk: `allow_origins=["*"]` permits any website to make authenticated requests to the API if a user's browser has a valid session token.
- Files: `backend/main.py` (line 12)
- Current mitigation: JWT auth still required for all endpoints. The token is not sent via cookies (it is in the Authorization header), so CSRF is not a direct risk. However, a malicious page could use a stolen token.
- Recommendations: Restrict `allow_origins` to the actual frontend URL in production. Add the frontend origin as an env var (e.g., `FRONTEND_URL`) and use it in the CORS config.

**Service Role Key Used for All Backend Operations:**
- Risk: The backend uses `supabase_service_role_key` (which bypasses RLS) for all database operations. This means RLS policies only protect against direct Supabase client access, not against backend bugs.
- Files: `backend/database.py` (line 7), `backend/config.py` (line 12)
- Current mitigation: All backend endpoints manually filter by `user_id` via `get_user_id()` dependency. The SQL execution function (`execute_readonly_query`) explicitly sets `SET LOCAL role = 'authenticated'` to enforce RLS.
- Recommendations: This is acceptable for the current architecture, but every new query must be carefully reviewed to ensure `user_id` filtering is included. A missed filter would expose data across users.

**SQL Injection via Text-to-SQL Tool:**
- Risk: The `execute_readonly_query` function accepts arbitrary SQL from the LLM and executes it. While it blocks non-SELECT keywords, the keyword blocklist approach is fragile. A crafted query could potentially bypass the regex check (e.g., using SQL comments, Unicode characters, or subqueries with function calls).
- Files: `supabase/migrations/015_execute_readonly_query.sql`, `backend/services/sql_service.py`
- Current mitigation: Keyword blocklist regex, RLS enforcement via `SET LOCAL role`, row limit. The function runs as `SECURITY DEFINER`, which means it executes with the function owner's privileges.
- Recommendations: Consider using a more robust SQL parser instead of regex. Add a whitelist of allowed tables/columns. Consider running the query in a read-only transaction (`SET TRANSACTION READ ONLY`). Log all executed queries for audit.

**No File Size Limit on Upload:**
- Risk: Users can upload arbitrarily large files. The entire file is read into memory (`content = await file.read()`) with no size check.
- Files: `backend/routers/documents.py` (line 42)
- Current mitigation: None. Supabase Storage may have its own limits, but the backend will still read the full file into memory before uploading.
- Recommendations: Add a `max_upload_size` config setting and check `len(content)` before processing. Also consider streaming the upload rather than reading it all into memory. A reasonable default would be 50-100MB.

**No Rate Limiting:**
- Risk: No rate limiting on any endpoint. A malicious user could spam the chat endpoint (triggering expensive LLM calls), upload thousands of documents, or flood the SQL execution endpoint.
- Files: `backend/main.py`, all routers
- Current mitigation: None
- Recommendations: Add rate limiting middleware (e.g., `slowapi` for FastAPI). Critical endpoints: `/api/threads/{id}/messages` (LLM cost), `/api/documents/upload` (processing cost), SQL tool execution.

**Test Credentials in Source Code:**
- Risk: `CLAUDE.md` contains test credentials (`ragtest1@gmail.com` / `testpass123`). Test files also hardcode these credentials.
- Files: `CLAUDE.md`, `backend/tests/test_record_manager.py` (line 69), `backend/tests/test_e2e_subagent.py` (line 20)
- Current mitigation: These are for a test/development environment.
- Recommendations: If this repo is public or shared, these credentials give access to the test account's data. Use environment variables for test credentials.

## Performance Bottlenecks

**Unbounded Chat History Sent to LLM:**
- Problem: Every message in a thread is loaded and sent to the LLM on each new message. Long conversations will exceed context window limits and increase latency and cost linearly.
- Files: `backend/routers/chat.py` (lines 214-223)
- Cause: All messages are fetched with no limit: `.select("role, content").eq("thread_id", thread_id).order("created_at")`. Every message is sent as-is to the LLM.
- Improvement path: Implement a sliding window (e.g., last N messages), summarize older messages, or use token counting to trim history to fit the model's context window. Add a `max_history_messages` config setting.

**LLM-Based Reranking is N API Calls:**
- Problem: When `rerank_provider = "llm"`, each candidate document gets a separate LLM API call for scoring. With `candidate_k = max(top_k * 4, 20)`, that is 20+ sequential LLM calls per search query.
- Files: `backend/services/rerank_service.py` (lines 19-43)
- Cause: Each document scored individually with a full LLM request.
- Improvement path: Batch multiple documents into a single prompt (score all at once). Or switch to a dedicated rerank API (`rerank_provider = "api"`) which handles batching natively. Add concurrency (asyncio.gather) if keeping per-doc LLM calls.

**No Vector Index on Embeddings:**
- Problem: Migration 010 dropped all vector indexes and never recreated them due to Supabase's 2000-dimension limit. Vector search uses sequential scan.
- Files: `supabase/migrations/010_fix_vector_column.sql` (comments on lines 1-3)
- Cause: pgvector ivfflat indexes are limited to 2000 dimensions on Supabase. The embeddings are 2048 dimensions.
- Improvement path: Switch to HNSW index type (supports higher dimensions in newer pgvector versions). Alternatively, switch to an embedding model that produces <=2000 dimensions (the config defaults to `text-embedding-3-small` at 1536 dims, suggesting the 2048 column may be oversized for the current model). Or use pgvector's dimension reduction features.

**Document Processing Blocks Upload Response:**
- Problem: As noted in Tech Debt, document processing is synchronous. For large PDFs, this means the HTTP response is delayed until parsing, chunking, metadata extraction (LLM call), embedding generation (API calls), and DB insertion are all complete.
- Files: `backend/routers/documents.py` (lines 79-87)
- Cause: `process_document()` called inline in the request handler.
- Improvement path: Return immediately after creating the document record with `status: pending`, then process in background.

## Fragile Areas

**SSE Stream Parsing in Frontend:**
- Files: `frontend/src/hooks/useChat.ts` (lines 66-138)
- Why fragile: The SSE parsing is hand-rolled. It splits on `\n`, looks for `data: ` prefixes, and parses JSON. The parser does not handle the `event:` prefix lines from SSE-starlette (it only looks at `data:` lines). If the SSE format changes or the server sends multi-line data fields, parsing will silently fail.
- Safe modification: Consider using the EventSource API or a library like `eventsource-parser` for robust SSE parsing. The `catch {}` on line 133 swallows all parsing errors silently.
- Test coverage: No unit tests for SSE parsing logic.

**Tool Loop Without Bound:**
- Files: `backend/routers/chat.py` (lines 249-309)
- Why fragile: The `while True` loop that handles tool calls has no iteration limit. If the LLM keeps requesting tools (e.g., in a loop asking the same question), this will run indefinitely, accumulating LLM costs.
- Safe modification: Add a `max_tool_rounds` counter (e.g., 10) and break with an error message if exceeded.
- Test coverage: E2E tests exist but do not test runaway tool loops.

**Incremental Document Update Re-parenting:**
- Files: `backend/services/ingestion_service.py` (lines 127-226)
- Why fragile: `process_document_incremental()` re-parents surviving chunks from the old document to the new one, deletes stale chunks, then deletes the old document. If this process fails partway through (e.g., after re-parenting but before deleting the old doc), chunks could belong to a document that still exists, creating inconsistent state.
- Safe modification: Wrap the entire operation in a database transaction. Currently, each Supabase client call is its own transaction.
- Test coverage: No automated tests for incremental processing failure scenarios.

## Scaling Limits

**Message History:**
- Current capacity: Works fine for conversations under ~100 messages
- Limit: At ~500+ messages per thread, the full history sent to the LLM will exceed most model context windows (128K tokens). Even before that, latency and cost scale linearly.
- Scaling path: Implement conversation summarization or sliding window. Add token counting.

**Document Count Per User:**
- Current capacity: Sequential scan for vector search works for small document sets
- Limit: Without a vector index, performance degrades linearly with chunk count. At ~10K+ chunks, vector search will become noticeably slow.
- Scaling path: Restore vector index (requires dimension <=2000 or HNSW), or use a dedicated vector database.

**Concurrent Users:**
- Current capacity: Single FastAPI process, synchronous document processing
- Limit: Each document upload blocks a thread. With default uvicorn settings, only a few concurrent uploads before requests queue.
- Scaling path: Async document processing, multiple uvicorn workers, connection pooling for Supabase client.

## Test Coverage Gaps

**No Frontend Tests:**
- What's not tested: Zero test files exist for the React frontend. No unit tests for components, hooks, or utilities.
- Files: All files in `frontend/src/`
- Risk: UI regressions, broken SSE parsing, auth flow bugs go undetected.
- Priority: Medium -- the frontend is relatively thin, but the SSE parsing in `useChat.ts` and auth flow in `AuthContext.tsx` are critical paths.

**No Unit Tests for Core Services:**
- What's not tested: `embedding_service.py`, `retrieval_service.py`, `llm_service.py`, `metadata_service.py`, `parsing_service.py`, `rerank_service.py`, `subagent_service.py`, `web_search_service.py`, `sql_service.py`
- Files: `backend/services/*.py`
- Risk: Embedding failures, retrieval bugs, reranking errors, SQL injection bypass all go undetected until manual testing.
- Priority: High -- these are the core RAG pipeline services. The only existing tests are for `record_manager.py` (unit + integration) and `test_e2e_subagent.py` (E2E).

**No Test Framework:**
- What's not tested: Tests use raw `assert` statements and manual `python -m tests.test_*` execution. No pytest, no test runner, no CI integration.
- Files: `backend/tests/test_record_manager.py`, `backend/tests/test_e2e_subagent.py`
- Risk: Tests are not discoverable, not run automatically, and have no fixtures/mocking infrastructure.
- Priority: Medium -- adding pytest and a test runner would make it easier to add tests incrementally.

**Chat Router Not Tested:**
- What's not tested: The core chat flow -- message sending, SSE streaming, tool dispatch, tool loop, message persistence.
- Files: `backend/routers/chat.py`
- Risk: This is the primary user-facing feature. Regressions in streaming, tool calling, or message storage would break the core experience.
- Priority: High

## Missing Critical Features

**No Token/Cost Tracking:**
- Problem: No tracking of LLM token usage or API costs per user or per request.
- Blocks: Cost management, usage-based billing, abuse detection, budget alerts.

**No Request Logging/Audit Trail:**
- Problem: No structured logging of API requests, tool invocations, or user actions beyond basic Python `logger` calls. No request IDs for tracing.
- Blocks: Debugging production issues, security audit, usage analytics.

**No Graceful Error Recovery for SSE:**
- Problem: If the SSE stream errors mid-response, the frontend removes the empty assistant message but does not show an error to the user or offer a retry option.
- Files: `frontend/src/hooks/useChat.ts` (lines 139-143)
- Blocks: Good user experience during LLM provider outages or timeouts.

---

*Concerns audit: 2026-04-03*
