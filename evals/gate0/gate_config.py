"""Bridge from the harness to backend/app/core/config.py.

backend/CLAUDE.md: "The eval harness reaches these constants via
evals/gate0/gate_config.py, which puts backend/ on sys.path (parents[2]/backend)
and imports app.core.config."

    evals/gate0/gate_config.py
    parents[0] = evals/gate0
    parents[1] = evals
    parents[2] = <repo root>

Import constants FROM HERE inside the harness. Re-deriving a floor locally is the
"restating an existing constant as a literal" bug backend/CLAUDE.md calls out.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = REPO_ROOT / "backend"

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Also make evals/gate0 importable so `detector`, `scorers` resolve when the
# harness is invoked from the repo root rather than from inside gate0.
_GATE0_DIR = Path(__file__).resolve().parent
if str(_GATE0_DIR) not in sys.path:
    sys.path.insert(0, str(_GATE0_DIR))

from app.core.config import (  # noqa: E402,F401
    CUE_MAX_WORDS,
    DEFAULT_POSE_MODEL,
    EXERCISE_LIBRARY_DIR,
    FLAG_SUSTAIN_FRAMES,
    FORM_PRECISION_FLOORS,
    FORM_PRECISION_FLOOR_HIGH,
    FORM_PRECISION_FLOOR_LOW,
    FORM_PRECISION_FLOOR_MED,
    FORM_RECALL_FLOORS,
    FORM_RECALL_FLOOR_HIGH,
    FORM_RECALL_FLOOR_LOW,
    FORM_RECALL_FLOOR_MED,
    GATE0_TARGET_ACCURACY,
    INSUFFICIENT_EVIDENCE_MIN_FRAMES,
    MIN_KEYPOINT_VISIBILITY,
    MIN_VISIBLE_LANDMARK_RATIO,
    POSE_MODEL_CANDIDATES,
    PROTOTYPE_DEFAULT_PORT,
    PROTOTYPE_SESSION_MAX_FRAMES,
    PROTOTYPE_SUPPORTED_EXERCISES,
    REPO_ROOT as CONFIG_REPO_ROOT,
    SUBJECT_LOCK_FLOOR,
    SUBJECT_LOCK_MIN_BOX_AREA,
    VIEW_MAX_GAP,
    ExerciseLibraryError,
    load_exercise_library,
    vision_live_exercises,
)
from app.core.schemas import (  # noqa: E402,F401
    DetectorResult,
    Frame,
    Person,
    RepRecord,
)
