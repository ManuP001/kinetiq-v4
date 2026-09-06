"""Turn per-frame fault observations into a per-rep verdict.

Two jobs:
  1. Sustain -- a fault must hold for `sustain_frames` before it fires, so one
     noisy frame is not a coaching cue.
  2. Insufficient evidence -- if a rep never had enough judgeable frames for a
     check, that is NOT "clean". It is unknown, and saying so is the difference
     between an honest report and a fabricated pass.
"""

from __future__ import annotations

from typing import Any


class FlagAccumulator:
    def __init__(self, min_frames_for_evidence: int) -> None:
        self.min_frames_for_evidence = min_frames_for_evidence
        self._run: dict[str, int] = {}
        self._fired: set[str] = set()
        self._judged: dict[str, int] = {}

    def observe(self, fault_id: str, triggered: bool, judgeable: bool, sustain_frames: int) -> None:
        if not judgeable:
            self._run[fault_id] = 0
            return
        self._judged[fault_id] = self._judged.get(fault_id, 0) + 1
        if triggered:
            self._run[fault_id] = self._run.get(fault_id, 0) + 1
            if self._run[fault_id] >= max(1, sustain_frames):
                self._fired.add(fault_id)
        else:
            self._run[fault_id] = 0

    def resolve(self, all_fault_ids: list[str]) -> tuple[list[str], list[str]]:
        """Return (fired_faults, insufficient_evidence)."""
        fired = sorted(self._fired)
        unknown = sorted(
            fid for fid in all_fault_ids
            if fid not in self._fired
            and self._judged.get(fid, 0) < self.min_frames_for_evidence
        )
        return fired, unknown

    def reset(self) -> None:
        self._run.clear()
        self._fired.clear()
        self._judged.clear()


def severity_rank(severity: str) -> int:
    return {"high": 3, "med": 2, "low": 1}.get(normalize_severity(severity), 0)


def normalize_severity(raw: str) -> str:
    """`medium` is a legacy spelling; `med` is canonical. Alias kept, not primary."""
    value = (raw or "").strip().lower()
    if value == "medium":
        return "med"
    if value not in ("high", "med", "low"):
        raise ValueError(f"unknown severity {raw!r}; expected high/med/low")
    return value


def worst_first(faults: list[str], contract_faults: dict[str, Any]) -> list[str]:
    """Order faults so the most severe is first -- the cue picker takes [0]."""
    return sorted(
        faults,
        key=lambda f: (-severity_rank(contract_faults.get(f, {}).get("severity", "low")), f),
    )
