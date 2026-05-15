# Deferred Items — Phase 06.1

Pre-existing issues discovered during execution that are out of scope for
the current plan (per execute-plan SCOPE BOUNDARY rule).

## Pre-existing ESLint Errors (not introduced by Plan 06.1-01)

Surfaced when running `npm run lint` after Task 2 (06.1-01). All four errors
exist on `master` prior to Plan 06.1-01 and live in files this plan does
NOT touch.

| File | Line | Rule | Description |
|------|------|------|-------------|
| `frontend/src/components/FileUpload.tsx` | 5:56 | `@typescript-eslint/no-explicit-any` | Unexpected `any` in props type |
| `frontend/src/contexts/AuthContext.tsx` | 45:17 | `react-refresh/only-export-components` | Mixes `useAuth` hook export with `AuthProvider` component |
| `frontend/src/contexts/ToastContext.tsx` | 96:17 | `react-refresh/only-export-components` | Mixes `useToast` hook export with `ToastProvider` component |
| `frontend/src/pages/ChatPage.tsx` | 29:5 | `react-hooks/set-state-in-effect` | `loadThreads()` called synchronously in `useEffect` |

Status: not fixed. These predate Plan 06.1-01 and are unrelated to mobile
responsiveness. Track for a dedicated lint-cleanup plan in a future phase.

## Mobile UAT (12-point) — verify on deployed CF Pages URL after push

**Owner:** end user
**Why deferred:** During Plan 06.1-02 Task 3 human-verify checkpoint, local UAT
was found impractical — the local `.env` Supabase project URL did not match the
prod Supabase project that the deployed app is wired to, making local mobile
emulation a non-representative test of what real users will see. Decision:
defer the entire 12-point checklist + 2 a11y sanity checks to run against
`https://boardgame-rag-prod.pages.dev` once Cloudflare Pages auto-deploys
the merged `master` branch.

**Re-run target:** `https://boardgame-rag-prod.pages.dev` after CF Pages
auto-deploy completes from this branch's push to `master`.

**Test credentials:** `ragtest1@gmail.com` / `testpass123` (per CLAUDE.md).

### 12-point success-criteria checklist (from `06.1-CONTEXT.md`)

- [ ] 1. **375px chat viewport intact** — `/` shows chat input at the bottom, message area edge-to-edge, no horizontal scrollbar.
- [ ] 2. **Hamburger opens drawer** — Tap top-left hamburger. Drawer slides in from the left over ~250ms; backdrop fades in.
- [ ] 3. **Drawer composition** — Drawer shows three nav icons in a row at the top (Chat highlighted; Documents; Logout) and the thread list below (`+ New Chat` button + threads, or empty state).
- [ ] 4. **Tap thread closes drawer + activates** — Tap a thread row. Drawer slides out; the tapped thread becomes active in the chat panel.
- [ ] 5. **Backdrop tap closes drawer** — Open drawer, tap the dimmed area to the right of the panel. Drawer closes.
- [ ] 6. **Swipe-left closes drawer** — Open drawer, drag the panel surface left ~100px and release. Drawer closes.
- [ ] 7. **Escape key closes drawer** — Open drawer, press Escape. Drawer closes; focus returns to the hamburger button.
- [ ] 8. **Body scroll lock** — Open drawer, attempt to scroll the dimmed backdrop area. Page underneath does NOT scroll. Close drawer, scroll resumes.
- [ ] 9. **Desktop ≥768px unchanged** — Resize window to 1024px. Confirm: IconSidebar (56px) + ThreadSidebar (256px) + chat content render side-by-side; NO hamburger visible.
- [ ] 10. **DocumentsPage mobile** — At 375px, visit `/documents`. Hamburger top-left. Tap → drawer opens with nav row + folder tree. Tap a folder → drawer closes, folder selected, content panel shows that folder's contents at full width.
- [ ] 11. **No new npm deps** — `git diff frontend/package.json frontend/package-lock.json` is empty (verify on the deployed commit).
- [ ] 12. **iOS Safari dynamic viewport** — On a real iOS Safari 17+ device: open drawer while URL bar visible. Confirm drawer bottom edge reaches the bottom of the visible viewport — no gap where Safari's hidden chrome would be.

### A11y sanity checks

- [ ] A1. **A11y inspector** — In DevTools Accessibility panel with drawer open, confirm the drawer has `role="dialog"`, `aria-modal="true"`, `aria-label="Navigation and threads"`. Hamburger has `aria-expanded="true"` when open. Close button has `aria-label="Close menu"`. Hamburger has `aria-label="Open menu"`.
- [ ] A2. **Tab focus trap** — With drawer open, press Tab repeatedly. Focus cycles only among elements inside the drawer (close X, nav icons, `+ New Chat`, thread rows). It does NOT escape to the page underneath.

### Pass/fail protocol

Reply "approved" once all 12 checks + 2 a11y checks PASS, or list failing
criterion numbers with observed behavior so the executor can fix and re-verify.
Only after deployed UAT passes should Phase 06.1 be marked verified.
