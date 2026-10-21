FROM python:3.12-slim

# Build-time arguments — injected by deploy.yml via --build-arg
# Docker silently ignores unknown build args, so ARG must be declared here
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

WORKDIR /app

# Install system dependencies
# libmagic1 is required by python-magic (magic-byte file-type validation used
# by the bundled compliance_engine package).  Without it, importing python-magic
# raises "failed to find libmagic.so.1 / libmagic-mgc" at runtime.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
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

# ---------------------------------------------------------------------------
# Phase 19.12.1 — Bundle the compliance-service as an importable package so
# that the worker can run compliance scans in-process (no HTTP round-trip).
#
# The compliance-service source tree is copied to /app/compliance_engine/.
# Its __init__.py (services/compliance-service/__init__.py) re-exports the
# four primary classes (PIIDetector, RegulatoryMapper, PolicyEngine,
# ComplianceReport) so callers can do:
#     from compliance_engine import PIIDetector
#
# PYTHONPATH has TWO entries:
#   /app                  → allows  `import compliance_engine`  (package)
#   /app/compliance_engine → allows the intra-package bare imports that the
#                            compliance-service modules already use, e.g.
#                            `from pii_detector import PIIDetector`, without
#                            requiring any changes to the upstream source.
# ---------------------------------------------------------------------------
# Phase 313.3 — public build: the paid compliance engine is NOT shipped
# in the OSS worker image (overlay replaces the private COPY line).
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

