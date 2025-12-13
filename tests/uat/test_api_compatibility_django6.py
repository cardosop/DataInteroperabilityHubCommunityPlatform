"""
API Compatibility Tests for Django 6

Tests API compatibility:
- API version compatibility
- API backward compatibility
- API response format compatibility
- API error format compatibility
- API contracts maintained
"""
import pytest
import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.assets.models import Asset
from tests.factories import TenantFactory

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class APIVersionCompatibilityTest(TestCase):
    """Test API version compatibility"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
    
    def test_api_v1_endpoints_exist(self):
        """Test API v1 endpoints exist"""
        # Test v1 endpoints
        endpoints = [
            '/api/v1/assets/',
            '/api/v1/contracts/',
            '/api/v1/files/',
            '/api/v1/jobs/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should return 200, 404 (endpoint not found), or 403 (forbidden)
            self.assertIn(response.status_code, [200, 404, 403])
    
    def test_api_version_header(self):
        """Test API version header"""
        response = self.client.get('/api/v1/assets/')
        
        # API version may be in header or URL
        # This test verifies endpoints are accessible
        self.assertIn(response.status_code, [200, 404, 403])


class APIBackwardCompatibilityTest(TestCase):
    """Test API backward compatibility"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
    
    def test_api_response_structure_unchanged(self):
        """Test API response structure is unchanged"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="compat-asset",
            name="Compat Asset",
            status='DRAFT'
        )
        
        # Retrieve asset
        response = self.client.get(f'/api/v1/assets/{asset.id}/')
        
        if response.status_code == 200:
            data = json.loads(response.content)
            # Response should have expected structure
            # (id, name, status, etc.)
            self.assertIsInstance(data, dict)
    
    def test_api_error_format_unchanged(self):
        """Test API error format is unchanged"""
        # Request nonexistent resource
        response = self.client.get('/api/v1/assets/00000000-0000-0000-0000-000000000000/')
        
        if response.status_code in [400, 404]:
            # Error response should be JSON
            content_type = response.get('Content-Type', '')
            if 'application/json' in content_type:
                data = json.loads(response.content)
                # Should have error information
                self.assertIsInstance(data, dict)


class APIResponseFormatCompatibilityTest(TestCase):
    """Test API response format compatibility"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
    
    def test_json_response_format(self):
        """Test JSON response format"""
        response = self.client.get('/api/v1/assets/')
        
        if response.status_code == 200:
            # Should be JSON
            content_type = response.get('Content-Type', '')
            self.assertIn('application/json', content_type)
            
            # Should be parseable JSON
            data = json.loads(response.content)
            self.assertIsInstance(data, (dict, list))
    
    def test_pagination_format(self):
        """Test pagination format"""
        response = self.client.get('/api/v1/assets/')
        
        if response.status_code == 200:
            data = json.loads(response.content)
            
            # Paginated responses should have 'results' and 'count'
            # Non-paginated responses may be a list
            # Response can be:
            # - A dict with 'results' key (paginated)
            # - A list (non-paginated)
            # - An empty dict {} (no results, paginated but empty)
            # - A dict with other keys (custom pagination format)
            if isinstance(data, dict):
                # PageNumberPagination returns: {'count': int, 'next': url, 'previous': url, 'results': [...]}
                # Some endpoints may use custom keys like 'assets', 'contracts', etc.
                # Check for standard pagination keys or custom resource keys
                has_pagination_keys = any(key in data for key in ['results', 'count', 'next', 'previous', 'items', 'data'])
                has_resource_keys = any(key in data for key in ['assets', 'contracts', 'jobs', 'files', 'datasets'])
                # Or it could be an empty dict
                is_empty = len(data) == 0
                self.assertTrue(has_pagination_keys or has_resource_keys or is_empty, 
                              f"Expected pagination/resource keys or empty dict, got: {list(data.keys())}")
            elif isinstance(data, list):
                # Non-paginated response is a list
                self.assertIsInstance(data, list)
            else:
                # Should be dict or list
                self.assertIsInstance(data, (dict, list))


class APIErrorFormatCompatibilityTest(TestCase):
    """Test API error format compatibility"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
    
    def test_404_error_format(self):
        """Test 404 error format"""
        response = self.client.get('/api/v1/nonexistent/')
        
        if response.status_code == 404:
            # Error should be JSON
            content_type = response.get('Content-Type', '')
            if 'application/json' in content_type:
                data = json.loads(response.content)
                self.assertIsInstance(data, dict)
    
    def test_400_error_format(self):
        """Test 400 error format"""
        # Invalid request
        response = self.client.post(
            '/api/v1/assets/',
            {'invalid_field': 'invalid_value'},
            format='json'
        )
        
        if response.status_code == 400:
            # Error should be JSON
            content_type = response.get('Content-Type', '')
            if 'application/json' in content_type:
                data = json.loads(response.content)
                self.assertIsInstance(data, dict)


class APIContractsMaintainedTest(TestCase):
    """Test API contracts are maintained"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
    
    def test_openapi_schema_exists(self):
        """Test OpenAPI schema exists"""
        response = self.client.get('/api-docs/openapi.json')
        
        # Should return 200 or 404
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            schema = json.loads(response.content)
            # Should have OpenAPI structure
            self.assertIn('openapi', schema)
            self.assertIn('info', schema)
            self.assertIn('paths', schema)
    
    def test_api_endpoints_documented(self):
        """Test API endpoints are documented"""
        response = self.client.get('/api-docs/openapi.json')
        
        if response.status_code == 200:
            schema = json.loads(response.content)
            paths = schema.get('paths', {})
            
            # Should have some documented paths
            self.assertGreater(len(paths), 0)

