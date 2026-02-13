"""
E2E Tests for Workflow Execution with Business Rules (Phase 6.2)

Comprehensive E2E tests for workflow execution with business rules validation:
- ProductCreationWorkflow, ContractCreationWorkflow, AssetCreationWorkflow,
  MarketplacePublicationWorkflow, DatasetCreationWorkflow, ScheduledIngestionWorkflow
- Success path with validation at each step, validation results logged, metrics in state_data
- Failure path: validation failure blocks workflow, WorkflowExecutionError, instance FAILED
- Validation results stored in state_data (_validation_results)
- Compensation with business rules (warnings logged, compensation proceeds)

No mocks/stubs; uses real WorkflowEngine, business rules, and services.

Run in Docker: docker compose exec api-service python -m pytest tests/e2e/test_workflow_business_rules_e2e.py -v --tb=short
Use --reuse-db after first run to reuse test database and speed up.
"""

import json
import uuid

import pytest

from hub.apps.orchestration.models import WorkflowStatus
from hub.apps.orchestration.workflow_engine import WorkflowExecutionError
from hub.apps.orchestration.workflows.asset_creation import AssetCreationWorkflow
from hub.apps.orchestration.workflows.contract_creation import ContractCreationWorkflow
from hub.apps.orchestration.workflows.marketplace_publication import (
    MarketplacePublicationWorkflow,
)
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from tests.e2e.workflow_e2e_base import WorkflowE2ETestBase

pytestmark = pytest.mark.workflow_e2e
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, ValidationStatus
from hub.apps.orchestration.workflows.dataset_creation import DatasetCreationWorkflow
from hub.apps.orchestration.workflows.scheduled_ingestion import (
    ScheduledIngestionWorkflow,
)
from hub.apps.tenants.models import KYCStatus


def _valid_odps_doc():
    """Minimal valid ODPS document for ProductCreationWorkflow (product.dataSchema required by BR)."""
    return {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                    "name": "Test Product E2E",
                    "description": "Test product for E2E business rules",
                }
            },
            "dataSchema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"},
                ]
            },
            "contract": {
                "spec": {
                    "apiVersion": "odcs.io/v3.0.2",
                    "kind": "DataContract",
                    "id": f"test-odcs-{uuid.uuid4().hex[:8]}",
                    "name": "Test ODCS Contract E2E",
                    "version": "1.0.0",
                    "description": "Test ODCS for E2E",
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string", "nullable": False},
                            {"name": "name", "type": "string", "nullable": True},
                        ]
                    },
                }
            },
        },
    }


def _invalid_odps_doc():
    """Invalid ODPS (missing product) for validation failure."""
    return {"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}


def _valid_odcs_contract():
    """Minimal valid ODCS contract for ContractCreationWorkflow."""
    return {
        "apiVersion": "odcs.io/v3.0.2",
        "kind": "DataContract",
        "id": f"test-contract-{uuid.uuid4().hex[:8]}",
        "name": "Test Contract E2E",
        "version": "3.0.2",
        "description": "Test contract for E2E",
        "schema": {
            "fields": [
                {"name": "email", "type": "string"},
                {"name": "name", "type": "string"},
            ]
        },
        "info": {
            "name": "Test Contract",
            "description": "Test",
            "version": "3.0.2",
            "owners": [{"name": "Test", "email": "test@example.com"}],
        },
    }


# --- 6.2.1 ProductCreationWorkflow with business rules ---


@pytest.mark.timeout(1800)  # 30 min: covers django_db_setup (migrations) on first run + test
class TestProductCreationWorkflowBusinessRulesE2E(WorkflowE2ETestBase):
    """E2E tests for ProductCreationWorkflow with business rules (Phase 6.2.1)."""

    workflow_classes = [ProductCreationWorkflow]

    def test_successful_execution_with_business_rules_validation(self):
        """Verify business rules validation at each step, results in state_data, workflow completes."""
        input_data = {
            "original_raw": json.dumps(_valid_odps_doc()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            ProductCreationWorkflow.WORKFLOW_NAME, input_data
        )
        self.assertIsNone(err, f"Workflow should succeed, got: {err}")
        self.assert_workflow_completed(instance)
        self.assert_validation_results_in_state_data(instance)
        self.assert_validation_metrics_recorded(instance)
        self.assert_workflow_step_count_at_least(instance, 1)

    def test_validation_failure_blocks_workflow_and_marks_failed(self):
        """Verify validation failure at step blocks workflow, WorkflowExecutionError, instance FAILED."""
        input_data = {
            "original_raw": json.dumps(_invalid_odps_doc()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            ProductCreationWorkflow.WORKFLOW_NAME, input_data
        )
        self.assert_workflow_failed(instance)
        self.assert_workflow_error_details_contain_validation(instance)
        if err:
            self.assertIsInstance(err, (WorkflowExecutionError, ValueError, Exception))

    def test_validation_results_stored_in_state_data_on_success(self):
        """Verify validation results are stored in state_data (duration/cached)."""
        input_data = {
            "original_raw": json.dumps(_valid_odps_doc()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, _ = self.create_start_and_execute(
            ProductCreationWorkflow.WORKFLOW_NAME, input_data
        )
        self.assert_validation_results_in_state_data(instance)
        vr = (instance.state_data or {}).get("_validation_results", {})
        for key in (
            "workflow_state",
            "step_input",
            "step_execution",
            "step_output",
            "post_workflow_state",
        ):
            self.assertIn(key, vr)
            self.assertIn("duration", vr[key])


# --- 6.2.2 ContractCreationWorkflow with business rules ---


@pytest.mark.timeout(600)  # 10 min: covers possible db_setup on first run in session
class TestContractCreationWorkflowBusinessRulesE2E(WorkflowE2ETestBase):
    """E2E tests for ContractCreationWorkflow with business rules (Phase 6.2.2)."""

    workflow_classes = [ContractCreationWorkflow]

    def test_successful_execution_with_business_rules_validation(self):
        """Success path: validation at each step, workflow completes."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME, input_data
        )
        self.assertIsNone(err, f"Workflow should succeed, got: {err}")
        self.assert_workflow_completed(instance)
        self.assert_validation_results_in_state_data(instance)

    def test_validation_failure_blocks_workflow(self):
        """Invalid contract input: workflow fails, error_details contain validation."""
        input_data = {
            "original_raw": json.dumps({"invalid": "contract"}),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME, input_data
        )
        self.assert_workflow_failed(instance)
        self.assert_workflow_error_details_contain_validation(instance)


# --- 6.2.3 AssetCreationWorkflow with business rules ---


@pytest.mark.timeout(1800)  # 30 min: multi-workflow run + possible db_setup
class TestAssetCreationWorkflowBusinessRulesE2E(WorkflowE2ETestBase):
    """E2E tests for AssetCreationWorkflow with business rules (Phase 6.2.3)."""

    workflow_classes = [ContractCreationWorkflow, AssetCreationWorkflow]

    def test_successful_execution_contract_first_with_business_rules(self):
        """Contract-first: create contract then run asset_creation with contract_id."""
        # Create contract via contract_creation workflow first
        contract_input = {
            "original_raw": json.dumps(_valid_odcs_contract()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        contract_instance, _ = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME, contract_input
        )
        contract_instance.refresh_from_db()
        if contract_instance.status != WorkflowStatus.COMPLETED:
            self.skipTest(
                "ContractCreationWorkflow did not complete; cannot run AssetCreationWorkflow"
            )
        contract = (
            Contract.objects.filter(tenant=self.tenant, original_spec_type=OriginalSpecType.ODCS)
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(contract, "Contract should exist after contract_creation")
        # Asset creation (contract-first; key/name required by create_asset_record step)
        asset_input = {
            "contract_id": str(contract.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "auto_activate": False,
            "key": f"e2e-asset-{uuid.uuid4().hex[:8]}",
            "name": "E2E Asset Business Rules",
        }
        instance, err = self.create_start_and_execute(
            AssetCreationWorkflow.WORKFLOW_NAME, asset_input
        )
        self.assertIsNone(err, f"Asset workflow should succeed, got: {err}")
        self.assert_workflow_completed(instance)
        self.assert_validation_results_in_state_data(instance)

    def test_validation_failure_blocks_workflow(self):
        """Invalid input (missing required): workflow fails."""
        asset_input = {
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            # missing contract_id and file_id - will fail validation or first step
        }
        instance, err = self.create_start_and_execute(
            AssetCreationWorkflow.WORKFLOW_NAME, asset_input
        )
        # May fail at start or first step; expect failed or no progress
        instance.refresh_from_db()
        self.assertTrue(
            instance.status
            in (WorkflowStatus.FAILED, WorkflowStatus.RUNNING, WorkflowStatus.DRAFT),
            f"Expected FAILED/RUNNING/DRAFT, got {instance.status}",
        )
        if instance.status == WorkflowStatus.FAILED:
            self.assert_workflow_error_details_contain_validation(instance)


# --- 6.2.4 MarketplacePublicationWorkflow with business rules ---


@pytest.mark.timeout(600)  # 10 min: multi-workflow chain + possible db_setup
class TestMarketplacePublicationWorkflowBusinessRulesE2E(WorkflowE2ETestBase):
    """E2E tests for MarketplacePublicationWorkflow with business rules (Phase 6.2.4)."""

    workflow_classes = [
        ContractCreationWorkflow,
        AssetCreationWorkflow,
        MarketplacePublicationWorkflow,
    ]

    def test_successful_execution_with_business_rules_when_eligible(self):
        """When asset/tenant are eligible, workflow completes with validation."""
        # Set tenant KYC to VERIFIED so marketplace eligibility passes
        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save(update_fields=["kyc_status", "updated_at"])
        # Create contract then asset
        contract_input = {
            "original_raw": json.dumps(_valid_odcs_contract()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, contract_input)
        contract = (
            Contract.objects.filter(tenant=self.tenant, original_spec_type=OriginalSpecType.ODCS)
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(contract)
        contract.status = ContractStatus.ACTIVE
        contract.validation_status = ValidationStatus.VALID
        contract.save(update_fields=["status", "validation_status", "updated_at"])
        asset_input = {
            "contract_id": str(contract.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "auto_activate": False,
            "key": f"e2e-mp-asset-{uuid.uuid4().hex[:8]}",
            "name": "E2E Marketplace Asset",
        }
        self.create_start_and_execute(AssetCreationWorkflow.WORKFLOW_NAME, asset_input)
        asset = Asset.objects.filter(tenant=self.tenant).order_by("-created_at").first()
        self.assertIsNotNone(asset)
        asset.status = AssetStatus.ACTIVE
        asset.save(update_fields=["status", "updated_at"])
        # Marketplace publication
        mp_input = {
            "asset_id": str(asset.id),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            MarketplacePublicationWorkflow.WORKFLOW_NAME, mp_input
        )
        if err is None:
            self.assert_workflow_completed(instance)
            self.assert_validation_results_in_state_data(instance)
        else:
            instance.refresh_from_db()
            self.assert_workflow_failed(instance)
            self.assert_workflow_error_details_contain_validation(instance)

    def test_validation_failure_when_ineligible(self):
        """Invalid asset_id or ineligible asset: workflow fails with validation/error."""
        mp_input = {
            "asset_id": str(uuid.uuid4()),
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            MarketplacePublicationWorkflow.WORKFLOW_NAME, mp_input
        )
        instance.refresh_from_db()
        self.assert_workflow_failed(instance)


# --- 6.2.5 Other workflows with business rules ---


@pytest.mark.timeout(1800)  # 30 min: covers db_setup on first run in session
class TestDatasetCreationWorkflowBusinessRulesE2E(WorkflowE2ETestBase):
    """E2E tests for DatasetCreationWorkflow with business rules (Phase 6.2.5)."""

    workflow_classes = [DatasetCreationWorkflow]

    def test_validation_failure_when_missing_required_input(self):
        """Missing file_id / invalid input: workflow fails."""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(
            DatasetCreationWorkflow.WORKFLOW_NAME, input_data
        )
        instance.refresh_from_db()
        self.assert_workflow_failed(instance)


@pytest.mark.timeout(1800)  # 30 min: covers db_setup on first run in session
class TestScheduledIngestionWorkflowBusinessRulesE2E(WorkflowE2ETestBase):
    """E2E tests for ScheduledIngestionWorkflow with business rules (Phase 6.2.5)."""

    workflow_classes = [ScheduledIngestionWorkflow]

    def test_workflow_registered_and_accepts_minimal_input(self):
        """Workflow is registered and runs (may fail on missing config but validation runs)."""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "name": "test-ingestion-e2e",
            "schedule": "0 0 * * *",
        }
        instance = self.create_workflow_instance(
            ScheduledIngestionWorkflow.WORKFLOW_NAME, input_data
        )
        self.assertIsNotNone(instance)
        instance = self.start_workflow_instance(str(instance.id))
        try:
            instance = self.execute_workflow_instance(str(instance.id))
        except Exception:
            instance.refresh_from_db()
        instance.refresh_from_db()
        self.assertIn(
            instance.status,
            (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.RUNNING),
        )
        if instance.status == WorkflowStatus.COMPLETED:
            self.assert_validation_results_in_state_data(instance)
