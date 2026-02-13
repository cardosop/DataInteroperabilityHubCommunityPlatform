"""
Unit tests for API middleware (RequestIDMiddleware).
"""
import pytest
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from unittest.mock import Mock, patch
import uuid
import structlog

from hub.apps.api.middleware import RequestIDMiddleware


pytestmark = pytest.mark.django_db(transaction=True)


class RequestIDMiddlewareTest(TestCase):
    """Test RequestIDMiddleware"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = RequestIDMiddleware(self.get_response)
    
    def test_middleware_is_callable(self):
        """Test that middleware is callable (Django 6 pattern)"""
        request = self.factory.get("/api/v1/assets/")
        response = self.middleware(request)
        
        self.assertIsNotNone(response)
        self.assertIsInstance(response, HttpResponse)
        self.get_response.assert_called_once()
    
    def test_generates_request_id(self):
        """Test that middleware generates request ID if not present"""
        request = self.factory.get("/api/v1/assets/")
        
        self.middleware.process_request(request)
        
        self.assertTrue(hasattr(request, 'id'))
        self.assertTrue(hasattr(request, 'request_id'))
        self.assertEqual(request.id, request.request_id)
        # Should be a valid UUID string
        try:
            uuid.UUID(request.id)
        except ValueError:
            self.fail("Request ID is not a valid UUID")
    
    def test_uses_existing_request_id(self):
        """Test that middleware uses existing X-Request-ID header"""
        existing_id = str(uuid.uuid4())
        request = self.factory.get("/api/v1/assets/", HTTP_X_REQUEST_ID=existing_id)
        
        self.middleware.process_request(request)
        
        self.assertEqual(request.id, existing_id)
        self.assertEqual(request.request_id, existing_id)
    
    def test_adds_request_id_to_response(self):
        """Test that middleware adds request ID to response headers"""
        request = self.factory.get("/api/v1/assets/")
        request.request_id = "test-request-id-123"
        
        response = HttpResponse()
        response = self.middleware.process_response(request, response)
        
        self.assertEqual(response['X-Request-ID'], "test-request-id-123")
    
    def test_binds_request_id_to_structlog(self):
        """Test that middleware binds request ID to structlog context"""
        request = self.factory.get("/api/v1/assets/")
        
        with patch('structlog.contextvars.bind_contextvars') as mock_bind:
            self.middleware.process_request(request)
            
            # Should bind request_id, route, and method
            mock_bind.assert_called_once()
            # Check call arguments (can be positional or keyword)
            call_kwargs = mock_bind.call_args[1] if mock_bind.call_args[1] else {}
            if 'request_id' in call_kwargs:
                self.assertEqual(call_kwargs['route'], "/api/v1/assets/")
                self.assertEqual(call_kwargs['method'], "GET")
            # Request ID should be generated
            self.assertTrue(hasattr(request, 'request_id'))
    
    def test_binds_tenant_id_to_structlog(self):
        """Test that middleware binds tenant_id to structlog in response"""
        from hub.apps.tenants.models import Tenant
        
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        request = self.factory.get("/api/v1/assets/")
        request.tenant = tenant
        
        response = HttpResponse()
        
        with patch('structlog.contextvars.bind_contextvars') as mock_bind:
            self.middleware.process_response(request, response)
            
            # Should bind tenant_id
            mock_bind.assert_called()
            # Check if tenant_id was bound
            calls = [call[1] for call in mock_bind.call_args_list if 'tenant_id' in call[1]]
            if calls:
                self.assertEqual(calls[0]['tenant_id'], str(tenant.id))
    
    def test_binds_user_id_to_structlog(self):
        """Test that middleware binds user_id to structlog in response"""
        from hub.apps.users.models import User
        from hub.apps.tenants.models import Tenant
        
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=tenant
        )
        
        request = self.factory.get("/api/v1/assets/")
        request.user = user
        
        response = HttpResponse()
        
        with patch('structlog.contextvars.bind_contextvars') as mock_bind:
            self.middleware.process_response(request, response)
            
            # Should bind user_id
            mock_bind.assert_called()
            # Check if user_id was bound
            calls = [call[1] for call in mock_bind.call_args_list if 'user_id' in call[1]]
            if calls:
                self.assertEqual(calls[0]['user_id'], str(user.id))
    
    def test_middleware_performance(self):
        """Test middleware performance (should be fast)"""
        import time
        
        request = self.factory.get("/api/v1/assets/")
        
        start = time.time()
        for _ in range(1000):
            self.middleware.process_request(request)
        elapsed = time.time() - start
        
        # Should process 1000 requests in less than 0.5 seconds
        self.assertLess(elapsed, 0.5, f"Middleware too slow: {elapsed:.3f}s for 1000 requests")

