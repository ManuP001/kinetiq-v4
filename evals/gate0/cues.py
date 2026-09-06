"""Coaching cues, and the word cap that keeps them readable mid-set.

Root CLAUDE.md "Quality Bar": "A cue never exceeds its word cap (enforced in
cues.py)." Enforcement is here and it raises -- a contract that ships an over-long
cue should fail a test, not quietly render off the edge of a phone screen.
"""

from __future__ import annotations

from typing import Any

from gate_config import CUE_MAX_WORDS


class CueTooLongError(ValueError):
    pass


def word_count(cue: str) -> int:
    return len([w for w in cue.strip().split() if w])


def validate_cue(fault_id: str, cue: str, max_words: int = CUE_MAX_WORDS) -> str:
    n = word_count(cue)
    if n == 0:
        raise CueTooLongError(f"{fault_id}: cue is empty")
    if n > max_words:
        raise CueTooLongError(
            f"{fault_id}: cue {cue!r} is {n} words, over the {max_words}-word cap"
        )
    return cue


def validate_library_cues(library: dict[str, Any], max_words: int = CUE_MAX_WORDS) -> int:
    """Check every cue in every contract. Returns how many were checked."""
    checked = 0
    for exercise_id, contract in sorted(library.items()):
        for fault_id, spec in sorted((contract.get("faults") or {}).items()):
            cue = spec.get("cue")
            if cue is None:
                raise CueTooLongError(f"{exercise_id}.{fault_id}: no cue defined")
            validate_cue(f"{exercise_id}.{fault_id}", cue, max_words)
            checked += 1
    return checked


def cue_for_fault(contract: dict[str, Any], fault_id: str) -> str | None:
    spec = (contract.get("faults") or {}).get(fault_id)
    if not spec:
        return None
    cue = spec.get("cue")
    return validate_cue(fault_id, cue) if cue else None
