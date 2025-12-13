"""
E2E tests for Scheduled Ingestion

End-to-end tests for complete scheduled ingestion workflows.
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
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File


pytestmark = pytest.mark.django_db(transaction=True)


class ScheduledIngestionE2ETest(TestCase):
    """E2E tests for scheduled ingestion"""
    
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
    
    @patch('hub.apps.scheduled_ingestion.views.DeploymentSyncService')
    @patch('hub.apps.scheduled_ingestion.ingestion.SourceConnectorFactory')
    @patch('hub.apps.scheduled_ingestion.ingestion.S3StorageClient')
    @patch('hub.apps.jobs.tasks.process_job')
    def test_complete_ingestion_lifecycle(self, mock_process_job, mock_storage_class, mock_factory, mock_sync):
        """Test complete ingestion lifecycle from creation to completion"""
        # Mock Prefect deployment
        mock_deployment = MagicMock()
        mock_deployment.id = uuid.uuid4()
        mock_sync.return_value.create_or_update_deployment.return_value = mock_deployment
        
        # Step 1: Create scheduled ingestion
        data = {
            "name": "Daily Sales Ingestion",
            "description": "Ingests daily sales CSV files from S3",
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
        
        response = self.client.post(
            '/api/v1/scheduled-ingestions/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ingestion_id = response.data['id']
        
        # Step 2: Verify ingestion created
        ingestion = ScheduledIngestion.objects.get(id=ingestion_id)
        self.assertEqual(ingestion.name, "Daily Sales Ingestion")
        self.assertEqual(ingestion.status, ScheduledIngestionStatus.ACTIVE)
        self.assertIsNotNone(ingestion.prefect_deployment_id)
        
        # Step 3: Manually trigger ingestion
        from hub.apps.scheduled_ingestion.views import run_deployment, get_client
        
        with patch('hub.apps.scheduled_ingestion.views.run_deployment') as mock_run:
            mock_flow_run = MagicMock()
            mock_flow_run.id = uuid.uuid4()
            mock_run.return_value = mock_flow_run
            
            response = self.client.post(
                f'/api/v1/scheduled-ingestions/{ingestion_id}/trigger/'
            )
            
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            job_id = response.data['job_id']
            run_id = response.data['scheduled_ingestion_run_id']
        
        # Step 4: Verify run and job created
        run = ScheduledIngestionRun.objects.get(id=run_id)
        self.assertEqual(run.scheduled_ingestion.id, uuid.UUID(ingestion_id))
        self.assertEqual(run.status, ScheduledIngestionRunStatus.PENDING)
        
        job = Job.objects.get(id=job_id)
        self.assertEqual(job.type, JobType.SCHEDULED_INGESTION)
        self.assertEqual(job.status, JobStatus.PENDING)
        
        # Step 5: Execute ingestion (simulate job processing)
        mock_connector = MagicMock()
        mock_connector.discover_files.return_value = ["sales/daily/sales_2024-01-15.csv"]
        mock_connector.get_file_metadata.return_value = {
            "last_modified": timezone.now(),
            "size": 100
        }
        
        mock_result = MagicMock()
        mock_result.status.value = "SUCCESS"
        
        def mock_download(config, file_path, dest_path):
            with open(dest_path, 'wb') as f:
                f.write(b"date,amount\n2024-01-15,1000")
            return mock_result
        
        mock_connector.download_file.side_effect = mock_download
        mock_factory.get_connector.return_value = mock_connector
        
        mock_storage = MagicMock()
        mock_storage.save_file.return_value = f"{self.tenant.id}/file_id/sales_2024-01-15.csv"
        mock_storage.get_file_content.return_value = b"date,amount\n2024-01-15,1000"
        mock_storage_class.return_value = mock_storage
        
        from hub.apps.jobs.tasks import _execute_scheduled_ingestion_job
        result = _execute_scheduled_ingestion_job(job)
        
        # Step 6: Verify ingestion results
        self.assertEqual(result["files_found"], 1)
        self.assertEqual(result["files_processed"], 1)
        self.assertEqual(result["datasets_created"], 1)
        
        # Step 7: Verify run updated
        run.refresh_from_db()
        self.assertEqual(run.status, ScheduledIngestionRunStatus.COMPLETED)
        self.assertIsNotNone(run.completed_at)
        
        # Step 8: Verify dataset and asset created
        datasets = Dataset.objects.filter(tenant=self.tenant)
        self.assertEqual(datasets.count(), 1)
        
        assets = Asset.objects.filter(tenant=self.tenant)
        self.assertEqual(assets.count(), 1)
        asset = assets.first()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        
        # Step 9: Check run history
        response = self.client.get(f'/api/v1/scheduled-ingestions/{ingestion_id}/runs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['status'], "COMPLETED")
        
        # Step 10: Update ingestion
        update_data = {
            "description": "Updated description",
            "schedule": "0 3 * * *"
        }
        
        with patch('hub.apps.scheduled_ingestion.views.DeploymentSyncService') as mock_sync_update:
            mock_sync_update.return_value.create_or_update_deployment.return_value = mock_deployment
            
            response = self.client.patch(
                f'/api/v1/scheduled-ingestions/{ingestion_id}/',
                update_data,
                format='json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['description'], "Updated description")
            self.assertEqual(response.data['schedule'], "0 3 * * *")
        
        # Step 11: Delete ingestion
        with patch('hub.apps.scheduled_ingestion.views.DeploymentSyncService') as mock_sync_delete:
            mock_sync_delete.return_value.delete_deployment.return_value = None
            
            response = self.client.delete(f'/api/v1/scheduled-ingestions/{ingestion_id}/')
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deleted
        self.assertFalse(ScheduledIngestion.objects.filter(id=ingestion_id).exists())
    
    @patch('hub.apps.scheduled_ingestion.views.DeploymentSyncService')
    def test_multiple_ingestions_tenant_isolation(self, mock_sync):
        """Test that multiple ingestions are properly isolated by tenant"""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        user2 = User.objects.create_user(
            email="user2@example.com",
            password="testpass123",
            tenant=tenant2,
            status=UserStatus.ACTIVE
        )
        
        # Mock Prefect deployment
        mock_deployment = MagicMock()
        mock_deployment.id = uuid.uuid4()
        mock_sync.return_value.create_or_update_deployment.return_value = mock_deployment
        
        # Create ingestion for tenant1
        data1 = {
            "name": "Tenant 1 Ingestion",
            "source_type": "S3",
            "source_config": {"bucket": "bucket1"},
            "schedule": "0 0 * * *"
        }
        
        response1 = self.client.post(
            '/api/v1/scheduled-ingestions/',
            data1,
            format='json'
        )
        ingestion1_id = response1.data['id']
        
        # Create ingestion for tenant2
        client2 = APIClient()
        client2.force_authenticate(user=user2)
        
        data2 = {
            "name": "Tenant 2 Ingestion",
            "source_type": "GCS",
            "source_config": {"bucket": "bucket2"},
            "schedule": "0 1 * * *"
        }
        
        response2 = client2.post(
            '/api/v1/scheduled-ingestions/',
            data2,
            format='json'
        )
        ingestion2_id = response2.data['id']
        
        # List ingestions for tenant1 - should only see tenant1's
        response = self.client.get('/api/v1/scheduled-ingestions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ingestion_ids = [item['id'] for item in response.data]
        self.assertIn(ingestion1_id, ingestion_ids)
        self.assertNotIn(ingestion2_id, ingestion_ids)
        
        # List ingestions for tenant2 - should only see tenant2's
        response = client2.get('/api/v1/scheduled-ingestions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ingestion_ids = [item['id'] for item in response.data]
        self.assertNotIn(ingestion1_id, ingestion_ids)
        self.assertIn(ingestion2_id, ingestion_ids)

