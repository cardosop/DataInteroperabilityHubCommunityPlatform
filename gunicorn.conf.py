"""
Gunicorn configuration for the DataInteroperabilityHub API service.

Used by all non-development environments (staging, production, test).
Development uses `uvicorn --reload` directly (see docker-compose.yml).

Worker formula: (2 × CPU cores) + 1 — optimal for I/O-bound Django/DRF apps.
  1 CPU  →  3 workers
  2 CPU  →  5 workers
  4 CPU  →  9 workers
  8 CPU  → 17 workers

Override per environment via GUNICORN_WORKERS env var.
"""

import multiprocessing
import os

bind = "0.0.0.0:8000"

# Dynamic worker count — set GUNICORN_WORKERS per environment, defaults to (2×cores)+1
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# UvicornWorker: ASGI worker that handles HTTP + WebSocket (Django Channels).
# Required for WebSocket support — WSGI workers (sync/gthread) silently drop WS upgrades.
worker_class = "uvicorn.workers.UvicornWorker"

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))

# Recycle workers after N requests (±jitter) to prevent memory accumulation
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# Log to stdout/stderr (captured by Docker / k8s log collectors)
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
