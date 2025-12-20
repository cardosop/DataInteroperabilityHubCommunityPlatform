"""
Comprehensive tests for scheduled ingestion credential endpoints.

Tests cover:
- GET /api/v1/scheduled-ingestions/{id}/credentials/ - Get masked credentials
- POST /api/v1/scheduled-ingestions/{id}/credentials/test/ - Test connection
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from hub.apps.scheduled_ingestion.models import ScheduledIngestion, ScheduledIngestionStatus, SourceType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, Role, UserRole

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class CredentialsEndpointTest(TestCase):
    """Test credentials endpoint"""
    
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
        
        # Create DATA_PROVIDER role (must belong to tenant)
        self.data_provider_role = Role.objects.create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            description="Data Provider Role"
        )
        UserRole.objects.create(user=self.user, role=self.data_provider_role)
        
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            description="Test scheduled ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": "test-bucket",
                "prefix": "data/",
                "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            },
            schedule="0 0 * * *",
            file_pattern=".*\\.csv",
            auto_create_asset=True,
            auto_activate=True,
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_credentials_success(self):
        """Test getting masked credentials"""
        response = self.client.get(f'/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('scheduled_ingestion_id', response.data)
        self.assertIn('source_type', response.data)
        self.assertIn('masked_credentials', response.data)
        self.assertIn('metadata', response.data)
        
        # Verify credentials are masked
        masked_creds = response.data['masked_credentials']
        self.assertIn('secret_access_key', masked_creds)
        self.assertIn('access_key_id', masked_creds)
        # Verify actual secret is not exposed
        self.assertNotIn('wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY', masked_creds['secret_access_key'])
        self.assertTrue('***' in masked_creds['secret_access_key'] or '****' in masked_creds['secret_access_key'])
    
    def test_get_credentials_unauthorized(self):
        """Test getting credentials without authentication"""
        self.client.logout()
        response = self.client.get(f'/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_credentials_forbidden(self):
        """Test getting credentials for another tenant's ingestion"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE"
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        
        self.client.force_authenticate(user=other_user)
        response = self.client.get(f'/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_get_credentials_not_found(self):
        """Test getting credentials for non-existent ingestion"""
        import uuid
        fake_id = uuid.uuid4()
        response = self.client.get(f'/api/v1/scheduled-ingestions/{fake_id}/credentials/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('hub.apps.scheduled_ingestion.views.SourceConnectorFactory')
    def test_test_credentials_success(self, mock_factory):
        """Test successful connection test"""
        # Mock connector
        mock_connector = MagicMock()
        mock_connector.test_connection.return_value = True
        mock_factory.get_connector.return_value = mock_connector
        
        response = self.client.post(f'/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)
        self.assertTrue(response.data['success'])
        self.assertIn('message', response.data)
        self.assertIn('tested_at', response.data)
        self.assertIn('connection_details', response.data)
    
    @patch('hub.apps.scheduled_ingestion.views.SourceConnectorFactory')
    def test_test_credentials_failure(self, mock_factory):
        """Test failed connection test"""
        # Mock connector
        mock_connector = MagicMock()
        mock_connector.test_connection.return_value = False
        mock_factory.get_connector.return_value = mock_connector
        
        response = self.client.post(f'/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)
        self.assertFalse(response.data['success'])
        self.assertIn('message', response.data)
    
    def test_test_credentials_unauthorized(self):
        """Test testing credentials without authentication"""
        self.client.logout()
        response = self.client.post(f'/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_test_credentials_forbidden(self):
        """Test testing credentials for another tenant's ingestion"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE"
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        
        self.client.force_authenticate(user=other_user)
        response = self.client.post(f'/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    @patch('hub.apps.scheduled_ingestion.views.SourceConnectorFactory')
    def test_test_credentials_connector_unavailable(self, mock_factory):
        """Test connection test when connector service is unavailable"""
        mock_factory.side_effect = ImportError("Connector service not available")
        
        response = self.client.post(f'/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/')
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('error', response.data or {})
    
    def test_credentials_masking_different_source_types(self):
        """Test credential masking for different source types"""
        # Test GCS
        gcs_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="GCS Ingestion",
            source_type=SourceType.GCS,
            source_config={
                "bucket": "test-bucket",
                "credentials_json": '{"private_key": "secret-key-12345"}',
                "private_key": "very-secret-key"
            },
            schedule="0 0 * * *",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user
        )
        
        response = self.client.get(f'/api/v1/scheduled-ingestions/{gcs_ingestion.id}/credentials/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        masked_creds = response.data['masked_credentials']
        # Verify sensitive fields are masked
        if 'private_key' in masked_creds:
            self.assertTrue('***' in masked_creds['private_key'] or '****' in masked_creds['private_key'])

