#!/usr/bin/env python3
"""Regenerate frontend/severities.json from exercises/*.json.

frontend/CLAUDE.md: "Flag color comes from severities.json (generated from
exercises/*.json); don't hardcode a severity map in JS." Run this whenever a
contract's severities change.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals" / "gate0"))

from exercise_lib import load_fault_metadata  # noqa: E402

meta = load_fault_metadata()
out = {
    "_generated_by": "frontend/generate_severities.py -- do not edit by hand",
    "exercises": {
        eid: {fid: {"severity": v["severity"], "cue": v["cue"]}
              for fid, v in faults.items()}
        for eid, faults in meta.items() if faults
    },
}
path = ROOT / "frontend" / "severities.json"
path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {path.relative_to(ROOT)} ({sum(len(v) for v in out['exercises'].values())} faults)")
