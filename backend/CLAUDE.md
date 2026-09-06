# CLAUDE.md — backend/

Inherits the root `CLAUDE.md`; this states only what's specific to `backend/`.

## Purpose
`app/core/config.py` — the single source of truth for gate floors, thresholds and named
constants (`GATE0_TARGET_ACCURACY`, `SUBJECT_LOCK_FLOOR`, `FORM_PRECISION_FLOOR_*`,
`POSE_MODEL_CANDIDATES`, `PROTOTYPE_SESSION_MAX_FRAMES`) — plus `schemas.py`. The only
running service is the detector API, which lives in `evals/gate0/prototype_api/` so its
imports resolve.

## Conventions
- No magic numbers. A threshold is named here (or in a contract) and imported, never inlined.
- The harness reaches these via `evals/gate0/gate_config.py`, which puts `backend/` on
  `sys.path` (`parents[2]/backend`). Do not move `config.py` — that path is load-bearing
  for every import and all 118 tests.
- `EXERCISE_LIBRARY_DIR` resolves to `<repo>/exercises` (`parents[3]`), and
  `load_exercise_library()` is the one loader. Don't add a second exercise reader.
- `load_exercise_library()` RAISES on a missing or empty directory rather than returning
  `{}`. A silently-empty library boots fine, answers `/health` with 200, and 500s every
  real request — a health check would call that healthy.

## Boundaries
- Changing a threshold value is a detection change: surface it, don't do it silently.
- Adding a constant is fine; restating an existing one as a literal anywhere is a bug.
- Gate floors are policy (how good the detector must be). Detection thresholds are
  contract data (how it decides). Don't mix the two.
