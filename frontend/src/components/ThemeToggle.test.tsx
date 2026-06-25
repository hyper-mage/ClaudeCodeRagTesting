import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, makeApiMock } from '../test/utils'
import { apiFetch } from '../lib/api'
import ThemeToggle from './ThemeToggle'

// ThemeToggle fires a fire-and-forget PUT /api/preferences — mock the api boundary.
vi.mock('../lib/api', () => makeApiMock())
const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>

function putBody(call: number): unknown {
  return JSON.parse((mockApiFetch.mock.calls[call][1] as RequestInit).body as string)
}

describe('ThemeToggle (UI-SPEC LOCKED)', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue({})
    localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('reads its initial label from the <html> class — Sun/"Switch to light theme" when dark', async () => {
    const user = userEvent.setup()
    document.documentElement.classList.add('dark') // first paint = dark
    renderWithProviders(<ThemeToggle />)

    const btn = screen.getByRole('button', { name: 'Switch to light theme' })
    expect(btn).toHaveAttribute('aria-pressed', 'true')

    // Click flips the <html> class, writes localStorage, and fires the PUT with the new theme.
    await user.click(btn)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('theme')).toBe('light')
    expect(mockApiFetch).toHaveBeenCalledWith('/api/preferences', expect.objectContaining({ method: 'PUT' }))
    expect(putBody(0)).toEqual({ theme: 'light' })

    // Label now reflects the new (light) theme.
    expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('shows Moon/"Switch to dark theme" when light and persists dark on click', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ThemeToggle />) // no dark class = light

    const btn = screen.getByRole('button', { name: 'Switch to dark theme' })
    expect(btn).toHaveAttribute('aria-pressed', 'false')

    await user.click(btn)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(putBody(0)).toEqual({ theme: 'dark' })
  })

  it('is fire-and-forget: a rejected PUT does not throw or revert the applied class', async () => {
    const user = userEvent.setup()
    mockApiFetch.mockRejectedValue(new Error('network down'))
    document.documentElement.classList.add('dark')
    renderWithProviders(<ThemeToggle />)

    await user.click(screen.getByRole('button', { name: 'Switch to light theme' }))

    // Applied class + localStorage stand despite the rejected request.
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('theme')).toBe('light')
  })

  it('is a neutral control (not the blue-600 accent) and exposes aria-pressed', () => {
    document.documentElement.classList.add('dark')
    renderWithProviders(<ThemeToggle />)

    const btn = screen.getByRole('button', { name: 'Switch to light theme' })
    expect(btn).toHaveAttribute('aria-pressed')
    expect(btn.className).not.toContain('blue-600')
  })
})
