"""Form precision/recall per fault, severity-gated.

Severity gating is the point: a high-severity fault is a safety call, so a false
positive is expensive (higher precision floor) while a miss is judged a little
more leniently. Floors come from config; none is restated here.

Counting rule: a rep whose fault outcome was 'insufficient evidence' is excluded
from that fault's tally rather than scored as a true negative. Scoring an
unjudgeable rep as clean would inflate precision exactly where the detector was
blindest.
"""

from __future__ import annotations

from typing import Any

from detector.flag_hysteresis import normalize_severity
from gate_config import FORM_PRECISION_FLOORS, FORM_RECALL_FLOORS


def _precision(tp: int, fp: int) -> float | None:
    return tp / (tp + fp) if (tp + fp) > 0 else None


def _recall(tp: int, fn: int) -> float | None:
    return tp / (tp + fn) if (tp + fn) > 0 else None


def score(
    rep_pairs: list[dict[str, Any]],
    severities: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """rep_pairs: [{exercise_id, predicted:[fault_id], truth:[fault_id],
                    insufficient:[fault_id]}]"""
    tally: dict[tuple[str, str], dict[str, int]] = {}
    insufficient: dict[str, int] = {}

    for pair in rep_pairs:
        exercise_id = pair["exercise_id"]
        predicted = set(pair.get("predicted") or [])
        truth = set(pair.get("truth") or [])
        unknown = set(pair.get("insufficient") or [])
        for fault_id in unknown:
            insufficient[fault_id] = insufficient.get(fault_id, 0) + 1

        for fault_id in sorted(set(severities.get(exercise_id, {})) | predicted | truth):
            if fault_id in unknown:
                continue
            cell = tally.setdefault((exercise_id, fault_id), {"tp": 0, "fp": 0, "fn": 0})
            in_pred, in_truth = fault_id in predicted, fault_id in truth
            if in_pred and in_truth:
                cell["tp"] += 1
            elif in_pred:
                cell["fp"] += 1
            elif in_truth:
                cell["fn"] += 1

    rows, passed = [], True
    for (exercise_id, fault_id), cell in sorted(tally.items()):
        if cell["tp"] == 0 and cell["fp"] == 0 and cell["fn"] == 0:
            continue
        severity = normalize_severity(severities.get(exercise_id, {}).get(fault_id, "low"))
        p, r = _precision(cell["tp"], cell["fp"]), _recall(cell["tp"], cell["fn"])
        p_floor, r_floor = FORM_PRECISION_FLOORS[severity], FORM_RECALL_FLOORS[severity]
        p_ok = p is None or p >= p_floor
        r_ok = r is None or r >= r_floor
        passed = passed and p_ok and r_ok
        rows.append({
            "exercise_id": exercise_id, "fault_id": fault_id, "severity": severity,
            "tp": cell["tp"], "fp": cell["fp"], "fn": cell["fn"],
            "precision": p, "recall": r,
            "precision_floor": p_floor, "recall_floor": r_floor,
            "passed": p_ok and r_ok,
        })

    return {
        "dimension": "form_pr", "rows": rows,
        "insufficient_evidence": dict(sorted(insufficient.items())),
        "passed": passed,
    }
