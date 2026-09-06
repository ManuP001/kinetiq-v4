"""Pure geometry helpers. No thresholds live here -- callers pass them in."""

from __future__ import annotations

import math

Point = list[float]


def visible(p: Point | None, min_vis: float) -> bool:
    return p is not None and len(p) >= 4 and p[3] >= min_vis


def midpoint(a: Point, b: Point) -> Point:
    return [(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0,
            (a[2] + b[2]) / 2.0 if len(a) > 2 and len(b) > 2 else 0.0,
            min(a[3], b[3]) if len(a) > 3 and len(b) > 3 else 1.0]


def distance(a: Point, b: Point) -> float:
    """Image-plane (x/y) distance. Deliberately 2D: used for frontal-plane
    measures like hip width, where depth must NOT contribute."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _z(p: Point) -> float:
    return p[2] if len(p) > 2 else 0.0


def joint_angle(a: Point, b: Point, c: Point) -> float | None:
    """Interior angle ABC in degrees (b is the vertex). None if degenerate.

    Uses all three axes. BlazePose emits a per-landmark z and the frame schema
    carries it, so ignoring it would make every joint angle view-dependent: a
    squat seen head-on has almost no x/y bend at the knee, and a 2D angle would
    read it as a straight leg and count no reps at all.
    """
    v1 = (a[0] - b[0], a[1] - b[1], _z(a) - _z(b))
    v2 = (c[0] - b[0], c[1] - b[1], _z(c) - _z(b))
    n1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2 + v1[2] ** 2)
    n2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2 + v2[2] ** 2)
    if n1 == 0.0 or n2 == 0.0:
        return None
    cos = (v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def angle_from_vertical(top: Point, bottom: Point) -> float | None:
    """Degrees the segment bottom->top leans off vertical. 0 = upright.

    Image coordinates: y grows downward, so 'up' is negative y.
    """
    dx = top[0] - bottom[0]
    dy = top[1] - bottom[1]
    dz = _z(top) - _z(bottom)
    if dx == 0.0 and dy == 0.0 and dz == 0.0:
        return None
    # Lean is the tilt off the vertical axis, wherever in the horizontal plane
    # it points -- so combine x and z before comparing against y.
    return math.degrees(math.atan2(math.hypot(dx, dz), abs(dy)))


def collinearity_angle(a: Point, b: Point, c: Point) -> float | None:
    """180 deg = perfectly straight A-B-C. Used for the push-up body line."""
    return joint_angle(a, b, c)


def ema(prev: float | None, value: float, alpha: float) -> float:
    """Exponential moving average; seeds itself on the first sample."""
    if prev is None:
        return value
    return alpha * value + (1.0 - alpha) * prev


def box_area(box: list[float] | None) -> float:
    if not box or len(box) < 4:
        return 0.0
    return max(0.0, box[2]) * max(0.0, box[3])


def box_center(box: list[float]) -> tuple[float, float]:
    return box[0] + box[2] / 2.0, box[1] + box[3] / 2.0


def box_iou(a: list[float], b: list[float]) -> float:
    ax0, ay0, aw, ah = a[0], a[1], a[2], a[3]
    bx0, by0, bw, bh = b[0], b[1], b[2], b[3]
    ax1, ay1, bx1, by1 = ax0 + aw, ay0 + ah, bx0 + bw, by0 + bh
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    union = max(0.0, aw * ah) + max(0.0, bw * bh) - inter
    return inter / union if union > 0 else 0.0
