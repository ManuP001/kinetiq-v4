# Kinetiq v4

An AI virtual physical trainer: your phone camera counts reps and flags exercise form, entirely
on-device. This is the **self-contained monorepo** — detector, eval harness, exercise contracts,
detector API, and the live camera PWA in one repo, one deploy.

Start with **`CLAUDE.md`** (governance + where everything lives), then `docs/ROADMAP.md` (current
status and the gate in force).

## Run the prototype locally (real webcam)
```powershell
cd evals\gate0\prototype_api
.\run_local.ps1                       # bash twin: ./run_local.sh
```
Opens the API on :8000 and the PWA on :8080. `http://localhost` is a secure context, so the webcam
works with no HTTPS. Then: allow camera → pick Squat/Push-up/Lunge → do a few reps → End set.

## Verify it (no webcam needed)
```bash
python -m unittest discover -s evals/gate0 -p "test_*.py"        # 301 backend tests
python evals/gate0/aggregate.py --golden evals/gate0/golden --mode full   # Stage 0 gate
python evals/gate0/prototype_api/smoke_assess.py                 # live API+detector loop
```

## Deploy
One GitHub repo → Render Blueprint (`render.yaml`): API as a Docker web service + PWA as a static
site. Ordered steps in `docs/DEPLOY_RUNBOOK.md`.

## The one rule to know
Nothing is called "built" unless its files exist and an acceptance check ran green (`CLAUDE.md` →
Architecture Rules). All eval evidence so far is synthetic — real accuracy is unmeasured until the
first real gym session (GATE G-REAL, `docs/ROADMAP.md`).
