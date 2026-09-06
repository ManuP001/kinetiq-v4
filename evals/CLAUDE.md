# CLAUDE.md — evals/

Inherits from the root `CLAUDE.md`; this states only what's specific to `evals/`.

## Purpose
`gate0/` is the whole detection engine and its eval discipline: the compound detector, per-dimension
scorers, the frozen golden set, the regression harness, and the live detector API — one place,
because of one-detector-two-consumers. "Correct" here = whatever the golden set checks
(`docs/EVAL_STRATEGY.md`, `docs/EVAL_HARNESS_STAGE0_SPEC.md`).

## Layout
- `detector/` — `subject_lock`, `plausibility`, `rep_counter`, `faults`, `flag_hysteresis`, `geometry`,
  `keypoint_map`, and `adapter.py` which exposes **`run_detector`** (the one entry point).
- `scorers/` — one scorer per dimension: `rep_match`, `form_pr`, `phantom`, `subject_lock`, `view`.
- `golden/` — frozen keypoints + PT labels (currently synthetic fixtures; real clips land per
  `docs/GOLDEN_SET_PROTOCOL.md`). Never commit video.
- `prototype_api/` — the FastAPI detector API (`main.py` → `/prototype/assess`, `/health`), the run
  scripts (`run_local.*`), `check_local.sh`, `Dockerfile`, and `smoke_assess.py` (Gate B).
- `aggregate.py` / `golden_loader.py` / `effectiveness_report.py` — harness entry points.

## Eval Types
- Rule-based scorers over the golden set (rep-accuracy, form P/R, phantom, subject-lock, view).
- Human PT labels are the ground truth for form faults (`docs/GOLDEN_SET_PROTOCOL.md`).

## Running
- Full gate: `python aggregate.py --golden golden --mode full` → must print `Stage 0 gate: PASS`.
- Fast gate (CI per-push): `--mode fast`. Unit tests: `python -m unittest discover -p "test_*.py"`.

## Adding a New Eval
Every field bug becomes a permanent golden case the day it's found. A frame must match
`validate_frame_schema` (`golden_loader.py`): `{t_ms, pose_model, people:[{track_id, kp:[[x,y,z,vis]…]}]}`.

## Boundaries
Detection logic and threshold values are frozen under GATE G-REAL. Scorers, fixtures, and the harness
are not — improve those freely, but a change must keep every dimension green (a rising number can hide
a falling one).
