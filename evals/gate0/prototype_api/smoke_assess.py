#!/usr/bin/env python3
"""Gate B smoke test: the live API + the real detector, no webcam.

Streams a golden clip through /prototype/assess in small POSTs, exactly the way
the PWA does (new frames each call, reset on the first), and asserts the loop
returns reps, flags and a cue. This is the headless proof that the API path
works; a real-webcam run via run_local is the other half.

Run:  python evals/gate0/prototype_api/smoke_assess.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_GATE0 = Path(__file__).resolve().parents[1]
if str(_GATE0) not in sys.path:
    sys.path.insert(0, str(_GATE0))

from fastapi.testclient import TestClient  # noqa: E402

from prototype_api.main import app  # noqa: E402

CLIP = _GATE0 / "golden" / "squat_kneecave_front_004.json"
BATCH = 8


def main() -> int:
    clip = json.loads(CLIP.read_text(encoding="utf-8"))
    frames = clip["frames"]
    client = TestClient(app)

    health = client.get("/health")
    if health.status_code != 200 or health.json().get("status") != "ok":
        print(f"FAIL: /health returned {health.status_code}: {health.text}")
        return 1
    if not health.json().get("contracts_loaded"):
        print("FAIL: /health reports zero contracts loaded")
        return 1

    posts = 0
    payload = None
    for i in range(0, len(frames), BATCH):
        chunk = frames[i:i + BATCH]
        response = client.post("/prototype/assess", json={
            "session_id": "gate-b-smoke",
            "exercise_id": clip["exercise_id"],
            "reset": i == 0,
            "frames": chunk,
        })
        posts += 1
        if response.status_code != 200:
            print(f"FAIL: POST {posts} returned {response.status_code}: {response.text}")
            return 1
        payload = response.json()

    assert payload is not None
    expected = clip["ground_truth"]["rep_count"]

    print("--- Gate B smoke result ---")
    print(f"clip            : {clip['clip_id']}")
    print(f"frames streamed : {len(frames)} in {posts} POSTs")
    print(f"rep_count       : {payload['rep_count']} (ground truth {expected})")
    print(f"subject_lock_ok : {payload['subject_lock_ok']}")
    print(f"flags (any rep) : {payload['flags']}")
    print(f"coaching_cue    : {payload['coaching_cue']!r}")

    problems = []
    if payload["rep_count"] != expected:
        problems.append(f"rep_count {payload['rep_count']} != ground truth {expected}")
    if not payload["flags"]:
        problems.append("no form flag returned (this clip has a labelled fault)")
    if not payload["coaching_cue"]:
        problems.append("no coaching cue returned")
    if not payload["subject_lock_ok"]:
        problems.append("subject lock failed")

    if problems:
        for p in problems:
            print(f"FAIL: {p}")
        return 1

    print("PASS: live API + real detector returned reps, flags, and a cue.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
