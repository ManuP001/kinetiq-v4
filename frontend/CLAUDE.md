# CLAUDE.md — frontend/

Inherits from the root `CLAUDE.md` and the design system in `DESIGN.md`; this states only what's
specific to `frontend/`. This is the live camera PWA — the piece that never existed before v4.

## What it is
A zero-build static PWA (`index.html`, `app.js`, `styles.css`, `config.js`, `manifest.json`, `sw.js`).
Served by any static host (`python -m http.server` locally, a Render static site in prod). No
framework, no bundler — one less thing to break at gym wifi speed.

## Data flow (do not break the privacy invariant)
webcam → MediaPipe PoseLandmarker (in-browser) → 33 BlazePose keypoints → a frame
`{t_ms, pose_model:"blazepose_33", people:[{track_id:0, kp:[[x,y,z,vis]×33]}]}` → buffered → `POST`ed to
`/prototype/assess`. **Only keypoints leave the browser. Never send the video frame or an image.**

## Conventions
- The frame shape is dictated by the backend's `validate_frame_schema` — if the detector's expected
  keypoint schema changes, change the frame builder in `app.js` to match; do not guess.
- Send only NEW frames each POST with `reset:true` on the first call; the server buffers per session.
- `exercise_id` must be one of `squat`/`pushup`/`lunge` (the API rejects others with 422).
- API base URL lives ONLY in `config.js` (`API_BASE_URL`). Deploy = edit that one line / `set-api-url`.
- Flag color comes from `severities.json` (generated from `exercises/*.json`); don't hardcode a
  severity map in JS. Regenerate `severities.json` if a contract's severities change.

## States every screen handles
Loading (model warmup), camera-prompt, permission-denied (+Retry), running, API-unreachable
(non-destructive banner; buffered frames re-queued, never dropped), empty summary. See `DESIGN.md`.

## Boundaries
The PWA is a consumer of the detector, never a second implementation of it. Rep counting, flags, and
cues come from the API response — do not reimplement any detection or thresholding in JavaScript.
