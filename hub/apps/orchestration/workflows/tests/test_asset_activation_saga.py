"""
Tests for Asset Activation Saga workflow.

These tests verify:
- Saga step execution (contract validation, DQ check, compliance check, activation)
- Compensation logic (rollback activation, reset status)
- Error handling and rollback scenarios
"""

import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.orchestration.saga import (
    SagaOrchestrator,
)
from hub.apps.orchestration.workflows.asset_activation_saga import (
    activate_asset,
    check_compliance,
    check_data_quality,
    compensate_activation,
    create_asset_activation_saga,
    execute_asset_activation,
    validate_contract,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


class AssetActivationSagaTest(TestCase):
    """Test Asset Activation Saga workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        # Create asset
        self.asset = Asset.objects.create(
            name="Test Asset",
            key="test-asset",
            tenant=self.tenant,
            status=AssetStatus.DRAFT,
            dq_status="PASS",
            compliance_status="PASS",
        )

        # Create contract
        self.contract = Contract.objects.create(
            asset=self.asset,
            tenant=self.tenant,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "3.0.0"}',
        )

    def test_validate_contract_success(self):
        """Test contract validation step succeeds."""
        result = validate_contract({"asset_id": str(self.asset.id)})

        self.assertTrue(result.success)
        self.assertIn("contract_id", result.output)
        self.assertEqual(result.output["contract_id"], str(self.contract.id))
        self.assertEqual(result.output["original_asset_status"], AssetStatus.DRAFT.value)

    def test_validate_contract_no_contract(self):
        """Test contract validation fails when no contract exists."""
        asset_no_contract = Asset.objects.create(
            name="No Contract Asset",
            key="no-contract-asset",
            tenant=self.tenant,
            status=AssetStatus.DRAFT,
        )

        result = validate_contract({"asset_id": str(asset_no_contract.id)})

        self.assertFalse(result.success)
        self.assertIn("No active contract", result.error)

    def test_validate_contract_asset_not_found(self):
        """Test contract validation fails when asset doesn't exist."""
        result = validate_contract({"asset_id": "00000000-0000-0000-0000-000000000000"})

        self.assertFalse(result.success)
        self.assertIn("not found", result.error)

    def test_check_data_quality_success(self):
        """Test DQ check step succeeds."""
        # Create successful DQ job
        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
        )

        result = check_data_quality({"asset_id": str(self.asset.id)})

        self.assertTrue(result.success)
        self.assertIn("dq_status", result.output)
        self.assertEqual(result.output["dq_status"], "PASS")

    def test_check_data_quality_fail(self):
        """Test DQ check fails when asset DQ status is FAIL."""
        self.asset.dq_status = "FAIL"
        self.asset.save()

        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
        )

        result = check_data_quality({"asset_id": str(self.asset.id)})

        self.assertFalse(result.success)
        self.assertIn("data quality check failed", result.error)

    def test_check_data_quality_no_job(self):
        """Test DQ check fails when no DQ job exists."""
        result = check_data_quality({"asset_id": str(self.asset.id)})

        self.assertFalse(result.success)
        self.assertIn("No successful DQ job", result.error)

    def test_check_compliance_success(self):
        """Test compliance check step succeeds."""
        # Create successful compliance job
        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
        )

        result = check_compliance({"asset_id": str(self.asset.id)})

        self.assertTrue(result.success)
        self.assertIn("compliance_status", result.output)
        self.assertEqual(result.output["compliance_status"], "PASS")

    def test_check_compliance_fail(self):
        """Test compliance check fails when asset compliance status is FAIL."""
        self.asset.compliance_status = "FAIL"
        self.asset.save()

        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
        )

        result = check_compliance({"asset_id": str(self.asset.id)})

        self.assertFalse(result.success)
        self.assertIn("compliance check failed", result.error)

    def test_activate_asset_success(self):
        """Test asset activation step succeeds."""
        original_status = self.asset.status

        result = activate_asset(
            {"asset_id": str(self.asset.id), "original_asset_status": original_status.value}
        )

        self.assertTrue(result.success)
        self.assertIn("new_status", result.output)
        self.assertEqual(result.output["new_status"], AssetStatus.ACTIVE.value)

        # Verify asset was activated
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.ACTIVE)

    def test_compensate_activation_success(self):
        """Test activation compensation resets asset status."""
        # First activate the asset
        self.asset.status = AssetStatus.ACTIVE
        self.asset.save()

        original_status = AssetStatus.DRAFT

        result = compensate_activation(
            {
                "asset_id": str(self.asset.id),
                "original_status": original_status.value,
                "step_output": {"original_status": original_status.value},
            }
        )

        self.assertTrue(result.success)
        self.assertIn("reset_status", result.output)

        # Verify asset status was reset
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.DRAFT)

    def test_compensate_activation_default_status(self):
        """Test activation compensation uses default status when original not provided."""
        # First activate the asset
        self.asset.status = AssetStatus.ACTIVE
        self.asset.save()

        result = compensate_activation({"asset_id": str(self.asset.id), "step_output": {}})

        self.assertTrue(result.success)

        # Verify asset status was reset to DRAFT (default)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.DRAFT)

    def test_full_saga_execution_success(self):
        """Test full saga execution succeeds when all steps pass."""
        # Create required jobs
        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
        )
        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
        )

        result = execute_asset_activation(str(self.asset.id))

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIn("saga_id", result)

        # Verify asset was activated
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.ACTIVE)

    def test_full_saga_execution_failure_contract_validation(self):
        """Test saga execution fails and compensates when contract validation fails."""
        # Remove contract
        self.contract.delete()

        result = execute_asset_activation(str(self.asset.id))

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "COMPENSATED")
        self.assertIn("error", result)

        # Verify asset status was not changed
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.DRAFT)

    def test_full_saga_execution_failure_dq_check(self):
        """Test saga execution fails and compensates when DQ check fails."""
        # Set DQ status to FAIL
        self.asset.dq_status = "FAIL"
        self.asset.save()

        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
        )

        result = execute_asset_activation(str(self.asset.id))

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "COMPENSATED")

        # Verify asset status was not changed (contract validation passed but DQ failed)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.DRAFT)

    def test_full_saga_execution_failure_compliance_check(self):
        """Test saga execution fails and compensates when compliance check fails."""
        # Set compliance status to FAIL
        self.asset.compliance_status = "FAIL"
        self.asset.save()

        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
        )
        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
        )

        result = execute_asset_activation(str(self.asset.id))

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "COMPENSATED")

        # Verify asset status was not changed
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.DRAFT)

    def test_full_saga_execution_failure_activation(self):
        """Test saga execution fails and compensates when activation fails."""
        # Create required jobs
        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
        )
        Job.objects.create(
            resource_type="ASSET",
            resource_id=self.asset.id,
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
        )

        # Mock activation to fail
        with patch(
            "hub.apps.orchestration.workflows.asset_activation_saga.Asset.objects.get"
        ) as mock_get:
            mock_asset = MagicMock()
            mock_asset.status = AssetStatus.DRAFT
            mock_asset.save.side_effect = Exception("Database error")
            mock_get.return_value = mock_asset

            result = execute_asset_activation(str(self.asset.id))

            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "COMPENSATED")

    def test_create_asset_activation_saga(self):
        """Test saga creation."""
        orchestrator = create_asset_activation_saga(str(self.asset.id))

        self.assertIsInstance(orchestrator, SagaOrchestrator)
        self.assertEqual(orchestrator.context.state["asset_id"], str(self.asset.id))
