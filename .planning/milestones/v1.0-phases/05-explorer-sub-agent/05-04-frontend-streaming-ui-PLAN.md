---
phase: 05-explorer-sub-agent
plan: 04
type: execute
wave: 4
depends_on:
  - "05-03"
files_modified:
  - frontend/src/hooks/useChat.ts
  - frontend/src/components/ToolCallCard.tsx
  - frontend/src/components/MessageBubble.tsx
autonomous: false
requirements:
  - EXPL-04
  - EXPL-06
must_haves:
  truths:
    - "Frontend parses SSE rows with type='sub_event' and attaches them to the parent ToolCallCard by parent_call_id"
    - "ToolCallCard for explore_kb renders a nested list of sub_events under the parent card"
    - "Explorer in-progress state shows an X/N progress indicator (Pitfall 8)"
    - "User can collapse/expand the nested sub-event list (Pitfall 8)"
  artifacts:
    - path: frontend/src/hooks/useChat.ts
      provides: "Sub-event parsing branch that mutates the parent ToolEvent's subEvents array"
      contains: "sub_event"
    - path: frontend/src/components/ToolCallCard.tsx
      provides: "Nested sub_event rendering when tool === 'explore_kb'"
      contains: "subEvents"
    - path: frontend/src/components/MessageBubble.tsx
      provides: "Pass subEvents through to ToolCallCard"
      contains: "subEvents"
  key_links:
    - from: frontend/src/hooks/useChat.ts
      to: frontend/src/components/ToolCallCard.tsx
      via: "ToolEvent.subEvents array"
      pattern: "subEvents"
    - from: frontend/src/components/MessageBubble.tsx
      to: frontend/src/components/ToolCallCard.tsx
      via: "<ToolCallCard subEvents={t.subEvents} ... />"
      pattern: "subEvents={"
---

<objective>
Surface the explorer's progress in the chat UI. After this plan: when the user asks a question that triggers `explore_kb`, an indigo-styled card appears immediately, then real-time nested sub-cards (one per kb_tree/kb_ls/kb_read sub-call) populate under it as the explorer runs. When the explorer finishes, the parent card shows the final synthesis.

Purpose: Plans 01-03 are entirely backend; Plan 04 makes the explorer visible to the user. Without this plan, the explorer works but appears to the user as a single long pause.

Output:
- ToolEvent.subEvents type added to useChat.ts; type === 'sub_event' branch parses and appends nested events keyed by parent_call_id
- ToolCallCard renders a nested expandable list when `subEvents` is present
- Progress indicator: "Exploring... (X/10)" header on running explore_kb cards (X = sub_tool_starts received so far; 10 = `explorer_max_tool_calls` budget). Both axes are tool-call counts, so the ratio is meaningful.
- MessageBubble passes subEvents prop through to ToolCallCard
- One human-verify checkpoint to confirm the visual flow is correct
</objective>

<execution_context>
@.claude/get-shit-done/workflows/execute-plan.md
@.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/05-explorer-sub-agent/05-RESEARCH.md
@.planning/phases/05-explorer-sub-agent/05-VALIDATION.md
@.planning/phases/05-explorer-sub-agent/05-03-SUMMARY.md
@frontend/src/hooks/useChat.ts
@frontend/src/components/ToolCallCard.tsx
@frontend/src/components/MessageBubble.tsx

<interfaces>
<!-- Existing types in useChat.ts (extend, do not replace) -->

```typescript
export interface ToolEvent {
  tool: string
  args_preview: string
  output?: string
  call_id?: string
  subagent?: boolean
  status: 'running' | 'complete'
  // NEW (added by this plan):
  subEvents?: SubEvent[]
}

export interface SubEvent {
  type: 'sub_iteration' | 'sub_tool_start' | 'sub_tool_result'
  iteration?: number          // for sub_iteration
  call_id?: string            // for sub_tool_*
  tool?: string               // for sub_tool_*
  args_preview?: string       // for sub_tool_start
  output?: string             // for sub_tool_result (already clipped server-side to 1000 chars)
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolsUsed?: ToolEvent[]
}
```

<!-- SSE row shapes the frontend now sees (defined by Plan 03 backend) -->

```jsonc
// parent tool_start (existing)
{ "tool_event": true, "type": "tool_start", "tool": "explore_kb",
  "subagent": true, "call_id": "call_abc", "args_preview": "..." }

// NEW — nested sub_event rows
{ "tool_event": true, "type": "sub_event", "subagent": true,
  "parent_call_id": "call_abc",
  "sub_event": { "type": "sub_tool_start", "call_id": "sub_1",
                 "tool": "kb_tree", "args_preview": "depth=2" } }

{ "tool_event": true, "type": "sub_event", "subagent": true,
  "parent_call_id": "call_abc",
  "sub_event": { "type": "sub_tool_result", "call_id": "sub_1",
                 "tool": "kb_tree", "output": "Catan/\n  rules.md" } }

{ "tool_event": true, "type": "sub_event", "subagent": true,
  "parent_call_id": "call_abc",
  "sub_event": { "type": "sub_iteration", "iteration": 2 } }

// parent tool_result (existing — output is JSON-encoded {"tool":"explore_kb",...ExplorerResult})
{ "tool_event": true, "type": "tool_result", "tool": "explore_kb",
  "subagent": true, "call_id": "call_abc",
  "output": "{\"tool\":\"explore_kb\",\"mode\":\"summarize\",\"synthesis\":\"...\",...}" }
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend useChat.ts — SubEvent type + sub_event SSE parsing branch</name>
  <read_first>
    - frontend/src/hooks/useChat.ts (full)
    - .planning/phases/05-explorer-sub-agent/05-03-SUMMARY.md (verify SSE row shapes)
    - .planning/phases/05-explorer-sub-agent/05-RESEARCH.md (lines 599-625 — frontend extension example)
  </read_first>
  <files>
    - frontend/src/hooks/useChat.ts
  </files>
  <behavior>
    - SubEvent interface exported; ToolEvent gains optional `subEvents?: SubEvent[]` field
    - SSE rows with `parsed.tool_event === true && parsed.type === 'sub_event'` route to a new branch
    - Branch finds the parent ToolEvent in the current message's toolsUsed by `t.call_id === parsed.parent_call_id` and appends `parsed.sub_event` to its `subEvents` array (initializing to [])
    - If parent not found (defensive), the sub_event is silently dropped (don't crash)
    - Existing tool_start / tool_result branches unchanged; legacy fallback branch unchanged
    - Setting subEvents triggers re-render via existing setMessages map pattern (immutable update)
  </behavior>
  <action>
    1) In `frontend/src/hooks/useChat.ts`:

    Add the SubEvent interface BEFORE the existing `export interface ToolEvent`:
    ```typescript
    export interface SubEvent {
      type: 'sub_iteration' | 'sub_tool_start' | 'sub_tool_result'
      iteration?: number
      call_id?: string
      tool?: string
      args_preview?: string
      output?: string
    }
    ```

    Update ToolEvent — add `subEvents?: SubEvent[]` field at end of interface body.

    2) In the SSE parsing block (the `if (parsed.tool_event === true) {` chain around lines 99-148), add a new `else if` branch BEFORE the existing legacy fallback `else {`:
    ```typescript
    } else if (parsed.type === 'sub_event') {
      // Explorer sub-agent progress event — append to parent ToolEvent's subEvents
      setMessages(prev =>
        prev.map(m => {
          if (m.id !== assistantId) return m
          return {
            ...m,
            toolsUsed: (m.toolsUsed || []).map(t =>
              t.call_id === parsed.parent_call_id
                ? { ...t, subEvents: [...(t.subEvents || []), parsed.sub_event as SubEvent] }
                : t
            ),
          }
        })
      )
    ```

    Make sure to keep the existing `} else {` legacy branch AFTER this new branch.

    3) Also update the loadMessages mapping (lines 25-41) to type-cast tools_used so subEvents passes through if persisted:
    ```typescript
    setMessages(data.messages.map((m: Record<string, unknown>) => ({
      ...m,
      toolsUsed: m.tools_used as ToolEvent[] | undefined,
    })))
    ```
    This already happens — no change needed if subEvents is in ToolEvent and the cast is broad enough. Verify by reading the file. If the existing cast restricts the shape, broaden to include subEvents (subEvents is optional so persisted rows without it still type-check).

    Note: backend currently does NOT persist subEvents in the tools_used DB column (only the parent ToolEvent's `output` carries the final ExplorerResult). On page reload, sub-cards won't replay; this is acceptable — the parent card still shows the synthesis. Document this in the SUMMARY.
  </action>
  <acceptance_criteria>
    - `grep -n "export interface SubEvent" frontend/src/hooks/useChat.ts` returns a match
    - `grep -n "subEvents" frontend/src/hooks/useChat.ts` returns ≥3 matches (interface field + state update + spread)
    - `grep -n "parsed.type === 'sub_event'" frontend/src/hooks/useChat.ts` returns a match
    - `grep -n "parent_call_id" frontend/src/hooks/useChat.ts` returns a match
    - `grep -n "sub_iteration" frontend/src/hooks/useChat.ts` returns a match (in the union type)
    - `grep -n "sub_tool_start" frontend/src/hooks/useChat.ts` returns a match
    - `grep -n "sub_tool_result" frontend/src/hooks/useChat.ts` returns a match
    - `cd frontend && npm run lint` exits 0 (no new lint errors)
    - `cd frontend && npx tsc --noEmit -p tsconfig.app.json` exits 0 (TypeScript happy)
  </acceptance_criteria>
  <verify>
    <automated>cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run lint</automated>
  </verify>
  <done>
    SubEvent type exported, ToolEvent extended, SSE parsing branch handles sub_event rows by mutating parent ToolEvent's subEvents array immutably. TS + lint clean.
  </done>
</task>

<task type="auto">
  <name>Task 2: Extend ToolCallCard.tsx — nested sub_event rendering + progress indicator + plumb subEvents through MessageBubble</name>
  <read_first>
    - frontend/src/components/ToolCallCard.tsx (full)
    - frontend/src/components/MessageBubble.tsx (full)
    - frontend/src/hooks/useChat.ts (after Task 1 — to import SubEvent type)
    - .planning/phases/05-explorer-sub-agent/05-RESEARCH.md (lines 458-461 — Pitfall 8 collapse-by-default UX)
  </read_first>
  <files>
    - frontend/src/components/ToolCallCard.tsx
    - frontend/src/components/MessageBubble.tsx
  </files>
  <behavior>
    - ToolCallCard accepts new `subEvents?: SubEvent[]` prop and `tool === 'explore_kb'`-aware rendering
    - When subEvents is non-empty, render a nested list under the main card content (BELOW the existing `output` block, or in the card body when expanded)
    - For sub_tool_start without a matching sub_tool_result: show running spinner inline
    - For sub_tool_result: show as completed (Check icon)
    - For sub_iteration: render as a subtle header line "Iteration N"
    - Progress indicator (W4 fix): when `tool === 'explore_kb' && status === 'running'`, show in header: `Exploring... (X/10)` where X = number of sub_tool_starts received so far and 10 = `explorer_max_tool_calls` budget. Both axes are tool-call counts, so the ratio is meaningful. Do NOT use iteration cap (6) as denominator — it would mismatch the counter axis. Constants are hardcoded for now; a later phase can expose them via a `/api/config` endpoint if needed.
    - Pair sub_tool_start + sub_tool_result rows by call_id; render each pair as ONE compact line (icon + tool name + args_preview + status)
    - Nested list COLLAPSED by default for explore_kb cards (Pitfall 8); separate expand/collapse from the main card's expand state
    - TOOL_LABELS extended to include `explore_kb: 'Explore KB'`
    - TOOL_ICONS extended to include `explore_kb: Compass` (from lucide-react)
    - MessageBubble passes `t.subEvents` through to ToolCallCard's `subEvents` prop
  </behavior>
  <action>
    1) Update `frontend/src/components/ToolCallCard.tsx`:

    Add `Compass, Loader2` to the lucide-react import line (already imports Search, Globe, etc.):
    ```typescript
    import { FolderOpen, GitBranch, FileText, Search, Globe, Database, Brain, Check, ChevronDown, ChevronUp, Compass } from 'lucide-react'
    ```

    Add `import type { SubEvent } from '../hooks/useChat'` near the top.

    Extend the Props interface:
    ```typescript
    interface Props {
      tool: string
      args_preview: string
      output?: string
      call_id?: string
      subagent?: boolean
      status: 'running' | 'complete'
      subEvents?: SubEvent[]
    }
    ```

    Extend TOOL_LABELS:
    ```typescript
    const TOOL_LABELS: Record<string, string> = {
      kb_ls: 'List Files',
      kb_tree: 'KB Tree',
      kb_read: 'Read Document',
      kb_grep: 'Search Content',
      kb_glob: 'Find Files',
      search_documents: 'Document Search',
      query_database: 'Database Query',
      web_search: 'Web Search',
      analyze_document: 'Document Analysis',
      explore_kb: 'Explore KB',
    }
    ```

    Extend TOOL_ICONS:
    ```typescript
    const TOOL_ICONS: Record<string, LucideIcon> = {
      kb_ls: FolderOpen,
      kb_tree: GitBranch,
      kb_read: FileText,
      kb_grep: Search,
      kb_glob: Globe,
      search_documents: Search,
      query_database: Database,
      web_search: Globe,
      analyze_document: Brain,
      explore_kb: Compass,
    }
    ```

    Add a module-level constant mirroring the backend's `explorer_max_tool_calls` default (kept in sync manually; see note in source):
    ```typescript
    // Must match backend/config.py -> Settings.explorer_max_tool_calls default.
    // Denominator for the Explore KB progress indicator; both numerator (sub_tool_start
    // count) and denominator (tool-call budget) share the same axis, so the ratio is
    // meaningful. If you change this, update the backend default at the same time.
    const EXPLORER_MAX_TOOL_CALLS = 10
    ```

    Replace the function body (keeping the destructuring update for the new prop):

    ```typescript
    export default function ToolCallCard({ tool, args_preview, output, subagent, status, subEvents }: Props) {
      const [expanded, setExpanded] = useState(false)
      const [subExpanded, setSubExpanded] = useState(false)

      const Icon = TOOL_ICONS[tool] || Search
      const label = TOOL_LABELS[tool] || tool
      const iconColor = subagent
        ? 'text-indigo-300'
        : tool.startsWith('kb_')
          ? 'text-emerald-400'
          : 'text-gray-400'
      const borderColor = subagent ? 'border-indigo-700' : 'border-gray-700'

      // Pair up sub_tool_start + sub_tool_result by call_id; collect iteration markers.
      const subToolStarts = (subEvents || []).filter(s => s.type === 'sub_tool_start')
      const subToolResults = new Map<string, SubEvent>()
      for (const s of (subEvents || [])) {
        if (s.type === 'sub_tool_result' && s.call_id) subToolResults.set(s.call_id, s)
      }
      const subIterations = (subEvents || []).filter(s => s.type === 'sub_iteration')
      // Progress ratio: tool-calls-started / tool-call-budget. Both share the same axis
      // (explorer_max_tool_calls on the backend), so the number is meaningful.
      const explorerProgress = tool === 'explore_kb' && status === 'running'
        ? `Exploring... (${subToolStarts.length}/${EXPLORER_MAX_TOOL_CALLS})`
        : null

      return (
        <div className={`border ${borderColor} rounded-md overflow-hidden`}>
          <div
            className="flex items-center justify-between px-2 py-2 cursor-pointer bg-gray-800/50"
            onClick={() => setExpanded(!expanded)}
          >
            <div className="flex items-center gap-1 min-w-0">
              <Icon className={`w-4 h-4 flex-shrink-0 ${iconColor}`} />
              <span className="text-xs font-semibold text-gray-200">{label}</span>
              {args_preview && (
                <span className="text-xs font-mono text-gray-400 truncate max-w-[200px] ml-1">
                  {args_preview}
                </span>
              )}
              {explorerProgress && (
                <span className="text-xs text-indigo-300 ml-2">{explorerProgress}</span>
              )}
            </div>
            <div className="flex items-center gap-1 flex-shrink-0 ml-2">
              {status === 'running' ? (
                <span className="w-3.5 h-3.5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
              ) : (
                <Check className="w-3.5 h-3.5 text-gray-500" />
              )}
              {expanded ? (
                <ChevronUp className="w-3.5 h-3.5 text-gray-500" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
              )}
            </div>
          </div>
          {expanded && (
            <div className="border-t border-gray-700 px-4 py-2 bg-gray-800">
              {/* Nested sub-events for explore_kb */}
              {tool === 'explore_kb' && subEvents && subEvents.length > 0 && (
                <div className="mb-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); setSubExpanded(!subExpanded) }}
                    className="text-xs text-indigo-300 hover:text-indigo-200 mb-1"
                  >
                    {subExpanded
                      ? `Hide sub-steps (${subToolStarts.length})`
                      : `Show sub-steps (${subToolStarts.length})`}
                  </button>
                  {subExpanded && (
                    <ul className="border-l-2 border-indigo-700 pl-3 space-y-1">
                      {subIterations.length > 0 && (
                        <li className="text-xs text-gray-500 italic">
                          {subIterations.length} iteration{subIterations.length !== 1 ? 's' : ''}
                        </li>
                      )}
                      {subToolStarts.map((s, i) => {
                        const result = s.call_id ? subToolResults.get(s.call_id) : undefined
                        const SubIcon = s.tool ? (TOOL_ICONS[s.tool] || Search) : Search
                        const subLabel = s.tool ? (TOOL_LABELS[s.tool] || s.tool) : 'tool'
                        return (
                          <li key={s.call_id || i} className="flex items-start gap-1 text-xs">
                            <SubIcon className="w-3 h-3 mt-0.5 text-emerald-400 flex-shrink-0" />
                            <span className="font-semibold text-gray-300">{subLabel}</span>
                            {s.args_preview && (
                              <span className="font-mono text-gray-500 truncate max-w-[180px]">
                                {s.args_preview}
                              </span>
                            )}
                            {result ? (
                              <Check className="w-3 h-3 text-gray-500 flex-shrink-0" />
                            ) : (
                              <span className="w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>
              )}
              {/* Original output payload */}
              {output && (
                <pre className="text-xs font-mono text-gray-300 whitespace-pre-wrap max-h-[300px] overflow-y-auto">
                  {output}
                </pre>
              )}
            </div>
          )}
        </div>
      )
    }
    ```

    2) Update `frontend/src/components/MessageBubble.tsx`:

    The local ToolEvent interface (lines 5-12) duplicates the one in useChat.ts. Add `subEvents?: SubEvent[]` to it OR (preferred) replace it with `import type { ToolEvent } from '../hooks/useChat'`. If replacing:
    - Add at top: `import type { ToolEvent } from '../hooks/useChat'`
    - Remove the local `interface ToolEvent { ... }` block
    - The `Props` interface continues to use `ToolEvent[]` — no change

    In the `<ToolCallCard ... />` JSX (around line 44), add `subEvents={t.subEvents}` after the existing props:
    ```tsx
    <ToolCallCard
      key={t.call_id || i}
      tool={t.tool}
      args_preview={t.args_preview}
      output={t.output}
      call_id={t.call_id}
      subagent={t.subagent}
      status={t.status}
      subEvents={t.subEvents}
    />
    ```
  </action>
  <acceptance_criteria>
    - `grep -n "subEvents" frontend/src/components/ToolCallCard.tsx` returns ≥4 matches
    - `grep -n "explore_kb" frontend/src/components/ToolCallCard.tsx` returns ≥3 matches (TOOL_LABELS, TOOL_ICONS, progress check)
    - `grep -n "Compass" frontend/src/components/ToolCallCard.tsx` returns a match
    - `grep -n "Exploring" frontend/src/components/ToolCallCard.tsx` returns a match (progress indicator)
    - `grep -n "EXPLORER_MAX_TOOL_CALLS" frontend/src/components/ToolCallCard.tsx` returns ≥2 matches (constant + usage) — W4 fix, ensures denominator is tool-call budget not iteration cap
    - `grep -c "/6" frontend/src/components/ToolCallCard.tsx` returns 0 — no stale iteration-cap denominator
    - `grep -n "subEvents={" frontend/src/components/MessageBubble.tsx` returns a match
    - `grep -n "import type { ToolEvent }" frontend/src/components/MessageBubble.tsx` returns a match (preferred shared type) OR local interface includes `subEvents?: SubEvent[]`
    - `cd frontend && npx tsc --noEmit -p tsconfig.app.json` exits 0
    - `cd frontend && npm run lint` exits 0
    - `cd frontend && npm run build` exits 0 (production build proves the React tree is valid)
  </acceptance_criteria>
  <verify>
    <automated>cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run lint && npm run build</automated>
  </verify>
  <done>
    ToolCallCard renders nested sub-event list with collapsible UI for explore_kb; progress indicator `Exploring... (X/10)` uses tool-call axis on both numerator and denominator (W4 fix); MessageBubble forwards subEvents; TS + lint + production build all clean.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Human verification — explorer UI flow end-to-end</name>
  <read_first>
    - .planning/phases/05-explorer-sub-agent/05-VALIDATION.md (Manual-Only Verifications table)
    - .planning/phases/05-explorer-sub-agent/05-RESEARCH.md (lines 707-714 — Golden UAT queries)
  </read_first>
  <files></files>
  <action>
    Backend + frontend dev servers must be running.
    1) `cd backend && venv/Scripts/python -m uvicorn main:app --reload --port 8000`
    2) `cd frontend && npm run dev`
    3) Open the chat UI in browser (http://localhost:5173) and login with test creds (ragtest1@gmail.com / testpass123).
  </action>
  <what-built>
    Explorer sub-agent visible in the chat UI:
    - explore_kb shows up as an indigo Compass-icon ToolCallCard when triggered
    - During run: card header shows "Exploring... (X/10)" progress (X = tool calls started so far; 10 = explorer_max_tool_calls budget) and a spinner
    - Expanding the card reveals a "Show sub-steps (N)" toggle
    - Expanding sub-steps shows nested kb_tree / kb_ls / kb_read entries with their args_preview, each with running spinner -> check icon as they complete
    - When the explorer finishes: parent card shows the final ExplorerResult JSON in its output area, parent agent's text response appears below
  </what-built>
  <how-to-verify>
    Run the four golden UAT queries in sequence in the chat UI. Confirm each behaves as described.

    1) **Folder summary (EXPL-02):**
       Type: `Summarize the Catan folder.`
       Expected:
       - Indigo "Explore KB" card appears (compass icon, mode="summarize")
       - "Exploring... (X/10)" header updates as sub-steps run (numerator monotonically increases with each kb_* sub-call)
       - Expand card -> "Show sub-steps (≥2)" -> verify kb_tree and kb_read entries appear with check icons
       - Final response below card mentions Catan rules in coherent multi-paragraph synthesis

    2) **Find similar (EXPL-03):**
       Type: `What games are like Azul?`
       Expected:
       - Indigo "Explore KB" card with mode="find_similar"
       - At least 2 candidate games surface in the response
       - Each has a relevance/reasoning sentence (NOT just a name list)

    3) **Multi-step search (EXPL-01):**
       Type: `Find all games in the KB that have tile placement mechanics.`
       Expected:
       - Explore card with mode="deep_search" or "find_similar"
       - At least 2 games surfaced, each with a short justification
       - Sub-steps include kb_grep and at least one of kb_ls/kb_tree

    4) **Recommendation (EXPL-04):**
       Mention a game in chat history first ("Tell me about Catan"), then in a follow-up: `What else might I like?`
       Expected:
       - Parent agent calls explore_kb with mode="find_similar" or "deep_search" and a query that mentions Catan (resolved seed pattern)
       - Recommendations come back

    Then verify EXPL-05 budget cap behaves gracefully:

    5) **Budget cap (EXPL-05):**
       Stop the backend, set `EXPLORER_MAX_ITERATIONS=2` in `.env`, restart, run query 1 again.
       Expected: card still completes; response either (a) acknowledges incomplete exploration or (b) returns a partial summary; no crash, no hung spinner. Reset env var afterward.

    For each query, also confirm in browser DevTools Network tab:
    - The SSE stream contains rows with `"type":"sub_event"` interleaved between the parent's tool_start and tool_result
    - Each sub_event row carries `"parent_call_id":"<the parent call id>"`
  </how-to-verify>
  <acceptance_criteria>
    - All 5 manual scenarios produce the documented behavior
    - Progress indicator displays `Exploring... (X/10)` during run (not `/6`)
    - No console errors in browser DevTools
    - No backend tracebacks during normal queries (budget exhaustion is allowed for scenario 5 only)
    - User explicitly approves with "approved" or describes any issues found
  </acceptance_criteria>
  <resume-signal>Type "approved" if all five queries behaved correctly, or describe issues per scenario number.</resume-signal>
  <done>
    User has confirmed the explorer renders progress in real time with the correct tool-call-axis denominator, the four functional modes work, and the budget cap degrades gracefully.
  </done>
</task>

</tasks>

<verification>
- TypeScript + ESLint + production build all green for the frontend
- Manual UAT confirms phase success criteria #4 (progress streamed) is met
- Manual UAT confirms phase success criteria #1, #2, #3 produce visible, well-formed responses
- Manual UAT confirms phase success criteria #5 (budget cap) degrades gracefully
- Progress indicator denominator matches numerator axis (both tool-call counts) — W4 fix
</verification>

<success_criteria>
- All 5 phase success criteria observable end-to-end via the live UI
- EXPL-04 (frontend rendering) and EXPL-06 (SSE parsing) PROVED visually
- No regressions to existing tool cards (analyze_document, kb_*, search_documents) — verified by checking they still render correctly during the UAT runs
</success_criteria>

<output>
After completion, create `.planning/phases/05-explorer-sub-agent/05-04-SUMMARY.md` documenting:
- Final SubEvent and ToolEvent type shapes
- ToolCallCard prop interface (with subEvents)
- `EXPLORER_MAX_TOOL_CALLS` constant location + backend sync requirement
- Known limitation: subEvents are NOT persisted to DB; on page reload, the parent card shows only the final synthesis (a Phase 6 enhancement could persist the sub-event log if useful)
- UAT results for the five golden queries (one-line verdict per scenario)
- Any UI tweaks made during UAT (e.g., progress indicator copy adjustments)
</output>
