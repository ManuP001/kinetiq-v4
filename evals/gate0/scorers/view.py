"""View robustness: accuracy must not collapse between camera angles."""

from __future__ import annotations

from typing import Any

from gate_config import VIEW_MAX_GAP
from scorers.rep_match import clip_accuracy


def score(results: list[dict[str, Any]], max_gap: float = VIEW_MAX_GAP) -> dict[str, Any]:
    by_ex: dict[str, dict[str, list[float]]] = {}
    for row in results:
        if row.get("clip_type") != "normal":
            continue
        by_ex.setdefault(row["exercise_id"], {}).setdefault(row["view"], []).append(
            clip_accuracy(row["detected"], row["truth"])
        )

    breakdown = {}
    for exercise_id, views in sorted(by_ex.items()):
        means = {v: sum(s) / len(s) for v, s in sorted(views.items())}
        gap = (max(means.values()) - min(means.values())) if len(means) > 1 else None
        breakdown[exercise_id] = {
            "views": means, "gap": gap, "passed": gap is None or gap <= max_gap,
        }
    return {
        "dimension": "view", "max_gap": max_gap, "per_exercise": breakdown,
        "passed": all(v["passed"] for v in breakdown.values()) if breakdown else True,
    }
