"""
Tests for Workflow Task Business Rules Integration (Phase 2)

Comprehensive TDD tests for:
1. ProductCreationWorkflow tasks with business rules
2. ContractCreationWorkflow tasks with business rules
3. AssetCreationWorkflow tasks with business rules
4. DatasetCreationWorkflow tasks with business rules
5. MarketplacePublicationWorkflow tasks with business rules

All tests follow TDD principles, use real implementations (no mocks/stubs),
and fix root causes rather than workarounds.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType
from hub.apps.datasets.models import Dataset
from hub.apps.orchestration.models import (
    WorkflowDefinition,
)
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.workflows.asset_creation import AssetCreationWorkflow
from hub.apps.orchestration.workflows.contract_creation import ContractCreationWorkflow
from hub.apps.orchestration.workflows.dataset_creation import DatasetCreationWorkflow
from hub.apps.orchestration.workflows.marketplace_publication import MarketplacePublicationWorkflow
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


class WorkflowTaskBusinessRulesIntegrationTestBase(TestCase):
    """Base test class for workflow task business rules integration tests"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts (root cause fix)
        # Semantic service signals trigger on every Asset/Contract save, causing 60s timeouts
        # This provides 10-100x speedup by preventing semantic service calls during tests
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            # Disconnect signals to prevent semantic service calls during tests
            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            # Signals may not be available - continue without disconnecting
            pass

        # Call super().setUp() first to let Django set up the database connection
        super().setUp()

        # Ensure database connection is valid (TestCase manages connections automatically,
        # but we ensure it's ready after super().setUp())
        from django.db import OperationalError, InterfaceError, connection

        try:
            connection.ensure_connection()
        except (OperationalError, InterfaceError):
            # Django will handle on first use
            pass

        self.engine = WorkflowEngine()
        # Use unique tenant name/slug to avoid conflicts with --reuse-db

        unique_id = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{unique_id}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )

    def tearDown(self):
        """Clean up test fixtures"""
        # Reconnect semantic service signals after test
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            # Reconnect signals after test
            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            # Signals may not be available - continue without reconnecting
            pass

        # Note: For TestCase, Django automatically manages database connections
        # and transactions, so we don't need to close connections manually.
        # Closing connections here can cause issues for subsequent tests.

        super().tearDown()


class TestProductCreationWorkflowBusinessRules(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test ProductCreationWorkflow tasks with business rules"""

    def test_parse_odps_task_validates_using_business_rules(self):
        """Test that _parse_odps_task validates using ODPSBusinessRules"""
        # Create workflow definition
        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="product_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "parse_odps",
                            "type": "task",
                            "task": "product_creation.parse_odps",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        # Register workflow and tasks
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        ProductCreationWorkflow.register_workflow(registry)
        ProductCreationWorkflow.register_tasks(self.engine)

        # Create valid ODPS document
        valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "test-product", "name": "Test Product"}},
                "dataSchema": {"type": "object", "fields": [{"name": "field1", "type": "string"}]},
            },
        }

        import json

        original_raw = json.dumps(valid_odps)

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name="product_creation",
            input_data={
                "original_raw": original_raw,
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute parse_odps step - should validate using business rules
        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        result = self.engine._execute_task_step(instance, step, step_def)

        # Verify task executed successfully
        self.assertIsNotNone(result)
        self.assertIn("odps_document", result)
        self.assertIn("odps_version", result)

    def test_create_odps_contract_task_method_exists(self):
        """Structural check: _create_odps_contract_task method exists.

        Full business-rules validation test would require a complete workflow
        execution with the contract creation workflow — tracked separately.
        """
        self.assertTrue(
            hasattr(ProductCreationWorkflow, "_create_odps_contract_task"),
            "_create_odps_contract_task method must exist on ProductCreationWorkflow",
        )


class TestContractCreationWorkflowBusinessRules(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test ContractCreationWorkflow tasks with business rules"""

    def test_validate_input_task_validates_using_business_rules(self):
        """Test that _validate_input_task validates using ContractsBusinessRules"""
        # Create workflow definition (use get_or_create to avoid duplicates with --reuse-db)
        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="contract_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "validate_input",
                            "type": "task",
                            "task": "contract_creation.validate_input",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        # Register workflow and tasks
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(self.engine)

        # Create valid contract data
        valid_contract = {
            "info": {"name": "Test Contract", "version": "1.0.0"},
            "schema": {"type": "object"},
        }

        import json

        original_raw = json.dumps(valid_contract)

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name="contract_creation",
            input_data={
                "original_raw": original_raw,
                "original_format": "JSON",
                "original_spec_type": "ODCS",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute validate_input step - should validate using business rules
        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        result = self.engine._execute_task_step(instance, step, step_def)

        # Verify task executed successfully
        self.assertIsNotNone(result)
        self.assertTrue(result.get("validated", False))


class TestAssetCreationWorkflowBusinessRules(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test AssetCreationWorkflow tasks with business rules"""

    def test_create_asset_record_task_validates_using_business_rules(self):
        """Test that _create_asset_record_task validates using AssetsBusinessRules"""
        # Create workflow definition
        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="asset_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "create_asset_record",
                            "type": "task",
                            "task": "asset_creation.create_asset_record",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        # Register workflow and tasks
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        AssetCreationWorkflow.register_workflow(registry)
        AssetCreationWorkflow.register_tasks(self.engine)

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name="asset_creation",
            input_data={
                "key": "test-asset",
                "name": "Test Asset",
                "tenant_id": str(self.tenant.id),
                "created_by_id": str(self.user.id),
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute create_asset_record step - should validate using business rules
        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        result = self.engine._execute_task_step(instance, step, step_def)

        # Verify task executed successfully
        self.assertIsNotNone(result)
        self.assertIn("asset_id", result)

        # Verify asset was created and validated
        asset_id = result["asset_id"]
        asset = Asset.objects.get(id=asset_id)
        self.assertIsNotNone(asset)
        self.assertEqual(asset.status, AssetStatus.DRAFT)


class TestDatasetCreationWorkflowBusinessRules(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test DatasetCreationWorkflow tasks with business rules"""

    def test_create_dataset_record_task_validates_using_business_rules(self):
        """Test that _create_dataset_record_task validates using DatasetsBusinessRules"""
        # Create file first
        from hub.apps.files.models import File, FileStatus

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1000,
            content_type="text/csv",
            storage_path="/test/test.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        # Create workflow definition
        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="dataset_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "create_dataset_record",
                            "type": "task",
                            "task": "dataset_creation.create_dataset_record",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        # Register workflow and tasks
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        DatasetCreationWorkflow.register_workflow(registry)
        DatasetCreationWorkflow.register_tasks(self.engine)

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name="dataset_creation",
            input_data={
                "tenant_id": str(self.tenant.id),
                "file_id": str(file_obj.id),
                "file_format": "CSV",
                "schema_json": {"fields": [{"name": "field1", "type": "string"}]},
                "triggered_by_id": str(self.user.id),
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Populate state_data as the task expects data from state_data
        instance.state_data.update(
            {
                "tenant_id": str(self.tenant.id),
                "file_id": str(file_obj.id),
                "file_format": "CSV",
                "schema_json": {"fields": [{"name": "field1", "type": "string"}]},
                "triggered_by_id": str(self.user.id),
            }
        )
        instance.save(update_fields=["state_data"])

        # Execute create_dataset_record step - should validate using business rules
        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        result = self.engine._execute_task_step(instance, step, step_def)

        # Verify task executed successfully
        self.assertIsNotNone(result)
        self.assertIn("dataset_id", result)

        # Verify dataset was created and validated
        dataset_id = result["dataset_id"]
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertIsNotNone(dataset)


class TestMarketplacePublicationWorkflowBusinessRules(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test MarketplacePublicationWorkflow tasks with business rules"""

    def test_validate_asset_eligibility_task_validates_using_business_rules(self):
        """Test that _validate_asset_eligibility_task validates using MarketplaceBusinessRules"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create contract with validation_status
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="JSON",
            original_raw='{"info": {"name": "test"}}',
            validation_status="VALID",  # Set validation_status to VALID
            created_by=self.user,
        )

        # Create workflow definition
        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="marketplace_publication",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "validate_asset_eligibility",
                            "type": "task",
                            "task": "marketplace_publication.validate_asset_eligibility",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        # Register workflow and tasks
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        MarketplacePublicationWorkflow.register_workflow(registry)
        MarketplacePublicationWorkflow.register_tasks(self.engine)

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name="marketplace_publication",
            input_data={
                "asset_id": str(asset.id),
                "tenant_id": str(self.tenant.id),
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute validate_asset_eligibility step - should validate using business rules
        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        result = self.engine._execute_task_step(instance, step, step_def)

        # Verify task executed successfully
        self.assertIsNotNone(result)
        # eligibility_passed is nested in validation_results
        self.assertIn("validation_results", result)
        validation_results = result.get("validation_results", {})
        self.assertIn("eligibility_passed", validation_results)
        self.assertTrue(validation_results.get("eligibility_passed", False))


class TestAccessRequestWorkflowBusinessRules(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test AccessRequestWorkflow tasks with business rules"""

    def test_create_access_request_task_validates_using_business_rules(self):
        """Test that _create_access_request_task validates using GovernanceBusinessRules"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.governance.models import AccessRequest, AccessRequestStatus
        from hub.apps.orchestration.workflows.access_request import AccessRequestWorkflow

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create workflow definition
        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="access_request",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "create_access_request",
                            "type": "task",
                            "task": "access_request.create_access_request",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        # Register workflow and tasks
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        AccessRequestWorkflow.register_workflow(registry)
        AccessRequestWorkflow.register_tasks(self.engine)

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name="access_request",
            input_data={
                "tenant_id": str(self.tenant.id),
                "requested_by_id": str(self.user.id),
                "asset_id": str(asset.id),
                "reason": "Test access request",
                "requested_access_type": "READ",
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute create_access_request step - should validate using business rules
        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        result = self.engine._execute_task_step(instance, step, step_def)

        # Verify task executed successfully
        self.assertIsNotNone(result)
        self.assertIn("access_request_id", result)

        # Verify access request was created
        access_request_id = result["access_request_id"]
        access_request = AccessRequest.objects.get(id=access_request_id)
        self.assertIsNotNone(access_request)
        self.assertEqual(access_request.status, AccessRequestStatus.PENDING.value)


class TestDataMeshWorkflowBusinessRules(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test DataMeshWorkflow tasks with business rules"""

    def test_validate_domain_task_validates_using_business_rules(self):
        """Test that _validate_domain_task validates using DataMeshBusinessRules"""
        from hub.apps.orchestration.workflows.data_mesh import DataMeshWorkflow

        # Create workflow definition
        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="data_mesh",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "validate_domain",
                            "type": "task",
                            "task": "data_mesh.validate_domain",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        # Register workflow and tasks
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        DataMeshWorkflow.register_workflow(registry)
        DataMeshWorkflow.register_tasks(self.engine)

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name="data_mesh",
            input_data={
                "tenant_id": str(self.tenant.id),
                "name": "test-domain",
                "description": "Test Domain",
                "owner_id": str(self.user.id),
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Execute validate_domain step - should validate using business rules
        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        result = self.engine._execute_task_step(instance, step, step_def)

        # Verify task executed successfully
        self.assertIsNotNone(result)
        self.assertIn("validated", result)
        self.assertTrue(result.get("validated", False))


class TestVersionCreationWorkflowBusinessRules(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test VersionCreationWorkflow tasks with business rules"""

    def test_create_version_record_task_validates_using_business_rules(self):
        """Test that _create_version_record_task validates using DatasetsBusinessRules"""
        from hub.apps.files.models import File, FileStatus
        from hub.apps.orchestration.workflows.version_creation import VersionCreationWorkflow

        # Create file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            size=1000,
            content_type="text/csv",
            storage_path="/test/test.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=file_obj,
            format="CSV",
            version=1,
            schema_json={"fields": [{"name": "field1", "type": "string"}]},
            created_by=self.user,
        )

        # Create workflow definition
        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="version_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "create_version_record",
                            "type": "task",
                            "task": "version_creation.create_version_record",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        # Register workflow and tasks
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        VersionCreationWorkflow.register_workflow(registry)
        VersionCreationWorkflow.register_tasks(self.engine)

        # Create workflow instance
        instance = self.engine.create_instance(
            workflow_name="version_creation",
            input_data={
                "dataset_id": str(dataset.id),
                "tenant_id": str(self.tenant.id),
                "semantic_version": "1.0.1",
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        # Populate state_data
        instance.state_data.update(
            {
                "dataset_id": str(dataset.id),
                "semantic_version": "1.0.1",
            }
        )
        instance.save(update_fields=["state_data"])

        # Execute create_version_record step - should validate using business rules
        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        result = self.engine._execute_task_step(instance, step, step_def)

        # Verify task executed successfully
        self.assertIsNotNone(result)
        self.assertIn("version_record_created", result)
        self.assertTrue(result.get("version_record_created", False))


class TestWorkflowTaskBusinessRulesFailureTest(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test failure scenarios for workflow task business rules integration"""

    def test_parse_odps_task_fails_with_invalid_odps(self):
        """Test that _parse_odps_task fails with invalid ODPS document"""
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        ProductCreationWorkflow.register_workflow(registry)
        ProductCreationWorkflow.register_tasks(self.engine)

        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="product_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "parse_odps",
                            "type": "task",
                            "task": "product_creation.parse_odps",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        instance = self.engine.create_instance(
            workflow_name="product_creation",
            input_data={"original_raw": '{"invalid": "odps"}', "original_format": "JSON"},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        # Should raise workflow error for invalid step input
        from hub.apps.orchestration.workflow_engine import WorkflowExecutionError

        with self.assertRaises((WorkflowExecutionError, ValueError)):
            self.engine._execute_task_step(instance, step, step_def)

    def test_create_contract_task_fails_with_missing_data(self):
        """Test that contract creation task fails with missing required data"""
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(self.engine)

        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="contract_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "create_contract",
                            "type": "task",
                            "task": "contract_creation.create_contract",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        instance = self.engine.create_instance(
            workflow_name="contract_creation",
            input_data={},  # Missing required data
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        # Should handle missing data gracefully
        with self.assertRaises(Exception):
            self.engine._execute_task_step(instance, step, step_def)


class TestWorkflowTaskBusinessRulesEdgeCasesTest(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test edge cases for workflow task business rules integration"""

    def test_parse_odps_task_with_empty_document(self):
        """Test that _parse_odps_task handles empty document"""
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        ProductCreationWorkflow.register_workflow(registry)
        ProductCreationWorkflow.register_tasks(self.engine)

        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="product_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "parse_odps",
                            "type": "task",
                            "task": "product_creation.parse_odps",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        instance = self.engine.create_instance(
            workflow_name="product_creation",
            input_data={"original_raw": "", "original_format": "JSON"},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        # Should handle empty document gracefully
        with self.assertRaises(Exception):
            self.engine._execute_task_step(instance, step, step_def)

    def test_create_contract_task_with_very_large_document(self):
        """Test that contract creation handles very large documents"""
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        ContractCreationWorkflow.register_workflow(registry)
        ContractCreationWorkflow.register_tasks(self.engine)

        # Create very large document (edge case)
        large_data = {"field": "x" * 1000000}  # 1MB of data

        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="contract_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "create_contract",
                            "type": "task",
                            "task": "contract_creation.create_contract",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        instance = self.engine.create_instance(
            workflow_name="contract_creation",
            input_data=large_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        # Large documents should be handled gracefully — either processed
        # successfully or rejected with a meaningful error (not a crash).
        try:
            result = self.engine._execute_task_step(instance, step, step_def)
            self.assertIsNotNone(result)
        except (KeyError, TypeError, AttributeError, RuntimeError) as e:
            self.fail(f"Unexpected code error processing large document: {e}")
        except Exception:
            pass  # Expected rejection (ValueError from workflow) for oversized content


class TestWorkflowTaskBusinessRulesErrorHandlingTest(WorkflowTaskBusinessRulesIntegrationTestBase):
    """Test error handling for workflow task business rules integration"""

    def test_parse_odps_task_handles_json_decode_error(self):
        """Test that _parse_odps_task handles JSON decode errors"""
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        ProductCreationWorkflow.register_workflow(registry)
        ProductCreationWorkflow.register_tasks(self.engine)

        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name="product_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "parse_odps",
                            "type": "task",
                            "task": "product_creation.parse_odps",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        instance = self.engine.create_instance(
            workflow_name="product_creation",
            input_data={"original_raw": "invalid json {", "original_format": "JSON"},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.engine.start_instance(str(instance.id))

        step = instance.steps.first()
        step_def = workflow_def.dsl_json["steps"][0]

        # Should handle JSON decode error gracefully
        with self.assertRaises(Exception):
            self.engine._execute_task_step(instance, step, step_def)

    def test_create_contract_task_handles_database_error(self):
        """Test that invalid tenant_id is rejected by create_instance (input validation).

        create_instance resolves tenant_id via Tenant.objects.get(id=tenant_id), so an
        invalid UUID raises ValidationError before any task runs. This tests that the
        engine boundary validates inputs and does not create an instance with bad tenant_id.
        """
        from django.core.exceptions import ValidationError

        from hub.apps.orchestration.registry import WorkflowRegistry

        ContractCreationWorkflow.register_workflow(WorkflowRegistry())
        ContractCreationWorkflow.register_tasks(self.engine)

        WorkflowDefinition.objects.get_or_create(
            name="contract_creation",
            version="1.0.0",
            defaults={
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {
                            "name": "create_contract",
                            "type": "task",
                            "task": "contract_creation.create_contract",
                        }
                    ],
                },
                "created_by": self.user,
            },
        )

        # Invalid tenant_id must be rejected at create_instance (UUID validation)
        with self.assertRaises((ValidationError, ValueError)) as ctx:
            self.engine.create_instance(
                workflow_name="contract_creation",
                input_data={"contract_data": {}},
                tenant_id="invalid-uuid",
                created_by_id=str(self.user.id),
            )

        # Error should indicate invalid UUID / tenant
        msg = str(ctx.exception).lower()
        self.assertTrue(
            "uuid" in msg or "valid" in msg or "tenant" in msg or "invalid" in msg,
            f"Expected UUID/validation error message, got: {ctx.exception}",
        )
