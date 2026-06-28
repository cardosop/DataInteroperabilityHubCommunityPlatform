FROM python:3.12-slim

# Build-time arguments injected by CI (docker build --build-arg GIT_SHA=...)
# GIT_SHA is exposed as OTEL_SERVICE_VERSION so TracerProvider picks it up via
# settings.OTEL_SERVICE_VERSION without any runtime env var override.
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

WORKDIR /app

# Install system dependencies (unixodbc + PostgreSQL ODBC driver for virtualization ODBC sources,
# libfreetype6 for reportlab PDF invoice generation)
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl \
    unixodbc \
    unixodbc-dev \
    odbc-postgresql \
    libfreetype6 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI + Compose v2 plugin (needed for Docker Compose integration
# tests that run inside the container; docker.sock is mounted from the host).
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz \
    -o /tmp/docker.tgz && \
    tar -xzf /tmp/docker.tgz -C /tmp && \
    mv /tmp/docker/docker /usr/local/bin/docker && \
    chmod +x /usr/local/bin/docker && \
    rm -rf /tmp/docker /tmp/docker.tgz && \
    mkdir -p /usr/local/lib/docker/cli-plugins && \
    curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.1/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose && \
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Install kubectl (needed for Kubernetes manifest integration tests;
# validates kustomize build output via apply --dry-run=client).
RUN curl -fsSL "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    -o /usr/local/bin/kubectl && \
    chmod +x /usr/local/bin/kubectl

# Create non-root user early — this layer is cacheable until the base
# image changes (rare).  G3.1 (glittery-herding-graham): security hardening
# matching services/prefect-integration/Dockerfile.
RUN useradd -m -u 1000 appuser

# Copy requirements
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies (production + development for testing)
# --no-cache-dir ensures pip always resolves the latest matching version
# instead of reusing stale wheels from BuildKit's cache mount.
RUN pip install --no-cache-dir --timeout=1200 --retries=20 -r requirements.txt && \
    pip install --no-cache-dir --timeout=1200 --retries=20 -r requirements-dev.txt && \
    chown -R appuser:appuser /app

# Copy application code with correct ownership.
# --chown sets ownership during the copy so we avoid a recursive chown
# over millions of files (which was the bottleneck in every rebuild).
COPY --chown=appuser:appuser . .

# Install CLI and SDK packages for comprehensive testing
RUN --mount=type=cache,target=/root/.cache/pip \
    cd /app/cli && pip install --timeout=1200 --retries=20 -e . && \
    cd /app/sdk/python && pip install --timeout=1200 --retries=20 -e .

# OCI standard labels for registry UX (visible in GHCR, Docker Hub, etc.)
ENV OTEL_SERVICE_VERSION=${GIT_SHA} \
    GIT_SHA=${GIT_SHA}

LABEL org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/DataInteroperabilityHub/DataInteroperabilityHub"

USER appuser

EXPOSE 8000

# Default command: gunicorn with ASGI app + uvicorn workers (handles HTTP + WebSocket).
# gunicorn.conf.py at WORKDIR sets worker count from GUNICORN_WORKERS env var (default: cpu_count*2+1).
# Development overrides this with `uvicorn --reload` in docker-compose.yml.
CMD ["gunicorn", "hub.asgi:application", "--config", "gunicorn.conf.py"]

