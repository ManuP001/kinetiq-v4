#!/usr/bin/env python3
"""
Gate B smoke: prove the live loop end-to-end WITHOUT a webcam.

Drives the real FastAPI app (prototype_api.main) and the real detector (run_detector, the same
one the offline harness calls) with a canned keypoint sequence taken from a committed golden
fixture, exactly as the PWA would stream it: reset on the first POST, new frames each call. Asserts
a completed rep, a form flag, and a coaching cue come back in the documented AssessResponse shape.

Run:  python evals/gate0/prototype_api/smoke_assess.py
Exits non-zero on any failure so it can gate CI / a deploy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

# prototype_api is importable as a package from the gate0 dir (how main.py's tests import it).
_GATE0 = Path(__file__).resolve().parents[1]
if str(_GATE0) not in sys.path:
    sys.path.insert(0, str(_GATE0))

from prototype_api.main import app  # noqa: E402

FIXTURE = _GATE0 / "golden" / "squat_badform_001.keypoints.jsonl"
EXERCISE = "squat"
CHUNK = 8  # frames per POST — mimics the PWA flushing a small batch each interval


def _load_frames(path: Path):
    frames = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return frames


def main() -> int:
    if not FIXTURE.is_file():
        print(f"FAIL: canned fixture missing: {FIXTURE}")
        return 1
    frames = _load_frames(FIXTURE)
    client = TestClient(app)
    session_id = "smoke-session"

    # 0) health
    h = client.get("/health")
    assert h.status_code == 200, f"/health {h.status_code}"

    # 1) stream the fixture in chunks, reset on the first call
    last = None
    for i in range(0, len(frames), CHUNK):
        chunk = frames[i : i + CHUNK]
        body = {
            "session_id": session_id,
            "exercise_id": EXERCISE,
            "frames": chunk,
            "reset": i == 0,
        }
        r = client.post("/prototype/assess", json=body)
        assert r.status_code == 200, f"assess {r.status_code}: {r.text[:200]}"
        last = r.json()

    # 2) assertions — a real rep, real flags, real cue, documented shape
    for key in (
        "rep_count", "rep_in_progress", "phase", "current_flags",
        "insufficient_evidence", "subject_lock_ok", "coaching_cue", "reps",
    ):
        assert key in last, f"response missing field {key!r}"

    rep_count = last["rep_count"]
    all_flags = sorted({f for rep in last["reps"] for f in rep["flags"]})

    print("--- Gate B smoke result ---")
    print(f"frames streamed : {len(frames)} in {(-(-len(frames)//CHUNK))} POSTs")
    print(f"rep_count       : {rep_count}")
    print(f"subject_lock_ok : {last['subject_lock_ok']}")
    print(f"flags (any rep) : {all_flags}")
    print(f"coaching_cue    : {last['coaching_cue']!r}")

    assert rep_count > 0, "expected at least one completed rep from the fixture"
    assert all_flags, "expected at least one form flag from the bad-form fixture"
    assert last["coaching_cue"], "expected a coaching cue once a rep with a flag completed"

    print("PASS: live API + real detector returned reps, flags, and a cue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
