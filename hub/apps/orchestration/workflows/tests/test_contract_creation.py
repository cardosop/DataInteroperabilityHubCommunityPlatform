"""
Tests for Contract Creation Workflow

Comprehensive unit, integration, and E2E tests for contract creation workflow.
"""
import json
import uuid
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import transaction

from hub.apps.orchestration.workflows.contract_creation import ContractCreationWorkflow
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, StepStatus
from hub.apps.contracts.models import Contract, ContractStatus, NormalizationStatus
from hub.apps.tenants.models import Tenant
from hub.apps.search.models import SearchIndex
from hub.apps.semantic.models import SemanticResource
from hub.apps.audit.models import AuditEvent

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
        self.sample_contract = {
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
        """Test contract normalization task with DCS contract (should fail)"""
        dcs_contract = {
            "dataContractSpecification": "1.0.0",
            "id": "test-contract"
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
        
        self.assertIn("DCS_NOT_SUPPORTED", str(cm.exception))
    
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
        
        self.sample_contract = {
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
            '/api/v1/contracts/contracts/',
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
            '/api/v1/contracts/contracts/',
            {
                'original_raw': json.dumps(self.sample_contract),
                'original_format': 'INVALID_FORMAT'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_contract_creation_with_dcs_contract(self):
        """Test contract creation with DCS contract (should return 400)"""
        from rest_framework.test import APIClient
        
        dcs_contract = {
            "dataContractSpecification": "1.0.0",
            "id": "test-contract"
        }
        
        client = APIClient()
        client.force_authenticate(user=self.user)
        
        response = client.post(
            '/api/v1/contracts/contracts/',
            {
                'original_raw': json.dumps(dcs_contract),
                'original_format': 'JSON'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('DCS_NOT_SUPPORTED', response_data.get('details', {}).get('code', ''))

