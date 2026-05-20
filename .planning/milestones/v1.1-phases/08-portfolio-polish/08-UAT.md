---
status: complete
phase: 08-portfolio-polish
source:
  - 08-00-SUMMARY.md
  - 08-01-SUMMARY.md
  - 08-02-SUMMARY.md
  - 08-03-SUMMARY.md
  - 08-04-SUMMARY.md
  - 08-05-SUMMARY.md
  - 08-06-SUMMARY.md
  - 08-07-SUMMARY.md
started: "2026-05-20T10:35:00.000Z"
updated: "2026-05-20T10:50:00.000Z"
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Backend redeployed clean on Fly (Dockerfile changed in b5392f7). Machine boots without errors, /api/health returns 200, and a fresh anon Try-demo click successfully seeds the welcome thread + D&D sample doc (proves the data/ bundle fix holds on a cold container).
result: pass

### 2. Try-demo anon onboarding
expected: Login page shows "Try the demo" CTA above the email form. Clicking it mints an anonymous session, seeds a "Welcome to the demo" thread + D&D 5e quick-reference doc, and lands the user in chat — no signup required.
result: pass

### 3. Demo identity pill
expected: While in an anon demo session, an amber "Demo" pill is visible in the sidebar (desktop) and mobile top bar. Signing in as a permanent user shows no pill.
result: pass

### 4. Graceful chat error + retry
expected: When the LLM upstream fails, the chat shows an in-thread red error bubble + a 4s toast, and a Retry button re-sends the message with no orphan/duplicate assistant rows in the thread.
result: pass

### 5. shields.io badges live
expected: README badge row renders two live badges — UptimeRobot uptime ratio and GitHub last-commit — both showing real values, not "invalid".
result: pass

### 6. Portfolio README on GitHub
expected: Repo-root README renders as a portfolio landing page on github.com — hero GIF plays, architecture diagram + 4 screenshots load, two tech tables render, link to docs/MASTERCLASS.md works.
result: pass

### 7. Portfolio assets present
expected: docs/ contains architecture.png, hero.gif, and 4 screenshots under docs/screenshots/ — all within size caps, no PII visible.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
