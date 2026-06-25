import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DeprecationNotice from './DeprecationNotice'

// The server-composed SC#4 copy (UI-SPEC § Copywriting Contract). The component renders the
// content VERBATIM as escaped React text — it must not interpolate or sanitize beyond escaping.
const NOTICE_COPY =
  'Model "anthropic/claude-2" is no longer available — using openai/gpt-4o instead.'

describe('DeprecationNotice (SC#4 / D-06 — quiet persisted system line)', () => {
  it('renders the content string verbatim as text', () => {
    render(<DeprecationNotice content={NOTICE_COPY} />)
    expect(screen.getByText(NOTICE_COPY)).toBeInTheDocument()
  })

  it('renders a muted Info icon (lucide svg) alongside the caption', () => {
    const { container } = render(<DeprecationNotice content={NOTICE_COPY} />)
    // lucide-react renders an <svg> — the quiet Info marker is the only icon in this line.
    const svg = container.querySelector('svg')
    expect(svg).toBeTruthy()
  })

  it('is NOT a message bubble (no blue-600 user bubble / no rounded-lg chat bubble)', () => {
    const { container } = render(<DeprecationNotice content={NOTICE_COPY} />)
    // MessageBubble uses rounded-lg + bg-blue-600 (user) / bg-gray-800 (assistant). The notice
    // is a flat centered divider line, never a bubble.
    expect(container.querySelector('[class*="rounded-lg"]')).toBeNull()
    expect(container.querySelector('[class*="bg-blue-600"]')).toBeNull()
  })

  it('is NOT alarming — uses no red/amber/destructive classes', () => {
    const { container } = render(<DeprecationNotice content={NOTICE_COPY} />)
    const html = container.innerHTML
    expect(html).not.toMatch(/red-/)
    expect(html).not.toMatch(/amber-/)
    expect(html).not.toMatch(/destructive/)
  })

  it('does not use dangerouslySetInnerHTML (XSS — T-13-XSS-NOTICE): a script-like content stays inert text', () => {
    const malicious = '<img src=x onerror=alert(1)>'
    const { container } = render(<DeprecationNotice content={malicious} />)
    // Rendered as escaped text content, never as a live <img> element.
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText(malicious)).toBeInTheDocument()
  })
})
