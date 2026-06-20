"""
Pytest fixtures for Prefect Server/Workers testing.

These fixtures provide real Prefect Server and Worker instances for testing
(not mocks/stubs) using Docker containers.
"""

import os
import time

import pytest
import requests


@pytest.fixture(scope="session")
def prefect_server_url() -> str:
    """
    Get Prefect Server URL from environment or use default.

    Returns:
        Prefect Server API URL
    """
    return os.getenv("PREFECT_API_URL", "http://localhost:4200/api")


@pytest.fixture(scope="session")
def prefect_server_health(prefect_server_url: str) -> bool:
    """
    Check if Prefect Server is healthy.

    Args:
        prefect_server_url: Prefect Server API URL

    Returns:
        True if server is healthy, False otherwise
    """
    try:
        response = requests.get(f"{prefect_server_url}/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def prefect_server_available(prefect_server_health: bool) -> bool:
    """
    Skip tests if Prefect Server is not available.

    Args:
        prefect_server_health: Whether Prefect Server is healthy

    Returns:
        True if available, otherwise skips test
    """
    if not prefect_server_health:
        pytest.skip(
            "Prefect Server is not available. Start with: docker-compose -f docker-compose.test.yml up -d prefect-server"
        )
    return True


@pytest.fixture(scope="function")
def prefect_api_key(prefect_server_available: bool) -> str | None:
    """
    Get or create Prefect API key for testing.

    NOTE: In a real implementation, this would create a test API key.
    For now, returns None (Prefect Server may allow anonymous access in test mode).

    Args:
        prefect_server_available: Whether Prefect Server is available

    Returns:
        API key or None
    """
    # TODO: Implement API key creation when Prefect Server is set up
    # For now, return None (may work with anonymous access in test mode)
    return None


@pytest.fixture(scope="function")
def prefect_work_pool(prefect_server_available: bool, prefect_api_key: str | None) -> str:
    """
    Get or create Prefect work pool for testing.

    Args:
        prefect_server_available: Whether Prefect Server is available
        prefect_api_key: Prefect API key

    Returns:
        Work pool name
    """
    # Default work pool name for testing
    return "default"


@pytest.fixture(scope="function")
def wait_for_prefect_server(prefect_server_url: str, max_wait: int = 60) -> bool:
    """
    Wait for Prefect Server to be ready.

    Args:
        prefect_server_url: Prefect Server API URL
        max_wait: Maximum wait time in seconds

    Returns:
        True if server is ready, False otherwise
    """
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{prefect_server_url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)  # noqa: sleep-needed  # INTENTIONAL: test-specific delay
    return False
