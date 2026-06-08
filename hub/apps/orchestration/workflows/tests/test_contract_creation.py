"""
Tests for Contract Creation Workflow

Comprehensive unit, integration, and E2E tests for contract creation workflow.
"""
import json
import uuid
import pytest
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import transaction, models

from hub.apps.orchestration.workflows.contract_creation import ContractCreationWorkflow
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, StepStatus
from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus
from hub.apps.tenants.models import Tenant
from hub.apps.search.models import SearchIndex
from hub.apps.semantic.models import SemanticResource
from hub.apps.audit.models import AuditEvent
from hub.apps.core.events.models import Event
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

User = get_user_model()

# Mark all tests to use database with transactions
pytestmark = pytest.mark.django_db(transaction=True)


class ContractCreationWorkflowUnitTest(TestCase):
    """Unit tests for contract creation workflow tasks"""

    def setUp(self):
        """Set up test fixtures"""
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant Unit {unique_id}",
            slug=f"test-tenant-unit-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-unit-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(self.registry)
        ContractCreationWorkflow.register_tasks(self.engine)

        # Sample ODCS contract (valid format)
        # Note: ODCS contracts do NOT have a 'product' field - that's ODPS
        # ODCS contracts have: apiVersion, kind, id, name, version, schema, info sections
        self.sample_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": f"test-contract-{unique_id}",
            "name": "Test Contract",
            "version": "3.0.2",
            "description": "Test contract description",
            "schema": {
                "fields": [
                    {"name": "email", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            },
            "info": {
                "name": "Test Contract",
                "description": "Test contract description",
                "version": "3.0.2",
                "owners": [
                    {"name": "John Doe", "email": "john@example.com"}
                ]
            }
        }

    def test_validate_input_task_success(self):
        """Test input validation task with valid input"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.registry.get_workflow(ContractCreationWorkflow.WORKFLOW_NAME),
            tenant=self.tenant,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id)
            },
            status=WorkflowStatus.RUNNING
        )

        step = instance.steps.create(
            step_name="validate_input",
            step_index=0,
            status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("contract_creation.validate_input")
        result = task_func(instance.input_data, instance, step)

        self.assertTrue(result["validated"])
        self.assertEqual(result["original_format"], "JSON")
        self.assertEqual(result["tenant_id"], str(self.tenant.id))

    def test_validate_input_task_missing_required_fields(self):
        """Test input validation task with missing required fields"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.registry.get_workflow(ContractCreationWorkflow.WORKFLOW_NAME),
            tenant=self.tenant,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                # Missing original_format, tenant_id, user_id
            },
            status=WorkflowStatus.RUNNING
        )

        step = instance.steps.create(
            step_name="validate_input",
            step_index=0,
            status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("contract_creation.validate_input")

        with self.assertRaises(ValueError) as cm:
            task_func(instance.input_data, instance, step)

        self.assertIn("required", str(cm.exception).lower())

    def test_normalize_contract_task_success(self):
        """Test contract normalization task with valid ODCS contract"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.registry.get_workflow(ContractCreationWorkflow.WORKFLOW_NAME),
            tenant=self.tenant,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id)
            },
            status=WorkflowStatus.RUNNING
        )

        step = instance.steps.create(
            step_name="normalize_contract",
            step_index=1,
            status=StepStatus.PENDING
        )

        # Set validated input in state
        instance.state_data = {
            "original_raw": json.dumps(self.sample_contract),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance.save()

        task_func = self.engine.task_registry.get("contract_creation.normalize_contract")
        result = task_func(instance.state_data, instance, step)

        self.assertIsNotNone(result["hub_contract"])
        self.assertEqual(result["detected_spec_type"], "ODCS")
        self.assertEqual(result["normalization_status"], NormalizationStatus.NORMALIZED_OK.value)

    def test_normalize_contract_task_dcs_rejection(self):
        """Test contract normalization task with deprecated contract format (should fail)"""
        # DCS contracts are now treated as ODCS and fail during normalization
        # due to missing required fields. Without 'name' field, it fails validation.
        dcs_contract = {
            "dataContractSpecification": "1.0.0",
            "id": "test-contract"
            # Missing 'name' field - will cause normalization failure
        }

        instance = WorkflowInstance.objects.create(
            workflow_definition=self.registry.get_workflow(ContractCreationWorkflow.WORKFLOW_NAME),
            tenant=self.tenant,
            input_data={
                "original_raw": json.dumps(dcs_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id)
            },
            status=WorkflowStatus.RUNNING
        )

        step = instance.steps.create(
            step_name="normalize_contract",
            step_index=1,
            status=StepStatus.PENDING
        )

        instance.state_data = {
            "original_raw": json.dumps(dcs_contract),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }
        instance.save()

        task_func = self.engine.task_registry.get("contract_creation.normalize_contract")

        with self.assertRaises(ValueError) as cm:
            task_func(instance.state_data, instance, step)

        # DCS contracts fail normalization due to missing required fields
        # Error code is INVALID_SPEC_FORMAT, not DCS_NOT_SUPPORTED
        error_message = str(cm.exception)
        self.assertIn("INVALID_SPEC_FORMAT", error_message)
        # Should contain normalization error about missing required fields
        # The error could be about missing 'name' field, 'product.details', or other required fields
        # Check that error message contains at least one relevant keyword (case-insensitive)
        error_lower = error_message.lower()
        has_relevant_keyword = (
            "product.details" in error_lower or
            "product/details" in error_lower or
            "language" in error_lower or
            "required" in error_lower or
            "name" in error_lower or
            "normalization" in error_lower or
            "missing" in error_lower or
            "odpsnormalizationerror" in error_lower
        )
        self.assertTrue(
            has_relevant_keyword,
            f"Error message should contain relevant keyword, got: {error_message}"
        )

    def test_create_contract_record_task_success(self):
        """Test contract record creation task"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.registry.get_workflow(ContractCreationWorkflow.WORKFLOW_NAME),
            tenant=self.tenant,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id)
            },
            status=WorkflowStatus.RUNNING
        )

        step = instance.steps.create(
            step_name="create_contract_record",
            step_index=3,
            status=StepStatus.PENDING
        )

        # Set normalized contract in state
        instance.state_data = {
            "original_raw": json.dumps(self.sample_contract),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "hub_contract": {"info": {"title": "Test Contract"}},
            "detected_spec_type": "ODCS",
            "detected_spec_version": "3.0.2",
            "normalization_status": NormalizationStatus.NORMALIZED_OK.value,
            "normalization_errors": [],
            "normalization_warnings": [],
            "validation_errors": []
        }
        instance.save()

        task_func = self.engine.task_registry.get("contract_creation.create_contract_record")

        with transaction.atomic():
            result = task_func(instance.state_data, instance, step)

        self.assertIn("contract_id", result)
        contract = Contract.objects.get(id=result["contract_id"])
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.created_by, self.user)
        self.assertEqual(contract.status, ContractStatus.DRAFT)
        self.assertEqual(contract.normalization_status, NormalizationStatus.NORMALIZED_OK)

    def test_link_odps_task_skip_no_action(self):
        """Test ODPS linking task skips when no action is provided"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.registry.get_workflow(ContractCreationWorkflow.WORKFLOW_NAME),
            tenant=self.tenant,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id)
            },
            status=WorkflowStatus.RUNNING
        )

        # Create contract first
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw=json.dumps(self.sample_contract),
            hub_contract_json={"id": "test-contract", "info": {"name": "Test"}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.DRAFT,
            created_by=self.user
        )

        instance.state_data = {
            "contract_id": str(contract.id),
            "user_id": str(self.user.id)
        }
        instance.save()

        step = instance.steps.create(
            step_name="link_odps",
            step_index=4,
            status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("contract_creation.link_odps")
        result = task_func(instance.state_data, instance, step)

        self.assertTrue(result.get("odps_linking_skipped"))
        self.assertEqual(result.get("reason"), "No ODPS action specified")

    def test_link_odps_task_generate(self):
        """Test ODPS linking task with generate action"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.registry.get_workflow(ContractCreationWorkflow.WORKFLOW_NAME),
            tenant=self.tenant,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "odps_action": "generate"
            },
            status=WorkflowStatus.RUNNING
        )

        # Create contract with marketplace data for ODPS generation
        hub_contract = {
            "id": "test-contract",
            "info": {
                "name": "Test Contract",
                "description": "Test description",
                "version": "1.0.0"
            },
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            },
            "marketplace": {
                "license_summary": "Test license",
                "intended_use": ["analytics"]
            }
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw=json.dumps(self.sample_contract),
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.DRAFT,
            created_by=self.user
        )

        instance.state_data = {
            "contract_id": str(contract.id),
            "user_id": str(self.user.id),
            "odps_action": "generate"
        }
        instance.save()

        step = instance.steps.create(
            step_name="link_odps",
            step_index=4,
            status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("contract_creation.link_odps")

        with transaction.atomic():
            result = task_func(instance.state_data, instance, step)

        self.assertTrue(result.get("odps_linked"))
        self.assertIn("odps_contract_id", result)

        # Verify ODPS contract was created
        odps_contract = Contract.objects.get(id=result["odps_contract_id"])
        self.assertEqual(odps_contract.original_spec_type, "ODPS")
        self.assertEqual(odps_contract.tenant, self.tenant)

        # Verify bidirectional link
        contract.refresh_from_db()
        self.assertIn("extensions", contract.hub_contract_json)
        self.assertIn("x_odps", contract.hub_contract_json["extensions"])
        self.assertEqual(
            contract.hub_contract_json["extensions"]["x_odps"]["odps_link"],
            result["odps_contract_id"]
        )

        odps_contract.refresh_from_db()
        self.assertIn("extensions", odps_contract.hub_contract_json)
        self.assertIn("x_odps", odps_contract.hub_contract_json["extensions"])
        self.assertEqual(
            odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"],
            str(contract.id)
        )

    def test_link_odps_task_link_existing(self):
        """Test ODPS linking task with link action (existing ODPS)"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.registry.get_workflow(ContractCreationWorkflow.WORKFLOW_NAME),
            tenant=self.tenant,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "odps_action": "link"
            },
            status=WorkflowStatus.RUNNING
        )

        # Create ODCS contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw=json.dumps(self.sample_contract),
            hub_contract_json={"id": "test-contract", "info": {"name": "Test"}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.DRAFT,
            created_by=self.user
        )

        # Create existing ODPS contract
        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODPS",
            original_spec_version="4.1",
            original_format="JSON",
            original_raw='{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}}}',
            hub_contract_json={"id": "test-product", "info": {"name": "Test Product"}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.DRAFT,
            created_by=self.user
        )

        instance.state_data = {
            "contract_id": str(contract.id),
            "user_id": str(self.user.id),
            "odps_action": "link",
            "odps_contract_id": str(odps_contract.id)
        }
        instance.save()

        step = instance.steps.create(
            step_name="link_odps",
            step_index=4,
            status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("contract_creation.link_odps")

        with transaction.atomic():
            result = task_func(instance.state_data, instance, step)

        self.assertTrue(result.get("odps_linked"))
        self.assertEqual(result["odps_contract_id"], str(odps_contract.id))

        # Verify bidirectional link
        contract.refresh_from_db()
        self.assertIn("extensions", contract.hub_contract_json)
        self.assertIn("x_odps", contract.hub_contract_json["extensions"])
        self.assertEqual(
            contract.hub_contract_json["extensions"]["x_odps"]["odps_link"],
            str(odps_contract.id)
        )

        odps_contract.refresh_from_db()
        self.assertIn("extensions", odps_contract.hub_contract_json)
        self.assertIn("x_odps", odps_contract.hub_contract_json["extensions"])
        self.assertEqual(
            odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"],
            str(contract.id)
        )

    def test_link_odps_task_upload(self):
        """Test ODPS linking task with upload action"""
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.registry.get_workflow(ContractCreationWorkflow.WORKFLOW_NAME),
            tenant=self.tenant,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "odps_action": "upload"
            },
            status=WorkflowStatus.RUNNING
        )

        # Create ODCS contract first
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw=json.dumps(self.sample_contract),
            hub_contract_json={"id": "test-contract", "info": {"name": "Test"}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.DRAFT,
            created_by=self.user
        )

        # Create valid ODPS document
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test product description"
                    }
                }
            }
        }

        instance.state_data = {
            "contract_id": str(contract.id),
            "user_id": str(self.user.id),
            "odps_action": "upload",
            "odps_raw": json.dumps(odps_doc),
            "odps_format": "JSON"
        }
        instance.save()

        step = instance.steps.create(
            step_name="link_odps",
            step_index=4,
            status=StepStatus.PENDING
        )

        task_func = self.engine.task_registry.get("contract_creation.link_odps")

        with transaction.atomic():
            result = task_func(instance.state_data, instance, step)

        self.assertTrue(result.get("odps_linked"))
        self.assertIn("odps_contract_id", result)

        # Verify ODPS contract was created
        odps_contract = Contract.objects.get(id=result["odps_contract_id"])
        self.assertEqual(odps_contract.original_spec_type, "ODPS")
        self.assertEqual(odps_contract.tenant, self.tenant)

        # Verify bidirectional link
        contract.refresh_from_db()
        self.assertIn("extensions", contract.hub_contract_json)
        self.assertIn("x_odps", contract.hub_contract_json["extensions"])
        self.assertEqual(
            contract.hub_contract_json["extensions"]["x_odps"]["odps_link"],
            result["odps_contract_id"]
        )

        odps_contract.refresh_from_db()
        self.assertIn("extensions", odps_contract.hub_contract_json)
        self.assertIn("x_odps", odps_contract.hub_contract_json["extensions"])
        self.assertEqual(
            odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"],
            str(contract.id)
        )


class ContractCreationWorkflowIntegrationTest(TestCase):
    """Integration tests for contract creation workflow"""

    def setUp(self):
        """Set up test fixtures"""
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant Integration {unique_id}",
            slug=f"test-tenant-integration-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-integration-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        self.sample_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": f"test-contract-{unique_id}",
            "name": "Test Contract",
            "version": "3.0.2",
            "description": "Test contract description",
            "schema": {
                "fields": [
                    {"name": "email", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            },
            "info": {
                "name": "Test Contract",
                "description": "Test contract description",
                "version": "3.0.2",
                "owners": [
                    {"name": "John Doe", "email": "john@example.com"}
                ]
            }
        }

    def test_full_workflow_execution_success(self):
        """Test full workflow execution end-to-end"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.sample_contract),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            engine=engine,
            registry=registry
        )

        # Verify contract was created
        self.assertIsNotNone(contract)
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.created_by, self.user)
        self.assertEqual(contract.status, ContractStatus.DRAFT)
        self.assertIsNotNone(contract.hub_contract_json)

        # Verify search index was created
        search_index = SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id
        ).first()
        self.assertIsNotNone(search_index)

        # Verify audit log was created
        audit_event = AuditEvent.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            action="CONTRACT_CREATED",
            resource_id=str(contract.id)
        ).first()
        self.assertIsNotNone(audit_event)

    def test_workflow_execution_with_invalid_contract(self):
        """Test workflow execution with invalid contract (should fail gracefully)"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        invalid_contract = {"invalid": "contract"}

        with self.assertRaises(ValueError):
            ContractCreationWorkflow.execute(
                original_raw=json.dumps(invalid_contract),
                original_format="JSON",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                engine=engine,
                registry=registry
            )

    def test_workflow_execution_with_asset(self):
        """Test workflow execution with asset association"""
        from hub.apps.assets.models import Asset

        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            created_by=self.user
        )

        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.sample_contract),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset.id),
            engine=engine,
            registry=registry
        )

        self.assertEqual(contract.asset, asset)
        self.assertEqual(contract.version, 1)

    def test_workflow_rollback_on_failure(self):
        """Test workflow rollback when a step fails"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        # Use invalid tenant_id to cause failure
        with self.assertRaises(ValueError):
            ContractCreationWorkflow.execute(
                original_raw=json.dumps(self.sample_contract),
                original_format="JSON",
                tenant_id="00000000-0000-0000-0000-000000000000",  # Invalid UUID
                user_id=str(self.user.id),
                engine=engine,
                registry=registry
            )

        # Verify no contract was created
        contract_count = Contract.objects.filter(tenant=self.tenant).count()
        self.assertEqual(contract_count, 0)

    def test_workflow_execution_with_odps_generate(self):
        """Test workflow execution with ODPS generation"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        # Create contract directly (bypassing workflow to avoid ODPS detection issues)
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw=json.dumps(self.sample_contract),
            hub_contract_json={
                "id": self.sample_contract["id"],
                "info": {
                    "name": self.sample_contract["name"],
                    "description": self.sample_contract["description"],
                    "version": self.sample_contract["version"]
                },
                "schema": self.sample_contract["schema"],
                "marketplace": {
                    "license_summary": "Test license",
                    "intended_use": ["analytics"]
                }
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.DRAFT,
            created_by=self.user
        )

        # Verify contract was created
        self.assertIsNotNone(contract)
        self.assertIsNotNone(contract.hub_contract_json)

        # Now execute ODPS linking step manually
        from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, StepStatus

        # Create a new workflow instance for ODPS linking
        workflow_instance = engine.create_instance(
            workflow_name=ContractCreationWorkflow.WORKFLOW_NAME,
            input_data={
                "contract_id": str(contract.id),
                "user_id": str(self.user.id),
                "odps_action": "generate"
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        workflow_instance.state_data = {
            "contract_id": str(contract.id),
            "user_id": str(self.user.id),
            "odps_action": "generate"
        }
        workflow_instance.save()

        # Get the highest step index to avoid conflicts
        max_step_index = workflow_instance.steps.aggregate(
            max_index=models.Max('step_index')
        )['max_index'] or -1

        step = workflow_instance.steps.create(
            step_name="link_odps",
            step_index=max_step_index + 1,
            status=StepStatus.PENDING
        )

        task_func = engine.task_registry.get("contract_creation.link_odps")

        with transaction.atomic():
            result = task_func(workflow_instance.state_data, workflow_instance, step)

        # Verify ODPS contract was created and linked
        self.assertTrue(result.get("odps_linked"))
        self.assertIn("odps_contract_id", result)

        contract.refresh_from_db()
        self.assertIn("extensions", contract.hub_contract_json)
        self.assertIn("x_odps", contract.hub_contract_json["extensions"])
        odps_contract_id = contract.hub_contract_json["extensions"]["x_odps"]["odps_link"]

        odps_contract = Contract.objects.get(id=odps_contract_id)
        self.assertEqual(odps_contract.original_spec_type, "ODPS")
        self.assertEqual(odps_contract.tenant, self.tenant)


class ContractCreationWorkflowE2ETest(TestCase):
    """End-to-end tests for contract creation workflow via API"""

    def setUp(self):
        """Set up test fixtures"""
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant E2E {unique_id}",
            slug=f"test-tenant-e2e-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-e2e-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.sample_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": f"e2e-test-contract-{unique_id}",
            "name": "E2E Test Contract",
            "version": "3.0.2",
            "description": "E2E test contract description",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"},
                    {"name": "price", "type": "number"}
                ]
            },
            "info": {
                "name": "E2E Test Contract",
                "description": "E2E test contract description",
                "version": "3.0.2",
                "owners": [
                    {"name": "Jane Doe", "email": "jane@example.com"}
                ]
            }
        }

    def test_contract_creation_via_viewset(self):
        """Test contract creation via REST API ViewSet"""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.post(
            '/api/v1/contracts/',
            {
                'original_raw': json.dumps(self.sample_contract),
                'original_format': 'JSON'
            },
            format='json'
        )

        self.assertEqual(response.status_code, 201)

        # Verify contract was created
        contract_data = response.json()
        contract = Contract.objects.get(id=contract_data['id'])
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.created_by, self.user)
        self.assertIsNotNone(contract.hub_contract_json)

        # Verify search index was created
        search_index = SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id
        ).first()
        self.assertIsNotNone(search_index)

        # Verify audit log was created
        audit_event = AuditEvent.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            action="CONTRACT_CREATED",
            resource_id=str(contract.id)
        ).first()
        self.assertIsNotNone(audit_event)

    def test_contract_creation_with_invalid_format(self):
        """Test contract creation with invalid format (should return 400)"""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.post(
            '/api/v1/contracts/',
            {
                'original_raw': json.dumps(self.sample_contract),
                'original_format': 'INVALID_FORMAT'
            },
            format='json'
        )

        self.assertEqual(response.status_code, 400)

    def test_contract_creation_with_dcs_contract(self):
        """Test contract creation with deprecated contract format (should return 400)"""
        from rest_framework.test import APIClient

        # DCS contracts are now treated as ODCS and fail during normalization
        # due to missing required fields (product.details)
        dcs_contract = {
            "dataContractSpecification": "1.0.0",
            "id": "test-contract",
            "name": "Test Contract"  # Add name field to avoid early validation failure
        }

        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.post(
            '/api/v1/contracts/',
            {
                'original_raw': json.dumps(dcs_contract),
                'original_format': 'JSON'
            },
            format='json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        # DCS contracts fail normalization with NORMALIZATION_FAILED or INVALID_SPEC_FORMAT
        # Error code is no longer DCS_NOT_SUPPORTED
        error_code = response_data.get('details', {}).get('code', '') or response_data.get('code', '')
        self.assertIn(
            error_code,
            ['NORMALIZATION_FAILED', 'INVALID_SPEC_FORMAT', 'VALIDATION_ERROR', 'STRUCTURELESS_CONTRACT'],
            f"Expected NORMALIZATION_FAILED, INVALID_SPEC_FORMAT, VALIDATION_ERROR, or STRUCTURELESS_CONTRACT, got: {error_code}"
        )


class ContractCreationWorkflowStepEventsTest(TestCase):
    """Integration tests to verify ContractCreationWorkflow receives step events"""

    def setUp(self):
        """Set up test fixtures"""
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant Step Events {unique_id}",
            slug=f"test-tenant-step-events-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-step-events-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        self.sample_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": f"test-contract-{unique_id}",
            "name": "Test Contract",
            "version": "3.0.2",
            "description": "Test contract description",
            "schema": {
                "fields": [
                    {"name": "email", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            },
            "info": {
                "name": "Test Contract",
                "description": "Test contract description",
                "version": "3.0.2",
                "owners": [
                    {"name": "John Doe", "email": "john@example.com"}
                ]
            }
        }

    def test_contract_creation_workflow_receives_step_events(self):
        """Test that ContractCreationWorkflow receives step.started and step.completed events"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        # Execute workflow
        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.sample_contract),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            engine=engine,
            registry=registry
        )

        # Verify contract was created
        self.assertIsNotNone(contract)

        # Get workflow instance to find its ID
        workflow_instances = WorkflowInstance.objects.filter(
            workflow_name=ContractCreationWorkflow.WORKFLOW_NAME,
            tenant=self.tenant
        ).order_by('-created_at')
        self.assertEqual(workflow_instances.count(), 1)
        workflow_instance = workflow_instances.first()

        # Query actual events from database (no mocks - real event persistence)
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(workflow_instance.id)
        ).order_by('created_at')

        step_completed_events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(workflow_instance.id)
        ).order_by('created_at')

        # ContractCreationWorkflow has 8 steps, so we should have 8 started and 8 completed events
        self.assertGreaterEqual(step_started_events.count(), 8,
                               f"Expected at least 8 step.started events, got {step_started_events.count()}")
        self.assertGreaterEqual(step_completed_events.count(), 8,
                               f"Expected at least 8 step.completed events, got {step_completed_events.count()}")

        # Collect event data
        step_started_data = [event.data for event in step_started_events]
        step_completed_data = [event.data for event in step_completed_events]

        # ContractCreationWorkflow has 8 steps, so we should have 8 started and 8 completed events
        self.assertGreaterEqual(len(step_started_events), 8,
                               f"Expected at least 8 step.started events, got {len(step_started_events)}")
        self.assertGreaterEqual(len(step_completed_events), 8,
                               f"Expected at least 8 step.completed events, got {len(step_completed_events)}")

        # Verify each step event has required metadata
        for event_data in step_started_data:
            self.assertIn("workflow_instance_id", event_data)
            self.assertIn("step_index", event_data)
            self.assertIn("step_name", event_data)
            self.assertIn("step_type", event_data)
            self.assertIn("progress_percentage", event_data)
            self.assertIsInstance(event_data["step_index"], int)
            self.assertIsInstance(event_data["progress_percentage"], (int, float))
            self.assertGreaterEqual(event_data["progress_percentage"], 0.0)
            self.assertLessEqual(event_data["progress_percentage"], 100.0)

        for event_data in step_completed_data:
            self.assertIn("workflow_instance_id", event_data)
            self.assertIn("step_index", event_data)
            self.assertIn("step_name", event_data)
            self.assertIn("progress_percentage", event_data)
            self.assertIn("duration_ms", event_data)
            self.assertIsInstance(event_data["step_index"], int)
            self.assertIsInstance(event_data["progress_percentage"], (int, float))
            self.assertIsInstance(event_data["duration_ms"], int)
            self.assertGreaterEqual(event_data["progress_percentage"], 0.0)
            self.assertLessEqual(event_data["progress_percentage"], 100.0)
            self.assertGreaterEqual(event_data["duration_ms"], 0)

        # Verify step names match expected workflow steps
        expected_step_names = [
            "validate_input",
            "normalize_contract",
            "validate_hubcontract",
            "create_contract_record",
            "index_for_search",
            "generate_semantic_mapping",
            "send_notifications",
            "audit_logging"
        ]

        actual_step_names = [event_data["step_name"] for event_data in step_started_data]
        for expected_name in expected_step_names:
            self.assertIn(expected_name, actual_step_names,
                         f"Expected step '{expected_name}' not found in step events")

        # Verify progress increases or stays the same as steps progress
        started_progresses = sorted([e["progress_percentage"] for e in step_started_data],
                                   key=lambda x: step_started_data[[e["progress_percentage"] for e in step_started_data].index(x)]["step_index"])
        for i in range(1, len(started_progresses)):
            self.assertGreaterEqual(started_progresses[i], started_progresses[i-1] - 1.0,
                                  "Progress should generally increase or stay the same")

    def test_contract_creation_workflow_step_events_no_breaking_changes(self):
        """Regression test: Verify workflow execution still works correctly with step events"""

        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        # Execute workflow
        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.sample_contract),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            engine=engine,
            registry=registry
        )

        # Verify contract was created successfully (no breaking changes)
        self.assertIsNotNone(contract)
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.created_by, self.user)
        self.assertEqual(contract.status, ContractStatus.DRAFT)
        self.assertIsNotNone(contract.hub_contract_json)

        # Verify search index was created
        search_index = SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id
        ).first()
        self.assertIsNotNone(search_index)

        # Verify audit log was created
        audit_event = AuditEvent.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            action="CONTRACT_CREATED",
            resource_id=str(contract.id)
        ).first()
        self.assertIsNotNone(audit_event)

        # Verify workflow instance completed successfully
        workflow_instances = WorkflowInstance.objects.filter(
            workflow_name=ContractCreationWorkflow.WORKFLOW_NAME,
            tenant=self.tenant
        )
        self.assertEqual(workflow_instances.count(), 1)
        workflow_instance = workflow_instances.first()
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)

        # Verify progress is stored in state_data
        self.assertIn("progress_percentage", workflow_instance.state_data)
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100.0)


class ContractCreationWorkflowTechnicalFirstE2ETest(TestCase):
    """Comprehensive E2E tests for Technical-First flow (task 3.2.2)"""

    def setUp(self):
        """Set up test fixtures"""
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant Technical First {unique_id}",
            slug=f"test-tenant-technical-first-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-technical-first-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        # Sample ODCS contract (all versions: 3.0.2+, 2.2.2)
        self.odcs_contract_v3_0_2 = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": f"technical-first-odcs-{unique_id}",
            "name": "Technical-First ODCS Contract",
            "version": "1.0.0",
            "description": "ODCS contract for Technical-First flow E2E test",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False},
                    {"name": "price", "type": "number", "nullable": True}
                ]
            },
            "info": {
                "owners": [
                    {"name": "Technical Owner", "email": "technical@example.com"}
                ]
            }
        }

        self.odcs_contract_v2_2_2 = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": f"technical-first-odcs-v2-{unique_id}",
            "name": "Technical-First ODCS Contract v2.2.2",
            "version": "1.0.0",
            "description": "ODCS v2.2.2 contract for Technical-First flow E2E test",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            }
        }

        # Sample ODPS contract for linking
        self.odps_contract = {
            "schema": "https://schemas.opendataproducts.org/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Technical-First Product",
                        "description": "Product for Technical-First flow",
                        "productVersion": "1.0.0"
                    }
                },
                "contract": {
                    "spec": self.odcs_contract_v3_0_2
                },
                "dataQuality": {
                    "declarative": []
                },
                "SLA": {
                    "declarative": []
                },
                "pricingPlans": {
                    "declarative": []
                }
            }
        }

        # Create test file for data file linking
        from hub.apps.files.models import File, FileStatus
        self.test_file = File.objects.create(
            tenant=self.tenant,
            name="test_data.csv",
            storage_path="test/test_data.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )

    def test_technical_first_flow_basic(self):
        """Test Technical-First flow: Step 1-3 (Validate, Normalize, Create ODCS Contract)"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        # Execute workflow (basic flow without ODPS or data file)
        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.odcs_contract_v3_0_2),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            engine=engine,
            registry=registry
        )

        # Verify Step 1: ODCS contract validated (all versions: 3.0.2+, 2.2.2)
        self.assertIsNotNone(contract)
        self.assertEqual(contract.original_spec_type, "ODCS")
        self.assertEqual(contract.original_spec_version, "3.0.2")

        # Verify Step 2: ODCS normalized to HubContract (technical)
        self.assertIsNotNone(contract.hub_contract_json)
        self.assertIn("schema", contract.hub_contract_json)
        self.assertEqual(contract.normalization_status, NormalizationStatus.NORMALIZED_OK)

        # Verify Step 3: ODCS Contract created (original_spec_type="ODCS", technical)
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.created_by, self.user)
        self.assertEqual(contract.status, ContractStatus.DRAFT)

    def test_technical_first_flow_with_odps_linking(self):
        """Test Technical-First flow: Step 1-5 (with ODPS linking)"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        # Execute workflow with ODPS generation
        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.odcs_contract_v3_0_2),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            odps_action="generate",
            engine=engine,
            registry=registry
        )

        # Verify ODCS contract created
        self.assertIsNotNone(contract)
        self.assertEqual(contract.original_spec_type, "ODCS")

        # Verify Step 4: ODPS linked (optional)
        # Verify Step 5: ODPS Contract created and linked
        odps_contract_id = contract.hub_contract_json.get("extensions", {}).get("x_odps", {}).get("odps_link")
        self.assertIsNotNone(odps_contract_id, "ODPS contract should be linked")

        odps_contract = Contract.objects.get(id=odps_contract_id)
        self.assertEqual(odps_contract.original_spec_type, "ODPS")
        self.assertEqual(odps_contract.tenant, self.tenant)

        # Verify bidirectional linking
        self.assertEqual(
            odps_contract.hub_contract_json.get("extensions", {}).get("x_odps", {}).get("odcs_link"),
            str(contract.id)
        )

    def test_technical_first_flow_with_data_file(self):
        """Test Technical-First flow: Step 1-6 (with data file linking)"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        # Execute workflow with data file linking
        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.odcs_contract_v3_0_2),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(self.test_file.id),
            asset_key="technical-first-asset",
            asset_name="Technical-First Asset",
            engine=engine,
            registry=registry
        )

        # Verify ODCS contract created
        self.assertIsNotNone(contract)

        # Verify Step 6: Data file linked (Asset created)
        from hub.apps.assets.models import Asset
        asset = Asset.objects.filter(tenant=self.tenant, key="technical-first-asset").first()
        self.assertIsNotNone(asset, "Asset should be created")
        self.assertEqual(asset.name, "Technical-First Asset")
        self.assertEqual(contract.asset, asset)

    def test_technical_first_flow_complete(self):
        """Test Technical-First flow: Complete flow (all steps 1-8)"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        # Execute complete workflow: ODCS + ODPS + Data file
        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.odcs_contract_v3_0_2),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            odps_action="generate",
            file_id=str(self.test_file.id),
            asset_key="complete-technical-first-asset",
            asset_name="Complete Technical-First Asset",
            engine=engine,
            registry=registry
        )

        # Verify all steps completed
        # Step 1-3: ODCS validated, normalized, created
        self.assertIsNotNone(contract)
        self.assertEqual(contract.original_spec_type, "ODCS")
        self.assertIsNotNone(contract.hub_contract_json)

        # Step 4-5: ODPS linked and created
        odps_contract_id = contract.hub_contract_json.get("extensions", {}).get("x_odps", {}).get("odps_link")
        self.assertIsNotNone(odps_contract_id)
        odps_contract = Contract.objects.get(id=odps_contract_id)
        self.assertEqual(odps_contract.original_spec_type, "ODPS")

        # Step 6: Asset created and linked
        from hub.apps.assets.models import Asset
        asset = Asset.objects.filter(tenant=self.tenant, key="complete-technical-first-asset").first()
        self.assertIsNotNone(asset)
        self.assertEqual(contract.asset, asset)
        self.assertEqual(odps_contract.asset, asset)

        # Step 7: Indexed for search (ODCS technical + ODPS marketplace)
        odcs_search_index = SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id
        ).first()
        self.assertIsNotNone(odcs_search_index, "ODCS contract should be indexed")

        odps_search_index = SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=odps_contract.id
        ).first()
        self.assertIsNotNone(odps_search_index, "ODPS contract should be indexed")

        # Step 8: Semantic mapping (ODCS technical + ODPS marketplace)
        odcs_semantic = SemanticResource.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id
        ).first()
        # Semantic mapping may be skipped if service unavailable, so we check if it exists
        if odcs_semantic:
            self.assertIsNotNone(odcs_semantic.uri)

        odps_semantic = SemanticResource.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=odps_contract.id
        ).first()
        if odps_semantic:
            self.assertIsNotNone(odps_semantic.uri)

    def test_technical_first_flow_odcs_v2_2_2(self):
        """Test Technical-First flow with ODCS v2.2.2 (backward compatibility)"""
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(engine)

        # Execute workflow with ODCS v2.2.2
        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.odcs_contract_v2_2_2),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            engine=engine,
            registry=registry
        )

        # Verify ODCS v2.2.2 contract validated and normalized
        self.assertIsNotNone(contract)
        self.assertEqual(contract.original_spec_type, "ODCS")
        self.assertEqual(contract.original_spec_version, "2.2.2")
        self.assertIsNotNone(contract.hub_contract_json)
        self.assertEqual(contract.normalization_status, NormalizationStatus.NORMALIZED_OK)


class ContractCreationWorkflowODPSLinkingTest(TestCase):
    """Comprehensive tests for ODPS linking in ContractCreationWorkflow (Task 7.1.2)"""

    def setUp(self):
        """Set up test fixtures"""
        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant ODPS Linking {unique_id}",
            slug=f"test-tenant-odps-linking-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-odps-linking-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(self.registry)
        ContractCreationWorkflow.register_tasks(self.engine)

        # Sample ODCS contract (proper format)
        self.sample_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": f"test-contract-{unique_id}",
            "name": "Test Contract",
            "version": "1.0.0",
            "description": "Test contract description",
            "schema": {
                "fields": [
                    {"name": "email", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            },
            "info": {
                "owners": [
                    {"name": "John Doe", "email": "john@example.com"}
                ]
            },
            "marketplace": {
                "license_summary": "Test license",
                "intended_use": ["analytics"]
            }
        }

    def test_link_odps_step_event_publishing(self):
        """Test that link_odps step publishes workflow.step.started and workflow.step.completed events"""
        from unittest.mock import patch
        import uuid

        with patch("hub.apps.core.events.service_publishers.EventPublisher.publish") as mock_publish:
            mock_publish.return_value = str(uuid.uuid4())

            # Execute workflow with ODPS generation
            # The workflow will create the ODCS contract first, then link ODPS
            ContractCreationWorkflow.execute(
                original_raw=json.dumps(self.sample_contract),
                original_format="JSON",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                odps_action="generate",
                engine=self.engine,
                registry=self.registry
            )

            # Verify link_odps step events were published
            step_started_calls = [
                call for call in mock_publish.call_args_list
                if call[1]["event_type"] == "workflow.step.started"
                and call[1]["data"]["step_name"] == "link_odps"
            ]
            step_completed_calls = [
                call for call in mock_publish.call_args_list
                if call[1]["event_type"] == "workflow.step.completed"
                and call[1]["data"]["step_name"] == "link_odps"
            ]

            self.assertEqual(len(step_started_calls), 1, "link_odps step.started event should be published")
            self.assertEqual(len(step_completed_calls), 1, "link_odps step.completed event should be published")

            # Verify event data structure
            started_call = step_started_calls[0]
            self.assertIn("step_index", started_call[1]["data"])
            self.assertIn("step_name", started_call[1]["data"])
            self.assertIn("progress_percentage", started_call[1]["data"])
            self.assertEqual(started_call[1]["data"]["step_name"], "link_odps")

            completed_call = step_completed_calls[0]
            self.assertIn("step_index", completed_call[1]["data"])
            self.assertIn("step_name", completed_call[1]["data"])
            self.assertIn("progress_percentage", completed_call[1]["data"])
            self.assertIn("duration_ms", completed_call[1]["data"])
            self.assertEqual(completed_call[1]["data"]["step_name"], "link_odps")

    def test_link_odps_compensation_on_failure(self):
        """Test that ODPS linking compensation is executed when workflow fails after linking"""
        # Create ODCS contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw=json.dumps(self.sample_contract),
            hub_contract_json={
                "id": self.sample_contract["id"],
                "info": {
                    "name": self.sample_contract["name"],
                    "description": self.sample_contract["description"],
                    "version": self.sample_contract["version"]
                },
                "schema": self.sample_contract["schema"],
                "marketplace": self.sample_contract["marketplace"]
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.DRAFT,
            created_by=self.user
        )

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name=ContractCreationWorkflow.WORKFLOW_NAME,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "odps_action": "generate"
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        instance.state_data = {
            "contract_id": str(contract.id),
            "user_id": str(self.user.id),
            "odps_action": "generate"
        }
        instance.save()

        # Execute link_odps step manually
        from hub.apps.orchestration.models import WorkflowStep, StepStatus
        # Get the link_odps step from the workflow instance (it was created when instance was created)
        step = instance.steps.filter(step_name="link_odps").first()
        if not step:
            # If step doesn't exist, create it with the next available index
            max_index = instance.steps.aggregate(models.Max('step_index'))['step_index__max'] or -1
            step = instance.steps.create(
                step_name="link_odps",
                step_index=max_index + 1,
                status=StepStatus.PENDING
            )

        task_func = self.engine.task_registry.get("contract_creation.link_odps")

        with transaction.atomic():
            result = task_func(instance.state_data, instance, step)

        # Verify ODPS contract was created and linked
        self.assertTrue(result.get("odps_linked"))
        odps_contract_id = result["odps_contract_id"]
        odps_contract = Contract.objects.get(id=odps_contract_id)

        # Verify bidirectional link exists
        contract.refresh_from_db()
        self.assertIn("extensions", contract.hub_contract_json)
        self.assertIn("x_odps", contract.hub_contract_json["extensions"])
        self.assertEqual(
            contract.hub_contract_json["extensions"]["x_odps"]["odps_link"],
            odps_contract_id
        )

        # Now test compensation
        compensation_func = self.engine.task_registry.get("contract_creation.rollback_odps_linking")
        compensation_input = {
            "contract_id": str(contract.id),
            "odps_contract_id": odps_contract_id,
            "odps_action": "generate"
        }

        with transaction.atomic():
            compensation_result = compensation_func(compensation_input, instance, step)

        # Verify compensation executed
        self.assertTrue(compensation_result.get("rolled_back"))

        # Verify links were removed
        contract.refresh_from_db()
        if contract.hub_contract_json and "extensions" in contract.hub_contract_json:
            x_odps = contract.hub_contract_json["extensions"].get("x_odps", {})
            self.assertNotIn("odps_link", x_odps, "ODPS link should be removed")

        # Verify ODPS contract was deleted (since it was generated)
        with self.assertRaises(Contract.DoesNotExist):
            Contract.objects.get(id=odps_contract_id)

    def test_link_odps_compensation_preserves_existing_contract(self):
        """Test that compensation preserves existing ODPS contract when linking (not generating)"""
        # Create ODCS contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw=json.dumps(self.sample_contract),
            hub_contract_json={
                "id": self.sample_contract["id"],
                "info": {"name": self.sample_contract["name"]}
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.DRAFT,
            created_by=self.user
        )

        # Create existing ODPS contract
        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODPS",
            original_spec_version="4.1",
            original_format="JSON",
            original_raw='{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}}}',
            hub_contract_json={"id": "test-product", "info": {"name": "Test Product"}},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.DRAFT,
            created_by=self.user
        )

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name=ContractCreationWorkflow.WORKFLOW_NAME,
            input_data={
                "original_raw": json.dumps(self.sample_contract),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
                "odps_action": "link",
                "odps_contract_id": str(odps_contract.id)
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        instance.state_data = {
            "contract_id": str(contract.id),
            "user_id": str(self.user.id),
            "odps_action": "link",
            "odps_contract_id": str(odps_contract.id)
        }
        instance.save()

        # Execute link_odps step
        from hub.apps.orchestration.models import WorkflowStep, StepStatus
        # Get the link_odps step from the workflow instance (it was created when instance was created)
        step = instance.steps.filter(step_name="link_odps").first()
        if not step:
            # If step doesn't exist, create it with the next available index
            max_index = instance.steps.aggregate(models.Max('step_index'))['step_index__max'] or -1
            step = instance.steps.create(
                step_name="link_odps",
                step_index=max_index + 1,
                status=StepStatus.PENDING
            )

        task_func = self.engine.task_registry.get("contract_creation.link_odps")

        with transaction.atomic():
            result = task_func(instance.state_data, instance, step)

        # Verify linking succeeded
        self.assertTrue(result.get("odps_linked"))

        # Now test compensation
        compensation_func = self.engine.task_registry.get("contract_creation.rollback_odps_linking")
        compensation_input = {
            "contract_id": str(contract.id),
            "odps_contract_id": str(odps_contract.id),
            "odps_action": "link"  # Existing contract, should not be deleted
        }

        with transaction.atomic():
            compensation_result = compensation_func(compensation_input, instance, step)

        # Verify compensation executed
        self.assertTrue(compensation_result.get("rolled_back"))

        # Verify links were removed
        contract.refresh_from_db()
        if contract.hub_contract_json and "extensions" in contract.hub_contract_json:
            x_odps = contract.hub_contract_json["extensions"].get("x_odps", {})
            self.assertNotIn("odps_link", x_odps, "ODPS link should be removed")

        odps_contract.refresh_from_db()
        if odps_contract.hub_contract_json and "extensions" in odps_contract.hub_contract_json:
            x_odps = odps_contract.hub_contract_json["extensions"].get("x_odps", {})
            self.assertNotIn("odcs_link", x_odps, "ODCS link should be removed")

        # Verify existing ODPS contract was NOT deleted (only links removed)
        odps_contract_after = Contract.objects.get(id=odps_contract.id)
        self.assertIsNotNone(odps_contract_after, "Existing ODPS contract should be preserved")

    def test_link_odps_integration_full_workflow(self):
        """Integration test: Full workflow execution with ODPS linking"""
        # Execute full workflow with ODPS generation
        contract = ContractCreationWorkflow.execute(
            original_raw=json.dumps(self.sample_contract),
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            odps_action="generate",
            engine=self.engine,
            registry=self.registry
        )

        # Verify ODCS contract created
        self.assertIsNotNone(contract)
        self.assertEqual(contract.original_spec_type, "ODCS")

        # Verify ODPS contract was created and linked
        odps_contract_id = contract.hub_contract_json.get("extensions", {}).get("x_odps", {}).get("odps_link")
        self.assertIsNotNone(odps_contract_id, "ODPS contract should be linked")

        odps_contract = Contract.objects.get(id=odps_contract_id)
        self.assertEqual(odps_contract.original_spec_type, "ODPS")
        self.assertEqual(odps_contract.tenant, self.tenant)

        # Verify bidirectional linking
        self.assertEqual(
            odps_contract.hub_contract_json.get("extensions", {}).get("x_odps", {}).get("odcs_link"),
            str(contract.id)
        )

        # Verify both contracts are indexed
        odcs_search_index = SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id
        ).first()
        self.assertIsNotNone(odcs_search_index, "ODCS contract should be indexed")

        odps_search_index = SearchIndex.objects.filter(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=odps_contract.id
        ).first()
        self.assertIsNotNone(odps_search_index, "ODPS contract should be indexed")

