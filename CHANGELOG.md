# CHANGELOG — Kinetiq v4

All notable changes to the v4 monorepo. Format loosely per Keep a Changelog.

---

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
