"""`run_detector` -- the ONE detector entry point.

Root CLAUDE.md, one-detector-two-consumers: this function is called by BOTH the
live API (evals/gate0/prototype_api) and the offline harness (aggregate.py).
Detection logic changes here, never in a consumer.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - direct-script convenience
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from . import cues_bridge as _cues  # noqa: E402
from . import faults as fault_checks  # noqa: E402
from . import flag_hysteresis, plausibility  # noqa: E402
from .rep_counter import RepCounter  # noqa: E402
from .subject_lock import SubjectTracker  # noqa: E402

try:
    from gate_config import (  # type: ignore
        FLAG_SUSTAIN_FRAMES,
        INSUFFICIENT_EVIDENCE_MIN_FRAMES,
        MIN_KEYPOINT_VISIBILITY,
        MIN_VISIBLE_LANDMARK_RATIO,
        SUBJECT_LOCK_FLOOR,
        SUBJECT_LOCK_MIN_BOX_AREA,
        RepRecord,
        DetectorResult,
    )
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from gate_config import (  # type: ignore
        FLAG_SUSTAIN_FRAMES,
        INSUFFICIENT_EVIDENCE_MIN_FRAMES,
        MIN_KEYPOINT_VISIBILITY,
        MIN_VISIBLE_LANDMARK_RATIO,
        SUBJECT_LOCK_FLOOR,
        SUBJECT_LOCK_MIN_BOX_AREA,
        RepRecord,
        DetectorResult,
    )


class DetectorError(ValueError):
    pass


def _contract_for(exercise_id: str, library: dict[str, Any]) -> dict[str, Any]:
    try:
        contract = library[exercise_id]
    except KeyError:
        raise DetectorError(
            f"unknown exercise_id {exercise_id!r}; known: {sorted(library)}"
        ) from None
    if not contract.get("vision_support"):
        raise DetectorError(
            f"{exercise_id!r} is not vision-live (vision_support: false). It has a contract "
            "but no validated rep signal or fault checks, so the detector will not guess at "
            "one. Turning it on is gated behind GATE G-REAL."
        )
    if not contract.get("rep_signal"):
        raise DetectorError(f"{exercise_id!r} is vision-live but declares no rep_signal")
    return contract


def run_detector(
    frames: list[dict[str, Any]],
    exercise_id: str,
    library: dict[str, Any],
    *,
    subject_lock_floor: float = SUBJECT_LOCK_FLOOR,
) -> DetectorResult:
    """Score a sequence of keypoint frames for one exercise.

    `frames` are validated frame dicts (see golden_loader.validate_frame_schema).
    Returns a DetectorResult; never raises on merely-poor input, only on a
    contract/config error the caller must fix.
    """
    contract = _contract_for(exercise_id, library)
    signal = contract["rep_signal"]
    contract_faults: dict[str, Any] = contract.get("faults") or {}
    fault_ids = sorted(contract_faults)
    frame_fault_ids = [f for f in fault_ids
                       if fault_checks.scope_of(contract_faults[f]["check"]) == "frame"]
    rep_fault_ids = [f for f in fault_ids
                     if fault_checks.scope_of(contract_faults[f]["check"]) == "rep"]

    validity = plausibility.contract_validity(
        contract,
        {"min_visibility": MIN_KEYPOINT_VISIBILITY,
         "min_visible_ratio": MIN_VISIBLE_LANDMARK_RATIO},
    )
    min_vis = validity["min_visibility"]

    # Fail fast on a contract naming a check we don't implement, before scoring.
    for fid, spec in contract_faults.items():
        fault_checks.get_check(spec["check"])

    tracker = SubjectTracker(SUBJECT_LOCK_MIN_BOX_AREA)
    counter = RepCounter(signal, min_vis)
    accumulator = flag_hysteresis.FlagAccumulator(INSUFFICIENT_EVIDENCE_MIN_FRAMES)

    reps: list[RepRecord] = []
    notes: list[str] = []
    rep_min_angle: float | None = None
    reps_emitted = 0

    for frame in frames:
        pose_model = frame["pose_model"]
        person = tracker.select(frame.get("people") or [])
        if person is None:
            continue

        kp = person.get("kp") or []
        verdict = plausibility.check_person(
            kp, pose_model, validity["required"], min_vis, validity["min_visible_ratio"]
        )

        angle = counter.measure(kp, pose_model) if verdict.ok else None
        if angle is not None:
            rep_min_angle = angle if rep_min_angle is None else min(rep_min_angle, angle)

        ctx = {
            "kp": kp,
            "pose_model": pose_model,
            "min_visibility": min_vis,
            "rep_min_angle": rep_min_angle,
            "active_side": counter._locked_side,
        }

        if verdict.ok:
            for fid in frame_fault_ids:
                spec = contract_faults[fid]
                outcome = fault_checks.evaluate(spec["check"], ctx, spec.get("params") or {})
                accumulator.observe(
                    fid,
                    triggered=bool(outcome),
                    judgeable=outcome is not None,
                    sustain_frames=int(spec.get("sustain_frames", FLAG_SUSTAIN_FRAMES)),
                )
            counter.update(kp, pose_model, int(frame["t_ms"]))

        # A completed rep closes the evidence window for that rep.
        if counter.count > reps_emitted:
            start, end = counter.rep_boundaries[-1]
            fired, unknown = accumulator.resolve(frame_fault_ids)

            # Rep-scope checks answer once, now that the whole rep is known.
            for fid in rep_fault_ids:
                spec = contract_faults[fid]
                outcome = fault_checks.evaluate(spec["check"], ctx, spec.get("params") or {})
                if outcome is None:
                    unknown.append(fid)
                elif outcome:
                    fired.append(fid)
            fired.sort()
            unknown.sort()

            reps.append(
                RepRecord(index=counter.count, start_ms=start, end_ms=end,
                          faults=fired, insufficient_evidence=unknown)
            )
            accumulator.reset()
            rep_min_angle = None
            reps_emitted = counter.count

    lock_ratio = tracker.ratio
    lock_ok = lock_ratio >= subject_lock_floor
    if not lock_ok:
        notes.append(
            f"subject lock held {lock_ratio:.1%} of frames, below the {subject_lock_floor:.0%} floor"
        )

    cue = _cues.pick_cue(reps, contract)

    return DetectorResult(
        exercise_id=exercise_id,
        rep_count=len(reps),
        reps=reps,
        subject_lock_ok=lock_ok,
        subject_lock_ratio=lock_ratio,
        phase=counter.phase,
        coaching_cue=cue,
        status="ok",
        notes=notes,
    )
