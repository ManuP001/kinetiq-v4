"""Shared shapes for keypoint frames and detector results.

Stdlib only (root CLAUDE.md "Tech Stack": the offline path has no ML deps, and
these dataclasses are imported by the harness as well as the API).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# A keypoint is [x, y, z, visibility]; x/y normalised to the frame, vis in 0..1.
Keypoint = list[float]


@dataclass(frozen=True)
class Person:
    track_id: int
    kp: list[Keypoint]
    box: list[float] | None = None


@dataclass(frozen=True)
class Frame:
    t_ms: int
    pose_model: str
    people: list[Person]


@dataclass
class RepRecord:
    """One counted repetition and whatever the fault checks concluded about it."""

    index: int
    start_ms: int
    end_ms: int
    faults: list[str] = field(default_factory=list)
    insufficient_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "faults": sorted(self.faults),
            "insufficient_evidence": sorted(self.insufficient_evidence),
        }


@dataclass
class DetectorResult:
    exercise_id: str
    rep_count: int
    reps: list[RepRecord] = field(default_factory=list)
    subject_lock_ok: bool = True
    subject_lock_ratio: float = 1.0
    phase: str = "idle"
    coaching_cue: str | None = None
    status: str = "ok"
    notes: list[str] = field(default_factory=list)

    def all_faults(self) -> list[str]:
        seen: set[str] = set()
        for rep in self.reps:
            seen.update(rep.faults)
        return sorted(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exercise_id": self.exercise_id,
            "rep_count": self.rep_count,
            "reps": [r.to_dict() for r in self.reps],
            "subject_lock_ok": self.subject_lock_ok,
            "subject_lock_ratio": round(self.subject_lock_ratio, 4),
            "phase": self.phase,
            "coaching_cue": self.coaching_cue,
            "status": self.status,
            "flags": self.all_faults(),
            "notes": list(self.notes),
        }
