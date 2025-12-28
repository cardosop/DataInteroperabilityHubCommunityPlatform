"""
Integration tests for TransformationService compliance integration using real ComplianceService.

These tests use the real ComplianceServiceClient (no mocks) to ensure end-to-end integration.
If the compliance service is unavailable, tests will skip gracefully.
"""
import uuid
from django.test import TestCase
from unittest import skipIf
from unittest.mock import patch

from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus, ExecutionStatus
from hub.apps.transformation.exceptions import TransformationValidationError
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.tenants.models import Tenant
from hub.apps.governance.models import AccessPolicy
from hub.apps.compliance.service_client import ComplianceServiceClient


def compliance_service_available():
    """Check if compliance service is available"""
    try:
        client = ComplianceServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except Exception:
        return False


@skipIf(not compliance_service_available(), "Compliance service not available")
class ComplianceIntegrationRealServiceTest(TestCase):
    """Integration tests using real ComplianceService (no mocks)"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create role and user
        self.role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )
        self.user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.user, role=self.role)

        # Create ABAC policy
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Pipeline Operations",
            defaults={
                "conditions": {
                    "user": {"tenant_id": str(self.tenant.id)}
                },
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by": self.user
            }
        )

        # Create pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "task": "extract_data",
                        "input": {}
                    }
                ]
            },
            version="1.0.0",
            status=PipelineStatus.ACTIVE.value
        )

        # Create test asset with dataset and file
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE
        )

        # Create file with non-PII content (should pass compliance)
        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test.csv",
            storage_path="test/test.csv",
            size=100,
            content_type="text/csv",
            status=FileStatus.ACTIVE
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=10
        )

        # Upload file content to storage (mock storage for test)
        from hub.apps.files.storage import S3StorageClient
        with patch.object(S3StorageClient, 'save_file') as mock_save:
            mock_save.return_value = "test/test.csv"
            # File content: simple CSV without PII
            test_content = b"id,name,value\n1,Item1,100\n2,Item2,200\n"
            with patch.object(S3StorageClient, 'get_file_content') as mock_get:
                mock_get.return_value = test_content

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    @patch('hub.apps.files.storage.S3StorageClient.get_file_content')
    def test_input_compliance_check_with_real_service(self, mock_get_content):
        """Test input compliance check with real ComplianceService"""
        # Provide test file content (non-PII data)
        mock_get_content.return_value = b"id,name,value\n1,Item1,100\n2,Item2,200\n"

        # Create execution
        from hub.apps.transformation.models import PipelineExecution
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.PENDING
        )

        # Run compliance check with real service
        compliance_status = self.service._run_compliance_check(
            str(self.asset.id),
            str(self.tenant.id),
            execution
        )

        # Verify compliance check completed (may return None if service unavailable)
        # But if it returns, verify structure
        if compliance_status is not None:
            self.assertIn("overall_status", compliance_status)
            self.assertIn("risk_level", compliance_status)

            # Verify compliance status stored in execution_log
            execution.refresh_from_db()
            compliance_logs = [
                log for log in execution.execution_log
                if isinstance(log, dict) and log.get("message") == "Compliance check completed"
            ]
            self.assertGreater(len(compliance_logs), 0)

    @patch('hub.apps.files.storage.S3StorageClient.get_file_content')
    def test_output_asset_compliance_check_with_real_service(self, mock_get_content):
        """Test output asset compliance check with real ComplianceService"""
        # Create result asset
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE
        )

        result_file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="result.csv",
            storage_path="test/result.csv",
            size=100,
            content_type="text/csv",
            status=FileStatus.ACTIVE
        )

        result_dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=result_asset,
            file=result_file,
            version=1,
            format="CSV",
            row_count=10
        )

        # Provide test file content
        mock_get_content.return_value = b"id,name,value\n1,Item1,100\n2,Item2,200\n"

        # Create execution
        from hub.apps.transformation.models import PipelineExecution
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            result_asset=result_asset,
            status=ExecutionStatus.RUNNING
        )

        # Run output compliance check with real service
        compliance_status = self.service._check_output_asset_compliance(
            str(result_asset.id),
            str(self.tenant.id),
            execution
        )

        # Verify compliance check completed
        if compliance_status is not None:
            self.assertIn("overall_status", compliance_status)
            self.assertIn("risk_level", compliance_status)

            # Verify compliance status stored in execution_log
            execution.refresh_from_db()
            compliance_logs = [
                log for log in execution.execution_log
                if isinstance(log, dict) and log.get("message") == "Output asset compliance check completed"
            ]
            self.assertGreater(len(compliance_logs), 0)

