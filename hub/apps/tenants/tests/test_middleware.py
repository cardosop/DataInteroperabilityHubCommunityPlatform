"""
Unit tests for tenant middleware.
"""
import pytest
from django.test import TestCase, RequestFactory
from django.http import HttpResponse, JsonResponse
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.tenants.middleware import TenantSuspensionMiddleware



pytestmark = pytest.mark.django_db(transaction=True)
class TenantSuspensionMiddlewareTest(TestCase):
    """Test TenantSuspensionMiddleware"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.middleware = TenantSuspensionMiddleware(get_response=lambda request: HttpResponse())
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

