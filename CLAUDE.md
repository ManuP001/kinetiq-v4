# CLAUDE.md

## Project
Kinetiq — an AI virtual physical trainer that counts reps and flags exercise form from a
phone camera, entirely on-device. **This repo is a clean-room reconstruction** generated
from the `kinetiq v4` CLAUDE.md hierarchy alone (see `docs/CLEANROOM_NOTES.md`); no v4
source was read or copied. Stage: passes its own gates on synthetic fixtures. No human has
been in front of the camera yet.

## Purpose & Objectives
- Count reps and surface form flags accurately, live, from a single phone camera.
- Prove every claim with a number: a change is "better" only if the eval harness says so.
- Test whether a CLAUDE.md hierarchy is a sufficient spec — and record where it isn't.
- Non-goal: sending pixels off device, ever.

## Tech Stack
- Detector + harness: Python 3.12+, standard library only.
- Detector API: FastAPI + uvicorn (`evals/gate0/prototype_api`).
- PWA: vanilla HTML/CSS/JS, MediaPipe Tasks Vision (PoseLandmarker) from CDN, in-browser.
- Deploy: Render — API as a Docker web service, `frontend/` as a static site.
- CI: GitHub Actions (`.github/workflows/gate0-eval.yml`).

## Commands
- Tests: `python -m unittest discover -s evals/gate0 -p "test_*.py"` (118 tests)
- Eval gate: `python evals/gate0/aggregate.py --golden evals/gate0/golden --mode full`
- Gate B smoke: `python evals/gate0/prototype_api/smoke_assess.py`
- Whole prototype (webcam): `evals/gate0/prototype_api/run_local.ps1` (bash: `run_local.sh`)
- Regenerate fixtures: `cd evals/gate0/golden && python _generate_fixtures.py`

## Repo Structure
- `/backend` — `app/core/config.py`: the single source of gate floors and constants.
- `/evals` — `gate0/`: detector, scorers, golden set, harness, detector API.
- `/exercises` — 14 contracts; squat/pushup/lunge are vision-live.
- `/frontend` — the camera PWA.
- `/docs` — `CLEANROOM_NOTES.md` (what the spec pinned and left open), deploy runbook.

## Architecture Rules
- **Privacy invariant:** pose runs in-browser; only keypoint frames cross the network. The
  API has no pose runtime and no image decoder — enforced by a test, not by policy.
- **One-detector-two-consumers:** `run_detector` (`evals/gate0/detector/adapter.py`) is
  called by BOTH the live API and the offline harness. Never duplicate detection logic.
- **Anti-phantom rule:** nothing is described as "built" unless its files exist AND an
  acceptance check ran green. If unverified, say so.
- **Deterministic safety veto:** an advisory layer may add nuance but can never clear a
  hard safety flag or invent a rep the validity gate rejects.
- **Config is the single source of truth:** thresholds live in `exercises/*.json` or
  `backend/app/core/config.py`, imported via `gate_config`, never inlined.
- **"Unjudgeable" is not "clean":** a check with too little evidence reports unknown, and
  is excluded from precision/recall rather than counted as a true negative.
- **Fault checks carry a scope:** `frame` (smoothed by `sustain_frames`) or `rep`
  (evaluated once at rep close). Depth/ROM questions are rep-scope — see CLEANROOM_NOTES.
- **Joint angles are 3D:** a 2D angle cannot see a head-on squat — see CLEANROOM_NOTES.

## Patterns to Follow
- Surface uncertain/safety-critical decisions (`status: needs_pt_confirmation`) — never
  invent a threshold and present it as settled.
- Every field bug becomes a permanent eval case the day it's found.
- Small commits; every change updates `CHANGELOG.md` and the doc it affects.

## Patterns to Avoid
- Editing detection logic or thresholds to make a number look better.
- Treating green tests on synthetic golden data as proof of real-world accuracy.
- Authoring golden ground truth by reading it off the detector — that makes the gate vacuous.

## Testing
118 tests + the Stage-0 eval gate must stay green on every change; CI runs both, plus a job
asserting the committed fixtures still match their generator.

## Quality Bar
Mobile-first (390px), dark theme (`DESIGN.md`). Every screen handles loading / empty /
error / permission-denied. A cue never exceeds its word cap (enforced in `cues.py`).

## Known Issues
- All eval evidence is synthetic. Real accuracy is unmeasured.
- Every threshold is `needs_pt_confirmation` — derived, not validated by a trainer.
- The 11 non-MVP exercises have contracts but are NOT vision-live.
- The Docker image has never been built; nothing has been deployed.
