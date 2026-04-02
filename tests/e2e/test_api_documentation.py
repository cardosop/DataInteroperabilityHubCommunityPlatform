"""
E2E tests for API documentation endpoints.
"""
import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from tests.e2e.conftest import E2ETestBase
pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e_batch1]



class APIDocumentationE2ETest(E2ETestBase):
    """E2E tests for API documentation endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.client = APIClient()

    def test_openapi_schema_endpoint(self):
        """Test OpenAPI schema endpoint."""
        response = self.client.get('/api-docs/openapi.json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # OpenAPI schema endpoint returns JSON content type
        # It may be 'application/json' or 'application/vnd.oai.openapi+json'
        content_type = response['Content-Type'].lower()
        self.assertTrue(
            'json' in content_type or 'openapi' in content_type,
            f"Expected JSON or OpenAPI content type, got: {content_type}"
        )

        data = response.json()
        self.assertIn('openapi', data)
        self.assertIn('info', data)
        self.assertIn('paths', data)
        self.assertIn('components', data)

        # Verify API info
        self.assertEqual(data['info']['title'], 'Interoperable Data Hub API')
        self.assertIn('version', data['info'])

    def test_swagger_ui_endpoint(self):
        """Test Swagger UI endpoint."""
        response = self.client.get('/api-docs/')

        # Swagger UI returns HTML
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/html', response['Content-Type'])
        self.assertIn(b'Swagger', response.content)

    def test_redoc_endpoint(self):
        """Test ReDoc endpoint."""
        response = self.client.get('/api-docs/redoc/')

        # ReDoc returns HTML
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/html', response['Content-Type'])
        # ReDoc uses <redoc> tag, not "ReDoc" text
        self.assertIn(b'<redoc', response.content)

    def test_api_info_endpoint(self):
        """Test API info endpoint."""
        response = self.client.get('/api/v1/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn('name', data)
        self.assertIn('version', data)
        self.assertIn('base_url', data)
        self.assertIn('documentation', data)
        self.assertIn('endpoints', data)

        # Verify endpoints are listed
        endpoints = data['endpoints']
        self.assertIn('auth', endpoints)
        self.assertIn('tenants', endpoints)
        self.assertIn('users', endpoints)
        self.assertIn('assets', endpoints)
        self.assertIn('contracts', endpoints)
        self.assertIn('marketplace', endpoints)

    def test_openapi_schema_includes_all_endpoints(self):
        """Test that OpenAPI schema includes all major endpoints."""
        response = self.client.get('/api-docs/openapi.json')
        data = response.json()

        paths = data.get('paths', {})

        # Verify major endpoints are present (check for actual path patterns)
        # Paths may be nested, so check for any path containing the key
        path_keys = list(paths.keys())
        self.assertTrue(any('/auth/login' in key for key in path_keys), f"Auth login not found in {path_keys[:5]}")
        self.assertTrue(any('/tenants' in key for key in path_keys), f"Tenants not found in {path_keys[:5]}")
        self.assertTrue(any('/users' in key for key in path_keys), f"Users not found in {path_keys[:5]}")
        self.assertTrue(any('/assets' in key for key in path_keys), f"Assets not found in {path_keys[:5]}")
        self.assertTrue(any('/contracts' in key for key in path_keys), f"Contracts not found in {path_keys[:5]}")
        self.assertTrue(any('/marketplace/listings' in key for key in path_keys), f"Marketplace listings not found in {path_keys[:5]}")

        # Verify each found path has at least one HTTP method documented
        http_methods = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}
        undocumented_paths = []
        for path_key, path_spec in paths.items():
            if not isinstance(path_spec, dict):
                continue
            documented_methods = [m for m in path_spec if m.lower() in http_methods]
            if not documented_methods:
                undocumented_paths.append(path_key)
        self.assertEqual(
            undocumented_paths, [],
            f"Paths with no HTTP methods documented: {undocumented_paths}",
        )

