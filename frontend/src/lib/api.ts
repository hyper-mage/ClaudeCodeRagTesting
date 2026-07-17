import { supabase } from './supabase'
import type { Session } from '@supabase/supabase-js'

const API_BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

// Module-scoped session cache. buildHeaders() ran `await supabase.auth.getSession()` on
// EVERY apiFetch/apiStream — supabase-js v2 acquires a navigator LockManager lock per
// call (latency, worse with multiple tabs). We cache the session and read the token
// synchronously in the common path, falling back to getSession() only on cold start or
// near-expiry so we NEVER send an expired bearer.
let cachedSession: Session | null = null
let initialized = false

// Keeps the cache fresh on SIGNED_IN / SIGNED_OUT / TOKEN_REFRESHED / INITIAL_SESSION —
// so a logout drops the token (no Authorization header) and a refresh swaps in the new one.
supabase.auth.onAuthStateChange((_event, session) => {
  cachedSession = session
  initialized = true
})

async function buildHeaders(extra?: HeadersInit): Promise<Record<string, string>> {
  if (!initialized) {
    // First paint, before onAuthStateChange has fired: one-time synchronous-ish read.
    const { data } = await supabase.auth.getSession()
    cachedSession = data.session
    initialized = true
  } else if (
    cachedSession?.expires_at &&
    cachedSession.expires_at * 1000 - Date.now() < 60_000
  ) {
    // Token is at/near expiry — getSession() auto-refreshes; overwrite the cache so we
    // never attach an expired bearer (correctness guard).
    const { data } = await supabase.auth.getSession()
    cachedSession = data.session
  }
  const token = cachedSession?.access_token

  const headers: Record<string, string> = {
    ...(extra as Record<string, string> || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

/**
 * JSON-returning fetch helper.
 * Prefixes every path with VITE_API_BASE_URL (empty in dev -> Vite proxy; absolute Fly URL in prod).
 * Attaches Supabase bearer token when available.
 * Throws on non-2xx. Returns null for 204. Returns parsed JSON otherwise.
 *
 * Do NOT use for streaming endpoints — use apiStream for SSE.
 */
export async function apiFetch(path: string, options: RequestInit = {}) {
  const headers = await buildHeaders(options.headers)
  // Only set Content-Type for bodies that are not FormData (FormData sets its own boundary)
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
  }

  if (res.status === 204) return null
  return res.json()
}

/**
 * Streaming-aware fetch helper.
 * Prefixes path with VITE_API_BASE_URL. Attaches Supabase bearer token.
 * Returns the raw Response so the caller can read res.body.getReader() for SSE.
 * Throws on non-2xx (consumes body as text for the error message).
 *
 * Per D-06 — SSE chat in useChat.ts needs access to the raw Response body.
 */
export async function apiStream(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = await buildHeaders(options.headers)
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
  }
  return res
}
