FROM python:3.12-slim

# Build-time arguments — injected by deploy.yml via --build-arg
# Docker silently ignores unknown build args, so ARG must be declared here
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose build metadata as runtime env vars for OpenTelemetry service version
# and OCI image labels for traceability (matches services/api/Dockerfile)
ENV OTEL_SERVICE_VERSION=${GIT_SHA} \
    GIT_SHA=${GIT_SHA}

LABEL org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/DataInteroperabilityHub/DataInteroperabilityHub"

# Default command: process all priority queues (job_critical, job_default, job_low)
# Uses services/worker/main.py which includes health check HTTP server
# Can be overridden in docker-compose to process specific queues
# Priority order: job_critical (HIGH) → job_default (NORMAL) → job_low (LOW)
# Health check endpoints available at http://localhost:8080/healthz and /ready
CMD ["python", "services/worker/main.py", "job_critical", "job_default", "job_low"]

