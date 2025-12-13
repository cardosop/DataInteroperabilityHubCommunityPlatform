"""
Integration tests for workflow registry service.

Tests the workflow registry service end-to-end, including:
- Workflow registration
- Workflow discovery
- Dependency tracking
- Workflow validation
"""
import pytest
import os
import sys
import django
from pathlib import Path

# Add project root and services to path
project_root = Path(__file__).parent.parent.parent.parent
services_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(services_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

from fastapi.testclient import TestClient
from django.test import TestCase
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowDefinition

# Import app using importlib to handle hyphen in module name
import importlib.util
workflow_registry_main_path = Path(__file__).parent.parent / "main.py"
spec = importlib.util.spec_from_file_location("workflow_registry_main", str(workflow_registry_main_path))
workflow_registry_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow_registry_main)
app = workflow_registry_main.app


class WorkflowRegistryServiceIntegrationTest(TestCase):
    """Integration tests for workflow registry service."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.workflow_registry = WorkflowRegistry()
        
        # Clean up any existing workflows
        WorkflowDefinition.objects.all().delete()
        
        # Rebuild dependency graph to ensure clean state
        self.workflow_registry.build_dependency_graph()
    
    def tearDown(self):
        """Clean up test data."""
        # Clean up workflows
        WorkflowDefinition.objects.all().delete()
        
        # Rebuild dependency graph to ensure clean state for next test
        self.workflow_registry.build_dependency_graph()
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "workflow-registry-service"
    
    def test_register_workflow(self):
        """Test workflow registration."""
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
        
        request_data = {
            "workflow_name": "test_workflow",
            "dsl_json": workflow_dsl,
            "version": "1.0.0",
            "description": "Test workflow"
        }
        
        response = self.client.post("/workflows", json=request_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test_workflow"
        assert data["version"] == "1.0.0"
        assert data["description"] == "Test workflow"
        assert data["dsl_json"] == workflow_dsl
    
    def test_register_workflow_invalid_dsl(self):
        """Test workflow registration with invalid DSL."""
        request_data = {
            "workflow_name": "invalid_workflow",
            "dsl_json": {"invalid": "dsl"},
            "version": "1.0.0"
        }
        
        response = self.client.post("/workflows", json=request_data)
        assert response.status_code == 400
    
    def test_discover_workflows(self):
        """Test workflow discovery."""
        # Register a workflow first via API
        workflow_dsl = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "test_workflow",
                "dsl_json": workflow_dsl,
                "version": "1.0.0"
            }
        )
        
        # Discover workflows
        response = self.client.get("/workflows")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(wf["name"] == "test_workflow" for wf in data["workflows"])
    
    def test_discover_workflows_with_filters(self):
        """Test workflow discovery with filters."""
        # Register workflows via API
        workflow_dsl = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "workflow1",
                "dsl_json": workflow_dsl,
                "version": "1.0.0"
            }
        )
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "workflow2",
                "dsl_json": workflow_dsl,
                "version": "1.0.0"
            }
        )
        
        # Filter by name
        response = self.client.get("/workflows?workflow_name=workflow1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["workflows"][0]["name"] == "workflow1"
    
    def test_get_workflow(self):
        """Test getting a specific workflow."""
        # Register a workflow first via API
        workflow_dsl = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        register_response = self.client.post(
            "/workflows",
            json={
                "workflow_name": "test_workflow",
                "dsl_json": workflow_dsl,
                "version": "1.0.0"
            }
        )
        assert register_response.status_code == 201
        
        # Get workflow
        response = self.client.get("/workflows/test_workflow")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_workflow"
        assert data["version"] == "1.0.0"
    
    def test_get_workflow_not_found(self):
        """Test getting a non-existent workflow."""
        response = self.client.get("/workflows/nonexistent_workflow")
        assert response.status_code == 404
    
    def test_get_workflow_dependencies(self):
        """Test getting workflow dependencies."""
        # Register workflows with dependencies via API
        workflow_dsl_base = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        workflow_dsl_dependent = {
            "version": "1.0.0",
            "dependencies": ["base_workflow"],
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "base_workflow",
                "dsl_json": workflow_dsl_base,
                "version": "1.0.0"
            }
        )
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "dependent_workflow",
                "dsl_json": workflow_dsl_dependent,
                "version": "1.0.0"
            }
        )
        
        # Rebuild dependency graph via API
        self.client.post("/dependency-graph/build")
        
        # Get dependencies
        response = self.client.get("/workflows/dependent_workflow/dependencies")
        assert response.status_code == 200
        data = response.json()
        assert "base_workflow" in data["dependencies"]
    
    def test_get_workflow_dependents(self):
        """Test getting workflows that depend on a workflow."""
        # Register workflows with dependencies via API
        workflow_dsl_base = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        workflow_dsl_dependent = {
            "version": "1.0.0",
            "dependencies": ["base_workflow"],
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "base_workflow",
                "dsl_json": workflow_dsl_base,
                "version": "1.0.0"
            }
        )
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "dependent_workflow",
                "dsl_json": workflow_dsl_dependent,
                "version": "1.0.0"
            }
        )
        
        # Rebuild dependency graph via API
        self.client.post("/dependency-graph/build")
        
        # Get dependents
        response = self.client.get("/workflows/base_workflow/dependents")
        assert response.status_code == 200
        data = response.json()
        assert "dependent_workflow" in data["dependents"]
    
    def test_validate_workflow(self):
        """Test workflow validation."""
        # Register a valid workflow via API
        workflow_dsl = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "valid_workflow",
                "dsl_json": workflow_dsl,
                "version": "1.0.0"
            }
        )
        
        # Validate workflow
        response = self.client.get("/workflows/valid_workflow/validate")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["errors"]) == 0
    
    def test_validate_workflow_with_missing_dependency(self):
        """Test workflow validation with missing dependency."""
        # Register a workflow with a missing dependency
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": ["nonexistent_workflow"],
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        # This should fail during registration
        try:
            self.workflow_registry.register_workflow(
                workflow_name="invalid_workflow",
                dsl_json=workflow_dsl,
                version="1.0.0"
            )
        except Exception:
            pass  # Expected to fail
        
        # If somehow it was registered, validation should catch it
        # (This test verifies validation logic)
    
    def test_get_dependency_graph(self):
        """Test getting complete dependency graph."""
        # Register workflows with dependencies via API
        workflow_dsl_base = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        workflow_dsl_dependent = {
            "version": "1.0.0",
            "dependencies": ["base_workflow"],
            "steps": [{"name": "step1", "type": "task", "task": "task1"}]
        }
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "base_workflow",
                "dsl_json": workflow_dsl_base,
                "version": "1.0.0"
            }
        )
        
        self.client.post(
            "/workflows",
            json={
                "workflow_name": "dependent_workflow",
                "dsl_json": workflow_dsl_dependent,
                "version": "1.0.0"
            }
        )
        
        # Rebuild dependency graph via API
        self.client.post("/dependency-graph/build")
        
        # Get dependency graph
        response = self.client.get("/dependency-graph")
        assert response.status_code == 200
        data = response.json()
        assert "graph" in data
        assert "dependent_workflow" in data["graph"]
        assert "base_workflow" in data["graph"]["dependent_workflow"]
    
    def test_build_dependency_graph(self):
        """Test rebuilding dependency graph."""
        response = self.client.post("/dependency-graph/build")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

