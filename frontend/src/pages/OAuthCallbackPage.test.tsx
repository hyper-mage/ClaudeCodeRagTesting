import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { ReactElement } from 'react'
import { renderWithProviders, makeAuthMock, resetMockAuth } from '../test/utils'
import OAuthCallbackPage from './OAuthCallbackPage'
import { apiFetch } from '../lib/api'
import { startOpenRouterConnect } from '../lib/pkce'

// Mock the I/O boundary — no real backend, no network.
vi.mock('../lib/api', () => ({
  apiFetch: vi.fn(),
  apiStream: vi.fn(),
}))

// Shared providers convention (ChatPage.test.tsx analog) — pass-through auth.
vi.mock('../contexts/AuthContext', () => makeAuthMock())

// Spyable PKCE launcher — the real one redirects via window.location.assign.
vi.mock('../lib/pkce', () => ({
  startOpenRouterConnect: vi.fn(),
}))

// The page navigates imperatively; ChatPage.test.tsx never asserts navigation, so per
// the plan we mock useNavigate (keeping the rest of react-router-dom real for MemoryRouter).
const { mockNavigate } = vi.hoisted(() => ({ mockNavigate: vi.fn() }))
vi.mock('react-router-dom', async importOriginal => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

const mockedApiFetch = vi.mocked(apiFetch)
const mockedStartConnect = vi.mocked(startOpenRouterConnect)

// Locked toast strings (UI-SPEC §Copywriting) — exact copy incl. the em-dash; ${label}
// (display name ?? id) is the ONLY interpolation.
const TOAST_THREAD = (label: string) => `Connected — ${label} is set for this chat.`
const TOAST_DEFAULT = (label: string) => `Connected — ${label} is now your default model.`
const TOAST_APPLY_FAILED = "Connected, but your model pick didn't apply — pick it again."
const TOAST_LEGACY = 'OpenRouter connected.'

const STASH_KEY = 'or_pending_selection'
const CALLBACK_PATH = '/settings/openrouter/callback'
const CALLBACK_QUERY = '?code=code-123&state=state-xyz'

interface RouteConfig {
  exchange?: () => unknown
  models?: () => unknown
  patchThread?: () => unknown
  putPreferences?: () => unknown
}

// Route apiFetch by (path, options). Defaults: exchange succeeds; the catalog fetch
// REJECTS (label falls back to the raw model id); PATCH/PUT succeed.
function routeApiFetch(config: RouteConfig = {}) {
  const {
    exchange = () => ({ connected: true }),
    models = () => {
      throw new Error('API error 500: no catalog')
    },
    patchThread = () => ({}),
    putPreferences = () => ({}),
  } = config

  mockedApiFetch.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path === '/api/keys/openrouter/exchange') return exchange()
    if (path === '/api/models') return models()
    if (/^\/api\/threads\/[^/]+$/.test(path) && options?.method === 'PATCH') return patchThread()
    if (path === '/api/preferences' && options?.method === 'PUT') return putPreferences()
    return null
  })
}

// The page reads code/state from window.location.search (NOT router state — D-07),
// so seed the real jsdom URL alongside the sessionStorage PKCE pair.
function seedPkce() {
  sessionStorage.setItem('or_pkce_verifier', 'verifier-abc')
  sessionStorage.setItem('or_pkce_state', 'state-xyz')
  window.history.replaceState(null, '', `${CALLBACK_PATH}${CALLBACK_QUERY}`)
}

function seedStash(stash: Record<string, unknown> | string) {
  sessionStorage.setItem(STASH_KEY, typeof stash === 'string' ? stash : JSON.stringify(stash))
}

function renderCallbackPage() {
  return renderWithProviders(
    (
      <MemoryRouter initialEntries={[`${CALLBACK_PATH}${CALLBACK_QUERY}`]}>
        <OAuthCallbackPage />
      </MemoryRouter>
    ) as ReactElement
  )
}

describe('OAuthCallbackPage pending-selection resume (D-02, one-shot)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetMockAuth()
    sessionStorage.clear()
    seedPkce()
    routeApiFetch()
  })

  afterEach(() => {
    sessionStorage.clear()
  })

  it('Test 1: thread stash — PATCH /api/threads/{id}, combined toast with catalog display name, stash removed, navigate to returnTo', async () => {
    routeApiFetch({
      models: () => [
        { id: 'meta-llama/llama-3.3-70b-instruct', name: 'Llama 3.3 70B', is_free: true },
      ],
    })
    seedStash({
      kind: 'thread',
      modelId: 'meta-llama/llama-3.3-70b-instruct',
      threadId: 't1',
      returnTo: '/',
    })
    renderCallbackPage()

    // Combined toast fires with the resolved display name — NOT the legacy toast.
    expect(await screen.findByText(TOAST_THREAD('Llama 3.3 70B'))).toBeInTheDocument()
    expect(screen.queryByText(TOAST_LEGACY)).not.toBeInTheDocument()

    // The exchange fired…
    expect(
      mockedApiFetch.mock.calls.some(([p]) => p === '/api/keys/openrouter/exchange')
    ).toBe(true)
    // …and the original pick applied to the thread.
    const patchCall = mockedApiFetch.mock.calls.find(
      ([p, o]) => p === '/api/threads/t1' && (o as RequestInit | undefined)?.method === 'PATCH'
    )
    expect(patchCall).toBeTruthy()
    expect((patchCall![1] as RequestInit).body).toBe(
      JSON.stringify({ model: 'meta-llama/llama-3.3-70b-instruct' })
    )

    // One-shot: the stash is gone.
    expect(sessionStorage.getItem(STASH_KEY)).toBeNull()
    // Navigation went to the stash's allowlisted returnTo.
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('Test 2: default stash — PUT /api/preferences, label falls back to the raw id when the catalog fetch fails, navigate /settings', async () => {
    // routeApiFetch default: /api/models rejects → label = raw modelId (silent fallback).
    seedStash({ kind: 'default', modelId: 'openai/gpt-4o-mini', returnTo: '/settings' })
    renderCallbackPage()

    expect(await screen.findByText(TOAST_DEFAULT('openai/gpt-4o-mini'))).toBeInTheDocument()
    expect(screen.queryByText(TOAST_LEGACY)).not.toBeInTheDocument()

    const putCall = mockedApiFetch.mock.calls.find(
      ([p, o]) => p === '/api/preferences' && (o as RequestInit | undefined)?.method === 'PUT'
    )
    expect(putCall).toBeTruthy()
    expect((putCall![1] as RequestInit).body).toBe(
      JSON.stringify({ default_model: 'openai/gpt-4o-mini' })
    )

    expect(sessionStorage.getItem(STASH_KEY)).toBeNull()
    expect(mockNavigate).toHaveBeenCalledWith('/settings', { replace: true })
  })

  it('Test 3: apply failure — stash removed BEFORE the apply, warning toast, navigation still happens, failure screen never renders', async () => {
    let stashAtApplyTime: string | null = 'sentinel-not-checked'
    routeApiFetch({
      patchThread: () => {
        stashAtApplyTime = sessionStorage.getItem(STASH_KEY)
        throw new Error('API error 500: boom')
      },
    })
    seedStash({ kind: 'thread', modelId: 'm-1', threadId: 't1', returnTo: '/' })
    renderCallbackPage()

    expect(await screen.findByText(TOAST_APPLY_FAILED)).toBeInTheDocument()
    // removeItem ran BEFORE the PATCH — one-shot even though the apply threw (Pitfall 6).
    expect(stashAtApplyTime).toBeNull()
    expect(sessionStorage.getItem(STASH_KEY)).toBeNull()
    // Still navigated — the connection itself succeeded.
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
    // The failure screen (role=alert) never rendered for an apply error.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText(TOAST_LEGACY)).not.toBeInTheDocument()
  })

  it("Test 4: no stash — legacy behavior unchanged: 'OpenRouter connected.' toast → /settings", async () => {
    renderCallbackPage()

    expect(await screen.findByText(TOAST_LEGACY)).toBeInTheDocument()
    expect(mockNavigate).toHaveBeenCalledWith('/settings', { replace: true })
    // No apply calls fired.
    expect(mockedApiFetch.mock.calls.some(([p]) => p === '/api/preferences')).toBe(false)
    expect(
      mockedApiFetch.mock.calls.some(([p]) => /^\/api\/threads\//.test(p as string))
    ).toBe(false)
  })

  it('Test 5: malformed stash JSON — behaves as the no-stash legacy path (no crash) and still consumes the stash', async () => {
    seedStash('{not-json!!!')
    renderCallbackPage()

    expect(await screen.findByText(TOAST_LEGACY)).toBeInTheDocument()
    expect(mockNavigate).toHaveBeenCalledWith('/settings', { replace: true })
    // One-shot read: the unparseable stash does not linger for a later visit.
    expect(sessionStorage.getItem(STASH_KEY)).toBeNull()
    // No apply attempted.
    expect(mockedApiFetch.mock.calls.some(([p]) => p === '/api/preferences')).toBe(false)
  })

  it.each(['https://evil.example', '/other'])(
    'Test 6: returnTo %s is not allowlisted — apply still runs but navigation is forced to /settings',
    async returnTo => {
      seedStash({ kind: 'default', modelId: 'm-2', returnTo })
      renderCallbackPage()

      expect(await screen.findByText(TOAST_DEFAULT('m-2'))).toBeInTheDocument()
      expect(mockNavigate).toHaveBeenCalledWith('/settings', { replace: true })
      expect(mockNavigate).not.toHaveBeenCalledWith(returnTo, expect.anything())
    }
  )

  it("Test 7: failure screen — 'Back to settings' clears the pending stash", async () => {
    const user = userEvent.setup()
    // CSRF mismatch → the exchange never fires and the failure screen renders.
    sessionStorage.setItem('or_pkce_state', 'a-different-state')
    seedStash({ kind: 'thread', modelId: 'm-1', threadId: 't1', returnTo: '/' })
    renderCallbackPage()

    await screen.findByRole('alert')
    await user.click(screen.getByRole('button', { name: 'Back to settings' }))

    expect(sessionStorage.getItem(STASH_KEY)).toBeNull()
    expect(mockNavigate).toHaveBeenCalledWith('/settings')
  })

  it('Test 8: failure screen — Retry relaunches PKCE and preserves the pending stash', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem('or_pkce_state', 'a-different-state')
    const stash = { kind: 'thread', modelId: 'm-1', threadId: 't1', returnTo: '/' }
    seedStash(stash)
    renderCallbackPage()

    await screen.findByRole('alert')
    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(mockedStartConnect).toHaveBeenCalledTimes(1)
    expect(sessionStorage.getItem(STASH_KEY)).toBe(JSON.stringify(stash))
  })
})
