import { useState } from 'react'
import { Sun, Moon } from 'lucide-react'
import { applyStoredTheme } from '../lib/themeBootstrap'
import { apiFetch } from '../lib/api'

type Theme = 'light' | 'dark'

// LOCKED copy (UI-SPEC § Copywriting — theme toggle a11y labels). Do not paraphrase.
const LABEL = {
  toLight: 'Switch to light theme',
  toDark: 'Switch to dark theme',
} as const

/**
 * ThemeToggle — a NEUTRAL (not blue-600 accent) icon button that flips light/dark.
 *
 * Click order (D-02 — localStorage is the paint source of truth):
 *   1. write localStorage.theme = next   (so a reload paints the new theme flash-free)
 *   2. applyStoredTheme()                (reads the value just written, toggles <html>.dark)
 *   3. fire-and-forget PUT /api/preferences { theme } — a rejected request must NOT revert
 *      the already-applied class (the class is the source of truth; the server is best-effort).
 *
 * Initial state is read from the current <html> class (set by the index.html bootstrap) so the
 * control is consistent with first paint.
 */
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  )

  function toggle() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    try {
      localStorage.setItem('theme', next)
    } catch {
      // Private-mode / storage-disabled: still apply the class below so the UI responds.
    }
    applyStoredTheme() // reads the just-written value and toggles <html>.dark
    setTheme(next)
    // Best-effort server persist; never block the UI and never revert on failure.
    void apiFetch('/api/preferences', {
      method: 'PUT',
      body: JSON.stringify({ theme: next }),
    }).catch(() => {})
  }

  const isDark = theme === 'dark'
  // Sun while dark (action = go light); Moon while light (action = go dark).
  const label = isDark ? LABEL.toLight : LABEL.toDark
  const Icon = isDark ? Sun : Moon

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      aria-pressed={isDark}
      title={label}
      className="inline-flex h-11 w-11 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100"
    >
      <Icon size={20} aria-hidden="true" />
    </button>
  )
}
