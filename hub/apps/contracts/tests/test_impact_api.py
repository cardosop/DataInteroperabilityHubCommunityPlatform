"""
Integration tests for Impact Analysis API

Tests for impact analysis API endpoints.
"""
import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import Contract
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class ImpactAPITest(TestCase):
    """Test Impact Analysis API"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            name="Test Contract",
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract", "info": {"name": "Test Contract"}}',
            hub_contract_json={
                "info": {
                    "name": "Test Contract",
                    "title": "Test Contract"
                }
            },
            created_by=self.user
        )
        
        # Authenticate
        self.client.force_authenticate(user=self.user)
    
    def test_impact_analysis_endpoint(self):
        """Test impact analysis endpoint"""
        url = reverse('contract-impact-analysis', kwargs={'pk': self.contract.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nodes", response.data)
        self.assertIn("links", response.data)
        self.assertIn("summary", response.data)
    
    def test_impact_analysis_with_depth(self):
        """Test impact analysis with depth parameter"""
        url = reverse('contract-impact-analysis', kwargs={'pk': self.contract.id})
        response = self.client.get(url, {'depth': 5})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_impact_analysis_csv_format(self):
        """Test impact analysis CSV format"""
        url = reverse('contract-impact-analysis', kwargs={'pk': self.contract.id})
        response = self.client.get(url, {'format': 'csv'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['content-type'], 'text/csv')
    
    def test_impact_analysis_dot_format(self):
        """Test impact analysis DOT format"""
        url = reverse('contract-impact-analysis', kwargs={'pk': self.contract.id})
        response = self.client.get(url, {'format': 'dot'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['content-type'], 'text/plain')
        self.assertIn("digraph ImpactAnalysis", response.content.decode())
    
    def test_impact_analysis_mermaid_format(self):
        """Test impact analysis Mermaid format"""
        url = reverse('contract-impact-analysis', kwargs={'pk': self.contract.id})
        response = self.client.get(url, {'format': 'mermaid'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['content-type'], 'text/plain')
        self.assertIn("graph LR", response.content.decode())
    
    def test_impact_analysis_paths_format(self):
        """Test impact analysis paths format"""
        url = reverse('contract-impact-analysis', kwargs={'pk': self.contract.id})
        response = self.client.get(url, {'format': 'paths'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("paths", response.data)
        self.assertIn("total_paths", response.data)

