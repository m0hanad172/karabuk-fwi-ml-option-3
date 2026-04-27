# =====================================================================
# Karabuk FWI — backend image
# =====================================================================
# Starter template. Smoke-test before relying on it; see
# docs/DEPLOYMENT_PLAN.md for the rollout checklist.
# =====================================================================

FROM python:3.11-slim AS base

# Runtime deps for opencv (used by the monitoring layer). Ultralytics
# pulls in torch which provides its own libs, so we only need the
# minimal X-less OpenCV runtime here.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && python -m pip install --no-cache-dir -r /app/requirements.txt

# Copy backend source. The build context in docker-compose.yml is the
# `backend/` directory itself, so the paths below are relative to that.
COPY src/      /app/src/
COPY configs/  /app/configs/
COPY scripts/  /app/scripts/
COPY models/   /app/models/
COPY data/     /app/data/
COPY pytest.ini /app/pytest.ini

# Runtime DB lives here — mount a volume to persist it.
RUN mkdir -p /app/outputs

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    KARABUK_DB_PATH=/app/outputs/karabuk_fwi.db

EXPOSE 8000

# Production-style entrypoint (no --reload). Override in compose for dev.
CMD ["python", "-m", "uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
