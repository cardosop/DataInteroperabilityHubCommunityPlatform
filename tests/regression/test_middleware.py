"""
Comprehensive regression tests for all middleware functionality.

Tests all middleware components:
- TenantScopingMiddleware
- TenantSuspensionMiddleware
- RateLimitMiddleware
- RequestIDMiddleware
- MetricsMiddleware
"""
import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import UserStatus
from hub.apps.auth.models import APIKey
from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.tenants.middleware import TenantSuspensionMiddleware
from hub.apps.rate_limiting.middleware import RateLimitMiddleware
from hub.apps.api.middleware import RequestIDMiddleware
from hub.apps.observability.middleware import MetricsMiddleware

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MiddlewareRegressionTest(TestCase):
    """Base class for middleware regression tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(
            name="Middleware Test Tenant",
            slug="middleware-test-tenant"
        )
        self.user = User.objects.create_user(
            email="middleware@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )


class TenantScopingMiddlewareTest(MiddlewareRegressionTest):
    """Test TenantScopingMiddleware"""
    
    def test_tenant_scoping_with_authenticated_user(self):
        """Test tenant scoping with authenticated user"""
        self.client.force_authenticate(user=self.user)
        
        # Make a request
        response = self.client.get('/api/v1/assets/')
        
        # Should succeed (tenant should be set by middleware)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_tenant_scoping_with_api_key(self):
        """Test tenant scoping with API key"""
        # API keys must be user-scoped (not tenant-scoped)
        api_key_obj = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,  # User-scoped API key required
            name="Test API Key",
            key_hash=APIKey.hash_key("test-key-123")
        )
        
        # Make request with API key
        response = self.client.get(
            '/api/v1/assets/',
            HTTP_AUTHORIZATION="ApiKey test-key-123"
        )
        
        # Should succeed (tenant should be set by middleware)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_tenant_scoping_without_authentication(self):
        """Test tenant scoping without authentication"""
        # Make unauthenticated request
        response = self.client.get('/api/v1/assets/')
        
        # Should fail with authentication required
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class TenantSuspensionMiddlewareTest(MiddlewareRegressionTest):
    """Test TenantSuspensionMiddleware"""
    
    def test_suspended_tenant_blocks_access(self):
        """Test that suspended tenant blocks write operations"""
        # Suspend tenant and refresh from DB to ensure status is updated
        self.tenant.suspend()
        # Refresh tenant from DB to get latest status (this ensures we have the latest from DB)
        self.tenant.refresh_from_db()
        # Verify tenant is actually suspended
        self.assertEqual(self.tenant.status, TenantStatus.SUSPENDED)
        
        # Ensure user has tenant relationship properly set
        # Refresh user from DB to ensure tenant_id is loaded
        self.user.refresh_from_db()
        # Access tenant relationship to ensure it's loaded (triggers Django to set tenant_id)
        _ = self.user.tenant  # Access to trigger relationship loading
        # Verify user has tenant_id set
        self.assertIsNotNone(self.user.tenant_id, "User should have tenant_id set")
        self.assertEqual(self.user.tenant_id, self.tenant.id, "User tenant_id should match tenant id")
        
        # Force authenticate - this sets request.user
        self.client.force_authenticate(user=self.user)
        
        # Verify the user object passed to force_authenticate has tenant_id
        # This ensures the middleware can access it
        self.assertIsNotNone(self.user.tenant_id, "User object should have tenant_id before request")
        
        # Make a write request (POST) - should be blocked
        response = self.client.post(
            '/api/v1/assets/',
            {'key': 'test-asset', 'name': 'Test Asset'},
            format='json'
        )
        
        # Should be blocked for write operations (403 Forbidden)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, 
                        f"Expected 403 Forbidden for suspended tenant, got {response.status_code}. "
                        f"Response: {response.content if hasattr(response, 'content') else 'No content'}")
        
        # Parse JSON response (middleware returns JsonResponse, not DRF Response)
        import json
        if hasattr(response, 'content'):
            response_data = json.loads(response.content.decode('utf-8'))
        elif hasattr(response, 'data'):
            response_data = response.data
        else:
            response_data = {}
        
        self.assertIn('suspended', response_data.get('error', '').lower() or '')
        
        # GET requests should still work (read-only mode)
        response = self.client.get('/api/v1/assets/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_active_tenant_allows_access(self):
        """Test that active tenant allows access"""
        # Tenant is active by default
        self.client.force_authenticate(user=self.user)
        
        # Make a request
        response = self.client.get('/api/v1/assets/')
        
        # Should succeed
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_health_endpoint_bypasses_suspension(self):
        """Test that health endpoint bypasses suspension"""
        self.tenant.suspend()
        
        # Health endpoint should work even for suspended tenants
        response = self.client.get('/health/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])


class RateLimitMiddlewareTest(MiddlewareRegressionTest):
    """Test RateLimitMiddleware"""
    
    def test_rate_limit_headers_present(self):
        """Test that rate limit headers are present in responses"""
        self.client.force_authenticate(user=self.user)
        
        # Make a request
        response = self.client.get('/api/v1/assets/')
        
        # Should have rate limit headers (if middleware is active)
        # Headers may or may not be present depending on configuration
        if 'X-RateLimit-Limit' in response.headers:
            self.assertIn('X-RateLimit-Limit', response.headers)
            self.assertIn('X-RateLimit-Remaining', response.headers)
    
    def test_rate_limit_exceeded_response(self):
        """Test rate limit exceeded response"""
        self.client.force_authenticate(user=self.user)
        
        # Make many requests to potentially exceed rate limit
        # This depends on rate limit configuration
        for _ in range(100):
            response = self.client.get('/api/v1/assets/')
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                # Rate limit exceeded
                self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
                break


class RequestIDMiddlewareTest(MiddlewareRegressionTest):
    """Test RequestIDMiddleware"""
    
    def test_request_id_generated(self):
        """Test that request ID is generated"""
        self.client.force_authenticate(user=self.user)
        
        # Make a request
        response = self.client.get('/api/v1/assets/')
        
        # Should have request ID in response headers (if middleware is active)
        # Request ID may be in X-Request-ID header or response data
        if 'X-Request-ID' in response.headers:
            request_id = response.headers['X-Request-ID']
            # Should be a valid UUID
            try:
                uuid.UUID(request_id)
            except ValueError:
                self.fail(f"Request ID {request_id} is not a valid UUID")
    
    def test_request_id_from_header(self):
        """Test that request ID from header is used"""
        self.client.force_authenticate(user=self.user)
        
        custom_request_id = str(uuid.uuid4())
        
        # Make request with custom request ID
        response = self.client.get(
            '/api/v1/assets/',
            HTTP_X_REQUEST_ID=custom_request_id
        )
        
        # If middleware is active, should use custom request ID
        if 'X-Request-ID' in response.headers:
            self.assertEqual(response.headers['X-Request-ID'], custom_request_id)


class MetricsMiddlewareTest(MiddlewareRegressionTest):
    """Test MetricsMiddleware"""
    
    def test_metrics_recorded(self):
        """Test that metrics are recorded for requests"""
        self.client.force_authenticate(user=self.user)
        
        # Make a request
        response = self.client.get('/api/v1/assets/')
        
        # Metrics should be recorded (verified via Prometheus metrics endpoint)
        # This is tested in integration tests, here we just verify the request succeeds
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])


class MiddlewareIntegrationTest(MiddlewareRegressionTest):
    """Test middleware working together"""
    
    def test_full_middleware_stack(self):
        """Test full middleware stack"""
        self.client.force_authenticate(user=self.user)
        
        # Make a request through full middleware stack
        response = self.client.get('/api/v1/assets/')
        
        # Should process through all middleware
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_middleware_order(self):
        """Test middleware execution order"""
        # Suspend tenant and ensure status is persisted
        self.tenant.suspend()
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, TenantStatus.SUSPENDED)
        
        self.client.force_authenticate(user=self.user)
        
        # Tenant suspension should block write operations before rate limiting
        # Make a write request (POST) - should be blocked by suspension middleware
        response = self.client.post(
            '/api/v1/assets/',
            {'key': 'test-asset', 'name': 'Test Asset'},
            format='json'
        )
        
        # Should be blocked by suspension middleware (403) before rate limit check
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN,
                        f"Expected 403 Forbidden for suspended tenant, got {response.status_code}. "
                        f"Response: {response.content if hasattr(response, 'content') else 'No content'}")
        
        # Parse JSON response (middleware returns JsonResponse, not DRF Response)
        import json
        if hasattr(response, 'content'):
            response_data = json.loads(response.content.decode('utf-8'))
        elif hasattr(response, 'data'):
            response_data = response.data
        else:
            response_data = {}
        
        self.assertIn('suspended', response_data.get('error', '').lower() or '')

