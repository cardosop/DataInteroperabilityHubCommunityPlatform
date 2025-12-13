"""
Integration tests for workflow engine service.

Tests the workflow engine service end-to-end, including:
- Workflow instance processing
- Health check endpoints
- Service startup and shutdown
"""
import pytest
import time
import requests
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry


class WorkflowEngineServiceIntegrationTest(TestCase):
    """Integration tests for workflow engine service."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.workflow_engine = WorkflowEngine()
        self.workflow_registry = WorkflowRegistry()
        
        # Register workflow tasks
        from hub.apps.orchestration.workflows import (
            ContractCreationWorkflow,
            ScheduledIngestionWorkflow,
            AccessRequestWorkflow,
            DataQualityCheckWorkflow,
            ComplianceReportingWorkflow,
            AssetCreationWorkflow,
            DatasetCreationWorkflow,
            VersionCreationWorkflow,
            MarketplacePublicationWorkflow,
        )
        
        workflow_classes = [
            ContractCreationWorkflow,
            ScheduledIngestionWorkflow,
            AccessRequestWorkflow,
            DataQualityCheckWorkflow,
            ComplianceReportingWorkflow,
            AssetCreationWorkflow,
            DatasetCreationWorkflow,
            VersionCreationWorkflow,
            MarketplacePublicationWorkflow,
        ]
        
        for workflow_class in workflow_classes:
            if hasattr(workflow_class, 'register_tasks'):
                workflow_class.register_tasks(self.workflow_engine)
    
    def test_create_and_process_draft_workflow(self):
        """Test creating a DRAFT workflow and processing it."""
        # Create a simple workflow definition
        workflow_dsl = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "test_step",
                    "type": "task",
                    "task": "test_task",
                }
            ]
        }
        
        # Register a test task
        def test_task(input_data, instance, step):
            return {"result": "success", "output": "test completed"}
        
        self.workflow_engine.register_task("test_task", test_task)
        
        # Create workflow definition
        workflow_def = self.workflow_registry.register_workflow(
            workflow_name="test_workflow",
            dsl_json=workflow_dsl,
            version="1.0.0"
        )
        
        # Create workflow instance
        instance = self.workflow_engine.create_instance(
            workflow_name="test_workflow",
            input_data={"test": "data"}
        )
        
        # Verify instance is in DRAFT status
        self.assertEqual(instance.status, WorkflowStatus.DRAFT)
        
        # Process the workflow (start and execute)
        self.workflow_engine.start_instance(str(instance.id))
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowStatus.RUNNING)
        
        self.workflow_engine.execute_instance(str(instance.id))
        instance.refresh_from_db()
        
        # Verify workflow completed
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertIsNotNone(instance.output_data)
    
    def test_process_running_workflow(self):
        """Test continuing execution of a RUNNING workflow."""
        # Create a workflow with multiple steps
        workflow_dsl = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "test_task1",
                },
                {
                    "name": "step2",
                    "type": "task",
                    "task": "test_task2",
                }
            ]
        }
        
        # Register test tasks
        def test_task1(input_data, instance, step):
            return {"step1": "done"}
        
        def test_task2(input_data, instance, step):
            return {"step2": "done"}
        
        self.workflow_engine.register_task("test_task1", test_task1)
        self.workflow_engine.register_task("test_task2", test_task2)
        
        # Create workflow definition
        workflow_def = self.workflow_registry.register_workflow(
            workflow_name="test_multi_step_workflow",
            dsl_json=workflow_dsl,
            version="1.0.0"
        )
        
        # Create and start workflow instance
        instance = self.workflow_engine.create_instance(
            workflow_name="test_multi_step_workflow",
            input_data={}
        )
        
        self.workflow_engine.start_instance(str(instance.id))
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowStatus.RUNNING)
        
        # Execute first step
        self.workflow_engine.execute_instance(str(instance.id))
        instance.refresh_from_db()
        
        # Verify first step completed and workflow is still running or completed
        self.assertIn(instance.status, [WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED])
        
        # If still running, continue execution
        if instance.status == WorkflowStatus.RUNNING:
            self.workflow_engine.execute_instance(str(instance.id))
            instance.refresh_from_db()
            self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
    
    def test_workflow_processing_with_batch(self):
        """Test processing multiple workflows in a batch."""
        # Create multiple workflow instances
        workflow_dsl = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "test_step",
                    "type": "task",
                    "task": "test_task",
                }
            ]
        }
        
        def test_task(input_data, instance, step):
            return {"result": "success"}
        
        self.workflow_engine.register_task("test_task", test_task)
        
        workflow_def = self.workflow_registry.register_workflow(
            workflow_name="batch_test_workflow",
            dsl_json=workflow_dsl,
            version="1.0.0"
        )
        
        # Create 3 workflow instances
        instances = []
        for i in range(3):
            instance = self.workflow_engine.create_instance(
                workflow_name="batch_test_workflow",
                input_data={"index": i}
            )
            instances.append(instance)
        
        # Verify all are in DRAFT status
        for instance in instances:
            self.assertEqual(instance.status, WorkflowStatus.DRAFT)
        
        # Process all workflows
        for instance in instances:
            self.workflow_engine.start_instance(str(instance.id))
            self.workflow_engine.execute_instance(str(instance.id))
            instance.refresh_from_db()
            self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
    
    def test_workflow_processing_with_errors(self):
        """Test workflow processing handles errors gracefully."""
        workflow_dsl = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "failing_step",
                    "type": "task",
                    "task": "failing_task",
                }
            ]
        }
        
        def failing_task(input_data, instance, step):
            raise ValueError("Task failed intentionally")
        
        self.workflow_engine.register_task("failing_task", failing_task)
        
        workflow_def = self.workflow_registry.register_workflow(
            workflow_name="failing_workflow",
            dsl_json=workflow_dsl,
            version="1.0.0"
        )
        
        # Create workflow instance
        instance = self.workflow_engine.create_instance(
            workflow_name="failing_workflow",
            input_data={}
        )
        
        # Process workflow (should handle error)
        self.workflow_engine.start_instance(str(instance.id))
        
        try:
            self.workflow_engine.execute_instance(str(instance.id))
        except Exception:
            pass  # Expected to fail
        
        instance.refresh_from_db()
        
        # Verify workflow is marked as failed
        self.assertEqual(instance.status, WorkflowStatus.FAILED)
        self.assertIsNotNone(instance.error_message)

