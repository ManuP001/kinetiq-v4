"""Load and validate the frozen golden set.

evals/CLAUDE.md pins the frame contract:
    {t_ms, pose_model, people:[{track_id, kp:[[x,y,z,vis]...]}]}
validate_frame_schema is the gatekeeper -- a new eval case must satisfy it.

A clip is one JSON file in golden/:
    {clip_id, exercise_id, view, clip_type, pt_verified, frames:[...],
     ground_truth:{rep_count, reps:[{index, faults:[...]}]}}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gate_config import POSE_MODEL_CANDIDATES

VALID_VIEWS = ("side", "front", "diagonal")
VALID_CLIP_TYPES = ("normal", "phantom_bench", "phantom_empty", "bystander")


class GoldenSetError(ValueError):
    pass


def validate_frame_schema(frame: Any, where: str = "frame") -> None:
    if not isinstance(frame, dict):
        raise GoldenSetError(f"{where}: must be an object, got {type(frame).__name__}")
    for key in ("t_ms", "pose_model", "people"):
        if key not in frame:
            raise GoldenSetError(f"{where}: missing required key {key!r}")
    if not isinstance(frame["t_ms"], int):
        raise GoldenSetError(f"{where}: t_ms must be an int (milliseconds)")
    if frame["pose_model"] not in POSE_MODEL_CANDIDATES:
        raise GoldenSetError(
            f"{where}: pose_model {frame['pose_model']!r} not in {list(POSE_MODEL_CANDIDATES)}"
        )
    people = frame["people"]
    if not isinstance(people, list):
        raise GoldenSetError(f"{where}: people must be a list")
    for i, person in enumerate(people):
        loc = f"{where}.people[{i}]"
        if not isinstance(person, dict):
            raise GoldenSetError(f"{loc}: must be an object")
        if "track_id" not in person:
            raise GoldenSetError(f"{loc}: missing 'track_id'")
        if not isinstance(person["track_id"], int):
            raise GoldenSetError(f"{loc}: track_id must be an int")
        kp = person.get("kp")
        if not isinstance(kp, list) or not kp:
            raise GoldenSetError(f"{loc}: 'kp' must be a non-empty list")
        for j, point in enumerate(kp):
            if not isinstance(point, list) or len(point) != 4:
                raise GoldenSetError(f"{loc}.kp[{j}]: must be [x, y, z, visibility]")
            if not all(isinstance(v, (int, float)) for v in point):
                raise GoldenSetError(f"{loc}.kp[{j}]: all four values must be numeric")
        box = person.get("box")
        if box is not None and (not isinstance(box, list) or len(box) != 4):
            raise GoldenSetError(f"{loc}: 'box' must be [x, y, w, h] when present")


def validate_clip(clip: dict[str, Any], where: str) -> None:
    for key in ("clip_id", "exercise_id", "view", "clip_type", "pt_verified",
                "frames", "ground_truth"):
        if key not in clip:
            raise GoldenSetError(f"{where}: missing required key {key!r}")
    if clip["view"] not in VALID_VIEWS:
        raise GoldenSetError(f"{where}: view {clip['view']!r} not in {list(VALID_VIEWS)}")
    if clip["clip_type"] not in VALID_CLIP_TYPES:
        raise GoldenSetError(
            f"{where}: clip_type {clip['clip_type']!r} not in {list(VALID_CLIP_TYPES)}"
        )
    if not isinstance(clip["pt_verified"], bool):
        raise GoldenSetError(f"{where}: pt_verified must be a bool")
    if not isinstance(clip["frames"], list):
        raise GoldenSetError(f"{where}: frames must be a list")
    for i, frame in enumerate(clip["frames"]):
        validate_frame_schema(frame, f"{where}.frames[{i}]")

    gt = clip["ground_truth"]
    if not isinstance(gt, dict) or "rep_count" not in gt:
        raise GoldenSetError(f"{where}.ground_truth: needs 'rep_count'")
    for i, rep in enumerate(gt.get("reps") or []):
        if "index" not in rep:
            raise GoldenSetError(f"{where}.ground_truth.reps[{i}]: missing 'index'")
        if not isinstance(rep.get("faults", []), list):
            raise GoldenSetError(f"{where}.ground_truth.reps[{i}]: 'faults' must be a list")


def load_clip(path: Path) -> dict[str, Any]:
    try:
        clip = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GoldenSetError(f"{Path(path).name}: invalid JSON: {exc}") from exc
    validate_clip(clip, Path(path).name)
    return clip


def load_golden_set(directory: Path, allow_unverified: bool = False) -> list[dict[str, Any]]:
    directory = Path(directory)
    if not directory.is_dir():
        raise GoldenSetError(f"golden set directory not found: {directory}")

    clips: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        clip = load_clip(path)
        if clip["clip_id"] in seen:
            raise GoldenSetError(f"duplicate clip_id {clip['clip_id']!r}")
        seen.add(clip["clip_id"])

        # Ground truth for form faults is a human PT judgement (evals/CLAUDE.md).
        # Unverified faults are indistinguishable from 'not yet reviewed', so they
        # must not silently become a P/R number.
        if not clip["pt_verified"] and not allow_unverified:
            raise GoldenSetError(
                f"{path.name}: pt_verified is false. Blank faults could mean 'clean set, "
                "trainer confirmed' or 'trainer hasn't reviewed it yet', and only pt_verified "
                "tells those apart.\n"
                "  -> Have a PT review the labels, then set pt_verified: true.\n"
                "  -> Or pass --allow-unverified for a preview read (never a real result)."
            )
        clips.append(clip)

    if not clips:
        raise GoldenSetError(f"no golden clips found in {directory}")
    return clips
