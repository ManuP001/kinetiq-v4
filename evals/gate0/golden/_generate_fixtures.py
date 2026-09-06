#!/usr/bin/env python3
"""Regenerate the synthetic golden fixtures.

WHAT THESE ARE: geometric constructions. A skeleton is placed analytically so a
named joint angle hits a chosen value, then sampled over time. They exercise the
scorers and pin regressions.

WHAT THESE ARE NOT: recordings of a human being. They prove nothing about
real-world accuracy (root CLAUDE.md, Known Issues). Real clips land per
docs/GOLDEN_SET_PROTOCOL.md and replace these as ground truth.

Ground truth here is AUTHORED from the construction parameters -- "this clip was
built with a 42 deg torso lean, so the label is torso_lean" -- never copied from
detector output. Reading labels back off the detector would make the gate vacuous.

Run:  python _generate_fixtures.py
"""

from __future__ import annotations

import json
import math
import pathlib

OUT = pathlib.Path(__file__).resolve().parent
N_LM = 33
VIS = 0.93

# BlazePose indices we actually place; the rest get a plausible filler.
IDX = {
    "nose": 0, "left_shoulder": 11, "right_shoulder": 12, "left_elbow": 13,
    "right_elbow": 14, "left_wrist": 15, "right_wrist": 16, "left_hip": 23,
    "right_hip": 24, "left_knee": 25, "right_knee": 26, "left_ankle": 27,
    "right_ankle": 28, "left_heel": 29, "right_heel": 30,
    "left_foot_index": 31, "right_foot_index": 32,
}


def blank():
    return [[0.5, 0.5, 0.0, 0.2] for _ in range(N_LM)]


def put(kp, name, x, y, z=0.0, vis=VIS):
    kp[IDX[name]] = [round(x, 5), round(y, 5), round(z, 5), vis]


def rot(vx, vy, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return vx * c - vy * s, vx * s + vy * c


def unit(vx, vy):
    n = math.hypot(vx, vy)
    return (vx / n, vy / n) if n else (0.0, 0.0)


def box_for(kp):
    pts = [p for p in kp if p[3] >= 0.5]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    pad = 0.02
    return [round(max(0.0, x0 - pad), 4), round(max(0.0, y0 - pad), 4),
            round((x1 - x0) + 2 * pad, 4), round((y1 - y0) + 2 * pad, 4)]


# ---------------------------------------------------------------------------
# Leg-driven exercises (squat, lunge)
# ---------------------------------------------------------------------------

def leg_skeleton(knee_deg, trunk_deg, view, valgus=0.0, ankle=(0.50, 0.90)):
    """Place a body so hip-knee-ankle == knee_deg and the torso leans trunk_deg.

    phi (shin lean) + psi (thigh lean) == 180 - knee_deg, which makes the interior
    angle exactly knee_deg. Same convention as geometry.joint_angle.
    """
    L_SHIN, L_THIGH, L_TRUNK = 0.20, 0.22, 0.26
    total = 180.0 - knee_deg
    phi = 0.30 * total
    psi = total - phi

    ax, ay = ankle
    kx = ax + L_SHIN * math.sin(math.radians(phi))
    ky = ay - L_SHIN * math.cos(math.radians(phi))
    hx = kx - L_THIGH * math.sin(math.radians(psi))
    hy = ky - L_THIGH * math.cos(math.radians(psi))
    sx = hx + L_TRUNK * math.sin(math.radians(trunk_deg))
    sy = hy - L_TRUNK * math.cos(math.radians(trunk_deg))

    # The movement happens in the SAGITTAL plane. Which camera axis that lands on
    # depends entirely on where the phone is:
    #   side view  -> the sagittal axis is across the image, so it lands on x.
    #   front view -> the sagittal axis points AT the camera, so it lands on z,
    #                 and x carries only the body's left/right width.
    # Getting this wrong is what makes a front-view knee's forward travel look
    # like it caved sideways.
    sag = {"ankle": 0.0, "knee": kx - ax, "hip": hx - ax, "shoulder": sx - ax}
    ys = {"ankle": ay, "knee": ky, "hip": hy, "shoulder": sy}
    half = 0.012 if view == "side" else 0.075
    base = 0.50

    kp = blank()
    for side, sign in (("left", -1.0), ("right", 1.0)):
        # Caving drives the knee toward the midline; the midline is at `base`, so
        # the direction flips with which side of it this leg is on.
        cave = (valgus if side == "left" else 0.0) * (-sign)
        for joint in ("ankle", "knee", "hip", "shoulder"):
            lateral = base + sign * half * (1.4 if joint == "shoulder" else 1.0)
            if joint == "knee":
                lateral += cave
            if view == "side":
                put(kp, side + "_" + joint, lateral + sag[joint], ys[joint], 0.0)
            else:
                put(kp, side + "_" + joint, lateral, ys[joint], sag[joint])
        hx_l = base + sign * half
        put(kp, side + "_heel", hx_l - 0.02 + (sag["ankle"] if view == "side" else 0.0),
            ay + 0.01, 0.0 if view == "side" else -0.02)
        put(kp, side + "_foot_index",
            hx_l + (0.06 if view == "side" else 0.0), ay + 0.01,
            0.0 if view == "side" else 0.06)
        put(kp, side + "_elbow", base + sign * half * 1.8,
            sy + 0.12, 0.0 if view == "side" else sag["shoulder"])
        put(kp, side + "_wrist", base + sign * half * 2.0,
            sy + 0.24, 0.0 if view == "side" else sag["shoulder"])
    put(kp, "nose", base, sy - 0.08, 0.0 if view == "side" else sag["shoulder"])
    return kp


# ---------------------------------------------------------------------------
# Push-up
# ---------------------------------------------------------------------------

def pushup_skeleton(elbow_deg, flare_deg, sag, view="side"):
    """Place a push-up so shoulder-elbow-wrist == elbow_deg and the angle at the
    shoulder between elbow and hip == flare_deg. Depth lowers the shoulder."""
    L_UPPER, L_FORE, L_TRUNK = 0.13, 0.13, 0.53
    depth = (170.0 - elbow_deg) / 80.0
    sx, sy = 0.32, 0.52 + 0.10 * depth
    axx, ayy = sx + L_TRUNK, sy + 0.06

    hx = sx + 0.55 * (axx - sx)
    hy = sy + 0.55 * (ayy - sy) + sag

    # Elbow at exactly flare_deg off the shoulder->hip direction.
    ux, uy = unit(hx - sx, hy - sy)
    ex_d, ey_d = rot(ux, uy, -flare_deg)
    ex, ey = sx + L_UPPER * ex_d, sy + L_UPPER * ey_d

    # Wrist so the interior angle at the elbow is exactly elbow_deg.
    bx, by = unit(sx - ex, sy - ey)
    wx_d, wy_d = rot(bx, by, -elbow_deg)
    wx, wy = ex + L_FORE * wx_d, ey + L_FORE * wy_d

    half = 0.012 if view == "side" else 0.070
    kp = blank()
    for side, sign in (("left", -1.0), ("right", 1.0)):
        put(kp, side + "_shoulder", sx + sign * half, sy)
        put(kp, side + "_elbow", ex + sign * half, ey)
        put(kp, side + "_wrist", wx + sign * half, wy)
        put(kp, side + "_hip", hx + sign * half, hy)
        put(kp, side + "_ankle", axx + sign * half, ayy)
        put(kp, side + "_knee", hx + 0.55 * (axx - hx) + sign * half,
            hy + 0.55 * (ayy - hy))
        put(kp, side + "_heel", axx + sign * half + 0.02, ayy)
        put(kp, side + "_foot_index", axx + sign * half + 0.05, ayy + 0.02)
    put(kp, "nose", sx - 0.06, sy - 0.03)
    return kp


# ---------------------------------------------------------------------------
# Motion
# ---------------------------------------------------------------------------

def cycle(n_reps, frames_per_rep=20):
    """Yield (rep_index, depth 0..1) over a smooth down-up cycle.

    20 frames at dt=100ms is a 2.0s rep, which is what an unhurried squat
    actually takes. This is not cosmetic: the contract's min_rep_ms rejects
    anything faster as dither, so a fixture with an unrealistically quick rep
    gets correctly thrown out and the clip silently scores zero.
    """
    for rep in range(1, n_reps + 1):
        for i in range(frames_per_rep):
            yield rep, (1.0 - math.cos(2.0 * math.pi * i / frames_per_rep)) / 2.0


def frames_from(builder, n_reps, dt=100, extra=None):
    out = []
    t = 0
    for _rep, depth in cycle(n_reps):
        kp = builder(depth)
        people = [{"track_id": 0, "kp": kp, "box": box_for(kp)}]
        if extra:
            people.extend(extra(t))
        out.append({"t_ms": t, "pose_model": "blazepose_33", "people": people})
        t += dt
    # Settle back at the top so the final rep's ascent completes.
    for _ in range(6):
        kp = builder(0.0)
        out.append({"t_ms": t, "pose_model": "blazepose_33",
                    "people": [{"track_id": 0, "kp": kp, "box": box_for(kp)}]})
        t += dt
    return out


def clip(clip_id, exercise_id, view, clip_type, frames, rep_faults, notes):
    return {
        "clip_id": clip_id, "exercise_id": exercise_id, "view": view,
        "clip_type": clip_type, "pt_verified": True,
        "synthetic": True, "notes": notes,
        "ground_truth": {
            "rep_count": len(rep_faults),
            "reps": [{"index": i + 1, "faults": f} for i, f in enumerate(rep_faults)],
        },
        "frames": frames,
    }


def build():
    clips = []

    def squat(top, bottom, trunk_top, trunk_bottom, view, valgus=0.0):
        return lambda d: leg_skeleton(top - d * (top - bottom),
                                      trunk_top + d * (trunk_bottom - trunk_top),
                                      view, valgus=valgus * d)

    clips.append(clip(
        "squat_clean_side_001", "squat", "side", "normal",
        frames_from(squat(172, 84, 12, 45, "side"), 3), [[], [], []],
        "Full-depth squat, upright enough. Valgus is unjudgeable from the side."))

    clips.append(clip(
        "squat_shallow_side_002", "squat", "side", "normal",
        frames_from(squat(172, 118, 12, 40, "side"), 3),
        [["shallow_depth"], ["shallow_depth"], ["shallow_depth"]],
        "Bottom angle 118 deg: counts as a rep (<130) but never reaches depth (>100)."))

    clips.append(clip(
        "squat_clean_front_003", "squat", "front", "normal",
        frames_from(squat(172, 84, 12, 45, "front"), 3), [[], [], []],
        "Same movement, hips separated: valgus is judgeable and absent."))

    clips.append(clip(
        "squat_kneecave_front_004", "squat", "front", "normal",
        frames_from(squat(172, 84, 12, 45, "front", valgus=0.045), 3),
        [["knee_cave_left"], ["knee_cave_left"], ["knee_cave_left"]],
        "Left knee driven medially, growing with depth."))

    clips.append(clip(
        "squat_lean_side_005", "squat", "side", "normal",
        frames_from(squat(172, 88, 15, 68, "side"), 3),
        [["excessive_forward_lean"], ["excessive_forward_lean"],
         ["excessive_forward_lean"]],
        "Torso reaches 68 deg off vertical, past the 55 deg threshold."))

    def pu(bottom, flare, sag):
        return lambda d: pushup_skeleton(170 - d * (170 - bottom), flare, sag * d)

    clips.append(clip(
        "pushup_clean_side_006", "pushup", "side", "normal",
        frames_from(pu(88, 45, 0.0), 4), [[], [], [], []],
        "Full ROM, elbows tucked, body line straight."))

    clips.append(clip(
        "pushup_hipsag_side_007", "pushup", "side", "normal",
        frames_from(pu(88, 45, 0.060), 4),
        [["hip_sag"], ["hip_sag"], ["hip_sag"], ["hip_sag"]],
        "Hips drop through the rep, breaking the shoulder-hip-ankle line."))

    clips.append(clip(
        "pushup_flare_side_008", "pushup", "side", "normal",
        frames_from(pu(88, 88, 0.0), 4),
        [["elbow_flare"], ["elbow_flare"], ["elbow_flare"], ["elbow_flare"]],
        "Elbows held 88 deg from the torso, past the 75 deg threshold."))

    def lunge(bottom, trunk_bottom):
        return lambda d: leg_skeleton(172 - d * (172 - bottom),
                                      8 + d * (trunk_bottom - 8), "side")

    clips.append(clip(
        "lunge_clean_side_009", "lunge", "side", "normal",
        frames_from(lunge(96, 12), 2), [[], []],
        "Clean lunge, upright torso."))

    clips.append(clip(
        "lunge_lean_side_010", "lunge", "side", "normal",
        frames_from(lunge(96, 42), 2), [["torso_lean"], ["torso_lean"]],
        "Torso pitches to 42 deg, past the 25 deg threshold."))

    clips.append(clip(
        "phantom_empty_011", "squat", "side", "phantom_empty",
        [{"t_ms": i * 100, "pose_model": "blazepose_33", "people": []}
         for i in range(40)],
        [], "No person in frame. Must not manufacture a rep."))

    static = leg_skeleton(172, 10, "side")
    clips.append(clip(
        "phantom_bench_012", "squat", "side", "phantom_bench",
        [{"t_ms": i * 100, "pose_model": "blazepose_33",
          "people": [{"track_id": 0, "kp": static, "box": box_for(static)}]}
         for i in range(40)],
        [], "A motionless shape. No descent, so no rep."))

    def bystander(t):
        if t < 500:
            return []
        kp = leg_skeleton(168, 6, "side", ankle=(0.86, 0.88))
        return [{"track_id": 7, "kp": kp, "box": box_for(kp)}]

    clips.append(clip(
        "pushup_bystander_013", "pushup", "side", "bystander",
        frames_from(pu(88, 45, 0.0), 4, extra=bystander), [[], [], [], []],
        "A second person enters at 500ms. The lock must stay on track_id 0."))

    return clips


def main():
    for old in OUT.glob("*.json"):
        old.unlink()
    clips = build()
    for c in clips:
        (OUT / (c["clip_id"] + ".json")).write_text(
            json.dumps(c, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum(len(c["frames"]) for c in clips)
    reps = sum(c["ground_truth"]["rep_count"] for c in clips)
    print("wrote %d clips, %d frames, %d ground-truth reps" % (len(clips), total, reps))


if __name__ == "__main__":
    main()
