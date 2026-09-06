"""No-phantom-reps: an empty room or a bench must produce zero reps."""

from __future__ import annotations

from typing import Any

PHANTOM_CLIP_TYPES = ("phantom_bench", "phantom_empty")


def score(results: list[dict[str, Any]]) -> dict[str, Any]:
    checked, failures = 0, []
    for row in results:
        if row.get("clip_type") not in PHANTOM_CLIP_TYPES:
            continue
        checked += 1
        if row["detected"] != 0:
            failures.append({"clip_id": row["clip_id"], "detected": row["detected"]})
    return {
        "dimension": "phantom",
        "checked": checked,
        "failures": failures,
        "passed": not failures,
    }
