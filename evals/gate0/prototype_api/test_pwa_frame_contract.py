"""The PWA's exact on-the-wire frame shape must survive run_detector.

WHY THIS FILE EXISTS
--------------------
The live PWA was broken for days by a frame shape that every existing test
accepted. `frontend/app.js` built `people: [{track_id, kp}]` with no `box`.
`validate_frame_schema` does not check for `box`, so the frame validated, reached
the detector, and raised `KeyError: 'box'` inside subject_lock -- a bare HTTP 500
that, carrying no CORS header, reached the browser as the generic "Failed to
fetch". Nothing pointed at the real cause.

Every other test missed it because they all feed frames that ALREADY have a box:
  - the offline harness reads golden fixtures, which carry `box`
  - smoke_assess.py replays those same fixtures
  - check_local.sh posts a hand-written probe that includes `box`

So the one shape nobody exercised was the one the real client actually sends.
These tests reproduce the PWA's payload from the browser's side of the wire.

If you change `buildFrame` in frontend/app.js, change the builder here to match.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_GATE0 = Path(__file__).resolve().parents[1]
if str(_GATE0) not in sys.path:
    sys.path.insert(0, str(_GATE0))

from fastapi.testclient import TestClient  # noqa: E402

from prototype_api.main import app  # noqa: E402

N_LANDMARKS = 33


def pwa_bbox(kp):
    """Mirror of bboxOf() in frontend/app.js -- [x, y, w, h] over visible points."""
    pts = [(x, y) for (x, y, _z, vis) in kp if vis >= 0.3]
    if not pts:
        return [0.0, 0.0, 0.0, 0.0]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    return [x0, y0, x1 - x0, y1 - y0]


def pwa_frame(t_ms, *, y_offset=0.0, visibility=0.9, include_box=True):
    """A frame shaped exactly as frontend/app.js buildFrame() emits one."""
    kp = []
    for i in range(N_LANDMARKS):
        x = 0.40 + (i % 5) * 0.03
        y = 0.20 + (i / N_LANDMARKS) * 0.6 + y_offset
        kp.append([round(x, 5), round(y, 5), 0.0, visibility])
    person = {"track_id": 0, "kp": kp}
    if include_box:
        person["box"] = pwa_bbox(kp)
    return {"t_ms": t_ms, "pose_model": "blazepose_33", "people": [person]}


class TestPwaFrameContract(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(app, raise_server_exceptions=False)

    def test_pwa_shaped_frame_is_accepted(self):
        """The regression: this exact payload used to raise KeyError('box') -> 500."""
        r = self.c.post("/prototype/assess", json={
            "session_id": "pwa-contract", "exercise_id": "squat", "reset": True,
            "frames": [pwa_frame(0)],
        })
        self.assertEqual(
            r.status_code, 200,
            f"the PWA's own frame shape must not 500. Body: {r.text[:300]}")
        self.assertIn("rep_count", r.json())

    def test_a_streamed_sequence_is_accepted(self):
        """Several frames in one POST, as the PWA sends after buffering."""
        frames = [pwa_frame(i * 100, y_offset=0.02 * (i % 5)) for i in range(12)]
        r = self.c.post("/prototype/assess", json={
            "session_id": "pwa-seq", "exercise_id": "squat", "reset": True,
            "frames": frames,
        })
        self.assertEqual(r.status_code, 200, r.text[:300])

    def test_every_supported_exercise_accepts_the_pwa_shape(self):
        supported = self.c.get("/health").json()["supported_exercises"]
        self.assertTrue(supported)
        for ex in supported:
            with self.subTest(exercise=ex):
                r = self.c.post("/prototype/assess", json={
                    "session_id": f"pwa-{ex}", "exercise_id": ex, "reset": True,
                    "frames": [pwa_frame(0)],
                })
                self.assertEqual(r.status_code, 200, f"{ex}: {r.text[:200]}")

    def test_low_visibility_frame_does_not_crash(self):
        """Nobody properly in shot: a degenerate box must not take the server down."""
        r = self.c.post("/prototype/assess", json={
            "session_id": "pwa-lowvis", "exercise_id": "squat", "reset": True,
            "frames": [pwa_frame(0, visibility=0.05)],
        })
        self.assertEqual(r.status_code, 200, r.text[:300])

    def test_missing_box_is_a_4xx_not_a_5xx(self):
        """A client that omits `box` is sending a bad request, and should be told
        so. Returning 500 hides the cause behind a CORS-less error the browser
        reports only as "Failed to fetch" -- which is exactly what happened.

        Currently EXPECTED TO FAIL against an unpatched API: it documents the
        server-side hardening that should follow this fix.
        """
        r = self.c.post("/prototype/assess", json={
            "session_id": "pwa-nobox", "exercise_id": "squat", "reset": True,
            "frames": [pwa_frame(0, include_box=False)],
        })
        self.assertLess(
            r.status_code, 500,
            "a frame missing 'box' should be rejected as a client error, not crash "
            f"the detector. Got {r.status_code}.")


if __name__ == "__main__":
    unittest.main()
