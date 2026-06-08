"""
Shared pytest fixtures for CLI integration tests.

Provides service health checks and common fixtures for ODH integration tests,
plus a session-level auto-skip when the main Meshant API on port 8000 is not
reachable. CLI integration tests SHOULD never fail because a dev box has no
local API service running — they should skip cleanly. The actual integration
runs happen in CI where docker compose is up.
"""
import os
import pytest
import requests
import subprocess
import time

_api_test_port = os.environ.get("API_TEST_PORT", "8000")
_DEFAULT_API_BASE = f"http://localhost:{_api_test_port}"


def _api_is_reachable(url: str) -> bool:
    """Return True if the Meshant API root responds within the timeout."""
    try:
        response = requests.get(url, timeout=2)
    except requests.RequestException:
        return False
    # Any response (even 404 from root) proves the service is up.
    return response.status_code < 500


def pytest_collection_modifyitems(config, items):
    """Auto-skip CLI integration tests when no live Meshant API is reachable.

    Root cause: integration tests under ``cli/tests/integration/`` invoke the
    real CLI which makes real HTTP calls to the configured backend. On a dev
    box without docker compose running these calls fail with connection
    refused / 404 / 500, surfacing as 100+ test failures that are noise, not
    signal. The correct engineering behavior is to skip these tests when
    their precondition isn't met — the same pattern used by every
    integration suite in the SDK side of this repo.

    Opt-out: set ``MESHANT_FORCE_INTEGRATION=1`` to bypass the skip and run
    every integration test even when the API is unreachable (useful for
    triaging which tests would fail in CI).
    """
    if os.environ.get("MESHANT_FORCE_INTEGRATION") == "1":
        return
    api_url = os.environ.get(
        "MESHANT_API_URL",
        f"{_DEFAULT_API_BASE}/api/v1",
    )
    # Probe the API root once per session.
    api_root = api_url.rsplit("/api/v1", 1)[0] or api_url
    if _api_is_reachable(api_root):
        return
    skip_marker = pytest.mark.skip(
        reason=(
            f"Meshant API not reachable at {api_root}. CLI integration "
            "tests require a live backend; start docker compose or set "
            "MESHANT_FORCE_INTEGRATION=1 to override."
        )
    )
    for item in items:
        # Only skip items under tests/integration/ — leave unit tests alone.
        if "/tests/integration/" in str(item.fspath):
            item.add_marker(skip_marker)


def check_service_health(service_name: str, port: int, health_path: str = "/health", max_wait: int = 30) -> bool:
    """
    Check if a service is healthy.

    Args:
        service_name: Name of the service (for logging)
        port: Port number to check
        health_path: Health check endpoint path
        max_wait: Maximum time to wait in seconds

    Returns:
        True if service is healthy, False otherwise
    """
    for attempt in range(max_wait):
        try:
            response = requests.get(f"http://localhost:{port}{health_path}", timeout=2)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            # Connection refused / timeout is expected when the service
            # isn't up yet.  Let the retry loop keep trying.
            pass
        if attempt < max_wait - 1:
            time.sleep(1)
    return False


def start_service_if_needed(service_name: str, port: int, health_path: str = "/health") -> bool:
    """
    Start Docker Compose service if not running.

    Args:
        service_name: Docker Compose service name
        port: Service port number
        health_path: Health check endpoint path

    Returns:
        True if service is available, False otherwise
    """
    # Check if service is already running
    if check_service_health(service_name, port, health_path, max_wait=2):
        return True

    # Try to start the service
    try:
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
        result = subprocess.run(
            ['docker', 'compose', 'up', '-d', service_name],
            capture_output=True,
            timeout=60,
            cwd=project_dir
        )
        if result.returncode == 0:
            # Wait for service to be healthy
            return check_service_health(service_name, port, health_path, max_wait=60)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        # docker / docker-compose missing or broken — not a test failure.
        pass
    return False


@pytest.fixture(scope="session")
def odh_inference_scheduler_available():
    """
    Ensure ODH Inference Scheduler service is available.

    This fixture checks if the service is running and attempts to start it if needed.
    Tests that require this service should use this fixture.
    """
    service_name = "odh-inference-scheduler"
    port = 8097

    if not start_service_if_needed(service_name, port):
        pytest.skip(
            f"ODH Inference Scheduler service not available on port {port}. "
            f"Start with: docker compose up -d {service_name}"
        )
    return True


@pytest.fixture(scope="session")
def odh_training_operator_available():
    """
    Ensure ODH Training Operator service is available.

    This fixture checks if the service is running and attempts to start it if needed.
    Tests that require this service should use this fixture.
    """
    service_name = "odh-training-operator"
    port = 8096

    if not start_service_if_needed(service_name, port):
        pytest.skip(
            f"ODH Training Operator service not available on port {port}. "
            f"Start with: docker compose up -d {service_name}"
        )
    return True
