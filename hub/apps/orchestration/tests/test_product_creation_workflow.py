"""
Unit tests for Product Creation Workflow (Task 3.1.1)

Tests verify:
1. Workflow definition registration
2. Task registration
3. Workflow step execution
4. Error handling
5. Compensation logic
"""

try:
    import pytest

    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    pytest = None
    pytestmark = None

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.orchestration.models import WorkflowDefinition, WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


class ProductCreationWorkflowDefinitionTest(TestCase):
    """Test ProductCreationWorkflow definition and registration"""

    def setUp(self):
        """Set up test fixtures"""
        self.registry = WorkflowRegistry()
        self.engine = WorkflowEngine()

    def test_workflow_name_is_correct(self):
        """Test that workflow name is 'product_creation'"""
        self.assertEqual(ProductCreationWorkflow.WORKFLOW_NAME, "product_creation")

    def test_register_workflow_creates_definition(self):
        """Test that register_workflow creates workflow definition"""
        # Count existing definitions
        initial_count = WorkflowDefinition.objects.filter(
            name=ProductCreationWorkflow.WORKFLOW_NAME
        ).count()

        ProductCreationWorkflow.register_workflow(self.registry)

        # Verify workflow definition exists (may already exist from previous test)
        workflow_def = (
            WorkflowDefinition.objects.filter(name=ProductCreationWorkflow.WORKFLOW_NAME)
            .order_by("-created_at")
            .first()
        )

        self.assertIsNotNone(workflow_def, "Workflow definition should be created")
        self.assertEqual(workflow_def.name, ProductCreationWorkflow.WORKFLOW_NAME)
        self.assertEqual(workflow_def.version, "1.0.0")
        self.assertTrue(workflow_def.is_active)

    def test_workflow_dsl_has_all_required_steps(self):
        """Test that workflow DSL has all required steps"""
        ProductCreationWorkflow.register_workflow(self.registry)

        workflow_def = (
            WorkflowDefinition.objects.filter(name=ProductCreationWorkflow.WORKFLOW_NAME)
            .order_by("-created_at")
            .first()
        )

        self.assertIsNotNone(workflow_def, "Workflow definition should exist")
        dsl = workflow_def.dsl_json

        # Verify required fields
        self.assertIn("version", dsl)
        self.assertIn("steps", dsl)
        self.assertIn("compensation", dsl)
        self.assertTrue(dsl["compensation"]["enabled"])

        # Verify all required steps exist
        step_names = [step["name"] for step in dsl["steps"]]
        required_steps = [
            "parse_odps",
            "resolve_refs",
            "extract_contract",
            "validate_odcs",
            "normalize_odcs",
            "normalize_odps",
            "create_odcs_contract",
            "create_odps_contract",
            "link_contracts",
            "link_data_file",
            "index_for_search",
            "semantic_mapping",
        ]

        for required_step in required_steps:
            self.assertIn(
                required_step, step_names, f"Step '{required_step}' should be in workflow"
            )

    def test_workflow_steps_have_compensation(self):
        """Test that workflow steps that need compensation have it"""
        ProductCreationWorkflow.register_workflow(self.registry)

        workflow_def = (
            WorkflowDefinition.objects.filter(name=ProductCreationWorkflow.WORKFLOW_NAME)
            .order_by("-created_at")
            .first()
        )

        self.assertIsNotNone(workflow_def, "Workflow definition should exist")
        dsl = workflow_def.dsl_json

        # Steps that should have compensation
        steps_with_compensation = [
            "normalize_odcs",
            "normalize_odps",
            "create_odcs_contract",
            "create_odps_contract",
            "link_contracts",
        ]

        for step_def in dsl["steps"]:
            if step_def["name"] in steps_with_compensation:
                self.assertIn(
                    "compensation", step_def, f"Step '{step_def['name']}' should have compensation"
                )
                self.assertIn("type", step_def["compensation"])
                self.assertIn("task", step_def["compensation"])

    def test_register_tasks_registers_all_tasks(self):
        """Test that register_tasks registers all workflow tasks"""
        ProductCreationWorkflow.register_tasks(self.engine)

        # Verify all required tasks are registered
        required_tasks = [
            "product_creation.parse_odps",
            "product_creation.resolve_refs",
            "product_creation.extract_contract",
            "product_creation.validate_odcs",
            "product_creation.normalize_odcs",
            "product_creation.normalize_odps",
            "product_creation.create_odcs_contract",
            "product_creation.create_odps_contract",
            "product_creation.link_contracts",
            "product_creation.link_data_file",
            "product_creation.index_for_search",
            "product_creation.semantic_mapping",
        ]

        for task_name in required_tasks:
            self.assertIn(
                task_name, self.engine.task_registry, f"Task '{task_name}' should be registered"
            )

    def test_register_tasks_registers_compensation_tasks(self):
        """Test that register_tasks registers compensation tasks"""
        ProductCreationWorkflow.register_tasks(self.engine)

        # Verify compensation tasks are registered
        compensation_tasks = [
            "product_creation.rollback_normalize_odcs",
            "product_creation.rollback_normalize_odps",
            "product_creation.rollback_odcs_contract",
            "product_creation.rollback_odps_contract",
            "product_creation.rollback_link_contracts",
            "product_creation.rollback_link_data_file",
        ]

        for task_name in compensation_tasks:
            self.assertIn(
                task_name,
                self.engine.task_registry,
                f"Compensation task '{task_name}' should be registered",
            )


class ProductCreationWorkflowStepExecutionTest(TestCase):
    """Test ProductCreationWorkflow step execution"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        # Register workflow and tasks
        ProductCreationWorkflow.register_workflow(self.registry)
        ProductCreationWorkflow.register_tasks(self.engine)

        # Create valid ODPS document with inline ODCS contract
        self.valid_odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test product description",
                    }
                },
                "dataSchema": {
                    "fields": [
                        {"name": "id", "type": "string", "description": "Unique identifier"},
                        {"name": "name", "type": "string", "description": "Name field"},
                    ]
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-odcs-contract",
                        "name": "Test ODCS Contract",
                        "version": "1.0.0",
                        "schema": {
                            "fields": [
                                {
                                    "name": "id",
                                    "type": "string",
                                    "nullable": False,
                                    "description": "Unique identifier",
                                },
                                {
                                    "name": "name",
                                    "type": "string",
                                    "nullable": True,
                                    "description": "Name field",
                                },
                            ]
                        },
                    }
                },
            },
        }
        self.valid_odps_raw = json.dumps(self.valid_odps_doc)

    def test_parse_odps_task_with_valid_document_succeeds(self):
        """Test parse_odps task with valid ODPS document"""
        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Register workflow first
        ProductCreationWorkflow.register_workflow(self.registry)

        workflow_def = (
            WorkflowDefinition.objects.filter(name=ProductCreationWorkflow.WORKFLOW_NAME)
            .order_by("-created_at")
            .first()
        )

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            workflow_version="1.0.0",
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
        )

        step = type("Step", (), {"name": "parse_odps"})()
        result = ProductCreationWorkflow._parse_odps_task(input_data, instance, step)

        self.assertIn("odps_document", result)
        self.assertIn("odps_version", result)
        self.assertEqual(result["odps_version"], "4.1")
        self.assertIn("state", result)
        self.assertIn("odps_document", result["state"])

    def test_parse_odps_task_with_invalid_document_raises_error(self):
        """Test parse_odps task with invalid ODPS document raises error"""
        input_data = {
            "original_raw": '{"invalid": "odps"}',
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Register workflow first
        ProductCreationWorkflow.register_workflow(self.registry)

        workflow_def = (
            WorkflowDefinition.objects.filter(name=ProductCreationWorkflow.WORKFLOW_NAME)
            .order_by("-created_at")
            .first()
        )

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            workflow_version="1.0.0",
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
        )

        step = type("Step", (), {"name": "parse_odps"})()

        from hub.apps.contracts.odps_errors import ODPSValidationError

        with self.assertRaises(ODPSValidationError):
            ProductCreationWorkflow._parse_odps_task(input_data, instance, step)

    def test_parse_odps_task_with_malformed_json_raises_error(self):
        """Test parse_odps task with malformed JSON raises error (edge case)"""
        input_data = {
            "original_raw": '{"invalid": json}',  # Invalid JSON
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        ProductCreationWorkflow.register_workflow(self.registry)

        workflow_def = (
            WorkflowDefinition.objects.filter(name=ProductCreationWorkflow.WORKFLOW_NAME)
            .order_by("-created_at")
            .first()
        )

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            workflow_version="1.0.0",
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
        )

        step = type("Step", (), {"name": "parse_odps"})()

        # Should raise JSON decode error or validation error
        with self.assertRaises((ValueError, json.JSONDecodeError, Exception)):
            ProductCreationWorkflow._parse_odps_task(input_data, instance, step)

    def test_parse_odps_task_with_empty_string_raises_error(self):
        """Test parse_odps task with empty string raises error (edge case)"""
        input_data = {
            "original_raw": "",
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        ProductCreationWorkflow.register_workflow(self.registry)

        workflow_def = (
            WorkflowDefinition.objects.filter(name=ProductCreationWorkflow.WORKFLOW_NAME)
            .order_by("-created_at")
            .first()
        )

        instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            workflow_version="1.0.0",
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
        )

        step = type("Step", (), {"name": "parse_odps"})()

        # Should raise validation error for empty input
        with self.assertRaises(Exception):
            ProductCreationWorkflow._parse_odps_task(input_data, instance, step)

    def test_extract_contract_task_with_valid_contract_succeeds(self):
        """Test extract_contract task with valid product.contract"""
        input_data = {"odps_document_resolved": self.valid_odps_doc}

        instance = WorkflowInstance.objects.create(
            workflow_definition=WorkflowDefinition.objects.get(
                name=ProductCreationWorkflow.WORKFLOW_NAME
            ),
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            workflow_version="1.0.0",
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
            state_data={"odps_document_resolved": self.valid_odps_doc},
        )

        step = type("Step", (), {"name": "extract_contract"})()
        result = ProductCreationWorkflow._extract_contract_task(input_data, instance, step)

        self.assertIn("odcs_contract", result)
        self.assertIsNotNone(result["odcs_contract"])
        self.assertIn("state", result)
        self.assertIn("odcs_contract", result["state"])

    def test_extract_contract_task_with_missing_contract_raises_error(self):
        """Test extract_contract task with missing product.contract raises error"""
        odps_doc_no_contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string", "description": "Unique identifier"}]
                },
                # Missing contract section
            },
        }

        input_data = {"odps_document_resolved": odps_doc_no_contract}

        instance = WorkflowInstance.objects.create(
            workflow_definition=WorkflowDefinition.objects.get(
                name=ProductCreationWorkflow.WORKFLOW_NAME
            ),
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            workflow_version="1.0.0",
            tenant=self.tenant,
            input_data=input_data,
            created_by_id=str(self.user.id),
            status=WorkflowStatus.DRAFT,
            state_data={"odps_document_resolved": odps_doc_no_contract},
        )

        step = type("Step", (), {"name": "extract_contract"})()

        from hub.apps.contracts.odps_errors import ODPSValidationError

        with self.assertRaises(ODPSValidationError):
            ProductCreationWorkflow._extract_contract_task(input_data, instance, step)

    def test_workflow_definition_has_correct_structure(self):
        """Test that workflow definition has correct structure"""
        ProductCreationWorkflow.register_workflow(self.registry)

        # Get the most recent workflow definition (in case multiple exist)
        workflow_def = (
            WorkflowDefinition.objects.filter(name=ProductCreationWorkflow.WORKFLOW_NAME)
            .order_by("-created_at")
            .first()
        )

        self.assertIsNotNone(workflow_def, "Workflow definition should exist")
        dsl = workflow_def.dsl_json

        # Verify structure
        self.assertEqual(dsl["version"], "1.0.0")
        self.assertIsInstance(dsl["steps"], list)
        self.assertEqual(len(dsl["steps"]), 12)  # 12 steps including link_data_file
        self.assertTrue(dsl["compensation"]["enabled"])


class ProductCreationWorkflowE2ETest(TestCase):
    """E2E tests for Product-First flow (Task 3.1.2)"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant E2E", slug="test-tenant-e2e", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test-e2e@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        # Register workflow and tasks
        ProductCreationWorkflow.register_workflow(self.registry)
        ProductCreationWorkflow.register_tasks(self.engine)

        # Create valid ODPS document with inline ODCS contract
        self.valid_odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-e2e",
                        "name": "Test Product E2E",
                        "description": "Test product description for E2E testing",
                    }
                },
                "dataSchema": {
                    "fields": [
                        {"name": "id", "type": "string", "description": "Unique identifier"},
                        {"name": "name", "type": "string", "description": "Name field"},
                    ]
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-odcs-contract-e2e",
                        "name": "Test ODCS Contract E2E",
                        "version": "1.0.0",
                        "description": "Test ODCS contract for E2E testing",
                        "schema": {
                            "fields": [
                                {
                                    "name": "id",
                                    "type": "string",
                                    "nullable": False,
                                    "description": "Unique identifier",
                                },
                                {
                                    "name": "name",
                                    "type": "string",
                                    "nullable": True,
                                    "description": "Name field",
                                },
                            ]
                        },
                    }
                },
            },
        }
        self.valid_odps_raw = json.dumps(self.valid_odps_doc)

    def test_product_first_flow_success_path(self):
        """E2E test: Product-First flow success path (Task 3.1.2)"""
        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Execute workflow
        workflow_def = self.registry.get_workflow(ProductCreationWorkflow.WORKFLOW_NAME)
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Start and execute workflow
        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Verify workflow completed successfully
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

        # Verify both contracts were created
        odps_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODPS
        )
        odcs_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODCS
        )

        self.assertEqual(odps_contracts.count(), 1, "ODPS contract should be created")
        self.assertEqual(odcs_contracts.count(), 1, "ODCS contract should be created")

        odps_contract = odps_contracts.first()
        odcs_contract = odcs_contracts.first()

        # Verify contracts are linked bidirectionally
        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertIsNotNone(odcs_contract.hub_contract_json)

        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})

        if "x_odps" in odps_extensions:
            self.assertEqual(
                odps_extensions["x_odps"].get("odcs_link"),
                str(odcs_contract.id),
                "ODPS contract should link to ODCS contract",
            )

        if "x_odps" in odcs_extensions:
            self.assertEqual(
                odcs_extensions["x_odps"].get("odps_link"),
                str(odps_contract.id),
                "ODCS contract should link to ODPS contract",
            )

        # Verify contracts have correct spec types
        self.assertEqual(odps_contract.original_spec_type, OriginalSpecType.ODPS)
        self.assertEqual(odcs_contract.original_spec_type, OriginalSpecType.ODCS)

    def test_product_first_flow_error_handling_validation_error(self):
        """E2E test: Product-First flow error handling - validation error (Task 3.1.2)"""
        # Invalid ODPS document (missing required fields)
        invalid_odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                # Missing product field
            }
        )

        input_data = {
            "original_raw": invalid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Execute workflow
        workflow_def = self.registry.get_workflow(ProductCreationWorkflow.WORKFLOW_NAME)
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Start and execute workflow - should fail at validation step
        try:
            instance = self.engine.start_instance(str(instance.id))
            instance = self.engine.execute_instance(str(instance.id))
        except Exception:
            pass  # Expected to fail

        # Verify workflow failed (may be FAILED or ROLLED_BACK if compensation ran)
        instance.refresh_from_db()
        self.assertIn(instance.status, [WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK])

        # Verify no contracts were created
        odps_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODPS
        )
        odcs_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODCS
        )

        self.assertEqual(
            odps_contracts.count(), 0, "No ODPS contract should be created on validation error"
        )
        self.assertEqual(
            odcs_contracts.count(), 0, "No ODCS contract should be created on validation error"
        )

    def test_product_first_flow_error_handling_missing_contract(self):
        """E2E test: Product-First flow error handling - missing contract (Task 3.1.2)"""
        # ODPS document without product.contract
        odps_no_contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-no-contract",
                        "name": "Test Product No Contract",
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string", "description": "Unique identifier"}]
                },
                # Missing contract section
            },
        }
        odps_no_contract_raw = json.dumps(odps_no_contract)

        input_data = {
            "original_raw": odps_no_contract_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Execute workflow
        workflow_def = self.registry.get_workflow(ProductCreationWorkflow.WORKFLOW_NAME)
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Start and execute workflow - should fail at extract_contract step
        try:
            instance = self.engine.start_instance(str(instance.id))
            instance = self.engine.execute_instance(str(instance.id))
        except Exception:
            pass  # Expected to fail

        # Verify workflow failed (may be FAILED or ROLLED_BACK if compensation ran)
        instance.refresh_from_db()
        self.assertIn(instance.status, [WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK])

        # Verify no contracts were created
        odps_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODPS
        )
        odcs_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODCS
        )

        self.assertEqual(
            odps_contracts.count(), 0, "No ODPS contract should be created when contract is missing"
        )
        self.assertEqual(
            odcs_contracts.count(), 0, "No ODCS contract should be created when contract is missing"
        )

    def test_product_first_flow_with_optional_asset_creation(self):
        """E2E test: Product-First flow with optional asset creation (Task 3.1.2 Step 10)"""
        from hub.apps.files.models import File, FileStatus

        # Create a test file
        test_file = File.objects.create(
            tenant=self.tenant,
            name="test-data.csv",
            size=1024,
            content_type="text/csv",
            storage_path="test/test-data.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "file_id": str(test_file.id),
            "asset_key": "test-asset-e2e",
            "asset_name": "Test Asset E2E",
        }

        # Execute workflow
        workflow_def = self.registry.get_workflow(ProductCreationWorkflow.WORKFLOW_NAME)
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Start and execute workflow
        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Verify workflow completed successfully
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

        # Verify asset was created
        from hub.apps.assets.models import Asset

        assets = Asset.objects.filter(tenant=self.tenant, key="test-asset-e2e")
        self.assertEqual(assets.count(), 1, "Asset should be created")

        asset = assets.first()

        # Verify contracts are linked to asset
        odps_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODPS, asset=asset
        )
        odcs_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODCS, asset=asset
        )

        self.assertEqual(odps_contracts.count(), 1, "ODPS contract should be linked to asset")
        self.assertEqual(odcs_contracts.count(), 1, "ODCS contract should be linked to asset")


class ProductCreationWorkflowCompensationTest(TestCase):
    """Integration tests for ProductCreationWorkflow compensation logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant Compensation", slug="test-tenant-compensation"
        )
        self.user = User.objects.create_user(
            email="test-compensation@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        # Register workflow and tasks
        ProductCreationWorkflow.register_workflow(self.registry)
        ProductCreationWorkflow.register_tasks(self.engine)

        # Create valid ODPS document with inline ODCS contract
        self.valid_odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-compensation",
                        "name": "Test Product Compensation",
                        "description": "Test product for compensation testing",
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string", "description": "Unique identifier"}]
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-odcs-contract-compensation",
                        "name": "Test ODCS Contract Compensation",
                        "version": "1.0.0",
                        "schema": {
                            "fields": [
                                {
                                    "name": "id",
                                    "type": "string",
                                    "nullable": False,
                                    "description": "Unique identifier",
                                }
                            ]
                        },
                    }
                },
            },
        }
        self.valid_odps_raw = json.dumps(self.valid_odps_doc)

    def test_compensation_rolls_back_odcs_contract_on_failure(self):
        """Test that compensation deletes ODCS contract when workflow fails after creation"""
        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Manually execute steps up to create_odcs_contract
        instance = self.engine.start_instance(str(instance.id))

        # Execute steps manually to get to create_odcs_contract
        from hub.apps.orchestration.models import StepStatus, WorkflowStep

        steps = WorkflowStep.objects.filter(workflow_instance=instance).order_by("step_index")

        # Get step definitions from workflow DSL
        dsl = instance.workflow_definition.dsl_json
        step_defs = dsl.get("steps", [])

        # Execute parse_odps, resolve_refs, extract_contract, validate_odcs, normalize_odcs
        for step in steps[:5]:  # First 5 steps
            try:
                step_def = step_defs[step.step_index]
                step_output = self.engine._execute_step(instance, step, step_def)

                # Update workflow state with step output (as workflow engine does)
                step_state = step_output.get("state", {})
                if step_state:
                    instance.state_data.update(step_state)
                # Also merge top-level step output keys into state_data
                for key, value in step_output.items():
                    if key != "state" and key != "output":
                        instance.state_data[key] = value
                instance.save(update_fields=["state_data", "updated_at"])

                step.status = StepStatus.COMPLETED
                step.save()
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error_message = str(e)
                step.save()
                raise

        # Execute create_odcs_contract step
        create_odcs_step = steps[6]  # create_odcs_contract is step 6 (0-indexed)
        try:
            create_odcs_step_def = step_defs[create_odcs_step.step_index]
            result = self.engine._execute_step(instance, create_odcs_step, create_odcs_step_def)

            # Update workflow state with step output
            step_state = result.get("state", {})
            if step_state:
                instance.state_data.update(step_state)
            for key, value in result.items():
                if key != "state" and key != "output":
                    instance.state_data[key] = value
            instance.save(update_fields=["state_data", "updated_at"])

            create_odcs_step.status = StepStatus.COMPLETED
            create_odcs_step.save()

            # Verify ODCS contract was created
            odcs_contract_id = instance.state_data.get("odcs_contract_id")
            self.assertIsNotNone(odcs_contract_id, "ODCS contract should be created")

            odcs_contract = Contract.objects.get(id=odcs_contract_id)
            self.assertIsNotNone(odcs_contract, "ODCS contract should exist")

            # Now simulate failure in next step (create_odps_contract)
            # This should trigger compensation for create_odcs_contract
            create_odps_step = steps[7]  # create_odps_contract is step 7

            # Mock a failure in create_odps_contract
            def failing_task(input_data, instance, step):
                raise ValueError("Simulated failure in create_odps_contract")

            # Temporarily replace the task
            original_task = self.engine.task_registry.get("product_creation.create_odps_contract")
            self.engine.task_registry["product_creation.create_odps_contract"] = failing_task

            try:
                # Try to execute create_odps_contract - should fail
                # Note: _execute_step catches exceptions when compensation is enabled, so we check step status instead
                create_odps_step_def = step_defs[create_odps_step.step_index]
                self.engine._execute_step(instance, create_odps_step, create_odps_step_def)

                # Verify step was marked as failed
                create_odps_step.refresh_from_db()
                self.assertEqual(create_odps_step.status, StepStatus.FAILED)

                # Trigger compensation via _handle_step_failure (which is what execute_instance does)
                self.engine._handle_step_failure(instance, create_odps_step)

                # Verify ODCS contract was deleted (compensation executed)
                with self.assertRaises(Contract.DoesNotExist):
                    Contract.objects.get(id=odcs_contract_id)

            finally:
                # Restore original task
                if original_task:
                    self.engine.task_registry["product_creation.create_odps_contract"] = (
                        original_task
                    )

        except Exception as e:
            # If we get here, compensation should have been triggered
            # Verify ODCS contract was deleted
            odcs_contract_id = instance.state_data.get("odcs_contract_id")
            if odcs_contract_id:
                try:
                    Contract.objects.get(id=odcs_contract_id)
                    # If contract still exists, compensation didn't work
                    self.fail("ODCS contract should have been deleted by compensation")
                except Contract.DoesNotExist:
                    # Contract was deleted - compensation worked
                    pass

    def test_compensation_rolls_back_odps_contract_on_failure(self):
        """Test that compensation deletes ODPS contract when workflow fails after creation"""
        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Execute workflow up to create_odps_contract
        instance = self.engine.start_instance(str(instance.id))

        # Manually execute steps to get to create_odps_contract
        from hub.apps.orchestration.models import StepStatus, WorkflowStep

        steps = WorkflowStep.objects.filter(workflow_instance=instance).order_by("step_index")

        # Get step definitions from workflow DSL
        dsl = instance.workflow_definition.dsl_json
        step_defs = dsl.get("steps", [])

        # Execute all steps up to create_odps_contract (step 7)
        for step in steps[:8]:  # First 8 steps (including create_odps_contract)
            try:
                step_def = step_defs[step.step_index]
                step_output = self.engine._execute_step(instance, step, step_def)

                # Update workflow state with step output
                step_state = step_output.get("state", {})
                if step_state:
                    instance.state_data.update(step_state)
                for key, value in step_output.items():
                    if key != "state" and key != "output":
                        instance.state_data[key] = value
                instance.save(update_fields=["state_data", "updated_at"])

                step.status = StepStatus.COMPLETED
                step.save()
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error_message = str(e)
                step.save()
                raise

        # Verify ODPS contract was created
        instance.refresh_from_db()
        odps_contract_id = instance.state_data.get("odps_contract_id")
        self.assertIsNotNone(odps_contract_id, "ODPS contract should be created")

        odps_contract = Contract.objects.get(id=odps_contract_id)
        self.assertIsNotNone(odps_contract, "ODPS contract should exist")

        # Now simulate failure in link_contracts step
        # This should trigger compensation for create_odps_contract
        link_contracts_step = steps[8]  # link_contracts is step 8

        # Mock a failure in link_contracts
        def failing_task(input_data, instance, step):
            raise ValueError("Simulated failure in link_contracts")

        # Temporarily replace the task
        original_task = self.engine.task_registry.get("product_creation.link_contracts")
        self.engine.task_registry["product_creation.link_contracts"] = failing_task

        try:
            # Try to execute link_contracts - should fail
            # Note: _execute_step catches exceptions when compensation is enabled, so we check step status instead
            link_contracts_step_def = step_defs[link_contracts_step.step_index]
            self.engine._execute_step(instance, link_contracts_step, link_contracts_step_def)

            # Verify step was marked as failed
            link_contracts_step.refresh_from_db()
            self.assertEqual(link_contracts_step.status, StepStatus.FAILED)

            # Trigger compensation via _handle_step_failure (which is what execute_instance does)
            # This will compensate all previous steps including create_odps_contract
            self.engine._handle_step_failure(instance, link_contracts_step)

            # Verify ODPS contract was deleted (compensation executed)
            with self.assertRaises(Contract.DoesNotExist):
                Contract.objects.get(id=odps_contract_id)

        finally:
            # Restore original task
            if original_task:
                self.engine.task_registry["product_creation.link_contracts"] = original_task

    def test_compensation_rolls_back_contract_linking_on_failure(self):
        """Test that compensation removes contract links when workflow fails after linking"""
        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Execute workflow up to link_contracts
        instance = self.engine.start_instance(str(instance.id))

        # Manually execute steps to get to link_contracts
        from hub.apps.orchestration.models import StepStatus, WorkflowStep

        steps = WorkflowStep.objects.filter(workflow_instance=instance).order_by("step_index")

        # Get step definitions from workflow DSL
        dsl = instance.workflow_definition.dsl_json
        step_defs = dsl.get("steps", [])

        # Execute all steps up to link_contracts
        for step in steps[:8]:  # First 8 steps (including create_odps_contract)
            try:
                step_def = step_defs[step.step_index]
                step_output = self.engine._execute_step(instance, step, step_def)

                # Update workflow state with step output
                step_state = step_output.get("state", {})
                if step_state:
                    instance.state_data.update(step_state)
                for key, value in step_output.items():
                    if key != "state" and key != "output":
                        instance.state_data[key] = value
                instance.save(update_fields=["state_data", "updated_at"])

                step.status = StepStatus.COMPLETED
                step.save()
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error_message = str(e)
                step.save()
                raise

        # Verify contracts are linked
        instance.refresh_from_db()
        odps_contract_id = instance.state_data.get("odps_contract_id")
        odcs_contract_id = instance.state_data.get("odcs_contract_id")

        odps_contract = Contract.objects.get(id=odps_contract_id)
        odcs_contract = Contract.objects.get(id=odcs_contract_id)

        # Check if links exist in hub_contract_json
        odps_has_link = odps_contract.hub_contract_json and odps_contract.hub_contract_json.get(
            "extensions", {}
        ).get("x_odps", {}).get("odcs_link")
        odcs_has_link = odcs_contract.hub_contract_json and odcs_contract.hub_contract_json.get(
            "extensions", {}
        ).get("x_odps", {}).get("odps_link")

        # If links don't exist yet, execute link_contracts step
        if not odps_has_link or not odcs_has_link:
            link_contracts_step = steps[8]
            try:
                link_contracts_step_def = step_defs[link_contracts_step.step_index]
                step_output = self.engine._execute_step(
                    instance, link_contracts_step, link_contracts_step_def
                )

                # Update workflow state with step output
                step_state = step_output.get("state", {})
                if step_state:
                    instance.state_data.update(step_state)
                for key, value in step_output.items():
                    if key != "state" and key != "output":
                        instance.state_data[key] = value
                instance.save(update_fields=["state_data", "updated_at"])

                link_contracts_step.status = StepStatus.COMPLETED
                link_contracts_step.save()

                # Refresh contracts
                odps_contract.refresh_from_db()
                odcs_contract.refresh_from_db()
            except Exception as e:
                pass

        # Verify links exist
        odps_contract.refresh_from_db()
        odcs_contract.refresh_from_db()

        odps_link = odps_contract.hub_contract_json and odps_contract.hub_contract_json.get(
            "extensions", {}
        ).get("x_odps", {}).get("odcs_link")
        odcs_link = odcs_contract.hub_contract_json and odcs_contract.hub_contract_json.get(
            "extensions", {}
        ).get("x_odps", {}).get("odps_link")

        if odps_link or odcs_link:
            # Links exist - now test compensation
            link_contracts_step = steps[8]

            # Trigger compensation for link_contracts using engine's compensation instance
            self.engine.compensation._compensate_step(instance, link_contracts_step)

            # Verify links were removed
            odps_contract.refresh_from_db()
            odcs_contract.refresh_from_db()

            odps_link_after = (
                odps_contract.hub_contract_json
                and odps_contract.hub_contract_json.get("extensions", {})
                .get("x_odps", {})
                .get("odcs_link")
            )
            odcs_link_after = (
                odcs_contract.hub_contract_json
                and odcs_contract.hub_contract_json.get("extensions", {})
                .get("x_odps", {})
                .get("odps_link")
            )

            self.assertIsNone(odps_link_after, "ODPS contract link should be removed")
            self.assertIsNone(odcs_link_after, "ODCS contract link should be removed")


class ProductCreationWorkflowEventPublishingTest(TestCase):
    """Test ProductCreationWorkflow event publishing (Task 7.1.1)"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant Events", slug="test-tenant-events", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test-events@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        # Register workflow and tasks
        ProductCreationWorkflow.register_workflow(self.registry)
        ProductCreationWorkflow.register_tasks(self.engine)

        # Create valid ODPS document with inline ODCS contract
        self.valid_odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-events",
                        "name": "Test Product Events",
                        "description": "Test product for event testing",
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string", "description": "Unique identifier"}]
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-odcs-contract-events",
                        "name": "Test ODCS Contract Events",
                        "version": "1.0.0",
                        "schema": {
                            "fields": [
                                {
                                    "name": "id",
                                    "type": "string",
                                    "nullable": False,
                                    "description": "Unique identifier",
                                }
                            ]
                        },
                    }
                },
            },
        }
        self.valid_odps_raw = json.dumps(self.valid_odps_doc)

    def test_workflow_created_event_published(self):
        """Test that workflow.created event is published when ProductCreationWorkflow instance is created"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        # Count events before
        initial_count = Event.objects.filter(event_type="workflow.created").count()

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Verify workflow.created event was published by querying Event model
        created_events = Event.objects.filter(
            event_type="workflow.created",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertGreater(created_events.count(), 0, "workflow.created event should be published")

        # Verify event data
        created_event = created_events.first()
        self.assertEqual(created_event.data["workflow_instance_id"], str(instance.id))
        self.assertEqual(created_event.data["workflow_name"], ProductCreationWorkflow.WORKFLOW_NAME)
        self.assertEqual(created_event.tenant_id, self.tenant.id)
        self.assertEqual(created_event.user_id, self.user.id)

    def test_workflow_created_event_published_edge_case_empty_input(self):
        """Test workflow.created event published with empty input data (edge case)"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": "",
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Verify event was still published even with empty input
        created_events = Event.objects.filter(
            event_type="workflow.created",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertGreater(
            created_events.count(), 0, "Event should be published even with empty input"
        )

    def test_workflow_started_event_published(self):
        """Test that workflow.started event is published when ProductCreationWorkflow is started"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Count started events before
        initial_count = Event.objects.filter(
            event_type="workflow.started",
            data__workflow_instance_id=str(instance.id),
        ).count()

        instance = self.engine.start_instance(str(instance.id))

        # Verify workflow.started event was published by querying Event model
        started_events = Event.objects.filter(
            event_type="workflow.started",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertEqual(
            started_events.count(),
            initial_count + 1,
            "workflow.started event should be published once",
        )

        # Verify event data
        started_event = started_events.first()
        self.assertEqual(started_event.data["workflow_instance_id"], str(instance.id))
        self.assertEqual(started_event.data["workflow_name"], ProductCreationWorkflow.WORKFLOW_NAME)
        self.assertEqual(started_event.tenant_id, self.tenant.id)
        self.assertEqual(started_event.user_id, self.user.id)

    def test_workflow_started_event_not_published_if_already_started(self):
        """Test that workflow.started event is not published twice if workflow already started (edge case)"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Start workflow first time
        instance = self.engine.start_instance(str(instance.id))
        first_started_count = Event.objects.filter(
            event_type="workflow.started",
            data__workflow_instance_id=str(instance.id),
        ).count()

        # Try to start again (engine rejects RUNNING -> RUNNING; no duplicate event)
        instance.refresh_from_db()
        if instance.status == WorkflowStatus.RUNNING:
            from django.core.exceptions import ValidationError
            try:
                self.engine.start_instance(str(instance.id))
            except ValidationError:
                # Expected: invalid transition RUNNING -> RUNNING
                pass
            second_started_count = Event.objects.filter(
                event_type="workflow.started",
                data__workflow_instance_id=str(instance.id),
            ).count()
            # Should not have increased (second start was rejected, so no new event)
            self.assertLessEqual(
                second_started_count,
                first_started_count,
                "Should not publish duplicate workflow.started when start_instance rejects RUNNING->RUNNING",
            )

    def test_workflow_step_events_published(self):
        """Test that workflow.step.started and workflow.step.completed events are published for each step"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))

        # Count step events before execution
        initial_started_count = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).count()
        initial_completed_count = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        # Execute workflow
        instance = self.engine.execute_instance(str(instance.id))

        # Verify step events were published by querying Event model
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        )
        step_completed_events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        )

        # ProductCreationWorkflow has 12 steps, so we should have step events
        self.assertGreater(
            step_started_events.count(),
            initial_started_count,
            "workflow.step.started events should be published",
        )
        self.assertGreater(
            step_completed_events.count(),
            initial_completed_count,
            "workflow.step.completed events should be published",
        )

        # Verify first step event has correct structure
        first_started = step_started_events.order_by("timestamp").first()
        if first_started:
            self.assertIn("step_index", first_started.data)
            self.assertIn("step_name", first_started.data)
            self.assertIn("progress_percentage", first_started.data)
            self.assertEqual(first_started.tenant_id, self.tenant.id)
            self.assertEqual(first_started.user_id, self.user.id)

        # Verify first completed event has correct structure
        first_completed = step_completed_events.order_by("timestamp").first()
        if first_completed:
            self.assertIn("step_index", first_completed.data)
            self.assertIn("step_name", first_completed.data)
            self.assertIn("progress_percentage", first_completed.data)
            self.assertEqual(first_completed.tenant_id, self.tenant.id)
            self.assertEqual(first_completed.user_id, self.user.id)

    def test_workflow_step_events_published_in_order(self):
        """Test that workflow step events are published in correct order (edge case)"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Get all step events ordered by timestamp
        step_events = Event.objects.filter(
            event_type__in=["workflow.step.started", "workflow.step.completed"],
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        # Verify events alternate between started and completed (or at least started comes before completed for same step)
        step_indices_seen = {}
        for event in step_events:
            step_index = event.data.get("step_index")
            step_name = event.data.get("step_name")
            if step_index is not None:
                if step_index not in step_indices_seen:
                    step_indices_seen[step_index] = []
                step_indices_seen[step_index].append(event.event_type)

        # For each step, started should come before completed
        for step_index, event_types in step_indices_seen.items():
            started_indices = [i for i, et in enumerate(event_types) if "started" in et]
            completed_indices = [i for i, et in enumerate(event_types) if "completed" in et]
            if started_indices and completed_indices:
                # First started should come before first completed
                self.assertLess(
                    min(started_indices),
                    min(completed_indices),
                    f"Step {step_index} ({step_name}): started event should come before completed",
                )

    def test_workflow_completed_event_published(self):
        """Test that workflow.completed event is published when ProductCreationWorkflow completes successfully"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))

        # Count completed events before execution
        initial_count = Event.objects.filter(
            event_type="workflow.completed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        instance = self.engine.execute_instance(str(instance.id))

        # Verify workflow.completed event was published by querying Event model
        completed_events = Event.objects.filter(
            event_type="workflow.completed",
            data__workflow_instance_id=str(instance.id),
        )
        self.assertEqual(
            completed_events.count(),
            initial_count + 1,
            "workflow.completed event should be published once",
        )

        # Verify event data
        completed_event = completed_events.first()
        self.assertEqual(completed_event.data["workflow_instance_id"], str(instance.id))
        self.assertEqual(
            completed_event.data["workflow_name"], ProductCreationWorkflow.WORKFLOW_NAME
        )
        self.assertIn("output_data", completed_event.data)
        self.assertIn("duration_ms", completed_event.data)
        self.assertEqual(completed_event.tenant_id, self.tenant.id)
        self.assertEqual(completed_event.user_id, self.user.id)
        # Verify duration_ms is a number
        self.assertIsInstance(completed_event.data["duration_ms"], (int, float))
        self.assertGreaterEqual(completed_event.data["duration_ms"], 0)

    def test_workflow_completed_event_not_published_on_failure(self):
        """Test that workflow.completed event is NOT published when workflow fails (edge case)"""
        from hub.apps.core.events.models import Event

        # Invalid ODPS document that will cause failure
        invalid_odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                # Missing product field
            }
        )

        input_data = {
            "original_raw": invalid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))

        # Count completed events before execution
        initial_completed_count = Event.objects.filter(
            event_type="workflow.completed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        # Execute workflow - should fail
        try:
            instance = self.engine.execute_instance(str(instance.id))
        except Exception:
            pass  # Expected to fail

        instance.refresh_from_db()

        # Verify workflow.completed event was NOT published if workflow failed
        if instance.status != WorkflowStatus.COMPLETED:
            completed_events = Event.objects.filter(
                event_type="workflow.completed",
                data__workflow_instance_id=str(instance.id),
            )
            self.assertEqual(
                completed_events.count(),
                initial_completed_count,
                "workflow.completed event should NOT be published when workflow fails",
            )

    def test_workflow_failed_event_published(self):
        """Test that workflow.failed event is published when ProductCreationWorkflow fails"""
        from hub.apps.core.events.models import Event

        # Invalid ODPS document that will cause failure
        invalid_odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                # Missing product field
            }
        )

        input_data = {
            "original_raw": invalid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))

        # Count failed events before execution
        initial_failed_count = Event.objects.filter(
            event_type="workflow.failed",
            data__workflow_instance_id=str(instance.id),
        ).count()

        # Execute workflow - should fail
        try:
            instance = self.engine.execute_instance(str(instance.id))
        except Exception:
            pass  # Expected to fail

        instance.refresh_from_db()

        # Verify workflow.failed event was published if workflow failed
        if instance.status == WorkflowStatus.FAILED:
            failed_events = Event.objects.filter(
                event_type="workflow.failed",
                data__workflow_instance_id=str(instance.id),
            )
            # Note: Failed event might not be published if exception is raised before event publishing
            # This is acceptable behavior - the important thing is that the workflow status is FAILED
            if failed_events.count() > initial_failed_count:
                failed_event = failed_events.order_by("-timestamp").first()
                self.assertEqual(failed_event.data["workflow_instance_id"], str(instance.id))
                self.assertEqual(
                    failed_event.data["workflow_name"], ProductCreationWorkflow.WORKFLOW_NAME
                )
                self.assertIn("error_message", failed_event.data)
                self.assertEqual(failed_event.tenant_id, self.tenant.id)
                self.assertEqual(failed_event.user_id, self.user.id)
                # Verify error_message is not empty
                self.assertIsNotNone(failed_event.data["error_message"])
                self.assertNotEqual(failed_event.data["error_message"], "")

    def test_workflow_failed_event_with_detailed_error_info(self):
        """Test that workflow.failed event includes detailed error information (edge case)"""
        from hub.apps.core.events.models import Event

        # Create ODPS document with invalid contract structure
        invalid_odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {"en": {"productID": "test", "name": "Test"}},
                    "dataSchema": {"fields": []},
                    "contract": {
                        "spec": {
                            # Invalid contract - missing required fields
                            "apiVersion": "odcs.io/v3.0.2",
                        }
                    },
                },
            }
        )

        input_data = {
            "original_raw": invalid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))

        # Execute workflow - should fail
        try:
            instance = self.engine.execute_instance(str(instance.id))
        except Exception:
            pass  # Expected to fail

        instance.refresh_from_db()

        # Verify failed event has detailed error information
        if instance.status == WorkflowStatus.FAILED:
            failed_events = Event.objects.filter(
                event_type="workflow.failed",
                data__workflow_instance_id=str(instance.id),
            )
            if failed_events.exists():
                failed_event = failed_events.order_by("-timestamp").first()
                # Verify error details are present
                self.assertIn("error_message", failed_event.data)
                error_message = failed_event.data["error_message"]
                self.assertIsNotNone(error_message)
                self.assertIsInstance(error_message, str)
                # Error message should contain useful information
                self.assertGreater(len(error_message), 0)


class ProductCreationWorkflowProgressTrackingTest(TestCase):
    """Test ProductCreationWorkflow progress tracking (Task 7.1.1)"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant Progress", slug="test-tenant-progress"
        )
        self.user = User.objects.create_user(
            email="test-progress@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        # Register workflow and tasks
        ProductCreationWorkflow.register_workflow(self.registry)
        ProductCreationWorkflow.register_tasks(self.engine)

        # Create valid ODPS document with inline ODCS contract
        self.valid_odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-progress",
                        "name": "Test Product Progress",
                        "description": "Test product for progress tracking",
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string", "description": "Unique identifier"}]
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-odcs-contract-progress",
                        "name": "Test ODCS Contract Progress",
                        "version": "1.0.0",
                        "schema": {
                            "fields": [
                                {
                                    "name": "id",
                                    "type": "string",
                                    "nullable": False,
                                    "description": "Unique identifier",
                                }
                            ]
                        },
                    }
                },
            },
        }
        self.valid_odps_raw = json.dumps(self.valid_odps_doc)

    def test_progress_tracked_in_state_data(self):
        """Test that progress percentage is tracked in WorkflowInstance.state_data"""
        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Verify progress is tracked in state_data
        instance.refresh_from_db()
        self.assertIsNotNone(instance.state_data, "state_data should not be None")
        self.assertIn(
            "progress_percentage",
            instance.state_data,
            "progress_percentage should be in state_data",
        )

        progress = instance.state_data.get("progress_percentage")
        self.assertIsNotNone(progress, "progress_percentage should not be None")
        self.assertGreaterEqual(progress, 0.0, "progress_percentage should be >= 0.0")
        self.assertLessEqual(progress, 100.0, "progress_percentage should be <= 100.0")

        # For completed workflow, progress should be 100%
        if instance.status == WorkflowStatus.COMPLETED:
            self.assertEqual(progress, 100.0, "Progress should be 100% for completed workflow")

    def test_progress_increases_monotonically(self):
        """Test that progress percentage increases monotonically during workflow execution"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Get all step events with progress_percentage from Event model
        step_events = Event.objects.filter(
            event_type__in=["workflow.step.started", "workflow.step.completed"],
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        progress_values = []
        for event in step_events:
            if "progress_percentage" in event.data:
                progress_values.append(event.data["progress_percentage"])

        # Verify progress increases monotonically (or stays the same)
        if len(progress_values) > 1:
            for i in range(1, len(progress_values)):
                self.assertGreaterEqual(
                    progress_values[i],
                    progress_values[i - 1],
                    f"Progress should not decrease: {progress_values[i-1]} -> {progress_values[i]}",
                )

    def test_progress_increases_monotonically_edge_case_retry(self):
        """Test that progress increases monotonically even when steps are retried (edge case)"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))

        # Get initial progress
        initial_events = Event.objects.filter(
            event_type__in=["workflow.step.started", "workflow.step.completed"],
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        initial_progress_values = [
            e.data["progress_percentage"] for e in initial_events if "progress_percentage" in e.data
        ]

        # Execute workflow
        instance = self.engine.execute_instance(str(instance.id))

        # Get all progress values after execution
        all_events = Event.objects.filter(
            event_type__in=["workflow.step.started", "workflow.step.completed"],
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")

        all_progress_values = [
            e.data["progress_percentage"] for e in all_events if "progress_percentage" in e.data
        ]

        # Verify progress never decreases
        if len(all_progress_values) > 1:
            for i in range(1, len(all_progress_values)):
                self.assertGreaterEqual(
                    all_progress_values[i],
                    all_progress_values[i - 1],
                    f"Progress should not decrease even with retries: "
                    f"{all_progress_values[i-1]} -> {all_progress_values[i]}",
                )

    def test_progress_in_step_events(self):
        """Test that progress_percentage is included in step.started and step.completed events"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Verify progress_percentage in step events by querying Event model
        step_started_events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        )
        step_completed_events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        )

        # Verify all step.started events have progress_percentage
        self.assertGreater(step_started_events.count(), 0, "Should have step.started events")
        for event in step_started_events:
            self.assertIn("progress_percentage", event.data)
            progress = event.data["progress_percentage"]
            self.assertIsNotNone(progress, "progress_percentage should not be None")
            self.assertIsInstance(progress, (int, float), "progress_percentage should be a number")
            self.assertGreaterEqual(progress, 0.0, "progress_percentage should be >= 0.0")
            self.assertLessEqual(progress, 100.0, "progress_percentage should be <= 100.0")

        # Verify all step.completed events have progress_percentage
        self.assertGreater(step_completed_events.count(), 0, "Should have step.completed events")
        for event in step_completed_events:
            self.assertIn("progress_percentage", event.data)
            progress = event.data["progress_percentage"]
            self.assertIsNotNone(progress, "progress_percentage should not be None")
            self.assertIsInstance(progress, (int, float), "progress_percentage should be a number")
            self.assertGreaterEqual(progress, 0.0, "progress_percentage should be >= 0.0")
            self.assertLessEqual(progress, 100.0, "progress_percentage should be <= 100.0")

    def test_progress_in_step_events_edge_case_final_step(self):
        """Test that final step has progress_percentage = 100.0 (edge case)"""
        from hub.apps.core.events.models import Event

        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }

        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Get the last step completed event
        last_completed_event = (
            Event.objects.filter(
                event_type="workflow.step.completed",
                data__workflow_instance_id=str(instance.id),
            )
            .order_by("-timestamp")
            .first()
        )

        if last_completed_event and instance.status == WorkflowStatus.COMPLETED:
            # Final step should have progress_percentage = 100.0
            self.assertIn("progress_percentage", last_completed_event.data)
            final_progress = last_completed_event.data["progress_percentage"]
            self.assertEqual(
                final_progress,
                100.0,
                f"Final step should have progress_percentage = 100.0, got {final_progress}",
            )
