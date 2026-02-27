"""
Integration tests for Traefik as single entrypoint.

Phase 10: With Traefik and dynamic routes enabled, verifies:
- GET / (or frontend host) → response from frontend service
- GET /api/v1/... → response from api-gateway (routing to api-service)

Uses real Traefik, frontend, api-gateway, and api-service; no mocks.

Run with Docker Compose (recommended):
  ./scripts/run_phase10_traefik_routing_tests.sh
  Or: docker compose up -d traefik frontend api-gateway api-service
      docker compose exec -e PYTEST_DOCKER_COMPOSE_RUNTIME=1 -e TRAEFIK_BASE_URL=https://traefik:443 api-service \\
        python -m pytest tests/integration/test_traefik_routing.py -v -m 'integration and docker_compose_runtime'

When TRAEFIK_BASE_URL is set (e.g. https://traefik:443), services are assumed already up.
When unset, set PYTEST_DOCKER_COMPOSE_RUNTIME=1 to start services via DockerComposeManager (host run).
"""
import os
import time
from pathlib import Path

import pytest
import requests

# Suppress InsecureRequestWarning when using verify=False for Traefik self-signed/dev cert
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

project_root = Path(__file__).resolve().parent.parent.parent

# Reuse Docker Compose manager implementation from test_docker_compose_deployment
from tests.integration.test_docker_compose_deployment import DockerComposeManager, _docker_available
from tests.utils.polling import wait_until


@pytest.fixture(scope="module")
def docker_compose_file():
    """Path to docker-compose.yml."""
    compose_file = project_root / "docker-compose.yml"
    assert compose_file.exists(), f"docker-compose.yml not found at {compose_file}"
    return compose_file


# Traefik routing test services: traefik, frontend, api-gateway, api-service and their deps
TRAEFIK_ROUTING_SERVICES = [
    "traefik",
    "frontend",
    "api-gateway",
    "api-service",
]


def _traefik_secure_port() -> int:
    """Traefik HTTPS port on host (docker-compose: TRAEFIK_SECURE_PORT:-8443)."""
    return int(os.environ.get("TRAEFIK_SECURE_PORT", "8443"))


def _traefik_base_url() -> str:
    """Base URL for Traefik HTTPS.
    When TRAEFIK_BASE_URL is set (e.g. https://traefik:443 from inside Docker), use it.
    Otherwise use host URL (https://127.0.0.1:TRAEFIK_SECURE_PORT).
    """
    base = os.environ.get("TRAEFIK_BASE_URL", "").strip()
    if base:
        return base.rstrip("/")
    port = _traefik_secure_port()
    return f"https://127.0.0.1:{port}"


def _traefik_services_already_running() -> bool:
    """True when services are assumed up (e.g. running in api-service with Docker Compose)."""
    return bool(os.environ.get("TRAEFIK_BASE_URL", "").strip())


@pytest.fixture(scope="module")
def docker_compose_manager_traefik(docker_compose_file):
    """Create Docker Compose manager for Traefik routing tests (used only when not TRAEFIK_BASE_URL)."""
    if not _traefik_services_already_running() and not _docker_available():
        pytest.skip("Docker CLI not available (run these tests on host with Docker)")
    manager = DockerComposeManager(docker_compose_file)
    yield manager
    if not _traefik_services_already_running():
        manager.stop_services()


@pytest.fixture(scope="module")
def traefik_services_up(docker_compose_manager_traefik):
    """Ensure Traefik, frontend, api-gateway, api-service (and deps) are up.
    When TRAEFIK_BASE_URL is set, assume services are already running (e.g. in Docker Compose).
    Otherwise start them via DockerComposeManager (for host-based runs).
    """
    if not _traefik_services_already_running():
        docker_compose_manager_traefik.start_services(TRAEFIK_ROUTING_SERVICES, wait=True)
        # Poll until route responds (no fixed sleep per 3.3.2)
        def _root_ok():
            try:
                r = requests.get(
                    f"{_traefik_base_url()}/",
                    timeout=5,
                    verify=False,
                    headers={"Host": "localhost"},
                )
                return r.status_code == 200
            except Exception:
                return False

        wait_until(_root_ok, timeout=10, interval=0.5, message="Traefik route GET / not 200")
    return docker_compose_manager_traefik


@pytest.mark.integration
@pytest.mark.docker_compose_runtime
class TestTraefikRouting:
    """Traefik single-entrypoint routing: GET / → frontend, GET /api/v1/... → api-gateway."""

    def test_traefik_get_root_returns_frontend(self, traefik_services_up):
        """GET / via Traefik returns response from frontend (HTML)."""
        base = _traefik_base_url()
        resp = requests.get(
            f"{base}/",
            timeout=15,
            verify=False,
            headers={"Host": "localhost"},
        )
        assert resp.status_code == 200, (
            f"GET / via Traefik must return 200, got {resp.status_code}"
        )
        content_type = resp.headers.get("Content-Type", "")
        assert "text/html" in content_type or resp.text.lstrip().lower().startswith("<!doctype html") or "<html" in resp.text.lower(), (
            f"GET / must be HTML from frontend; Content-Type={content_type}, body start={resp.text[:200]!r}"
        )

    def test_traefik_get_api_v1_health_returns_api_gateway(self, traefik_services_up):
        """GET /api/v1/health via Traefik returns response from api-gateway (JSON)."""
        base = _traefik_base_url()
        resp = requests.get(
            f"{base}/api/v1/health",
            timeout=15,
            verify=False,
            headers={"Host": "localhost"},
        )
        assert resp.status_code == 200, (
            f"GET /api/v1/health via Traefik must return 200, got {resp.status_code}"
        )
        data = resp.json()
        assert "status" in data, (
            f"Gateway health must include 'status'; got keys: {list(data.keys())}"
        )
        assert data["status"] in ("healthy", "degraded"), (
            f"Gateway health status must be healthy or degraded; got {data.get('status')}"
        )
        assert "backend_services" in data, (
            "Gateway aggregate health must include backend_services"
        )


def pytest_configure(config):
    """Register custom markers when this module is loaded."""
    config.addinivalue_line(
        "markers", "docker_compose_runtime: marks tests as requiring Docker Compose runtime"
    )
