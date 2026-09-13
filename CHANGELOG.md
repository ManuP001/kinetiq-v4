# CHANGELOG — Kinetiq v4

All notable changes to the v4 monorepo. Format loosely per Keep a Changelog.

---

## [Unreleased] — 2026-09-13 — PWA survives a cold start

### Fixed
- **"Can't reach the trainer" on the first rep of a session.** Render's free tier sleeps a
  web service after ~15 min idle and the next request pays a 30-60s cold start, which lands
  on the first POST of a set. `flush()` treated that single failure as fatal and blocked the
  user on an error screen requiring a manual Retry. It now:
  - **Pre-warms on load** — `/health` is pinged when the app opens, so the server is usually
    awake by the time an exercise is picked.
  - **Wakes before the set** — after camera start, polls `/health` (90s budget) behind a
    "Waking the coach" message. Does not block: on timeout the set starts anyway and frames
    buffer.
  - **Retries with backoff** — the first 10 failures back off 1s→8s behind a non-blocking
    amber banner while recording continues; only sustained failure interrupts.
  - **Guards against stacked POSTs** — an in-flight flag stops the 400ms timer piling
    concurrent requests onto a booting server.
  - Frames are still never dropped: they re-queue and replay, so the rep count catches up.

### Verified
- `/health` confirmed to return `access-control-allow-origin` for the PWA origin, so the
  browser can read the pre-warm response (not just wake the server blindly).
- 301 tests OK; Stage 0 gate PASS; Gate B smoke PASS. No detector logic or thresholds touched.

---

## [Unreleased] — 2026-09-08 — first deploy wiring

### Changed
- `frontend/config.js`: `API_BASE_URL` now points at `https://kinetiq-v4-api.onrender.com`
  instead of `http://localhost:8000`. On a phone, `localhost` means the phone itself, so the
  deployed PWA had nothing to call — and an HTTPS page calling plain `http://` is blocked as
  mixed content regardless. Set via `frontend/set-api-url.ps1`.

### Deploy status (verified)
- PWA static site is **live** at https://kinetiq-v4.onrender.com — index, `app.js`,
  `config.js`, `styles.css`, `severities.json`, `manifest.json`, `sw.js` all serve 200.
  Confirmed on a real Android phone: HTTPS, camera permission, MediaPipe load, exercise
  picker and the API-unreachable retry state all work.
- Detector API is **NOT yet deployed**. Until the service exists at the URL above, the PWA
  will still show "Can't reach the trainer" — expected, not a regression.
- `PROTOTYPE_API_CORS_ORIGINS` must be set to `https://kinetiq-v4.onrender.com` on the API
  service, followed by a restart, before the browser can complete a call.

### Note
An earlier working-tree state had `evals/` missing from disk (109 files). Restored from
commit 923406e; 301 tests, the Stage 0 gate and the Gate B smoke all re-verified green. No
content was lost and no commit was affected.

## [0.1.0] — 2026-09-06 — self-contained monorepo + the real camera PWA

The first version where the detector, eval harness, exercise contracts, detector API, and the live
camera PWA all live in ONE repo — and where the camera app actually exists as files. v3 described a
PWA ("kinetiq-demo3") as built when none was ever generated; v4 exists to end that, and every claim
below names the acceptance check that proved it.

### Added — the camera PWA (`frontend/`), the piece that never existed
Zero-build static PWA: `index.html`, `app.js`, `styles.css`, `config.js`, `manifest.json`, `sw.js`.
MediaPipe PoseLandmarker (BlazePose) runs in-browser; the app builds keypoint frames in the exact
shape `golden_loader.validate_frame_schema` enforces (`{t_ms, pose_model:"blazepose_33",
people:[{track_id, kp:[[x,y,z,vis]×33]}]}`), buffers them, and POSTs only keypoints to
`/prototype/assess` — pixels never leave the device. Renders live rep count, phase, severity-colored
form flags, coaching cue, and subject-lock state, with a session summary from the accumulated `reps[]`.
Handles loading / camera-prompt / permission-denied / API-unreachable (frames re-queued, never
dropped) / empty-summary states. `severities.json` is generated from `exercises/*.json` (the contract
stays the single source).

### Added — imported the eval-validated backend, paths preserved
`backend/app/core/{config.py,schemas.py}`, `evals/gate0/**` (detector, scorers, labeling, golden,
harness, prototype_api), `exercises/*.json` (14), and the CI workflow — copied from kinetiq-v2 at
their exact relative paths so `gate_config.py`'s `parents[2]/backend` import and
`config.py`'s `parents[3]/exercises` resolution keep working unchanged. Governing docs carried into
`docs/`.

### Added — scaffold (project-scaffold skill)
Root `CLAUDE.md` (<100 lines), `DESIGN.md`, folder `CLAUDE.md` for `backend/`, `evals/`, `frontend/`,
`skills/`; the skill itself at `skills/project-scaffold/SKILL.md`. `agents/` intentionally omitted
(the v2 6-agent backend is a later phase).

### Added — Gate B smoke (`evals/gate0/prototype_api/smoke_assess.py`)
Drives the real FastAPI app + real `run_detector` with a canned golden fixture, streamed in chunks
exactly as the PWA would (reset on first POST), and asserts a rep, a flag, a cue, and the documented
response shape. Runnable headless (CI/deploy gate) — proves the live loop without a webcam.

### Changed — run scripts point at the in-repo PWA
`run_local.ps1` / `run_local.sh` now default the PWA dir to `<repo>/frontend` (was the phantom
`../kinetiq-demo3`), set CORS to the PWA origin, and print instructions matching the actual app.

### Fixed — CI would have been red on first run
`gate0-eval.yml`'s `unittest discover -s evals/gate0` collects the `prototype_api` tests, which import
fastapi, but the workflow had no install step (it assumed stdlib-only). Added a pinned
`prototype_api/requirements.txt` install to both `fast-gate` (3.12/3.13 matrix) and `full-gate`.

### Added — one-repo deploy (`render.yaml`)
Both services in one Blueprint: API (Docker web service, context = repo root) + PWA (static site).
`frontend/set-api-url.ps1` rewrites the one API-URL line in `config.js` for deploy.

### Acceptance checks (this release is "built" because these ran green)
- **Gate A:** `python -m unittest discover -s evals/gate0 -p "test_*.py"` → **301 tests OK**;
  `aggregate.py --golden evals/gate0/golden --mode full` → **Stage 0 gate: PASS**.
- **Gate B:** `smoke_assess.py` and a live `run_local` round-trip both return `rep_count=4`,
  `knee_cave_left`, cue "Push your left knee out"; PWA `index.html`/`app.js`/`severities.json` served 200.

### Still not verified (honest status)
- Real-world accuracy: **unmeasured**. All golden evidence is synthetic. GATE G-REAL
  (`docs/ROADMAP.md`) — one real gym session — is the next gate and blocks everything above Stage 3.
- The PWA has not been run against a real webcam on a phone yet (needs HTTPS / local run on a device).
- Branch protection required-status-checks is a GitHub-settings step, not done here.
