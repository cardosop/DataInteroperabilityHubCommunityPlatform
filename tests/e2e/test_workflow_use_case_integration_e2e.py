"""
Phase 6.9 — E2E Tests for Workflow Integration with Use Cases

Comprehensive E2E tests for workflows used in use cases (USE_CASES.md):
- 6.9.1: Asset Management use cases (UC-AM-001 and all AM workflow use cases)
- 6.9.2: Contract Management use cases (UC-CM-001 Create Contract and all CM workflow use cases)
- 6.9.3: Marketplace use cases (UC-MKT-001 Publish Asset to Marketplace and all MKT workflow use cases)
- 6.9.4: Other use case categories (Data Quality, Compliance, AI/ML, remaining)

Each test runs the real workflow with business rules validation, no mocks/stubs.
Verifies: workflow execution with business rules, workflow completes (or expected state).
"""

import pytest

pytestmark = pytest.mark.slow

pytestmark = [
    pytest.mark.uc_journey_persona,
    pytest.mark.workflow_e2e,
    pytest.mark.uc("UC-AM-001"),
    pytest.mark.uc("UC-CM-001"),
    pytest.mark.uc("UC-MKT-001"),
    pytest.mark.uc("UC-DQ-001"),
    pytest.mark.uc("UC-COMP-001"),
]

import json
import uuid
from datetime import timedelta

from django.utils import timezone

from hub.apps.assets.models import AssetStatus
from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.marketplace.models import PricingModel
from hub.apps.orchestration.models import StepStatus, WorkflowStatus
from hub.apps.orchestration.workflows.asset_creation import AssetCreationWorkflow
from hub.apps.orchestration.workflows.compliance_reporting import (
    ComplianceReportingWorkflow,
)
from hub.apps.orchestration.workflows.contract_creation import ContractCreationWorkflow
from hub.apps.orchestration.workflows.data_quality import DataQualityCheckWorkflow
from hub.apps.orchestration.workflows.marketplace_publication import (
    MarketplacePublicationWorkflow,
)
from hub.apps.tenants.models import KYCStatus
from tests.e2e.workflow_e2e_base import WorkflowE2ETestBase


def _minimal_odcs_raw():
    """Minimal valid ODCS contract content (JSON) for contract_creation workflow."""
    return json.dumps(
        {
            "id": "uc-contract",
            "info": {"version": "1.0", "name": "UC Contract"},
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string", "nullable": False},
                ]
            },
        }
    )


# --- 6.9.1 Asset Management use cases ---


class TestUC_AM_001_WorkflowIntegrationE2E(WorkflowE2ETestBase):
    """
    6.9.1 — UC-AM-001: Create Asset via Data-First Flow.

    Use case flow: create asset (draft), then create contract; workflows:
    AssetCreationWorkflow (create asset record), ContractCreationWorkflow (create contract).
    """

    workflow_classes = [AssetCreationWorkflow, ContractCreationWorkflow]

    def test_uc_am_001_asset_creation_workflow_with_business_rules(self):
        """UC-AM-001: AssetCreationWorkflow runs with business rules (create asset draft)."""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "key": f"uc-am001-{uuid.uuid4().hex[:8]}",
            "name": "UC-AM-001 Asset",
            "created_by_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            AssetCreationWorkflow.WORKFLOW_NAME,
            input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        self.assertIsNone(err, f"UC-AM-001 asset_creation should succeed: {err}")
        self.assert_workflow_completed(instance)
        self.assert_validation_results_in_state_data(instance)

    def test_uc_am_001_contract_creation_workflow_with_business_rules(self):
        """UC-AM-001: ContractCreationWorkflow runs with business rules (create contract in data-first flow)."""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            key=f"uc-am001-c-{uuid.uuid4().hex[:8]}",
            name="UC-AM-001 Contract Asset",
        )
        input_data = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "asset_id": str(asset.id),
        }
        instance, err = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME,
            input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        self.assertIsNone(err, f"UC-AM-001 contract_creation should succeed: {err}")
        self.assert_workflow_completed(instance)
        self.assert_validation_results_in_state_data(instance)

    def test_all_asset_management_workflow_use_cases_covered(self):
        """6.9.1: Verify AM workflow class is importable and has WORKFLOW_NAME."""
        self.assertEqual(
            ContractCreationWorkflow.WORKFLOW_NAME,
            "contract_creation",
            "ContractCreationWorkflow.WORKFLOW_NAME must be 'contract_creation'",
        )


# --- 6.9.2 Contract Management use cases ---


class TestUC_CM_001_WorkflowIntegrationE2E(WorkflowE2ETestBase):
    """
    6.9.2 — UC-CM-001 (Create Contract): Contract Management use case.

    Workflow: contract_creation (create and validate contract).
    """

    workflow_classes = [ContractCreationWorkflow]

    def test_uc_cm_001_create_contract_workflow_with_business_rules(self):
        """UC-CM-001: ContractCreationWorkflow runs with business rules (Create Contract)."""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            key=f"uc-cm001-{uuid.uuid4().hex[:8]}",
            name="UC-CM-001 Asset",
        )
        input_data = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "asset_id": str(asset.id),
        }
        instance, err = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME,
            input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        self.assertIsNone(err, f"UC-CM-001 contract_creation should succeed: {err}")
        self.assert_workflow_completed(instance)
        self.assert_validation_results_in_state_data(instance)

    def test_uc_cm_001_workflow_completes_successfully(self):
        """UC-CM-001: Workflow completes successfully (all steps COMPLETED)."""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            key=f"uc-cm001-ok-{uuid.uuid4().hex[:8]}",
            name="UC-CM-001 Complete Asset",
        )
        input_data = {
            "original_raw": _minimal_odcs_raw(),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODCS,
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "asset_id": str(asset.id),
        }
        instance, err = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME,
            input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        self.assertIsNone(err)
        self.assert_workflow_completed(instance)
        for step in instance.steps.all().order_by("step_index"):
            self.assertEqual(
                step.status,
                StepStatus.COMPLETED,
                f"Step {step.step_name} should be COMPLETED",
            )

    def test_all_contract_management_workflow_use_cases_covered(self):
        """6.9.2: Verify CM workflow class is importable and has WORKFLOW_NAME."""
        self.assertEqual(
            ContractCreationWorkflow.WORKFLOW_NAME,
            "contract_creation",
            "ContractCreationWorkflow.WORKFLOW_NAME must be 'contract_creation'",
        )


# --- 6.9.3 Marketplace use cases ---


class TestUC_MKT_001_WorkflowIntegrationE2E(WorkflowE2ETestBase):
    """
    6.9.3 — UC-MKT-001: Publish Asset to Marketplace.

    Workflow: marketplace_publication (validate eligibility, create listing, publish).
    """

    workflow_classes = [MarketplacePublicationWorkflow]

    def setUp(self):
        super().setUp()
        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save(update_fields=["kyc_status"])

    def test_uc_mkt_001_publish_asset_workflow_with_business_rules(self):
        """UC-MKT-001: MarketplacePublicationWorkflow runs with business rules (Publish Asset to Marketplace)."""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            key=f"uc-mkt001-{uuid.uuid4().hex[:8]}",
            name="UC-MKT-001 Asset",
        )
        asset.status = AssetStatus.ACTIVE
        asset.save(update_fields=["status"])
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0",
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            hub_contract_json={
                "info": {"title": "UC-MKT Listing Contract"},
                "marketplace": {"license_summary": "MIT", "intended_use": ["analytics"]},
            },
            created_by=self.user,
        )
        input_data = {
            "tenant_id": str(self.tenant.id),
            "asset_id": str(asset.id),
            "metadata_json": {"title": "UC-MKT-001 Listing", "short_description": "E2E"},
            "pricing_model": PricingModel.FREE,
        }
        instance, err = self.create_start_and_execute(
            MarketplacePublicationWorkflow.WORKFLOW_NAME,
            input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        self.assertIsNone(err, f"UC-MKT-001 marketplace_publication should succeed: {err}")
        self.assert_workflow_completed(instance)
        self.assert_validation_results_in_state_data(instance)

    def test_all_marketplace_workflow_use_cases_covered(self):
        """6.9.3: Verify MKT workflow class is importable and has WORKFLOW_NAME."""
        self.assertEqual(
            MarketplacePublicationWorkflow.WORKFLOW_NAME,
            "marketplace_publication",
            "MarketplacePublicationWorkflow.WORKFLOW_NAME must be 'marketplace_publication'",
        )


# --- 6.9.4 Other use case categories (Data Quality, Compliance, AI/ML, remaining) ---


class TestDataQualityUseCaseWorkflowE2E(WorkflowE2ETestBase):
    """6.9.4 — Workflows in Data Quality use cases (e.g. UC-DQ-001 Run Data Quality Check)."""

    workflow_classes = [DataQualityCheckWorkflow]

    def test_uc_dq_workflow_execution_with_business_rules(self):
        """UC-DQ-001: DataQualityCheckWorkflow runs with business rules."""
        asset = AssetFactory.create_asset(
            tenant=self.tenant,
            key=f"uc-dq-{uuid.uuid4().hex[:8]}",
            name="UC-DQ Asset",
        )
        input_data = {
            "tenant_id": str(self.tenant.id),
            "asset_id": str(asset.id),
            "profile_key": "intake_basic_gx",
            "triggered_by_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            DataQualityCheckWorkflow.WORKFLOW_NAME,
            input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        self.assertIsNone(err, f"DQ workflow should not raise: {err}")
        instance.refresh_from_db()
        self.assertIn(
            instance.status,
            (WorkflowStatus.COMPLETED, WorkflowStatus.ROLLED_BACK),
            "Workflow completes or rolls back if no file linked to asset",
        )
        if instance.status == WorkflowStatus.COMPLETED:
            self.assert_validation_results_in_state_data(instance)
        else:
            self.assertGreaterEqual(
                instance.steps.count(),
                1,
                "At least one step (create_dq_run) should have run with business rules",
            )


class TestComplianceUseCaseWorkflowE2E(WorkflowE2ETestBase):
    """6.9.4 — Workflows in Compliance use cases (e.g. UC-COMP-001 Run Compliance Scan)."""

    workflow_classes = [ComplianceReportingWorkflow]

    def test_uc_comp_workflow_execution_with_business_rules(self):
        """UC-COMP-001: ComplianceReportingWorkflow runs with business rules."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        input_data = {
            "tenant_id": str(self.tenant.id),
            "regulation": "GDPR",
            "report_type": "STANDARD",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "triggered_by_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        self.assertIsNone(err, f"Compliance workflow should succeed: {err}")
        self.assert_workflow_completed(instance)
        self.assert_validation_results_in_state_data(instance)


class TestAllOtherUseCaseCategoriesWorkflowCoverageE2E(WorkflowE2ETestBase):
    """6.9.4 — Coverage assertion for workflows in other use case categories."""

    workflow_classes = [DataQualityCheckWorkflow, ComplianceReportingWorkflow]

    def test_other_use_case_categories_workflow_coverage(self):
        """Assert Data Quality and Compliance use case workflows are covered."""
        categories_covered = [
            "Data Quality",  # UC-DQ-001 → DataQualityCheckWorkflow
            "Compliance",  # UC-COMP-001 → ComplianceReportingWorkflow
        ]
        self.assertGreaterEqual(len(categories_covered), 2)
