"""Detector unit tests: geometry, validity, rep counting, faults, hysteresis."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_config  # noqa: E402,F401
from detector import faults, flag_hysteresis, geometry, keypoint_map, plausibility  # noqa: E402
from detector.adapter import DetectorError, run_detector  # noqa: E402
from detector.rep_counter import RepCounter  # noqa: E402
from detector.subject_lock import SubjectTracker  # noqa: E402

MODEL = "blazepose_33"


def kp33(**named):
    """Build a 33-landmark array; named args are 'left_hip=(x, y)' or (x, y, z)."""
    kp = [[0.5, 0.5, 0.0, 0.1] for _ in range(33)]
    for name, pos in named.items():
        x, y = pos[0], pos[1]
        z = pos[2] if len(pos) > 2 else 0.0
        kp[keypoint_map.index_of(MODEL, name)] = [x, y, z, 0.95]
    return kp


class TestGeometry(unittest.TestCase):
    def test_right_angle(self):
        a, b, c = [0, 0, 0, 1], [0, 1, 0, 1], [1, 1, 0, 1]
        self.assertAlmostEqual(geometry.joint_angle(a, b, c), 90.0, places=4)

    def test_straight_line_is_180(self):
        a, b, c = [0, 0, 0, 1], [0, 1, 0, 1], [0, 2, 0, 1]
        self.assertAlmostEqual(geometry.joint_angle(a, b, c), 180.0, places=4)

    def test_degenerate_returns_none(self):
        p = [0.5, 0.5, 0.0, 1]
        self.assertIsNone(geometry.joint_angle(p, p, [1, 1, 0, 1]))

    def test_angle_uses_z(self):
        """A bend purely in depth must still register -- this is what makes a
        head-on squat countable."""
        a, b, c = [0, 0, 0, 1], [0, 1, 0, 1], [0, 1, 1, 1]
        self.assertAlmostEqual(geometry.joint_angle(a, b, c), 90.0, places=4)

    def test_vertical_lean(self):
        self.assertAlmostEqual(
            geometry.angle_from_vertical([0, 0, 0, 1], [0, 1, 0, 1]), 0.0, places=4)
        self.assertAlmostEqual(
            geometry.angle_from_vertical([1, 0, 0, 1], [0, 1, 0, 1]), 45.0, places=4)

    def test_lean_combines_x_and_z(self):
        self.assertAlmostEqual(
            geometry.angle_from_vertical([0, 0, 1, 1], [0, 1, 0, 1]), 45.0, places=4)

    def test_ema_seeds_on_first_sample(self):
        self.assertEqual(geometry.ema(None, 10.0, 0.5), 10.0)
        self.assertEqual(geometry.ema(10.0, 20.0, 0.5), 15.0)

    def test_box_iou(self):
        self.assertAlmostEqual(geometry.box_iou([0, 0, 1, 1], [0, 0, 1, 1]), 1.0)
        self.assertAlmostEqual(geometry.box_iou([0, 0, 1, 1], [2, 2, 1, 1]), 0.0)

    def test_visible(self):
        self.assertTrue(geometry.visible([0, 0, 0, 0.9], 0.5))
        self.assertFalse(geometry.visible([0, 0, 0, 0.2], 0.5))
        self.assertFalse(geometry.visible(None, 0.5))


class TestKeypointMap(unittest.TestCase):
    def test_blazepose_has_33(self):
        self.assertEqual(len(keypoint_map.BLAZEPOSE_33), 33)
        self.assertEqual(keypoint_map.EXPECTED_LANDMARK_COUNT[MODEL], 33)

    def test_indices_are_unique(self):
        idx = list(keypoint_map.BLAZEPOSE_33.values())
        self.assertEqual(len(idx), len(set(idx)))
        self.assertEqual(sorted(idx), list(range(33)))

    def test_unknown_model_raises(self):
        with self.assertRaises(keypoint_map.KeypointMapError):
            keypoint_map.landmark_map("not_a_model")

    def test_unknown_landmark_raises_rather_than_guessing(self):
        with self.assertRaises(keypoint_map.KeypointMapError):
            keypoint_map.index_of(MODEL, "tail")

    def test_get_returns_none_past_end(self):
        self.assertIsNone(keypoint_map.get([[0, 0, 0, 1]], MODEL, "left_ankle"))


class TestPlausibility(unittest.TestCase):
    REQUIRED = ["left_hip", "right_hip", "left_knee", "right_knee"]

    def test_rejects_empty(self):
        self.assertFalse(plausibility.check_person([], MODEL, self.REQUIRED, 0.5, 0.6).ok)

    def test_rejects_wrong_landmark_count(self):
        v = plausibility.check_person([[0, 0, 0, 1]] * 17, MODEL, self.REQUIRED, 0.5, 0.6)
        self.assertFalse(v.ok)
        self.assertIn("expected 33", v.reason)

    def test_accepts_single_point_probe(self):
        """check_local.sh sends one point; that must not be a schema error."""
        self.assertTrue(plausibility.check_person([[0.5, 0.5, 0, 0.9]], MODEL, [], 0.5, 0.6).ok)

    def test_rejects_when_too_few_visible(self):
        kp = kp33(left_hip=(0.4, 0.5))
        v = plausibility.check_person(kp, MODEL, self.REQUIRED, 0.5, 0.6)
        self.assertFalse(v.ok)
        self.assertAlmostEqual(v.visible_ratio, 0.25)

    def test_accepts_when_enough_visible(self):
        kp = kp33(left_hip=(0.4, 0.5), right_hip=(0.6, 0.5),
                  left_knee=(0.4, 0.7), right_knee=(0.6, 0.7))
        self.assertTrue(plausibility.check_person(kp, MODEL, self.REQUIRED, 0.5, 0.6).ok)


class TestSubjectLock(unittest.TestCase):
    def person(self, tid, box):
        return {"track_id": tid, "kp": [[0.5, 0.5, 0, 0.9]], "box": box}

    def test_picks_largest_central(self):
        t = SubjectTracker(0.01)
        chosen = t.select([self.person(1, [0.0, 0.0, 0.1, 0.1]),
                           self.person(2, [0.35, 0.3, 0.3, 0.4])])
        self.assertEqual(chosen["track_id"], 2)

    def test_stays_on_subject_when_bystander_is_bigger(self):
        t = SubjectTracker(0.01)
        t.select([self.person(0, [0.35, 0.3, 0.3, 0.4])])
        chosen = t.select([self.person(0, [0.35, 0.3, 0.3, 0.4]),
                           self.person(9, [0.0, 0.0, 0.6, 0.9])])
        self.assertEqual(chosen["track_id"], 0, "a bigger bystander must not steal the lock")

    def test_reacquires_by_overlap_when_track_id_churns(self):
        t = SubjectTracker(0.01)
        t.select([self.person(0, [0.35, 0.3, 0.3, 0.4])])
        chosen = t.select([self.person(5, [0.36, 0.31, 0.3, 0.4])])
        self.assertIsNotNone(chosen)
        self.assertEqual(t.track_id, 5)

    def test_ratio_counts_missing_frames(self):
        t = SubjectTracker(0.01)
        t.select([self.person(0, [0.3, 0.3, 0.3, 0.4])])
        t.select([])
        self.assertAlmostEqual(t.ratio, 0.5)
        self.assertFalse(t.ok(0.99))

    def test_empty_stream_is_not_a_lock_failure(self):
        self.assertAlmostEqual(SubjectTracker(0.01).ratio, 1.0)


class TestRepCounter(unittest.TestCase):
    SIGNAL = {"type": "joint_angle", "joints": ["hip", "knee", "ankle"], "side": "left",
              "down_enter_deg": 130.0, "up_exit_deg": 160.0, "min_rep_ms": 500}

    def legs(self, knee_deg):
        """Place a left leg whose hip-knee-ankle angle is knee_deg."""
        total = 180.0 - knee_deg
        phi, psi = 0.3 * total, 0.7 * total
        ax, ay = 0.5, 0.9
        kx = ax + 0.2 * math.sin(math.radians(phi))
        ky = ay - 0.2 * math.cos(math.radians(phi))
        hx = kx - 0.22 * math.sin(math.radians(psi))
        hy = ky - 0.22 * math.cos(math.radians(psi))
        return kp33(left_ankle=(ax, ay), left_knee=(kx, ky), left_hip=(hx, hy))

    def drive(self, angles, dt=100):
        rc = RepCounter(self.SIGNAL, 0.5)
        for i, a in enumerate(angles):
            rc.update(self.legs(a), MODEL, i * dt)
        return rc

    def test_rejects_non_hysteretic_contract(self):
        bad = dict(self.SIGNAL, down_enter_deg=160.0, up_exit_deg=160.0)
        with self.assertRaises(ValueError):
            RepCounter(bad, 0.5)

    def test_counts_one_clean_rep(self):
        angles = [175] * 3 + [150, 120, 95, 90, 95, 120, 150] + [175] * 3
        self.assertEqual(self.drive(angles).count, 1)

    def test_dither_at_the_threshold_is_not_a_rep(self):
        angles = [175, 158, 162, 158, 162, 158, 162, 175]
        self.assertEqual(self.drive(angles).count, 0,
                         "hysteresis must swallow noise around one threshold")

    def test_too_fast_is_rejected(self):
        angles = [175, 90, 175]
        self.assertEqual(self.drive(angles, dt=50).count, 0)

    def test_measure_returns_none_when_occluded(self):
        rc = RepCounter(self.SIGNAL, 0.5)
        self.assertIsNone(rc.measure(kp33(), MODEL))

    def test_phase_is_reported(self):
        rc = self.drive([175, 150, 120, 95])
        self.assertIn(rc.phase, ("down", "bottom", "descending"))


class TestFaultRegistry(unittest.TestCase):
    def test_unknown_check_raises(self):
        with self.assertRaises(faults.UnknownCheckError):
            faults.get_check("no_such_check")

    def test_depth_check_is_rep_scope(self):
        self.assertEqual(faults.scope_of("min_angle_above"), "rep")

    def test_other_checks_are_frame_scope(self):
        for name in ("trunk_lean_above", "body_line_break", "knee_valgus"):
            self.assertEqual(faults.scope_of(name), "frame")

    def test_min_angle_above(self):
        self.assertTrue(faults.evaluate("min_angle_above", {"rep_min_angle": 120}, {"deg": 100}))
        self.assertFalse(faults.evaluate("min_angle_above", {"rep_min_angle": 85}, {"deg": 100}))
        self.assertIsNone(faults.evaluate("min_angle_above", {"rep_min_angle": None}, {"deg": 100}))

    def ctx(self, kp):
        return {"kp": kp, "pose_model": MODEL, "min_visibility": 0.5,
                "rep_min_angle": None, "active_side": "left"}

    def test_trunk_lean(self):
        upright = kp33(left_shoulder=(0.5, 0.4), right_shoulder=(0.5, 0.4),
                       left_hip=(0.5, 0.7), right_hip=(0.5, 0.7))
        self.assertFalse(faults.evaluate("trunk_lean_above", self.ctx(upright), {"deg": 55}))
        leaning = kp33(left_shoulder=(0.9, 0.4), right_shoulder=(0.9, 0.4),
                       left_hip=(0.5, 0.7), right_hip=(0.5, 0.7))
        self.assertTrue(faults.evaluate("trunk_lean_above", self.ctx(leaning), {"deg": 45}))

    def test_trunk_lean_unjudgeable_without_landmarks(self):
        self.assertIsNone(faults.evaluate("trunk_lean_above", self.ctx(kp33()), {"deg": 55}))

    def test_body_line_break(self):
        straight = kp33(left_shoulder=(0.2, 0.5), left_hip=(0.5, 0.5), left_ankle=(0.8, 0.5))
        self.assertFalse(faults.evaluate("body_line_break", self.ctx(straight), {"deg": 160}))
        sagging = kp33(left_shoulder=(0.2, 0.5), left_hip=(0.5, 0.68), left_ankle=(0.8, 0.5))
        self.assertTrue(faults.evaluate("body_line_break", self.ctx(sagging), {"deg": 160}))

    def test_knee_valgus_refuses_a_side_view(self):
        """Hips nearly overlapping means we cannot see across the body."""
        side = kp33(left_shoulder=(0.5, 0.4), right_shoulder=(0.51, 0.4),
                    left_hip=(0.5, 0.65), right_hip=(0.51, 0.65),
                    left_knee=(0.6, 0.78), left_ankle=(0.5, 0.9))
        self.assertIsNone(faults.evaluate(
            "knee_valgus", self.ctx(side), {"side": "left", "ratio": 0.85,
                                            "min_hip_width_ratio": 0.15}))

    def test_knee_valgus_detects_cave_in_front_view(self):
        params = {"side": "left", "ratio": 0.85, "min_hip_width_ratio": 0.15}
        clean = kp33(left_shoulder=(0.42, 0.4), right_shoulder=(0.58, 0.4),
                     left_hip=(0.425, 0.65), right_hip=(0.575, 0.65),
                     left_knee=(0.425, 0.78), left_ankle=(0.425, 0.9))
        self.assertFalse(faults.evaluate("knee_valgus", self.ctx(clean), params))
        caved = kp33(left_shoulder=(0.42, 0.4), right_shoulder=(0.58, 0.4),
                     left_hip=(0.425, 0.65), right_hip=(0.575, 0.65),
                     left_knee=(0.47, 0.78), left_ankle=(0.425, 0.9))
        self.assertTrue(faults.evaluate("knee_valgus", self.ctx(caved), params))

    def test_knee_valgus_ignores_forward_travel(self):
        """Forward knee travel lives on z; it must not read as a lateral cave."""
        params = {"side": "left", "ratio": 0.85, "min_hip_width_ratio": 0.15}
        forward = kp33(left_shoulder=(0.42, 0.4), right_shoulder=(0.58, 0.4),
                       left_hip=(0.425, 0.65, 0.0), right_hip=(0.575, 0.65, 0.0),
                       left_knee=(0.425, 0.78, 0.18), left_ankle=(0.425, 0.9, 0.0))
        self.assertFalse(faults.evaluate("knee_valgus", self.ctx(forward), params))


class TestFlagHysteresis(unittest.TestCase):
    def test_sustain_required(self):
        acc = flag_hysteresis.FlagAccumulator(2)
        acc.observe("f", True, True, sustain_frames=2)
        self.assertEqual(acc.resolve(["f"])[0], [])
        acc.observe("f", True, True, sustain_frames=2)
        self.assertEqual(acc.resolve(["f"])[0], ["f"])

    def test_run_resets_on_a_clean_frame(self):
        acc = flag_hysteresis.FlagAccumulator(2)
        acc.observe("f", True, True, 2)
        acc.observe("f", False, True, 2)
        acc.observe("f", True, True, 2)
        self.assertEqual(acc.resolve(["f"])[0], [])

    def test_unjudgeable_is_not_clean(self):
        acc = flag_hysteresis.FlagAccumulator(2)
        acc.observe("f", False, False, 2)
        fired, unknown = acc.resolve(["f"])
        self.assertEqual(fired, [])
        self.assertEqual(unknown, ["f"], "no evidence must report as unknown, not as absent")

    def test_fired_fault_is_not_also_unknown(self):
        acc = flag_hysteresis.FlagAccumulator(5)
        acc.observe("f", True, True, 1)
        fired, unknown = acc.resolve(["f"])
        self.assertEqual(fired, ["f"])
        self.assertEqual(unknown, [])

    def test_severity_normalisation(self):
        self.assertEqual(flag_hysteresis.normalize_severity("medium"), "med")
        self.assertEqual(flag_hysteresis.normalize_severity("HIGH"), "high")
        with self.assertRaises(ValueError):
            flag_hysteresis.normalize_severity("critical")

    def test_worst_first(self):
        contract = {"a": {"severity": "low"}, "b": {"severity": "high"}, "c": {"severity": "med"}}
        self.assertEqual(flag_hysteresis.worst_first(["a", "b", "c"], contract), ["b", "c", "a"])


class TestRunDetector(unittest.TestCase):
    def setUp(self):
        self.lib = gate_config.load_exercise_library()

    def test_unknown_exercise_raises(self):
        with self.assertRaises(DetectorError):
            run_detector([], "moon_walk", self.lib)

    def test_non_vision_exercise_refused(self):
        with self.assertRaises(DetectorError) as cm:
            run_detector([], "deadlift", self.lib)
        self.assertIn("not vision-live", str(cm.exception))

    def test_empty_input_is_zero_reps_not_an_error(self):
        result = run_detector([], "squat", self.lib)
        self.assertEqual(result.rep_count, 0)
        self.assertIsNone(result.coaching_cue)

    def test_result_serialises(self):
        d = run_detector([], "squat", self.lib).to_dict()
        for key in ("exercise_id", "rep_count", "reps", "flags", "subject_lock_ok", "phase"):
            self.assertIn(key, d)


if __name__ == "__main__":
    unittest.main()
