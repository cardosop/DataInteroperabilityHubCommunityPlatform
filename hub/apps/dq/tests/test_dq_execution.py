"""
Unit tests for DQ execution.
"""
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from django.utils import timezone

from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.dq.views import execute_dq_run
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.models import Dataset
from hub.apps.assets.models import Asset, DQStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


class DQExecutionTest(TestCase):
    """Test DQ execution"""
    
    def setUp(self):
        """Set up test fixtures"""
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
        
        # Create file
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            timeout_seconds=1800
        )
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.dq.views.DQServiceClient')
    def test_execute_dq_run_success(self, mock_dq_client_class, mock_storage_client_class):
        """Test successful DQ run execution"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"id,name\n1,Test\n2,Sample"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_dq_client = MagicMock()
        mock_dq_client.run_dq.return_value = {
            'overall_status': 'PASS',
            'quality_score': 95.5,
            'checks': [
                {
                    'check_id': 'not_null_primary_key',
                    'status': 'PASS',
                    'message': 'All ID columns are not null'
                }
            ],
            'engine_type': 'GX',
            'engine_version': '0.18.0',
            'profile_key': 'intake_basic_gx',
            'metadata': {
                'total_rows': 2,
                'total_columns': 2,
                'execution_time_seconds': 1.5
            }
        }
        mock_dq_client_class.return_value = mock_dq_client
        
        # Create DQ run
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        # Execute DQ run
        execute_dq_run(str(dq_run.id))
        
        # Verify DQ run was updated
        dq_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(dq_run.overall_status, 'PASS')
        self.assertEqual(dq_run.quality_score, 95.5)
        self.assertIsNotNone(dq_run.completed_at)
        self.assertIsNotNone(dq_run.started_at)
        
        # Verify metering information
        self.assertIn('metering', dq_run.details_json)
        metering = dq_run.details_json['metering']
        self.assertEqual(metering['operation_type'], 'DQ_RUN')
        self.assertEqual(metering['rows_inspected'], 2)
        self.assertEqual(metering['columns_inspected'], 2)
        self.assertEqual(metering['engine_type'], 'GX')
        self.assertIn('execution_time_seconds', metering)
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.dq.views.DQServiceClient')
    def test_execute_dq_run_updates_asset_dq_status(self, mock_dq_client_class, mock_storage_client_class):
        """Test that DQ run updates asset DQ status"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"id,name\n1,Test"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_dq_client = MagicMock()
        mock_dq_client.run_dq.return_value = {
            'overall_status': 'WARN',
            'quality_score': 80.0,
            'checks': [],
            'engine_type': 'GX',
            'engine_version': '0.18.0',
            'profile_key': 'intake_basic_gx',
            'metadata': {'total_rows': 1, 'total_columns': 2}
        }
        mock_dq_client_class.return_value = mock_dq_client
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Create dataset linked to asset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=self.file,
            format="CSV",
            created_by=self.user
        )
        
        # Create DQ run for asset
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            dataset=dataset,
            file=self.file,
            job=self.job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        # Execute DQ run
        execute_dq_run(str(dq_run.id))
        
        # Verify asset DQ status was updated
        asset.refresh_from_db()
        self.assertEqual(asset.dq_status, DQStatus.WARN)
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.dq.views.DQServiceClient')
    def test_execute_dq_run_failure(self, mock_dq_client_class, mock_storage_client_class):
        """Test DQ run execution failure"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"id,name\n1,Test"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_dq_client = MagicMock()
        mock_dq_client.run_dq.side_effect = Exception("DQ service error")
        mock_dq_client_class.return_value = mock_dq_client
        
        # Create DQ run
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key='intake_basic_gx',
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING
        )
        
        # Execute DQ run
        execute_dq_run(str(dq_run.id))
        
        # Verify DQ run was marked as failed
        dq_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.FAILED)
        self.assertIsNotNone(dq_run.completed_at)
        self.assertIn('error', dq_run.details_json)

