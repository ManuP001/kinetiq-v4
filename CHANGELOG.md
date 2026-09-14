# CHANGELOG — Kinetiq v4

All notable changes to the v4 monorepo. Format loosely per Keep a Changelog.

---

## [Unreleased] — 2026-09-14 — sets longer than ~2 minutes no longer die

### Fixed — "Can't reach the trainer" partway through a set
Diagnosed from a 27-minute session's Network tab plus load tests against the live API:

1. **The session cap was a dead end.** The API holds at most `PROTOTYPE_SESSION_MAX_FRAMES`
   (3,600 ≈ 2 min at 30fps) per session and answers every later request with **413**. The app
   treated 413 like an outage: it re-queued the frames and retried into the same full session
   forever. Reproduced: first 413 at exactly ~120s, then permanent.
2. **Every retry grew.** Re-queued frames were resent on each attempt, so the body grew without
   bound — 2.2 MB one minute after the cap, tens of MB by 27 min.
3. **Sessions were never freed.** ~20 MB per full session, held until process death, on a 512 MB
   free-tier instance. The live API was observed returning **502** (Render's own HTML page,
   no CORS header → "Failed to fetch") and apparently restarting mid-test. Consistent with
   memory exhaustion from 1–3; not confirmed without Render logs.

### Changed
- **`frontend/segments.js` (new):** one visible set now spans as many server sessions as needed.
  The app rolls to a fresh session at 80% of the cap **only between reps** (`rep_in_progress ==
  false`), force-rolls at 95%, and carries the rep count and per-rep records forward. A 413 now
  triggers a roll-and-resend instead of a retry loop. The detector is untouched: each segment is
  scored by the same `run_detector`; the tracker only sums what the API returns.
- **Bounded retry queue:** capped at one server session of frames. Anything shed during a long
  outage is disclosed on the summary screen rather than silently lowering the count.
- **`/health` publishes `session_max_frames`**, so the cap stays single-sourced in `config.py`.
- **Idle + LRU session eviction** (`PROTOTYPE_SESSION_IDLE_TTL_S` = 300s,
  `PROTOTYPE_MAX_SESSIONS` = 12): bounds worst-case memory to ~250 MB.
- **Fixed a pre-existing bug:** `stopSet` set `running = false` before its "final flush", and
  `flush()` returns when `!running` — so the tail of every set was never sent. It now waits for
  any in-flight POST and delivers the remainder.
- `sw.js` precaches `segments.js`; cache bumped to `shell-v3`.
- CI runs the new JS tests.

### Verified
- 27-minute set driven by the real `segments.js` against a running API: **4,050/4,050 requests
  200, zero 413**, 17 server sessions, **648 of 648 reps counted — none lost at any of the 16
  roll boundaries**, 0 frames dropped.
- Same set with the old behaviour: first failure at ~120s, 413 thereafter, body growing each retry.
- 314 Python tests OK (306 + 7 eviction + 1 health); 10 JS tests OK; Stage 0 gate PASS; Gate B
  smoke PASS. No detection logic or thresholds touched.

---

## [Unreleased] — 2026-09-13 — THE root cause: the PWA never sent `box`

### Fixed — the actual reason the live prototype never worked
`frontend/app.js` built `people: [{track_id, kp}]` with **no `box`**. The detector's
subject-lock selects who to coach by bounding-box area and indexes `p["box"]`
unconditionally (`detector/subject_lock.py:56` -> `geometry.bbox_area`). `box` is not
covered by `validate_frame_schema`, so the frame validated cleanly, reached the detector,
and raised `KeyError: 'box'`. Starlette raises that 500 ABOVE `CORSMiddleware`, so it
arrived at the browser with no `Access-Control-Allow-Origin` — and a browser reports a
CORS-less error only as **"Failed to fetch"**. The real cause was invisible from the client.

- `buildFrame` now derives and sends `box` as `[x, y, w, h]` from the visible keypoint
  extremes (MediaPipe supplies landmarks but no box), matching the golden fixtures.
- `z` is emitted as `0` rather than `null` when the model omits it.

### Added — the test gap that let this ship
`prototype_api/test_pwa_frame_contract.py` (5 tests) exercises the PWA's exact on-the-wire
payload. Every existing test missed this because they all feed frames that already carry a
`box`: the harness reads golden fixtures, `smoke_assess.py` replays those fixtures, and
`check_local.sh` posts a hand-written probe that includes one. The single shape nobody
tested was the one the real client actually sends.

### Hardened — so the next failure is legible
- `_validate_frames` rejects a missing or malformed `box` as **422** with a message naming
  the field, instead of letting it crash the detector.
- A catch-all exception handler returns unexpected errors as JSON **through** the middleware
  stack, so a 500 keeps its CORS headers and the client can read the reason.

### Verified
306 tests OK (301 + 5 new); Stage 0 gate PASS; Gate B smoke PASS. No detector logic or
thresholds touched — the fix is in the client's frame builder and the API's input validation.

---

## [Unreleased] — 2026-09-13 — stale service worker pinned the old app shell

### Fixed — this was the real cause of "Can't reach the trainer"
`sw.js` was **cache-first with a fixed cache name** (`kinetiq-v4-shell-v1`):

    caches.match(req).then((hit) => hit || fetch(req))

Once a browser had opened the site, `app.js` and `config.js` were pinned in that cache
permanently. `activate` only deletes caches whose name differs from the current one, and the
name never changed — so **every redeploy was invisible** to anyone who had visited before.
A browser stuck on the original `config.js` kept calling `http://localhost:8000`, which is
unreachable from a phone and blocked as mixed content from an HTTPS page: exactly the
observed "Failed to fetch". The server was never contacted at all.

- `sw.js` is now **network-first** for the same-origin shell, with the cache written on every
  good response and served only when the network fails. Offline still works; a redeploy is
  no longer invisible. Correctness beats the few ms cache-first saved, for an app that
  redeploys often and whose API URL lives inside the shell.
- Cache bumped to `kinetiq-v4-shell-v2` so `activate` evicts the poisoned v1.
- `app.js` forces `registration.update()` on load and reloads once on `controllerchange`, so
  a new worker takes effect immediately instead of on some later visit.
- CDN and API requests are still never intercepted.

### Ruled out during diagnosis (all verified healthy)
- CORS: preflight returns `allow-origin` for the PWA origin, `allow-methods: POST`, and
  `allow-headers: …Content-Type`.
- API: `/health` 200 and a real `/prototype/assess` POST 200, both with the PWA `Origin` set.
- The earlier cold-start work (`fce5478`) was a genuine robustness gain but was **not** the
  cause of this error.

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
