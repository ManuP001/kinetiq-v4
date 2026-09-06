# CLAUDE.md — evals/

Inherits the root `CLAUDE.md`; this states only what's specific to `evals/`.

## Purpose
`gate0/` is the detection engine and its eval discipline in one place, because of
one-detector-two-consumers. "Correct" here means whatever the golden set checks.

## Layout
- `detector/` — `geometry`, `keypoint_map`, `plausibility`, `subject_lock`, `rep_counter`,
  `faults`, `flag_hysteresis`, and `adapter.py` exposing **`run_detector`**.
- `scorers/` — one per dimension: `rep_match`, `form_pr`, `phantom`, `subject_lock`, `view`.
- `golden/` — frozen fixtures plus `_generate_fixtures.py` that produces them. Never
  commit video.
- `prototype_api/` — the FastAPI service, run scripts, `check_local.sh`, `Dockerfile`,
  `smoke_assess.py`.
- `aggregate.py` / `golden_loader.py` / `effectiveness_report.py` — harness entry points.

## Running
- Full gate: `python aggregate.py --golden golden --mode full` → must print `Stage 0 gate: PASS`.
- Fast gate (CI per-push): `--mode fast`. Tests: `python -m unittest discover -p "test_*.py"`.

## Adding a New Eval
Every field bug becomes a permanent golden case the day it's found. A frame must satisfy
`validate_frame_schema`: `{t_ms, pose_model, people:[{track_id, kp:[[x,y,z,vis]...]}]}`.

Ground truth is authored from the fixture's construction parameters, or from a PT's labels
— **never** by running the detector and recording what it said. Doing that makes the gate
agree with itself forever.

## Fault checks
A check returns tri-state: `True` (present), `False` (checked, absent), `None` (not
judgeable). `None` is not `False`, and the difference is load-bearing — it flows through to
"insufficient evidence" and is excluded from P/R.

Each check declares a scope via `@register(name, scope=...)`:
- `frame` — judged per frame, smoothed by `sustain_frames`.
- `rep` — judged once at rep close. Depth/ROM checks MUST be rep-scope, or they latch on
  the descent of a perfectly good rep.

A contract's `down_enter_deg` (the rep-detection gate) must sit ABOVE any depth-fault
threshold for that exercise. Otherwise a too-shallow rep is never counted as a rep, and the
fault that exists to catch it can never fire. A test enforces this for every contract.

## Boundaries
Scorers, fixtures and the harness can be improved freely, but a change must keep every
dimension green — a rising number can hide a falling one.
