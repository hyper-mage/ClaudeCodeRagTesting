/**
 * Theme bootstrap — the testable source of truth for resolving + applying the active theme.
 *
 * The inline <head> script in index.html (which runs synchronously BEFORE the module bundle,
 * for flash-free first paint — D-02 / RESEARCH Pattern 4, Pitfall 5) is a tiny hand-written
 * mirror of the same boolean computed here. This module is unit-tested under jsdom; the inline
 * script is intentionally kept byte-for-byte equivalent in its boolean so first paint matches.
 *
 * Security (T-13-THEME): any stored value other than the literal "dark" is treated as light, so
 * a tampered localStorage.theme (e.g. "purple") cannot poison the pre-mount paint. The server
 * CHECK constraint + Pydantic Literal (Plans 01/03) bound the persisted value independently.
 */

type Theme = 'light' | 'dark'

/**
 * The slice of a storage object the bootstrap reads. `Storage` (the real localStorage type) is
 * accepted because it exposes string-indexed access; tests pass a plain `{ theme?: string }`.
 */
type ThemeStorage = { theme?: string } | Storage

type MatchMediaFn = (query: string) => { matches: boolean }

/**
 * Resolve and apply the active theme to the document root.
 *
 * isDark when storage.theme === "dark", OR (theme absent AND the system prefers dark).
 * Toggles the "dark" class on `root` and returns the resolved theme.
 *
 * Dependency-free and jsdom-safe: matchMedia is only consulted when no theme is stored, and
 * the caller-supplied `mql` is invoked through a guarded call so a missing/stub matchMedia
 * never throws.
 *
 * @param storage object exposing an optional `theme` (defaults to localStorage)
 * @param root    the element whose classList carries the "dark" class (defaults to <html>)
 * @param mql     a matchMedia-compatible function (defaults to window.matchMedia, bound)
 */
export function applyStoredTheme(
  storage: ThemeStorage = localStorage,
  root: HTMLElement = document.documentElement,
  mql: MatchMediaFn = (query: string) => window.matchMedia(query),
): Theme {
  const stored = readTheme(storage)
  const hasStored = stored !== undefined
  const prefersDark = !hasStored && systemPrefersDark(mql)
  const isDark = stored === 'dark' || prefersDark

  root.classList.toggle('dark', isDark)
  return isDark ? 'dark' : 'light'
}

/**
 * Read the stored theme as a string, or undefined when no value is stored. Handles both the
 * real `Storage` (getItem returns null when the key is absent) and a plain `{ theme?: string }`
 * test object. A null/absent value becomes undefined so the system fallback engages.
 */
function readTheme(storage: ThemeStorage): string | undefined {
  if (typeof (storage as Storage).getItem === 'function') {
    return (storage as Storage).getItem('theme') ?? undefined
  }
  return (storage as { theme?: string }).theme ?? undefined
}

/**
 * Guarded system-preference probe. Returns false (light) if matchMedia is unavailable or throws
 * (jsdom often lacks a real implementation) so the bootstrap can never crash first paint.
 */
function systemPrefersDark(mql: MatchMediaFn): boolean {
  try {
    return !!mql('(prefers-color-scheme: dark)')?.matches
  } catch {
    return false
  }
}
