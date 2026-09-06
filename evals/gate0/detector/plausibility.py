"""The validity gate: is this frame good enough to judge at all?

Root CLAUDE.md, deterministic safety veto: an advisory layer "can never ... invent
a rep the validity gate rejects". So this runs first and its verdict is final.
"""

from __future__ import annotations

from typing import Any

from . import geometry, keypoint_map


class FrameVerdict:
    __slots__ = ("ok", "reason", "visible_ratio")

    def __init__(self, ok: bool, reason: str = "", visible_ratio: float = 0.0) -> None:
        self.ok = ok
        self.reason = reason
        self.visible_ratio = visible_ratio

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"FrameVerdict(ok={self.ok}, reason={self.reason!r}, ratio={self.visible_ratio:.2f})"


def check_person(
    kp: list[list[float]],
    pose_model: str,
    required: list[str],
    min_visibility: float,
    min_visible_ratio: float,
) -> FrameVerdict:
    """A person is judgeable when enough of the landmarks the contract needs are visible."""
    if not kp:
        return FrameVerdict(False, "no keypoints", 0.0)

    expected = keypoint_map.EXPECTED_LANDMARK_COUNT.get(pose_model)
    if expected is not None and len(kp) not in (expected, 1):
        # len==1 is the single-point synthetic probe used by check_local/smoke paths.
        return FrameVerdict(
            False, f"expected {expected} landmarks for {pose_model}, got {len(kp)}", 0.0
        )

    if not required:
        return FrameVerdict(True, "", 1.0)

    seen = 0
    for name in required:
        point = keypoint_map.get(kp, pose_model, name)
        if geometry.visible(point, min_visibility):
            seen += 1
    ratio = seen / len(required)
    if ratio < min_visible_ratio:
        return FrameVerdict(
            False, f"only {seen}/{len(required)} required landmarks visible", ratio
        )
    return FrameVerdict(True, "", ratio)


def contract_validity(contract: dict[str, Any], defaults: dict[str, float]) -> dict[str, Any]:
    validity = contract.get("validity") or {}
    return {
        "required": list(validity.get("required_landmarks") or []),
        "min_visibility": float(validity.get("min_visibility", defaults["min_visibility"])),
        "min_visible_ratio": float(
            validity.get("min_visible_ratio", defaults["min_visible_ratio"])
        ),
    }
