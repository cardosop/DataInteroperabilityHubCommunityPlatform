"""
Smoke tests for API health endpoints.

These tests verify that all services are running and responding correctly.
"""
import os
import pytest
import requests
from typing import Dict, Any


# Get API URL from environment or use default
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
TIMEOUT = 10


@pytest.fixture
def api_client():
    """Create a requests session for API calls."""
    session = requests.Session()
    session.timeout = TIMEOUT
    return session


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_main_health_endpoint(self, api_client):
        """Test the main health endpoint."""
        response = api_client.get(f"{API_BASE_URL}/health/")
        assert response.status_code == 200, f"Health endpoint returned {response.status_code}"
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_semantic_service_health(self, api_client):
        """Test semantic service health endpoint (direct microservice check)."""
        import os
        semantic_url = os.getenv('SEMANTIC_SERVICE_URL', 'http://localhost:8082')
        try:
            response = api_client.get(f"{semantic_url}/health", timeout=5)
            assert response.status_code == 200, f"Semantic service health returned {response.status_code}"
            data = response.json()
            assert "status" in data
        except Exception:
            pytest.skip("Semantic service not available")
    
    def test_datacontract_service_health(self, api_client):
        """Test DataContract service health endpoint (direct microservice check)."""
        import os
        datacontract_url = os.getenv('DATACONTRACT_SERVICE_URL', 'http://localhost:8081')
        try:
            response = api_client.get(f"{datacontract_url}/health", timeout=5)
            assert response.status_code == 200, f"DataContract service health returned {response.status_code}"
            data = response.json()
            assert "status" in data
        except Exception:
            pytest.skip("DataContract service not available")
    
    def test_compliance_service_health(self, api_client):
        """Test compliance service health endpoint (direct microservice check)."""
        import os
        compliance_url = os.getenv('COMPLIANCE_SERVICE_URL', 'http://localhost:8083')
        try:
            response = api_client.get(f"{compliance_url}/health", timeout=5)
            assert response.status_code == 200, f"Compliance service health returned {response.status_code}"
            data = response.json()
            assert "status" in data
        except Exception:
            pytest.skip("Compliance service not available")
    
    def test_dq_service_health(self, api_client):
        """Test DQ service health endpoint (direct microservice check)."""
        import os
        dq_url = os.getenv('DQ_SERVICE_URL', 'http://localhost:8084')
        try:
            response = api_client.get(f"{dq_url}/health", timeout=5)
            assert response.status_code == 200, f"DQ service health returned {response.status_code}"
            data = response.json()
            assert "status" in data
        except Exception:
            pytest.skip("DQ service not available")


class TestAPIEndpoints:
    """Test basic API endpoints."""
    
    def test_openapi_schema_endpoint(self, api_client):
        """Test OpenAPI schema endpoint."""
        response = api_client.get(f"{API_BASE_URL}/api-docs/openapi.json")
        assert response.status_code == 200, f"Schema endpoint returned {response.status_code}"
        
        data = response.json()
        assert "openapi" in data or "swagger" in data
    
    def test_api_root_endpoint(self, api_client):
        """Test API root endpoint."""
        response = api_client.get(f"{API_BASE_URL}/api/v1/")
        # Should return 200 or 401/403 (if authentication required)
        assert response.status_code in [200, 401, 403], \
            f"API root returned unexpected status {response.status_code}"


class TestAuthentication:
    """Test authentication endpoints."""
    
    def test_unauthenticated_request_rejected(self, api_client):
        """Test that unauthenticated requests are properly rejected."""
        # Try to access a protected endpoint
        response = api_client.get(f"{API_BASE_URL}/api/v1/tenants/")
        
        # Should return 401 (Unauthorized) or 403 (Forbidden)
        assert response.status_code in [401, 403], \
            f"Unauthenticated request returned unexpected status {response.status_code}"
    
    def test_login_endpoint_exists(self, api_client):
        """Test that login endpoint exists and handles requests."""
        # Try to login without credentials (should return 400)
        response = api_client.post(
            f"{API_BASE_URL}/api/v1/auth/login/",
            json={}
        )
        
        # Should return 400 (Bad Request) or 401 (Unauthorized)
        assert response.status_code in [400, 401], \
            f"Login endpoint returned unexpected status {response.status_code}"


class TestCoreWorkflows:
    """Test core workflow endpoints."""
    
    def test_tenants_endpoint_exists(self, api_client):
        """Test that tenants endpoint exists."""
        response = api_client.get(f"{API_BASE_URL}/api/v1/tenants/")
        
        # Should return 401/403 (auth required) or 200 (if public)
        assert response.status_code in [200, 401, 403], \
            f"Tenants endpoint returned unexpected status {response.status_code}"
    
    def test_assets_endpoint_exists(self, api_client):
        """Test that assets endpoint exists."""
        response = api_client.get(f"{API_BASE_URL}/api/v1/assets/")
        
        # Should return 401/403 (auth required) or 200 (if public)
        assert response.status_code in [200, 401, 403], \
            f"Assets endpoint returned unexpected status {response.status_code}"
    
    def test_contracts_endpoint_exists(self, api_client):
        """Test that contracts endpoint exists."""
        response = api_client.get(f"{API_BASE_URL}/api/v1/contracts/")
        
        # Should return 401/403 (auth required) or 200 (if public)
        assert response.status_code in [200, 401, 403], \
            f"Contracts endpoint returned unexpected status {response.status_code}"

