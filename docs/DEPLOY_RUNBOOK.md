# DEPLOY_RUNBOOK.md — Kinetiq v3 live prototype

> How to run the live prototype (Detector API + `kinetiq-demo3` PWA) — locally with a webcam for a fast
> confidence check, and deployed **over HTTPS** for the first real gym session (GATE G-REAL,
> `ROADMAP.md`). This is the strategic checklist; the exact commands live next to the code they run —
> see "Related docs" at the bottom.
> Last updated: 2026-09-04

---

## Start local, then go global

Two ways to run this, in the order worth doing them:

| | Local run | Render deploy |
|---|---|---|
| Reach | this machine only | anywhere (public HTTPS) |
| Setup | one command, no account | Render account + dashboard steps |
| Camera works? | **yes** — `http://localhost` is a secure context | yes — HTTPS |
| Use it for | proving the pipeline works on your own body, today | testers on phones, the real gym session |

Do the local run first. It costs one command and rules out every "is the app itself working"
question before any cloud variable enters the picture.

## Local run (real webcam, no cloud)

```powershell
cd kinetiq-v2\evals\gate0\prototype_api
.\run_local.ps1                      # bash twin: ./run_local.sh
```

Starts `prototype_api` on `localhost:8000` and the PWA on `localhost:8080`, wires CORS between them,
waits for `/health`, prints the URL. Ctrl+C stops both.

**Why this needs no HTTPS:** `http://localhost` is a **secure context** by browser spec, so
`getUserMedia` works; and an HTTP page calling an HTTP API is same-scheme, so there's no mixed-content
block. Both stop being true for a *phone*, which reaches this machine by LAN IP or a public URL —
neither of which is a secure context over plain HTTP. That is exactly why the Render path exists.

Click-by-click session steps and the `effectiveness_report.py` command to score the export are in
`kinetiq-v2/evals/gate0/prototype_api/README.md` §"Running the whole prototype locally (real webcam)".

---

## Why HTTPS (non-negotiable, for anything not on localhost)
Phone camera access **and** cross-origin calls both require HTTPS. A `http://<laptop-LAN-IP>` setup will
not get camera permission on the phone. Both the PWA and the API must be on HTTPS origins.

## Architecture reminder (keeps the deploy cheap)
- The **PWA** runs MediaPipe / BlazePose **in the browser** (on the phone). Pixels never leave the phone.
- The **Detector API** only runs the geometry detector (`run_detector`) over **keypoints** — it needs
  **no pose runtime** (no mediapipe/tensorflow/rtmlib), just the detector's Python deps. So the API host
  can be small.
- Only keypoints cross the wire. No pixels, no server-side storage beyond the in-memory session buffer.

---

## Deploying to Render (the global path)

Two services, two repos, one ordered sequence. **Every dashboard step below is yours** — they need your
Render account; nothing in either repo signs you up or provisions anything.

- **API** — `kinetiq-v2`, Docker web service, from the repo-root `render.yaml`
  (`dockerfilePath: ./evals/gate0/prototype_api/Dockerfile`, `dockerContext: .`,
  `healthCheckPath: /health`, `PROTOTYPE_API_CORS_ORIGINS` declared `sync: false`).
- **PWA** — `kinetiq-demo3`, static site, from its own `render.yaml` (`runtime: static`, no build,
  `staticPublishPath: .`).

### Wiring order (it's chicken-and-egg — follow it in order)

Each side needs the other's URL, so neither can be fully configured first. This order resolves it:

1. **Deploy the API.** In Render: New → Blueprint → connect the `kinetiq-v2` repo → it picks up the
   root `render.yaml`. Leave `PROTOTYPE_API_CORS_ORIGINS` unset for now (it defaults to `*`, which is
   fine for these first few minutes because no PWA is pointed at it yet).
2. **Note the API's URL** — `https://<name>.onrender.com`. Render appends a suffix if the name is
   taken, so copy the real one from the dashboard rather than assuming.
3. **Verify the API before wiring anything to it:**
   ```
   kinetiq-v2/evals/gate0/prototype_api/check_local.sh https://<api>.onrender.com
   ```
   Do **not** substitute a browser hit on `/health` for this — see the warning below.
4. **Bake that URL into the PWA:**
   ```powershell
   cd kinetiq-demo3
   .\set-api-url.ps1 https://<api>.onrender.com
   git commit -am "point PWA at the deployed API" && git push
   ```
5. **Deploy the PWA.** In Render: New → Blueprint → connect the `kinetiq-demo3` repo. Note its URL.
6. **Close the CORS loop:** in the **API** service's dashboard → Environment → set
   `PROTOTYPE_API_CORS_ORIGINS` to the PWA's **exact** origin (scheme + host, no trailing slash, no
   path — e.g. `https://kinetiq-live-prototype.onrender.com`), not `*` → save → **restart the API**.
7. **Verify end-to-end:** open the PWA URL in a browser, confirm it loads and reaches the API (do a
   few reps). If the calls fail, it's almost always step 6's origin string not matching exactly.

> ⚠️ **`/health` returning 200 does not prove the deploy is good.** If the image were built without
> `exercises/`, the service would still boot and answer `/health` with **200 OK** — and 500 on every
> real request — because `load_exercise_library()` globs a missing directory and silently returns
> `{}`. Render's health check would call that service healthy. `check_local.sh` catches it, because
> its second step does a real `/prototype/assess` round-trip. Always use it (step 3).

### Free-tier spin-down (plan for it, or it will bite mid-session)

Render's free plan idles a **web service** after ~15 minutes with no traffic; the next request pays a
**30–60s cold start**. That lands on the *first* request of a session — precisely when a tester is
standing in front of a camera wondering if it's broken — and it compounds with this API's own
recompute-over-the-whole-buffer cost. Pick one:

- **Pay for the instance for the test window** (cheapest in aggravation; downgrade after).
- **Keep it warm**: hit `/health` every ~10 minutes for the duration (a cron/uptime pinger).
- **Brief the testers**: "the first load can take up to a minute, that's the free server waking up."

Render **static sites don't spin down** (CDN-served), so this applies only to the API.

### Before you hand out the URL

- [ ] `check_local.sh` green against the API's Render URL.
- [ ] `PROTOTYPE_API_CORS_ORIGINS` set to the PWA's exact origin, API restarted.
- [ ] PWA loads over HTTPS and completes a session against the deployed API.
- [ ] You've decided how you're handling cold starts.

---

## Alternative: cloudflared tunnel (quick, same-network)

Still supported, and still the fastest thing to stand up — but it points at **your laptop**, so use it
for a session you're physically running, not for testers elsewhere.

```
cd kinetiq-v2/evals/gate0 && python -m prototype_api     # terminal 1
cd kinetiq-v2/evals/gate0/prototype_api && ./tunnel.sh   # terminal 2
```

Prints an `https://*.trycloudflare.com` URL — no signup, and no ngrok-style interstitial page (which
would block the PWA's `fetch()` calls outright). The laptop must stay awake and online for the whole
session, and the URL changes every restart, so you'd re-run `set-api-url.ps1` + redeploy the PWA each
time — which is exactly why Render is the better global path. `cloudflared` must be installed first
(`winget install --id Cloudflare.cloudflared`); that step is yours.

## Smoke test — do this BEFORE the real session (on an actual phone)
1. [ ] Open the PWA URL on the phone over HTTPS; grant camera permission.
2. [ ] Pick **squat**; do ~3 reps.
3. [ ] Confirm live **rep count**, a **coaching cue**, and **phase** render (and the API-lag banner does
       *not* stick / frames aren't dropped).
4. [ ] **Stop → Validate → enter actual reps → Summary → Export** produces a `.zip`.
5. [ ] Back on a machine, run that `.zip` through `effectiveness_report.py` — clean validate + a rep-
       accuracy number. If this passes, the pipeline is gym-ready.

---

## Session-day checklist (GATE G-REAL)
- [ ] Phone charged; tripod or a spot to place it low/on the floor (side/diagonal view — see
      `RECORDING_SHOTLIST.md`).
- [ ] PWA + API up (smoke test green within the last hour).
- [ ] A **trainer/PT** present or lined up to label reps afterward (needed for the form number).
- [ ] A person to **count reps aloud** (ground truth for rep-accuracy).
- [ ] Run the sets from `RECORDING_SHOTLIST.md` (clean + deliberately-sloppy + bench/bystander).
- [ ] Export every session bundle; keep them; **delete any incidental video** (keypoints only).

## After the session
- [ ] PT labels the reps (`GOLDEN_SET_PROTOCOL.md` §7 / the `labeling/` tool).
- [ ] Run `effectiveness_report.py` → the **first real** rep-accuracy + form precision/recall.
- [ ] Read the caveat header (small n, single-user BlazePose, interim cues). This is the GATE G-REAL result.

## Safety / privacy / teardown

**The deployed URL is public and unauthenticated.** There is no auth anywhere in this prototype, by
design (`prototype_api`'s own README says so explicitly). Anyone with the link can POST keypoints to it.
That is acceptable for a prototype because there is nothing behind it to protect — no accounts, no
stored data, no model weights — but it means:

- Keep the URLs **unlisted**: share them directly with the test cohort, don't post them anywhere
  indexable. Treat the URL itself as the only access control, because it is.
- **Suspend the API service** in Render's dashboard when the test round ends. Redeploying later is
  cheap; leaving an open endpoint running for weeks is the thing to avoid.

**What crosses the network, and what doesn't:**

- **Keypoints only. Never pixels.** The pose model runs in the browser; only the extracted landmark
  numbers are sent (the v3 privacy invariant, `CLAUDE.md` §2 — and it's enforced by the architecture,
  not by policy: the API has no pose runtime and could not consume a frame if it were sent one).
- **No server-side persistence** beyond the in-memory session buffer, which dies with the process.
  Nothing is written to disk, no database is attached.
- **New with a hosted deploy: keypoints now transit a third party's servers** (Render's), rather than
  staying on your laptop as they do with a tunnel or the local run. This is still compliant with the
  privacy invariant — keypoints are derived data, not pixels, and they aren't sent to any model — but
  it is a real change in who handles the data, and it's prototype-only. Not a pattern to carry into
  the production `/v2` API without a deliberate decision.
- **Delete any incidental video** from the session (phones record by habit) — keypoints and labels are
  the only artifacts that should survive.

---

## Related docs
- `ROADMAP.md` — GATE G-REAL and the decision tree off the result.
- `GOLDEN_SET_PROTOCOL.md` / `RECORDING_SHOTLIST.md` — what to record + how to label.
- `kinetiq-v2/evals/gate0/prototype_api/README.md` — the API's concrete commands: the local runner
  (`run_local.ps1`) and its click-by-click webcam session, Path R (Render/`Dockerfile`), Path A
  (`tunnel.sh`), `check_local.sh`, and exactly what about the Docker image is and isn't verified.
- `kinetiq-demo3/README.md` — the PWA's concrete deploy steps (`render.yaml`/`netlify.toml`,
  `set-api-url.ps1`/`config.js`, the mixed-content guard, model-load retry behavior).
