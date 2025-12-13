"""
Unit tests for Scheduled Ingestion API views

Tests for CRUD operations, run history, and manual trigger endpoints.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionStatus,
    ScheduledIngestionRunStatus,
    SourceType
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract


pytestmark = pytest.mark.django_db(transaction=True)


class ScheduledIngestionViewSetTest(TestCase):
    """Test ScheduledIngestionViewSet"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_create_scheduled_ingestion(self):
        """Test creating a scheduled ingestion"""
        data = {
            "name": "Daily Sales Ingestion",
            "description": "Ingests daily sales CSV files",
            "source_type": "S3",
            "source_config": {
                "bucket": "my-data-lake",
                "prefix": "sales/daily/",
                "access_key_id": "AKIA...",
                "secret_access_key": "abc..."
            },
            "schedule": "0 2 * * *",
            "file_pattern": "sales_\\d{4}-\\d{2}-\\d{2}\\.csv",
            "auto_create_asset": True,
            "auto_activate": True,
            "status": "ACTIVE"
        }
        
        with patch('hub.apps.scheduled_ingestion.views.DeploymentSyncService') as mock_sync:
            # Mock Prefect deployment creation
            mock_deployment = MagicMock()
            mock_deployment.id = uuid.uuid4()
            mock_sync.return_value.create_or_update_deployment.return_value = mock_deployment
            
            response = self.client.post(
                '/api/v1/scheduled-ingestions/',
                data,
                format='json'
            )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "Daily Sales Ingestion")
        self.assertEqual(response.data['source_type'], "S3")
        self.assertIn('id', response.data)
        
        # Verify scheduled ingestion created
        ingestion = ScheduledIngestion.objects.get(id=response.data['id'])
        self.assertEqual(ingestion.tenant, self.tenant)
        self.assertEqual(ingestion.created_by, self.user)
    
    def test_create_scheduled_ingestion_invalid_cron(self):
        """Test creating scheduled ingestion with invalid cron expression"""
        data = {
            "name": "Test Ingestion",
            "source_type": "S3",
            "source_config": {"bucket": "test-bucket"},
            "schedule": "invalid cron"
        }
        
        response = self.client.post(
            '/api/v1/scheduled-ingestions/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('schedule', response.data)
    
    def test_create_scheduled_ingestion_invalid_regex(self):
        """Test creating scheduled ingestion with invalid regex pattern"""
        data = {
            "name": "Test Ingestion",
            "source_type": "S3",
            "source_config": {"bucket": "test-bucket"},
            "schedule": "0 0 * * *",
            "file_pattern": "[invalid regex"
        }
        
        response = self.client.post(
            '/api/v1/scheduled-ingestions/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file_pattern', response.data)
    
    def test_list_scheduled_ingestions(self):
        """Test listing scheduled ingestions"""
        # Create test ingestions
        ingestion1 = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Ingestion 1",
            source_type=SourceType.S3,
            source_config={"bucket": "bucket1"},
            schedule="0 0 * * *",
            created_by=self.user
        )
        
        ingestion2 = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Ingestion 2",
            source_type=SourceType.GCS,
            source_config={"bucket": "bucket2"},
            schedule="0 1 * * *",
            created_by=self.user
        )
        
        response = self.client.get('/api/v1/scheduled-ingestions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        names = [item['name'] for item in response.data]
        self.assertIn("Ingestion 1", names)
        self.assertIn("Ingestion 2", names)
    
    def test_retrieve_scheduled_ingestion(self):
        """Test retrieving a scheduled ingestion"""
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule="0 0 * * *",
            created_by=self.user
        )
        
        response = self.client.get(f'/api/v1/scheduled-ingestions/{ingestion.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Test Ingestion")
        self.assertEqual(response.data['id'], str(ingestion.id))
    
    def test_update_scheduled_ingestion(self):
        """Test updating a scheduled ingestion"""
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule="0 0 * * *",
            created_by=self.user
        )
        
        data = {
            "description": "Updated description",
            "schedule": "0 3 * * *"
        }
        
        with patch('hub.apps.scheduled_ingestion.views.DeploymentSyncService') as mock_sync:
            # Mock Prefect deployment update
            mock_deployment = MagicMock()
            mock_deployment.id = ingestion.prefect_deployment_id or uuid.uuid4()
            mock_sync.return_value.create_or_update_deployment.return_value = mock_deployment
            
            response = self.client.patch(
                f'/api/v1/scheduled-ingestions/{ingestion.id}/',
                data,
                format='json'
            )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], "Updated description")
        self.assertEqual(response.data['schedule'], "0 3 * * *")
        
        # Verify updated in database
        ingestion.refresh_from_db()
        self.assertEqual(ingestion.description, "Updated description")
        self.assertEqual(ingestion.schedule, "0 3 * * *")
    
    def test_delete_scheduled_ingestion(self):
        """Test deleting a scheduled ingestion"""
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule="0 0 * * *",
            prefect_deployment_id=uuid.uuid4(),
            created_by=self.user
        )
        
        with patch('hub.apps.scheduled_ingestion.views.DeploymentSyncService') as mock_sync:
            # Mock Prefect deployment deletion
            mock_sync.return_value.delete_deployment.return_value = None
            
            response = self.client.delete(f'/api/v1/scheduled-ingestions/{ingestion.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deleted
        self.assertFalse(ScheduledIngestion.objects.filter(id=ingestion.id).exists())
    
    def test_list_runs(self):
        """Test listing runs for a scheduled ingestion"""
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule="0 0 * * *",
            created_by=self.user
        )
        
        # Create test runs
        run1 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now() - timedelta(hours=1)
        )
        
        run2 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=ingestion,
            status=ScheduledIngestionRunStatus.FAILED,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now(),
            error_message="Processing failed"
        )
        
        response = self.client.get(f'/api/v1/scheduled-ingestions/{ingestion.id}/runs/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        statuses = [item['status'] for item in response.data]
        self.assertIn("COMPLETED", statuses)
        self.assertIn("FAILED", statuses)
    
    def test_retrieve_run(self):
        """Test retrieving a specific run"""
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule="0 0 * * *",
            created_by=self.user
        )
        
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now(),
            details_json={"files_processed": 5, "datasets_created": 5}
        )
        
        response = self.client.get(
            f'/api/v1/scheduled-ingestions/{ingestion.id}/runs/{run.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], "COMPLETED")
        self.assertEqual(response.data['id'], str(run.id))
        self.assertEqual(response.data['details_json']['files_processed'], 5)
    
    @patch('hub.apps.scheduled_ingestion.views.run_deployment')
    @patch('hub.apps.scheduled_ingestion.views.get_client')
    @patch('hub.apps.scheduled_ingestion.views.create_job')
    def test_trigger_ingestion(self, mock_create_job, mock_get_client, mock_run_deployment):
        """Test manually triggering a scheduled ingestion"""
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule="0 0 * * *",
            prefect_deployment_id=uuid.uuid4(),
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user
        )
        
        # Mock Prefect flow run
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid.uuid4()
        mock_run_deployment.return_value = mock_flow_run
        
        # Mock job creation
        from hub.apps.jobs.models import Job
        mock_job = Job.objects.create(
            tenant=self.tenant,
            type="SCHEDULED_INGESTION",
            status="PENDING",
            resource_type="SCHEDULED_INGESTION",
            resource_id=str(ingestion.id),
            created_by=self.user
        )
        mock_create_job.return_value = mock_job
        
        response = self.client.post(
            f'/api/v1/scheduled-ingestions/{ingestion.id}/trigger/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('job_id', response.data)
        self.assertIn('scheduled_ingestion_run_id', response.data)
        
        # Verify run created
        run = ScheduledIngestionRun.objects.get(
            scheduled_ingestion=ingestion,
            prefect_flow_run_id=mock_flow_run.id
        )
        self.assertEqual(run.status, ScheduledIngestionRunStatus.PENDING)
    
    def test_trigger_ingestion_not_active(self):
        """Test triggering a non-active scheduled ingestion"""
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule="0 0 * * *",
            status=ScheduledIngestionStatus.PAUSED,
            created_by=self.user
        )
        
        response = self.client.post(
            f'/api/v1/scheduled-ingestions/{ingestion.id}/trigger/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not active", response.data['detail'].lower())
    
    def test_tenant_isolation(self):
        """Test that tenants can only see their own scheduled ingestions"""
        # Create another tenant
        tenant2 = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create ingestion for tenant2
        ingestion2 = ScheduledIngestion.objects.create(
            tenant=tenant2,
            name="Other Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "other-bucket"},
            schedule="0 0 * * *",
            created_by=self.user
        )
        
        # List ingestions - should only see own tenant's
        response = self.client.get('/api/v1/scheduled-ingestions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ingestion_ids = [item['id'] for item in response.data]
        self.assertNotIn(str(ingestion2.id), ingestion_ids)

