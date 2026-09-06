"""Subject-lock: did the detector stay on the right body?"""

from __future__ import annotations

from typing import Any

from gate_config import SUBJECT_LOCK_FLOOR


def score(results: list[dict[str, Any]], floor: float = SUBJECT_LOCK_FLOOR) -> dict[str, Any]:
    rows = [r for r in results if r.get("subject_lock_ratio") is not None
            and r.get("clip_type") == "bystander"]
    if not rows:
        return {"dimension": "subject_lock", "floor": floor, "clips": [],
                "mean": None, "passed": True}
    clips = [{"clip_id": r["clip_id"], "ratio": r["subject_lock_ratio"],
              "passed": r["subject_lock_ratio"] >= floor} for r in rows]
    mean = sum(c["ratio"] for c in clips) / len(clips)
    return {
        "dimension": "subject_lock", "floor": floor, "clips": clips,
        "mean": mean, "passed": all(c["passed"] for c in clips),
    }
