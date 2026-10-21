# ---------------------------------------------------------------------------
# Stage 1: dev — the image the compose DEV and TEST stacks build
# (build.target: dev).  Includes dev requirements for in-container tests.
# W8.1: the PRODUCTION image (final stage) stays free of dev tooling —
# pinned by scripts/tests/test_w81_image_hardening.py.
#
# PUBLIC OVERLAY (Phase 313.3.5 / P3-2b): regenerated from the private
# services/worker/Dockerfile with ONE adaptation — the paid
# compliance-service bundle is NOT shipped in the public worker image
# (the overlay replaces the private COPY lines). Everything else
# (stages, W8.1 hardening, U.6 no-upgrade) tracks the private file; the
# stage parity is pinned by
# scripts/tests/test_publish_tree.py::test_worker_dockerfile_overlay_tracks_the_stage_split.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS dev

# Build-time arguments — injected by deploy.yml via --build-arg
# Docker silently ignores unknown build args, so ARG must be declared here
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

WORKDIR /app

# Install system dependencies
# libmagic1 is required by python-magic (magic-byte file-type validation used
# by the bundled compliance_engine package).  Without it, importing python-magic
# raises "failed to find libmagic.so.1 / libmagic-mgc" at runtime.
# Phase U.6: no `apt-get upgrade` — same root fix as services/api/Dockerfile
# (non-reproducible layer + the 2026-09-01 staging bring-up stall).
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies (production + development for testing)
# --no-cache-dir ensures pip always resolves the latest matching version
# instead of reusing stale wheels from BuildKit's cache mount.
RUN pip install --no-cache-dir --timeout=1200 --retries=20 -r requirements.txt && \
    pip install --no-cache-dir --timeout=1200 --retries=20 -r requirements-dev.txt

# Copy application code
COPY . .

# Phase 313.3 public build: the paid compliance engine is NOT shipped
# in the OSS worker image (the overlay replaces the private COPY line;
# guarded imports in the worker fall back when the package is absent).
# COPY services/compliance-service/ /app/compliance_engine/

# Expose build metadata as runtime env vars for OpenTelemetry service version
# and OCI image labels for traceability (matches services/api/Dockerfile)
ENV OTEL_SERVICE_VERSION=${GIT_SHA} \
    GIT_SHA=${GIT_SHA} \
    PYTHONPATH=/app:/app/compliance_engine

LABEL org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/DataInteroperabilityHub/DataInteroperabilityHub"

# Default command: process all priority queues (job_critical, job_default, job_low)
# Uses services/worker/main.py which includes health check HTTP server
# Can be overridden in docker-compose to process specific queues
# Priority order: job_critical (HIGH) → job_default (NORMAL) → job_low (LOW)
# Health check endpoints available at http://localhost:8080/healthz and /ready
CMD ["python", "services/worker/main.py", "job_critical", "job_default", "job_low"]

# ---------------------------------------------------------------------------
# Stage 2: production — the default (final) target deploy.yml builds.
# W8.1: runtime dependencies only, non-root, in-image HEALTHCHECK against
# the worker's own health server (/healthz on 8080).
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS production

ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user created BEFORE the copies so --chown resolves and the
# layer stays cacheable (no recursive chown — same root fix as
# services/prefect-integration/Dockerfile).
RUN useradd -m -u 1000 appuser

# Production requirements only.
COPY requirements.txt ./
RUN pip install --no-cache-dir --timeout=1200 --retries=20 -r requirements.txt

# Application code with ownership set during the copy.
COPY --chown=appuser:appuser . .

# Compliance engine bundle (see the dev stage for the layout rationale).
# PUBLIC OVERLAY: the paid bundle is NOT shipped in the OSS worker image.
# COPY --chown=appuser:appuser services/compliance-service/ /app/compliance_engine/

ENV OTEL_SERVICE_VERSION=${GIT_SHA} \
    GIT_SHA=${GIT_SHA} \
    PYTHONPATH=/app:/app/compliance_engine

LABEL org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/DataInteroperabilityHub/DataInteroperabilityHub"

USER appuser

EXPOSE 8080

# W8.1 — in-image healthcheck against the worker's own health server
# (services/worker/main.py serves /healthz and /ready on 8080).
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8080/healthz || exit 1

CMD ["python", "services/worker/main.py", "job_critical", "job_default", "job_low"]
