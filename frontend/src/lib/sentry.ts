// OBS-01: Sentry init singleton for the frontend bundle.
//
// Mirrors the shape of ./supabase.ts:
//   - reads env via import.meta.env at module top
//   - no React, no JSX, no default export
//   - module is imported for side effects from main.tsx BEFORE createRoot
//
// PII scrub contract (CONTEXT D-1 + threat model T-07-01..03,06):
//   - Authorization request headers (full JWTs) are redacted in events and breadcrumbs
//   - any auto-attached event.user is stripped (identity attachment is forbidden — D-1)
//   - console breadcrumbs that mention the supabase auth-token localStorage key
//     (sb-<ref>-auth-token) are dropped entirely
//
// Quota envelope (Pitfall 8): tracesSampleRate 0.1, no replay integration.
//
// When VITE_SENTRY_DSN is unset (local dev, CI without DSN), this module is a no-op
// so dev builds never pollute the prod Sentry project (mirrors backend/services/tracing.py
// early-return pattern).
//
// Release tagging is owned by @sentry/vite-plugin at build time
// (release.name = process.env.CF_PAGES_COMMIT_SHA); do NOT add a release field below.

import * as Sentry from '@sentry/react'

const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined

if (dsn) {
  Sentry.init({
    dsn,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.consoleLoggingIntegration({ levels: ['log', 'warn', 'error'] }),
    ],
    tracesSampleRate: 0.1,
    enableLogs: true,
    beforeSend(event: Sentry.ErrorEvent) {
      const headers = event.request?.headers as Record<string, string> | undefined
      if (headers) {
        for (const key of Object.keys(headers)) {
          if (key.toLowerCase() === 'authorization') {
            headers[key] = '[redacted]'
          }
        }
      }
      if (event.user) {
        event.user = { ip_address: '{{auto}}' }
      }
      return event
    },
    beforeBreadcrumb(breadcrumb: Sentry.Breadcrumb) {
      if (breadcrumb.category === 'fetch' || breadcrumb.category === 'xhr') {
        const data = breadcrumb.data as Record<string, unknown> | undefined
        const reqHeaders = data?.request_headers as Record<string, string> | undefined
        if (reqHeaders) {
          for (const key of Object.keys(reqHeaders)) {
            if (key.toLowerCase() === 'authorization') {
              reqHeaders[key] = '[redacted]'
            }
          }
        }
      }
      if (
        breadcrumb.category === 'console' &&
        typeof breadcrumb.message === 'string' &&
        /sb-[^-]+-auth-token/.test(breadcrumb.message)
      ) {
        return null
      }
      return breadcrumb
    },
  })
}

export { Sentry }
