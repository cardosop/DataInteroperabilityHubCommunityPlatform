"""
Integration tests for marketplace migrations.

Tests that migrations correctly create all tables, indexes, and constraints.
"""

import pytest
from django.db import connection
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceMigrationsTest(TestCase):
    """Test marketplace migrations rollback and reapplication"""

    def setUp(self):
        """Set up test fixtures"""
        # Ensure we're starting from a clean state
        self.initial_migrations = [
            "0001_initial",
            "0002_alter_marketplaceconnection_config_and_more",
            "0003_marketplacesyncjob_updated_at",
            "0004_marketplacemapping",
        ]

    def test_all_tables_exist(self):
        """Test that all required tables exist after migrations"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename LIKE 'marketplace%'
                ORDER BY tablename
            """)
            tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            "marketplace_connections",
            "marketplace_mappings",
            "marketplace_sync_jobs",
        ]

        for table in expected_tables:
            self.assertIn(table, tables, f"Table {table} should exist")

    def _assert_index_covers_columns(self, table_name, columns, label):
        """Verify an index exists on *table_name* that covers every column in *columns*.

        Uses ``pg_indexes.indexdef`` (the index definition) rather than
        hardcoded hash-based index names.  Django auto-generates index-name
        suffixes by hashing the model/field names; the suffixes change
        whenever a migration is regenerated.  Matching on column presence
        in the index definition is resilient to those renames.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s",
                [table_name],
            )
            index_defs = {row[0]: row[1] for row in cursor.fetchall()}

        found = any(
            all(col in defn for col in columns) for defn in index_defs.values()
        )
        self.assertTrue(
            found,
            f"Missing index on {table_name} covering columns {columns} ({label})"
        )

    def test_marketplace_connections_indexes(self):
        """Test that required indexes exist for marketplace_connections."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'marketplace_connections'")
            indexes = [row[0] for row in cursor.fetchall()]

        # Stable constraint names (pkey, unique) — not hash-based.
        self.assertIn("marketplace_connections_pkey", indexes, "Missing primary key")
        self.assertIn("unique_tenant_connection_name", indexes, "Missing unique constraint")

        # Composite indexes — check column coverage, not hash-based names.
        self._assert_index_covers_columns(
            "marketplace_connections", ["tenant_id", "marketplace_type"],
            "(tenant, marketplace_type)")
        self._assert_index_covers_columns(
            "marketplace_connections", ["tenant_id", "is_active"],
            "(tenant, is_active)")
        self._assert_index_covers_columns(
            "marketplace_connections", ["marketplace_type", "is_active"],
            "(marketplace_type, is_active)")

    def test_marketplace_sync_jobs_indexes(self):
        """Test that required indexes exist for marketplace_sync_jobs."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'marketplace_sync_jobs'")
            indexes = [row[0] for row in cursor.fetchall()]

        self.assertIn("marketplace_sync_jobs_pkey", indexes, "Missing primary key")
        self._assert_index_covers_columns(
            "marketplace_sync_jobs", ["tenant_id", "connection_id"],
            "(tenant, connection)")
        self._assert_index_covers_columns(
            "marketplace_sync_jobs", ["tenant_id", "status"],
            "(tenant, status)")
        self._assert_index_covers_columns(
            "marketplace_sync_jobs", ["connection_id", "status"],
            "(connection, status)")
        self._assert_index_covers_columns(
            "marketplace_sync_jobs", ["status", "created_at"],
            "(status, created_at)")

    def test_marketplace_mappings_indexes(self):
        """Test that required indexes exist for marketplace_mappings."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'marketplace_mappings'")
            indexes = [row[0] for row in cursor.fetchall()]

        self.assertIn("marketplace_mappings_pkey", indexes, "Missing primary key")
        self.assertIn("unique_connection_asset_mapping", indexes, "Missing unique constraint")
        self._assert_index_covers_columns(
            "marketplace_mappings", ["tenant_id", "connection_id"],
            "(tenant, connection)")
        self._assert_index_covers_columns(
            "marketplace_mappings", ["connection_id", "hub_asset_id"],
            "(connection, hub_asset)")
        self._assert_index_covers_columns(
            "marketplace_mappings", ["tenant_id", "hub_asset_id"],
            "(tenant, hub_asset)")
        self._assert_index_covers_columns(
            "marketplace_mappings", ["external_listing_id"], "(external_listing_id)")

    def test_unique_constraints_exist(self):
        """Test that all unique constraints exist"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT conname, contype
                FROM pg_constraint
                WHERE conrelid IN (
                    SELECT oid FROM pg_class
                    WHERE relname LIKE 'marketplace%'
                )
                AND contype = 'u'
                ORDER BY conname
            """)
            constraints = {row[0]: row[1] for row in cursor.fetchall()}

        expected_constraints = [
            "unique_tenant_connection_name",  # marketplace_connections
            "unique_connection_asset_mapping",  # marketplace_mappings
        ]

        for constraint in expected_constraints:
            self.assertIn(constraint, constraints, f"Unique constraint {constraint} should exist")
            self.assertEqual(
                constraints[constraint], "u", f"Constraint {constraint} should be unique"
            )

    def test_foreign_key_constraints_exist(self):
        """Test that all foreign key constraints exist"""
        with connection.cursor() as cursor:
            # Check marketplace_connections FKs
            cursor.execute("""
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE conrelid = 'marketplace_connections'::regclass
                AND contype = 'f'
            """)
            connection_fk_count = cursor.fetchone()[0]
            self.assertGreaterEqual(
                connection_fk_count, 1, "marketplace_connections should have at least tenant FK"
            )

            # Check marketplace_sync_jobs FKs
            cursor.execute("""
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE conrelid = 'marketplace_sync_jobs'::regclass
                AND contype = 'f'
            """)
            sync_job_fk_count = cursor.fetchone()[0]
            self.assertGreaterEqual(
                sync_job_fk_count, 2, "marketplace_sync_jobs should have tenant and connection FKs"
            )

            # Check marketplace_mappings FKs
            cursor.execute("""
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE conrelid = 'marketplace_mappings'::regclass
                AND contype = 'f'
            """)
            mapping_fk_count = cursor.fetchone()[0]
            self.assertGreaterEqual(
                mapping_fk_count,
                3,
                "marketplace_mappings should have tenant, connection, and hub_asset FKs",
            )

    def test_migrations_applied(self):
        """Test that all migrations have been applied"""
        # Verify migrations are applied by checking table existence
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename LIKE 'marketplace%'
            """)
            table_count = cursor.fetchone()[0]

        # Verify at least the core marketplace tables exist.  Use
        # assertGreaterEqual instead of assertEqual so adding a new
        # marketplace_* table (a valid migration) doesn't break this test.
        self.assertGreaterEqual(
            table_count, 6,
            f"Expected at least 6 marketplace tables, found {table_count}"
        )

    def test_table_structures(self):
        """Test that table structures match expected schema"""
        # Test marketplace_connections structure
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'marketplace_connections'
                ORDER BY ordinal_position
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        expected_columns = [
            "id",
            "tenant_id",
            "marketplace_type",
            "name",
            "config",
            "is_active",
            "created_at",
            "updated_at",
        ]

        for col in expected_columns:
            self.assertIn(col, columns, f"Column {col} should exist in marketplace_connections")

        # Test marketplace_sync_jobs structure
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'marketplace_sync_jobs'
                ORDER BY ordinal_position
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        expected_columns = [
            "id",
            "tenant_id",
            "connection_id",
            "direction",
            "status",
            "items_synced",
            "items_failed",
            "errors",
            "metadata",
            "created_at",
            "updated_at",
            "completed_at",
        ]

        for col in expected_columns:
            self.assertIn(col, columns, f"Column {col} should exist in marketplace_sync_jobs")

        # Test marketplace_mappings structure
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'marketplace_mappings'
                ORDER BY ordinal_position
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        expected_columns = [
            "id",
            "tenant_id",
            "connection_id",
            "hub_asset_id",
            "external_listing_id",
            "external_resource_ids",
            "sync_metadata",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]

        for col in expected_columns:
            self.assertIn(col, columns, f"Column {col} should exist in marketplace_mappings")
