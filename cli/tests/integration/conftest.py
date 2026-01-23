"""
Shared pytest fixtures for CLI integration tests.

Provides service health checks and common fixtures for ODH integration tests.
"""
import pytest
import requests
import subprocess
import time
import os


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
        except Exception:
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
    except Exception:
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
