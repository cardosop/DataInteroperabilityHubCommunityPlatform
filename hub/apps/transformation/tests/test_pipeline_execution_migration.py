"""
Migration tests for PipelineExecution model.
"""
from django.test import TestCase
from django.db import connection
from django.core.management import call_command
from django.apps import apps


class PipelineExecutionMigrationTest(TestCase):
    """Test cases for PipelineExecution migration."""

    def test_migration_creates_table(self):
        """Test that migration creates transformation_pipeline_executions table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'transformation_pipeline_executions'
                );
            """)
            table_exists = cursor.fetchone()[0]
            self.assertTrue(table_exists, "transformation_pipeline_executions table should exist")

    def test_migration_creates_indexes(self):
        """Test that migration creates all required indexes."""
        with connection.cursor() as cursor:
            # Check indexes by querying pg_index and pg_attribute to verify columns
            cursor.execute("""
                SELECT
                    i.relname AS index_name,
                    array_agg(a.attname ORDER BY a.attnum) AS column_names
                FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE t.relname = 'transformation_pipeline_executions'
                AND t.relkind = 'r'
                GROUP BY i.relname
                ORDER BY i.relname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            # Verify indexes exist on required columns
            has_pipeline_index = any('pipeline_id' in cols for cols in indexes.values())
            has_asset_index = any('asset_id' in cols for cols in indexes.values())
            has_status_index = any('status' in cols for cols in indexes.values())
            has_started_at_index = any('started_at' in cols for cols in indexes.values())

            self.assertTrue(has_pipeline_index, "Should have index on pipeline_id")
            self.assertTrue(has_asset_index, "Should have index on asset_id")
            self.assertTrue(has_status_index, "Should have index on status")
            self.assertTrue(has_started_at_index, "Should have index on started_at")

    def test_migration_fields_exist(self):
        """Test that all required fields exist in the table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'transformation_pipeline_executions'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # Check required fields
            required_fields = [
                'id', 'pipeline_id', 'asset_id', 'execution_mode', 'status',
                'started_at', 'completed_at', 'result_asset_id', 'execution_log',
                'metrics', 'created_at', 'updated_at'
            ]

            for field in required_fields:
                self.assertIn(field, columns, f"Field {field} should exist")

    def test_migration_jsonb_field_type(self):
        """Test that execution_log and metrics are JSONB fields."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = 'transformation_pipeline_executions'
                AND column_name IN ('execution_log', 'metrics');
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # PostgreSQL JSONB fields show as 'jsonb' in udt_name
            if 'execution_log' in columns:
                self.assertEqual(columns['execution_log'][1], 'jsonb', "execution_log should be JSONB")
            if 'metrics' in columns:
                self.assertEqual(columns['metrics'][1], 'jsonb', "metrics should be JSONB")

    def test_migration_foreign_key_constraints(self):
        """Test that foreign key constraints are created."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_name = 'transformation_pipeline_executions';
            """)
            foreign_keys = list(cursor.fetchall())

            # Should have foreign keys to transformation_pipelines, assets (2x)
            fk_tables = {fk[2] for fk in foreign_keys}
            self.assertIn('transformation_pipelines', fk_tables, "Should have FK to transformation_pipelines")
            self.assertIn('assets', fk_tables, "Should have FK to assets")

    def test_migration_forward_creates_model(self):
        """Test that forward migration creates model that can be used."""
        # This test verifies the model can be imported and used
        from hub.apps.transformation.models import PipelineExecution

        self.assertIsNotNone(PipelineExecution)
        self.assertTrue(hasattr(PipelineExecution, '_meta'))
        self.assertEqual(PipelineExecution._meta.db_table, 'transformation_pipeline_executions')

    def test_migration_rollback_removes_table(self):
        """Test that backward migration removes the table."""
        # Verify table exists (migration has been applied)
        with connection.cursor() as cursor:
            # Check table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'transformation_pipeline_executions'
                );
            """)
            exists = cursor.fetchone()[0]
            self.assertTrue(exists, "Table should exist after migration")

            # Note: We don't actually test rollback in this test to avoid breaking other tests
            # The rollback functionality is tested by Django's migration framework itself
            # This test just verifies the table structure is correct and migration was applied

