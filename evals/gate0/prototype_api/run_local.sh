#!/usr/bin/env bash
# Run the whole prototype locally with a real webcam.
#   API  -> http://localhost:8000
#   PWA  -> http://localhost:8080
# http://localhost is a secure context by browser spec, so getUserMedia works
# without HTTPS. That stops being true for a phone on the LAN -- that is what
# the Render path in docs/DEPLOY_RUNBOOK.md is for.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PORT_API="${PORT_API:-8000}"
PORT_PWA="${PORT_PWA:-8080}"

export PROTOTYPE_API_CORS_ORIGINS="http://localhost:${PORT_PWA}"
cleanup() { kill "${API_PID:-}" "${PWA_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

( cd "$ROOT/evals/gate0" && python -m uvicorn prototype_api.main:app \
    --host 127.0.0.1 --port "$PORT_API" ) & API_PID=$!
( cd "$ROOT/frontend" && python -m http.server "$PORT_PWA" --bind 127.0.0.1 \
    >/dev/null 2>&1 ) & PWA_PID=$!

printf 'waiting for /health '
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${PORT_API}/health" >/dev/null 2>&1; then
    echo " ok"; break
  fi
  printf '.'; sleep 0.5
done

echo
echo "  API : http://localhost:${PORT_API}/health"
echo "  PWA : http://localhost:${PORT_PWA}"
echo "Ctrl+C to stop both."
wait
