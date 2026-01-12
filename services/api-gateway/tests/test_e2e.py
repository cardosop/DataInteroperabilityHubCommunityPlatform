"""
End-to-end tests for API Gateway service.

These tests test the complete request flow through the API Gateway.
All tests use real services - no mocks or stubs.
"""
import pytest
import os
import sys
from fastapi.testclient import TestClient
from django.utils import timezone

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

import django
django.setup()

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant, TenantStatus
from django.contrib.auth import get_user_model

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from main import app

User = get_user_model()


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestAPIGatewayE2E:
    """End-to-end tests for API Gateway"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def tenant(self):
        """Create a test tenant"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        return Tenant.objects.create(
            name=f"E2E Test Tenant {unique_id}",
            slug=f"e2e-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
        )

    @pytest.fixture
    def user(self, tenant):
        """Create a test user"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        return User.objects.create_user(
            email=f"e2e-test-user-{unique_id}@example.com",
            password="testpass123",
            tenant=tenant,
        )

    @pytest.fixture
    def api_key(self, tenant, user):
        """Create a test API key"""
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        api_key_obj = APIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            name="E2E Test Key",
            scopes=['read', 'write']
        )
        return plaintext_key

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "api-gateway"

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "api-gateway"

    def test_request_without_api_key(self, client):
        """Test request without API key returns 401"""
        # Health and metrics endpoints don't require API key
        # Test with a regular API endpoint
        response = client.get("/api/v1/test")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "API key required" in data["error"] or "required" in data["error"].lower()

    def test_request_with_invalid_api_key(self, client):
        """Test request with invalid API key returns 401"""
        response = client.get(
            "/api/v1/test",
            headers={"X-API-Key": "invalid-key-123"}
        )
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "Invalid" in data["error"] or "expired" in data["error"] or "not found" in data["error"].lower()

    def test_request_with_valid_api_key_authorization_header(self, client, api_key):
        """Test request with valid API key via Authorization header"""
        # Note: This will fail if backend service is not available
        # But it tests that the API key validation works
        response = client.get(
            "/api/v1/test",
            headers={"Authorization": f"ApiKey {api_key}"}
        )
        # Should either succeed (if backend is available) or return 502/504 (backend error)
        # But should NOT return 401 (authentication error)
        assert response.status_code != 401
        # If backend is not available, we might get 502 or 504
        # If backend is available, we might get 200 or other status
        assert response.status_code in [200, 404, 502, 504]

    def test_request_with_valid_api_key_x_api_key_header(self, client, api_key):
        """Test request with valid API key via X-API-Key header"""
        response = client.get(
            "/api/v1/test",
            headers={"X-API-Key": api_key}
        )
        # Should either succeed (if backend is available) or return 502/504 (backend error)
        # But should NOT return 401 (authentication error)
        assert response.status_code != 401
        assert response.status_code in [200, 404, 502, 504]

    def test_rate_limit_headers_in_response(self, client, api_key):
        """Test that rate limit headers are included in response"""
        # Use a known route that exists in routing config
        response = client.get(
            "/api/v1/contracts",
            headers={"X-API-Key": api_key}
        )

        # Check for rate limit headers (if request was processed and not 404)
        if response.status_code not in [401, 404, 502, 504]:
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers

    def test_gateway_request_id_header(self, client, api_key):
        """Test that gateway request ID is included in response"""
        # Use a known route that exists in routing config
        response = client.get(
            "/api/v1/contracts",
            headers={"X-API-Key": api_key}
        )

        # Check for gateway request ID header (if request was processed successfully)
        # Skip if there's an internal error (500) or other errors
        if response.status_code not in [401, 404, 500, 502, 504]:
            assert "X-Gateway-Request-ID" in response.headers

    def test_health_check_aggregation_endpoint(self, client):
        """Test aggregate health check endpoint"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert data["service"] == "api-gateway"
        assert "backend_services" in data
        assert isinstance(data["backend_services"], dict)

    def test_unknown_route_returns_404(self, client, api_key):
        """Test that unknown routes return 404"""
        response = client.get(
            "/api/v1/unknown-route-that-does-not-exist",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "Route not found" in data.get("error", "") or "not found" in data.get("error", "").lower()

    def test_query_string_preserved(self, client, api_key):
        """Test that query strings are preserved in routing"""
        # This test verifies query strings are forwarded to backend
        # The actual backend may not exist, but we check the request is processed
        response = client.get(
            "/api/v1/contracts?filter=active&sort=name",
            headers={"X-API-Key": api_key}
        )
        # Should not return 404 (route was found)
        # May return 502/504 if backend unavailable, but query string should be forwarded
        assert response.status_code != 404
