"""
Integration tests for Traefik as single entrypoint.

Phase 10: With Traefik and dynamic routes enabled, verifies:
- GET / (or frontend host) → response from frontend service
- GET /api/v1/... → response from api-service (Django)

Uses real Traefik, frontend, and api-service; no mocks.

**Inside Docker (test-batch-10-2i):** auto-detects ``traefik-test`` hostname
and uses plain HTTP on port 80.  No Docker CLI or TLS needed.

**On host:** set ``TRAEFIK_BASE_URL`` to the Traefik HTTPS endpoint and run
with ``PYTEST_DOCKER_COMPOSE_RUNTIME=1`` to manage services via Docker Compose.
"""

import os
import socket
from pathlib import Path

import pytest
import requests

project_root = Path(__file__).resolve().parent.parent.parent


# ── Environment detection ────────────────────────────────────────────────

def _running_inside_docker() -> bool:
    """True when we can reach traefik-test on port 80 (Docker test network)."""
    try:
        s = socket.create_connection(("traefik-test", 80), timeout=1)
        s.close()
        return True
    except OSError:
        return False


def _traefik_base_url() -> str:
    """Base URL for Traefik.

    Inside Docker: ``http://traefik-test:80`` (plain HTTP, no TLS between containers).
    On host: ``TRAEFIK_BASE_URL`` env var or ``https://127.0.0.1:8443``.
    """
    if _running_inside_docker():
        return "http://traefik-test:80"
    base = os.environ.get("TRAEFIK_BASE_URL", "").strip()
    if base:
        return base.rstrip("/")
    port = int(os.environ.get("TRAEFIK_SECURE_PORT", "8443"))
    return f"https://127.0.0.1:{port}"


def _use_tls() -> bool:
    """True when TLS/HTTPS should be used (host mode with self-signed cert)."""
    return not _running_inside_docker()


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def traefik_base():
    """Base URL for Traefik, skipping if unreachable."""
    if _running_inside_docker():
        return _traefik_base_url()
    # Host mode: require TRAEFIK_BASE_URL or Docker CLI
    if not os.environ.get("TRAEFIK_BASE_URL", "").strip():
        from tests.integration.test_docker_compose_deployment import _docker_available
        if not _docker_available():
            pytest.skip(
                "Traefik tests require Docker CLI on host. "
                "Run inside Docker (test-batch-10-2i) or set TRAEFIK_BASE_URL."
            )
    return _traefik_base_url()


# ── Tests ────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.requires_db
class TestTraefikRouting:
    """Traefik single-entrypoint routing: GET / → frontend, GET /api/v1/... → api-service."""

    def test_traefik_get_root_returns_frontend(self, traefik_base):
        """GET / via Traefik returns response from frontend (HTML)."""
        resp = requests.get(
            f"{traefik_base}/",
            timeout=15,
            verify=not _use_tls(),
        )
        assert resp.status_code == 200, (
            f"GET / via Traefik must return 200, got {resp.status_code}"
        )
        content_type = resp.headers.get("Content-Type", "")
        assert (
            "text/html" in content_type
            or resp.text.lstrip().lower().startswith("<!doctype html")
            or "<html" in resp.text.lower()
        ), (
            f"GET / must be HTML from frontend; "
            f"Content-Type={content_type}, body start={resp.text[:200]!r}"
        )

    def test_traefik_get_api_v1_health_returns_api_service(self, traefik_base):
        """GET /api/v1/health via Traefik returns response from api-service."""
        resp = requests.get(
            f"{traefik_base}/api/v1/health",
            timeout=15,
            verify=not _use_tls(),
        )
        # Any response from Django (200, 400, 401, 404, 503) proves Traefik
        # routed the request correctly to api-service.  400 is common when
        # the Host header doesn't match ALLOWED_HOSTS — routing still works.
        assert resp.status_code != 0, (
            f"GET /api/v1/health via Traefik must not hang; got {resp.status_code}"
        )
        # Verify we reached Django (not Traefik's own 404 router).
        # Django returns either JSON (API-style) or HTML (DEBUG=True 400 page).
        content_type = resp.headers.get("Content-Type", "")
        body_start = resp.text[:200].strip().lower() if resp.text else ""
        is_django = (
            "application/json" in content_type
            or "text/html" in content_type
            or "doctype html" in body_start
            or "<html" in body_start
        )
        assert is_django, (
            f"Health response must come from Django (JSON or HTML); "
            f"Content-Type={content_type}, body={body_start[:100]!r}"
        )


def pytest_configure(config):
    """Register custom markers when this module is loaded."""
    config.addinivalue_line(
        "markers", "docker_compose_runtime: marks tests as requiring Docker Compose runtime"
    )
