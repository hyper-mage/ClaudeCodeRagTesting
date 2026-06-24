import { describe, it, expect } from 'vitest'

// Smoke test: proves the vitest + jsdom + setup pipeline boots and that the
// crypto.randomUUID polyfill from setup.ts is available under jsdom (useChat
// depends on it for optimistic message ids).
describe('test runner setup', () => {
  it('runs assertions', () => {
    expect(true).toBe(true)
  })

  it('exposes a working DOM (jsdom)', () => {
    const el = document.createElement('div')
    el.textContent = 'ok'
    expect(el.textContent).toBe('ok')
  })

  it('provides crypto.randomUUID returning a string', () => {
    const id = crypto.randomUUID()
    expect(typeof id).toBe('string')
    expect(id.length).toBeGreaterThan(0)
  })
})
