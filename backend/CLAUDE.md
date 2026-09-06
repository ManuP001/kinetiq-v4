# CLAUDE.md — backend/

Inherits everything from the root `CLAUDE.md`; this only states what's specific to `backend/`.

## Purpose
Holds `app/core/config.py` — the **single source of truth** for gate floors, per-run thresholds, and
named constants (e.g. `GATE0_TARGET_ACCURACY`, `SUBJECT_LOCK_FLOOR`, `FORM_PRECISION_FLOOR_*`,
`POSE_MODEL_CANDIDATES`, `PROTOTYPE_SESSION_MAX_FRAMES`), plus `schemas.py`. The v2 6-agent FastAPI
service is NOT in v4 — that's a later phase. The only running service today is the detector API,
which physically lives in `evals/gate0/prototype_api/` (kept there so its imports resolve).

## Conventions
- No magic numbers. A threshold is named here (or in an exercise contract) and imported, never inlined.
- The eval harness reaches these constants via `evals/gate0/gate_config.py`, which puts `backend/` on
  `sys.path` (`parents[2]/backend`) and imports `app.core.config`. Do not move `config.py` out of
  `backend/app/core/` — that path is load-bearing for every import and all 301 tests.
- `config.py`'s `EXERCISE_LIBRARY_DIR` resolves to `<repo>/exercises` (`parents[3]/exercises`) and
  `load_exercise_library()` is the one loader; don't add a second exercise reader.

## Boundaries
- Changing a threshold *value* is a detection change gated by GATE G-REAL — surface it, don't do it.
- Adding a constant is fine; restating an existing one as a literal anywhere is a bug.
