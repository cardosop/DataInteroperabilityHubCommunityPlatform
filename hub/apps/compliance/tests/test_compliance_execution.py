"""
Unit tests for compliance execution.
"""
import pytest
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from django.utils import timezone

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.compliance.views import execute_compliance_run
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.models import Dataset
from hub.apps.assets.models import Asset, ComplianceStatus as AssetComplianceStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ComplianceExecutionTest(TestCase):
    """Test compliance execution"""
    
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
    def test_execute_compliance_run_success(self, mock_compliance_client_class, mock_storage_client_class):
        """Test successful compliance run execution"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"email,name\nuser@example.com,John Doe"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_compliance_client = MagicMock()
        mock_compliance_client.scan_file.return_value = {
            'overall_status': 'PASS',
            'risk_level': 'LOW',
            'risk_score': 1.5,
            'allowed_to_store': True,
            'detected_categories': [
                {'category': 'EMAIL', 'count': 1, 'match_ratio': 1.0}
            ],
            'column_findings': [
                {
                    'column': 'email',
                    'pii_categories': ['EMAIL'],
                    'match_ratio': 1.0
                }
            ],
            'regulation_mapping': {
                'GDPR': {'applies': True, 'categories': ['EMAIL']},
                'CCPA': {'applies': True, 'categories': ['EMAIL']}
            },
            'applicable_regulations': ['GDPR', 'CCPA'],
            'metadata': {
                'total_rows': 1,
                'total_columns': 2
            }
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
        
        # Verify compliance run was updated
        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.SUCCEEDED)
        self.assertEqual(compliance_run.overall_status, 'PASS')
        self.assertEqual(compliance_run.risk_level, RiskLevel.LOW)
        self.assertTrue(compliance_run.allowed_to_store)
        self.assertIsNotNone(compliance_run.completed_at)
        self.assertIsNotNone(compliance_run.started_at)
        
        # Verify metering information
        self.assertIn('metering', compliance_run.regulation_mapping_json)
        metering = compliance_run.regulation_mapping_json['metering']
        self.assertEqual(metering['operation_type'], 'COMPLIANCE_RUN')
        self.assertEqual(metering['rows_scanned'], 1)
        self.assertEqual(metering['columns_scanned'], 2)
        self.assertEqual(metering['scan_mode'], 'internal')
        self.assertIn('execution_time_seconds', metering)
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.views.ComplianceServiceClient')
    def test_execute_compliance_run_fail_closed(self, mock_compliance_client_class, mock_storage_client_class):
        """Test compliance run with fail-closed (allowed_to_store=False)"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"email,ssn\nuser@example.com,123-45-6789"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_compliance_client = MagicMock()
        mock_compliance_client.scan_file.return_value = {
            'overall_status': 'FAIL',
            'risk_level': 'CRITICAL',
            'risk_score': 10.0,
            'allowed_to_store': False,  # Fail-closed
            'detected_categories': [
                {'category': 'EMAIL', 'count': 1, 'match_ratio': 1.0},
                {'category': 'SSN', 'count': 1, 'match_ratio': 1.0}
            ],
            'column_findings': [],
            'regulation_mapping': {},
            'applicable_regulations': ['GDPR', 'HIPAA'],
            'metadata': {'total_rows': 1, 'total_columns': 2}
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
        
        # Verify compliance run was updated with fail-closed
        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.SUCCEEDED)
        self.assertFalse(compliance_run.allowed_to_store)
        self.assertEqual(compliance_run.risk_level, RiskLevel.CRITICAL)
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.views.ComplianceServiceClient')
    def test_execute_compliance_run_service_failure_fail_closed(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that service failure results in fail-closed behavior"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"email,name\nuser@example.com,John"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_compliance_client = MagicMock()
        mock_compliance_client.scan_file.side_effect = Exception("Compliance service error")
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
        
        # Verify compliance run was marked as failed with fail-closed
        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(compliance_run.allowed_to_store)  # Fail-closed
        self.assertIn('fail_closed', compliance_run.regulation_mapping_json)
        self.assertTrue(compliance_run.regulation_mapping_json['fail_closed'])
    
    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.views.ComplianceServiceClient')
    def test_execute_compliance_run_updates_asset_compliance_status(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that compliance run updates asset compliance status"""
        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.download_file.return_value = b"email,name\nuser@example.com,John"
        mock_storage_client_class.return_value = mock_storage_client
        
        mock_compliance_client = MagicMock()
        mock_compliance_client.scan_file.return_value = {
            'overall_status': 'WARN',
            'risk_level': 'MEDIUM',
            'risk_score': 3.0,
            'allowed_to_store': True,
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
        
        # Create dataset linked to asset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=self.file,
            format="CSV",
            created_by=self.user
        )
        
        # Create compliance run for asset
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            dataset=dataset,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.PENDING
        )
        
        # Execute compliance run
        execute_compliance_run(str(compliance_run.id))
        
        # Verify asset compliance status was updated
        asset.refresh_from_db()
        self.assertEqual(asset.compliance_status, AssetComplianceStatus.WARN)

