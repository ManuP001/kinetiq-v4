"""Rep-count accuracy against PT ground truth."""

from __future__ import annotations

from typing import Any

from gate_config import GATE0_TARGET_ACCURACY


def clip_accuracy(detected: int, truth: int) -> float:
    """1.0 on an exact match, degrading with the size of the miss.

    Deliberately not |d-t|<=1 tolerance: a systematic off-by-one is exactly the
    bug the gate exists to catch, and tolerance would hide it.
    """
    if truth == 0:
        return 1.0 if detected == 0 else 0.0
    return max(0.0, 1.0 - abs(detected - truth) / truth)


def score(results: list[dict[str, Any]], target: float = GATE0_TARGET_ACCURACY) -> dict[str, Any]:
    """results: [{exercise_id, clip_id, detected, truth}]"""
    per_exercise: dict[str, list[float]] = {}
    for row in results:
        per_exercise.setdefault(row["exercise_id"], []).append(
            clip_accuracy(row["detected"], row["truth"])
        )

    breakdown = {}
    for exercise_id, scores in sorted(per_exercise.items()):
        mean = sum(scores) / len(scores)
        breakdown[exercise_id] = {
            "accuracy": mean, "clips": len(scores), "passed": mean >= target,
        }
    return {
        "dimension": "rep_accuracy",
        "target": target,
        "per_exercise": breakdown,
        "passed": all(v["passed"] for v in breakdown.values()) if breakdown else True,
    }
