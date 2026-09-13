// app.js — Kinetiq v4 live camera PWA.
//
// Pipeline (privacy invariant: pixels NEVER leave this device):
//   webcam ─▶ MediaPipe PoseLandmarker (in-browser) ─▶ 33 keypoints
//          ─▶ frame {t_ms, pose_model, people:[{track_id, kp:[[x,y,z,vis]×33]}]}
//          ─▶ POST /prototype/assess (only keypoints cross the wire)
//          ─▶ render rep_count / phase / flags / coaching_cue / subject_lock_ok
//
// The frame shape and endpoint are read from the REAL backend
// (evals/gate0/golden_loader.py validate_frame_schema + prototype_api/main.py + schemas.py),
// not assumed — see docs/EVAL_HARNESS_STAGE0_SPEC.md §5.

import {
  PoseLandmarker,
  FilesetResolver,
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs";

const CFG = window.KINETIQ_CONFIG;
const API = CFG.API_BASE_URL.replace(/\/+$/, "");

// ---- DOM ----
const $ = (id) => document.getElementById(id);
const screens = {
  picker: $("screen-picker"),
  live: $("screen-live"),
  summary: $("screen-summary"),
};
const video = $("video");
const overlay = $("overlay");
const octx = overlay.getContext("2d");

// ---- session state ----
let landmarker = null;
let severities = {};
let stream = null;
let running = false;
let exercise = null;
let sessionId = null;
let firstPost = true;
let frameBuffer = []; // frames accumulated since last successful POST
let lastResponse = null;
let lastVideoTs = -1;
let postTimer = null;

// ---- connection resilience -------------------------------------------------
// Render's free tier puts a web service to sleep after ~15 min idle, and the
// next request pays a 30-60s cold start. That lands on the FIRST request of a
// session -- exactly when someone is standing in front of the camera. Without
// this, one failed POST during wake-up dumped the user on a blocking error.
//
// Two defences: wake the server before the set starts, and treat early POST
// failures as "not awake yet" (retry with backoff, keep recording) rather than
// as a dead end. Frames are never dropped -- they re-queue and replay, so the
// rep count catches up once the server answers.
let apiWarm = false;         // has /health answered since page load?
let flushInFlight = false;   // a POST is outstanding -- don't stack another on it
let failStreak = 0;          // consecutive failed flushes
let nextAttemptAt = 0;       // backoff gate, performance.now() ms
const HEALTH_TIMEOUT_MS = 12000;   // one /health probe
const WAKE_TIMEOUT_MS = 90000;     // total budget for waking a sleeping instance
const HARD_FAIL_AFTER = 10;        // give up quietly retrying, ask the user
const BACKOFF_MAX_MS = 8000;

// ---------------------------------------------------------------------------
// screens
function show(name) {
  for (const s of Object.values(screens)) s.classList.remove("active");
  screens[name].classList.add("active");
}
function setState(title, msg, actionLabel, actionFn) {
  $("state-title").textContent = title;
  $("state-msg").textContent = msg || "";
  const btn = $("state-action");
  if (actionLabel) {
    btn.textContent = actionLabel;
    btn.hidden = false;
    btn.onclick = actionFn;
  } else {
    btn.hidden = true;
  }
  $("state-overlay").hidden = false;
}
function clearState() {
  $("state-overlay").hidden = true;
}

// ---------------------------------------------------------------------------
// one-time load of the pose model + the derived severity table
async function loadModel() {
  if (landmarker) return;
  const files = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
  );
  landmarker = await PoseLandmarker.createFromOptions(files, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
      delegate: "GPU",
    },
    runningMode: "VIDEO",
    numPoses: 1, // single subject in-browser; subject-lock is exercised in the offline bake-off
  });
}
async function loadSeverities() {
  try {
    severities = await fetch("severities.json").then((r) => r.json());
  } catch {
    severities = {}; // coloring degrades gracefully to "med" if this is missing
  }
}

// ---------------------------------------------------------------------------
// camera
async function startCamera() {
  stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
    audio: false,
  });
  video.srcObject = stream;
  await video.play();
  overlay.width = video.videoWidth;
  overlay.height = video.videoHeight;
}
function stopCamera() {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
}

// ---------------------------------------------------------------------------
// build a backend-shaped frame from a MediaPipe result
function buildFrame(landmarks, tMs) {
  // MediaPipe normalized landmarks: {x, y, z, visibility}, 33 of them, BlazePose order.
  const kp = landmarks.map((p) => [
    +p.x.toFixed(5),
    +p.y.toFixed(5),
    p.z == null ? null : +p.z.toFixed(5),
    +(p.visibility ?? 0).toFixed(4),
  ]);
  return {
    t_ms: Math.round(tMs),
    pose_model: CFG.POSE_MODEL,
    people: [{ track_id: 0, kp }],
  };
}

// ---------------------------------------------------------------------------
// detection loop
function loop() {
  if (!running) return;
  const now = performance.now();
  if (video.currentTime !== lastVideoTs) {
    lastVideoTs = video.currentTime;
    const result = landmarker.detectForVideo(video, now);
    if (result.landmarks && result.landmarks.length > 0) {
      frameBuffer.push(buildFrame(result.landmarks[0], now));
      drawSkeleton(result.landmarks[0]);
    } else {
      octx.clearRect(0, 0, overlay.width, overlay.height);
    }
  }
  requestAnimationFrame(loop);
}

// ---------------------------------------------------------------------------
// non-blocking connection notice (the set keeps running underneath it)
function banner(msg) {
  const el = $("conn-banner");
  if (!el) return;
  if (msg) {
    el.textContent = msg;
    el.hidden = false;
  } else {
    el.hidden = true;
  }
}

// A cheap GET that tells us whether the instance is awake. Uses AbortController
// because a sleeping Render instance holds the connection open rather than
// refusing it -- without a timeout this would hang instead of retrying.
async function pingHealth(timeoutMs = HEALTH_TIMEOUT_MS) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API}/health`, { signal: ctrl.signal, cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(t);
  }
}

// Poll /health until the instance answers or the budget runs out.
async function wakeApi(onProgress) {
  if (apiWarm) return true;
  const deadline = performance.now() + WAKE_TIMEOUT_MS;
  let attempt = 0;
  while (performance.now() < deadline) {
    attempt++;
    if (onProgress) {
      const secs = Math.round((performance.now() - (deadline - WAKE_TIMEOUT_MS)) / 1000);
      onProgress(
        attempt === 1
          ? "Waking the server — this can take up to a minute on the free plan."
          : `Still waking… ${secs}s. Your reps are being recorded either way.`
      );
    }
    if (await pingHealth()) {
      apiWarm = true;
      return true;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  return false;
}

// ---------------------------------------------------------------------------
// POST buffered frames to the detector API
async function flush() {
  if (!running) return;
  if (frameBuffer.length === 0) return;

  // A cold start can take 30-60s while the post timer keeps firing every 400ms.
  // Without this guard we would stack dozens of concurrent POSTs onto a server
  // that is still booting, and each would carry a different slice of the buffer.
  if (flushInFlight) return;
  if (performance.now() < nextAttemptAt) return;

  const frames = frameBuffer;
  frameBuffer = [];
  flushInFlight = true;
  const body = {
    session_id: sessionId,
    exercise_id: exercise,
    frames,
    reset: firstPost,
  };
  try {
    const res = await fetch(`${API}/prototype/assess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`API ${res.status}: ${txt.slice(0, 140)}`);
    }
    firstPost = false;
    lastResponse = await res.json();
    render(lastResponse);

    // Recovered: drop the retry state and any notice we were showing.
    apiWarm = true;
    failStreak = 0;
    nextAttemptAt = 0;
    banner(null);
    clearState();
  } catch (err) {
    // Re-queue the frames we pulled so nothing is silently lost (the whole
    // project's discipline). They replay on the next successful POST and the
    // rep count catches up.
    frameBuffer = frames.concat(frameBuffer);
    failStreak++;

    if (failStreak < HARD_FAIL_AFTER) {
      // Probably a cold start, not a dead server. Back off and keep recording
      // instead of blocking the user on an error screen.
      const delay = Math.min(1000 * 2 ** (failStreak - 1), BACKOFF_MAX_MS);
      nextAttemptAt = performance.now() + delay;
      banner(
        apiWarm
          ? "Lost the coach — still recording, will catch up."
          : "Waking the server — still recording, your reps will catch up."
      );
    } else {
      // Sustained failure: now it is worth interrupting.
      banner(null);
      setState(
        "Can't reach the trainer",
        String(err.message || err),
        "Retry",
        async () => {
          failStreak = 0;
          nextAttemptAt = 0;
          clearState();
          banner("Reconnecting…");
          const ok = await wakeApi((m) => banner(m));
          banner(ok ? null : "Still no answer — check your connection.");
        }
      );
    }
  } finally {
    flushInFlight = false;
  }
}

// ---------------------------------------------------------------------------
// render a response
function render(r) {
  $("rep-count").textContent = r.rep_count;
  $("phase").textContent = r.phase || "—";

  const lock = $("hud-lock");
  lock.className = "lock-pill " + (r.subject_lock_ok ? "lock-ok" : "lock-lost");
  lock.textContent = r.subject_lock_ok ? "locked on you" : "can't see you";

  const cueEl = $("cue");
  if (r.coaching_cue) {
    cueEl.textContent = r.coaching_cue;
    cueEl.hidden = false;
  } else {
    cueEl.hidden = true;
  }

  const flagsEl = $("flags");
  flagsEl.innerHTML = "";
  for (const f of r.current_flags || []) {
    const sev = (severities[exercise] && severities[exercise][f]) || "med";
    const el = document.createElement("span");
    el.className = "flag " + sev;
    el.textContent = prettyFlag(f);
    flagsEl.appendChild(el);
  }
}
function prettyFlag(f) {
  return f.replace(/_/g, " ");
}

// ---------------------------------------------------------------------------
// skeleton overlay (cosmetic — helps a user frame themselves)
const CONNECTIONS = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [24, 26], [26, 28],
];
function drawSkeleton(lm) {
  octx.clearRect(0, 0, overlay.width, overlay.height);
  octx.lineWidth = 3;
  octx.strokeStyle = "rgba(16,185,129,0.9)";
  octx.fillStyle = "rgba(16,185,129,0.9)";
  for (const [a, b] of CONNECTIONS) {
    if (!lm[a] || !lm[b]) continue;
    octx.beginPath();
    octx.moveTo(lm[a].x * overlay.width, lm[a].y * overlay.height);
    octx.lineTo(lm[b].x * overlay.width, lm[b].y * overlay.height);
    octx.stroke();
  }
  for (const p of lm) {
    octx.beginPath();
    octx.arc(p.x * overlay.width, p.y * overlay.height, 4, 0, Math.PI * 2);
    octx.fill();
  }
}

// ---------------------------------------------------------------------------
// start / stop a set
async function startSet(ex) {
  exercise = ex;
  sessionId = `sess-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  firstPost = true;
  frameBuffer = [];
  lastResponse = null;
  lastVideoTs = -1;
  failStreak = 0;
  nextAttemptAt = 0;
  flushInFlight = false;
  banner(null);
  $("hud-exercise").textContent = ex;
  $("rep-count").textContent = "0";
  $("phase").textContent = "—";
  $("cue").hidden = true;
  $("flags").innerHTML = "";
  show("live");

  try {
    setState("Warming up", "Loading the on-device pose model…");
    await loadModel();
    setState("Camera", "Allow camera access to begin. Video stays on your device.");
    await startCamera();

    // Wake the detector before the first rep rather than discovering it is
    // asleep mid-set. We do NOT block the set on this: if it times out we start
    // anyway, buffer frames, and let flush() keep retrying -- losing the first
    // few reps of a set is worse than showing a notice.
    if (!apiWarm) {
      setState("Waking the coach", "The free server sleeps when idle. First start can take a minute.");
      const awake = await wakeApi((m) => setState("Waking the coach", m));
      clearState();
      if (!awake) banner("Server still waking — your reps are being recorded and will catch up.");
    } else {
      clearState();
    }
  } catch (err) {
    if (err && (err.name === "NotAllowedError" || err.name === "SecurityError")) {
      setState(
        "Camera blocked",
        "Kinetiq needs the camera to see your form. Enable it in your browser settings, then retry.",
        "Retry",
        () => startSet(ex)
      );
    } else {
      setState("Couldn't start", String(err.message || err), "Back", backToPicker);
    }
    return;
  }

  running = true;
  requestAnimationFrame(loop);
  postTimer = setInterval(flush, CFG.POST_INTERVAL_MS);
}

async function stopSet() {
  running = false;
  clearInterval(postTimer);
  postTimer = null;
  await flush(); // final flush so the last reps are counted
  stopCamera();
  octx.clearRect(0, 0, overlay.width, overlay.height);
  renderSummary(lastResponse);
  show("summary");
}
function backToPicker() {
  running = false;
  clearInterval(postTimer);
  stopCamera();
  clearState();
  banner(null);
  show("picker");
}

// ---------------------------------------------------------------------------
// summary from the accumulated reps[]
function renderSummary(r) {
  const reps = (r && r.reps) || [];
  const total = r ? r.rep_count : 0;
  $("sum-reps").textContent = total;

  const flagged = reps.filter((x) => x.flags && x.flags.length > 0);
  const clean = reps.length - flagged.length;
  $("sum-clean").textContent = reps.length
    ? `${clean} clean · ${flagged.length} flagged`
    : "No completed reps detected.";

  // tally flags across the set
  const tally = {};
  for (const x of flagged) for (const f of x.flags) tally[f] = (tally[f] || 0) + 1;
  const list = $("sum-flags");
  list.innerHTML = "";
  for (const [f, n] of Object.entries(tally)) {
    const sev = (severities[exercise] && severities[exercise][f]) || "med";
    const el = document.createElement("span");
    el.className = "flag " + sev;
    el.textContent = `${prettyFlag(f)} ×${n}`;
    list.appendChild(el);
  }
  $("sum-cue").textContent = reps.length
    ? "Keypoints only were sent to the detector — no video left your device."
    : "Try again — make sure your whole body is in frame.";
}

// ---------------------------------------------------------------------------
// wire up
document.querySelectorAll(".exercise-card").forEach((btn) => {
  btn.addEventListener("click", () => startSet(btn.dataset.exercise));
});
$("btn-stop").addEventListener("click", stopSet);
$("btn-back").addEventListener("click", backToPicker);
$("btn-again").addEventListener("click", () => show("picker"));

loadSeverities();

// Pre-warm the detector the moment the app opens. By the time someone has read
// the picker and chosen an exercise, a sleeping instance has usually finished
// booting -- which turns the most common cold start into no wait at all.
wakeApi().catch(() => {});

// register service worker (offline shell; pose model + API still need network)
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
