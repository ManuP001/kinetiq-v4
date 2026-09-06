"""Rep counting as a two-state machine over one contract-declared angle signal.

The hysteresis is the whole point: a single threshold on a noisy angle counts a
rep every time the signal dithers across it, which is precisely the phantom-rep
failure the golden set has a clip for. Entering 'down' and leaving it use two
different thresholds, and a rep must also last min_rep_ms.

Every number comes from the contract (`rep_signal`) -- none is inlined here.
"""

from __future__ import annotations

from typing import Any

from . import geometry, keypoint_map

_SIDES = ("left", "right")


class RepCounter:
    def __init__(self, signal: dict[str, Any], min_visibility: float) -> None:
        self.signal = signal
        self.min_visibility = min_visibility
        self.down_enter = float(signal["down_enter_deg"])
        self.up_exit = float(signal["up_exit_deg"])
        self.min_rep_ms = int(signal.get("min_rep_ms", 0))
        self.joints: list[str] = list(signal["joints"])
        self.side_mode: str = signal.get("side", "auto")

        self.state = "up"
        self.phase = "idle"
        self.rep_boundaries: list[tuple[int, int]] = []
        self._descent_start_ms: int | None = None
        self._smoothed: float | None = None
        self._locked_side: str | None = None

        if self.down_enter >= self.up_exit:
            raise ValueError(
                f"rep_signal is not hysteretic: down_enter_deg ({self.down_enter}) must be "
                f"below up_exit_deg ({self.up_exit}); equal values would count dither as reps"
            )

    # -- signal ------------------------------------------------------------

    def _angle_for_side(self, kp, pose_model: str, side: str) -> float | None:
        pts = []
        for joint in self.joints:
            point = keypoint_map.get(kp, pose_model, f"{side}_{joint}")
            if not geometry.visible(point, self.min_visibility):
                return None
            pts.append(point)
        if len(pts) != 3:
            return None
        return geometry.joint_angle(pts[0], pts[1], pts[2])

    def measure(self, kp, pose_model: str) -> float | None:
        """The rep signal for this frame, in degrees."""
        if self.side_mode in _SIDES:
            return self._angle_for_side(kp, pose_model, self.side_mode)

        angles = {s: self._angle_for_side(kp, pose_model, s) for s in _SIDES}
        present = {s: a for s, a in angles.items() if a is not None}
        if not present:
            return None
        if self._locked_side and self._locked_side in present:
            return present[self._locked_side]
        # 'auto': follow whichever side is working hardest (smallest angle), then
        # stay on it so a mid-set side switch cannot fake a rep.
        side = min(present, key=lambda s: present[s])
        self._locked_side = side
        return present[side]

    # -- state machine -----------------------------------------------------

    def update(self, kp, pose_model: str, t_ms: int) -> None:
        angle = self.measure(kp, pose_model)
        if angle is None:
            self.phase = "unknown"
            return

        self._smoothed = geometry.ema(self._smoothed, angle, alpha=0.6)
        value = self._smoothed

        if self.state == "up":
            if value <= self.down_enter:
                self.state = "down"
                self.phase = "down"
                self._descent_start_ms = t_ms
            else:
                self.phase = "up" if value >= self.up_exit else "descending"
        else:  # down
            if value >= self.up_exit:
                start = self._descent_start_ms if self._descent_start_ms is not None else t_ms
                if t_ms - start >= self.min_rep_ms:
                    self.rep_boundaries.append((start, t_ms))
                self.state = "up"
                self.phase = "up"
                self._descent_start_ms = None
            else:
                self.phase = "bottom" if value <= self.down_enter else "ascending"

    @property
    def count(self) -> int:
        return len(self.rep_boundaries)
