"""
Unit tests for workflow registry.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError

from hub.apps.orchestration.models import WorkflowDefinition
from hub.apps.orchestration.registry import WorkflowRegistry

pytestmark = pytest.mark.django_db(transaction=True)


class WorkflowRegistryTest(TestCase):
    """Test WorkflowRegistry"""
    
    def setUp(self):
        self.registry = WorkflowRegistry()
        self.valid_dsl = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "test_task"
                }
            ]
        }
    
    def test_register_workflow(self):
        """Test registering a workflow"""
        workflow_def = self.registry.register_workflow(
            workflow_name="test_workflow",
            dsl_json=self.valid_dsl
        )
        
        self.assertEqual(workflow_def.name, "test_workflow")
        self.assertEqual(workflow_def.version, "1.0.0")
    
    def test_register_workflow_invalid_dsl(self):
        """Test registering workflow with invalid DSL"""
        invalid_dsl = {"invalid": "dsl"}
        
        with self.assertRaises(ValidationError):
            self.registry.register_workflow(
                workflow_name="test_workflow",
                dsl_json=invalid_dsl
            )
    
    def test_discover_workflows_by_name(self):
        """Test discovering workflows by name"""
        self.registry.register_workflow(
            workflow_name="test_workflow",
            dsl_json=self.valid_dsl
        )
        self.registry.register_workflow(
            workflow_name="other_workflow",
            dsl_json=self.valid_dsl
        )
        
        workflows = self.registry.discover_workflows(workflow_name="test_workflow")
        
        self.assertEqual(len(workflows), 1)
        self.assertEqual(workflows[0].name, "test_workflow")
    
    def test_discover_workflows_active(self):
        """Test discovering active workflows"""
        self.registry.register_workflow(
            workflow_name="test_workflow",
            dsl_json=self.valid_dsl
        )
        
        # Create inactive version
        WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.1",
            dsl_json=self.valid_dsl,
            is_active=False
        )
        
        workflows = self.registry.discover_workflows(is_active=True)
        
        # Should only return active workflows
        self.assertTrue(all(w.is_active for w in workflows))
    
    def test_get_workflow(self):
        """Test getting a workflow"""
        self.registry.register_workflow(
            workflow_name="test_workflow",
            dsl_json=self.valid_dsl
        )
        
        workflow_def = self.registry.get_workflow("test_workflow")
        
        self.assertIsNotNone(workflow_def)
        self.assertEqual(workflow_def.name, "test_workflow")
    
    def test_get_dependencies(self):
        """Test getting workflow dependencies"""
        # Register dependency workflow
        self.registry.register_workflow(
            workflow_name="dependency_workflow",
            dsl_json=self.valid_dsl
        )
        
        # Register workflow with dependency
        dsl_with_dep = {
            "version": "1.0.0",
            "dependencies": ["dependency_workflow"],
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "test_task"
                }
            ]
        }
        
        self.registry.register_workflow(
            workflow_name="test_workflow",
            dsl_json=dsl_with_dep
        )
        
        dependencies = self.registry.get_dependencies("test_workflow")
        
        self.assertIn("dependency_workflow", dependencies)
    
    def test_get_dependents(self):
        """Test getting workflows that depend on a workflow"""
        # Register base workflow
        self.registry.register_workflow(
            workflow_name="base_workflow",
            dsl_json=self.valid_dsl
        )
        
        # Register dependent workflow
        dsl_with_dep = {
            "version": "1.0.0",
            "dependencies": ["base_workflow"],
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "test_task"
                }
            ]
        }
        
        self.registry.register_workflow(
            workflow_name="dependent_workflow",
            dsl_json=dsl_with_dep
        )
        
        dependents = self.registry.get_dependents("base_workflow")
        
        self.assertIn("dependent_workflow", dependents)
    
    def test_validate_workflow_valid(self):
        """Test validating valid workflow"""
        self.registry.register_workflow(
            workflow_name="test_workflow",
            dsl_json=self.valid_dsl
        )
        
        result = self.registry.validate_workflow("test_workflow")
        
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
    
    def test_validate_workflow_not_found(self):
        """Test validating non-existent workflow"""
        result = self.registry.validate_workflow("nonexistent_workflow")
        
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)
    
    def test_validate_workflow_missing_dependency(self):
        """Test validating workflow with missing dependency"""
        dsl_with_dep = {
            "version": "1.0.0",
            "dependencies": ["nonexistent_workflow"],
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "test_task"
                }
            ]
        }
        
        # Manually create workflow with invalid dependency
        workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json=dsl_with_dep,
            dependencies=["nonexistent_workflow"]
        )
        
        # Rebuild dependency graph
        self.registry.build_dependency_graph()
        
        result = self.registry.validate_workflow("test_workflow")
        
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)

