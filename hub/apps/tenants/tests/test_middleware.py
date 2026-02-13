"""
Unit tests for tenant middleware.
"""
import pytest
from django.test import TestCase, RequestFactory
from django.http import HttpResponse, JsonResponse
from unittest.mock import Mock
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.tenants.middleware import TenantSuspensionMiddleware



pytestmark = pytest.mark.django_db(transaction=True)
class TenantSuspensionMiddlewareTest(TestCase):
    """Test TenantSuspensionMiddleware"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = TenantSuspensionMiddleware(self.get_response)
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
    
    def test_suspended_tenant_blocks_writes(self):
        """Test that suspended tenant blocks write operations"""
        self.tenant.suspend()
        
        request = self.factory.post("/api/assets/")
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)
    
    def test_suspended_tenant_allows_reads(self):
        """Test that suspended tenant allows read operations"""
        self.tenant.suspend()
        
        request = self.factory.get("/api/assets/")
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)  # Middleware allows request to continue
    
    def test_deleted_tenant_blocks_all(self):
        """Test that deleted tenant blocks all operations"""
        self.tenant.soft_delete()
        
        request = self.factory.get("/api/assets/")
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)
    
    def test_active_tenant_allows_all(self):
        """Test that active tenant allows all operations"""
        request = self.factory.post("/api/assets/")
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)  # Middleware allows request to continue
    
    def test_allowed_paths_bypass_middleware(self):
        """Test that allowed paths bypass middleware"""
        self.tenant.suspend()
        
        request = self.factory.post("/health/")
        request.tenant = self.tenant
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)  # Health check is allowed

    def test_auth_paths_bypass_middleware(self):
        """Test that /api/v1/auth/ paths bypass subscription/suspension checks."""
        self.tenant.suspend()
        request = self.factory.post("/api/v1/auth/logout/")
        request.tenant = self.tenant
        request.tenant_id = str(self.tenant.id)
        response = self.middleware.process_request(request)
        self.assertIsNone(response, "Auth paths must be allowed regardless of subscription/suspension")

    def test_auth_sessions_revoke_bypass_middleware(self):
        """Test that POST /api/v1/auth/sessions/<id>/revoke/ bypasses subscription check."""
        self.tenant.suspend()
        request = self.factory.post("/api/v1/auth/sessions/00000000-0000-0000-0000-000000000001/revoke/")
        request.tenant = self.tenant
        request.tenant_id = str(self.tenant.id)
        response = self.middleware.process_request(request)
        self.assertIsNone(response, "Session revoke must be allowed regardless of subscription/suspension")
    
    def test_middleware_is_callable(self):
        """Test that middleware is callable (Django 6 pattern)"""
        request = self.factory.get("/api/v1/assets/")
        request.tenant = self.tenant
        
        response = self.middleware(request)
        
        self.assertIsNotNone(response)
        self.assertIsInstance(response, HttpResponse)
        self.get_response.assert_called_once()
    
    def test_middleware_performance(self):
        """Test middleware performance (should be fast)"""
        import time
        
        request = self.factory.get("/api/v1/assets/")
        request.tenant = self.tenant
        
        start = time.time()
        for _ in range(100):
            self.middleware.process_request(request)
        elapsed = time.time() - start
        
        # Should process 100 requests in less than 0.5 seconds
        self.assertLess(elapsed, 0.5, f"Middleware too slow: {elapsed:.3f}s for 100 requests")

