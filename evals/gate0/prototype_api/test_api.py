"""Detector API tests, including the privacy and one-detector invariants."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_GATE0 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_GATE0))

from fastapi.testclient import TestClient  # noqa: E402

from prototype_api.main import app  # noqa: E402

GOLDEN = _GATE0 / "golden"


def one_frame(t_ms=0, track_id=0):
    return {"t_ms": t_ms, "pose_model": "blazepose_33",
            "people": [{"track_id": track_id, "kp": [[0.5, 0.5, 0.0, 0.9]],
                        "box": [0.4, 0.4, 0.2, 0.2]}]}


class TestHealth(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(app)

    def test_health_ok(self):
        r = self.c.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_health_reports_loaded_contracts(self):
        """A zero here is the silent-empty-library failure; it must be visible."""
        self.assertGreater(self.c.get("/health").json()["contracts_loaded"], 0)

    def test_health_lists_only_vision_live_exercises(self):
        supported = self.c.get("/health").json()["supported_exercises"]
        self.assertEqual(sorted(supported), ["lunge", "pushup", "squat"])

    def test_health_declares_no_pose_runtime(self):
        self.assertIsNone(self.c.get("/health").json()["pose_runtime"])


class TestAssess(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(app)

    def test_single_static_frame_is_not_a_rep(self):
        r = self.c.post("/prototype/assess", json={
            "session_id": "t1", "exercise_id": "squat", "reset": True,
            "frames": [one_frame()]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["rep_count"], 0)

    def test_unsupported_exercise_is_422(self):
        r = self.c.post("/prototype/assess", json={
            "session_id": "t2", "exercise_id": "deadlift", "reset": True,
            "frames": [one_frame()]})
        self.assertEqual(r.status_code, 422)

    def test_unknown_exercise_is_422(self):
        r = self.c.post("/prototype/assess", json={
            "session_id": "t3", "exercise_id": "moonwalk", "reset": True,
            "frames": [one_frame()]})
        self.assertEqual(r.status_code, 422)

    def test_malformed_frame_is_422_not_500(self):
        bad = {"t_ms": 0, "pose_model": "blazepose_33",
               "people": [{"kp": [[0.5, 0.5, 0.0, 0.9]]}]}  # no track_id
        r = self.c.post("/prototype/assess", json={
            "session_id": "t4", "exercise_id": "squat", "reset": True, "frames": [bad]})
        self.assertEqual(r.status_code, 422)

    def test_unknown_pose_model_rejected(self):
        bad = one_frame()
        bad["pose_model"] = "handwave_5"
        r = self.c.post("/prototype/assess", json={
            "session_id": "t5", "exercise_id": "squat", "reset": True, "frames": [bad]})
        self.assertEqual(r.status_code, 422)

    def test_buffer_accumulates_across_posts(self):
        self.c.post("/prototype/assess", json={
            "session_id": "acc", "exercise_id": "squat", "reset": True,
            "frames": [one_frame(0)]})
        r = self.c.post("/prototype/assess", json={
            "session_id": "acc", "exercise_id": "squat", "reset": False,
            "frames": [one_frame(100)]})
        self.assertEqual(r.json()["frames_buffered"], 2)

    def test_reset_clears_the_buffer(self):
        self.c.post("/prototype/assess", json={
            "session_id": "rst", "exercise_id": "squat", "reset": True,
            "frames": [one_frame(0), one_frame(100)]})
        r = self.c.post("/prototype/assess", json={
            "session_id": "rst", "exercise_id": "squat", "reset": True,
            "frames": [one_frame(0)]})
        self.assertEqual(r.json()["frames_buffered"], 1)

    def test_sessions_are_isolated(self):
        self.c.post("/prototype/assess", json={
            "session_id": "a", "exercise_id": "squat", "reset": True,
            "frames": [one_frame(0), one_frame(100)]})
        r = self.c.post("/prototype/assess", json={
            "session_id": "b", "exercise_id": "squat", "reset": True,
            "frames": [one_frame(0)]})
        self.assertEqual(r.json()["frames_buffered"], 1)

    def test_reset_endpoint(self):
        self.c.post("/prototype/assess", json={
            "session_id": "z", "exercise_id": "squat", "reset": True,
            "frames": [one_frame()]})
        self.assertEqual(self.c.post("/prototype/reset?session_id=z").status_code, 200)

    def test_a_real_clip_produces_the_expected_reps_and_flags(self):
        """One-detector-two-consumers: the API must agree with the harness."""
        clip = json.loads((GOLDEN / "squat_kneecave_front_004.json").read_text(encoding="utf-8"))
        r = self.c.post("/prototype/assess", json={
            "session_id": "clip", "exercise_id": "squat", "reset": True,
            "frames": clip["frames"]})
        payload = r.json()
        self.assertEqual(payload["rep_count"], clip["ground_truth"]["rep_count"])
        self.assertIn("knee_cave_left", payload["flags"])
        self.assertTrue(payload["coaching_cue"])

    def test_response_shape(self):
        r = self.c.post("/prototype/assess", json={
            "session_id": "shape", "exercise_id": "squat", "reset": True,
            "frames": [one_frame()]}).json()
        for key in ("rep_count", "reps", "flags", "phase", "coaching_cue",
                    "subject_lock_ok", "frames_buffered"):
            self.assertIn(key, r)


class TestPrivacyInvariant(unittest.TestCase):
    """The API must be structurally incapable of receiving pixels."""

    def test_no_pose_runtime_is_importable_in_this_service(self):
        for module in ("mediapipe", "cv2", "tensorflow", "torch", "rtmlib"):
            self.assertNotIn(module, sys.modules,
                             f"{module} must not be loaded by the detector API")

    def test_source_has_no_image_handling_code(self):
        """Scan CODE only. Comments and docstrings are stripped first -- the
        module docstring says "no image decoder", and a naive substring scan
        would fail on the very sentence asserting the invariant."""
        import ast

        tree = ast.parse((Path(__file__).parent / "main.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                body = getattr(node, "body", None)
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body.pop(0)
                    if not body:
                        body.append(ast.Pass())
        code = ast.unparse(tree).lower()  # ast.unparse drops comments entirely

        for token in ("image", "jpeg", "png", "base64", "b64decode", "videoframe",
                      "pillow", "imread", "cv2"):
            self.assertNotIn(token, code,
                             f"main.py has code mentioning {token!r}; "
                             "this API takes keypoints only")

    def test_request_model_has_no_image_field(self):
        from prototype_api.main import AssessRequest
        self.assertEqual(sorted(AssessRequest.model_fields),
                         ["exercise_id", "frames", "reset", "session_id"])


class TestCorsConfig(unittest.TestCase):
    def test_origins_are_normalised(self):
        from prototype_api import main
        for origin in main.ALLOWED_ORIGINS:
            if origin != "*":
                self.assertFalse(origin.endswith("/"),
                                 "a trailing slash makes the origin never match")


if __name__ == "__main__":
    unittest.main()
