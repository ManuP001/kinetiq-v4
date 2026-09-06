# Detector API image for a Docker web service (Render/Fly/Railway).
#
# BUILD CONTEXT MUST BE THE REPO ROOT, not this directory. The detector's imports
# resolve by relative path arithmetic (gate_config.py reaches parents[2]/backend;
# config.py reaches parents[3]/exercises), so the image needs evals/gate0/,
# backend/app/core/ and exercises/ at the SAME relative layout as the repo -- not
# flattened.
#
#   docker build -f evals/gate0/prototype_api/Dockerfile -t kinetiq-api .
#   docker run -p 8000:8000 -e PROTOTYPE_API_CORS_ORIGINS="https://pwa.example.com" kinetiq-api
#
# No pose runtime here (no mediapipe/tensorflow): this service scores keypoints
# that the browser already extracted. That is the privacy invariant made physical.

FROM python:3.13-slim

WORKDIR /app

COPY evals/gate0/prototype_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Preserve the repo's relative layout -- see the note above.
COPY evals/gate0/ /app/evals/gate0/
COPY backend/app/ /app/backend/app/
COPY exercises/ /app/exercises/

WORKDIR /app/evals/gate0

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn prototype_api.main:app --host 0.0.0.0 --port ${PORT}"]
