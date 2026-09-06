#!/usr/bin/env bash
# One-command "does it all talk" check. Run this before handing a URL to anyone.
#
#   ./check_local.sh                          # a local dev run on 127.0.0.1:8000
#   ./check_local.sh https://api.example.com  # a deployed instance
#
# Step 2 is the point: /health returning 200 does NOT prove a good deploy. An
# image built without exercises/ boots fine and answers /health, then 500s on
# every real request. Only a real /prototype/assess round-trip catches that.
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
BASE_URL="${BASE_URL%/}"
echo "Checking ${BASE_URL} ..."

printf '1. GET /health ... '
HEALTH=$(curl -sf "${BASE_URL}/health") || {
  echo "FAILED (no response -- is the API running/reachable?)"; exit 1; }
python -c "
import json,sys
d=json.loads(sys.argv[1])
assert d.get('status')=='ok', f'unexpected body: {d!r}'
assert 'squat' in d.get('supported_exercises',[]), f'squat missing: {d!r}'
assert d.get('contracts_loaded',0)>0, f'zero contracts loaded: {d!r}'
" "$HEALTH" || { echo "FAILED (unexpected /health body: $HEALTH)"; exit 1; }
echo "ok"

printf '2. POST /prototype/assess (real round-trip) ... '
BODY=$(curl -sf -X POST "${BASE_URL}/prototype/assess" \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"check-local","exercise_id":"squat","reset":true,
       "frames":[{"t_ms":0,"pose_model":"blazepose_33",
         "people":[{"track_id":0,"kp":[[0.5,0.5,0.0,0.9]],"box":[0.4,0.4,0.2,0.2]}]}]}') || {
  echo "FAILED (non-2xx). If this is deployed and the browser is what fails,"
  echo "        check PROTOTYPE_API_CORS_ORIGINS -- curl itself ignores CORS."
  exit 1; }
python -c "
import json,sys
d=json.loads(sys.argv[1])
assert 'rep_count' in d, f'unexpected body: {d!r}'
assert d['rep_count']==0, f'a single static frame must not be a rep: {d!r}'
" "$BODY" || { echo "FAILED (unexpected body: $BODY)"; exit 1; }
echo "ok"

echo
echo "All checks passed. ${BASE_URL} is reachable and talking correctly."
echo "(API only. The phone smoke test in docs/DEPLOY_RUNBOOK.md is the only thing"
echo " that proves the PWA's camera, CORS and model-loading path.)"
