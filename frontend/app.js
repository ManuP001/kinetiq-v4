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
// POST buffered frames to the detector API
async function flush() {
  if (!running) return;
  if (frameBuffer.length === 0) return;
  const frames = frameBuffer;
  frameBuffer = [];
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
    clearState();
  } catch (err) {
    // Re-queue the frames we pulled so nothing is silently lost (the whole project's discipline).
    frameBuffer = frames.concat(frameBuffer);
    setState("Can't reach the trainer", String(err.message || err), "Retry", () => clearState());
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
    clearState();
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

// register service worker (offline shell; pose model + API still need network)
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
