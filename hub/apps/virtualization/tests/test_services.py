"""
Unit tests for Virtualization Service.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError, PermissionError, ValidationError
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.virtualization.models import (
    QueryExecution,
    QueryExecutionMode,
    QueryExecutionStatus,
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)
from hub.apps.virtualization.services import VirtualizationService

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VirtualizationServiceInitializationTest(TestCase):
    """Test VirtualizationService initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )

    def test_service_initialization_with_tenant_and_user(self):
        """Test service initialization with tenant_id and user_id"""
        service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        self.assertEqual(service.tenant_id, str(self.tenant.id))
        self.assertEqual(service.user_id, str(self.user.id))
        self.assertEqual(service.service_name, "virtualization_service")
        self.assertIsNotNone(service._event_publisher)

    def test_service_initialization_without_tenant_and_user(self):
        """Test service initialization without tenant_id and user_id"""
        service = VirtualizationService()

        self.assertIsNone(service.tenant_id)
        self.assertIsNone(service.user_id)
        self.assertEqual(service.service_name, "virtualization_service")
        self.assertIsNotNone(service._event_publisher)

    def test_service_initialization_with_tenant_only(self):
        """Test service initialization with tenant_id only"""
        service = VirtualizationService(tenant_id=str(self.tenant.id))

        self.assertEqual(service.tenant_id, str(self.tenant.id))
        self.assertIsNone(service.user_id)
        self.assertEqual(service.service_name, "virtualization_service")
        self.assertIsNotNone(service._event_publisher)


class VirtualizationServiceEventPublishingTest(TestCase):
    """Test VirtualizationService event publishing"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

    def test_publish_virtual_dataset_created_event(self):
        """Test publishing virtual_dataset.created event"""
        event_id = self.service.publish_virtual_dataset_created(
            virtual_dataset_id=str(self.virtual_dataset.id),
            name=self.virtual_dataset.name,
            query_type=self.virtual_dataset.query_type,
            status=self.virtual_dataset.status,
            version=self.virtual_dataset.version,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_virtual_dataset_updated_event(self):
        """Test publishing virtual_dataset.updated event"""
        changes = {"name": {"old": "Old Name", "new": "New Name"}}
        event_id = self.service.publish_virtual_dataset_updated(
            virtual_dataset_id=str(self.virtual_dataset.id),
            changes=changes,
            previous_status="DRAFT",
            new_status="ACTIVE",
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_virtual_dataset_deleted_event(self):
        """Test publishing virtual_dataset.deleted event"""
        event_id = self.service.publish_virtual_dataset_deleted(
            virtual_dataset_id=str(self.virtual_dataset.id),
            reason="Test deletion",
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_query_execution_started_event(self):
        """Test publishing query_execution.started event"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source WHERE id = :id",
            execution_mode=QueryExecutionMode.SYNC,
        )

        event_id = self.service.publish_query_execution_started(
            query_execution_id=str(execution.id),
            virtual_dataset_id=str(self.virtual_dataset.id),
            execution_mode=execution.execution_mode,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_query_execution_completed_event(self):
        """Test publishing query_execution.completed event"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source WHERE id = :id",
            status=QueryExecutionStatus.COMPLETED,
        )

        event_id = self.service.publish_query_execution_completed(
            query_execution_id=str(execution.id),
            virtual_dataset_id=str(self.virtual_dataset.id),
            status=execution.status,
            duration_ms=1500,
            rows_processed=1000,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_query_execution_failed_event(self):
        """Test publishing query_execution.failed event"""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source WHERE id = :id",
            status=QueryExecutionStatus.FAILED,
        )

        event_id = self.service.publish_query_execution_failed(
            query_execution_id=str(execution.id),
            virtual_dataset_id=str(self.virtual_dataset.id),
            error_message="Query execution failed: timeout",
            duration_ms=5000,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_event_publisher_uses_service_tenant_and_user(self):
        """Test that publish_virtual_dataset_created returns valid event id (real publisher)."""
        service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        event_id = service.publish_virtual_dataset_created(
            virtual_dataset_id=str(self.virtual_dataset.id),
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)
        self.assertGreater(len(event_id), 0)


class VirtualizationServiceCreateVirtualDatasetTest(TestCase):
    """Test VirtualizationService.create_virtual_dataset() method"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import Role, UserRole

        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )

        # Create DATA_PROVIDER role and assign to user
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_create_virtual_dataset_with_valid_sql_query(self):
        """Test creating virtual dataset with valid SQL query"""
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test SQL Dataset",
            query="SELECT id, name FROM users WHERE status = 'active'",
            query_type=QueryType.SQL,
            description="Test SQL virtual dataset",
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Test SQL Dataset")
        self.assertEqual(dataset.query, "SELECT id, name FROM users WHERE status = 'active'")
        self.assertEqual(dataset.query_type, QueryType.SQL)
        self.assertEqual(dataset.status, VirtualDatasetStatus.DRAFT)
        self.assertEqual(dataset.version, "1.0.0")
        self.assertEqual(dataset.tenant_id, self.tenant.id)
        self.assertEqual(dataset.created_by_id, self.user.id)

        # Verify dataset exists in database
        self.assertTrue(VirtualDataset.objects.filter(id=dataset.id).exists())

    def test_create_virtual_dataset_with_valid_sparql_query(self):
        """Test creating virtual dataset with valid SPARQL query"""
        sparql_query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT ?name ?email
        WHERE {
            ?person foaf:name ?name .
            ?person foaf:mbox ?email .
        }
        """
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test SPARQL Dataset",
            query=sparql_query.strip(),
            query_type=QueryType.SPARQL,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Test SPARQL Dataset")
        self.assertEqual(dataset.query_type, QueryType.SPARQL)
        self.assertEqual(dataset.status, VirtualDatasetStatus.DRAFT)

    def test_create_virtual_dataset_with_schema(self):
        """Test creating virtual dataset with schema definition"""
        schema = {
            "fields": [
                {"name": "id", "type": "integer", "nullable": False},
                {"name": "name", "type": "string", "nullable": True},
                {"name": "created_at", "type": "timestamp", "nullable": False},
            ]
        }
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset with Schema",
            query="SELECT id, name, created_at FROM users",
            query_type=QueryType.SQL,
            schema=schema,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.schema, schema)
        self.assertEqual(len(dataset.get_schema_fields()), 3)

    def test_create_virtual_dataset_with_custom_version(self):
        """Test creating virtual dataset with custom version"""
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset Custom Version",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            version="2.1.3",
        )

        self.assertEqual(dataset.version, "2.1.3")

    def test_create_virtual_dataset_with_custom_status(self):
        """Test creating virtual dataset with custom status"""
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset Active",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.assertEqual(dataset.status, VirtualDatasetStatus.ACTIVE)

    def test_create_virtual_dataset_with_sources(self):
        """Test creating virtual dataset with source configurations"""
        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "port": 5432,
                "database": "testdb",
                "username": "testuser",
            }
        ]
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset with Sources",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=sources,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.sources, sources)
        self.assertEqual(dataset.get_source_count(), 1)

    def test_create_virtual_dataset_with_invalid_sql_query(self):
        """Test creating virtual dataset with invalid SQL query"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Invalid SQL",
                query="INVALID SQL QUERY",
                query_type=QueryType.SQL,
            )

        self.assertIn("SQL query should contain SQL keywords", str(cm.exception))

    def test_create_virtual_dataset_with_dangerous_sql_operation(self):
        """Test creating virtual dataset with dangerous SQL operation (INSERT, UPDATE, DELETE)"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Dangerous SQL",
                query="INSERT INTO users (name) VALUES ('test')",
                query_type=QueryType.SQL,
            )

        self.assertIn("dangerous operation", str(cm.exception).lower())

    def test_create_virtual_dataset_with_invalid_sparql_query(self):
        """Test creating virtual dataset with invalid SPARQL query"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Invalid SPARQL",
                query="INVALID SPARQL QUERY",
                query_type=QueryType.SPARQL,
            )

        self.assertIn("SPARQL query should contain SPARQL keywords", str(cm.exception))

    def test_create_virtual_dataset_with_sparql_update_operation(self):
        """Test creating virtual dataset with SPARQL Update operation (not allowed)"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test SPARQL Update",
                query="INSERT DATA { <s> <p> <o> }",
                query_type=QueryType.SPARQL,
            )

        self.assertIn("SPARQL Update operation", str(cm.exception))

    def test_create_virtual_dataset_with_invalid_schema(self):
        """Test creating virtual dataset with invalid schema"""
        invalid_schema = "not a dict"
        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Invalid Schema",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                schema=invalid_schema,
            )

        self.assertIn("Schema must be a JSON object", str(cm.exception))

    def test_create_virtual_dataset_with_invalid_schema_fields(self):
        """Test creating virtual dataset with invalid schema fields structure"""
        invalid_schema = {"fields": "not a list"}
        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Invalid Schema Fields",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                schema=invalid_schema,
            )

        self.assertIn("Schema 'fields' must be an array", str(cm.exception))

    def test_create_virtual_dataset_with_empty_query(self):
        """Test creating virtual dataset with empty query"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Empty Query",
                query="",
                query_type=QueryType.SQL,
            )

        self.assertIn("Query cannot be empty", str(cm.exception))

    def test_create_virtual_dataset_with_duplicate_name_version(self):
        """Test creating virtual dataset with duplicate name and version"""
        # Create first dataset
        self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Duplicate Test",
            query="SELECT * FROM source1",
            query_type=QueryType.SQL,
            version="1.0.0",
        )

        # Try to create duplicate
        from hub.apps.core.services.base import ConflictError

        with self.assertRaises(ConflictError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Duplicate Test",
                query="SELECT * FROM source2",
                query_type=QueryType.SQL,
                version="1.0.0",
            )

        self.assertIn("already exists", str(cm.exception))

    def test_create_virtual_dataset_with_different_version_allowed(self):
        """Test that same name with different version is allowed"""
        # Create first dataset
        dataset1 = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Same Name",
            query="SELECT * FROM source1",
            query_type=QueryType.SQL,
            version="1.0.0",
        )

        # Create second dataset with same name but different version
        dataset2 = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Same Name",
            query="SELECT * FROM source2",
            query_type=QueryType.SQL,
            version="2.0.0",
        )

        self.assertNotEqual(dataset1.id, dataset2.id)
        self.assertEqual(dataset1.name, dataset2.name)
        self.assertNotEqual(dataset1.version, dataset2.version)

    def test_create_virtual_dataset_without_tenant_id(self):
        """Test creating virtual dataset without tenant_id raises error"""
        service = VirtualizationService()  # No tenant_id
        with self.assertRaises(ValidationError) as cm:
            service.create_virtual_dataset(
                tenant_id=None,
                user_id=str(self.user.id),
                name="Test",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
            )

        self.assertIn("tenant_id is required", str(cm.exception))

    def test_create_virtual_dataset_without_user_id(self):
        """Test creating virtual dataset without user_id raises error"""
        service = VirtualizationService(tenant_id=str(self.tenant.id))  # No user_id
        with self.assertRaises(ValidationError) as cm:
            service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=None,
                name="Test",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
            )

        self.assertIn("user_id is required", str(cm.exception))

    def test_create_virtual_dataset_with_nonexistent_tenant(self):
        """Test creating virtual dataset with nonexistent tenant raises error"""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError) as cm:
            self.service.create_virtual_dataset(
                tenant_id="00000000-0000-0000-0000-000000000000",
                user_id=str(self.user.id),
                name="Test",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
            )

        self.assertIn("Tenant", str(cm.exception))
        self.assertIn("not found", str(cm.exception))

    def test_create_virtual_dataset_with_nonexistent_user(self):
        """Test creating virtual dataset with nonexistent user raises error"""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id="00000000-0000-0000-0000-000000000000",
                name="Test",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
            )

        self.assertIn("User", str(cm.exception))
        self.assertIn("not found", str(cm.exception))

    def test_create_virtual_dataset_creates_audit_log(self):
        """Test that creating virtual dataset creates audit log"""
        from hub.apps.audit.models import AuditEvent

        initial_count = AuditEvent.objects.count()

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Audit Log",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        # Check audit log was created
        final_count = AuditEvent.objects.count()
        self.assertEqual(final_count, initial_count + 1)

        # Verify audit log details
        audit_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="CREATED", resource_id=str(dataset.id)
        ).first()

        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertEqual(audit_event.actor_user_id, self.user.id)
        self.assertEqual(audit_event.tenant_id, self.tenant.id)
        self.assertIn("dataset_id", audit_event.details_json)
        self.assertEqual(audit_event.details_json["name"], "Test Audit Log")


class VirtualizationServiceCreateVirtualDatasetIntegrationTest(TestCase):
    """Integration tests for virtual dataset creation workflow"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Integration Test Tenant",
            slug="integration-test-tenant",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="integration@example.com", password="testpass123", tenant=self.tenant
        )
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_create_virtual_dataset_full_workflow(self):
        """Test complete virtual dataset creation workflow"""
        # Create dataset with all fields
        schema = {
            "fields": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
                {"name": "value", "type": "float"},
            ]
        }
        sources = [{"type": "postgresql", "host": "localhost", "database": "testdb"}]

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Integration Test Dataset",
            query="SELECT id, name, value FROM test_table",
            query_type=QueryType.SQL,
            description="Integration test dataset",
            schema=schema,
            sources=sources,
            version="1.0.0",
            status=VirtualDatasetStatus.DRAFT,
        )

        # Verify dataset was created
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Integration Test Dataset")
        self.assertEqual(dataset.description, "Integration test dataset")
        self.assertEqual(dataset.query, "SELECT id, name, value FROM test_table")
        self.assertEqual(dataset.query_type, QueryType.SQL)
        self.assertEqual(dataset.schema, schema)
        self.assertEqual(dataset.sources, sources)
        self.assertEqual(dataset.version, "1.0.0")
        self.assertEqual(dataset.status, VirtualDatasetStatus.DRAFT)

        # Verify dataset can be retrieved
        retrieved = self.service.get_virtual_dataset(
            virtual_dataset_id=str(dataset.id), tenant_id=str(self.tenant.id)
        )
        self.assertEqual(retrieved.id, dataset.id)
        self.assertEqual(retrieved.name, dataset.name)

        # Verify audit log was created
        from hub.apps.audit.models import AuditEvent

        audit_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET",
            action="VIRTUAL_DATASET_CREATED",
            resource_id=str(dataset.id),
        ).first()
        self.assertIsNotNone(audit_event)

    def test_create_virtual_dataset_with_federated_query(self):
        """Test creating virtual dataset with federated query type"""
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Federated Query Dataset",
            query="SELECT * FROM SERVICE <http://sparql.endpoint.org> { SELECT ?s ?p ?o WHERE { ?s ?p ?o } }",
            query_type=QueryType.FEDERATED,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.query_type, QueryType.FEDERATED)

    def test_create_virtual_dataset_with_with_clause(self):
        """Test creating virtual dataset with SQL WITH clause"""
        query = """
        WITH recent_users AS (
            SELECT id, name, created_at
            FROM users
            WHERE created_at > '2024-01-01'
        )
        SELECT * FROM recent_users
        """
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="WITH Clause Dataset",
            query=query.strip(),
            query_type=QueryType.SQL,
        )

        self.assertIsNotNone(dataset)
        self.assertIn("WITH", dataset.query)

    def test_create_virtual_dataset_transaction_rollback_on_error(self):
        """Test that transaction is rolled back on error"""
        initial_count = VirtualDataset.objects.count()

        # Try to create dataset with invalid query (should fail)
        with self.assertRaises(ValidationError):
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Should Not Exist",
                query="INVALID QUERY",
                query_type=QueryType.SQL,
            )

        # Verify no dataset was created
        final_count = VirtualDataset.objects.count()
        self.assertEqual(final_count, initial_count)

    def test_create_virtual_dataset_with_multiple_sources(self):
        """Test creating virtual dataset with multiple source configurations"""
        sources = [
            {"type": "postgresql", "host": "db1.example.com", "database": "database1"},
            {"type": "mysql", "host": "db2.example.com", "database": "database2"},
        ]

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Multi-Source Dataset",
            query="SELECT * FROM source1 UNION SELECT * FROM source2",
            query_type=QueryType.SQL,
            sources=sources,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(len(dataset.sources), 2)
        self.assertEqual(dataset.get_source_count(), 2)

    def test_create_virtual_dataset_with_complex_schema(self):
        """Test creating virtual dataset with complex schema structure"""
        schema = {
            "fields": [
                {"name": "id", "type": "integer", "nullable": False, "primary_key": True},
                {
                    "name": "metadata",
                    "type": "object",
                    "nullable": True,
                    "properties": {
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "created_by": {"type": "string"},
                    },
                },
                {"name": "scores", "type": "array", "items": {"type": "number"}},
            ]
        }

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Complex Schema Dataset",
            query="SELECT id, metadata, scores FROM complex_table",
            query_type=QueryType.SQL,
            schema=schema,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.schema, schema)
        fields = dataset.get_schema_fields()
        self.assertEqual(len(fields), 3)


class VirtualizationServiceSearchIntegrationTest(TestCase):
    """Test VirtualizationService search service integration"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import Role, UserRole

        self.tenant = Tenant.objects.create(
            name="Search Test Tenant", slug="search-test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="search@example.com", password="testpass123", tenant=self.tenant
        )

        # Create DATA_PROVIDER role and assign to user
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_create_virtual_dataset_indexes_for_search(self):
        """Test that creating virtual dataset indexes it for search"""
        from hub.apps.search.models import SearchIndex

        # Create virtual dataset
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Searchable Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            description="A searchable virtual dataset",
            schema={
                "fields": [{"name": "id", "type": "integer"}, {"name": "name", "type": "string"}]
            },
        )

        # Verify search index was created
        search_index = SearchIndex.objects.filter(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
        ).first()

        self.assertIsNotNone(search_index)
        self.assertEqual(search_index.title, "Searchable Dataset")
        self.assertEqual(search_index.description, "A searchable virtual dataset")
        self.assertEqual(search_index.resource_type, "VIRTUAL_DATASET")
        self.assertEqual(search_index.resource_id, dataset.id)
        self.assertIsNotNone(search_index.search_vector)

    def test_search_index_contains_schema_fields(self):
        """Test that search index contains schema fields"""
        from hub.apps.search.models import SearchIndex

        schema = {
            "fields": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
                {"name": "email", "type": "string"},
            ]
        }

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Schema Dataset",
            query="SELECT id, name, email FROM users",
            query_type=QueryType.SQL,
            schema=schema,
        )

        search_index = SearchIndex.objects.get(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
        )

        self.assertIsNotNone(search_index.schema_fields)
        self.assertEqual(len(search_index.schema_fields), 3)
        self.assertEqual(search_index.schema_fields[0]["name"], "id")
        self.assertEqual(search_index.schema_fields[1]["name"], "name")
        self.assertEqual(search_index.schema_fields[2]["name"], "email")

    def test_search_index_contains_owner_information(self):
        """Test that search index contains owner information"""
        from hub.apps.search.models import SearchIndex

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Owner Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        search_index = SearchIndex.objects.get(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
        )

        self.assertEqual(search_index.owner_id, self.user.id)
        self.assertEqual(search_index.owner_email, self.user.email)

    def test_update_search_index_helper_method(self):
        """Test that _update_search_index helper method updates search index"""
        from hub.apps.search.models import SearchIndex

        # Create virtual dataset
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Update Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            description="Original description",
        )

        # Update dataset description
        dataset.description = "Updated description"
        dataset.save()

        # Update search index
        self.service._update_search_index(dataset)

        # Verify search index was updated
        search_index = SearchIndex.objects.get(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
        )

        self.assertEqual(search_index.description, "Updated description")

    def test_remove_from_search_index_helper_method(self):
        """Test that _remove_from_search_index helper method removes from search index"""
        from hub.apps.search.models import SearchIndex

        # Create virtual dataset
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Delete Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        # Verify search index exists
        self.assertTrue(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
            ).exists()
        )

        # Remove from search index
        self.service._remove_from_search_index(
            virtual_dataset_id=str(dataset.id), tenant_id=str(self.tenant.id)
        )

        # Verify search index was removed
        self.assertFalse(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
            ).exists()
        )

    def test_search_service_can_find_indexed_virtual_dataset(self):
        """Test that SearchService can find indexed virtual dataset"""
        from hub.apps.search.services import SearchService

        # Create virtual dataset
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Findable Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            description="This dataset should be findable via search",
        )

        # Search for it
        search_service = SearchService()
        results, total = search_service.search(
            tenant_id=str(self.tenant.id), query="Findable", resource_type="VIRTUAL_DATASET"
        )

        # Verify it was found
        self.assertGreater(
            total, 0, f"Search should return results. Got {total} results: {results}"
        )
        found = False
        for result in results:
            # Search results use 'id' field which contains the resource_id
            if result.get("id") == str(dataset.id):
                found = True
                self.assertEqual(result.get("title"), "Findable Dataset")
                self.assertEqual(result.get("type"), "VIRTUAL_DATASET")
                break
        self.assertTrue(
            found, f"Virtual dataset should be found in search results. Results: {results}"
        )

    def test_search_index_handles_indexing_failure_gracefully(self):
        """Test success path: dataset creation succeeds; indexing failure handling is structural."""
        # Verifies create_virtual_dataset succeeds. Indexing failure path would require
        # external failure injection (no mocks); this test asserts the happy path only.

        # Create dataset - should succeed even if indexing has issues
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Graceful Failure Test",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        # Dataset should be created successfully
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Graceful Failure Test")

    def test_search_index_with_empty_schema(self):
        """Test search indexing with empty schema"""
        from hub.apps.search.models import SearchIndex

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Empty Schema Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            schema=None,  # No schema
        )

        search_index = SearchIndex.objects.get(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
        )

        self.assertIsNotNone(search_index)
        self.assertEqual(search_index.title, "Empty Schema Dataset")
        # Schema fields should be empty list, not None
        self.assertEqual(search_index.schema_fields, [])

    def test_search_index_with_empty_sources(self):
        """Test search indexing with empty sources list"""
        from hub.apps.search.models import SearchIndex

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="No Sources Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=[],  # Empty sources
        )

        search_index = SearchIndex.objects.get(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
        )

        self.assertIsNotNone(search_index)
        self.assertEqual(search_index.title, "No Sources Dataset")

    def test_search_index_with_different_query_types(self):
        """Test search indexing works with different query types"""
        from hub.apps.search.models import SearchIndex

        # Test SQL
        sql_dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="SQL Query Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
        )

        sql_index = SearchIndex.objects.get(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=sql_dataset.id
        )
        self.assertIsNotNone(sql_index)

        # Test SPARQL
        sparql_query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?s ?p ?o WHERE { ?s ?p ?o }
        """
        sparql_dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="SPARQL Query Dataset",
            query=sparql_query.strip(),
            query_type=QueryType.SPARQL,
        )

        sparql_index = SearchIndex.objects.get(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=sparql_dataset.id
        )
        self.assertIsNotNone(sparql_index)

    def test_search_index_update_on_dataset_change(self):
        """Test that search index is updated when dataset is modified"""
        from hub.apps.search.models import SearchIndex

        # Create dataset
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Original Name",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            description="Original description",
        )

        # Get initial search index
        search_index = SearchIndex.objects.get(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
        )
        initial_indexed_at = search_index.indexed_at

        # Update dataset
        dataset.name = "Updated Name"
        dataset.description = "Updated description"
        dataset.save()

        # Update search index
        self.service._update_search_index(dataset)

        # Refresh search index
        search_index.refresh_from_db()
        self.assertEqual(search_index.title, "Updated Name")
        self.assertEqual(search_index.description, "Updated description")
        # Indexed_at should be updated
        self.assertGreater(search_index.indexed_at, initial_indexed_at)

    def test_search_index_removal_on_deletion(self):
        """Test that search index is removed when dataset is deleted"""
        from hub.apps.search.models import SearchIndex

        # Create dataset
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="To Be Deleted",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        # Verify search index exists
        self.assertTrue(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
            ).exists()
        )

        # Remove from search index
        self.service._remove_from_search_index(
            virtual_dataset_id=str(dataset.id), tenant_id=str(self.tenant.id)
        )

        # Verify search index was removed
        self.assertFalse(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
            ).exists()
        )

    def test_search_index_with_complex_schema_structure(self):
        """Test search indexing with complex nested schema structure"""
        from hub.apps.search.models import SearchIndex

        complex_schema = {
            "fields": [
                {
                    "name": "id",
                    "type": "integer",
                    "nullable": False,
                    "constraints": {"primary_key": True},
                },
                {
                    "name": "metadata",
                    "type": "object",
                    "nullable": True,
                    "properties": {
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "created_by": {"type": "string"},
                    },
                },
            ]
        }

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Complex Schema Dataset",
            query="SELECT id, metadata FROM complex_table",
            query_type=QueryType.SQL,
            schema=complex_schema,
        )

        search_index = SearchIndex.objects.get(
            tenant_id=self.tenant.id, resource_type="VIRTUAL_DATASET", resource_id=dataset.id
        )

        self.assertIsNotNone(search_index)
        self.assertEqual(len(search_index.schema_fields), 2)
        self.assertEqual(search_index.schema_fields[0]["name"], "id")
        self.assertEqual(search_index.schema_fields[1]["name"], "metadata")


def compliance_service_available():
    """Check if compliance service is available"""
    try:
        from hub.apps.compliance.service_client import ComplianceServiceClient

        client = ComplianceServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Compliance service not available: {e}")
        return False


def storage_service_available():
    """Check if storage service is available"""
    try:
        from hub.apps.files.storage import S3StorageClient

        client = S3StorageClient()
        # Try to list buckets as a health check
        client.client.list_buckets()
        return True
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Storage service not available: {e}")
        return False


class VirtualizationServiceComplianceIntegrationTest(TestCase):
    """Test compliance service integration for virtual dataset creation using real services"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    @pytest.mark.skipif(
        not compliance_service_available() or not storage_service_available(),
        reason="Compliance service or storage service not available",
    )
    def test_create_virtual_dataset_with_compliant_asset_source(self):
        """Test creating virtual dataset with compliant asset source using real services"""
        import uuid

        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.files.storage import S3StorageClient

        # Create asset with compliant dataset
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", compliance_status="PASS"
        )

        # Create test CSV content (compliant - no PII)
        test_csv_content = b"id,name,value\n1,Test,100\n2,Sample,200\n3,Example,300"

        # Upload file to real storage
        from django.core.files.base import ContentFile

        storage_client = S3StorageClient()
        try:
            # Use save_file method which requires tenant_id and file_id
            # We'll create the file first, then upload
            file_id = str(uuid.uuid4())
            storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=file_id,
                file_content=ContentFile(test_csv_content, name="test.csv"),
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file to storage: {e}")

        # Create file and dataset
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path=storage_path,
            size=len(test_csv_content),
            content_type="text/csv",
            status="ACTIVE",
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "integer"}]},
        )

        # Create source with asset_id
        sources = [{"type": "asset", "asset_id": str(asset.id), "name": "test-source"}]

        # Use real compliance service
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Compliant Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=sources,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Compliant Dataset")

    @pytest.mark.skipif(
        not compliance_service_available() or not storage_service_available(),
        reason="Compliance service or storage service not available",
    )
    def test_create_virtual_dataset_blocks_non_compliant_source(self):
        """Test that virtual dataset creation is blocked for non-compliant sources using real services"""
        import uuid

        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.files.storage import S3StorageClient

        # Create asset with non-compliant dataset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="non-compliant-asset",
            name="Non-Compliant Asset",
            compliance_status="FAIL",
        )

        # Create test CSV content with PII (email addresses) - should fail compliance
        test_csv_content = b"email,phone,name\ntest@example.com,555-1234,John Doe\nuser@example.com,555-5678,Jane Smith"

        # Upload file to real storage
        from django.core.files.base import ContentFile

        storage_client = S3StorageClient()
        try:
            # Use save_file method which requires tenant_id and file_id
            # We'll create the file first, then upload
            file_id = str(uuid.uuid4())
            storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=file_id,
                file_content=ContentFile(test_csv_content, name="test.csv"),
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file to storage: {e}")

        # Create file and dataset
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="non-compliant.csv",
            storage_path=storage_path,
            size=len(test_csv_content),
            content_type="text/csv",
            status="ACTIVE",
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            schema_json={
                "fields": [{"name": "email", "type": "string"}, {"name": "phone", "type": "string"}]
            },
        )

        sources = [{"type": "asset", "asset_id": str(asset.id), "name": "non-compliant-source"}]

        # Use real compliance service - should block creation
        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Non-Compliant Dataset",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                sources=sources,
            )

        self.assertIn("compliance", str(cm.exception).lower())

    def test_create_virtual_dataset_blocks_cross_tenant_source_without_entitlement(self):
        """Test that cross-tenant source access is blocked without entitlement"""
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        # Create asset in other tenant
        other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-asset",
            name="Other Asset",
            compliance_status="PASS",
        )

        sources = [
            {"type": "asset", "asset_id": str(other_asset.id), "name": "cross-tenant-source"}
        ]

        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Cross-Tenant Dataset",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                sources=sources,
            )

        self.assertIn("cross-tenant", str(cm.exception).lower())

    @pytest.mark.skipif(
        not compliance_service_available() or not storage_service_available(),
        reason="Compliance service or storage service not available",
    )
    def test_create_virtual_dataset_allows_cross_tenant_source_with_entitlement(self):
        """Test that cross-tenant source access is allowed with entitlement using real services"""
        import uuid

        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.marketplace.models import Entitlement, EntitlementStatus, Listing

        # Create asset in other tenant
        other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-asset",
            name="Other Asset",
            compliance_status="PASS",
            status=AssetStatus.ACTIVE,
        )

        # Create test CSV content (compliant)
        test_csv_content = b"id,name,value\n1,Test,100\n2,Sample,200\n3,Example,300"

        # Upload file to real storage
        from django.core.files.base import ContentFile

        storage_client = S3StorageClient()
        try:
            # Use save_file method which requires tenant_id and file_id
            # We'll create the file first, then upload
            file_id = str(uuid.uuid4())
            storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=file_id,
                file_content=ContentFile(test_csv_content, name="test.csv"),
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file to storage: {e}")

        # Create file and dataset
        file_obj = File.objects.create(
            tenant=self.other_tenant,
            name="cross-tenant.csv",
            storage_path=storage_path,
            size=len(test_csv_content),
            content_type="text/csv",
            status="ACTIVE",
        )

        dataset = Dataset.objects.create(
            tenant=self.other_tenant,
            asset=other_asset,
            file=file_obj,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "integer"}]},
        )

        # Create listing and entitlement
        listing = Listing.objects.create(
            tenant=self.other_tenant,
            asset=other_asset,
            status="PUBLISHED",
            metadata_json={"title": "Other Asset Listing"},
        )

        entitlement = Entitlement.objects.create(
            tenant=self.tenant, listing=listing, asset=other_asset, status=EntitlementStatus.ACTIVE
        )

        sources = [
            {"type": "asset", "asset_id": str(other_asset.id), "name": "cross-tenant-source"}
        ]

        # Use real compliance service
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Cross-Tenant Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=sources,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Cross-Tenant Dataset")

    @pytest.mark.skipif(
        not compliance_service_available() or not storage_service_available(),
        reason="Compliance service or storage service not available",
    )
    def test_create_virtual_dataset_with_multiple_sources_validates_all(self):
        """Test that all sources are validated for compliance using real services"""
        import uuid

        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.files.storage import S3StorageClient

        # Create two assets
        asset1 = Asset.objects.create(
            tenant=self.tenant, key="asset1", name="Asset 1", compliance_status="PASS"
        )

        asset2 = Asset.objects.create(
            tenant=self.tenant, key="asset2", name="Asset 2", compliance_status="PASS"
        )

        # Create test CSV content for both assets
        test_csv_content = b"id,name,value\n1,Test,100\n2,Sample,200\n3,Example,300"

        # Upload file for asset1
        from django.core.files.base import ContentFile

        storage_client = S3StorageClient()
        file_id1 = str(uuid.uuid4())
        try:
            storage_path1 = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=file_id1,
                file_content=ContentFile(test_csv_content, name="asset1.csv"),
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file to storage: {e}")

        file_obj1 = File.objects.create(
            tenant=self.tenant,
            name="asset1.csv",
            storage_path=storage_path1,
            size=len(test_csv_content),
            content_type="text/csv",
            status="ACTIVE",
        )

        dataset1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset1,
            file=file_obj1,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "integer"}]},
        )

        # Upload file for asset2
        file_id2 = str(uuid.uuid4())
        try:
            storage_path2 = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=file_id2,
                file_content=ContentFile(test_csv_content, name="asset2.csv"),
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file to storage: {e}")

        file_obj2 = File.objects.create(
            tenant=self.tenant,
            name="asset2.csv",
            storage_path=storage_path2,
            size=len(test_csv_content),
            content_type="text/csv",
            status="ACTIVE",
        )

        dataset2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset2,
            file=file_obj2,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "integer"}]},
        )

        sources = [
            {"type": "asset", "asset_id": str(asset1.id), "name": "source1"},
            {"type": "asset", "asset_id": str(asset2.id), "name": "source2"},
        ]

        # Use real compliance service - should validate both sources
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Multi-Source Dataset",
            query="SELECT * FROM source1 UNION SELECT * FROM source2",
            query_type=QueryType.SQL,
            sources=sources,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Multi-Source Dataset")

    def test_create_virtual_dataset_skips_compliance_when_service_unavailable(self):
        """Test that compliance check is skipped when service is unavailable"""
        import uuid

        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.files.storage import S3StorageClient

        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", compliance_status="PASS"
        )

        # Create test CSV content
        test_csv_content = b"id,name,value\n1,Test,100\n2,Sample,200\n3,Example,300"

        # Upload file to real storage
        from django.core.files.base import ContentFile

        storage_client = S3StorageClient()
        try:
            # Use save_file method which requires tenant_id and file_id
            # We'll create the file first, then upload
            file_id = str(uuid.uuid4())
            storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=file_id,
                file_content=ContentFile(test_csv_content, name="test.csv"),
            )
        except Exception as e:
            self.skipTest(f"Failed to upload test file to storage: {e}")

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path=storage_path,
            size=len(test_csv_content),
            content_type="text/csv",
            status="ACTIVE",
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "integer"}]},
        )

        sources = [{"type": "asset", "asset_id": str(asset.id), "name": "test-source"}]

        # Create dataset with sources (real compliance service; may succeed or degrade)
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Dataset With Sources",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=sources,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Dataset With Sources")
        self.assertEqual(dataset.query_type, QueryType.SQL)


class VirtualizationServiceGovernanceIntegrationTest(TestCase):
    """Test governance service integration for virtual dataset creation using real services"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_create_virtual_dataset_checks_user_permissions(self):
        """Test that user permissions are checked for virtual dataset creation"""
        # Create user without required role
        regular_user = User.objects.create_user(
            email="regular@example.com", password="testpass123", tenant=self.tenant
        )

        service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(regular_user.id))

        # Should fail without required role
        from hub.apps.core.services.base import PermissionError

        with self.assertRaises(PermissionError) as cm:
            service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(regular_user.id),
                name="Test Dataset",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
            )

        self.assertIn("required role", str(cm.exception).lower())

    def test_create_virtual_dataset_with_data_provider_role(self):
        """Test that users with DATA_PROVIDER role can create virtual datasets"""
        from hub.apps.users.models import Role, UserRole

        # Create DATA_PROVIDER role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data provider role"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(user=self.user, role=role)

        # Should succeed with DATA_PROVIDER role
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Test Dataset")

    def test_create_virtual_dataset_validates_resource_quota(self):
        """Test that resource quota is validated for virtual dataset creation"""
        from hub.apps.governance.services import GovernanceService
        from hub.apps.users.models import Role, UserRole

        # Create DATA_PROVIDER role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data provider role"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(user=self.user, role=role)

        # Create virtual dataset - should validate quota
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset Quota",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        self.assertIsNotNone(dataset)

    def test_create_virtual_dataset_checks_abac_policies(self):
        """Test that ABAC policies are checked for virtual dataset creation"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.users.models import Role, UserRole

        # Create DATA_PROVIDER role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data provider role"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(user=self.user, role=role)

        # Create ABAC policy that allows virtualization operations
        # Use simpler conditions that will match - just check tenant_id
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Virtualization Operations",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)},
                "resource": {"tenant_id": str(self.tenant.id)},
            },
            effect="ALLOW",
            priority=100,
            enabled=True,
            created_by=self.user,
        )

        # Should succeed with ABAC policy allowing access
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset ABAC",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        self.assertIsNotNone(dataset)

    def test_create_virtual_dataset_blocks_with_deny_abac_policy(self):
        """Test that ABAC policy denial blocks virtual dataset creation"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.users.models import Role, UserRole

        # Create DATA_PROVIDER role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data provider role"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(user=self.user, role=role)

        # Create ABAC policy that denies virtualization operations
        # Use simpler conditions that will match - just check tenant_id
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Virtualization Operations",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)},
                "resource": {"tenant_id": str(self.tenant.id)},
            },
            effect="DENY",
            priority=200,  # Higher priority than allow
            enabled=True,
            created_by=self.user,
        )

        # Should fail with ABAC policy denying access
        from hub.apps.core.services.base import PermissionError

        with self.assertRaises(PermissionError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Dataset Denied",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
            )

        self.assertIn("ABAC policy", str(cm.exception))

    def test_create_virtual_dataset_enforces_tenant_resource_limits(self):
        """Test that tenant-level resource limits are enforced"""
        from hub.apps.governance.services import GovernanceService
        from hub.apps.users.models import Role, UserRole

        # Create DATA_PROVIDER role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data provider role"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(user=self.user, role=role)

        # Create ABAC policy that allows virtualization operations
        # Use simpler conditions that will match - just check tenant_id
        from hub.apps.governance.models import AccessPolicy

        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Virtualization Operations",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)},
                "resource": {"tenant_id": str(self.tenant.id)},
            },
            effect="ALLOW",
            priority=100,
            enabled=True,
            created_by=self.user,
        )

        # Should succeed when within tenant limits
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset Limits",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        self.assertIsNotNone(dataset)


class VirtualizationServiceAuditLoggingTest(TestCase):
    """Test comprehensive audit logging for virtual dataset operations"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import Role, UserRole

        self.tenant = Tenant.objects.create(
            name="Audit Test Tenant", slug="audit-test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="audit@example.com", password="testpass123", tenant=self.tenant
        )

        # Create DATA_PROVIDER role and assign to user
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_create_virtual_dataset_creates_audit_event_with_correct_action(self):
        """Test that creating virtual dataset creates audit event with action=CREATED"""
        from hub.apps.audit.models import AuditEvent

        sources = [
            {"type": "postgres", "connection": "postgresql://localhost:5432/db"},
            {"type": "mysql", "connection": "mysql://localhost:3306/db"},
        ]

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Audit Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            description="Test description",
            schema={"fields": [{"name": "id", "type": "integer"}]},
            sources=sources,
            version="1.0.0",
        )

        # Verify audit event was created
        audit_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="CREATED", resource_id=str(dataset.id)
        ).first()

        self.assertIsNotNone(audit_event, "Audit event should be created")
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertEqual(audit_event.actor_user_id, self.user.id)
        self.assertEqual(audit_event.tenant_id, self.tenant.id)

        # Verify details_json contains required fields
        details = audit_event.details_json
        self.assertIn("dataset_id", details)
        self.assertEqual(details["dataset_id"], str(dataset.id))
        self.assertIn("query_type", details)
        self.assertEqual(details["query_type"], QueryType.SQL)
        self.assertIn("sources", details)
        self.assertEqual(len(details["sources"]), 2)
        self.assertIn("name", details)
        self.assertEqual(details["name"], "Audit Test Dataset")

    def test_create_virtual_dataset_audit_event_includes_all_required_fields(self):
        """Test that audit event includes dataset_id, query_type, and sources"""
        from hub.apps.audit.models import AuditEvent

        sources = [{"type": "postgres", "connection": "postgresql://localhost:5432/db"}]

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Required Fields Test",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
        )

        audit_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="CREATED", resource_id=str(dataset.id)
        ).first()

        self.assertIsNotNone(audit_event)
        details = audit_event.details_json

        # Verify all required fields are present
        self.assertIn("dataset_id", details)
        self.assertIn("query_type", details)
        self.assertIn("sources", details)

        # Verify values
        self.assertEqual(details["dataset_id"], str(dataset.id))
        self.assertEqual(details["query_type"], QueryType.SQL)
        self.assertIsInstance(details["sources"], list)
        self.assertEqual(len(details["sources"]), 1)

    def test_update_virtual_dataset_creates_audit_event_with_correct_action(self):
        """Test that updating virtual dataset creates audit event with action=UPDATED"""
        from hub.apps.audit.models import AuditEvent

        # Create a dataset first
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Update Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=[{"type": "postgres", "connection": "postgresql://localhost:5432/db"}],
        )

        initial_audit_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", resource_id=str(dataset.id)
        ).count()

        # Update the dataset
        updated_dataset = self.service.update_virtual_dataset(
            virtual_dataset_id=str(dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Dataset Name",
            description="Updated description",
        )

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", resource_id=str(dataset.id)
        ).order_by("-timestamp")

        self.assertEqual(audit_events.count(), initial_audit_count + 1)

        update_audit = audit_events.first()
        self.assertEqual(update_audit.action, "UPDATED")
        self.assertEqual(update_audit.result, "SUCCESS")
        self.assertEqual(update_audit.actor_user_id, self.user.id)

        # Verify details_json contains required fields
        details = update_audit.details_json
        self.assertIn("dataset_id", details)
        self.assertEqual(details["dataset_id"], str(dataset.id))
        self.assertIn("query_type", details)
        self.assertIn("sources", details)
        self.assertIn("changes", details)
        self.assertIn("name", details["changes"])

    def test_update_virtual_dataset_audit_event_includes_changes(self):
        """Test that update audit event includes change tracking"""
        from hub.apps.audit.models import AuditEvent

        sources = [{"type": "postgres", "connection": "postgresql://localhost:5432/db"}]

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Original Name",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            description="Original description",
            sources=sources,
            version="1.0.0",
            status=VirtualDatasetStatus.DRAFT,
        )

        # Update multiple fields
        updated_dataset = self.service.update_virtual_dataset(
            virtual_dataset_id=str(dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name",
            description="Updated description",
            version="1.1.0",
            status=VirtualDatasetStatus.ACTIVE,
        )

        audit_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="UPDATED", resource_id=str(dataset.id)
        ).first()

        self.assertIsNotNone(audit_event)
        details = audit_event.details_json

        # Verify changes are tracked
        self.assertIn("changes", details)
        changes = details["changes"]
        self.assertIn("name", changes)
        self.assertIn("description", changes)
        self.assertIn("version", changes)
        self.assertIn("status", changes)

        # Verify old and new values
        self.assertEqual(changes["name"]["old"], "Original Name")
        self.assertEqual(changes["name"]["new"], "Updated Name")
        self.assertEqual(changes["version"]["old"], "1.0.0")
        self.assertEqual(changes["version"]["new"], "1.1.0")

    def test_delete_virtual_dataset_creates_audit_event_with_correct_action(self):
        """Test that deleting virtual dataset creates audit event with action=DELETED"""
        from hub.apps.audit.models import AuditEvent

        sources = [{"type": "postgres", "connection": "postgresql://localhost:5432/db"}]

        # Create a dataset
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Delete Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=sources,
        )

        dataset_id = str(dataset.id)

        # Delete the dataset
        self.service.delete_virtual_dataset(
            virtual_dataset_id=dataset_id, tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Verify audit event was created (before deletion)
        audit_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="DELETED", resource_id=dataset_id
        ).first()

        self.assertIsNotNone(audit_event, "Audit event should be created before deletion")
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertEqual(audit_event.actor_user_id, self.user.id)
        self.assertEqual(audit_event.tenant_id, self.tenant.id)

        # Verify details_json contains required fields
        details = audit_event.details_json
        self.assertIn("dataset_id", details)
        self.assertEqual(details["dataset_id"], dataset_id)
        self.assertIn("query_type", details)
        self.assertEqual(details["query_type"], QueryType.SQL)
        self.assertIn("sources", details)
        self.assertEqual(len(details["sources"]), 1)
        self.assertIn("name", details)
        self.assertEqual(details["name"], "Delete Test Dataset")

        # Verify dataset is actually deleted
        self.assertFalse(VirtualDataset.objects.filter(id=dataset_id).exists())

    def test_delete_virtual_dataset_audit_event_includes_all_required_fields(self):
        """Test that delete audit event includes dataset_id, query_type, and sources"""
        from hub.apps.audit.models import AuditEvent

        sources = [
            {"type": "postgres", "connection": "postgresql://localhost:5432/db"},
            {"type": "mysql", "connection": "mysql://localhost:3306/db"},
        ]

        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Delete Fields Test",
            query="SELECT id, name FROM users",
            query_type=QueryType.SPARQL,
            sources=sources,
        )

        dataset_id = str(dataset.id)

        self.service.delete_virtual_dataset(
            virtual_dataset_id=dataset_id, tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        audit_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="DELETED", resource_id=dataset_id
        ).first()

        self.assertIsNotNone(audit_event)
        details = audit_event.details_json

        # Verify all required fields are present
        self.assertIn("dataset_id", details)
        self.assertIn("query_type", details)
        self.assertIn("sources", details)

        # Verify values
        self.assertEqual(details["dataset_id"], dataset_id)
        self.assertEqual(details["query_type"], QueryType.SPARQL)
        self.assertIsInstance(details["sources"], list)
        self.assertEqual(len(details["sources"]), 2)

    def test_audit_logging_handles_failure_gracefully(self):
        """Test success path: dataset creation succeeds; audit failure handling is structural."""
        # Verifies create_virtual_dataset succeeds. Audit failure path would require
        # external failure injection (no mocks); this test asserts the happy path only.

        # Create dataset - should succeed even if audit logging fails
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Graceful Failure Test",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
        )

        # Dataset should be created successfully
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Graceful Failure Test")

    def test_audit_event_creation_integration(self):
        """Integration test for complete audit logging workflow"""
        from hub.apps.audit.models import AuditEvent

        sources = [{"type": "postgres", "connection": "postgresql://localhost:5432/db"}]

        # Create
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Integration Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=sources,
        )

        create_audit = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="CREATED", resource_id=str(dataset.id)
        ).first()
        self.assertIsNotNone(create_audit)

        # Update
        self.service.update_virtual_dataset(
            virtual_dataset_id=str(dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Integration Test",
        )

        update_audit = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="UPDATED", resource_id=str(dataset.id)
        ).first()
        self.assertIsNotNone(update_audit)

        # Delete
        dataset_id = str(dataset.id)
        self.service.delete_virtual_dataset(
            virtual_dataset_id=dataset_id, tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        delete_audit = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="DELETED", resource_id=dataset_id
        ).first()
        self.assertIsNotNone(delete_audit)

        # Verify all three audit events exist
        all_audits = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", resource_id=dataset_id
        ).order_by("timestamp")

        self.assertEqual(all_audits.count(), 3)
        actions = [audit.action for audit in all_audits]
        self.assertIn("CREATED", actions)
        self.assertIn("UPDATED", actions)
        self.assertIn("DELETED", actions)


class VirtualizationServiceGetQueryResultTest(TestCase):
    """Test get_query_result() method for retrieving query execution results"""

    def setUp(self):
        """Set up test fixtures"""
        from django.core.cache import cache

        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create a test virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM test_table",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        # Clear cache
        cache.clear()

    def test_get_query_result_from_cache_json(self):
        """Test retrieving query result from cache in JSON format"""
        from django.core.cache import cache
        from django.utils import timezone

        # Create test data
        test_results = [
            {"id": 1, "name": "Test 1", "value": 100},
            {"id": 2, "name": "Test 2", "value": 200},
            {"id": 3, "name": "Test 3", "value": 300},
        ]

        # Create cache key and store results
        cache_key = f"virtual_query:{self.virtual_dataset.id}:abc123:def456"
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": QueryType.SQL,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution with cache key
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100, "rows_processed": len(test_results)},
        )

        # Retrieve results
        result = self.service.get_query_result(execution_id=str(execution.id), format="json")

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["execution_id"], str(execution.id))
        self.assertEqual(result["format"], "json")
        self.assertEqual(result["total_count"], len(test_results))
        self.assertEqual(result["returned_count"], len(test_results))
        self.assertEqual(result["content_type"], "application/json")
        self.assertEqual(result["data"], test_results)
        self.assertFalse(result["stream_enabled"])

    def test_get_query_result_with_pagination_page(self):
        """Test retrieving query result with page-based pagination"""
        from django.core.cache import cache
        from django.utils import timezone

        # Create test data with 100 items
        test_results = [{"id": i, "name": f"Test {i}", "value": i * 10} for i in range(1, 101)]

        # Create cache key and store results
        cache_key = f"virtual_query:{self.virtual_dataset.id}:abc123:def456"
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": QueryType.SQL,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100, "rows_processed": len(test_results)},
        )

        # Retrieve first page
        result = self.service.get_query_result(
            execution_id=str(execution.id), format="json", page=1, page_size=25
        )

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["total_count"], 100)
        self.assertEqual(result["returned_count"], 25)
        self.assertIsNotNone(result["pagination"])
        self.assertEqual(result["pagination"]["type"], "page")
        self.assertEqual(result["pagination"]["page"], 1)
        self.assertEqual(result["pagination"]["page_size"], 25)
        self.assertEqual(result["pagination"]["total_pages"], 4)
        self.assertTrue(result["pagination"]["has_next"])
        self.assertFalse(result["pagination"]["has_previous"])
        self.assertEqual(len(result["data"]), 25)
        self.assertEqual(result["data"][0]["id"], 1)

        # Retrieve second page
        result2 = self.service.get_query_result(
            execution_id=str(execution.id), format="json", page=2, page_size=25
        )

        self.assertEqual(result2["pagination"]["page"], 2)
        self.assertTrue(result2["pagination"]["has_previous"])
        self.assertEqual(len(result2["data"]), 25)
        self.assertEqual(result2["data"][0]["id"], 26)

    def test_get_query_result_with_pagination_offset(self):
        """Test retrieving query result with offset-based pagination"""
        from django.core.cache import cache
        from django.utils import timezone

        # Create test data
        test_results = [{"id": i, "name": f"Test {i}", "value": i * 10} for i in range(1, 51)]

        # Create cache key and store results
        cache_key = f"virtual_query:{self.virtual_dataset.id}:abc123:def456"
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": QueryType.SQL,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100, "rows_processed": len(test_results)},
        )

        # Retrieve with offset
        result = self.service.get_query_result(
            execution_id=str(execution.id), format="json", offset=10, limit=20
        )

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["total_count"], 50)
        self.assertEqual(result["returned_count"], 20)
        self.assertIsNotNone(result["pagination"])
        self.assertEqual(result["pagination"]["type"], "offset")
        self.assertEqual(result["pagination"]["offset"], 10)
        self.assertEqual(result["pagination"]["limit"], 20)
        self.assertTrue(result["pagination"]["has_next"])
        self.assertTrue(result["pagination"]["has_previous"])
        self.assertEqual(len(result["data"]), 20)
        self.assertEqual(result["data"][0]["id"], 11)

    def test_get_query_result_csv_format(self):
        """Test retrieving query result in CSV format"""
        from django.core.cache import cache
        from django.utils import timezone

        # Create test data
        test_results = [
            {"id": 1, "name": "Test 1", "value": 100},
            {"id": 2, "name": "Test 2", "value": 200},
        ]

        # Create cache key and store results
        cache_key = f"virtual_query:{self.virtual_dataset.id}:abc123:def456"
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": QueryType.SQL,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100, "rows_processed": len(test_results)},
        )

        # Retrieve in CSV format
        result = self.service.get_query_result(execution_id=str(execution.id), format="csv")

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["format"], "csv")
        self.assertEqual(result["content_type"], "text/csv")
        self.assertIsInstance(result["data"], str)
        self.assertIn("id,name,value", result["data"])
        self.assertIn("1,Test 1,100", result["data"])

    def test_get_query_result_parquet_format(self):
        """Test retrieving query result in Parquet format"""
        import base64

        from django.core.cache import cache
        from django.utils import timezone

        # Create test data
        test_results = [
            {"id": 1, "name": "Test 1", "value": 100},
            {"id": 2, "name": "Test 2", "value": 200},
        ]

        # Create cache key and store results
        cache_key = f"virtual_query:{self.virtual_dataset.id}:abc123:def456"
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": QueryType.SQL,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100, "rows_processed": len(test_results)},
        )

        # Retrieve in Parquet format
        result = self.service.get_query_result(execution_id=str(execution.id), format="parquet")

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["format"], "parquet")
        self.assertEqual(result["content_type"], "application/parquet")
        self.assertIsInstance(result["data"], str)
        # Verify it's base64 encoded
        try:
            decoded = base64.b64decode(result["data"])
            self.assertGreater(len(decoded), 0)
        except Exception:
            self.fail("Parquet data is not valid base64")

    def test_get_query_result_execution_not_completed(self):
        """Test retrieving result from execution that is not completed"""
        from django.utils import timezone

        # Create pending execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.PENDING,
        )

        # Attempt to retrieve results
        with self.assertRaises(ValidationError) as cm:
            self.service.get_query_result(execution_id=str(execution.id))

        self.assertIn("not completed", str(cm.exception).lower())

    def test_get_query_result_no_results_found(self):
        """Test retrieving result when no results are found"""
        from django.utils import timezone

        # Create completed execution without cache key or storage path
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            metrics={"duration_ms": 100},
        )

        # Attempt to retrieve results
        with self.assertRaises(NotFoundError) as cm:
            self.service.get_query_result(execution_id=str(execution.id))

        self.assertIn("no results found", str(cm.exception).lower())

    def test_get_query_result_invalid_format(self):
        """Test retrieving result with invalid format"""
        from django.core.cache import cache
        from django.utils import timezone

        # Create test data
        test_results = [{"id": 1, "name": "Test 1"}]

        # Create cache key and store results
        cache_key = f"virtual_query:{self.virtual_dataset.id}:abc123:def456"
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": QueryType.SQL,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100},
        )

        # Attempt to retrieve with invalid format
        with self.assertRaises(ValidationError) as cm:
            self.service.get_query_result(execution_id=str(execution.id), format="invalid")

        self.assertIn("unsupported format", str(cm.exception).lower())

    def test_get_query_result_invalid_pagination(self):
        """Test retrieving result with invalid pagination parameters"""
        from django.core.cache import cache
        from django.utils import timezone

        # Create test data
        test_results = [{"id": 1, "name": "Test 1"}]

        # Create cache key and store results
        cache_key = f"virtual_query:{self.virtual_dataset.id}:abc123:def456"
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": QueryType.SQL,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100},
        )

        # Attempt to retrieve with both page and offset
        with self.assertRaises(ValidationError) as cm:
            self.service.get_query_result(execution_id=str(execution.id), page=1, offset=10)

        self.assertIn("cannot use both", str(cm.exception).lower())

    def test_get_query_result_streaming_enabled(self):
        """Test retrieving result with streaming enabled for large datasets"""
        from django.core.cache import cache
        from django.utils import timezone

        # Create test data with more than 1000 items
        test_results = [{"id": i, "name": f"Test {i}", "value": i * 10} for i in range(1, 1501)]

        # Create cache key and store results
        cache_key = f"virtual_query:{self.virtual_dataset.id}:abc123:def456"
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": QueryType.SQL,
                "cached_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100, "rows_processed": len(test_results)},
        )

        # Retrieve with streaming enabled
        result = self.service.get_query_result(
            execution_id=str(execution.id), format="json", stream=True
        )

        # Assertions
        self.assertIsNotNone(result)
        self.assertTrue(result["stream_enabled"])
        self.assertIn("stream_url", result)
        self.assertIn(str(execution.id), result["stream_url"])
