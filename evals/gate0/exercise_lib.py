"""Contract accessors for the harness. The loader itself lives in config.py."""

from __future__ import annotations

from typing import Any

from detector.flag_hysteresis import normalize_severity  # noqa: F401
from gate_config import ExerciseLibraryError, load_exercise_library


def load_fault_severities(directory=None) -> dict[str, dict[str, str]]:
    """{exercise_id: {fault_id: severity}} -- what the PWA's severities.json mirrors."""
    library = load_exercise_library(directory)
    return {
        eid: {fid: normalize_severity(spec.get("severity", "low"))
              for fid, spec in sorted((c.get("faults") or {}).items())}
        for eid, c in sorted(library.items())
    }


def load_fault_metadata(directory=None) -> dict[str, dict[str, dict[str, Any]]]:
    library = load_exercise_library(directory)
    return {
        eid: {
            fid: {
                "severity": normalize_severity(spec.get("severity", "low")),
                "cue": spec.get("cue"),
                "check": spec.get("check"),
                "status": spec.get("status"),
            }
            for fid, spec in sorted((c.get("faults") or {}).items())
        }
        for eid, c in sorted(library.items())
    }


def known_faults(exercise_id: str, directory=None) -> list[str]:
    library = load_exercise_library(directory)
    if exercise_id not in library:
        raise ExerciseLibraryError(f"unknown exercise_id {exercise_id!r}")
    return sorted((library[exercise_id].get("faults") or {}))
