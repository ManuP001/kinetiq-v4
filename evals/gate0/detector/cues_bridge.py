"""Thin shim so detector/ can reach evals/gate0/cues.py without a circular import."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_GATE0 = Path(__file__).resolve().parents[1]
if str(_GATE0) not in sys.path:
    sys.path.insert(0, str(_GATE0))

from cues import cue_for_fault  # noqa: E402
from . import flag_hysteresis  # noqa: E402


def pick_cue(reps: list[Any], contract: dict[str, Any]) -> str | None:
    """One cue for the set: the most severe fault on the most recent faulting rep.

    One cue, not a list -- a person mid-set can act on exactly one correction.
    """
    contract_faults = contract.get("faults") or {}
    for rep in reversed(reps):
        if not rep.faults:
            continue
        ordered = flag_hysteresis.worst_first(list(rep.faults), contract_faults)
        cue = cue_for_fault(contract, ordered[0])
        if cue:
            return cue
    return None
