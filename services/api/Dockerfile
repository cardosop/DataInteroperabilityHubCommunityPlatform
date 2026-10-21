# ---------------------------------------------------------------------------
# Stage 1: dev — the image the compose DEV and TEST stacks build
# (build.target: dev).  Carries everything the in-container test suites
# need: dev requirements, the docker CLI + compose plugin, kubectl,
# gitleaks, promtool, git, and the editable CLI/SDK installs.
# W8.1: the PRODUCTION image (final stage) must stay free of this
# tooling — pinned by scripts/tests/test_w81_image_hardening.py.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS dev

# Build-time arguments injected by CI (docker build --build-arg GIT_SHA=...)
# GIT_SHA is exposed as OTEL_SERVICE_VERSION so TracerProvider picks it up via
# settings.OTEL_SERVICE_VERSION without any runtime env var override.
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

WORKDIR /app

# Install system dependencies (unixodbc + PostgreSQL ODBC driver for virtualization ODBC sources,
# libfreetype6 for reportlab PDF invoice generation)
# Phase U.6: no `apt-get upgrade` — upgrading inside a build is
# non-reproducible (layer contents depend on WHEN the build runs) and on
# 2026-09-01 it stalled the staging bring-up for 1.7h on a slow mirror.
# Fresh base images are pulled at build time; pin what we need and install.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
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
    libharfbuzz-subset0 \
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

# git for the in-container repo-side tests (tests/security/test_secrets_rotation.py
# shells out to the real binary against the bind-mounted .git). Installed as its
# own late layer so a change to this line never invalidates the expensive pip
# requirement layers above.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# gitleaks for the in-container tracked-tree secrets scan
# (tests/security/test_secrets_rotation.py::test_gitleaks_reports_tree_clean).
# Static binary, same pattern and late-layer caching rationale as the
# docker CLI install above.
RUN curl -fsSL https://github.com/gitleaks/gitleaks/releases/download/v8.18.4/gitleaks_8.18.4_linux_x64.tar.gz \
    -o /tmp/gitleaks.tgz && \
    tar -xzf /tmp/gitleaks.tgz -C /tmp && \
    mv /tmp/gitleaks /usr/local/bin/gitleaks && \
    chmod +x /usr/local/bin/gitleaks && \
    rm -f /tmp/gitleaks.tgz

# promtool for Prometheus alert-rule validation
# (tests/infrastructure/test_synthetic_probes.py::test_promtool_validates_rules).
# Copied from the official Prometheus image — version matches the stack.
COPY --from=prom/prometheus:v2.53.0 /bin/promtool /usr/local/bin/promtool

# Python SDK editable install — tests/sdk_python/test_sdk_installation.py
# (and importlib.metadata checks elsewhere) require the SDK pip-installed,
# not just importable via PYTHONPATH.
RUN pip install --no-cache-dir -e /app/sdk/python

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

# ---------------------------------------------------------------------------
# Stage 2: production — the default (final) target deploy.yml builds.
# W8.1: runtime dependencies ONLY (gcc/unixodbc-dev stay because pyodbc
# ships no manylinux wheel and builds from source at pip install),
# non-root user, in-image HEALTHCHECK.  No dev tooling, no
# requirements-dev, no editable CLI/SDK.
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
    unixodbc \
    unixodbc-dev \
    odbc-postgresql \
    libfreetype6 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user created BEFORE the copies so --chown resolves and the
# layer stays cacheable (no recursive chown — see services/api history).
RUN useradd -m -u 1000 appuser

# Production requirements only.
COPY requirements.txt ./
RUN pip install --no-cache-dir --timeout=1200 --retries=20 -r requirements.txt

# Application code with ownership set during the copy.
COPY --chown=appuser:appuser . .

ENV OTEL_SERVICE_VERSION=${GIT_SHA} \
    GIT_SHA=${GIT_SHA}

LABEL org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/DataInteroperabilityHub/DataInteroperabilityHub"

USER appuser

EXPOSE 8000

# W8.1 — in-image healthcheck matching the compose/helm healthchecks.
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8000/health/ || exit 1

CMD ["gunicorn", "hub.asgi:application", "--config", "gunicorn.conf.py"]
