FROM python:3.12-slim

# Build-time arguments injected by CI (docker build --build-arg GIT_SHA=...)
# GIT_SHA is exposed as OTEL_SERVICE_VERSION so TracerProvider picks it up via
# settings.OTEL_SERVICE_VERSION without any runtime env var override.
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

WORKDIR /app

# Install system dependencies (unixodbc + PostgreSQL ODBC driver for virtualization ODBC sources,
# libfreetype6 for reportlab PDF invoice generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl \
    unixodbc \
    unixodbc-dev \
    odbc-postgresql \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies (production + development for testing)
# Long timeout for large wheels on slow links (same policy as Prefect worker images)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout=1200 --retries=20 -r requirements.txt && \
    pip install --timeout=1200 --retries=20 -r requirements-dev.txt

# Copy application code
COPY . .

# Install CLI and SDK packages for comprehensive testing
RUN --mount=type=cache,target=/root/.cache/pip \
    cd /app/cli && pip install --timeout=1200 --retries=20 -e . && \
    cd /app/sdk/python && pip install --timeout=1200 --retries=20 -e .

# Expose port
# Expose build args as runtime environment variables.
# OTEL_SERVICE_VERSION: consumed by hub/apps/observability/otel_config.py
#   get_service_version() → settings.OTEL_SERVICE_VERSION → this value.
# OCI standard labels for registry UX (visible in GHCR, Docker Hub, etc.)
ENV OTEL_SERVICE_VERSION=${GIT_SHA} \
    GIT_SHA=${GIT_SHA}

LABEL org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/DataInteroperabilityHub/DataInteroperabilityHub"

EXPOSE 8000

# Default command: gunicorn with ASGI app + uvicorn workers (handles HTTP + WebSocket).
# gunicorn.conf.py at WORKDIR sets worker count from GUNICORN_WORKERS env var (default: cpu_count*2+1).
# Development overrides this with `uvicorn --reload` in docker-compose.yml.
CMD ["gunicorn", "hub.asgi:application", "--config", "gunicorn.conf.py"]

