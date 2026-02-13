"""
Unit tests for Virtualization Models.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.virtualization.models import (
    QueryExecution,
    QueryExecutionMode,
    QueryExecutionStatus,
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VirtualDatasetModelTest(TestCase):
    """Test VirtualDataset model"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

    def test_create_virtual_dataset_minimal(self):
        """Test creating a virtual dataset with minimal required fields"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT * FROM source1",
            query_type=QueryType.SQL,
        )

        self.assertIsNotNone(dataset.id)
        self.assertEqual(dataset.tenant, self.tenant)
        self.assertEqual(dataset.created_by, self.user)
        self.assertEqual(dataset.name, "Test Virtual Dataset")
        self.assertEqual(dataset.query, "SELECT * FROM source1")
        self.assertEqual(dataset.query_type, QueryType.SQL)
        self.assertEqual(dataset.version, "1.0.0")
        self.assertEqual(dataset.status, VirtualDatasetStatus.DRAFT)
        self.assertEqual(dataset.schema, {})
        self.assertEqual(dataset.sources, [])
        self.assertIsNotNone(dataset.created_at)
        self.assertIsNotNone(dataset.updated_at)

    def test_create_virtual_dataset_defaults_tdd(self):
        """TDD: minimal create sets default version, status, schema, sources."""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Defaults TDD",
            query="SELECT 1",
            query_type=QueryType.SQL,
        )
        self.assertEqual(dataset.version, "1.0.0")
        self.assertEqual(dataset.status, VirtualDatasetStatus.DRAFT)
        self.assertEqual(dataset.schema, {})
        self.assertEqual(dataset.sources, [])

    def test_create_virtual_dataset_full(self):
        """Test creating a virtual dataset with all fields"""
        schema = {
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
                {"name": "value", "type": "number"},
            ]
        }
        sources = [
            {
                "name": "source1",
                "type": "postgresql",
                "connection": {"host": "localhost", "port": 5432},
            },
            {
                "name": "source2",
                "type": "mysql",
                "connection": {"host": "localhost", "port": 3306},
            },
        ]

        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Full Virtual Dataset",
            description="A complete virtual dataset example",
            query="SELECT id, name, value FROM source1 UNION SELECT id, name, value FROM source2",
            query_type=QueryType.FEDERATED,
            schema=schema,
            sources=sources,
            version="2.1.0",
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.assertEqual(dataset.name, "Full Virtual Dataset")
        self.assertEqual(dataset.description, "A complete virtual dataset example")
        self.assertEqual(dataset.query_type, QueryType.FEDERATED)
        self.assertEqual(dataset.schema, schema)
        self.assertEqual(dataset.sources, sources)
        self.assertEqual(dataset.version, "2.1.0")
        self.assertEqual(dataset.status, VirtualDatasetStatus.ACTIVE)

    def test_virtual_dataset_str_representation(self):
        """Test string representation of virtual dataset"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            version="1.2.3",
            status=VirtualDatasetStatus.ACTIVE,
        )

        expected_str = "Test Dataset v1.2.3 (ACTIVE)"
        self.assertEqual(str(dataset), expected_str)

    def test_virtual_dataset_unique_constraint(self):
        """Test that name+version is unique per tenant"""
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Unique Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            version="1.0.0",
        )

        # Same tenant, same name, same version should fail
        # Django validation happens before database constraint, so we catch ValidationError
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                VirtualDataset.objects.create(
                    tenant=self.tenant,
                    created_by=self.user,
                    name="Unique Dataset",
                    query="SELECT * FROM source2",
                    query_type=QueryType.SQL,
                    version="1.0.0",
                )

        # Different tenant, same name, same version should succeed
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        dataset2 = VirtualDataset.objects.create(
            tenant=other_tenant,
            created_by=self.user,
            name="Unique Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            version="1.0.0",
        )
        self.assertIsNotNone(dataset2.id)

        # Same tenant, same name, different version should succeed
        dataset3 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Unique Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            version="2.0.0",
        )
        self.assertIsNotNone(dataset3.id)

    def test_virtual_dataset_validation_empty_name(self):
        """Test that empty name raises ValidationError"""
        dataset = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        with self.assertRaises(ValidationError) as cm:
            dataset.full_clean()

        self.assertIn("name", cm.exception.error_dict)
        # Django validation message
        error_message = str(cm.exception.error_dict["name"][0])
        self.assertTrue(
            "cannot be empty" in error_message or "cannot be blank" in error_message,
            f"Expected 'cannot be empty' or 'cannot be blank' in error message: {error_message}",
        )

    def test_virtual_dataset_validation_empty_query(self):
        """Test that empty query raises ValidationError"""
        dataset = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="",
            query_type=QueryType.SQL,
        )

        with self.assertRaises(ValidationError) as cm:
            dataset.full_clean()

        self.assertIn("query", cm.exception.error_dict)
        # Django validation message
        error_message = str(cm.exception.error_dict["query"][0])
        self.assertTrue(
            "cannot be empty" in error_message or "cannot be blank" in error_message,
            f"Expected 'cannot be empty' or 'cannot be blank' in error message: {error_message}",
        )

    def test_virtual_dataset_validation_invalid_schema(self):
        """Test that invalid schema (not a dict) raises ValidationError"""
        dataset = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            schema="not a dict",  # Should be dict
        )

        with self.assertRaises(ValidationError) as cm:
            dataset.full_clean()

        self.assertIn("schema", cm.exception.error_dict)
        self.assertIn("JSON object", str(cm.exception.error_dict["schema"][0]))

    def test_virtual_dataset_validation_invalid_sources(self):
        """Test that invalid sources (not a list) raises ValidationError"""
        dataset = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources="not a list",  # Should be list
        )

        with self.assertRaises(ValidationError) as cm:
            dataset.full_clean()

        self.assertIn("sources", cm.exception.error_dict)
        self.assertIn("JSON array", str(cm.exception.error_dict["sources"][0]))

    def test_virtual_dataset_validation_invalid_version_format(self):
        """Test that invalid version format raises ValidationError"""
        # Test with non-semantic version
        dataset = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            version="invalid",
        )

        with self.assertRaises(ValidationError) as cm:
            dataset.full_clean()

        self.assertIn("version", cm.exception.error_dict)

        # Test with wrong number of parts
        dataset2 = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset 2",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            version="1.0",  # Missing patch version
        )

        with self.assertRaises(ValidationError) as cm:
            dataset2.full_clean()

        self.assertIn("version", cm.exception.error_dict)

    def test_virtual_dataset_validation_sql_query(self):
        """Test SQL query validation"""
        # Valid SQL query
        dataset = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="SQL Dataset",
            query="SELECT id, name FROM users WHERE status = 'active'",
            query_type=QueryType.SQL,
        )
        dataset.full_clean()  # Should not raise

        # Invalid SQL query (no SQL keywords)
        dataset2 = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="Invalid SQL Dataset",
            query="just some text",
            query_type=QueryType.SQL,
        )

        with self.assertRaises(ValidationError) as cm:
            dataset2.full_clean()

        self.assertIn("query", cm.exception.error_dict)

    def test_virtual_dataset_validation_sparql_query(self):
        """Test SPARQL query validation"""
        # Valid SPARQL query
        dataset = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="SPARQL Dataset",
            query="PREFIX ex: <http://example.org/> SELECT ?s ?p ?o WHERE { ?s ?p ?o }",
            query_type=QueryType.SPARQL,
        )
        dataset.full_clean()  # Should not raise

        # Invalid SPARQL query (no SPARQL keywords)
        dataset2 = VirtualDataset(
            tenant=self.tenant,
            created_by=self.user,
            name="Invalid SPARQL Dataset",
            query="just some text",
            query_type=QueryType.SPARQL,
        )

        with self.assertRaises(ValidationError) as cm:
            dataset2.full_clean()

        self.assertIn("query", cm.exception.error_dict)

    def test_virtual_dataset_get_schema_fields(self):
        """Test get_schema_fields method"""
        # Schema with fields array
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 1",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            schema={
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"},
                ]
            },
        )
        fields = dataset1.get_schema_fields()
        self.assertEqual(len(fields), 2)
        self.assertEqual(fields[0]["name"], "id")

        # Schema as dict with field names as keys
        dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 2",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            schema={
                "id": {"type": "string"},
                "name": {"type": "string"},
            },
        )
        fields = dataset2.get_schema_fields()
        self.assertEqual(len(fields), 2)
        self.assertIn("id", fields)
        self.assertIn("name", fields)

        # Empty or None schema
        dataset3 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 3",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            schema=None,
        )
        fields = dataset3.get_schema_fields()
        self.assertEqual(fields, [])

    def test_virtual_dataset_get_source_count(self):
        """Test get_source_count method"""
        # Dataset with sources
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 1",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=[
                {"name": "source1", "type": "postgresql"},
                {"name": "source2", "type": "mysql"},
                {"name": "source3", "type": "mongodb"},
            ],
        )
        self.assertEqual(dataset1.get_source_count(), 3)

        # Dataset without sources
        dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 2",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=None,
        )
        self.assertEqual(dataset2.get_source_count(), 0)

        # Dataset with empty sources
        dataset3 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 3",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=[],
        )
        self.assertEqual(dataset3.get_source_count(), 0)

    def test_virtual_dataset_is_active(self):
        """Test is_active method"""
        # Active dataset
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Active Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        self.assertTrue(dataset1.is_active())

        # Inactive dataset
        dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Inactive Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.INACTIVE,
        )
        self.assertFalse(dataset2.is_active())

        # Draft dataset
        dataset3 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Draft Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
        )
        self.assertFalse(dataset3.is_active())

    def test_virtual_dataset_created_by_nullable(self):
        """Test that created_by can be null"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=None,
            name="System Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        self.assertIsNone(dataset.created_by)
        self.assertIsNotNone(dataset.id)

    def test_virtual_dataset_cascade_delete_tenant(self):
        """Test that virtual datasets are deleted when tenant is deleted"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )
        dataset_id = dataset.id

        # Delete user first (since User.tenant might be restricted)
        self.user.delete()

        # Delete tenant
        self.tenant.delete()

        # Dataset should be deleted
        self.assertFalse(VirtualDataset.objects.filter(id=dataset_id).exists())

    def test_virtual_dataset_set_null_created_by(self):
        """Test that created_by is set to null when user is deleted"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )
        dataset_id = dataset.id

        # Delete user
        self.user.delete()

        # Dataset should still exist but created_by should be null
        dataset.refresh_from_db()
        self.assertIsNone(dataset.created_by)
        self.assertEqual(dataset.id, dataset_id)

    def test_virtual_dataset_indexes(self):
        """Test that indexes are created correctly"""
        from django.db import connection

        with connection.cursor() as cursor:
            # Check indexes exist
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'virtual_datasets'
                ORDER BY indexname
            """
            )
            indexes = [row[0] for row in cursor.fetchall()]

            # Django auto-generates index names, so we check for patterns
            # Check for tenant index (can be virtual_dat_tenant__03bd99_idx or virtual_datasets_tenant_id_*)
            tenant_indexes = [
                idx for idx in indexes if "tenant" in idx.lower() and "idx" in idx.lower()
            ]
            self.assertGreater(
                len(tenant_indexes), 0, f"Should have tenant index, found: {indexes}"
            )

            # Check for created_by index
            created_by_indexes = [
                idx for idx in indexes if "created_by" in idx.lower() or "created" in idx.lower()
            ]
            self.assertGreater(
                len(created_by_indexes), 0, f"Should have created_by index, found: {indexes}"
            )

            # Check for query_type index
            query_type_indexes = [
                idx for idx in indexes if "query_type" in idx.lower() or "query_t" in idx.lower()
            ]
            self.assertGreater(
                len(query_type_indexes), 0, f"Should have query_type index, found: {indexes}"
            )

            # Check for status index
            status_indexes = [idx for idx in indexes if "status" in idx.lower()]
            self.assertGreater(
                len(status_indexes), 0, f"Should have status index, found: {indexes}"
            )

            # Check for created_at index
            created_at_indexes = [
                idx
                for idx in indexes
                if "created_at" in idx.lower()
                or ("created" in idx.lower() and "945d8c" in idx.lower())
            ]
            self.assertGreater(
                len(created_at_indexes), 0, f"Should have created_at index, found: {indexes}"
            )

    def test_virtual_dataset_all_query_types(self):
        """Test that all query types can be used"""
        # Map query types to appropriate query strings
        query_templates = {
            QueryType.SQL: "SELECT * FROM source",
            QueryType.SPARQL: "PREFIX ex: <http://example.org/> SELECT ?s ?p ?o WHERE { ?s ?p ?o }",
            QueryType.FEDERATED: "SELECT * FROM source1 UNION SELECT * FROM source2",
            QueryType.GRAPHQL: "{ query { id name } }",
            QueryType.REST: "GET /api/v1/data",
        }

        for query_type in QueryType.choices:
            query_type_value = query_type[0]
            query_string = query_templates.get(query_type_value, f"Query for {query_type_value}")
            dataset = VirtualDataset.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                name=f"Dataset {query_type_value}",
                query=query_string,
                query_type=query_type_value,
            )
            self.assertEqual(dataset.query_type, query_type_value)

    def test_virtual_dataset_all_statuses(self):
        """Test that all statuses can be used"""
        for status in VirtualDatasetStatus.choices:
            status_value = status[0]
            dataset = VirtualDataset.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                name=f"Dataset {status_value}",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                status=status_value,
            )
            self.assertEqual(dataset.status, status_value)

    def test_virtual_dataset_ordering(self):
        """Test that default ordering is by created_at descending"""
        # Create datasets with different timestamps
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="First Dataset",
            query="SELECT * FROM source1",
            query_type=QueryType.SQL,
        )

        import time

        time.sleep(0.1)  # Small delay to ensure different timestamps

        dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Second Dataset",
            query="SELECT * FROM source2",
            query_type=QueryType.SQL,
        )

        # Query should return newest first
        datasets = list(VirtualDataset.objects.all())
        self.assertEqual(datasets[0].name, "Second Dataset")
        self.assertEqual(datasets[1].name, "First Dataset")


class QueryExecutionModelTest(TestCase):
    """Test QueryExecution model"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

    def test_create_query_execution_minimal(self):
        """Test creating a query execution with minimal required fields"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source WHERE id = :id",
        )

        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.virtual_dataset, self.virtual_dataset)
        self.assertEqual(execution.query, "SELECT * FROM source WHERE id = :id")
        self.assertEqual(execution.execution_mode, QueryExecutionMode.MANUAL)
        self.assertEqual(execution.status, QueryExecutionStatus.PENDING)
        self.assertEqual(execution.parameters, {})
        self.assertEqual(execution.execution_log, [])
        self.assertEqual(execution.metrics, {})
        self.assertIsNone(execution.started_at)
        self.assertIsNone(execution.completed_at)
        self.assertIsNone(execution.result_cache_key)
        self.assertIsNone(execution.result_storage_path)
        self.assertIsNotNone(execution.created_at)
        self.assertIsNotNone(execution.updated_at)

    def test_create_query_execution_full(self):
        """Test creating a query execution with all fields"""
        parameters = {"id": 123, "name": "test"}
        execution_log = [
            {"timestamp": "2025-01-01T00:00:00Z", "level": "INFO", "message": "Starting execution"}
        ]
        metrics = {"duration_ms": 1500, "rows_processed": 1000, "memory_used_mb": 256}

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source WHERE id = :id AND name = :name",
            parameters=parameters,
            execution_mode=QueryExecutionMode.ASYNC,
            status=QueryExecutionStatus.COMPLETED,
            result_cache_key="cache:key:123",
            result_storage_path="/storage/results/execution_123.json",
            execution_log=execution_log,
            metrics=metrics,
        )

        self.assertEqual(execution.parameters, parameters)
        self.assertEqual(execution.execution_mode, QueryExecutionMode.ASYNC)
        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        self.assertEqual(execution.result_cache_key, "cache:key:123")
        self.assertEqual(execution.result_storage_path, "/storage/results/execution_123.json")
        self.assertEqual(execution.execution_log, execution_log)
        self.assertEqual(execution.metrics, metrics)

    def test_query_execution_str_representation(self):
        """Test string representation of query execution"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.PENDING,
        )

        expected_str = f"QueryExecution {execution.id} - {self.virtual_dataset.name} (PENDING)"
        self.assertEqual(str(execution), expected_str)

    def test_query_execution_cascade_delete_virtual_dataset(self):
        """Test that query executions are deleted when virtual dataset is deleted"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
        )
        execution_id = execution.id

        # Delete virtual dataset
        self.virtual_dataset.delete()

        # Execution should be deleted
        self.assertFalse(QueryExecution.objects.filter(id=execution_id).exists())

    def test_query_execution_validation_empty_query(self):
        """Test that empty query raises ValidationError"""
        execution = QueryExecution(
            virtual_dataset=self.virtual_dataset,
            query="",
        )

        with self.assertRaises(ValidationError) as cm:
            execution.full_clean()

        self.assertIn("query", cm.exception.error_dict)

    def test_query_execution_validation_invalid_parameters(self):
        """Test that invalid parameters (not a dict) raises ValidationError"""
        execution = QueryExecution(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            parameters="not a dict",  # Should be dict
        )

        with self.assertRaises(ValidationError) as cm:
            execution.full_clean()

        self.assertIn("parameters", cm.exception.error_dict)
        self.assertIn("JSON object", str(cm.exception.error_dict["parameters"][0]))

    def test_query_execution_validation_invalid_execution_log(self):
        """Test that invalid execution_log (not a list) raises ValidationError"""
        execution = QueryExecution(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            execution_log="not a list",  # Should be list
        )

        with self.assertRaises(ValidationError) as cm:
            execution.full_clean()

        self.assertIn("execution_log", cm.exception.error_dict)
        self.assertIn("JSON array", str(cm.exception.error_dict["execution_log"][0]))

    def test_query_execution_validation_invalid_metrics(self):
        """Test that invalid metrics (not a dict) raises ValidationError"""
        execution = QueryExecution(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            metrics="not a dict",  # Should be dict
        )

        with self.assertRaises(ValidationError) as cm:
            execution.full_clean()

        self.assertIn("metrics", cm.exception.error_dict)
        self.assertIn("JSON object", str(cm.exception.error_dict["metrics"][0]))

    def test_query_execution_validation_completed_before_started(self):
        """Test that completed_at before started_at raises ValidationError"""
        from django.utils import timezone

        now = timezone.now()

        execution = QueryExecution(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            started_at=now,
            completed_at=now - timezone.timedelta(seconds=10),  # Before started_at
        )

        with self.assertRaises(ValidationError) as cm:
            execution.full_clean()

        self.assertIn("completed_at", cm.exception.error_dict)

    def test_query_execution_validation_completed_without_completed_at(self):
        """Test that COMPLETED status without completed_at raises ValidationError when started_at is set"""
        from django.utils import timezone

        now = timezone.now()

        execution = QueryExecution(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.COMPLETED,
            started_at=now,
            completed_at=None,
        )

        with self.assertRaises(ValidationError) as cm:
            execution.full_clean()

        self.assertIn("completed_at", cm.exception.error_dict)

    def test_query_execution_validation_failed_without_completed_at(self):
        """Test that FAILED status without completed_at raises ValidationError when started_at is set"""
        from django.utils import timezone

        now = timezone.now()

        execution = QueryExecution(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.FAILED,
            started_at=now,
            completed_at=None,
        )

        with self.assertRaises(ValidationError) as cm:
            execution.full_clean()

        self.assertIn("completed_at", cm.exception.error_dict)

    def test_query_execution_validation_running_without_started_at(self):
        """Test that RUNNING status without started_at raises ValidationError when completed_at is set"""
        from django.utils import timezone

        now = timezone.now()

        execution = QueryExecution(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.RUNNING,
            started_at=None,
            completed_at=now,
        )

        with self.assertRaises(ValidationError) as cm:
            execution.full_clean()

        self.assertIn("started_at", cm.exception.error_dict)

    def test_query_execution_get_duration_seconds(self):
        """Test get_duration_seconds method"""
        from django.utils import timezone

        now = timezone.now()

        # Execution with both timestamps
        execution1 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            started_at=now,
            completed_at=now + timezone.timedelta(seconds=5),
        )
        self.assertEqual(execution1.get_duration_seconds(), 5.0)

        # Execution without timestamps
        execution2 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
        )
        self.assertIsNone(execution2.get_duration_seconds())

    def test_query_execution_get_duration_ms(self):
        """Test get_duration_ms method"""
        from django.utils import timezone

        now = timezone.now()

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            started_at=now,
            completed_at=now + timezone.timedelta(milliseconds=1500),
        )
        self.assertEqual(execution.get_duration_ms(), 1500)

    def test_query_execution_add_log_entry(self):
        """Test add_log_entry method"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
        )

        execution.add_log_entry("INFO", "Starting execution", save=True)
        execution.add_log_entry("WARNING", "Slow query detected", save=True)
        execution.refresh_from_db()

        self.assertEqual(len(execution.execution_log), 2)
        self.assertEqual(execution.execution_log[0]["level"], "INFO")
        self.assertEqual(execution.execution_log[0]["message"], "Starting execution")
        self.assertEqual(execution.execution_log[1]["level"], "WARNING")
        self.assertEqual(execution.execution_log[1]["message"], "Slow query detected")

    def test_query_execution_set_get_metric(self):
        """Test set_metric and get_metric methods"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
        )

        execution.set_metric("duration_ms", 1500, save=True)
        execution.set_metric("rows_processed", 1000, save=True)
        execution.refresh_from_db()

        self.assertEqual(execution.get_metric("duration_ms"), 1500)
        self.assertEqual(execution.get_metric("rows_processed"), 1000)
        self.assertEqual(execution.get_metric("nonexistent", "default"), "default")

    def test_query_execution_is_completed(self):
        """Test is_completed method"""
        # Completed execution
        execution1 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.COMPLETED,
        )
        self.assertTrue(execution1.is_completed())

        # Failed execution
        execution2 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.FAILED,
        )
        self.assertTrue(execution2.is_completed())

        # Cancelled execution
        execution3 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.CANCELLED,
        )
        self.assertTrue(execution3.is_completed())

        # Pending execution
        execution4 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.PENDING,
        )
        self.assertFalse(execution4.is_completed())

    def test_query_execution_is_running(self):
        """Test is_running method"""
        # Running execution
        execution1 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.RUNNING,
        )
        self.assertTrue(execution1.is_running())

        # Pending execution
        execution2 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.PENDING,
        )
        self.assertFalse(execution2.is_running())

    def test_query_execution_mark_started(self):
        """Test mark_started method"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.PENDING,
        )

        execution.mark_started()
        execution.refresh_from_db()

        self.assertEqual(execution.status, QueryExecutionStatus.RUNNING)
        self.assertIsNotNone(execution.started_at)

    def test_query_execution_mark_completed(self):
        """Test mark_completed method"""
        from django.utils import timezone

        now = timezone.now()

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.RUNNING,
            started_at=now - timezone.timedelta(seconds=5),
        )

        metrics = {"rows_processed": 1000, "memory_used_mb": 256}
        execution.mark_completed(metrics=metrics)
        execution.refresh_from_db()

        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        self.assertIsNotNone(execution.completed_at)
        self.assertEqual(execution.get_metric("rows_processed"), 1000)
        self.assertEqual(execution.get_metric("memory_used_mb"), 256)
        # Duration should be automatically calculated
        self.assertIsNotNone(execution.get_metric("duration_ms"))

    def test_query_execution_mark_failed(self):
        """Test mark_failed method"""
        from django.utils import timezone

        now = timezone.now()

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.RUNNING,
            started_at=now - timezone.timedelta(seconds=3),
        )

        metrics = {"error_code": "TIMEOUT"}
        execution.mark_failed(error_message="Query execution timed out", metrics=metrics)
        execution.refresh_from_db()

        self.assertEqual(execution.status, QueryExecutionStatus.FAILED)
        self.assertIsNotNone(execution.completed_at)
        self.assertEqual(execution.get_metric("error_code"), "TIMEOUT")
        # Check error message was added to logs
        self.assertGreater(len(execution.execution_log), 0)
        self.assertIn("ERROR", [log["level"] for log in execution.execution_log])
        # Duration should be automatically calculated
        self.assertIsNotNone(execution.get_metric("duration_ms"))

    def test_query_execution_mark_cancelled(self):
        """Test mark_cancelled method"""
        from django.utils import timezone

        now = timezone.now()

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.RUNNING,
            started_at=now,
        )

        execution.mark_cancelled(reason="User requested cancellation")
        execution.refresh_from_db()

        self.assertEqual(execution.status, QueryExecutionStatus.CANCELLED)
        self.assertIsNotNone(execution.completed_at)
        # Check cancellation reason was added to logs
        self.assertGreater(len(execution.execution_log), 0)
        log_messages = [log["message"] for log in execution.execution_log]
        self.assertTrue(any("cancelled" in msg.lower() for msg in log_messages))

    def test_query_execution_all_statuses(self):
        """Test that all statuses can be used"""
        for status in QueryExecutionStatus.choices:
            status_value = status[0]
            execution = QueryExecution.objects.create(
                virtual_dataset=self.virtual_dataset,
                query="SELECT * FROM source",
                status=status_value,
            )
            self.assertEqual(execution.status, status_value)

    def test_query_execution_all_execution_modes(self):
        """Test that all execution modes can be used"""
        for mode in QueryExecutionMode.choices:
            mode_value = mode[0]
            execution = QueryExecution.objects.create(
                virtual_dataset=self.virtual_dataset,
                query="SELECT * FROM source",
                execution_mode=mode_value,
            )
            self.assertEqual(execution.execution_mode, mode_value)

    def test_query_execution_indexes(self):
        """Test that indexes are created correctly"""
        from django.db import connection

        with connection.cursor() as cursor:
            # Check indexes exist
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'query_executions'
                ORDER BY indexname
            """
            )
            indexes = [row[0] for row in cursor.fetchall()]

            # Check for virtual_dataset index
            virtual_dataset_indexes = [idx for idx in indexes if "virtual" in idx.lower()]
            self.assertGreater(
                len(virtual_dataset_indexes),
                0,
                f"Should have virtual_dataset index, found: {indexes}",
            )

            # Check for status index
            status_indexes = [idx for idx in indexes if "status" in idx.lower()]
            self.assertGreater(
                len(status_indexes), 0, f"Should have status index, found: {indexes}"
            )

            # Check for started_at index
            started_at_indexes = [idx for idx in indexes if "started" in idx.lower()]
            self.assertGreater(
                len(started_at_indexes), 0, f"Should have started_at index, found: {indexes}"
            )

    def test_query_execution_ordering(self):
        """Test that default ordering is by started_at descending, then created_at descending"""
        # Create executions with different timestamps
        execution1 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source1",
        )

        import time

        time.sleep(0.1)  # Small delay to ensure different timestamps

        execution2 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source2",
        )

        # Query should return newest first (by created_at since started_at is None)
        executions = list(QueryExecution.objects.all())
        self.assertEqual(executions[0].query, "SELECT * FROM source2")
        self.assertEqual(executions[1].query, "SELECT * FROM source1")

    def test_query_execution_ordering_with_started_at(self):
        """Test ordering when started_at is set"""
        from django.utils import timezone

        now = timezone.now()

        # Create execution with earlier started_at
        execution1 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source1",
            started_at=now - timezone.timedelta(hours=1),
        )

        # Create execution with later started_at
        execution2 = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source2",
            started_at=now,
        )

        # Query should return newest started_at first
        executions = list(QueryExecution.objects.all())
        self.assertEqual(executions[0].query, "SELECT * FROM source2")
        self.assertEqual(executions[1].query, "SELECT * FROM source1")

    def test_query_execution_with_job(self):
        """Test creating a query execution with job reference"""
        from hub.apps.jobs.models import Job, JobStatus, JobType
        from hub.apps.jobs.utils import create_job

        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.VIRTUAL_QUERY_EXECUTION,
            resource_type="QUERY_EXECUTION",
            resource_id=str(uuid.uuid4()),
        )

        # Create execution with job reference
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            job=job,
        )

        self.assertEqual(execution.job, job)
        self.assertEqual(job.query_executions.first(), execution)

    def test_query_execution_sync_status_from_job_pending(self):
        """Test syncing execution status from job when job is PENDING"""
        from hub.apps.jobs.models import Job, JobStatus, JobType
        from hub.apps.jobs.utils import create_job

        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.VIRTUAL_QUERY_EXECUTION,
            resource_type="QUERY_EXECUTION",
            resource_id=str(uuid.uuid4()),
        )

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            job=job,
            status=QueryExecutionStatus.RUNNING,  # Different from job
        )

        # Sync should update execution to PENDING
        updated = execution.sync_status_from_job()
        self.assertTrue(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, QueryExecutionStatus.PENDING)

    def test_query_execution_sync_status_from_job_running(self):
        """Test syncing execution status from job when job is RUNNING"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.VIRTUAL_QUERY_EXECUTION,
            status=JobStatus.RUNNING,
            resource_type="QUERY_EXECUTION",
            resource_id=str(uuid.uuid4()),
        )
        job.mark_started()

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            job=job,
            status=QueryExecutionStatus.PENDING,
        )

        # Sync should update execution to RUNNING
        updated = execution.sync_status_from_job()
        self.assertTrue(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, QueryExecutionStatus.RUNNING)
        self.assertIsNotNone(execution.started_at)

    def test_query_execution_sync_status_from_job_completed(self):
        """Test syncing execution status from job when job is COMPLETED"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.VIRTUAL_QUERY_EXECUTION,
            status=JobStatus.PENDING,
            resource_type="QUERY_EXECUTION",
            resource_id=str(uuid.uuid4()),
        )
        job.mark_started()
        job.mark_completed()

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            job=job,
            status=QueryExecutionStatus.RUNNING,
        )

        # Sync should update execution to COMPLETED
        updated = execution.sync_status_from_job()
        self.assertTrue(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        self.assertIsNotNone(execution.completed_at)

    def test_query_execution_sync_status_from_job_failed(self):
        """Test syncing execution status from job when job is FAILED"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.VIRTUAL_QUERY_EXECUTION,
            status=JobStatus.PENDING,
            resource_type="QUERY_EXECUTION",
            resource_id=str(uuid.uuid4()),
        )
        job.mark_started()
        job.mark_failed("Test error message")

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            job=job,
            status=QueryExecutionStatus.RUNNING,
        )

        # Sync should update execution to FAILED
        updated = execution.sync_status_from_job()
        self.assertTrue(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, QueryExecutionStatus.FAILED)
        self.assertIsNotNone(execution.completed_at)
        # Check that error message was logged
        self.assertTrue(len(execution.execution_log) > 0)
        self.assertIn("Job failed", execution.execution_log[-1]["message"])

    def test_query_execution_sync_status_from_job_cancelled(self):
        """Test syncing execution status from job when job is CANCELLED"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.VIRTUAL_QUERY_EXECUTION,
            status=JobStatus.PENDING,
            resource_type="QUERY_EXECUTION",
            resource_id=str(uuid.uuid4()),
        )
        job.mark_cancelled()

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            job=job,
            status=QueryExecutionStatus.RUNNING,
        )

        # Sync should update execution to CANCELLED
        updated = execution.sync_status_from_job()
        self.assertTrue(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, QueryExecutionStatus.CANCELLED)
        self.assertIsNotNone(execution.completed_at)
        # Check that cancellation was logged
        self.assertTrue(len(execution.execution_log) > 0)
        self.assertIn("cancelled", execution.execution_log[-1]["message"].lower())

    def test_query_execution_sync_status_from_job_no_job(self):
        """Test syncing execution status when no job is linked"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            job=None,
        )

        # Sync should return False when no job
        updated = execution.sync_status_from_job()
        self.assertFalse(updated)

    def test_query_execution_sync_status_from_job_already_synced(self):
        """Test syncing execution status when already in sync"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.VIRTUAL_QUERY_EXECUTION,
            status=JobStatus.COMPLETED,
            resource_type="QUERY_EXECUTION",
            resource_id=str(uuid.uuid4()),
        )
        job.mark_started()
        job.mark_completed()

        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            job=job,
            status=QueryExecutionStatus.COMPLETED,
        )

        # Sync should return False when already in sync
        updated = execution.sync_status_from_job()
        self.assertFalse(updated)

    def test_query_execution_sync_status_from_job_terminal_state_protection(self):
        """Test that terminal execution states are not overwritten by non-terminal job states"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        # Execution is already COMPLETED
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.COMPLETED,
        )

        # Job is PENDING (non-terminal)
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.VIRTUAL_QUERY_EXECUTION,
            status=JobStatus.PENDING,
            resource_type="QUERY_EXECUTION",
            resource_id=str(uuid.uuid4()),
        )
        execution.job = job
        execution.save()

        # Sync should NOT update terminal execution state
        updated = execution.sync_status_from_job()
        self.assertFalse(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
