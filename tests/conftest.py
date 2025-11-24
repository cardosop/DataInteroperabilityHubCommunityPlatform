"""
Pytest configuration and shared fixtures
"""
import pytest
import os
import time
from django.test import Client
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


@pytest.fixture
def api_client():
    """Django REST Framework API client"""
    return Client()


@pytest.fixture
def test_user(db):
    """Create a test user"""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
        display_name="Test User"
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Authenticated API client"""
    api_client.force_login(test_user)
    return api_client


def wait_for_service_health(url: str, timeout: int = 30, interval: float = 1.0) -> bool:
    """
    Wait for a service to become healthy.
    
    Args:
        url: Health check URL
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds
        
    Returns:
        True if service is healthy, False otherwise
    """
    try:
        import httpx
    except ImportError:
        # Fallback to requests if httpx not available
        try:
            import requests
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    response = requests.get(url, timeout=5.0)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('status') == 'healthy':
                            return True
                except Exception:
                    pass
                time.sleep(interval)
            return False
        except ImportError:
            pytest.skip("httpx or requests required for service health checks")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


@pytest.fixture(scope="session")
def datacontract_service():
    """Ensure DataContract CLI service is running and healthy"""
    service_url = os.getenv(
        'DATACONTRACT_SERVICE_URL',
        getattr(settings, 'DATACONTRACT_CLI_SERVICE_URL', 'http://localhost:8080')
    )
    health_url = f"{service_url}/health"
    
    if not wait_for_service_health(health_url, timeout=30):
        pytest.skip(f"DataContract CLI service not available at {service_url}")
    
    return service_url


@pytest.fixture(scope="session")
def dq_service():
    """Ensure DQ service is running and healthy"""
    service_url = os.getenv(
        'DQ_SERVICE_URL',
        getattr(settings, 'DQ_SERVICE_URL', 'http://localhost:8083')
    )
    health_url = f"{service_url}/health"
    
    if not wait_for_service_health(health_url, timeout=30):
        pytest.skip(f"DQ service not available at {service_url}")
    
    return service_url


@pytest.fixture(scope="session")
def compliance_service():
    """Ensure Compliance service is running and healthy"""
    service_url = os.getenv(
        'COMPLIANCE_SERVICE_URL',
        getattr(settings, 'COMPLIANCE_SERVICE_URL', 'http://localhost:8082')
    )
    health_url = f"{service_url}/health"
    
    if not wait_for_service_health(health_url, timeout=30):
        pytest.skip(f"Compliance service not available at {service_url}")
    
    return service_url


@pytest.fixture(scope="session")
def semantic_service():
    """Ensure Semantic service is running and healthy"""
    service_url = os.getenv(
        'SEMANTIC_SERVICE_URL',
        getattr(settings, 'SEMANTIC_SERVICE_URL', 'http://localhost:8081')
    )
    health_url = f"{service_url}/health"
    
    if not wait_for_service_health(health_url, timeout=30):
        pytest.skip(f"Semantic service not available at {service_url}")
    
    return service_url


@pytest.fixture(scope="session")
def all_services(datacontract_service, dq_service, compliance_service, semantic_service):
    """Ensure all microservices are running and healthy"""
    return {
        'datacontract': datacontract_service,
        'dq': dq_service,
        'compliance': compliance_service,
        'semantic': semantic_service,
    }


def check_service_health(service_url: str, service_name: str, timeout: int = 10) -> bool:
    """
    Helper function to check if a service is healthy.
    Can be used in Django TestCase setUp methods.
    
    Args:
        service_url: Base URL of the service
        service_name: Name of the service (for error messages)
        timeout: Timeout in seconds
        
    Returns:
        True if service is healthy, False otherwise
    """
    health_url = f"{service_url}/health"
    return wait_for_service_health(health_url, timeout=timeout)

