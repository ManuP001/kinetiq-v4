"""Pick the one person being coached and stay locked to them.

The golden set carries a bystander clip, so this has to survive a second body
entering frame. Strategy: choose the dominant subject on the first judgeable
frame (largest box, tie-broken toward frame centre), then follow that identity by
track_id, falling back to box overlap when a track_id churns.
"""

from __future__ import annotations

from typing import Any

from . import geometry


class SubjectTracker:
    def __init__(self, min_box_area: float) -> None:
        self.min_box_area = min_box_area
        self.track_id: int | None = None
        self.last_box: list[float] | None = None
        self.frames_total = 0
        self.frames_locked = 0

    # -- selection ---------------------------------------------------------

    def _score(self, person: dict[str, Any]) -> float:
        box = person.get("box")
        if not box:
            return 0.0
        area = geometry.box_area(box)
        cx, cy = geometry.box_center(box)
        centrality = 1.0 - min(1.0, (abs(cx - 0.5) + abs(cy - 0.5)))
        return area * (1.0 + centrality)

    def _pick_initial(self, people: list[dict[str, Any]]) -> dict[str, Any] | None:
        candidates = [p for p in people if geometry.box_area(p.get("box")) >= self.min_box_area]
        pool = candidates or people
        if not pool:
            return None
        return max(pool, key=self._score)

    # -- per-frame ---------------------------------------------------------

    def select(self, people: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Return the locked subject for this frame, or None if nobody is present."""
        if not people:
            self.frames_total += 1
            return None

        self.frames_total += 1

        if self.track_id is None:
            chosen = self._pick_initial(people)
            if chosen is None:
                return None
            self.track_id = chosen.get("track_id")
            self.last_box = chosen.get("box")
            self.frames_locked += 1
            return chosen

        for person in people:
            if person.get("track_id") == self.track_id:
                self.last_box = person.get("box") or self.last_box
                self.frames_locked += 1
                return person

        # track_id vanished -- re-acquire by overlap, never by "biggest box now",
        # which is how a bystander steals the lock.
        if self.last_box:
            best, best_iou = None, 0.0
            for person in people:
                box = person.get("box")
                if not box:
                    continue
                iou = geometry.box_iou(self.last_box, box)
                if iou > best_iou:
                    best, best_iou = person, iou
            if best is not None and best_iou >= 0.3:
                self.track_id = best.get("track_id")
                self.last_box = best.get("box")
                self.frames_locked += 1
                return best

        return None

    # -- reporting ---------------------------------------------------------

    @property
    def ratio(self) -> float:
        if self.frames_total == 0:
            return 1.0
        return self.frames_locked / self.frames_total

    def ok(self, floor: float) -> bool:
        return self.ratio >= floor
