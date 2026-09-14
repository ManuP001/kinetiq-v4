#!/usr/bin/env python3
"""Unit tests for prototype_api/session_buffer.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototype_api.session_buffer import SessionBufferFullError, SessionBufferStore  # noqa: E402


class TestSessionBufferStore(unittest.TestCase):
    def setUp(self):
        self.store = SessionBufferStore(max_frames=5)

    def test_unknown_session_is_an_empty_buffer(self):
        self.assertEqual(self.store.get("nope"), [])

    def test_append_accumulates_across_calls(self):
        self.store.append("s1", [{"t_ms": 0}])
        self.store.append("s1", [{"t_ms": 100}])
        self.assertEqual(self.store.get("s1"), [{"t_ms": 0}, {"t_ms": 100}])

    def test_append_returns_the_full_buffer(self):
        self.store.append("s1", [{"t_ms": 0}])
        result = self.store.append("s1", [{"t_ms": 100}])
        self.assertEqual(result, [{"t_ms": 0}, {"t_ms": 100}])

    def test_reset_clears_the_session(self):
        self.store.append("s1", [{"t_ms": 0}])
        self.store.reset("s1")
        self.assertEqual(self.store.get("s1"), [])

    def test_reset_does_not_affect_other_sessions(self):
        self.store.append("s1", [{"t_ms": 0}])
        self.store.append("s2", [{"t_ms": 0}])
        self.store.reset("s1")
        self.assertEqual(self.store.get("s2"), [{"t_ms": 0}])

    def test_exceeding_max_frames_raises_and_appends_nothing(self):
        self.store.append("s1", [{"t_ms": i} for i in range(4)])
        with self.assertRaises(SessionBufferFullError):
            self.store.append("s1", [{"t_ms": 4}, {"t_ms": 5}])  # 4 + 2 > 5
        self.assertEqual(len(self.store.get("s1")), 4)  # unchanged, nothing partially appended

    def test_exactly_at_max_frames_is_allowed(self):
        result = self.store.append("s1", [{"t_ms": i} for i in range(5)])
        self.assertEqual(len(result), 5)

    def test_get_returns_a_copy_not_the_live_list(self):
        self.store.append("s1", [{"t_ms": 0}])
        snapshot = self.store.get("s1")
        snapshot.append({"t_ms": 999})
        self.assertEqual(len(self.store.get("s1")), 1)


if __name__ == "__main__":
    unittest.main()


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TestSessionEviction(unittest.TestCase):
    """Sessions used to be held until process death (~20 MB each on a 512 MB instance). These
    pin the eviction that stops repeated sets exhausting memory."""

    def setUp(self):
        self.clock = FakeClock()
        self.store = SessionBufferStore(max_frames=100, idle_ttl_s=60, max_sessions=3,
                                        clock=self.clock)

    def test_idle_session_is_evicted_after_ttl(self):
        self.store.append("old", [{"f": 1}])
        self.clock.t += 61
        self.store.append("new", [{"f": 2}])  # any activity triggers eviction
        self.assertEqual(self.store.get("old"), [])
        self.assertEqual(self.store.get("new"), [{"f": 2}])

    def test_active_session_survives_the_ttl(self):
        self.store.append("live", [{"f": 1}])
        for _ in range(5):          # touched every 50s -- never idle for 60s
            self.clock.t += 50
            self.store.append("live", [{"f": 1}])
        self.assertEqual(len(self.store.get("live")), 6)

    def test_session_just_inside_ttl_is_kept(self):
        self.store.append("a", [{"f": 1}])
        self.clock.t += 60
        self.store.append("b", [{"f": 2}])
        self.assertEqual(self.store.get("a"), [{"f": 1}])

    def test_lru_cap_evicts_least_recently_used(self):
        for sid in ("s1", "s2", "s3"):
            self.store.append(sid, [{"f": sid}])
            self.clock.t += 1
        self.store.append("s1", [{"f": "again"}])  # s1 is now most recent; s2 is oldest
        self.clock.t += 1
        self.store.append("s4", [{"f": "s4"}])
        self.assertEqual(len(self.store), 3)
        self.assertEqual(self.store.get("s2"), [], "the least-recently-used session goes first")
        self.assertEqual(len(self.store.get("s1")), 2)

    def test_the_session_being_served_is_never_evicted(self):
        store = SessionBufferStore(max_frames=100, idle_ttl_s=60, max_sessions=1,
                                   clock=self.clock)
        store.append("a", [{"f": 1}])
        store.append("b", [{"f": 2}])
        self.assertEqual(store.get("b"), [{"f": 2}])
        self.assertEqual(len(store), 1)

    def test_reset_counts_as_activity(self):
        self.store.append("x", [{"f": 1}])
        self.clock.t += 50
        self.store.reset("x")
        self.clock.t += 50
        self.store.append("y", [{"f": 2}])   # 100s since append, 50s since reset
        self.store.append("x", [{"f": 3}])
        self.assertEqual(self.store.get("x"), [{"f": 3}])

    def test_memory_stays_bounded_under_many_sets(self):
        """The failure mode itself: many sets in a row must not accumulate."""
        for i in range(200):
            self.store.append(f"set-{i}", [{"f": i}] * 10)
            self.clock.t += 5
        self.assertLessEqual(len(self.store), 3)
