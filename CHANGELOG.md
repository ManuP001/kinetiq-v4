# CHANGELOG

## [0.1.0] — 2026-09-06 — clean-room reconstruction

Generated from the `kinetiq v4` CLAUDE.md hierarchy alone (root + `backend/`, `evals/`,
`frontend/`, `skills/`). No source file from the original repo was read or copied.

### Added
- `backend/app/core/config.py` — gate floors, thresholds, the one exercise-library loader.
- `evals/gate0/detector/` — `geometry`, `keypoint_map`, `plausibility`, `subject_lock`,
  `rep_counter`, `faults`, `flag_hysteresis`, `adapter.run_detector`.
- `evals/gate0/scorers/` — `rep_match`, `form_pr`, `phantom`, `subject_lock`, `view`.
- `evals/gate0/golden/` — 13 synthetic clips and the generator that produces them.
- `evals/gate0/` — `aggregate.py`, `golden_loader.py`, `cues.py`, `exercise_lib.py`,
  `gate_config.py`, `effectiveness_report.py`.
- `evals/gate0/prototype_api/` — FastAPI service, Dockerfile, `smoke_assess.py`,
  `check_local.sh`, `run_local.ps1`/`.sh`.
- `exercises/` — 14 contracts; squat/push-up/lunge vision-live, all thresholds marked
  `needs_pt_confirmation`.
- `frontend/` — the camera PWA, `severities.json` generator, `set-api-url.ps1`.
- CI (`gate0-eval.yml`), `render.yaml`, docs.

### Design decisions forced during the build (see docs/CLEANROOM_NOTES.md)
- Fault checks carry a **scope**. Depth/ROM checks are rep-scope: asking "did this rep
  reach depth?" on every descent frame latches the fault on a good rep.
- Joint angles are computed in **3D**. A 2D angle reads a head-on squat as a straight leg
  and counts no reps at all.
- `knee_valgus` is a frontal-plane measure with an explicit view guard; from a side view
  it returns "unjudgeable" rather than reading forward knee travel as a cave.
- The rep-detection gate must sit above the depth-fault threshold, or a too-shallow rep is
  never counted and the fault it exists to catch can never fire.
- "Insufficient evidence" is a first-class outcome, distinct from "clean", and is excluded
  from precision/recall rather than scored as a true negative.

### Verified
- 118 unit tests pass.
- `Stage 0 gate: PASS` (full mode), exit 0.
- Gate B smoke: 3 reps, `knee_cave_left`, cue "Push your left knee out".
