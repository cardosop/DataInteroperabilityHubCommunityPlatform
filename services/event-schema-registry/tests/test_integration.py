"""
Integration tests for event schema registry service.

Tests the event schema registry service end-to-end, including:
- Event schema retrieval
- Event type discovery
- Event data validation
- Schema version management
"""
import pytest
import os
import sys
import django
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

from fastapi.testclient import TestClient
from django.test import TestCase
from hub.apps.core.events.event_types import get_all_event_types, get_event_schema
from hub.apps.core.events.schema import BASE_EVENT_SCHEMA, EventSchema

# Import app using importlib to handle hyphen in module name
import importlib.util
main_module_path = Path(__file__).parent.parent / "main.py"
spec = importlib.util.spec_from_file_location("event_schema_registry_main", str(main_module_path))
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)
app = main_module.app


class EventSchemaRegistryServiceIntegrationTest(TestCase):
    """Integration tests for event schema registry service."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "event-schema-registry-service"
        assert "version" in data
        assert "total_event_types" in data
    
    def test_list_event_types(self):
        """Test listing all event types."""
        response = self.client.get("/event-types")
        assert response.status_code == 200
        data = response.json()
        assert "event_types" in data
        assert "total" in data
        assert "version" in data
        assert isinstance(data["event_types"], list)
        assert len(data["event_types"]) > 0
    
    def test_list_event_types_with_category_filter(self):
        """Test listing event types filtered by category."""
        response = self.client.get("/event-types?category=contract")
        assert response.status_code == 200
        data = response.json()
        assert "event_types" in data
        # All returned types should start with "contract."
        for event_type in data["event_types"]:
            assert event_type.startswith("contract.")
    
    def test_get_event_type_schema(self):
        """Test getting schema for a specific event type."""
        response = self.client.get("/event-types/contract.created")
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "contract.created"
        assert "schema" in data
        assert "version" in data
        assert "base_schema" in data
        assert data["schema"] is not None
    
    def test_get_event_type_schema_not_found(self):
        """Test getting schema for non-existent event type."""
        response = self.client.get("/event-types/nonexistent.event")
        assert response.status_code == 404
    
    def test_get_base_schema(self):
        """Test getting base event schema."""
        response = self.client.get("/base-schema")
        assert response.status_code == 200
        data = response.json()
        assert data == BASE_EVENT_SCHEMA
    
    def test_validate_event_data_valid(self):
        """Test validating valid event data."""
        request_data = {
            "event_type": "contract.created",
            "data": {
                "contract_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
        
        response = self.client.post("/validate", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["errors"]) == 0
    
    def test_validate_event_data_invalid_missing_required(self):
        """Test validating event data with missing required field."""
        request_data = {
            "event_type": "contract.created",
            "data": {}  # Missing required contract_id
        }
        
        response = self.client.post("/validate", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
    
    def test_validate_event_data_invalid_type(self):
        """Test validating event data with invalid type."""
        request_data = {
            "event_type": "contract.created",
            "data": {
                "contract_id": 123  # Should be string UUID
            }
        }
        
        response = self.client.post("/validate", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
    
    def test_validate_full_event_valid(self):
        """Test validating a complete valid event."""
        event = EventSchema.build_event(
            event_type="contract.created",
            data={"contract_id": "123e4567-e89b-12d3-a456-426614174000"}
        )
        
        response = self.client.post("/validate-full", json=event)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["errors"]) == 0
    
    def test_validate_full_event_invalid(self):
        """Test validating an invalid complete event."""
        event = {
            "event_id": "invalid-uuid",  # Invalid UUID
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": "2025-01-15T10:00:00Z",
            "source": {
                "service": "hub",
                "tenant_id": None
            },
            "data": {
                "contract_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
        
        response = self.client.post("/validate-full", json=event)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
    
    def test_get_event_categories(self):
        """Test getting list of event categories."""
        response = self.client.get("/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "total" in data
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) > 0
        # Verify common categories exist
        assert "contract" in data["categories"]
        assert "asset" in data["categories"]
    
    def test_get_category_event_types(self):
        """Test getting event types for a specific category."""
        response = self.client.get("/categories/contract/event-types")
        assert response.status_code == 200
        data = response.json()
        assert "event_types" in data
        assert "total" in data
        assert "version" in data
        # All types should start with "contract."
        for event_type in data["event_types"]:
            assert event_type.startswith("contract.")
    
    def test_get_category_event_types_not_found(self):
        """Test getting event types for non-existent category."""
        response = self.client.get("/categories/nonexistent/event-types")
        assert response.status_code == 404
    
    def test_get_schema_version(self):
        """Test getting current schema version."""
        response = self.client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "total_event_types" in data
        assert "total_categories" in data
    
    def test_get_event_type_version(self):
        """Test getting version for specific event type."""
        response = self.client.get("/version/contract.created")
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "contract.created"
        assert "version" in data
        assert data["has_schema"] is True
    
    def test_get_event_type_version_not_found(self):
        """Test getting version for non-existent event type."""
        response = self.client.get("/version/nonexistent.event")
        assert response.status_code == 404
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
    
    def test_multiple_event_types(self):
        """Test retrieving schemas for multiple event types."""
        event_types = ["contract.created", "asset.created", "workflow.started"]
        
        for event_type in event_types:
            response = self.client.get(f"/event-types/{event_type}")
            assert response.status_code == 200
            data = response.json()
            assert data["event_type"] == event_type
            assert "schema" in data
    
    def test_validate_multiple_event_types(self):
        """Test validating data for multiple event types."""
        test_cases = [
            {
                "event_type": "contract.created",
                "data": {"contract_id": "123e4567-e89b-12d3-a456-426614174000"},
                "should_be_valid": True
            },
            {
                "event_type": "asset.created",
                "data": {"asset_id": "123e4567-e89b-12d3-a456-426614174000"},
                "should_be_valid": True
            },
            {
                "event_type": "contract.created",
                "data": {},  # Missing required field
                "should_be_valid": False
            }
        ]
        
        for test_case in test_cases:
            request_data = {
                "event_type": test_case["event_type"],
                "data": test_case["data"]
            }
            
            response = self.client.post("/validate", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] == test_case["should_be_valid"]

