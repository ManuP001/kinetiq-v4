#!/usr/bin/env python3
"""
evals/gate0/prototype_api/session_buffer.py

In-memory, per-process, per-session keypoint-frame buffer for the live detector API. NOT a
production session store: single process, no persistence, no eviction beyond the
PROTOTYPE_SESSION_MAX_FRAMES safeguard, an explicit reset, and idle/LRU eviction -- a process
restart loses every session, which is fine for step 1 of the live-vision-prototype build.

Eviction was added after sessions were found to live until the process died: ~20 MB per full
session, never freed, on a 512 MB free-tier instance. Repeated sets drove the service into memory
exhaustion and restarts, which the browser saw only as a CORS-less 502 ("Failed to fetch").

The API recomputes run_detector over the WHOLE accumulated buffer on every call (main.py) --
simple and correct for a prototype-length set, but O(frames-so-far) per request. The max-frames
safeguard here bounds that from growing without limit if a client keeps a session open
indefinitely; it is not a tuned product limit (config.py's PROTOTYPE_SESSION_MAX_FRAMES).
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, List

import gate_config


class SessionBufferFullError(RuntimeError):
    """Raised by append() instead of silently dropping frames -- a dropped frame would make the
    buffer's contents diverge from what the client believes it sent, which is exactly the kind of
    detector/consumer drift this whole prototype exists to avoid. The caller (main.py) turns this
    into a structured 4xx; nothing is appended when this raises."""


class SessionBufferStore:
    """Keyed by session_id. One process-wide lock, not per-session -- simple and correct at
    prototype request volume; a real product session store would need per-session locking (or a
    proper datastore) under real concurrency, out of scope here."""

    def __init__(
        self,
        max_frames: int = gate_config.PROTOTYPE_SESSION_MAX_FRAMES,
        idle_ttl_s: float = gate_config.PROTOTYPE_SESSION_IDLE_TTL_S,
        max_sessions: int = gate_config.PROTOTYPE_MAX_SESSIONS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_frames = max_frames
        self._idle_ttl_s = idle_ttl_s
        self._max_sessions = max_sessions
        self._clock = clock  # injectable so eviction is testable without sleeping
        self._lock = threading.Lock()
        # Insertion order doubles as recency order: every touch moves a session to the end,
        # so the front is always the least-recently-used.
        self._sessions: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
        self._last_seen: Dict[str, float] = {}

    # -- eviction (call with the lock held) ------------------------------------------------

    def _touch(self, session_id: str) -> None:
        self._last_seen[session_id] = self._clock()
        self._sessions.move_to_end(session_id)

    def _drop(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._last_seen.pop(session_id, None)

    def _evict(self, keep: str | None = None) -> None:
        now = self._clock()
        for sid in [s for s, seen in self._last_seen.items()
                    if now - seen > self._idle_ttl_s and s != keep]:
            self._drop(sid)
        while len(self._sessions) > self._max_sessions:
            oldest = next(iter(self._sessions))
            if oldest == keep:  # never evict the session being served right now
                self._sessions.move_to_end(oldest)
                oldest = next(iter(self._sessions))
                if oldest == keep:
                    break
            self._drop(oldest)

    # -- public API ------------------------------------------------------------------------

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def get(self, session_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._sessions[session_id] = []
            self._touch(session_id)
            self._evict(keep=session_id)

    def append(self, session_id: str, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Appends frames (already schema-validated by the caller) to session_id's buffer and
        returns the new full buffer. Raises SessionBufferFullError, appending nothing, if this
        would exceed the max-frames safeguard."""
        with self._lock:
            existing = self._sessions.setdefault(session_id, [])
            self._touch(session_id)
            self._evict(keep=session_id)
            if len(existing) + len(frames) > self._max_frames:
                raise SessionBufferFullError(
                    f"session {session_id!r}: {len(existing)} buffered + {len(frames)} new "
                    f"frame(s) would exceed PROTOTYPE_SESSION_MAX_FRAMES ({self._max_frames}); "
                    f"reset the session or send fewer frames per call"
                )
            existing.extend(frames)
            return list(existing)
