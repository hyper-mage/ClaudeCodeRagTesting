# Docker Smoke Run — Setup Walkthrough

End-to-end guide for running `backend/scripts/docker_smoke.sh` on a fresh Windows 11 machine. Validates Phase 02 (DEPLOY-01) gate before any Fly deploy.

---

## 1. Install Docker Desktop (Windows 11)

1. Download: https://www.docker.com/products/docker-desktop/ → "Docker Desktop for Windows" (AMD64).
2. Run `Docker Desktop Installer.exe`. Accept defaults. Keep "Use WSL 2 instead of Hyper-V" checked.
3. Reboot when prompted.
4. Launch Docker Desktop. Wait for tray icon → "Docker Desktop is running" (green).
5. If WSL2 kernel update prompt appears, run `wsl --update` in elevated PowerShell, then restart Docker Desktop.

**Verify** in new bash terminal:
```bash
docker --version
docker info | head -5
```
Both should succeed. `docker info` must show `Server` section (not just Client).

### 1a. If "Virtualization not detected"

Two layers must be on: BIOS virtualization + Windows WSL2/Hyper-V features.

**Check current state.** PowerShell (admin):
```powershell
systeminfo | findstr /i "Hyper-V"
```
Look for `Virtualization Enabled In Firmware: Yes`. Also Task Manager → Performance → CPU → bottom-right "Virtualization: Enabled".

**Enable in BIOS/UEFI** (if firmware = No):
1. Reboot. Spam BIOS key during POST: usually `Del`, `F2`, `F10`, or `Esc`.
2. Find setting (name varies):
   - Intel: **Intel VT-x** / **Intel Virtualization Technology** / **VT-d**
   - AMD: **SVM Mode** / **AMD-V** / **SVM**
   - Location: usually `Advanced` → `CPU Configuration` (or `Security` tab on some laptops)
3. Set → **Enabled**. Save + exit (`F10`).
4. Boot back. Re-check Task Manager → Virtualization: Enabled.

**Enable Windows features.** PowerShell (admin):
```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
dism.exe /online /enable-feature /featurename:HypervisorPlatform /all /norestart
```
Reboot.

**Update WSL2 kernel + set default:**
```powershell
wsl --update
wsl --set-default-version 2
wsl --status
```
Status should show `Default Version: 2` and a kernel version line.

Re-launch Docker Desktop. `docker info` should now show `Server:` section.

---

## 2. Verify required CLI tools

Smoke script needs `docker`, `curl`, `jq`, `bash`.
```bash
which docker curl jq bash
```
If `jq` missing → install via `winget install jqlang.jq` or `choco install jq`. Restart terminal.

---

## 3. Confirm `.env` populated

Repo root `.env` must contain (real values, not placeholders):
```
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon jwt>
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
OPENAI_API_KEY=...        # or OPENROUTER_API_KEY depending on config
```
Test creds (already in `CLAUDE.md`):
```
ragtest1@gmail.com / testpass123
```
Smoke script uses anon key + password grant — no service-role exposure.

Quick check:
```bash
grep -E "^(VITE_SUPABASE_URL|VITE_SUPABASE_ANON_KEY)=" .env
```
Both lines must be non-empty.

---

## 4. Run smoke script

From repo root:
```bash
bash backend/scripts/docker_smoke.sh
```

**Expect ~5–15 min first run** (downloads Python base + Docling models = several GB pull). Subsequent runs use layer cache.

**Stages it walks through:**
1. Preflight (tools + .env present)
2. `docker build -t boardgame-rag-backend:smoke .`
3. Image size audit (warn 6GB / fail 7.5GB)
4. Container boot (`docker run` background)
5. Health poll (`/api/health` → 200)
6. Supabase JWT acquire
7. PDF + DOCX ingest → chunk counts
8. Regression checks (CPU torch, appuser, models, no .env baked)
9. Teardown (stop + rm container)

---

## 5. Success signal

Last lines should look like:
```
[ OK ] torch is CPU-only
[ OK ] Runtime user is appuser
[ OK ] Docling models baked into /home/appuser/.cache/docling/models
[ OK ] .env not baked in
[ OK ] SMOKE PASS (image X.XX GB)
```

Once seen:
- Mark `02-HUMAN-UAT.md` tests passed
- Flip `02-VERIFICATION.md` status → `passed`
- Run `phase complete` to mark phase done in ROADMAP

---

## Common failures + fixes

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot connect to the Docker daemon` | Desktop not started | Launch Docker Desktop, wait for green |
| Build fails on `apt-get` | Slow mirror / network | Re-run; apt cache layer retries |
| Build OOM / disk full | <20GB free | Free disk; image ~5–6 GB + layers |
| Health timeout | Container crash on boot | `docker logs <id>` — check `.env` keys |
| Ingest 401 | JWT not acquired | Verify test creds + anon key correct |
| Ingest chunk_count = 0 | Docling parse fail | Check container logs for Docling error |
| `permission denied: docker_smoke.sh` | Lost +x bit | `chmod +x backend/scripts/docker_smoke.sh` |
| BIOS lacks VT option | Old/locked OEM BIOS | Update BIOS firmware from vendor site |
| Hyper-V conflicts (VirtualBox/VMware) | Older hypervisors fight WSL2 | Uninstall conflicting hypervisor |
| Corporate laptop, BIOS locked | IT policy | Ask IT to enable VT-x/SVM |
| `Hypervisor error` on boot | Memory integrity / Core Isolation | Settings → Privacy & Security → Windows Security → Device Security → Core Isolation → off, reboot |
| WSL2 install hangs | Old Windows build | Run `winver`, must be ≥ Win10 2004 / Win11 any |
