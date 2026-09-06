#!/usr/bin/env python3
"""Score a REAL session bundle -- the GATE G-REAL instrument.

The Stage 0 gate scores synthetic fixtures and proves only that the code behaves
as specified. This scores keypoints captured from an actual human, labelled by an
actual trainer, and is the first number that means anything about accuracy.

Bundle layout (a directory or a .zip of one):
    session.json   {session_id, exercise_id, view, captured_at, frames:[...]}
    labels.json    {pt_verified: bool, labeller, rep_count, reps:[{index, faults}]}

Usage:
    python effectiveness_report.py --bundle path/to/session_dir
    python effectiveness_report.py --bundle bundle.zip
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_config  # noqa: E402
from detector.adapter import run_detector  # noqa: E402
from exercise_lib import load_fault_severities  # noqa: E402
from golden_loader import GoldenSetError, validate_frame_schema  # noqa: E402
from scorers import form_pr, rep_match  # noqa: E402

CAVEAT = """\
!! READ THIS BEFORE QUOTING ANY NUMBER BELOW !!
  - Small n. One session is an anecdote with error bars, not an accuracy claim.
  - Single subject, single pose model (BlazePose), single camera placement.
  - Thresholds are still PT-unconfirmed (exercises/*.json status field).
  - Form ground truth is one trainer's judgement, not a consensus label.
This is the GATE G-REAL result. Its purpose is to decide what to fix next, not
to be quoted as "the detector is X% accurate".
"""


class BundleError(ValueError):
    pass


def load_bundle(path: Path):
    if path.is_file() and path.suffix == ".zip":
        tmp = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(path) as zf:
            zf.extractall(tmp)
        inner = [p for p in tmp.iterdir() if p.is_dir()]
        path = inner[0] if len(inner) == 1 and not (tmp / "session.json").exists() else tmp

    if not path.is_dir():
        raise BundleError(f"not a bundle directory or zip: {path}")
    for name in ("session.json", "labels.json"):
        if not (path / name).is_file():
            raise BundleError(f"{path}: missing {name}")

    session = json.loads((path / "session.json").read_text(encoding="utf-8"))
    labels = json.loads((path / "labels.json").read_text(encoding="utf-8"))

    for key in ("exercise_id", "frames"):
        if key not in session:
            raise BundleError(f"session.json: missing {key!r}")
    for i, frame in enumerate(session["frames"]):
        try:
            validate_frame_schema(frame, f"session.frames[{i}]")
        except GoldenSetError as exc:
            raise BundleError(str(exc)) from exc

    if not labels.get("pt_verified"):
        raise BundleError(
            "labels.json says pt_verified is false. Form faults are a human judgement; "
            "blank faults could mean 'clean set, trainer confirmed' or 'not reviewed "
            "yet', and only pt_verified tells those apart. Have the trainer review the "
            "labels and set pt_verified: true. There is no --force here: an unverified "
            "effectiveness report is worse than none, because it gets quoted."
        )
    return session, labels


def report(bundle: Path) -> tuple[str, int]:
    session, labels = load_bundle(bundle)
    library = gate_config.load_exercise_library()
    severities = load_fault_severities()
    exercise_id = session["exercise_id"]

    result = run_detector(session["frames"], exercise_id, library)
    truth_reps = labels.get("reps") or []
    truth_count = labels.get("rep_count", len(truth_reps))

    rows = [{"exercise_id": exercise_id, "clip_id": session.get("session_id", "session"),
             "detected": result.rep_count, "truth": truth_count}]
    acc = rep_match.score(rows)

    truth_by_index = {r["index"]: set(r.get("faults") or []) for r in truth_reps}
    pairs = []
    for rep in result.reps:
        gt = truth_by_index.get(rep.index)
        if gt is None:
            continue
        pairs.append({"exercise_id": exercise_id, "predicted": rep.faults,
                      "truth": sorted(gt), "insufficient": rep.insufficient_evidence})
    fpr = form_pr.score(pairs, severities)

    out = [CAVEAT, "=" * 70,
           f"EFFECTIVENESS REPORT -- {session.get('session_id', bundle.name)}", "=" * 70, "",
           f"exercise      : {exercise_id}",
           f"view          : {session.get('view', 'unspecified')}",
           f"captured      : {session.get('captured_at', 'unknown')}",
           f"labelled by   : {labels.get('labeller', 'unnamed')}",
           f"frames        : {len(session['frames'])}", "",
           "-- Rep count --",
           f"  detected {result.rep_count}, trainer counted {truth_count}",
           f"  accuracy {acc['per_exercise'][exercise_id]['accuracy'] * 100:.1f}%", "",
           "-- Subject lock --",
           f"  held {result.subject_lock_ratio * 100:.1f}% of frames", "",
           "-- Form flags --"]

    if not fpr["rows"]:
        out.append("  no scoreable fault observations (no matched reps, or none judgeable)")
    for row in fpr["rows"]:
        p = "n/a" if row["precision"] is None else f"{row['precision'] * 100:.0f}%"
        r = "n/a" if row["recall"] is None else f"{row['recall'] * 100:.0f}%"
        out.append(f"  {row['fault_id']:<24} sev={row['severity']:<4} "
                   f"tp={row['tp']} fp={row['fp']} fn={row['fn']}  P={p} R={r}")

    if fpr["insufficient_evidence"]:
        out.append("")
        out.append("-- Could not judge (framing/occlusion, NOT 'clean') --")
        for fault_id, n in fpr["insufficient_evidence"].items():
            out.append(f"  {fault_id:<24} {n} rep(s)")

    out += ["", "-- What to do with this --",
            "  Every disagreement above is a candidate permanent eval case",
            "  (docs/EVAL_STRATEGY.md). Add the clip to the golden set before",
            "  changing any threshold -- and changing one is GATE G-REAL work.", ""]
    return "\n".join(out) + "\n", 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score a real session bundle (GATE G-REAL)")
    ap.add_argument("--bundle", required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        text, code = report(args.bundle)
    except (BundleError, GoldenSetError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
