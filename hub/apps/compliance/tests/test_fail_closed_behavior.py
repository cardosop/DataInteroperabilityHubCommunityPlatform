"""
Unit tests for fail-closed behavior.
"""
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.views import execute_compliance_run
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.assets.models import Asset
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


class FailClosedBehaviorTest(TestCase):
    """Test fail-closed enforcement behavior"""
    
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
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            timeout_seconds=1800,
            details_json={
                'scan_mode': 'internal',
                'applicable_regulations': []
            }
        )
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.views.ComplianceServiceClient')
    def test_fail_closed_when_allowed_to_store_false(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that allowed_to_store=False triggers fail-closed behavior"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"email,ssn\nuser@example.com,123-45-6789"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_compliance_client = MagicMock()
        mock_compliance_client.scan_file.return_value = {
            'overall_status': 'FAIL',
            'risk_level': 'CRITICAL',
            'risk_score': 15.0,
            'allowed_to_store': False,  # Fail-closed
            'detected_categories': [
                {'category': 'SSN', 'count': 1000, 'match_ratio': 1.0}  # 100% > 1% threshold
            ],
            'column_findings': [],
            'regulation_mapping': {},
            'applicable_regulations': ['GDPR', 'HIPAA'],
            'metadata': {'total_rows': 1000, 'total_columns': 2}
        }
        mock_compliance_client_class.return_value = mock_compliance_client
        
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )
        
        # Execute compliance run
        execute_compliance_run(str(compliance_run.id))
        
        # Verify fail-closed behavior
        compliance_run.refresh_from_db()
        self.assertFalse(compliance_run.allowed_to_store)
        self.assertEqual(compliance_run.overall_status, 'FAIL')
        
        # Verify warning was logged (check via mock if needed)
        # The actual enforcement happens at ingestion/asset activation level
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.views.ComplianceServiceClient')
    def test_fail_closed_on_service_error(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that service errors result in fail-closed behavior"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"email,name\nuser@example.com,John"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_compliance_client = MagicMock()
        mock_compliance_client.scan_file.side_effect = Exception("Compliance service unavailable")
        mock_compliance_client_class.return_value = mock_compliance_client
        
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )
        
        # Execute compliance run
        execute_compliance_run(str(compliance_run.id))
        
        # Verify fail-closed on error
        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(compliance_run.allowed_to_store)  # Fail-closed
        self.assertIn('fail_closed', compliance_run.regulation_mapping_json)
        self.assertTrue(compliance_run.regulation_mapping_json['fail_closed'])
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.views.ComplianceServiceClient')
    def test_fail_closed_blocks_asset_activation(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that fail-closed compliance prevents asset activation"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"email,ssn\nuser@example.com,123-45-6789"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_compliance_client = MagicMock()
        mock_compliance_client.scan_file.return_value = {
            'overall_status': 'FAIL',
            'risk_level': 'CRITICAL',
            'risk_score': 20.0,
            'allowed_to_store': False,
            'detected_categories': [],
            'column_findings': [],
            'regulation_mapping': {},
            'applicable_regulations': [],
            'metadata': {'total_rows': 1, 'total_columns': 2}
        }
        mock_compliance_client_class.return_value = mock_compliance_client
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Create compliance run for asset
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )
        
        # Execute compliance run
        execute_compliance_run(str(compliance_run.id))
        
        # Verify asset compliance status
        compliance_run.refresh_from_db()
        asset.refresh_from_db()
        
        self.assertFalse(compliance_run.allowed_to_store)
        self.assertEqual(asset.compliance_status, AssetComplianceStatus.FAIL)
        
        # Asset activation should be blocked (enforced at asset.can_activate() level)
        can_activate, reason = asset.can_activate()
        self.assertFalse(can_activate)
        self.assertIn('compliance_status', reason.lower())

