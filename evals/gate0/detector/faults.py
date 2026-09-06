"""Fault checks, driven entirely by the exercise contract.

Root CLAUDE.md: "thresholds live in exercises/*.json ... imported, never restated
as inline literals". So a check here is a pure function of (landmarks, params) and
every number arrives in `params` from the contract. Adding a threshold to this file
would be the bug that rule describes.

A check returns a tri-state:
    True  -> fault present this frame
    False -> checked, absent
    None  -> not judgeable this frame (occluded landmark); NOT the same as False
"""

from __future__ import annotations

from typing import Any, Callable

from . import geometry, keypoint_map

CheckResult = bool | None
Check = Callable[..., CheckResult]

_REGISTRY: dict[str, Check] = {}

# A check's SCOPE decides when it is allowed to answer.
#   "frame" -- judged on each frame; sustain_frames smooths it.
#   "rep"   -- judged ONCE, when the rep closes.
# Depth/ROM checks must be rep-scope. Asking "did this rep reach depth?" on the
# way DOWN answers "not yet" for every descent frame, which latches the fault on
# a perfectly good rep. Scope is a property of the question, not a tunable.
_SCOPES: dict[str, str] = {}


class UnknownCheckError(ValueError):
    pass


def register(name: str, scope: str = "frame") -> Callable[[Check], Check]:
    if scope not in ("frame", "rep"):
        raise ValueError(f"unknown scope {scope!r}")

    def wrap(fn: Check) -> Check:
        _REGISTRY[name] = fn
        _SCOPES[name] = scope
        return fn
    return wrap


def scope_of(name: str) -> str:
    get_check(name)
    return _SCOPES[name]


def get_check(name: str) -> Check:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownCheckError(
            f"contract references check {name!r}, which this detector does not implement. "
            f"Known checks: {sorted(_REGISTRY)}. Refusing to silently skip a fault check."
        ) from None


def _pt(kp, model, name, min_vis):
    p = keypoint_map.get(kp, model, name)
    return p if geometry.visible(p, min_vis) else None


def _pair(kp, model, base, min_vis):
    """Return the better-visible of left_/right_ for a landmark base name."""
    left = _pt(kp, model, f"left_{base}", min_vis)
    right = _pt(kp, model, f"right_{base}", min_vis)
    if left and right:
        return left if left[3] >= right[3] else right
    return left or right


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

@register("min_angle_above", scope="rep")
def min_angle_above(ctx: dict[str, Any], params: dict[str, Any]) -> CheckResult:
    """Depth/ROM: the rep signal never got below `deg`.

    Evaluated against the running minimum for the current rep, so it reads as
    'this rep stayed too shallow' rather than 'this instant is shallow'.
    """
    lowest = ctx.get("rep_min_angle")
    if lowest is None:
        return None
    return lowest > float(params["deg"])


@register("trunk_lean_above")
def trunk_lean_above(ctx: dict[str, Any], params: dict[str, Any]) -> CheckResult:
    """Torso leans more than `deg` off vertical."""
    kp, model, min_vis = ctx["kp"], ctx["pose_model"], ctx["min_visibility"]
    shoulder = _pair(kp, model, "shoulder", min_vis)
    hip = _pair(kp, model, "hip", min_vis)
    if not shoulder or not hip:
        return None
    lean = geometry.angle_from_vertical(shoulder, hip)
    if lean is None:
        return None
    return lean > float(params["deg"])


@register("body_line_break")
def body_line_break(ctx: dict[str, Any], params: dict[str, Any]) -> CheckResult:
    """Push-up hip sag: shoulder-hip-ankle should be near straight (180 deg)."""
    kp, model, min_vis = ctx["kp"], ctx["pose_model"], ctx["min_visibility"]
    shoulder = _pair(kp, model, "shoulder", min_vis)
    hip = _pair(kp, model, "hip", min_vis)
    ankle = _pair(kp, model, "ankle", min_vis)
    if not shoulder or not hip or not ankle:
        return None
    angle = geometry.collinearity_angle(shoulder, hip, ankle)
    if angle is None:
        return None
    return angle < float(params["deg"])


@register("elbow_abduction_above")
def elbow_abduction_above(ctx: dict[str, Any], params: dict[str, Any]) -> CheckResult:
    """Elbow flare: angle at the shoulder between torso and upper arm."""
    kp, model, min_vis = ctx["kp"], ctx["pose_model"], ctx["min_visibility"]
    shoulder = _pair(kp, model, "shoulder", min_vis)
    elbow = _pair(kp, model, "elbow", min_vis)
    hip = _pair(kp, model, "hip", min_vis)
    if not shoulder or not elbow or not hip:
        return None
    angle = geometry.joint_angle(elbow, shoulder, hip)
    if angle is None:
        return None
    return angle > float(params["deg"])


@register("knee_valgus")
def knee_valgus(ctx: dict[str, Any], params: dict[str, Any]) -> CheckResult:
    """Knee cave: the knee tracks inside the hip-ankle line.

    Scale-free by construction -- the deviation is expressed as a fraction of hip
    width, so it does not change meaning when the subject stands closer to the phone.
    """
    kp, model, min_vis = ctx["kp"], ctx["pose_model"], ctx["min_visibility"]
    side = params.get("side", "auto")
    if side == "auto":
        side = ctx.get("active_side") or "left"

    hip = _pt(kp, model, f"{side}_hip", min_vis)
    knee = _pt(kp, model, f"{side}_knee", min_vis)
    ankle = _pt(kp, model, f"{side}_ankle", min_vis)
    left_hip = _pt(kp, model, "left_hip", min_vis)
    right_hip = _pt(kp, model, "right_hip", min_vis)
    if not hip or not knee or not ankle or not left_hip or not right_hip:
        return None

    hip_width = geometry.distance(left_hip, right_hip)
    if hip_width <= 0:
        return None

    # Frontal-plane guard. Valgus is only meaningful when we can actually see
    # across the hips. From a side view the hips project onto nearly the same
    # point, and the knee's forward travel -- normal squat mechanics -- would read
    # as a huge lateral deviation. Refuse to answer instead of inventing a fault.
    shoulder = _pair(kp, model, "shoulder", min_vis)
    if shoulder is not None:
        torso = geometry.distance(shoulder, hip)
        min_ratio = params.get("min_hip_width_ratio")
        if min_ratio is not None and torso > 0 and (hip_width / torso) < float(min_ratio):
            return None

    # Frontal-plane deviation: how far the knee sits from the foot ACROSS the
    # body, as a fraction of hip width (so it is scale-free -- standing closer to
    # the phone must not change the verdict). Compared against the ankle rather
    # than an interpolated hip-ankle line, because the knee's forward travel is
    # normal squat mechanics and lives on the depth axis, not this one.
    deviation = knee[0] - ankle[0]

    # Medial = toward the body's midline, so the sign flips per leg: for a hip
    # right of the midline, caving means a SMALLER x (negative deviation).
    midline = (left_hip[0] + right_hip[0]) / 2.0
    inward = -deviation if hip[0] > midline else deviation

    return (inward / hip_width) > (1.0 - float(params["ratio"]))


def evaluate(check_name: str, ctx: dict[str, Any], params: dict[str, Any]) -> CheckResult:
    return get_check(check_name)(ctx, params)


def known_checks() -> list[str]:
    return sorted(_REGISTRY)
