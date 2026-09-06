# DEPLOY_RUNBOOK.md

How to run the prototype locally with a webcam, and how to deploy it over HTTPS. One repo,
one root `render.yaml`, two services.

> **Status:** nothing here has been executed. The Docker image has not been built and no
> service has been deployed. These are instructions, not a record (anti-phantom rule).

---

## Start local, then go global

| | Local run | Render deploy |
|---|---|---|
| Reach | this machine only | anywhere (public HTTPS) |
| Setup | one command, no account | Render account + dashboard steps |
| Camera works? | **yes** — `http://localhost` is a secure context | yes — HTTPS |
| Use it for | proving the pipeline on your own body, today | testers on phones, the real session |

Do the local run first. It costs one command and rules out every "is the app itself
working" question before any cloud variable enters the picture.

## Local run

```powershell
evals\gate0\prototype_api\run_local.ps1      # bash twin: ./run_local.sh
```

API on `localhost:8000`, PWA on `localhost:8080`, CORS wired, waits for `/health`.
Ctrl+C stops both.

**Why no HTTPS is needed:** `http://localhost` is a **secure context** by browser spec, so
`getUserMedia` works; and an HTTP page calling an HTTP API is same-scheme, so nothing is
blocked as mixed content. Both stop being true for a *phone*, which reaches this machine by
LAN IP — neither a secure context nor same-origin. That is exactly why the Render path
exists.

---

## Why HTTPS is non-negotiable off localhost
Phone camera access **and** cross-origin calls both require HTTPS. `http://<laptop-LAN-IP>`
will not get camera permission on a phone. Both the PWA and the API must be HTTPS origins.

## Why the deploy stays cheap
The **PWA** runs the pose model in the browser, on the phone. The **API** only runs geometry
over keypoints — no mediapipe, no tensorflow, no GPU. So the API host can be small, and the
image is a slim Python base.

---

## Deploying to Render

**Every dashboard step below is yours** — they need your Render account.

### Wiring order (chicken-and-egg — follow it in order)

1. **Deploy the API.** Render → **New → Blueprint** → connect the repo → it picks up the
   root `render.yaml` and offers both services. Deploy **`kinetiq-v4-api` only** for now.
   Leave `PROTOTYPE_API_CORS_ORIGINS` unset (defaults to `*`, fine for these few minutes
   since no PWA points at it yet).

2. **Copy the API's real URL** from the dashboard — Render appends a suffix if the name is
   taken, so don't assume `kinetiq-v4-api`.

3. **Verify the API before wiring anything to it:**
   ```bash
   ./evals/gate0/prototype_api/check_local.sh https://<api>.onrender.com
   ```
   > ⚠️ **`/health` returning 200 does not prove the deploy is good.** If the image were
   > built without `exercises/`, the service would still boot and answer `/health` with
   > **200 OK** while 500-ing every real request — and Render's health check would call it
   > healthy. `check_local.sh` catches it because step 2 does a real `/prototype/assess`
   > round-trip. (This build makes the failure loud too: `load_exercise_library()` raises
   > rather than returning `{}`, so a bad image fails to start at all. Run the check
   > anyway — belt and braces.)

4. **Bake the API URL into the PWA:**
   ```powershell
   cd frontend
   .\set-api-url.ps1 https://<api>.onrender.com
   cd ..
   git commit -am "point PWA at the deployed API"
   git push
   ```

5. **Deploy the PWA.** Back in the Blueprint, deploy **`kinetiq-v4-pwa`** (static site,
   serves `frontend/`, no build step). Note its URL.

6. **Close the CORS loop.** API service → **Environment** → set
   `PROTOTYPE_API_CORS_ORIGINS` to the PWA's **exact** origin — scheme + host, **no
   trailing slash, no path, not `*`** — then Save.

7. **Restart the API.** The env var does not take effect until you do.

8. **Verify end-to-end.** Re-run `check_local.sh` against the API, then open the PWA and do
   a few reps. If the browser fails but `check_local.sh` passes, it is step 6's origin
   string not matching exactly — `curl` isn't subject to CORS, so only the browser catches it.

### Free-tier spin-down
Render idles a free **web service** after ~15 minutes; the next request pays a 30–60s cold
start. That lands on the *first* request of a session — with a tester standing in front of a
camera wondering if it's broken. Pick one: pay for the instance for the test window, ping
`/health` every ~10 minutes, or brief the testers. Static sites are CDN-served and do **not**
spin down, so this applies only to the API.

### Before you hand out the URL
- [ ] `check_local.sh` green against the API's Render URL.
- [ ] `PROTOTYPE_API_CORS_ORIGINS` set to the PWA's exact origin, API restarted.
- [ ] PWA loads over HTTPS and completes a session against the deployed API.
- [ ] You've decided how you're handling cold starts.

---

## Phone smoke test — before any real session
1. [ ] Open the PWA on the phone over HTTPS; grant camera permission.
2. [ ] Pick **squat**; do ~3 reps.
3. [ ] Confirm the rep count, a cue, and the phase render live, and that the
       API-unreachable banner does not stick.
4. [ ] Stop → check the summary counts what you actually did.

## Safety, privacy, teardown

**The deployed URL is public and unauthenticated.** There is no auth in this prototype, by
design. Anyone with the link can POST keypoints. That's acceptable because there is nothing
behind it to protect — no accounts, no stored data, no weights — but it means:

- Keep URLs **unlisted**. The URL is the only access control, because it is.
- **Suspend the API service** when the test round ends.

**What crosses the network:**
- **Keypoints only, never pixels.** The pose model runs in the browser; only landmark
  numbers are sent. Enforced by architecture — the API has no pose runtime and no image
  decoder, and a test asserts it.
- **No server-side persistence** beyond an in-memory session buffer that dies with the
  process.
- **A hosted deploy means keypoints transit a third party's servers** (Render's) rather than
  staying on your laptop. Still within the privacy invariant — keypoints are derived data,
  not pixels — but it is a real change in who handles the data, and it is prototype-only.
- **Delete any incidental video** from a session. Keypoints and labels are the only
  artifacts that should survive.
