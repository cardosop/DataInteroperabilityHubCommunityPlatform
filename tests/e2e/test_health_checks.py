"""
E2E tests for health check endpoints.
"""
import pytest
import requests
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from tests.e2e.conftest import E2ETestBase


class HealthCheckE2ETest(E2ETestBase):
    """E2E tests for health check endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.client = APIClient()
    
    def test_health_check_endpoint(self):
        """Test the main health check endpoint."""
        response = self.client.get('/health/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.json())
        self.assertIn('database', response.json())
        self.assertIn('redis', response.json())
        
        data = response.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['database'], 'connected')
        self.assertEqual(data['redis'], 'connected')
    
    def test_health_check_returns_json(self):
        """Test that health check returns JSON."""
        response = self.client.get('/health/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_semantic_service_health(self):
        """Test semantic service health endpoint."""
        import os
        semantic_url = os.environ.get('SEMANTIC_SERVICE_URL', 'http://localhost:8081')
        
        try:
            response = requests.get(f'{semantic_url}/health', timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
            self.assertIn('fuseki', data)
            self.assertEqual(data['fuseki'], 'connected')
        except requests.exceptions.RequestException:
            pytest.skip("Semantic service not available")
    
    def test_datacontract_service_health(self):
        """Test DataContract service health endpoint."""
        import os
        datacontract_url = os.environ.get('DATACONTRACT_SERVICE_URL', 'http://localhost:8080')
        
        try:
            response = requests.get(f'{datacontract_url}/health', timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
        except requests.exceptions.RequestException:
            pytest.skip("DataContract service not available")
    
    def test_compliance_service_health(self):
        """Test compliance service health endpoint."""
        import os
        compliance_url = os.environ.get('COMPLIANCE_SERVICE_URL', 'http://localhost:8082')
        
        try:
            response = requests.get(f'{compliance_url}/health', timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
        except requests.exceptions.RequestException:
            pytest.skip("Compliance service not available")
    
    def test_dq_service_health(self):
        """Test DQ service health endpoint."""
        import os
        dq_url = os.environ.get('DQ_SERVICE_URL', 'http://localhost:8083')
        
        try:
            response = requests.get(f'{dq_url}/health', timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
        except requests.exceptions.RequestException:
            pytest.skip("DQ service not available")

