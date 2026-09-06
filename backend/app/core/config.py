"""Single source of truth for gate floors, thresholds, and named constants.

backend/CLAUDE.md: "No magic numbers. A threshold is named here (or in an exercise
contract) and imported, never inlined."

Load-bearing path facts (backend/CLAUDE.md "Conventions"):
  - This file must stay at backend/app/core/config.py. evals/gate0/gate_config.py
    reaches it via parents[2]/backend, and every import depends on that.
  - EXERCISE_LIBRARY_DIR resolves to <repo>/exercises via parents[3].

        backend/app/core/config.py
        parents[0] = backend/app/core
        parents[1] = backend/app
        parents[2] = backend
        parents[3] = <repo root>
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

_THIS = Path(__file__).resolve()
REPO_ROOT: Path = _THIS.parents[3]
EXERCISE_LIBRARY_DIR: Path = REPO_ROOT / "exercises"

# --------------------------------------------------------------------------
# Stage 0 gate floors
#
# These are the pass/fail thresholds the eval harness enforces. They are gate
# policy, not detection thresholds -- they say how good the detector must be,
# not how it decides anything. Detection thresholds live in exercises/*.json.
# --------------------------------------------------------------------------

GATE0_TARGET_ACCURACY: float = 0.90
SUBJECT_LOCK_FLOOR: float = 0.99
VIEW_MAX_GAP: float = 0.10

# Form precision/recall floors are severity-gated: a high-severity fault is a
# safety call, so a false positive costs more -- its precision floor is higher.
FORM_PRECISION_FLOOR_HIGH: float = 0.90
FORM_PRECISION_FLOOR_MED: float = 0.75
FORM_PRECISION_FLOOR_LOW: float = 0.60

FORM_RECALL_FLOOR_HIGH: float = 0.60
FORM_RECALL_FLOOR_MED: float = 0.70
FORM_RECALL_FLOOR_LOW: float = 0.50

FORM_PRECISION_FLOORS: dict[str, float] = {
    "high": FORM_PRECISION_FLOOR_HIGH,
    "med": FORM_PRECISION_FLOOR_MED,
    "low": FORM_PRECISION_FLOOR_LOW,
}
FORM_RECALL_FLOORS: dict[str, float] = {
    "high": FORM_RECALL_FLOOR_HIGH,
    "med": FORM_RECALL_FLOOR_MED,
    "low": FORM_RECALL_FLOOR_LOW,
}

# --------------------------------------------------------------------------
# Pose model
# --------------------------------------------------------------------------

POSE_MODEL_CANDIDATES: tuple[str, ...] = ("blazepose_33", "movenet_17", "rtmpose_halpe26")
DEFAULT_POSE_MODEL: str = "blazepose_33"

# --------------------------------------------------------------------------
# Detector runtime
# --------------------------------------------------------------------------

MIN_KEYPOINT_VISIBILITY: float = 0.50
MIN_VISIBLE_LANDMARK_RATIO: float = 0.60
FLAG_SUSTAIN_FRAMES: int = 2
INSUFFICIENT_EVIDENCE_MIN_FRAMES: int = 2
SUBJECT_LOCK_MIN_BOX_AREA: float = 0.01

# --------------------------------------------------------------------------
# Prototype API
# --------------------------------------------------------------------------

PROTOTYPE_SESSION_MAX_FRAMES: int = 3600
PROTOTYPE_SUPPORTED_EXERCISES: tuple[str, ...] = ("squat", "pushup", "lunge")
PROTOTYPE_DEFAULT_PORT: int = 8000

# --------------------------------------------------------------------------
# Cues
# --------------------------------------------------------------------------

# Root CLAUDE.md "Quality Bar": a cue never exceeds its word cap.
CUE_MAX_WORDS: int = 6

# --------------------------------------------------------------------------
# Exercise library -- the ONE loader (backend/CLAUDE.md: "don't add a second
# exercise reader").
# --------------------------------------------------------------------------


class ExerciseLibraryError(ValueError):
    """Raised when an exercise contract is missing or malformed."""


def load_exercise_library(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load every exercise contract, keyed by exercise_id.

    Raises rather than returning {} on a missing directory. DEPLOY_RUNBOOK's
    warning about a silently-empty library is a real failure mode: a service
    that boots with {} answers /health with 200 and 500s every real request.
    Failing loudly here is what makes the health check meaningful.
    """
    directory = Path(directory) if directory is not None else EXERCISE_LIBRARY_DIR
    if not directory.is_dir():
        raise ExerciseLibraryError(
            f"exercise library directory not found: {directory}. "
            "The detector cannot score anything without contracts; refusing to "
            "start with an empty library."
        )

    library: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            contract = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ExerciseLibraryError(f"{path.name}: invalid JSON: {exc}") from exc

        exercise_id = contract.get("exercise_id")
        if not exercise_id:
            raise ExerciseLibraryError(f"{path.name}: missing 'exercise_id'")
        if exercise_id in library:
            raise ExerciseLibraryError(f"duplicate exercise_id {exercise_id!r} in {path.name}")
        library[exercise_id] = contract

    if not library:
        raise ExerciseLibraryError(f"no exercise contracts found in {directory}")
    return library


def vision_live_exercises(library: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """The exercises the detector will actually run (vision_support: true)."""
    library = library if library is not None else load_exercise_library()
    return sorted(k for k, v in library.items() if v.get("vision_support") is True)
