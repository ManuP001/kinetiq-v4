# Kinetiq — clean-room rebuild

An AI virtual physical trainer: counts reps and flags exercise form from a phone camera,
entirely on-device. The pose model runs in the browser; only joint coordinates ever cross
the network.

> **What this repo is.** A clean-room reconstruction generated from the `CLAUDE.md`
> hierarchy of `kinetiq v4` — root + `backend/`, `evals/`, `frontend/`, `skills/` — and
> nothing else. No source file from the original was read or copied. It is a test of
> whether that rules layer is a sufficient specification, and a comparison target. It is
> **not** a drop-in replacement for the eval-validated v4 detector.
>
> See `docs/CLEANROOM_NOTES.md` for what the spec pinned, what it left open, and what
> that means for anyone reading these numbers.

## Quick start

```bash
python -m unittest discover -s evals/gate0 -p "test_*.py"   # 118 tests
python evals/gate0/aggregate.py --golden evals/gate0/golden --mode full
python evals/gate0/prototype_api/smoke_assess.py            # API + real detector
```

Run the whole prototype with a webcam:

```powershell
evals\gate0\prototype_api\run_local.ps1     # bash twin: run_local.sh
```

API on `:8000`, PWA on `:8080`, CORS wired between them. `http://localhost` is a secure
context, so the camera works without HTTPS — which stops being true for a phone.

## Layout

| Path | What lives there |
|---|---|
| `backend/app/core/` | `config.py` — the single source of gate floors and constants; `schemas.py` |
| `evals/gate0/detector/` | The detector. `adapter.run_detector` is the one entry point |
| `evals/gate0/scorers/` | One scorer per gate dimension |
| `evals/gate0/golden/` | Frozen synthetic fixtures + the generator that makes them |
| `evals/gate0/prototype_api/` | FastAPI detector API, Dockerfile, run/check scripts |
| `exercises/` | 14 contracts; squat / push-up / lunge are vision-live |
| `frontend/` | The camera PWA (zero build, vanilla JS + MediaPipe) |

## Non-negotiables

- **Privacy.** Pose runs in-browser. The API has no pose runtime and no image decoder —
  it could not accept a frame if one were sent. Enforced by a test.
- **One detector.** The live API and the offline harness both call `run_detector`.
- **Anti-phantom.** Nothing is called "built" here without a green acceptance check.
- **Real accuracy is unmeasured.** Every number in this repo comes from synthetic
  fixtures. They prove the code behaves as specified. They say nothing about whether it
  works on a human being — that is GATE G-REAL.
