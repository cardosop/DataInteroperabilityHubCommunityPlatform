"""
Comprehensive tests for Virtualization Serializers.

Tests cover:
- Serialization/deserialization
- Validation (required fields, data types, constraints)
- Edge cases and error handling
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus
from hub.apps.virtualization.models import (
    QueryExecution,
    QueryExecutionMode,
    QueryExecutionStatus,
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)
from hub.apps.virtualization.serializers import (
    DatasetTopologySerializer,
    QueryExecutionCreateSerializer,
    QueryExecutionResultSerializer,
    QueryExecutionSerializer,
    VirtualDatasetCreateSerializer,
    VirtualDatasetSerializer,
    VirtualDatasetUpdateSerializer,
    VirtualizationTopologySerializer,
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VirtualDatasetCreateSerializerTest(TestCase):
    """Test VirtualDatasetCreateSerializer validation and serialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.valid_data = {
            "name": "Test Virtual Dataset",
            "description": "Test description",
            "query": "SELECT * FROM test_table",
            "query_type": QueryType.SQL,
            "schema": {"fields": [{"name": "id", "type": "integer"}]},
            "sources": [{"type": "database", "connection": "postgresql://..."}],
            "version": "1.0.0",
            "status": VirtualDatasetStatus.DRAFT,
        }

    def test_valid_serialization(self):
        """Test serialization with valid data"""
        serializer = VirtualDatasetCreateSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        validated_data = serializer.validated_data
        self.assertEqual(validated_data["name"], "Test Virtual Dataset")
        self.assertEqual(validated_data["query"], "SELECT * FROM test_table")
        self.assertEqual(validated_data["query_type"], QueryType.SQL)

    def test_required_fields(self):
        """Test that required fields are validated"""
        # Missing name
        data = self.valid_data.copy()
        data.pop("name")
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

        # Missing query
        data = self.valid_data.copy()
        data.pop("query")
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("query", serializer.errors)

        # Missing query_type
        data = self.valid_data.copy()
        data.pop("query_type")
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("query_type", serializer.errors)

    def test_name_validation(self):
        """Test name field validation"""
        # Empty name
        data = self.valid_data.copy()
        data["name"] = ""
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

        # Whitespace-only name
        data = self.valid_data.copy()
        data["name"] = "   "
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

        # Name too long
        data = self.valid_data.copy()
        data["name"] = "a" * 256
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

        # Valid name (should be trimmed)
        data = self.valid_data.copy()
        data["name"] = "  Test Dataset  "
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Test Dataset")

    def test_query_validation(self):
        """Test query field validation"""
        # Empty query
        data = self.valid_data.copy()
        data["query"] = ""
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("query", serializer.errors)

        # Whitespace-only query
        data = self.valid_data.copy()
        data["query"] = "   "
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("query", serializer.errors)

        # Valid query (should be trimmed)
        data = self.valid_data.copy()
        data["query"] = "  SELECT * FROM table  "
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["query"], "SELECT * FROM table")

    def test_schema_validation(self):
        """Test schema field validation"""
        # Valid schema (dict)
        data = self.valid_data.copy()
        data["schema"] = {"fields": [{"name": "id", "type": "integer"}]}
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Invalid schema (list instead of dict)
        data = self.valid_data.copy()
        data["schema"] = [{"name": "id", "type": "integer"}]
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("schema", serializer.errors)

        # Null schema (should be allowed)
        data = self.valid_data.copy()
        data["schema"] = None
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_sources_validation(self):
        """Test sources field validation"""
        # Valid sources (list)
        data = self.valid_data.copy()
        data["sources"] = [{"type": "database", "connection": "postgresql://..."}]
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Invalid sources (dict instead of list)
        data = self.valid_data.copy()
        data["sources"] = {"type": "database"}
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("sources", serializer.errors)

        # Null sources (should be allowed)
        data = self.valid_data.copy()
        data["sources"] = None
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_version_validation(self):
        """Test version field validation"""
        # Valid version
        data = self.valid_data.copy()
        data["version"] = "1.2.3"
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Invalid version format (missing parts)
        data = self.valid_data.copy()
        data["version"] = "1.2"
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("version", serializer.errors)

        # Invalid version format (non-numeric)
        data = self.valid_data.copy()
        data["version"] = "1.2.a"
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("version", serializer.errors)

        # Default version when not provided
        data = self.valid_data.copy()
        data.pop("version")
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["version"], "1.0.0")

    def test_query_type_validation(self):
        """Test query type validation with query content"""
        # Valid SQL query
        data = self.valid_data.copy()
        data["query"] = "SELECT * FROM table"
        data["query_type"] = QueryType.SQL
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Invalid SQL query (no SQL keywords)
        data = self.valid_data.copy()
        data["query"] = "just some text"
        data["query_type"] = QueryType.SQL
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("query", serializer.errors)

        # Valid SPARQL query
        data = self.valid_data.copy()
        data["query"] = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
        data["query_type"] = QueryType.SPARQL
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Invalid SPARQL query (no SPARQL keywords)
        data = self.valid_data.copy()
        data["query"] = "just some text"
        data["query_type"] = QueryType.SPARQL
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("query", serializer.errors)

    def test_status_default(self):
        """Test status default value"""
        data = self.valid_data.copy()
        data.pop("status")
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["status"], VirtualDatasetStatus.DRAFT)

    def test_valid_serialization_tdd(self):
        """TDD: validated_data contains required keys after valid serialization."""
        serializer = VirtualDatasetCreateSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        v = serializer.validated_data
        for key in ("name", "query", "query_type", "schema", "sources", "version", "status"):
            self.assertIn(key, v, f"Missing validated_data key: {key}")

    def test_failure_empty_name_returns_error(self):
        """Failure: empty name produces validation error with message."""
        serializer = VirtualDatasetCreateSerializer(data={**self.valid_data, "name": ""})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)
        self.assertTrue(len(serializer.errors["name"]) > 0)

    def test_edge_case_empty_sources_list(self):
        """Edge case: empty sources list is valid."""
        data = self.valid_data.copy()
        data["sources"] = []
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["sources"], [])

    def test_error_handling_invalid_query_type(self):
        """Error handling: invalid query_type returns field error."""
        data = self.valid_data.copy()
        data["query_type"] = "INVALID_TYPE"
        serializer = VirtualDatasetCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("query_type", serializer.errors)


class VirtualDatasetUpdateSerializerTest(TestCase):
    """Test VirtualDatasetUpdateSerializer validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

        self.valid_data = {"name": "Updated Dataset Name", "description": "Updated description"}

    def test_partial_update(self):
        """Test that all fields are optional for update"""
        serializer = VirtualDatasetUpdateSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())

        # Empty data should be valid (no changes)
        serializer = VirtualDatasetUpdateSerializer(data={})
        self.assertTrue(serializer.is_valid())

    def test_name_validation_on_update(self):
        """Test name validation when provided in update"""
        # Empty name
        data = {"name": ""}
        serializer = VirtualDatasetUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

        # Valid name
        data = {"name": "Updated Name"}
        serializer = VirtualDatasetUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Updated Name")

    def test_schema_validation_on_update(self):
        """Test schema validation when provided in update"""
        # Invalid schema (list instead of dict)
        data = {"schema": [{"name": "id"}]}
        serializer = VirtualDatasetUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("schema", serializer.errors)

        # Valid schema
        data = {"schema": {"fields": [{"name": "id"}]}}
        serializer = VirtualDatasetUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class VirtualDatasetSerializerTest(TestCase):
    """Test VirtualDatasetSerializer serialization/deserialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            description="Test description",
            query="SELECT * FROM test_table",
            query_type=QueryType.SQL,
            schema={"fields": [{"name": "id", "type": "integer"}]},
            sources=[{"type": "database"}],
            version="1.0.0",
            status=VirtualDatasetStatus.ACTIVE,
        )

    def test_serialization(self):
        """Test serialization of VirtualDataset model"""
        serializer = VirtualDatasetSerializer(self.virtual_dataset)
        data = serializer.data

        self.assertEqual(data["id"], str(self.virtual_dataset.id))
        self.assertEqual(data["name"], "Test Virtual Dataset")
        self.assertEqual(data["description"], "Test description")
        self.assertEqual(data["query"], "SELECT * FROM test_table")
        self.assertEqual(data["query_type"], QueryType.SQL)
        self.assertEqual(data["status"], VirtualDatasetStatus.ACTIVE)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_read_only_fields(self):
        """Test that read-only fields cannot be set"""
        serializer = VirtualDatasetSerializer(
            self.virtual_dataset, data={"id": "new-id", "name": "New Name"}, partial=True
        )
        # Read-only fields should be ignored
        self.assertTrue(serializer.is_valid())
        # ID should remain unchanged
        self.assertEqual(serializer.instance.id, self.virtual_dataset.id)

    def test_sources_credential_masking(self):
        """Test that password and connection_string in sources are masked in API response."""
        dataset_with_secrets = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset With Secrets",
            query="SELECT 1",
            query_type=QueryType.SQL,
            sources=[
                {"type": "postgresql", "host": "db1", "database": "mydb", "password": "secret123"},
                {"type": "odbc", "connection_string": "DRIVER={PG};PWD=odbc_secret"},
            ],
            status=VirtualDatasetStatus.ACTIVE,
        )
        serializer = VirtualDatasetSerializer(dataset_with_secrets)
        data = serializer.data
        self.assertEqual(data["sources"][0]["password"], "***masked***")
        self.assertEqual(data["sources"][1]["connection_string"], "***masked***")
        self.assertEqual(data["sources"][0]["host"], "db1")
        self.assertEqual(data["sources"][0]["database"], "mydb")


class QueryExecutionCreateSerializerTest(TestCase):
    """Test QueryExecutionCreateSerializer validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.valid_data = {
            "parameters": {"param1": "value1"},
            "execution_mode": QueryExecutionMode.SYNC,
            "force_async": False,
            "timeout_seconds": 300,
        }

    def test_valid_serialization(self):
        """Test serialization with valid data"""
        serializer = QueryExecutionCreateSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")

    def test_parameters_validation(self):
        """Test parameters field validation"""
        # Valid parameters (dict)
        data = {"parameters": {"param1": "value1"}}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Invalid parameters (list instead of dict)
        data = {"parameters": ["param1", "value1"]}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("parameters", serializer.errors)

        # Null parameters (should default to empty dict)
        data = {"parameters": None}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["parameters"], {})

        # Missing parameters (should default to empty dict)
        data = {}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["parameters"], {})

    def test_timeout_validation(self):
        """Test timeout_seconds validation"""
        # Valid timeout
        data = {"timeout_seconds": 300}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Timeout too small
        data = {"timeout_seconds": 0}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("timeout_seconds", serializer.errors)

        # Timeout too large
        data = {"timeout_seconds": 100000}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("timeout_seconds", serializer.errors)

        # Null timeout (should be allowed)
        data = {"timeout_seconds": None}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_execution_mode_validation(self):
        """Test execution_mode validation"""
        # Valid execution mode
        data = {"execution_mode": QueryExecutionMode.SYNC}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Invalid execution mode
        data = {"execution_mode": "INVALID"}
        serializer = QueryExecutionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("execution_mode", serializer.errors)


class QueryExecutionSerializerTest(TestCase):
    """Test QueryExecutionSerializer serialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT * FROM test_table",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.query_execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table WHERE id = :id",
            parameters={"id": 123},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
        )

    def test_serialization(self):
        """Test serialization of QueryExecution model"""
        serializer = QueryExecutionSerializer(self.query_execution)
        data = serializer.data

        self.assertEqual(data["id"], str(self.query_execution.id))
        self.assertEqual(data["virtual_dataset"], str(self.virtual_dataset.id))
        self.assertEqual(data["virtual_dataset_name"], "Test Virtual Dataset")
        self.assertEqual(data["query"], "SELECT * FROM test_table WHERE id = :id")
        self.assertEqual(data["parameters"], {"id": 123})
        self.assertEqual(data["execution_mode"], QueryExecutionMode.SYNC)
        self.assertEqual(data["status"], QueryExecutionStatus.COMPLETED)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_read_only_fields(self):
        """Test that read-only fields are properly marked"""
        serializer = QueryExecutionSerializer(self.query_execution)
        # All fields except query, parameters, execution_mode should be read-only
        self.assertIn("id", serializer.fields)
        self.assertTrue(serializer.fields["id"].read_only)


class QueryExecutionResultSerializerTest(TestCase):
    """Test QueryExecutionResultSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        import uuid

        self.valid_data = {
            "execution_id": uuid.uuid4(),
            "data": [{"id": 1, "name": "test"}],
            "total_count": 100,
            "returned_count": 10,
            "format": "json",
            "content_type": "application/json",
            "pagination": {"page": 1, "page_size": 10},
            "stream_enabled": False,
        }

    def test_valid_serialization(self):
        """Test serialization with valid data"""
        serializer = QueryExecutionResultSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")

    def test_required_fields(self):
        """Test that required fields are validated"""
        # Missing execution_id
        data = self.valid_data.copy()
        data.pop("execution_id")
        serializer = QueryExecutionResultSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("execution_id", serializer.errors)

        # Missing data
        data = self.valid_data.copy()
        data.pop("data")
        serializer = QueryExecutionResultSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("data", serializer.errors)


class TopologySerializerTest(TestCase):
    """Test Topology serializers"""

    def setUp(self):
        """Set up test fixtures"""
        import uuid
        from datetime import datetime

        from django.utils import timezone

        self.topology_data = {
            "nodes": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Test Dataset",
                    "description": "Test",
                    "status": VirtualDatasetStatus.ACTIVE,
                    "query_type": QueryType.SQL,
                    "version": "1.0.0",
                    "created_by_id": str(uuid.uuid4()),
                    "created_at": timezone.now(),
                    "updated_at": timezone.now(),
                }
            ],
            "edges": [
                {
                    "source": str(uuid.uuid4()),
                    "target": str(uuid.uuid4()),
                    "type": "SHARED_SOURCE",
                    "weight": 1,
                }
            ],
            "metadata": {
                "tenant_id": str(uuid.uuid4()),
                "dataset_count": 1,
                "relationship_count": 1,
                "generated_at": timezone.now(),
            },
            "summary": {
                "total_datasets": 1,
                "active_datasets": 1,
                "total_relationships": 1,
                "average_health_score": 100.0,
            },
        }

    def test_virtualization_topology_serialization(self):
        """Test VirtualizationTopologySerializer"""
        serializer = VirtualizationTopologySerializer(data=self.topology_data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")

    def test_dataset_topology_serialization(self):
        """Test DatasetTopologySerializer"""
        import uuid

        from django.utils import timezone

        dataset_topology_data = {
            "dataset": {
                "id": str(uuid.uuid4()),
                "name": "Test Dataset",
                "description": "Test",
                "status": VirtualDatasetStatus.ACTIVE,
                "query_type": QueryType.SQL,
                "version": "1.0.0",
                "created_by_id": str(uuid.uuid4()),
                "created_at": timezone.now(),
                "updated_at": timezone.now(),
            },
            "relationships": [
                {
                    "source": str(uuid.uuid4()),
                    "target": str(uuid.uuid4()),
                    "type": "SHARED_SOURCE",
                    "weight": 1,
                }
            ],
            "health_metrics": {
                "health_score": 100,
                "total_executions": 10,
                "completed_executions": 10,
                "failed_executions": 0,
                "running_executions": 0,
                "success_rate": 100.0,
                "recent_success_rate": 100.0,
                "recent_failed_count": 0,
                "average_duration_ms": 100.0,
                "is_active": True,
            },
        }

        serializer = DatasetTopologySerializer(data=dataset_topology_data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
