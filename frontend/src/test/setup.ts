/// <reference types="vitest/globals" />
import '@testing-library/jest-dom'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// Unmount React trees between tests so component state never leaks across cases.
afterEach(() => {
  cleanup()
})

// useChat.ts calls crypto.randomUUID() for optimistic message ids (lines 63/71).
// jsdom does not always expose it; polyfill so the hook runs under tests.
if (typeof globalThis.crypto === 'undefined') {
  // Minimal shim — only the surface our code touches.
  ;(globalThis as { crypto?: Crypto }).crypto = {} as Crypto
}
if (typeof globalThis.crypto.randomUUID !== 'function') {
  let counter = 0
  ;(globalThis.crypto as { randomUUID: () => `${string}-${string}-${string}-${string}-${string}` }).randomUUID =
    () => {
      counter += 1
      const hex = counter.toString(16).padStart(12, '0')
      return `00000000-0000-4000-8000-${hex}` as `${string}-${string}-${string}-${string}-${string}`
    }
}
