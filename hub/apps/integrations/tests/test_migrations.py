"""
Integration tests for marketplace migrations.

Tests that migrations correctly create all tables, indexes, and constraints.
"""
import pytest
from django.test import TestCase
from django.db import connection


pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceMigrationsTest(TestCase):
    """Test marketplace migrations rollback and reapplication"""

    def setUp(self):
        """Set up test fixtures"""
        # Ensure we're starting from a clean state
        self.initial_migrations = [
            '0001_initial',
            '0002_alter_marketplaceconnection_config_and_more',
            '0003_marketplacesyncjob_updated_at',
            '0004_marketplacemapping',
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
            'marketplace_connections',
            'marketplace_mappings',
            'marketplace_sync_jobs',
        ]

        for table in expected_tables:
            self.assertIn(table, tables, f"Table {table} should exist")

    def test_marketplace_connections_indexes(self):
        """Test that all indexes exist for marketplace_connections"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'marketplace_connections'
                ORDER BY indexname
            """)
            indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            'marketplace_connections_pkey',
            'marketplace_tenant__2b1851_idx',  # (tenant, marketplace_type)
            'marketplace_tenant__2590c0_idx',  # (tenant, is_active)
            'marketplace_marketp_f8af2a_idx',  # (marketplace_type, is_active)
            'unique_tenant_connection_name',   # Unique constraint
        ]

        for index in expected_indexes:
            self.assertIn(index, indexes, f"Index {index} should exist")

    def test_marketplace_sync_jobs_indexes(self):
        """Test that all indexes exist for marketplace_sync_jobs"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'marketplace_sync_jobs'
                ORDER BY indexname
            """)
            indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            'marketplace_sync_jobs_pkey',
            'marketplace_tenant__801ae8_idx',  # (tenant, connection)
            'marketplace_tenant__437c82_idx',  # (tenant, status)
            'marketplace_connect_efcfcf_idx',  # (connection, status)
            'marketplace_status_718840_idx',   # (status, created_at)
        ]

        for index in expected_indexes:
            self.assertIn(index, indexes, f"Index {index} should exist")

    def test_marketplace_mappings_indexes(self):
        """Test that all indexes exist for marketplace_mappings"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'marketplace_mappings'
                ORDER BY indexname
            """)
            indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            'marketplace_mappings_pkey',
            'marketplace_tenant__43e923_idx',  # (tenant, connection)
            'marketplace_connect_0b2496_idx',  # (connection, hub_asset)
            'marketplace_tenant__58c3cc_idx',  # (tenant, hub_asset)
            'marketplace_externa_f710ad_idx', # (external_listing_id)
            'unique_connection_asset_mapping', # Unique constraint
        ]

        for index in expected_indexes:
            self.assertIn(index, indexes, f"Index {index} should exist")

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
            'unique_tenant_connection_name',      # marketplace_connections
            'unique_connection_asset_mapping',    # marketplace_mappings
        ]

        for constraint in expected_constraints:
            self.assertIn(constraint, constraints, f"Unique constraint {constraint} should exist")
            self.assertEqual(constraints[constraint], 'u', f"Constraint {constraint} should be unique")

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
            self.assertGreaterEqual(connection_fk_count, 1, "marketplace_connections should have at least tenant FK")

            # Check marketplace_sync_jobs FKs
            cursor.execute("""
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE conrelid = 'marketplace_sync_jobs'::regclass
                AND contype = 'f'
            """)
            sync_job_fk_count = cursor.fetchone()[0]
            self.assertGreaterEqual(sync_job_fk_count, 2, "marketplace_sync_jobs should have tenant and connection FKs")

            # Check marketplace_mappings FKs
            cursor.execute("""
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE conrelid = 'marketplace_mappings'::regclass
                AND contype = 'f'
            """)
            mapping_fk_count = cursor.fetchone()[0]
            self.assertGreaterEqual(mapping_fk_count, 3, "marketplace_mappings should have tenant, connection, and hub_asset FKs")

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

        expected_table_count = 4  # marketplace_connections, marketplace_sync_jobs,
        # marketplace_mappings, marketplace_scheduled_syncs (0005)
        self.assertEqual(table_count, expected_table_count,
                        f"Expected {expected_table_count} marketplace tables, found {table_count}")

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
            'id', 'tenant_id', 'marketplace_type', 'name', 'config',
            'is_active', 'created_at', 'updated_at'
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
            'id', 'tenant_id', 'connection_id', 'direction', 'status',
            'items_synced', 'items_failed', 'errors', 'metadata',
            'created_at', 'updated_at', 'completed_at'
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
            'id', 'tenant_id', 'connection_id', 'hub_asset_id',
            'external_listing_id', 'external_resource_ids', 'sync_metadata',
            'last_synced_at', 'created_at', 'updated_at'
        ]

        for col in expected_columns:
            self.assertIn(col, columns, f"Column {col} should exist in marketplace_mappings")

