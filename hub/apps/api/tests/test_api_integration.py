"""
Integration tests for REST API endpoints.

Tests cover all major API endpoints to ensure they work correctly.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant, KYCStatus

User = get_user_model()


class APIIntegrationTest(TestCase):
    """Integration tests for REST API"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_api_info_endpoint(self):
        """Test API info endpoint"""
        response = self.client.get('/api/v1/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('name', response.data)
        self.assertIn('version', response.data)
        self.assertIn('endpoints', response.data)
    
    def test_openapi_schema_endpoint(self):
        """Test OpenAPI schema endpoint"""
        response = self.client.get('/api-docs/openapi.json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('openapi', response.data)
        self.assertIn('info', response.data)
        self.assertIn('paths', response.data)
    
    def test_swagger_ui_endpoint(self):
        """Test Swagger UI endpoint"""
        response = self.client.get('/api-docs/')
        
        # Should return HTML
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/html', response['Content-Type'])
    
    def test_redoc_endpoint(self):
        """Test ReDoc endpoint"""
        response = self.client.get('/api-docs/redoc/')
        
        # Should return HTML
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/html', response['Content-Type'])
    
    def test_error_response_format(self):
        """Test that error responses follow standardized format"""
        # Make request to non-existent endpoint
        response = self.client.get('/api/v1/nonexistent/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertIn('code', response.data['error'])
        self.assertIn('message', response.data['error'])
        self.assertIn('http_status', response.data['error'])
        self.assertIn('request_id', response.data['error'])
        self.assertIn('timestamp', response.data['error'])
    
    def test_request_id_header(self):
        """Test that request ID is included in response headers"""
        response = self.client.get('/api/v1/')
        
        self.assertIn('X-Request-ID', response)
        self.assertIsNotNone(response['X-Request-ID'])
    
    def test_rate_limit_headers(self):
        """Test that rate limit headers are included"""
        response = self.client.get('/api/v1/')
        
        # Rate limit headers should be present
        self.assertIn('X-RateLimit-Limit', response)
        self.assertIn('X-RateLimit-Remaining', response)
    
    def test_authentication_required(self):
        """Test that authentication is required for protected endpoints"""
        # Create unauthenticated client
        client = APIClient()
        
        # Try to access protected endpoint
        response = client.get('/api/v1/assets/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'AUTH_UNAUTHORIZED')

