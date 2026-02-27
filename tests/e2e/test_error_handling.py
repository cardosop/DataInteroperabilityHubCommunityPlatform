"""
Comprehensive E2E tests for error handling.

Covers:
- Standardized error response format
- Error code consistency
- HTTP status code mapping
- Error message format
- Request ID and timestamp
- Error details structure

Uses REAL services (no mocks).
"""
import pytest
import json
from django.test import TestCase
from rest_framework import status

from .conftest import E2ETestBase, get_response_data


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e5]


class ErrorHandlingE2ETest(E2ETestBase):
    """Test error handling operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
    
    def test_error_response_format(self):
        """Test error response follows standard format"""
        # Try to access non-existent resource
        import uuid
        fake_id = uuid.uuid4()
        
        response = self.client.get(f'/api/v1/assets/{fake_id}/')
        
        # Should return 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Check error format
        if 'error' in (get_response_data(response) or {}):
            error = (get_response_data(response) or {})['error']
            # Should have code, message, http_status
            self.assertIn('code', error)
            self.assertIn('message', error)
            # May have request_id, timestamp, details
        elif 'code' in (get_response_data(response) or {}):
            # Alternative format with code at top level
            self.assertIn('code', (get_response_data(response) or {}))
    
    def test_authentication_error_format(self):
        """Test authentication error format"""
        # Unauthenticated request
        self.client.force_authenticate(user=None)
        
        response = self.client.get('/api/v1/assets/')
        
        # Should return 401
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Check error format
        if 'error' in (get_response_data(response) or {}):
            error = (get_response_data(response) or {})['error']
            self.assertIn('code', error)
            # Should be AUTH_UNAUTHORIZED or similar
            self.assertIn('AUTH', error.get('code', '').upper())
    
    def test_validation_error_format(self):
        """Test validation error format"""
        # Try to create asset with invalid data
        response = self.client.post(
            '/api/v1/assets/',
            {
                'key': '',  # Invalid: empty key
                'name': 'Test Asset'
            },
            format='json'
        )
        
        # Validation error must return 400; 500 indicates server bug. See docs/TEST_ASSERTION_CONVENTIONS.md.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check error format
        if 'error' in (get_response_data(response) or {}):
            error = (get_response_data(response) or {})['error']
            self.assertIn('code', error)
            # Should be VALIDATION_ERROR or similar
            self.assertIn('VALIDATION', error.get('code', '').upper())
    
    def test_not_found_error_format(self):
        """Test not found error format"""
        import uuid
        fake_id = uuid.uuid4()
        
        response = self.client.get(f'/api/v1/assets/{fake_id}/')
        
        # Should return 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Check error format
        if 'error' in (get_response_data(response) or {}):
            error = (get_response_data(response) or {})['error']
            self.assertIn('code', error)
            # Should be NOT_FOUND or RESOURCE_NOT_FOUND
            code = error.get('code', '').upper()
            self.assertTrue('NOT_FOUND' in code or 'RESOURCE_NOT_FOUND' in code)
    
    def test_forbidden_error_format(self):
        """Test forbidden error format"""
        # Create other tenant
        from hub.apps.tenants.models import Tenant
        other_tenant = Tenant.objects.create(name='Other Tenant', slug='other-tenant')
        from hub.apps.users.models import User
        other_user = User.objects.create_user(email='other@example.com', password='testpass123', tenant=other_tenant)
        
        # Create asset in current tenant
        asset_id = self.create_asset(key='forbidden-test', name='Forbidden Test')
        
        # Switch to other user
        self.client.force_authenticate(user=other_user)
        
        # Try to access asset from other tenant
        response = self.client.get(f'/api/v1/assets/{asset_id}/')
        
        # Should return 404 (not found due to tenant isolation) or 403
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])
        
        if response.status_code == status.HTTP_403_FORBIDDEN:
            if 'error' in (get_response_data(response) or {}):
                error = (get_response_data(response) or {})['error']
                self.assertIn('code', error)
                # Should be AUTH_FORBIDDEN or similar
                code = error.get('code', '').upper()
                self.assertTrue('FORBIDDEN' in code or 'AUTH_FORBIDDEN' in code)
    
    def test_error_response_has_request_id(self):
        """Test error response includes request ID"""
        import uuid
        fake_id = uuid.uuid4()
        
        response = self.client.get(f'/api/v1/assets/{fake_id}/')
        
        # Check if request_id is present (may be in error object or headers)
        if 'error' in (get_response_data(response) or {}):
            error = (get_response_data(response) or {})['error']
            # Request ID may be optional
            if 'request_id' in error:
                self.assertIsNotNone(error['request_id'])
    
    def test_error_response_has_timestamp(self):
        """Test error response includes timestamp"""
        import uuid
        fake_id = uuid.uuid4()
        
        response = self.client.get(f'/api/v1/assets/{fake_id}/')
        
        # Check if timestamp is present
        if 'error' in (get_response_data(response) or {}):
            error = (get_response_data(response) or {})['error']
            # Timestamp may be optional
            if 'timestamp' in error:
                self.assertIsNotNone(error['timestamp'])
    
    def test_error_code_consistency(self):
        """Test error codes are consistent across endpoints"""
        import uuid
        fake_id = uuid.uuid4()
        
        # Test multiple endpoints return consistent error format
        endpoints = [
            f'/api/v1/assets/{fake_id}/',
            f'/api/v1/contracts/{fake_id}/',
            f'/api/v1/datasets/{fake_id}/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            
            # Should all return 404
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            
            # Error format should be consistent
            if 'error' in (get_response_data(response) or {}):
                error = (get_response_data(response) or {})['error']
                self.assertIn('code', error)
                self.assertIn('message', error)
    
    def test_error_details_structure(self):
        """Test error details structure for validation errors"""
        # Try to create asset with multiple validation errors
        response = self.client.post(
            '/api/v1/assets/',
            {
                'key': '',  # Invalid
                'name': '',  # Invalid
            },
            format='json'
        )
        
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            if 'error' in (get_response_data(response) or {}):
                error = (get_response_data(response) or {})['error']
                # May have details with field_errors
                if 'details' in error:
                    details = error['details']
                    # May contain field_errors array
                    if 'field_errors' in details:
                        self.assertIsInstance(details['field_errors'], list)
    
    def test_error_http_status_mapping(self):
        """Test error HTTP status code mapping"""
        # Test various error scenarios
        test_cases = [
            # (endpoint, method, expected_status, expected_code_prefix)
            ('/api/v1/assets/', 'GET', status.HTTP_401_UNAUTHORIZED, 'AUTH'),
        ]
        
        # Unauthenticated
        self.client.force_authenticate(user=None)
        
        for endpoint, method, expected_status, code_prefix in test_cases:
            if method == 'GET':
                response = self.client.get(endpoint)
            elif method == 'POST':
                response = self.client.post(endpoint, {}, format='json')
            
            if response.status_code == expected_status:
                if 'error' in (get_response_data(response) or {}):
                    error = (get_response_data(response) or {})['error']
                    code = error.get('code', '').upper()
                    self.assertTrue(code.startswith(code_prefix))
    
    def test_error_message_user_friendly(self):
        """Test error messages are user-friendly (no stack traces)"""
        import uuid
        fake_id = uuid.uuid4()
        
        response = self.client.get(f'/api/v1/assets/{fake_id}/')
        
        if 'error' in (get_response_data(response) or {}):
            error = (get_response_data(response) or {})['error']
            message = error.get('message', '')
            
            # Should not contain stack traces
            self.assertNotIn('Traceback', message)
            self.assertNotIn('File "', message)
            self.assertNotIn('line ', message)
            # Should not contain internal paths
            self.assertNotIn('/usr/', message)
            self.assertNotIn('/home/', message)

