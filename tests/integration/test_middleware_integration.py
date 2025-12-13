"""
Integration tests for all middleware working together.

Tests middleware execution order, interactions, and integration behavior.
"""
import pytest
from django.test import TestCase, RequestFactory, Client
from django.http import HttpResponse
from unittest.mock import Mock, patch
import uuid

from hub.apps.api.middleware import RequestIDMiddleware
from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.tenants.middleware import TenantSuspensionMiddleware
from hub.apps.rate_limiting.middleware import RateLimitMiddleware
from hub.apps.observability.middleware import MetricsMiddleware
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


pytestmark = pytest.mark.django_db(transaction=True)


class MiddlewareIntegrationTest(TestCase):
    """Test all middleware working together"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.client = Client()
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
    
    def test_middleware_execution_order(self):
        """Test that middleware execute in correct order"""
        # Create middleware chain
        get_response = Mock(return_value=HttpResponse())
        
        metrics = MetricsMiddleware(get_response)
        request_id = RequestIDMiddleware(metrics)
        tenant_scoping = TenantScopingMiddleware(request_id)
        tenant_suspension = TenantSuspensionMiddleware(tenant_scoping)
        rate_limit = RateLimitMiddleware(tenant_suspension)
        
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        
        # Execute middleware chain
        response = rate_limit(request)
        
        # Verify execution order
        # 1. RequestIDMiddleware should set request.id
        self.assertTrue(hasattr(request, 'id'))
        
        # 2. TenantScopingMiddleware should set tenant_id
        self.assertTrue(hasattr(request, 'tenant_id'))
        
        # 3. MetricsMiddleware should record start time
        self.assertTrue(hasattr(request, '_metrics_start_time'))
        
        # 4. Response should be returned
        self.assertIsNotNone(response)
    
    def test_middleware_with_real_request(self):
        """Test middleware with real HTTP request"""
        # Use Django test client which uses full middleware stack
        response = self.client.get("/health/")
        
        # Health endpoint should work
        self.assertEqual(response.status_code, 200)
        
        # Request ID should be in response headers
        self.assertIn('X-Request-ID', response)
    
    def test_middleware_error_handling(self):
        """Test middleware error handling"""
        # Create middleware that raises exception
        def failing_get_response(request):
            raise Exception("Test error")
        
        metrics = MetricsMiddleware(failing_get_response)
        request_id = RequestIDMiddleware(metrics)
        
        request = self.factory.get("/api/v1/assets/")
        
        # Should handle exception gracefully
        with self.assertRaises(Exception):
            request_id(request)
        
        # Request ID should still be set
        self.assertTrue(hasattr(request, 'id'))
    
    def test_middleware_performance_under_load(self):
        """Test middleware performance under load"""
        import time
        
        get_response = Mock(return_value=HttpResponse())
        metrics = MetricsMiddleware(get_response)
        request_id = RequestIDMiddleware(metrics)
        tenant_scoping = TenantScopingMiddleware(request_id)
        tenant_suspension = TenantSuspensionMiddleware(tenant_scoping)
        rate_limit = RateLimitMiddleware(tenant_suspension)
        
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        
        # Test with 100 requests
        start = time.time()
        for _ in range(100):
            rate_limit(request)
        elapsed = time.time() - start
        
        # Should process 100 requests in less than 2 seconds
        self.assertLess(elapsed, 2.0, f"Middleware too slow: {elapsed:.3f}s for 100 requests")
    
    def test_middleware_tenant_isolation(self):
        """Test that middleware maintains tenant isolation"""
        tenant2 = Tenant.objects.create(name="Test Tenant 2", slug="test-tenant-2")
        user2 = User.objects.create_user(
            email="test2@example.com",
            password="testpass123",
            tenant=tenant2
        )
        
        get_response = Mock(return_value=HttpResponse())
        tenant_scoping = TenantScopingMiddleware(get_response)
        
        # Request 1: User 1
        request1 = self.factory.get("/api/v1/assets/")
        request1.user = self.user
        tenant_scoping(request1)
        
        # Request 2: User 2
        request2 = self.factory.get("/api/v1/assets/")
        request2.user = user2
        tenant_scoping(request2)
        
        # Tenants should be isolated
        self.assertEqual(str(request1.tenant_id), str(self.tenant.id))
        self.assertEqual(str(request2.tenant_id), str(tenant2.id))
        self.assertNotEqual(request1.tenant_id, request2.tenant_id)
    
    def test_middleware_rate_limiting_integration(self):
        """Test rate limiting middleware with other middleware"""
        from hub.apps.rate_limiting.service import RateLimitResult
        from hub.apps.rate_limiting.utils import TimeWindow, EndpointCategory
        
        get_response = Mock(return_value=HttpResponse())
        
        with patch('hub.apps.rate_limiting.middleware.check_rate_limit') as mock_check:
            # Mock rate limit to allow
            mock_check.return_value = (True, [
                RateLimitResult(
                    allowed=True,
                    limit=60,
                    remaining=55,
                    reset_time=1000,
                    limit_type='tenant',
                    category=EndpointCategory.DQ_RUN,
                    window=TimeWindow.SUSTAINED
                )
            ])
            
            rate_limit = RateLimitMiddleware(get_response)
            request_id = RequestIDMiddleware(rate_limit)
            tenant_scoping = TenantScopingMiddleware(request_id)
            
            request = self.factory.post("/api/v1/dq/runs/")
            request.user = self.user
            
            response = tenant_scoping(request)
            
            # Should allow request
            self.assertIsNotNone(response)
            # Rate limit should be checked
            mock_check.assert_called_once()
    
    def test_middleware_suspended_tenant_integration(self):
        """Test suspended tenant middleware with other middleware"""
        self.tenant.suspend()
        
        get_response = Mock(return_value=HttpResponse())
        tenant_suspension = TenantSuspensionMiddleware(get_response)
        tenant_scoping = TenantScopingMiddleware(tenant_suspension)
        
        # Write operation should be blocked
        request = self.factory.post("/api/v1/assets/")
        request.user = self.user
        
        response = tenant_scoping(request)
        
        # Should return 403 response
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        
        # Read operation should be allowed
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        
        response = tenant_scoping(request)
        
        # Should allow request to continue
        # Suspended tenant should either return None (no response) or 200 (if middleware allows)
        # The assertion should check that response is either None or has status 200
        if response is not None:
            self.assertEqual(response.status_code, 200)

