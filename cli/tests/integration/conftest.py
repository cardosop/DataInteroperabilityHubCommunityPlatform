"""
Shared pytest fixtures for CLI integration tests.

Provides service health checks and common fixtures for ODH integration tests,
plus a session-level auto-skip when the main Meshant API on port 8000 is not
reachable. CLI integration tests SHOULD never fail because a dev box has no
local API service running — they should skip cleanly. The actual integration
runs happen in CI where docker compose is up.

W16 (Phase T.4): the auto-skip is the shared ``tests._env_skip`` policy —
in CI an unreachable API RAISES instead of skipping (the environment failure
announces itself); local runs keep the graceful skip.
"""

# Django-backed modules in this directory import ``hub``/Django models at
# module scope, so settings must be configured before collection.  Kept
# here (not in the suite-root conftest) so unit batches never import
# ``hub.settings`` — that import opens a real PostgreSQL connection.
from tests._django_bootstrap import ensure_django

ensure_django()

import os
import subprocess
import time

import pytest
import requests
from tests._env_skip import auto_skip_unreachable_api

from envpolicy import skip_or_fail


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

    W16: in CI an unreachable API fails the run loudly.
    """
    auto_skip_unreachable_api(
        items,
        suite_label="CLI integration tests",
        path_scopes=("/tests/integration/",),
    )


def check_service_health(
    _service_name: str, port: int, health_path: str = "/health", max_wait: int = 30
) -> bool:
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
            time.sleep(1)  # noqa: sleep-needed — polling loop  # INTENTIONAL: sleep-needed (auto-fixer marker completion)
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
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        result = subprocess.run(
            ["docker", "compose", "up", "-d", service_name],
            check=False,
            capture_output=True,
            timeout=60,
            cwd=project_dir,
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
        skip_or_fail(
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
        skip_or_fail(
            f"ODH Training Operator service not available on port {port}. "
            f"Start with: docker compose up -d {service_name}"
        )
    return True
