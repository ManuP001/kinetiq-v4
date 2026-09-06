#!/usr/bin/env python3
"""Stage 0 regression gate.

evals/CLAUDE.md: `python aggregate.py --golden golden --mode full` must print
`Stage 0 gate: PASS`. Exits non-zero when any dimension fails -- that non-zero is
what makes the CI gate real, so never swallow it in a pipeline without pipefail.

  fast  -- rep accuracy + phantom (per-push in CI)
  full  -- every dimension (nightly + pre-merge)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_config  # noqa: E402  (installs sys.path before the rest)
from cues import validate_library_cues  # noqa: E402
from detector.adapter import DetectorError, run_detector  # noqa: E402
from exercise_lib import load_fault_severities  # noqa: E402
from golden_loader import load_golden_set  # noqa: E402
from scorers import form_pr, phantom, rep_match, subject_lock, view  # noqa: E402

BAR = "=" * 70


def _fmt_pct(value):
    return "n/a" if value is None else f"{value * 100:.1f}%"


def run(golden_dir: Path, mode: str, allow_unverified: bool) -> tuple[str, int]:
    library = gate_config.load_exercise_library()
    severities = load_fault_severities()
    clips = load_golden_set(golden_dir, allow_unverified=allow_unverified)

    results, rep_pairs = [], []
    for clip in clips:
        exercise_id = clip["exercise_id"]
        try:
            detected = run_detector(clip["frames"], exercise_id, library)
        except DetectorError as exc:
            return f"error: {clip['clip_id']}: {exc}\n", 2

        results.append({
            "clip_id": clip["clip_id"], "exercise_id": exercise_id,
            "view": clip["view"], "clip_type": clip["clip_type"],
            "detected": detected.rep_count,
            "truth": clip["ground_truth"]["rep_count"],
            "subject_lock_ratio": detected.subject_lock_ratio,
        })

        truth_by_index = {r["index"]: set(r.get("faults") or [])
                          for r in clip["ground_truth"].get("reps") or []}
        for rep in detected.reps:
            gt = truth_by_index.get(rep.index)
            if gt is None:
                continue  # unmatched rep: rep_match already penalises the count
            for fault_id in gt:
                if fault_id not in severities.get(exercise_id, {}):
                    return (f"error: {clip['clip_id']}: fault {fault_id!r} on gt rep "
                            f"{rep.index} is not defined in {exercise_id!r}'s contract\n"), 2
            rep_pairs.append({
                "exercise_id": exercise_id, "predicted": rep.faults,
                "truth": sorted(gt), "insufficient": rep.insufficient_evidence,
            })

    cues_checked = validate_library_cues(library)

    out = [BAR, f"STAGE 0 GOLDEN SET REPORT  (mode: {mode})", BAR, ""]
    dimensions = []

    acc = rep_match.score(results)
    dimensions.append(acc)
    out.append(f"-- Rep-count accuracy (target {acc['target']:.0%}) --")
    for exercise_id, row in acc["per_exercise"].items():
        out.append(f"  {exercise_id:<18} {_fmt_pct(row['accuracy']):>6}  "
                   f"({row['clips']} clip(s))  [{'PASS' if row['passed'] else 'FAIL'}]")
    out.append("")

    ph = phantom.score(results)
    dimensions.append(ph)
    out.append("-- No-phantom-reps (clip types: phantom_bench, phantom_empty) --")
    out.append(f"  checked {ph['checked']} clip(s)  [{'PASS' if ph['passed'] else 'FAIL'}]")
    for failure in ph["failures"]:
        out.append(f"    {failure['clip_id']}: counted {failure['detected']} rep(s), expected 0")
    out.append("")

    out.append("-- Coaching-cue word cap --")
    out.append(f"  checked {cues_checked} cue(s)  [PASS]")
    out.append("")

    if mode == "full":
        fpr = form_pr.score(rep_pairs, severities)
        dimensions.append(fpr)
        out.append("-- Form precision/recall (per flag, severity-gated) --")
        current = None
        for row in fpr["rows"]:
            if row["exercise_id"] != current:
                current = row["exercise_id"]
                out.append(f"  {current}:")
            out.append(
                f"    {row['fault_id']:<22} sev={row['severity']:<4} "
                f"tp={row['tp']} fp={row['fp']} fn={row['fn']}  "
                f"precision={_fmt_pct(row['precision']):>6} (floor {row['precision_floor']:.0%})  "
                f"recall={_fmt_pct(row['recall']):>6} (floor {row['recall_floor']:.0%})  "
                f"[{'PASS' if row['passed'] else 'FAIL'}]"
            )
        if not fpr["rows"]:
            out.append("    (no scoreable fault observations)")
        out.append("")

        if fpr["insufficient_evidence"]:
            out.append("-- Insufficient evidence (too few judgeable frames) --")
            for fault_id, n in fpr["insufficient_evidence"].items():
                out.append(f"    {fault_id:<22} {n} rep(s)")
            out.append("")

        lock = subject_lock.score(results)
        dimensions.append(lock)
        out.append(f"-- Subject-lock (floor {lock['floor']:.0%}) --")
        for clip in lock["clips"]:
            out.append(f"    {clip['clip_id']:<28} {_fmt_pct(clip['ratio'])}")
        if lock["mean"] is not None:
            out.append(f"  mean {_fmt_pct(lock['mean'])}  [{'PASS' if lock['passed'] else 'FAIL'}]")
        else:
            out.append("  no bystander clips  [PASS]")
        out.append("")

        vw = view.score(results)
        dimensions.append(vw)
        out.append(f"-- View robustness (max gap {vw['max_gap']:.0%}) --")
        for exercise_id, row in vw["per_exercise"].items():
            views = ", ".join(f"{v}={_fmt_pct(s)}" for v, s in row["views"].items())
            gap = "n/a" if row["gap"] is None else f"{row['gap'] * 100:.1f}%"
            out.append(f"  {exercise_id:<18} {views}  gap={gap}  "
                       f"[{'PASS' if row['passed'] else 'FAIL'}]")
        out.append("")

    passed = all(d["passed"] for d in dimensions)
    out.append(f"Stage 0 gate: {'PASS' if passed else 'FAIL'}")
    return "\n".join(out) + "\n", 0 if passed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage 0 regression gate")
    parser.add_argument("--golden", default="golden", help="golden set directory")
    parser.add_argument("--mode", choices=("fast", "full"), default="full")
    parser.add_argument("--allow-unverified", action="store_true",
                        help="score PT-unverified clips (preview only, never a real result)")
    args = parser.parse_args(argv)

    report, code = run(Path(args.golden), args.mode, args.allow_unverified)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
