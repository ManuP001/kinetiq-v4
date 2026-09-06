# CLAUDE.md

## Project
Kinetiq v4 — an AI virtual physical trainer that counts reps and flags exercise form from a phone
camera, entirely on-device. This is the first **self-contained monorepo**: the eval-validated
detector, the eval harness, the exercise contracts, the detector API, and the live camera PWA all
live in one repo, one git history, one Render deploy. Earlier versions scattered these across five
folders and described a camera app ("kinetiq-demo3") as built when no files existed — v4 exists to
end that. Stage: working local prototype (squat / push-up / lunge), pre first real gym session.

## Purpose & Objectives
- Count reps and surface form flags accurately, live, from a single phone camera.
- Prove every claim with a number: a change is "better" only if the eval harness says so.
- Non-goal: tuning detection accuracy or turning on new exercises before GATE G-REAL
  (`docs/ROADMAP.md`) — one real gym session must produce a real effectiveness report first.
- Non-goal: sending pixels off device, ever (see Architecture Rules).

## Tech Stack
- Detector + harness: Python 3.12+, standard library only (no ML deps in the offline path).
- Detector API: FastAPI + uvicorn (`evals/gate0/prototype_api`).
- PWA: vanilla HTML/CSS/JS, MediaPipe Tasks Vision (PoseLandmarker / BlazePose) from CDN, in-browser.
- Deploy: Render — API as a Docker web service, `frontend/` as a static site (`render.yaml`).
- CI: GitHub Actions (`.github/workflows/gate0-eval.yml`) — the Stage-0 regression gate.

## Commands
- Backend tests: `python -m unittest discover -s evals/gate0 -p "test_*.py"` (301 tests)
- Eval gate: `python evals/gate0/aggregate.py --golden evals/gate0/golden --mode full`
- Gate B smoke (API+detector, no webcam): `python evals/gate0/prototype_api/smoke_assess.py`
- Run the whole prototype locally (webcam): `evals/gate0/prototype_api/run_local.ps1` (bash: `run_local.sh`)

## Repo Structure
- `/backend` — `app/core/config.py`: the single source of gate floors, thresholds, named constants.
- `/evals` — `gate0/`: the detector (`detector/`), scorers, golden set, harness, and the detector API.
- `/exercises` — the 14 exercise contracts (thresholds/severities/cues); squat/pushup/lunge are vision-live.
- `/frontend` — the live camera PWA (the piece that was always missing).
- `/skills` — project-specific Claude Code skills (`project-scaffold/`).
- `/docs` — governing docs carried from v3 (eval strategy, vision architecture, roadmap, deploy runbook…).

## Architecture Rules
- **Privacy invariant:** pose runs in-browser; only keypoint frames cross the network. No pixels leave
  the device — not to the API, not to any model. The PWA POSTs keypoints only.
- **One-detector-two-consumers:** `run_detector` (`evals/gate0/detector/adapter.py`) is called by BOTH
  the live API and the offline harness. Detection logic changes once, in `detector/`, never duplicated.
- **Anti-phantom rule:** nothing is described as "built" in any doc, CLAUDE.md, or commit unless its
  files exist AND an acceptance check ran green. No aspirational statuses. If unverified, say so.
- **Deterministic safety veto:** a learned/advisory layer may add nuance but can never clear a hard
  safety flag or invent a rep the validity gate rejects.
- **Config is the single source of truth:** thresholds live in `exercises/*.json` or
  `backend/app/core/config.py`, imported (via `gate_config`), never restated as inline literals.

## Patterns to Follow
- Surface uncertain/safety-critical decisions (`status: needs_pt_confirmation`) — never invent a threshold.
- Every field bug becomes a permanent eval case the day it's found (`docs/EVAL_STRATEGY.md`).
- Small commits; every change updates `CHANGELOG.md` and the doc it affects.

## Patterns to Avoid
- Editing detection logic/thresholds to make a number look better (GATE G-REAL blocks this).
- Treating green tests on synthetic golden data as proof of real-world accuracy — it is not.

## Testing
301 backend tests + the Stage-0 eval gate must stay green on every change; the CI workflow runs both.
The PWA is proven by `smoke_assess.py` (headless) and a real-webcam run via `run_local`.

## Quality Bar
Mobile-first (390px), dark theme (`DESIGN.md`). Every screen handles loading / empty / error /
permission-denied. A cue never exceeds its word cap (enforced in `cues.py`).

## Current Focus
Local prototype is built and verified (Gate A: 301 tests + eval gate PASS; Gate B: live loop returns
reps/flags/cue). Next: publish as a GitHub repo and deploy to Render (`docs/DEPLOY_RUNBOOK.md`), then
run the first real gym session (GATE G-REAL) — the gate that unblocks everything above Stage 3.

## Known Issues
- All eval evidence to date is synthetic/stubbed golden data. Real accuracy is unmeasured until G-REAL.
- The 11 non-MVP exercises have contracts but are NOT vision-live (`vision_support: false`).
- `agents/` (the 6-agent backend from v2) is intentionally absent — a later phase, not this prototype.
