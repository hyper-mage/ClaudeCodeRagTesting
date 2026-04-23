import { supabase } from './supabase'

const API_BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

async function buildHeaders(extra?: HeadersInit): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token

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
