// app.js -- the camera loop.
//
// PRIVACY INVARIANT (root CLAUDE.md): the pose model runs HERE, in the browser.
// The only thing that ever crosses the network is the array of landmark numbers.
// There is no code path in this file that sends a frame, a canvas, a blob or a
// data URL anywhere. Keep it that way.
//
// BOUNDARY (frontend/CLAUDE.md): this file is a CONSUMER of the detector. Rep
// counting, flags and cues all come from the API response. Nothing here decides
// whether a rep happened or a fault occurred.

import {
  FilesetResolver,
  PoseLandmarker,
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18";

const CFG = window.KINETIQ_CONFIG;
const API = CFG.API_BASE_URL.replace(/\/$/, "");

const $ = (id) => document.getElementById(id);
const screens = Array.from(document.querySelectorAll("[data-screen]"));

function show(id) {
  for (const s of screens) s.hidden = s.id !== id;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  exercise: "squat",
  severities: {},
  landmarker: null,
  stream: null,
  running: false,
  sessionId: null,
  firstPost: true,
  pending: [], // frames not yet acknowledged by the server
  lastResult: null,
  posting: false,
  apiDown: false,
  startedAt: 0,
  framesSeen: 0,
};

// ---------------------------------------------------------------------------
// Setup screen
// ---------------------------------------------------------------------------

const EXERCISES = [
  { id: "squat", label: "Squat", hint: "Phone at hip height, side or 45°" },
  { id: "pushup", label: "Push-up", hint: "Phone on the floor, side on" },
  { id: "lunge", label: "Lunge", hint: "Side on, both legs visible" },
];

function renderChoices() {
  const host = $("exercise-choices");
  host.innerHTML = "";
  for (const ex of EXERCISES) {
    const b = document.createElement("button");
    b.className = "choice";
    b.type = "button";
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", String(ex.id === state.exercise));
    b.innerHTML =
      `<span><strong>${ex.label}</strong><br><span class="muted small">${ex.hint}</span></span>` +
      `<span class="tick" aria-hidden="true">✓</span>`;
    b.addEventListener("click", () => {
      state.exercise = ex.id;
      renderChoices();
    });
    host.appendChild(b);
  }
}

// ---------------------------------------------------------------------------
// Boot: severities + pose model
// ---------------------------------------------------------------------------

async function boot() {
  try {
    const res = await fetch("severities.json", { cache: "no-cache" });
    state.severities = (await res.json()).exercises || {};
  } catch {
    // Non-fatal: flags still render, just without severity colour.
    state.severities = {};
  }

  try {
    $("loading-detail").textContent = "Loading the pose model…";
    const fileset = await FilesetResolver.forVisionTasks(
      `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${CFG.MEDIAPIPE_VERSION}/wasm`
    );
    state.landmarker = await PoseLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: CFG.POSE_TASK_URL, delegate: "GPU" },
      runningMode: "VIDEO",
      numPoses: 2, // >1 so a bystander is SEEN and the server can lock past them
      minPoseDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });
  } catch (err) {
    $("loading-detail").innerHTML =
      `Couldn’t load the pose model.<br><span class="small">${escapeHtml(String(err))}</span>`;
    return;
  }

  renderChoices();
  show("screen-setup");
}

// ---------------------------------------------------------------------------
// Camera
// ---------------------------------------------------------------------------

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    $("denied-detail").textContent =
      "This browser can’t open the camera. On a phone this usually means the page " +
      "isn’t on HTTPS — a plain http:// address other than localhost is blocked.";
    show("screen-denied");
    return;
  }
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 720 }, height: { ideal: 960 } },
      audio: false,
    });
  } catch (err) {
    $("denied-detail").textContent =
      err && err.name === "NotAllowedError"
        ? "Camera permission was denied. Kinetiq needs it to count reps — nothing is recorded or uploaded."
        : `Couldn’t open the camera (${err?.name || err}).`;
    show("screen-denied");
    return;
  }

  const video = $("video");
  video.srcObject = state.stream;
  await video.play();

  state.running = true;
  state.sessionId = `s-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  state.firstPost = true;
  state.pending = [];
  state.lastResult = null;
  state.apiDown = false;
  state.startedAt = performance.now();
  state.framesSeen = 0;

  render(null);
  show("screen-running");
  requestAnimationFrame(tick);
  state.timer = setInterval(flush, CFG.POST_INTERVAL_MS);
}

function stopCamera() {
  state.running = false;
  clearInterval(state.timer);
  if (state.stream) {
    for (const t of state.stream.getTracks()) t.stop();
    state.stream = null;
  }
  $("video").srcObject = null;
  renderSummary();
  show("screen-summary");
}

// ---------------------------------------------------------------------------
// Per-frame: pose -> the frame shape the detector expects
// ---------------------------------------------------------------------------

function bbox(landmarks) {
  let x0 = 1, y0 = 1, x1 = 0, y1 = 0;
  for (const p of landmarks) {
    if ((p.visibility ?? 1) < 0.5) continue;
    x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y);
    x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y);
  }
  if (x1 <= x0 || y1 <= y0) return [0, 0, 0, 0];
  return [x0, y0, x1 - x0, y1 - y0];
}

// The frame shape is dictated by the backend's validate_frame_schema
// (frontend/CLAUDE.md: "do not guess"):
//   {t_ms, pose_model, people:[{track_id, kp:[[x,y,z,vis]...], box}]}
function buildFrame(result, tMs) {
  const people = (result.landmarks || []).map((landmarks, i) => ({
    track_id: i,
    kp: landmarks.map((p) => [p.x, p.y, p.z ?? 0, p.visibility ?? 1]),
    box: bbox(landmarks),
  }));
  return { t_ms: Math.round(tMs), pose_model: CFG.POSE_MODEL, people };
}

let lastVideoTime = -1;

function tick() {
  if (!state.running) return;
  const video = $("video");
  if (video.readyState >= 2 && video.currentTime !== lastVideoTime) {
    lastVideoTime = video.currentTime;
    const tMs = performance.now() - state.startedAt;
    try {
      const result = state.landmarker.detectForVideo(video, tMs);
      if (result?.landmarks?.length) {
        state.pending.push(buildFrame(result, tMs));
        state.framesSeen++;
      }
    } catch {
      // A dropped inference frame is survivable; the next one will land.
    }
  }
  requestAnimationFrame(tick);
}

// ---------------------------------------------------------------------------
// Flush: send only NEW frames; never drop them on failure
// ---------------------------------------------------------------------------

async function flush() {
  if (!state.running || state.posting || state.pending.length === 0) return;
  state.posting = true;

  // Take the batch, but keep it until the server confirms. If the POST fails the
  // frames go back on the FRONT of the queue -- frontend/CLAUDE.md requires
  // buffered frames be re-queued, never dropped, or the rep count silently
  // under-counts exactly when the network is worst.
  const batch = state.pending;
  state.pending = [];
  const wasFirst = state.firstPost;

  try {
    const res = await fetch(`${API}/prototype/assess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sessionId,
        exercise_id: state.exercise,
        reset: wasFirst,
        frames: batch,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.firstPost = false;
    state.lastResult = await res.json();
    setApiDown(false);
    render(state.lastResult);
  } catch {
    state.pending = batch.concat(state.pending);
    setApiDown(true);
  } finally {
    state.posting = false;
  }
}

function setApiDown(down) {
  if (state.apiDown === down) return;
  state.apiDown = down;
  $("banner-api").hidden = !down;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function severityOf(faultId) {
  return state.severities?.[state.exercise]?.[faultId]?.severity || "unknown";
}

function humanize(faultId) {
  return faultId.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function render(result) {
  $("rep-count").textContent = result?.rep_count ?? 0;
  $("phase").textContent = result?.phase ?? "idle";

  const cue = $("cue");
  if (result?.coaching_cue) {
    cue.textContent = result.coaching_cue;
    cue.hidden = false;
  } else {
    cue.hidden = true;
  }

  const flags = $("flags");
  flags.innerHTML = "";
  for (const f of result?.flags || []) {
    const el = document.createElement("span");
    el.className = `pill ${severityOf(f)}`;
    el.textContent = humanize(f);
    flags.appendChild(el);
  }

  $("stat-line").textContent =
    `${state.framesSeen} frames · ${state.pending.length} queued`;
}

function renderSummary() {
  const r = state.lastResult;
  $("summary-reps").textContent = r?.rep_count ?? 0;
  const body = $("summary-body");
  body.innerHTML = "";

  if (!r || r.rep_count === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = state.framesSeen === 0
      ? "No frames captured. Was anyone in shot?"
      : "No complete reps detected in that set.";
    body.appendChild(empty);
    return;
  }

  const counts = new Map();
  const unknown = new Map();
  for (const rep of r.reps || []) {
    for (const f of rep.faults || []) counts.set(f, (counts.get(f) || 0) + 1);
    for (const f of rep.insufficient_evidence || []) unknown.set(f, (unknown.get(f) || 0) + 1);
  }

  if (counts.size === 0) {
    const clean = document.createElement("div");
    clean.className = "empty";
    clean.textContent = "No form flags raised. Clean set.";
    body.appendChild(clean);
  }
  for (const [f, n] of [...counts].sort((a, b) => b[1] - a[1])) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML =
      `<span class="pill ${severityOf(f)}">${escapeHtml(humanize(f))}</span>` +
      `<span class="muted">${n} of ${r.rep_count} reps</span>`;
    body.appendChild(row);
  }
  // Surfaced, not hidden: "couldn't tell" is different from "fine".
  for (const [f, n] of unknown) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML =
      `<span class="pill unknown">${escapeHtml(humanize(f))}</span>` +
      `<span class="muted small">couldn’t judge on ${n} rep(s) — check framing</span>`;
    body.appendChild(row);
  }
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

$("btn-start").addEventListener("click", startCamera);
$("btn-retry").addEventListener("click", startCamera);
$("btn-stop").addEventListener("click", stopCamera);
$("btn-again").addEventListener("click", () => {
  renderChoices();
  show("screen-setup");
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}

boot();
