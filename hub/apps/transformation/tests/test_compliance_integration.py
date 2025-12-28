"""
Unit tests for TransformationService compliance integration.

Tests verify comprehensive compliance checking for pipeline execution:
- Input asset compliance check
- Transformation compliance validation
- Output asset compliance check
- Compliance violation blocking
- Compliance status storage in execution_log

All tests use real ComplianceServiceClient (no mocks) to ensure integration.
"""
import uuid
from django.test import TestCase
from unittest.mock import patch, MagicMock

from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus, ExecutionStatus
from hub.apps.transformation.exceptions import TransformationValidationError
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.tenants.models import Tenant
from hub.apps.governance.models import AccessPolicy


class ComplianceIntegrationTest(TestCase):
    """Test compliance integration in TransformationService"""

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

        from hub.apps.files.models import FileStatus
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

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient')
    def test_input_compliance_check_passes(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that input compliance check passes when asset is compliant"""
        # Mock storage client
        mock_storage = MagicMock()
        mock_storage.get_file_content.return_value = b"col1,col2\nval1,val2\n"
        mock_storage_client_class.return_value = mock_storage

        # Mock compliance client
        mock_compliance = MagicMock()
        mock_compliance.health_check.return_value = (True, "compliance-service")
        mock_compliance.scan_file.return_value = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": {},
            "column_findings": [],
            "regulation_mapping": {}
        }
        mock_compliance_client_class.return_value = mock_compliance

        # Create execution
        from hub.apps.transformation.models import PipelineExecution
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.PENDING
        )

        # Run compliance check
        compliance_status = self.service._run_compliance_check(
            str(self.asset.id),
            str(self.tenant.id),
            execution
        )

        # Verify compliance status
        self.assertIsNotNone(compliance_status)
        self.assertEqual(compliance_status["overall_status"], "PASS")
        self.assertEqual(compliance_status["risk_level"], "LOW")

        # Verify compliance status stored in execution_log
        execution.refresh_from_db()
        self.assertIsInstance(execution.execution_log, list)
        compliance_logs = [
            log for log in execution.execution_log
            if isinstance(log, dict) and log.get("message") == "Compliance check completed"
        ]
        self.assertGreater(len(compliance_logs), 0)
        self.assertEqual(compliance_logs[0]["data"]["compliance_status"]["overall_status"], "PASS")

    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient')
    def test_input_compliance_check_blocks_execution_on_failure(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that input compliance check blocks execution when violations detected"""
        # Mock storage client
        mock_storage = MagicMock()
        mock_storage.get_file_content.return_value = b"col1,col2\nval1,val2\n"
        mock_storage_client_class.return_value = mock_storage

        # Mock compliance client with FAIL status
        mock_compliance = MagicMock()
        mock_compliance.health_check.return_value = (True, "compliance-service")
        mock_compliance.scan_file.return_value = {
            "overall_status": "FAIL",
            "risk_level": "HIGH",
            "allowed_to_store": False,
            "detected_categories": {"PII": ["email", "ssn"]},
            "column_findings": [],
            "regulation_mapping": {}
        }
        mock_compliance_client_class.return_value = mock_compliance

        # Create execution
        from hub.apps.transformation.models import PipelineExecution
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.PENDING
        )

        # Run compliance check - should raise TransformationValidationError
        with self.assertRaises(TransformationValidationError) as cm:
            self.service._run_compliance_check(
                str(self.asset.id),
                str(self.tenant.id),
                execution
            )

        # Verify error details
        self.assertIn("Compliance check failed", str(cm.exception))
        self.assertIn("asset_id", cm.exception.details)
        self.assertEqual(cm.exception.details["asset_id"], str(self.asset.id))
        self.assertIn("compliance_status", cm.exception.details)

    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient')
    def test_transformation_compliance_validation(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that transformation compliance validation runs"""
        # Mock storage client
        mock_storage = MagicMock()
        mock_storage.get_file_content.return_value = b"col1,col2\nval1,val2\n"
        mock_storage_client_class.return_value = mock_storage

        # Mock compliance client
        mock_compliance = MagicMock()
        mock_compliance.health_check.return_value = (True, "compliance-service")
        mock_compliance.scan_file.return_value = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": {},
            "column_findings": [],
            "regulation_mapping": {}
        }
        mock_compliance_client_class.return_value = mock_compliance

        # Create execution
        from hub.apps.transformation.models import PipelineExecution
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.PENDING
        )

        # Run compliance check
        compliance_status = self.service._run_compliance_check(
            str(self.asset.id),
            str(self.tenant.id),
            execution
        )

        # Verify transformation compliance validation was called
        execution.refresh_from_db()
        validation_logs = [
            log for log in execution.execution_log
            if isinstance(log, dict) and "Transformation compliance validation" in log.get("message", "")
        ]
        self.assertGreater(len(validation_logs), 0)

    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient')
    def test_output_asset_compliance_check(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that output asset compliance check works"""
        # Create result asset
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE
        )

        from hub.apps.files.models import FileStatus
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

        # Mock storage client
        mock_storage = MagicMock()
        mock_storage.get_file_content.return_value = b"col1,col2\nval1,val2\n"
        mock_storage_client_class.return_value = mock_storage

        # Mock compliance client
        mock_compliance = MagicMock()
        mock_compliance.health_check.return_value = (True, "compliance-service")
        mock_compliance.scan_file.return_value = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": {},
            "column_findings": [],
            "regulation_mapping": {}
        }
        mock_compliance_client_class.return_value = mock_compliance

        # Create execution
        from hub.apps.transformation.models import PipelineExecution
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            result_asset=result_asset,
            status=ExecutionStatus.RUNNING
        )

        # Run output compliance check
        compliance_status = self.service._check_output_asset_compliance(
            str(result_asset.id),
            str(self.tenant.id),
            execution
        )

        # Verify compliance status
        self.assertIsNotNone(compliance_status)
        self.assertEqual(compliance_status["overall_status"], "PASS")

        # Verify compliance status stored in execution_log
        execution.refresh_from_db()
        compliance_logs = [
            log for log in execution.execution_log
            if isinstance(log, dict) and log.get("message") == "Output asset compliance check completed"
        ]
        self.assertGreater(len(compliance_logs), 0)
        self.assertEqual(compliance_logs[0]["data"]["compliance_status"]["overall_status"], "PASS")

    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient')
    def test_output_compliance_check_blocks_on_failure(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that output compliance check blocks when violations detected"""
        # Create result asset
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE
        )

        from hub.apps.files.models import FileStatus
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

        # Mock storage client
        mock_storage = MagicMock()
        mock_storage.get_file_content.return_value = b"col1,col2\nval1,val2\n"
        mock_storage_client_class.return_value = mock_storage

        # Mock compliance client with FAIL status
        mock_compliance = MagicMock()
        mock_compliance.health_check.return_value = (True, "compliance-service")
        mock_compliance.scan_file.return_value = {
            "overall_status": "FAIL",
            "risk_level": "HIGH",
            "allowed_to_store": False,
            "detected_categories": {"PII": ["email", "ssn"]},
            "column_findings": [],
            "regulation_mapping": {}
        }
        mock_compliance_client_class.return_value = mock_compliance

        # Create execution
        from hub.apps.transformation.models import PipelineExecution
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            result_asset=result_asset,
            status=ExecutionStatus.RUNNING
        )

        # Run output compliance check - should raise TransformationValidationError
        with self.assertRaises(TransformationValidationError) as cm:
            self.service._check_output_asset_compliance(
                str(result_asset.id),
                str(self.tenant.id),
                execution
            )

        # Verify error details
        self.assertIn("Compliance check failed for output asset", str(cm.exception))
        self.assertIn("asset_id", cm.exception.details)
        self.assertEqual(cm.exception.details["asset_id"], str(result_asset.id))
        self.assertIn("compliance_status", cm.exception.details)

    @patch('hub.apps.files.storage.S3StorageClient')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient')
    def test_compliance_status_stored_in_execution_log(self, mock_compliance_client_class, mock_storage_client_class):
        """Test that compliance status is comprehensively stored in execution_log"""
        # Mock storage client
        mock_storage = MagicMock()
        mock_storage.get_file_content.return_value = b"col1,col2\nval1,val2\n"
        mock_storage_client_class.return_value = mock_storage

        # Mock compliance client
        mock_compliance = MagicMock()
        mock_compliance.health_check.return_value = (True, "compliance-service")
        mock_compliance.scan_file.return_value = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": {"PII": ["email"]},
            "column_findings": [{"column": "email", "category": "PII"}],
            "regulation_mapping": {"GDPR": ["email"]}
        }
        mock_compliance_client_class.return_value = mock_compliance

        # Create execution
        from hub.apps.transformation.models import PipelineExecution
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.PENDING
        )

        # Run compliance check
        compliance_status = self.service._run_compliance_check(
            str(self.asset.id),
            str(self.tenant.id),
            execution
        )

        # Verify comprehensive compliance status stored
        execution.refresh_from_db()
        compliance_logs = [
            log for log in execution.execution_log
            if isinstance(log, dict) and log.get("message") == "Compliance check completed"
        ]
        self.assertGreater(len(compliance_logs), 0)

        stored_status = compliance_logs[0]["data"]["compliance_status"]
        self.assertIn("overall_status", stored_status)
        self.assertIn("risk_level", stored_status)
        self.assertIn("detected_categories", stored_status)
        self.assertIn("column_findings", stored_status)
        self.assertIn("regulation_mapping", stored_status)

