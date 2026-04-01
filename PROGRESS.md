# Progress

Track your progress through the masterclass. Update this file as you complete modules - Claude Code reads this to understand where you are in the project.

## Convention
- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Modules

### Module 1: App Shell + Observability
- [x] Task 0: External Service Setup (manual — Supabase, OpenAI, LangSmith keys)
- [x] Task 1: Project Scaffolding & Environment Setup
- [x] Task 2: Supabase Database Schema & RLS
- [x] Task 3: Backend — Auth, Config & API Structure
- [x] Task 4: Frontend — Auth UI & App Shell
- [x] Task 5: OpenAI Responses API + SSE Streaming
- [x] Task 6: LangSmith Observability

### Module 2: BYO Retrieval + Memory
- [x] Task 1: Configuration for Multi-Provider Support
- [x] Task 2: LLM Service Rewrite (Chat Completions)
- [x] Task 3: Chat Router for Stateless Completions
- [x] Task 4a: Drop OpenAI Columns Migration
- [x] Task 4b: Ingestion Schema (pgvector + documents + chunks)
- [x] Task 5: Supabase Storage Bucket
- [x] Task 6: Embedding Service
- [x] Task 7: Ingestion Backend (Upload + Processing Pipeline)
- [x] Task 8: Retrieval Service + Tool Calling in Chat
- [x] Task 9: Icon Sidebar Navigation
- [x] Task 10: Documents Page + File Upload + Realtime Status
- [x] Task 11: End-to-End Verification
  - [x] SQL migrations run (003–010)
  - [x] Realtime enabled on documents table
  - [x] .env configured (OpenRouter + Nemotron models)
  - [x] Vector dimensions fixed (2048 for Nemotron embed, no index — pgvector 2000 dim limit)
  - [x] Embedding service switched to raw HTTP (OpenAI SDK parsing issue with OpenRouter)
  - [x] E2E tests: 22/22 passed (auth, threads, chat, streaming, history, documents, upload, chunking, RAG retrieval, cleanup)

### Module 3: Record Manager
- [x] Task 1: Database Migration (content_hash columns + unique index)
- [x] Task 2: Record Manager Service (hashing + diff logic)
- [x] Task 3: Upload Router + Ingestion Service Changes
- [x] Task 4: Frontend Duplicate Feedback
- [x] Task 5: End-to-End Verification

### Module 4: Metadata Extraction
- [x] Task 1: Pydantic DocumentMetadata Model
- [x] Task 2: Metadata Extraction Service (LLM-powered structured extraction)
- [x] Task 3: Database Migration (metadata column, GIN index, RPC update)
- [x] Task 4: Integrate Extraction into Ingestion Pipeline
- [x] Task 5: Retrieval Service Metadata Filtering
- [x] Task 6: Enhanced Tool Definition (document_type + topic filters)
- [x] Task 7: Frontend Display (metadata badges) + E2E Verification

### Module 5: Multi-Format Document Support
- [x] Task 1: Install Docling Dependency
- [x] Task 2: Parsing Service (docling wrapper with extract_text)
- [x] Task 3: Backend MIME Map + Ingestion Integration
- [x] Task 4: Frontend File Upload Updates
- [x] Task 5: End-to-End Testing (PDF, DOCX, HTML, MD, TXT)

### Module 6: Hybrid Search & Reranking
- [x] Task 1: Configuration (search_mode, RRF params, rerank settings)
- [x] Task 2: Database Migration (tsvector column, GIN index, trigger)
- [x] Task 3: Keyword Search RPC Function
- [x] Task 4: Rerank Service (LLM + API providers)
- [x] Task 5: Hybrid Retrieval with RRF Fusion
- [x] Task 6: Chat Router Wiring (search mode context in tool results)
- [x] Task 7: End-to-End Verification
  - [x] Config loads with new settings (hybrid mode, RRF k=60, rerank disabled)
  - [x] All services import correctly (retrieval, rerank)
  - [x] RRF fusion logic verified (deduplication, score boosting, correct ordering)
  - [x] Rerank no-ops correctly when disabled
  - [x] Chat router imports with new config dependency
  - [x] Run migrations 013-014 in Supabase SQL Editor
  - [x] E2E: upload doc, test hybrid search vs vector-only, verify LangSmith traces

### Module 7: Text-to-SQL + Web Search
- [x] Task 1: Web Search & SQL Config (config.py settings + system prompt)
- [x] Task 2: Safe SQL Execution RPC (migration 015)
- [x] Task 3: SQL Execution Service (sql_service.py)
- [x] Task 4: Web Search Service (web_search_service.py — Tavily)
- [x] Task 5: Multi-Tool Chat Router (tool definitions + execute_tool dispatch)
- [x] Task 6: SSE Tool Events (tool_event streaming)
- [x] Task 7: Frontend Tool Indicators (badges in MessageBubble)
- [x] Task 8: Markdown Rendering + Attribution (react-markdown + typography plugin)
- [x] Task 9: End-to-End Verification

### Module 8: Sub-Agents
- [x] Task 1: Configuration (subagent system prompt, max tokens, max context chars)
- [x] Task 2: Sub-Agent Service (resolve_document, get_full_document_text, run_document_analysis)
- [x] Task 3: Chat Router Wiring (analyze_document tool def, dispatch, sub-agent SSE events)
- [x] Task 4: Frontend SSE + UI (ToolEvent interface, sub-agent status handling, indigo badges with spinner)
- [x] Task 5: End-to-End Verification
  - [x] Summarize known doc (Calico_Rulebook.pdf) → analyze_document with sub-agent SSE events
  - [x] Key points in doc (PlayingThePlayer.md) → analyze_document with running/complete lifecycle
  - [x] Chunk search ("strategy") → search_documents (correct routing)
  - [x] Nonexistent doc → graceful "not found" response (LLM routed via query_database + search_documents — acceptable)
  - [x] General question → LLM answered directly (no tool needed — acceptable)
  - [x] Multi-tool → analyze_document called, LLM included summary in response (web_search skipped by LLM — acceptable)
