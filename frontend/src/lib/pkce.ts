// Web Crypto PKCE helpers for the OpenRouter OAuth round-trip.
//
// Source pattern: openrouter.ai OAuth docs (Phase 10 RESEARCH §Pattern 3) —
// there is no in-repo analog. Conventions follow sibling lib/ files
// (api.ts, supabase.ts): named exports only, no default export, no React
// import, camelCase functions, 2-space indent, single quotes, no semicolons.
//
// code_verifier + CSRF state live in sessionStorage (NOT localStorage) so a
// same-tab hard refresh on the callback succeeds (D-07) and the CSRF binding
// stays tab-scoped.

function base64url(bytes: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

export function randomString(len = 64): string {
  const arr = new Uint8Array(len)
  crypto.getRandomValues(arr)
  return base64url(arr.buffer).slice(0, len)
}

export async function challengeFromVerifier(verifier: string): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return base64url(hash)
}

// Generate a fresh verifier + CSRF state, persist BOTH to sessionStorage (not
// localStorage — D-07 hard-refresh + CSRF binding), then redirect to OpenRouter
// /auth with the S256 challenge. Shared by the SettingsPage Connect CTA and the
// OAuthCallbackPage Retry button so both run the identical PKCE init.
export async function startOpenRouterConnect(): Promise<void> {
  const verifier = randomString(64)
  const state = randomString(32)
  const challenge = await challengeFromVerifier(verifier)
  sessionStorage.setItem('or_pkce_verifier', verifier)
  sessionStorage.setItem('or_pkce_state', state)
  const callback = `${window.location.origin}/settings/openrouter/callback`
  window.location.assign(
    `https://openrouter.ai/auth?callback_url=${encodeURIComponent(callback)}` +
      `&code_challenge=${challenge}&code_challenge_method=S256&state=${state}`,
  )
}
