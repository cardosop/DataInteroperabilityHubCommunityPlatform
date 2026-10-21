"""
Worker Service Entry Point

Main entry point for the worker service that processes jobs from Redis queues.
Supports priority queues (job_critical, job_default, job_low) with reserved slots
and starvation prevention.

Usage:
    python services/worker/main.py [queue1] [queue2] ...

    Example:
        python services/worker/main.py job_critical job_default job_low

    Or use Django management command:
        python manage.py rqworker job_critical job_default job_low
"""

import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import django

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

# Setup Django
# JSON-friendly fallback before django.setup() installs django-structlog
# (see hub/settings.py) — early-startup messages stay structured.
logging.basicConfig(format="%(message)s", level=os.environ.get("LOG_LEVEL", "INFO"))

django.setup()

# Import after Django setup
from django.core.management import call_command

from services.worker.health import healthz, ready


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health check endpoints."""

    def do_GET(self):
        """Handle GET requests for health check endpoints."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == "/healthz":
            status_code, content = healthz()
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(content).encode("utf-8"))
        elif path == "/ready":
            status_code, content = ready()
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(content).encode("utf-8"))
        elif path == "/metrics":
            # Prometheus metrics endpoint
            try:
                from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

                metrics_data = generate_latest()
                self.send_response(200)
                self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                self.end_headers()
                self.wfile.write(metrics_data)
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress default logging for health checks."""
        # Health check requests are noisy, suppress logging


def start_health_check_server(port=8080):
    """
    Start HTTP server for health check endpoints in a background thread.

    Args:
        port: Port to listen on (default: 8080)
    """
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)

    def run_server():
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# WORKER_TYPE — selects which RQ queues this worker process joins (16.4).
#
# heavy  → job_critical only
#          Use for: DQ scans, compliance runs, scheduled data ingestion,
#          ODPS export / normalization (long-running, memory-intensive).
#          Deploy as a separate Deployment with higher memory limits.
#
# light  → job_default + job_low
#          Use for: webhook delivery, cache invalidation, search index
#          updates, contract validation (short-lived, I/O-bound).
#
# all    → job_critical + job_default + job_low  (default, backward-compat)
#          Suitable for development / single-node environments.
#
# Explicit queue args on the command line (sys.argv[1:]) always take
# precedence over WORKER_TYPE so operator overrides are always respected.
# ---------------------------------------------------------------------------
_WORKER_TYPE_QUEUES: dict[str, list[str]] = {
    "heavy": ["job_critical"],
    "light": ["job_default", "job_low"],
    "all": ["job_critical", "job_default", "job_low"],
}


def _resolve_concurrency() -> int | None:
    """Read WORKER_CONCURRENCY from the environment.

    Returns the integer value when the env var is a positive integer,
    or ``None`` when it is unset, empty, zero, negative, or non-integer.
    """
    import logging as _logging

    raw = os.environ.get("WORKER_CONCURRENCY", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
        if value <= 0:
            _logging.getLogger(__name__).warning(
                "WORKER_CONCURRENCY=%r must be positive, falling back to single-process rqworker",
                raw,
            )
            return None
    except ValueError:
        _logging.getLogger(__name__).warning(
            "Invalid WORKER_CONCURRENCY=%r — must be an integer, "
            "falling back to single-process rqworker",
            raw,
        )
        return None
    else:
        return value


def _resolve_serializer() -> str:
    """The RQ job serializer this worker must deserialize with.

    P0-7 (W105-ASYNC-LISTENER-LIVENESS): django-rq's rqworker command
    defaults ``--serializer`` to ``rq.serializers.DefaultSerializer``
    (pickle) and passes it to the Worker, OVERRIDING the queue's
    configured ``SERIALIZER`` — so a deployment with
    ``RQ_SERIALIZER=rq.serializers.JSONSerializer`` (the W0.7 R2-S8
    hardening) enqueued JSON while the worker tried to unpickle it:
    DeserializationError on EVERY job (search vectors, event
    persistence, webhook deliveries — the staging split the P0-7 probe
    caught).  The worker must agree with the enqueue side explicitly.
    """
    from django.conf import settings

    return getattr(settings, "RQ_SERIALIZER", None) or "rq.serializers.DefaultSerializer"


def start_event_listener() -> int:
    """Start the event-bus listener threads (W4.1, R2-B3/B4).

    The worker is the ONE process that runs the Redis pub/sub listener —
    bus subscribers (webhooks, mesh, virtualization, notifications) only
    deliver when a process runs ``EventBus.start_listening()`` (the
    pre-W4.1 stack had none, which is why the asset workflow grew the
    Phase-226 in-process webhook fallback).

    Gated by ``EVENT_BUS_LISTENER_ENABLED`` (kill switch).  Deployment
    contract: set the flag in BOTH worker and api services — the API
    reads the same flag to disarm its in-process webhook triggers so a
    deployment with the worker listener never double-delivers.

    Returns:
        Number of listener threads started (0 when disabled).
    """
    from hub.apps.core.events.listener import start_event_listener as _start

    listener = _start()
    if listener is None:
        return 0
    return len(listener.threads)


def main():
    """
    Main entry point for worker service.

    Reads WORKER_TYPE env var to select which RQ queues to join:
      heavy → job_critical
      light → job_default, job_low
      all   → all three queues (default)

    Also starts a health check HTTP server on port 8080 for k8s probes.
    """
    # Start health check server in background thread
    health_port = int(os.environ.get("WORKER_HEALTH_PORT", "8080"))
    start_health_check_server(port=health_port)

    # W4.1 (R2-B3/B4): the event-bus listener runs in the worker —
    # started BEFORE joining the RQ queues so bus delivery is live for
    # the whole process lifetime.  Kill switch:
    # EVENT_BUS_LISTENER_ENABLED=false.
    listener_threads = start_event_listener()
    if listener_threads:
        logging.getLogger(__name__).info("event_listener_started threads=%d", listener_threads)

    # Explicit queue args override WORKER_TYPE.
    if len(sys.argv) > 1:
        queues = sys.argv[1:]
    else:
        worker_type = os.environ.get("WORKER_TYPE", "all").lower()
        queues = _WORKER_TYPE_QUEUES.get(worker_type, _WORKER_TYPE_QUEUES["all"])
        if worker_type not in _WORKER_TYPE_QUEUES:
            logging.getLogger(__name__).warning(
                "Unknown WORKER_TYPE=%r — falling back to 'all'",
                worker_type,
            )

    # Use Django's call_command to run rqworker with proper options
    # --with-scheduler enables the built-in RQ scheduler so that
    # enqueue_in() delayed jobs (e.g. poll_compliance_job retries) fire
    # on time rather than waiting for manual promotion.
    # serializer= MUST be explicit — see _resolve_serializer().
    concurrency = _resolve_concurrency()
    if concurrency is not None:
        call_command(
            "rqworker-pool",
            *queues,
            verbosity=1,
            num_workers=concurrency,
            serializer=_resolve_serializer(),
        )
    else:
        call_command(
            "rqworker",
            *queues,
            verbosity=1,
            with_scheduler=True,
            serializer=_resolve_serializer(),
        )


if __name__ == "__main__":
    main()
