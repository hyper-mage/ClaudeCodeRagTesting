import { describe, it, expect, vi, beforeEach } from 'vitest'
import { applyStoredTheme } from '../lib/themeBootstrap'

/**
 * Unit tests for applyStoredTheme — the jsdom-testable source of truth mirrored by the
 * inline <head> script in index.html (Task 1, Plan 13-05, PREF-02 / D-02).
 *
 * Contract (13-05-PLAN <behavior>):
 *   - storage.theme === "dark"            → root gets "dark", returns "dark"
 *   - storage.theme === "light"           → root loses "dark", returns "light"
 *   - theme absent + matchMedia dark      → root gets "dark"   (system fallback)
 *   - theme absent + matchMedia light     → root loses "dark"  (system fallback)
 *   - any non-"dark" stored value (e.g. "purple") normalizes to light (T-13-THEME defensive)
 *   - jsdom-safe: never crashes when matchMedia is a stub
 */

function fakeRoot(): HTMLElement {
  const el = document.createElement('html')
  return el
}

function mqlStub(matches: boolean) {
  // Mirrors the window.matchMedia signature surface applyStoredTheme touches.
  return vi.fn((_query: string) => ({ matches }) as MediaQueryList)
}

describe('applyStoredTheme', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('adds the dark class and returns "dark" when storage.theme === "dark"', () => {
    const root = fakeRoot()
    const resolved = applyStoredTheme({ theme: 'dark' }, root, mqlStub(false))
    expect(root.classList.contains('dark')).toBe(true)
    expect(resolved).toBe('dark')
  })

  it('removes the dark class and returns "light" when storage.theme === "light"', () => {
    const root = fakeRoot()
    root.classList.add('dark') // start dark to prove it is removed
    const resolved = applyStoredTheme({ theme: 'light' }, root, mqlStub(true))
    expect(root.classList.contains('dark')).toBe(false)
    expect(resolved).toBe('light')
  })

  it('falls back to the system preference (dark) when theme is absent', () => {
    const root = fakeRoot()
    const mql = mqlStub(true)
    const resolved = applyStoredTheme({}, root, mql)
    expect(mql).toHaveBeenCalledWith('(prefers-color-scheme: dark)')
    expect(root.classList.contains('dark')).toBe(true)
    expect(resolved).toBe('dark')
  })

  it('falls back to the system preference (light) when theme is absent', () => {
    const root = fakeRoot()
    const resolved = applyStoredTheme({}, root, mqlStub(false))
    expect(root.classList.contains('dark')).toBe(false)
    expect(resolved).toBe('light')
  })

  it('normalizes any non-"dark" stored value to light (defensive, T-13-THEME)', () => {
    const root = fakeRoot()
    root.classList.add('dark')
    // "purple" is present, so the system fallback is NOT consulted; treated as not-dark.
    const resolved = applyStoredTheme({ theme: 'purple' }, root, mqlStub(true))
    expect(root.classList.contains('dark')).toBe(false)
    expect(resolved).toBe('light')
  })

  it('is jsdom-safe — does not crash when matchMedia is a bare stub and theme is present', () => {
    const root = fakeRoot()
    expect(() => applyStoredTheme({ theme: 'dark' }, root, mqlStub(false))).not.toThrow()
  })
})
