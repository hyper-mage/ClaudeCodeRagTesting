import type { ReactElement, ReactNode } from 'react'
import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import { vi } from 'vitest'
import { ToastProvider } from '../contexts/ToastContext'

/**
 * Shared component-test helpers for Phase 999.1.
 *
 * Imported by Plans 01, 02, and 03 — keep generic. Provides:
 *   - renderWithProviders(ui, { isAnon? }) wrapping ToastProvider; auth is supplied via the
 *     module-level mock (see authMockState / makeAuthMock) so components that call useAuth()
 *     get a controllable `isAnon` without driving the live Supabase session.
 *   - ProvidersWrapper — the same tree as a component, for renderHook({ wrapper }).
 *   - mockSSEResponse(chunks) → a Response-like object whose body.getReader() yields the
 *     given SSE `data: ...` lines then signals done (for apiStream mocks).
 *   - makeApiMock() / makeAuthMock() → vi.fn-based module mocks to drop into a test file's
 *     `vi.mock('../lib/api', ...)` / `vi.mock('../contexts/AuthContext', ...)` factory.
 *
 * NOTE on hoisting: vi.mock is hoisted per test file, so a test that needs the api or auth
 * module mocked must call vi.mock itself with these factories. The auth value is read from the
 * shared authMockState object, which renderWithProviders/ProvidersWrapper update per render.
 */

// ---------------------------------------------------------------------------
// Auth mock state (consumed by makeAuthMock; set by the providers below)
// ---------------------------------------------------------------------------

export const authMockState: { isAnon: boolean } = { isAnon: false }

export function setMockAuth(next: { isAnon?: boolean }) {
  if (next.isAnon !== undefined) authMockState.isAnon = next.isAnon
}

export function resetMockAuth() {
  authMockState.isAnon = false
}

/**
 * Factory for `vi.mock('../contexts/AuthContext', () => makeAuthMock())`.
 * Returns a useAuth() that reflects the live authMockState (settable via setMockAuth or the
 * `isAnon` option on renderWithProviders) and a pass-through AuthProvider so existing imports
 * keep type-checking. No Supabase session is touched.
 */
export function makeAuthMock() {
  return {
    useAuth: () => ({
      user: null,
      session: null,
      loading: false,
      signOut: async () => {},
      isAnon: authMockState.isAnon,
    }),
    AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  }
}

// ---------------------------------------------------------------------------
// Provider tree
// ---------------------------------------------------------------------------

interface ProviderOptions {
  isAnon?: boolean
}

export function ProvidersWrapper({ children }: { children: ReactNode }) {
  // Pure wrapper — auth state is set imperatively before render (see renderWithProviders /
  // setMockAuth), never mutated during render.
  return <ToastProvider>{children}</ToastProvider>
}

/**
 * Render `ui` inside ToastProvider with a controllable `isAnon` (effective when the test
 * mocks ../contexts/AuthContext via makeAuthMock). Use for components/hooks that consume
 * useToast() and/or useAuth().
 */
export function renderWithProviders(
  ui: ReactElement,
  options: ProviderOptions & Omit<RenderOptions, 'wrapper'> = {}
): RenderResult {
  const { isAnon = false, ...rtlOptions } = options
  // Set the shared auth state imperatively, outside the render path.
  setMockAuth({ isAnon })
  return render(ui, {
    wrapper: ({ children }) => <ProvidersWrapper>{children}</ProvidersWrapper>,
    ...rtlOptions,
  })
}

// ---------------------------------------------------------------------------
// SSE / api mocks
// ---------------------------------------------------------------------------

/**
 * Build a minimal Response-like object whose body.getReader() yields the given
 * chunks (already-formatted SSE lines, e.g. `data: {"text":"hello"}`) one read at
 * a time, then signals done. Each chunk is newline-terminated so the consumer's
 * line-splitting in useChat sees complete `data: ` lines.
 */
export function mockSSEResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const queue = chunks.map(c => encoder.encode(c.endsWith('\n') ? c : `${c}\n`))
  let i = 0

  const reader: ReadableStreamDefaultReader<Uint8Array> = {
    read: async () => {
      if (i < queue.length) {
        const value = queue[i]
        i += 1
        return { done: false, value }
      }
      return { done: true, value: undefined }
    },
    releaseLock: () => {},
    cancel: async () => {},
    closed: Promise.resolve(undefined),
  }

  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => reader,
    },
  } as unknown as Response
}

/**
 * Returns a fresh pair of vi.fn mocks for the api boundary. Use inside a test
 * file's `vi.mock('../lib/api', () => makeApiMock())` factory, then import the
 * mocked apiFetch/apiStream and assert on them.
 */
export function makeApiMock() {
  return {
    apiFetch: vi.fn(),
    apiStream: vi.fn(),
  }
}
