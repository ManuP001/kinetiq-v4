// config.js -- runtime config for the Kinetiq camera PWA.
//
// The API base URL is the ONE thing that changes between local and deployed.
// Keep it here so deploying is editing one line (or running set-api-url.ps1),
// never a code change.
//
//   local run (run_local) : the API is same-host on :8000
//   Render                : the deployed API origin, https, no trailing slash
window.KINETIQ_CONFIG = {
  API_BASE_URL: "http://localhost:8000",

  // How often buffered keypoint frames are flushed to the detector API (ms).
  // The server rescores the whole buffer each call, so this trades latency
  // against request volume.
  POST_INTERVAL_MS: 400,

  // Must stay "blazepose_33" -- it is the landmark order the detector's
  // keypoint_map.py expects. Changing it without changing the detector's map
  // silently misreads every joint.
  POSE_MODEL: "blazepose_33",

  // Pose model assets, loaded in-browser from a CDN. The video never leaves
  // this device; only the extracted landmark numbers are POSTed.
  MEDIAPIPE_VERSION: "0.10.18",
  POSE_TASK_URL:
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
};
