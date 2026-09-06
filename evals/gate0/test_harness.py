"""Harness tests: config, contracts, cues, golden loader, scorers, aggregate."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_config  # noqa: E402
import golden_loader  # noqa: E402
from cues import CueTooLongError, validate_cue, validate_library_cues, word_count  # noqa: E402
from exercise_lib import known_faults, load_fault_metadata, load_fault_severities  # noqa: E402
from scorers import form_pr, phantom, rep_match, subject_lock, view  # noqa: E402

GATE0 = Path(__file__).resolve().parent
GOLDEN = GATE0 / "golden"


class TestConfigIsSingleSourceOfTruth(unittest.TestCase):
    def test_paths_resolve(self):
        self.assertTrue(gate_config.EXERCISE_LIBRARY_DIR.is_dir())
        self.assertEqual(gate_config.EXERCISE_LIBRARY_DIR.name, "exercises")

    def test_backend_config_is_where_every_import_expects_it(self):
        """backend/CLAUDE.md calls this path load-bearing. Moving it breaks all imports."""
        self.assertTrue((gate_config.REPO_ROOT / "backend" / "app" / "core" / "config.py").is_file())

    def test_floors_are_ordered_by_severity(self):
        """A high-severity fault is a safety call: a false positive must cost more."""
        self.assertGreater(gate_config.FORM_PRECISION_FLOOR_HIGH,
                           gate_config.FORM_PRECISION_FLOOR_MED)
        self.assertGreater(gate_config.FORM_PRECISION_FLOOR_MED,
                           gate_config.FORM_PRECISION_FLOOR_LOW)

    def test_floors_are_probabilities(self):
        for name in dir(gate_config):
            if "FLOOR" in name or name == "GATE0_TARGET_ACCURACY":
                v = getattr(gate_config, name)
                if isinstance(v, float):
                    self.assertGreaterEqual(v, 0.0, name)
                    self.assertLessEqual(v, 1.0, name)

    def test_default_pose_model_is_a_candidate(self):
        self.assertIn(gate_config.DEFAULT_POSE_MODEL, gate_config.POSE_MODEL_CANDIDATES)

    def test_missing_library_raises_rather_than_returning_empty(self):
        """An empty library is the silent failure DEPLOY_RUNBOOK warns about."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(gate_config.ExerciseLibraryError):
                gate_config.load_exercise_library(Path(tmp) / "nope")

    def test_empty_dir_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(gate_config.ExerciseLibraryError):
                gate_config.load_exercise_library(Path(tmp))


class TestExerciseContracts(unittest.TestCase):
    def setUp(self):
        self.lib = gate_config.load_exercise_library()

    def test_fourteen_contracts(self):
        self.assertEqual(len(self.lib), 14)

    def test_three_are_vision_live(self):
        self.assertEqual(gate_config.vision_live_exercises(self.lib),
                         ["lunge", "pushup", "squat"])

    def test_filename_matches_exercise_id(self):
        for path in gate_config.EXERCISE_LIBRARY_DIR.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(path.stem, data["exercise_id"])

    def test_thresholds_are_marked_unconfirmed(self):
        """CLAUDE.md: never invent a threshold. These were derived, not validated,
        so every contract must say so rather than look settled."""
        for eid, c in self.lib.items():
            self.assertEqual(c.get("status"), "needs_pt_confirmation", eid)
            self.assertIn("threshold_provenance", c, eid)

    def test_non_live_exercises_declare_no_detection_config(self):
        for eid, c in self.lib.items():
            if not c.get("vision_support"):
                self.assertIsNone(c.get("rep_signal"), eid)
                self.assertEqual(c.get("faults"), {}, eid)

    def test_rep_signal_is_hysteretic(self):
        for eid in gate_config.vision_live_exercises(self.lib):
            sig = self.lib[eid]["rep_signal"]
            self.assertLess(sig["down_enter_deg"], sig["up_exit_deg"], eid)

    def test_rep_gate_sits_above_the_depth_fault(self):
        """If the depth threshold were at or above the rep gate, a too-shallow rep
        would never be counted and the fault could never fire."""
        for eid in gate_config.vision_live_exercises(self.lib):
            c = self.lib[eid]
            enter = c["rep_signal"]["down_enter_deg"]
            for fid, spec in c["faults"].items():
                if spec["check"] == "min_angle_above":
                    self.assertLess(spec["params"]["deg"], enter, f"{eid}.{fid}")

    def test_every_check_is_implemented(self):
        from detector import faults as fault_checks
        for eid, c in self.lib.items():
            for fid, spec in (c.get("faults") or {}).items():
                fault_checks.get_check(spec["check"])

    def test_every_fault_has_severity_and_cue(self):
        for eid, c in self.lib.items():
            for fid, spec in (c.get("faults") or {}).items():
                self.assertIn(spec.get("severity"), ("high", "med", "low"), f"{eid}.{fid}")
                self.assertTrue(spec.get("cue"), f"{eid}.{fid}")

    def test_required_landmarks_exist_in_the_model(self):
        from detector import keypoint_map
        for eid in gate_config.vision_live_exercises(self.lib):
            for name in self.lib[eid]["validity"]["required_landmarks"]:
                keypoint_map.index_of("blazepose_33", name)

    def test_severities_and_metadata_agree(self):
        sev, meta = load_fault_severities(), load_fault_metadata()
        self.assertEqual(sorted(sev), sorted(meta))
        for eid in sev:
            self.assertEqual(sorted(sev[eid]), sorted(meta[eid]))

    def test_known_faults(self):
        self.assertIn("shallow_depth", known_faults("squat"))
        self.assertEqual(known_faults("plank"), [])


class TestCues(unittest.TestCase):
    def test_word_count(self):
        self.assertEqual(word_count("  Sit   lower "), 2)

    def test_cap_enforced(self):
        with self.assertRaises(CueTooLongError):
            validate_cue("f", "one two three four five six seven", max_words=6)

    def test_empty_cue_rejected(self):
        with self.assertRaises(CueTooLongError):
            validate_cue("f", "   ")

    def test_every_shipped_cue_is_within_cap(self):
        n = validate_library_cues(gate_config.load_exercise_library())
        self.assertGreater(n, 0)


class TestGoldenLoader(unittest.TestCase):
    def good_frame(self):
        return {"t_ms": 0, "pose_model": "blazepose_33",
                "people": [{"track_id": 0, "kp": [[0.1, 0.2, 0.0, 0.9]]}]}

    def test_accepts_a_good_frame(self):
        golden_loader.validate_frame_schema(self.good_frame())

    def test_rejects_missing_key(self):
        f = self.good_frame(); del f["pose_model"]
        with self.assertRaises(golden_loader.GoldenSetError):
            golden_loader.validate_frame_schema(f)

    def test_rejects_unknown_pose_model(self):
        f = self.good_frame(); f["pose_model"] = "guesswork_9"
        with self.assertRaises(golden_loader.GoldenSetError):
            golden_loader.validate_frame_schema(f)

    def test_rejects_non_int_t_ms(self):
        f = self.good_frame(); f["t_ms"] = "0"
        with self.assertRaises(golden_loader.GoldenSetError):
            golden_loader.validate_frame_schema(f)

    def test_rejects_wrong_keypoint_arity(self):
        f = self.good_frame(); f["people"][0]["kp"] = [[0.1, 0.2, 0.3]]
        with self.assertRaises(golden_loader.GoldenSetError):
            golden_loader.validate_frame_schema(f)

    def test_rejects_missing_track_id(self):
        f = self.good_frame(); del f["people"][0]["track_id"]
        with self.assertRaises(golden_loader.GoldenSetError):
            golden_loader.validate_frame_schema(f)

    def test_rejects_bad_box(self):
        f = self.good_frame(); f["people"][0]["box"] = [0, 0, 1]
        with self.assertRaises(golden_loader.GoldenSetError):
            golden_loader.validate_frame_schema(f)

    def test_loads_the_real_golden_set(self):
        clips = golden_loader.load_golden_set(GOLDEN)
        self.assertGreaterEqual(len(clips), 10)

    def test_every_clip_is_pt_verified(self):
        for clip in golden_loader.load_golden_set(GOLDEN):
            self.assertTrue(clip["pt_verified"], clip["clip_id"])

    def test_unverified_clip_is_refused_by_default(self):
        clip = json.loads((GOLDEN / "squat_clean_side_001.json").read_text(encoding="utf-8"))
        clip["pt_verified"] = False
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "c.json").write_text(json.dumps(clip), encoding="utf-8")
            with self.assertRaises(golden_loader.GoldenSetError):
                golden_loader.load_golden_set(Path(tmp))
            self.assertEqual(len(golden_loader.load_golden_set(Path(tmp), allow_unverified=True)), 1)

    def test_ground_truth_faults_are_declared_in_the_contract(self):
        lib = gate_config.load_exercise_library()
        for clip in golden_loader.load_golden_set(GOLDEN):
            declared = set(lib[clip["exercise_id"]].get("faults") or {})
            for rep in clip["ground_truth"].get("reps") or []:
                for fault in rep.get("faults") or []:
                    self.assertIn(fault, declared, f"{clip['clip_id']}: {fault}")

    def test_no_video_in_the_golden_set(self):
        """evals/CLAUDE.md: never commit video."""
        bad = [p.name for p in GOLDEN.iterdir()
               if p.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm",
                                       ".jpg", ".jpeg", ".png", ".heic"}]
        self.assertEqual(bad, [])


class TestScorers(unittest.TestCase):
    def test_exact_match_scores_one(self):
        self.assertEqual(rep_match.clip_accuracy(5, 5), 1.0)

    def test_off_by_one_is_penalised(self):
        self.assertAlmostEqual(rep_match.clip_accuracy(4, 5), 0.8)

    def test_zero_truth_handled(self):
        self.assertEqual(rep_match.clip_accuracy(0, 0), 1.0)
        self.assertEqual(rep_match.clip_accuracy(2, 0), 0.0)

    def test_rep_match_fails_below_target(self):
        rows = [{"exercise_id": "squat", "clip_id": "a", "detected": 1, "truth": 5}]
        self.assertFalse(rep_match.score(rows)["passed"])

    def test_phantom_only_checks_phantom_clips(self):
        rows = [{"clip_id": "n", "clip_type": "normal", "detected": 9},
                {"clip_id": "p", "clip_type": "phantom_empty", "detected": 0}]
        out = phantom.score(rows)
        self.assertEqual(out["checked"], 1)
        self.assertTrue(out["passed"])

    def test_phantom_fails_on_invented_rep(self):
        rows = [{"clip_id": "p", "clip_type": "phantom_bench", "detected": 1}]
        self.assertFalse(phantom.score(rows)["passed"])

    def test_subject_lock_floor(self):
        rows = [{"clip_id": "b", "clip_type": "bystander", "subject_lock_ratio": 0.5}]
        self.assertFalse(subject_lock.score(rows)["passed"])

    def test_view_gap(self):
        rows = [
            {"exercise_id": "squat", "clip_type": "normal", "view": "side", "detected": 5, "truth": 5},
            {"exercise_id": "squat", "clip_type": "normal", "view": "front", "detected": 2, "truth": 5},
        ]
        self.assertFalse(view.score(rows)["passed"])

    def test_form_pr_counts_tp_fp_fn(self):
        sev = {"squat": {"shallow_depth": "med"}}
        pairs = [
            {"exercise_id": "squat", "predicted": ["shallow_depth"], "truth": ["shallow_depth"]},
            {"exercise_id": "squat", "predicted": ["shallow_depth"], "truth": []},
            {"exercise_id": "squat", "predicted": [], "truth": ["shallow_depth"]},
        ]
        row = form_pr.score(pairs, sev)["rows"][0]
        self.assertEqual((row["tp"], row["fp"], row["fn"]), (1, 1, 1))

    def test_form_pr_excludes_unjudgeable_reps(self):
        """An unjudgeable rep must not be scored as a clean one -- that would
        inflate precision exactly where the detector was blindest."""
        sev = {"squat": {"knee_cave_left": "high"}}
        pairs = [{"exercise_id": "squat", "predicted": [], "truth": [],
                  "insufficient": ["knee_cave_left"]}]
        out = form_pr.score(pairs, sev)
        self.assertEqual(out["rows"], [])
        self.assertEqual(out["insufficient_evidence"]["knee_cave_left"], 1)

    def test_high_severity_precision_floor_is_stricter(self):
        pairs = [{"exercise_id": "x", "predicted": ["f"], "truth": ["f"]},
                 {"exercise_id": "x", "predicted": ["f"], "truth": []}]
        self.assertFalse(form_pr.score(pairs, {"x": {"f": "high"}})["passed"])  # 50% < 90%
        self.assertFalse(form_pr.score(pairs, {"x": {"f": "med"}})["passed"])   # 50% < 75%


class TestAggregate(unittest.TestCase):
    def test_full_gate_passes_and_exits_zero(self):
        import aggregate
        report, code = aggregate.run(GOLDEN, "full", False)
        self.assertIn("Stage 0 gate: PASS", report)
        self.assertEqual(code, 0)

    def test_fast_gate_passes(self):
        import aggregate
        report, code = aggregate.run(GOLDEN, "fast", False)
        self.assertIn("Stage 0 gate: PASS", report)
        self.assertEqual(code, 0)

    def test_a_regression_fails_the_gate_nonzero(self):
        """The gate must actually gate: a broken detection has to exit non-zero."""
        import aggregate
        with tempfile.TemporaryDirectory() as tmp:
            src = json.loads((GOLDEN / "squat_clean_side_001.json").read_text(encoding="utf-8"))
            src["ground_truth"]["rep_count"] = 99
            (Path(tmp) / "c.json").write_text(json.dumps(src), encoding="utf-8")
            report, code = aggregate.run(Path(tmp), "fast", False)
        self.assertIn("Stage 0 gate: FAIL", report)
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
