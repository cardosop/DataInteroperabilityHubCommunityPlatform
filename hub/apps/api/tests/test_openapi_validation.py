"""
Tests for OpenAPI schema validation.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
import json

from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant, KYCStatus

User = get_user_model()


class OpenAPIValidationTest(TestCase):
    """Test OpenAPI schema generation and validation"""
    
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
    
    def test_openapi_schema_structure(self):
        """Test that OpenAPI schema has correct structure"""
        response = self.client.get('/api-docs/openapi.json')
        
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        
        # Check required OpenAPI 3.0 fields
        self.assertIn('openapi', schema)
        self.assertIn('info', schema)
        self.assertIn('paths', schema)
        self.assertIn('components', schema)
        
        # Check OpenAPI version
        self.assertTrue(schema['openapi'].startswith('3.'))
    
    def test_openapi_info_section(self):
        """Test that OpenAPI info section is correct"""
        response = self.client.get('/api-docs/openapi.json')
        schema = response.json()
        
        info = schema['info']
        self.assertIn('title', info)
        self.assertIn('version', info)
        self.assertIn('description', info)
        self.assertEqual(info['version'], '1.0.0')
    
    def test_openapi_paths_exist(self):
        """Test that major API paths are included in schema"""
        response = self.client.get('/api-docs/openapi.json')
        schema = response.json()
        
        paths = list(schema['paths'].keys())
        
        # Check that major endpoint prefixes are present (drf-spectacular generates specific paths)
        # e.g., /api/v1/auth/login/, /api/v1/tenants/tenants/, etc.
        path_prefixes = [
            '/api/v1/auth',
            '/api/v1/tenants',
            '/api/v1/users',
            '/api/v1/assets',
            '/api/v1/contracts',
            '/api/v1/files',
            '/api/v1/jobs',
            '/api/v1/marketplace',
        ]
        
        for prefix in path_prefixes:
            # Check if any path starts with this prefix
            matching_paths = [p for p in paths if p.startswith(prefix)]
            self.assertGreater(len(matching_paths), 0, 
                             f"No paths found starting with {prefix}. Available paths: {paths[:10]}")
    
    def test_openapi_components_schemas(self):
        """Test that component schemas are defined"""
        response = self.client.get('/api-docs/openapi.json')
        schema = response.json()
        
        components = schema.get('components', {})
        schemas = components.get('schemas', {})
        
        # Check that common schemas exist
        self.assertIn('Error', schemas)
    
    def test_openapi_security_schemes(self):
        """Test that security schemes are defined"""
        response = self.client.get('/api-docs/openapi.json')
        schema = response.json()
        
        components = schema.get('components', {})
        security_schemes = components.get('securitySchemes', {})
        
        # Check that authentication schemes are defined
        self.assertIn('BearerAuth', security_schemes)
    
    def test_openapi_operation_descriptions(self):
        """Test that operations have descriptions"""
        response = self.client.get('/api-docs/openapi.json')
        schema = response.json()
        
        # Check a sample path
        if '/api/v1/assets/' in schema['paths']:
            asset_path = schema['paths']['/api/v1/assets/']
            if 'get' in asset_path:
                self.assertIn('summary', asset_path['get'])
                self.assertIn('description', asset_path['get'])
    
    def test_openapi_response_schemas(self):
        """Test that responses have schemas defined"""
        response = self.client.get('/api-docs/openapi.json')
        schema = response.json()
        
        # Check a sample path
        if '/api/v1/assets/' in schema['paths']:
            asset_path = schema['paths']['/api/v1/assets/']
            if 'get' in asset_path:
                responses = asset_path['get'].get('responses', {})
                if '200' in responses:
                    self.assertIn('content', responses['200'])
    
    def test_openapi_error_responses(self):
        """Test that error responses are documented"""
        response = self.client.get('/api-docs/openapi.json')
        schema = response.json()
        
        # Check a sample path
        if '/api/v1/assets/' in schema['paths']:
            asset_path = schema['paths']['/api/v1/assets/']
            if 'get' in asset_path:
                responses = asset_path['get'].get('responses', {})
                # Should have 401, 403, 404, etc.
                self.assertIn('401', responses)
                self.assertIn('403', responses)
    
    def test_openapi_schema_valid_json(self):
        """Test that OpenAPI schema is valid JSON"""
        response = self.client.get('/api-docs/openapi.json')
        
        self.assertEqual(response.status_code, 200)
        
        # Should be able to parse as JSON
        try:
            schema = json.loads(response.content)
            self.assertIsInstance(schema, dict)
        except json.JSONDecodeError:
            self.fail("OpenAPI schema is not valid JSON")
    
    def test_openapi_schema_contains_tags(self):
        """Test that OpenAPI schema contains tags"""
        response = self.client.get('/api-docs/openapi.json')
        schema = response.json()
        
        # Check that tags are defined
        self.assertIn('tags', schema)
        self.assertIsInstance(schema['tags'], list)
        self.assertGreater(len(schema['tags']), 0)

