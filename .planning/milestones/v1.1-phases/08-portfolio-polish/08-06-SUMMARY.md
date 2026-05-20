---
phase: "08"
plan: "06"
status: complete
date: 2026-05-20
requirements-completed: [PORT-03]
---

# Plan 08-06 — Portfolio Assets (COMPLETE)

All 6 asset files delivered under `docs/`. PORT-03 asset portion satisfied. Plan 08-05 README can embed every asset via relative links.

## Assets Delivered

| Asset | Path | Size | Tooling |
|-------|------|------|---------|
| Architecture diagram | `docs/architecture.png` | 177 KB | Milanote (see deviation) |
| Screenshot 1 — login | `docs/screenshots/01-login-try-demo.png` | 14 KB | Windows Snipping Tool |
| Screenshot 2 — chat + tools | `docs/screenshots/02-chat-tool-calls.png` | 136 KB | Windows Snipping Tool |
| Screenshot 3 — documents | `docs/screenshots/03-documents-upload.png` | 26 KB | Windows Snipping Tool |
| Screenshot 4 — mobile drawer | `docs/screenshots/04-mobile-drawer.png` | 18 KB | Windows Snipping Tool |
| Hero GIF | `docs/hero.gif` | 1.1 MB | Snipping Tool MP4 → ffmpeg |

All under their respective size caps (diagram ≤500 KB, screenshots ≤200 KB each, GIF ≤5 MB).

## Task 1 — Architecture diagram

9 nodes: Browser (React SPA), Cloudflare Pages, Fly.io (FastAPI + Docling nested), Supabase (4 sub-nodes: Postgres+pgvector, Auth+anon, Storage, Realtime), OpenRouter, LangSmith, Sentry, UptimeRobot. 10 labeled edges covering runtime + observability flows (solid for runtime, dashed for observability/probe).

## Task 2 — Screenshots

All 4 captured from a fresh anon-demo session on the deployed CF Pages URL. No PII (no email, no UUID, no real-user content) — verified by visual review. Demo amber pill visible in screenshots 2-4.

- Item 3 caveat: documents screenshot shows status badge `completed` rather than mid-upload. Upload completes sub-second on a small file; the status badge requirement (D-14) is met — the surface clearly shows a status badge on an ingested document.

## Task 3 — Hero GIF

Source: 114.6 s, 1200×720 MP4 from Windows Snipping Tool. Converted via ffmpeg 8.1.1 (installed via `winget install Gyan.FFmpeg`) two-pass palette method:

```
# pass 1 — palette
ffmpeg -i hero.gif.mp4 -vf "setpts=PTS/6.4,fps=12,scale=800:-1:flags=lanczos,palettegen=stats_mode=diff" palette.png
# pass 2 — apply
ffmpeg -i hero.gif.mp4 -i palette.png -lavfi "setpts=PTS/6.4,fps=12,scale=800:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" hero.gif
```

6.4× speedup (most of the 114 s source was free-tier LLM wait time) → 17.9 s final. 800 px wide, 12 fps, 215 frames, 1.1 MB. Flow visible: login → Try-demo click → chat loads → query → tool-call cards → streamed answer. Source MP4 (54 MB) NOT committed — too large for repo.

## Deviations

1. **Architecture diagram authored in Milanote, not Excalidraw (D-12).** D-12 specified Excalidraw with a committed `.excalidraw` source file. The author used Milanote and exported PNG only. Milanote has no portable open-source export format; the editable source persists in the author's Milanote account. PNG committed standalone. Future-edit convenience (the rationale behind the D-12 source requirement) is preserved via the Milanote board, just not in-repo. Accepted as a non-blocking deviation.

2. **Hero GIF source recorded as MP4, not GIF directly.** Windows Snipping Tool records video; ScreenToGif (RESEARCH recommendation) was not used. Net result identical — ffmpeg conversion produced a spec-compliant 1.1 MB GIF. No functional impact.

## Deferred Polish

- Architecture diagram is light-themed; a dark-mode variant matching the app could be a future portfolio pass.
- Hero GIF 6.4× speedup blurs the streamed-text portion; a re-record on a faster model would allow a more readable 1×-2× pace if desired later.

## Verification

- `docs/architecture.png` — 177 KB ≤ 500 KB ✓
- 4 screenshots — 14/136/26/18 KB, each ≤ 200 KB ✓
- `docs/hero.gif` — 1.1 MB ≤ 5 MB ✓
- No PII in any captured image ✓
- All paths match `08-06-PLAN.md` `files_modified` (except `docs/architecture.excalidraw` — see deviation 1)

## Commits

- `2c0a641` feat(08-06): architecture diagram PNG
- `a6fd69b` feat(08-06): 4 portfolio screenshots
- `6664566` feat(08-06): hero GIF
