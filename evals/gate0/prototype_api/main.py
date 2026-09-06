"""Detector API -- the live consumer of run_detector.

Privacy invariant (root CLAUDE.md): this service accepts KEYPOINTS ONLY. It has
no pose runtime and no image decoder, so it could not consume a video frame if
one were sent. That is the invariant enforced by architecture rather than policy.

One-detector-two-consumers: rep counting, flags and cues all come from
run_detector. Nothing in this file re-implements or second-guesses detection.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# Import as if from evals/gate0 -- gate_config puts backend/ on sys.path.
_GATE0 = Path(__file__).resolve().parents[1]
if str(_GATE0) not in sys.path:
    sys.path.insert(0, str(_GATE0))

import gate_config  # noqa: E402
from detector.adapter import DetectorError, run_detector  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from golden_loader import GoldenSetError, validate_frame_schema  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

# Loaded once at import. If exercises/ is missing this RAISES and the service
# fails to start -- deliberately. A service that boots with an empty library
# answers /health with 200 and 500s every real request, and the health check
# would call it healthy (see docs/DEPLOY_RUNBOOK.md).
LIBRARY = gate_config.load_exercise_library()
SUPPORTED = gate_config.vision_live_exercises(LIBRARY)

app = FastAPI(
    title="Kinetiq detector API",
    version="0.1.0",
    description="Scores keypoint frames. Never receives pixels.",
)

_origins_raw = os.environ.get("PROTOTYPE_API_CORS_ORIGINS", "*").strip()
ALLOWED_ORIGINS = ["*"] if _origins_raw == "*" else [
    o.strip().rstrip("/") for o in _origins_raw.split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Session buffer (in memory, dies with the process -- no persistence anywhere)
# ---------------------------------------------------------------------------

_SESSIONS: dict[str, list[dict[str, Any]]] = {}


def _append(session_id: str, frames: list[dict[str, Any]], reset: bool) -> list[dict[str, Any]]:
    if reset or session_id not in _SESSIONS:
        _SESSIONS[session_id] = []
    buffer = _SESSIONS[session_id]
    buffer.extend(frames)
    cap = gate_config.PROTOTYPE_SESSION_MAX_FRAMES
    if len(buffer) > cap:
        del buffer[: len(buffer) - cap]
    return buffer


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AssessRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    exercise_id: str
    frames: list[dict[str, Any]]
    reset: bool = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "supported_exercises": SUPPORTED,
        "contracts_loaded": len(LIBRARY),
        "pose_runtime": None,
        "accepts": "keypoints only",
    }


@app.post("/prototype/assess")
def assess(req: AssessRequest) -> dict[str, Any]:
    if req.exercise_id not in SUPPORTED:
        raise HTTPException(
            status_code=422,
            detail=(f"exercise_id {req.exercise_id!r} is not vision-live. "
                    f"Supported: {SUPPORTED}"),
        )

    for i, frame in enumerate(req.frames):
        try:
            validate_frame_schema(frame, f"frames[{i}]")
        except GoldenSetError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    buffer = _append(req.session_id, req.frames, req.reset)

    try:
        result = run_detector(buffer, req.exercise_id, LIBRARY)
    except DetectorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload = result.to_dict()
    payload["frames_buffered"] = len(buffer)
    return payload


@app.post("/prototype/reset")
def reset(session_id: str) -> dict[str, Any]:
    _SESSIONS.pop(session_id, None)
    return {"status": "ok", "session_id": session_id}
