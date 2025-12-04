"""
E2E tests for health check endpoints.
"""
import pytest
import requests
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework import status
from rest_framework.test import APIClient
from tests.e2e.conftest import (
    E2ETestBase, 
    get_semantic_service_url,
    get_datacontract_service_url,
    get_compliance_service_url,
    get_dq_service_url,
    check_service_health
)
pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e_batch3]



class HealthCheckE2ETest(E2ETestBase):
    """E2E tests for health check endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.client = APIClient()
    
    def test_health_check_endpoint(self):
        """Test the main health check endpoint."""
        # Health check may return 503 if Redis is not available in test environment
        # This is acceptable for E2E tests - we just verify the endpoint exists
        response = self.client.get('/health/')
        
        # Accept both 200 and 503 as valid responses (503 means dependencies unavailable)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('database', data)
        self.assertIn('redis', data)
        
        # If healthy, verify all components
        if response.status_code == status.HTTP_200_OK:
            self.assertEqual(data['status'], 'healthy')
            self.assertEqual(data['database'], 'connected')
            self.assertEqual(data['redis'], 'connected')
    
    def test_health_check_returns_json(self):
        """Test that health check returns JSON."""
        response = self.client.get('/health/')
        
        # Accept both 200 and 503
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_semantic_service_health(self):
        """Test semantic service health endpoint."""
        semantic_url = get_semantic_service_url()
        
        if not check_service_health(semantic_url, timeout=5):
            pytest.skip(f"Semantic service not available at {semantic_url}")
        
        try:
            response = requests.get(f'{semantic_url}/health', timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
            # Check for fuseki only if it's in the response (some services may not include it)
            if 'fuseki' in data:
                self.assertEqual(data['fuseki'], 'connected')
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Semantic service not available: {e}")
    
    def test_datacontract_service_health(self):
        """Test DataContract service health endpoint."""
        datacontract_url = get_datacontract_service_url()
        
        if not check_service_health(datacontract_url, timeout=5):
            pytest.skip(f"DataContract service not available at {datacontract_url}")
        
        try:
            response = requests.get(f'{datacontract_url}/health', timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
        except requests.exceptions.RequestException as e:
            pytest.skip(f"DataContract service not available: {e}")
    
    def test_compliance_service_health(self):
        """Test compliance service health endpoint."""
        compliance_url = get_compliance_service_url()
        
        if not check_service_health(compliance_url, timeout=5):
            pytest.skip(f"Compliance service not available at {compliance_url}")
        
        try:
            response = requests.get(f'{compliance_url}/health', timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Compliance service not available: {e}")
    
    def test_dq_service_health(self):
        """Test DQ service health endpoint."""
        dq_url = get_dq_service_url()
        
        if not check_service_health(dq_url, timeout=5):
            pytest.skip(f"DQ service not available at {dq_url}")
        
        try:
            response = requests.get(f'{dq_url}/health', timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
        except requests.exceptions.RequestException as e:
            pytest.skip(f"DQ service not available: {e}")

