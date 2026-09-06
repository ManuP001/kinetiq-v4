"""Landmark-name -> index maps per pose model.

frontend/CLAUDE.md pins the wire format to blazepose_33, and the PWA must send the
landmark order this file expects. The other two models are declared in
POSE_MODEL_CANDIDATES but are not wired to a live consumer, so they are mapped only
as far as the shared subset the detector actually reads.
"""

from __future__ import annotations

# MediaPipe PoseLandmarker (BlazePose) 33-landmark order.
BLAZEPOSE_33: dict[str, int] = {
    "nose": 0,
    "left_eye_inner": 1, "left_eye": 2, "left_eye_outer": 3,
    "right_eye_inner": 4, "right_eye": 5, "right_eye_outer": 6,
    "left_ear": 7, "right_ear": 8,
    "mouth_left": 9, "mouth_right": 10,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_pinky": 17, "right_pinky": 18,
    "left_index": 19, "right_index": 20,
    "left_thumb": 21, "right_thumb": 22,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
    "left_heel": 29, "right_heel": 30,
    "left_foot_index": 31, "right_foot_index": 32,
}

MOVENET_17: dict[str, int] = {
    "nose": 0, "left_eye": 1, "right_eye": 2, "left_ear": 3, "right_ear": 4,
    "left_shoulder": 5, "right_shoulder": 6, "left_elbow": 7, "right_elbow": 8,
    "left_wrist": 9, "right_wrist": 10, "left_hip": 11, "right_hip": 12,
    "left_knee": 13, "right_knee": 14, "left_ankle": 15, "right_ankle": 16,
}

RTMPOSE_HALPE26: dict[str, int] = dict(MOVENET_17)
RTMPOSE_HALPE26.update({"head": 17, "neck": 18, "hip": 19,
                        "left_big_toe": 20, "right_big_toe": 21,
                        "left_small_toe": 22, "right_small_toe": 23,
                        "left_heel": 24, "right_heel": 25})

_MAPS: dict[str, dict[str, int]] = {
    "blazepose_33": BLAZEPOSE_33,
    "movenet_17": MOVENET_17,
    "rtmpose_halpe26": RTMPOSE_HALPE26,
}

EXPECTED_LANDMARK_COUNT: dict[str, int] = {
    "blazepose_33": 33, "movenet_17": 17, "rtmpose_halpe26": 26,
}


class KeypointMapError(ValueError):
    pass


def landmark_map(pose_model: str) -> dict[str, int]:
    try:
        return _MAPS[pose_model]
    except KeyError:
        raise KeypointMapError(
            f"unknown pose_model {pose_model!r}; expected one of {sorted(_MAPS)}"
        ) from None


def index_of(pose_model: str, name: str) -> int:
    mapping = landmark_map(pose_model)
    try:
        return mapping[name]
    except KeyError:
        raise KeypointMapError(
            f"{pose_model} has no landmark {name!r}. This detector never guesses a "
            "landmark index -- add it to the map or pick a model that has it."
        ) from None


def get(kp: list[list[float]], pose_model: str, name: str) -> list[float] | None:
    """Return [x, y, z, vis] for a named landmark, or None if it isn't present."""
    try:
        idx = index_of(pose_model, name)
    except KeypointMapError:
        return None
    if idx >= len(kp):
        return None
    return kp[idx]
