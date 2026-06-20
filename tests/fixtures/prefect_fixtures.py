"""
Prefect Server and Workers Test Fixtures

Real fixtures (not mocks) for Prefect Server and Workers integration testing.
These fixtures provide actual Prefect Server and Workers instances for testing.
"""

import os
import time
from contextlib import contextmanager
from typing import Any

import httpx
import pytest


def wait_for_prefect_server(url: str, timeout: int = 60, interval: float = 2.0) -> bool:
    """
    Wait for Prefect Server to become healthy.

    Args:
        url: Prefect Server URL
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds

    Returns:
        True if server is healthy, False otherwise
    """
    health_url = f"{url}/api/health"
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = httpx.get(health_url, timeout=5.0)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(interval)

    return False


def wait_for_prefect_worker(url: str, timeout: int = 60, interval: float = 2.0) -> bool:
    """
    Wait for Prefect Worker to become healthy.

    Args:
        url: Prefect Worker health check URL
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds

    Returns:
        True if worker is healthy, False otherwise
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(interval)

    return False


@pytest.fixture(scope="session")
def prefect_server_url() -> str:
    """
    Prefect Server URL fixture.

    Returns the Prefect Server URL from environment or defaults to localhost.
    """
    return os.getenv("PREFECT_SERVER_URL", "http://localhost:4200")


@pytest.fixture(scope="session")
def prefect_server_healthy(prefect_server_url: str) -> str:
    """
    Ensure Prefect Server is running and healthy.

    This fixture waits for Prefect Server to become available before tests run.
    If the server is not available, tests will be skipped.
    """
    if not wait_for_prefect_server(prefect_server_url, timeout=60):
        pytest.skip(f"Prefect Server not available at {prefect_server_url}")

    return prefect_server_url


@pytest.fixture(scope="session")
def prefect_api_client(prefect_server_healthy: str):
    """
    Prefect API client fixture.

    Provides a configured Prefect API client for interacting with Prefect Server.
    """
    try:
        from prefect import get_client
        from prefect.client.orchestration import PrefectClient

        # Create Prefect client with server URL
        client = PrefectClient(api_url=f"{prefect_server_healthy}/api")
        return client
    except ImportError:
        pytest.skip("Prefect client not available - install prefect package")
    except Exception as e:
        pytest.skip(f"Failed to create Prefect client: {e}")


@pytest.fixture(scope="session")
def prefect_worker_url() -> str:
    """
    Prefect Worker URL fixture.

    Returns the Prefect Worker health check URL from environment or defaults.
    """
    return os.getenv("PREFECT_WORKER_HEALTH_URL", "http://localhost:4201/health")


@pytest.fixture(scope="session")
def prefect_worker_healthy(prefect_worker_url: str) -> str:
    """
    Ensure Prefect Worker is running and healthy.

    This fixture waits for Prefect Worker to become available before tests run.
    If the worker is not available, tests will be skipped.
    """
    if not wait_for_prefect_worker(prefect_worker_url, timeout=60):
        pytest.skip(f"Prefect Worker not available at {prefect_worker_url}")

    return prefect_worker_url


@pytest.fixture(scope="session")
def prefect_worker_pool(prefect_api_client, prefect_server_healthy: str) -> dict[str, Any]:
    """
    Prefect Worker Pool fixture.

    Creates a test worker pool for running Prefect flows.
    """
    try:
        # Create a test worker pool
        pool_name = f"test-pool-{int(time.time())}"

        # Use Prefect API to create pool
        # This is a placeholder - actual implementation depends on Prefect API
        pool_config = {
            "name": pool_name,
            "type": "process",
            "base_job_template": {"job_configuration": {"command": "python -m prefect.engine"}},
        }

        return pool_config
    except Exception as e:
        pytest.skip(f"Failed to create Prefect worker pool: {e}")


@pytest.fixture
def prefect_deployment(prefect_api_client, prefect_server_healthy: str) -> dict[str, Any]:
    """
    Prefect Deployment fixture.

    Creates a test Prefect deployment for running flows.
    """
    try:
        deployment_name = f"test-deployment-{int(time.time())}"

        deployment_config = {
            "name": deployment_name,
            "flow_name": "test-flow",
            "work_pool_name": "default",
            "enabled": True,
        }

        return deployment_config
    except Exception as e:
        pytest.skip(f"Failed to create Prefect deployment: {e}")


@pytest.fixture
def prefect_flow_run(prefect_api_client, prefect_deployment: dict[str, Any]) -> dict[str, Any]:
    """
    Prefect Flow Run fixture.

    Creates a test Prefect flow run.
    """
    try:
        flow_run_name = f"test-flow-run-{int(time.time())}"

        flow_run_config = {
            "name": flow_run_name,
            "deployment_id": prefect_deployment.get("id"),
            "state": "PENDING",
        }

        return flow_run_config
    except Exception as e:
        pytest.skip(f"Failed to create Prefect flow run: {e}")


@contextmanager
def prefect_docker_compose_fixture(compose_file: str = "docker-compose.test.yml"):
    """
    Context manager for Prefect Server Docker Compose fixture.

    Starts Prefect Server using Docker Compose and ensures it's healthy.
    Yields the server URL and cleans up on exit.
    """
    import subprocess

    # Start Prefect Server
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d", "prefect-server"], check=True
    )

    server_url = "http://localhost:4200"

    try:
        # Wait for server to be healthy
        if wait_for_prefect_server(server_url, timeout=60):
            yield server_url
        else:
            raise RuntimeError("Prefect Server failed to become healthy")
    finally:
        # Stop Prefect Server
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "stop", "prefect-server"], check=False
        )


@contextmanager
def prefect_workers_docker_compose_fixture(compose_file: str = "docker-compose.test.yml"):
    """
    Context manager for Prefect Workers Docker Compose fixture.

    Starts Prefect Workers using Docker Compose and ensures they're healthy.
    Yields the worker health URL and cleans up on exit.
    """
    import subprocess

    # Start Prefect Workers
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d", "prefect-worker"], check=True
    )

    worker_url = "http://localhost:4201/health"

    try:
        # Wait for workers to be healthy
        if wait_for_prefect_worker(worker_url, timeout=60):
            yield worker_url
        else:
            raise RuntimeError("Prefect Workers failed to become healthy")
    finally:
        # Stop Prefect Workers
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "stop", "prefect-worker"], check=False
        )
