"""
Migration tests for VirtualDataset model.

Tests forward and backward migrations to ensure data integrity.
"""

import contextlib
import importlib
import uuid

import pytest
from django.db import connection, migrations as django_migrations
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


class VirtualDatasetMigrationTest(TestCase):
    """Test migration for VirtualDataset model"""

    @classmethod
    def tearDownClass(cls):
        from django.db import connection
        from django.db.transaction import TransactionManagementError

        connection.needs_rollback = False
        with contextlib.suppress(TransactionManagementError):
            super().tearDownClass()

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.orchestration.registry import reset_workflow_definition_cache

        reset_workflow_definition_cache()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_migration_forward_creates_table(self):
        """Test that forward migration creates the virtual_datasets table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'virtual_datasets'
                );
            """)
            table_exists = cursor.fetchone()[0]
            self.assertTrue(table_exists, "Table should exist after migration")

    def test_migration_forward_creates_model(self):
        """Test that forward migration allows creating VirtualDataset instances."""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            name="Test Virtual Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

        self.assertIsNotNone(dataset.id)
        self.assertEqual(dataset.tenant, self.tenant)
        self.assertEqual(dataset.name, "Test Virtual Dataset")
        self.assertEqual(dataset.query, "SELECT * FROM source")
        self.assertEqual(dataset.query_type, QueryType.SQL)
        self.assertEqual(dataset.status, VirtualDatasetStatus.DRAFT)
        self.assertEqual(dataset.version, "1.0.0")

    def test_migration_fields_exist(self):
        """Test that all required fields exist in the table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'virtual_datasets'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # Check required fields
            self.assertIn("id", columns)
            self.assertIn("tenant_id", columns)
            self.assertIn("created_by_id", columns)
            self.assertIn("name", columns)
            self.assertIn("description", columns)
            self.assertIn("query", columns)
            self.assertIn("query_type", columns)
            self.assertIn("schema", columns)
            self.assertIn("sources", columns)
            self.assertIn("version", columns)
            self.assertIn("status", columns)
            self.assertIn("created_at", columns)
            self.assertIn("updated_at", columns)

            # Check data types
            self.assertEqual(columns["id"][0], "uuid")
            self.assertEqual(columns["name"][0], "character varying")
            self.assertEqual(columns["query"][0], "text")
            self.assertEqual(columns["query_type"][0], "character varying")
            self.assertEqual(columns["schema"][0], "jsonb")
            self.assertEqual(columns["sources"][0], "jsonb")
            self.assertEqual(columns["version"][0], "character varying")
            self.assertEqual(columns["status"][0], "character varying")

            # Check nullable fields
            self.assertEqual(columns["description"][1], "YES")  # nullable
            self.assertEqual(columns["created_by_id"][1], "YES")  # nullable

    def test_migration_indexes_exist(self):
        """Test that all required indexes exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    i.indexname,
                    array_agg(a.attname ORDER BY array_position(idx.indkey, a.attnum)) as column_names
                FROM pg_indexes i
                JOIN pg_class c ON c.relname = i.indexname
                JOIN pg_index idx ON idx.indexrelid = c.oid
                JOIN pg_class t ON t.oid = idx.indrelid AND t.relname = 'virtual_datasets'
                JOIN pg_attribute a ON a.attrelid = idx.indrelid AND a.attnum = ANY(idx.indkey)
                WHERE i.tablename = 'virtual_datasets'
                AND i.schemaname = 'public'
                GROUP BY i.indexname
                ORDER BY i.indexname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            # Verify structural index coverage — check columns, not
            # auto-generated hash-based index names which change on every
            # schema migration.
            indexed_columns = set()
            composite_indexes = []
            for idx_name, cols in indexes.items():
                for col in cols:
                    indexed_columns.add(col)
                if len(cols) > 1:
                    composite_indexes.append((idx_name, cols))

            # Single-column indexes that must exist
            for required_col in ("tenant_id", "created_by_id", "query_type", "status", "created_at"):
                self.assertIn(
                    required_col, indexed_columns,
                    f"Column '{required_col}' should have at least one index"
                )

            # Composite indexes that must exist
            required_composites = [
                ("tenant_id", "status"),
                ("tenant_id", "query_type"),
                ("tenant_id", "created_at"),
            ]
            composite_col_sets = [frozenset(cols) for _, cols in composite_indexes]
            for req_pair in required_composites:
                req_set = frozenset(req_pair)
                self.assertTrue(
                    any(req_set.issubset(cs) for cs in composite_col_sets),
                    f"Should have a composite index covering {req_pair}; "
                    f"found composites: {[(n, c) for n, c in composite_indexes]}",
                )

    def test_migration_unique_constraint_exists(self):
        """Test that unique constraint exists for (tenant, name, version)."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    conname,
                    pg_get_constraintdef(oid) as constraint_def
                FROM pg_constraint
                WHERE conrelid = 'virtual_datasets'::regclass
                AND contype = 'u';
            """)
            constraints = {row[0]: row[1] for row in cursor.fetchall()}

            # Check for unique constraint
            self.assertIn("unique_virtual_dataset_name_version_per_tenant", constraints)
            constraint_def = constraints["unique_virtual_dataset_name_version_per_tenant"]
            self.assertIn("tenant_id", constraint_def)
            self.assertIn("name", constraint_def)
            self.assertIn("version", constraint_def)

    def test_migration_foreign_key_constraints_exist(self):
        """Test that foreign key constraints exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    conname,
                    pg_get_constraintdef(oid) as constraint_def
                FROM pg_constraint
                WHERE conrelid = 'virtual_datasets'::regclass
                AND contype = 'f';
            """)
            constraints = {row[0]: row[1] for row in cursor.fetchall()}

            # Check for tenant foreign key
            tenant_fk_found = False
            created_by_fk_found = False
            for _conname, constraint_def in constraints.items():
                if "tenant_id" in constraint_def and "tenants" in constraint_def.lower():
                    tenant_fk_found = True
                if "created_by_id" in constraint_def and "users" in constraint_def.lower():
                    created_by_fk_found = True

            self.assertTrue(tenant_fk_found, "Tenant foreign key constraint should exist")
            self.assertTrue(created_by_fk_found, "Created_by foreign key constraint should exist")

    def test_migration_rollback_is_reversible(self):
        """Verify virtualization migrations are reversible via static analysis.

        Instead of executing destructive DDL (``migrate zero`` / ``migrate``)
        against the shared ``--reuse-db`` test database, we import each
        migration module and inspect its operations.  Django auto-generates
        reverse operations for ``CreateModel``, ``AddField``, etc.; we
        confirm none of the operations are marked non-reversible and that
        every operation has a discoverable reverse path.
        """
        migration_modules = [
            "hub.apps.virtualization.migrations.0001_initial",
            "hub.apps.virtualization.migrations.0002_alter_virtualdataset_schema_and_more",
            "hub.apps.virtualization.migrations.0003_add_query_execution",
            "hub.apps.virtualization.migrations.0004_add_job_to_query_execution",
            "hub.apps.virtualization.migrations.0005_add_workflow_instance_to_query_execution",
            "hub.apps.virtualization.migrations.0006_encrypt_sources",
            "hub.apps.virtualization.migrations.0007_enable_rls_virtual_datasets",
            "hub.apps.virtualization.migrations.0008_merge",
        ]

        for mod_name in migration_modules:
            mod = importlib.import_module(mod_name)
            mig = mod.Migration
            self.assertIsNotNone(mig, f"Migration module {mod_name} should define Migration")

            for op in mig.operations:
                self.assertTrue(
                    getattr(op, "reversible", True),
                    f"Operation {op.describe()!r} in {mod_name} should be reversible",
                )

        # Also verify the initial migration creates the virtual_datasets
        # table (source of truth for forward migration correctness).
        m0001 = importlib.import_module(
            "hub.apps.virtualization.migrations.0001_initial"
        )
        create_ops = [
            op for op in m0001.Migration.operations
            if isinstance(op, django_migrations.CreateModel)
        ]
        self.assertGreater(
            len(create_ops), 0,
            "0001_initial should contain at least one CreateModel operation",
        )

    def test_data_persistence_after_model_creation(self):
        """Test that VirtualDataset records persist and new records can be created.

        Verifies basic CRUD operations after migrations are applied.  For
        migration reversibility verification see
        ``test_migration_rollback_is_reversible`` above which uses static
        analysis (importlib inspection of migration operations) rather than
        destructive DDL.
        """
        # Create test data
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            name="Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            schema={"fields": [{"name": "id", "type": "string"}]},
            sources=[{"name": "source1", "type": "postgresql"}],
            version="1.0.0",
            status=VirtualDatasetStatus.ACTIVE,
        )
        dataset_id = dataset.id

        self.assertTrue(VirtualDataset.objects.filter(id=dataset_id).exists())

        # Verify we can still create new datasets after the initial one
        new_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            name="New Dataset After First",
            query="SELECT * FROM source2",
            query_type=QueryType.SQL,
        )
        self.assertIsNotNone(new_dataset.id)
        self.assertEqual(new_dataset.name, "New Dataset After First")
        self.assertEqual(new_dataset.query, "SELECT * FROM source2")


class QueryExecutionMigrationTest(TestCase):
    """Test migration for QueryExecution model"""

    @classmethod
    def tearDownClass(cls):
        from django.db import connection
        from django.db.transaction import TransactionManagementError

        connection.needs_rollback = False
        with contextlib.suppress(TransactionManagementError):
            super().tearDownClass()

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.orchestration.registry import reset_workflow_definition_cache

        reset_workflow_definition_cache()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            name="Test Virtual Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
        )

    def test_migration_forward_creates_table(self):
        """Test that forward migration creates the query_executions table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'query_executions'
                );
            """)
            table_exists = cursor.fetchone()[0]
            self.assertTrue(table_exists, "Table should exist after migration")

    def test_migration_forward_creates_model(self):
        """Test that forward migration allows creating QueryExecution instances."""
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source WHERE id = :id",
        )

        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.virtual_dataset, self.virtual_dataset)
        self.assertEqual(execution.query, "SELECT * FROM source WHERE id = :id")
        self.assertEqual(execution.status, QueryExecutionStatus.PENDING)
        self.assertEqual(execution.execution_mode, QueryExecutionMode.MANUAL)

    def test_migration_fields_exist(self):
        """Test that all required fields exist in the table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'query_executions'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # Check required fields
            self.assertIn("id", columns)
            self.assertIn("virtual_dataset_id", columns)
            self.assertIn("query", columns)
            self.assertIn("parameters", columns)
            self.assertIn("execution_mode", columns)
            self.assertIn("status", columns)
            self.assertIn("started_at", columns)
            self.assertIn("completed_at", columns)
            self.assertIn("result_cache_key", columns)
            self.assertIn("result_storage_path", columns)
            self.assertIn("execution_log", columns)
            self.assertIn("metrics", columns)
            self.assertIn("created_at", columns)
            self.assertIn("updated_at", columns)

            # Check data types
            self.assertEqual(columns["id"][0], "uuid")
            self.assertEqual(columns["query"][0], "text")
            self.assertEqual(columns["parameters"][0], "jsonb")
            self.assertEqual(columns["execution_mode"][0], "character varying")
            self.assertEqual(columns["status"][0], "character varying")
            self.assertEqual(columns["execution_log"][0], "jsonb")
            self.assertEqual(columns["metrics"][0], "jsonb")

            # Check nullable fields
            self.assertEqual(columns["parameters"][1], "YES")  # nullable
            self.assertEqual(columns["started_at"][1], "YES")  # nullable
            self.assertEqual(columns["completed_at"][1], "YES")  # nullable
            self.assertEqual(columns["result_cache_key"][1], "YES")  # nullable
            self.assertEqual(columns["result_storage_path"][1], "YES")  # nullable
            self.assertEqual(columns["execution_log"][1], "YES")  # nullable
            self.assertEqual(columns["metrics"][1], "YES")  # nullable

    def test_migration_indexes_exist(self):
        """Test that all required indexes exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    i.indexname,
                    array_agg(a.attname ORDER BY array_position(idx.indkey, a.attnum)) as column_names
                FROM pg_indexes i
                JOIN pg_class c ON c.relname = i.indexname
                JOIN pg_index idx ON idx.indexrelid = c.oid
                JOIN pg_class t ON t.oid = idx.indrelid AND t.relname = 'query_executions'
                JOIN pg_attribute a ON a.attrelid = idx.indrelid AND a.attnum = ANY(idx.indkey)
                WHERE i.tablename = 'query_executions'
                AND i.schemaname = 'public'
                GROUP BY i.indexname
                ORDER BY i.indexname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            # Check for key indexes
            virtual_dataset_indexes = [idx for idx in indexes if "virtual" in idx.lower()]
            self.assertGreater(
                len(virtual_dataset_indexes),
                0,
                f"Should have virtual_dataset index, found: {list(indexes.keys())}",
            )

            status_indexes = [idx for idx in indexes if "status" in idx.lower()]
            self.assertGreater(
                len(status_indexes), 0, f"Should have status index, found: {list(indexes.keys())}"
            )

            started_at_indexes = [idx for idx in indexes if "started" in idx.lower()]
            self.assertGreater(
                len(started_at_indexes),
                0,
                f"Should have started_at index, found: {list(indexes.keys())}",
            )

            # Verify composite indexes - collect (name, columns) tuples
            composite_indexes = [
                (idx_name, columns)
                for idx_name, columns in indexes.items()
                if len(columns) > 1
            ]
            self.assertGreater(
                len(composite_indexes),
                0,
                f"Should have composite indexes, found: {list(indexes.keys())}",
            )

            # Verify composite index coverage — check column
            # composition rather than auto-generated index names.
            composite_col_sets = [frozenset(cols) for _, cols in composite_indexes]
            required_qe_composites = [
                ("virtual_dataset_id", "status"),
                ("virtual_dataset_id", "started_at"),
            ]
            for req_pair in required_qe_composites:
                req_set = frozenset(req_pair)
                self.assertTrue(
                    any(req_set.issubset(cs) for cs in composite_col_sets),
                    f"Should have a composite index covering {req_pair}",
                )

    def test_migration_foreign_key_constraints_exist(self):
        """Test that foreign key constraints exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    conname,
                    pg_get_constraintdef(oid) as constraint_def
                FROM pg_constraint
                WHERE conrelid = 'query_executions'::regclass
                AND contype = 'f';
            """)
            constraints = {row[0]: row[1] for row in cursor.fetchall()}

            # Check for virtual_dataset foreign key
            virtual_dataset_fk_found = False
            for _conname, constraint_def in constraints.items():
                if (
                    "virtual_dataset_id" in constraint_def
                    and "virtual_datasets" in constraint_def.lower()
                ):
                    virtual_dataset_fk_found = True

            self.assertTrue(
                virtual_dataset_fk_found, "Virtual dataset foreign key constraint should exist"
            )

    def test_migration_rollback_is_reversible(self):
        """Verify query_executions migrations are reversible via static analysis.

        Imports each migration module that defines the query_executions table
        (0003_add_query_execution onward) and confirms every operation is
        marked reversible.  This avoids destructive DDL against the shared
        ``--reuse-db`` database.
        """
        qe_migration_modules = [
            "hub.apps.virtualization.migrations.0003_add_query_execution",
            "hub.apps.virtualization.migrations.0004_add_job_to_query_execution",
            "hub.apps.virtualization.migrations.0005_add_workflow_instance_to_query_execution",
        ]

        for mod_name in qe_migration_modules:
            mod = importlib.import_module(mod_name)
            mig = mod.Migration
            self.assertIsNotNone(mig, f"Migration module {mod_name} should define Migration")

            for op in mig.operations:
                self.assertTrue(
                    getattr(op, "reversible", True),
                    f"Operation {op.describe()!r} in {mod_name} should be reversible",
                )

        # Confirm 0003_add_query_execution creates the query_executions table
        m0003 = importlib.import_module(
            "hub.apps.virtualization.migrations.0003_add_query_execution"
        )
        create_ops = [
            op for op in m0003.Migration.operations
            if isinstance(op, django_migrations.CreateModel)
        ]
        self.assertGreater(
            len(create_ops), 0,
            "0003_add_query_execution should contain at least one CreateModel",
        )

    def test_data_persistence_after_model_creation(self):
        """Test that QueryExecution records persist and new records can be created.

        Verifies basic CRUD operations after migrations are applied.  For
        migration reversibility verification see
        ``test_migration_rollback_is_reversible`` above which uses static
        analysis (importlib inspection of migration operations) rather than
        destructive DDL.
        """
        # Create test data
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source WHERE id = :id",
            parameters={"id": 123},
            execution_mode=QueryExecutionMode.ASYNC,
            status=QueryExecutionStatus.COMPLETED,
            execution_log=[
                {"timestamp": "2025-01-01T00:00:00Z", "level": "INFO", "message": "Test"}
            ],
            metrics={"duration_ms": 1500, "rows_processed": 1000},
        )
        execution_id = execution.id

        # Verify data exists
        self.assertTrue(QueryExecution.objects.filter(id=execution_id).exists())

        # Verify we can still create new executions after the initial one
        new_execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM source2",
        )
        self.assertIsNotNone(new_execution.id)
        self.assertEqual(new_execution.query, "SELECT * FROM source2")
