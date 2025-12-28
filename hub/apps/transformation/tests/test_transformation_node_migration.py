"""
Test migration 0002 for TransformationNode model.

Tests:
1. Migration forward (creates table, indexes, constraints)
2. Migration rollback (removes table, indexes, constraints)
3. Index creation verification
4. Field creation verification
5. Foreign key constraint verification

Note: Uses TestCase instead of TransactionTestCase to avoid flush issues with foreign key constraints.
"""
from django.test import TestCase
from django.db import connection
from django.core.management import call_command
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.transformation.models import TransformationPipeline, TransformationNode, PipelineStatus

User = get_user_model()


class TransformationNodeMigrationTest(TestCase):
    """Test migration 0002 for TransformationNode model"""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.valid_pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "extract_data",
                    "input": {}
                }
            ]
        }
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            description="Test pipeline description",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0",
            status=PipelineStatus.DRAFT
        )

    def test_migration_creates_table(self):
        """Test that migration creates the transformation_nodes table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'transformation_nodes'
                );
            """)
            table_exists = cursor.fetchone()[0]
            self.assertTrue(table_exists, "transformation_nodes table should exist")

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
                WHERE t.relname = 'transformation_nodes'
                AND t.relkind = 'r'
                GROUP BY i.relname
                ORDER BY i.relname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            # Verify indexes exist on required columns
            has_pipeline_index = any('pipeline_id' in cols for cols in indexes.values())
            has_node_type_index = any('node_type' in cols for cols in indexes.values())
            has_order_index = any('order' in cols for cols in indexes.values())
            has_pipeline_order_index = any(
                'pipeline_id' in cols and 'order' in cols
                for cols in indexes.values()
            )

            self.assertTrue(has_pipeline_index, "Should have index on pipeline_id")
            self.assertTrue(has_node_type_index, "Should have index on node_type")
            self.assertTrue(has_order_index, "Should have index on order")
            self.assertTrue(
                has_pipeline_order_index,
                "Should have composite index on pipeline_id and order"
            )

    def test_migration_creates_foreign_key_constraint(self):
        """Test that migration creates foreign key constraint to transformation_pipelines."""
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
                WHERE tc.table_name = 'transformation_nodes'
                AND tc.constraint_type = 'FOREIGN KEY';
            """)
            foreign_keys = cursor.fetchall()

            # Should have foreign key to transformation_pipelines
            fk_tables = [fk[2] for fk in foreign_keys]
            self.assertIn(
                'transformation_pipelines',
                fk_tables,
                "Should have foreign key to transformation_pipelines table"
            )

            # Verify the foreign key column
            fk_columns = {fk[1]: fk[2] for fk in foreign_keys}
            self.assertEqual(
                fk_columns.get('pipeline_id'),
                'transformation_pipelines',
                "pipeline_id should reference transformation_pipelines"
            )

    def test_migration_forward_creates_model(self):
        """Test that forward migration allows creating TransformationNode instances."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={"filter_expression": "age > 18"},
            position={"x": 100, "y": 200},
            order=1
        )

        self.assertIsNotNone(node.id)
        self.assertEqual(node.pipeline, self.pipeline)
        self.assertEqual(node.node_type, "filter")
        self.assertEqual(node.order, 1)

    def test_migration_rollback_removes_table(self):
        """Test that migration rollback removes the table."""
        # First verify table exists
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'transformation_nodes'
                );
            """)
            table_exists_before = cursor.fetchone()[0]
            self.assertTrue(table_exists_before, "Table should exist before rollback")

        # Rollback migration (rollback to 0001)
        call_command('migrate', 'transformation', '0001', verbosity=0, interactive=False)

        # Verify table is removed
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'transformation_nodes'
                );
            """)
            table_exists_after = cursor.fetchone()[0]
            self.assertFalse(table_exists_after, "Table should not exist after rollback")

        # Re-apply migration for other tests
        call_command('migrate', 'transformation', verbosity=0, interactive=False)

    def test_migration_fields_exist(self):
        """Test that all required fields exist in the table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'transformation_nodes'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # Check required fields exist
            required_fields = [
                'id', 'pipeline_id', 'node_type', 'node_config',
                'position', 'order', 'created_at', 'updated_at'
            ]

            for field in required_fields:
                self.assertIn(field, columns, f"Field {field} should exist")

    def test_migration_jsonb_field_type(self):
        """Test that node_config and position are JSONB fields."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'transformation_nodes'
                AND column_name IN ('node_config', 'position');
            """)
            json_fields = {row[0]: row[1] for row in cursor.fetchall()}

            # PostgreSQL JSONField maps to jsonb
            self.assertEqual(json_fields.get('node_config'), 'jsonb')
            self.assertEqual(json_fields.get('position'), 'jsonb')

    def test_migration_uuid_field_type(self):
        """Test that id field is UUID type."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'transformation_nodes'
                AND column_name = 'id';
            """)
            id_field = cursor.fetchone()

            # PostgreSQL UUIDField maps to uuid
            self.assertEqual(id_field[1], 'uuid')

    def test_migration_integer_field_type(self):
        """Test that order field is integer type."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'transformation_nodes'
                AND column_name = 'order';
            """)
            order_field = cursor.fetchone()

            # PostgreSQL IntegerField maps to integer
            self.assertEqual(order_field[1], 'integer')

    def test_migration_cascade_delete(self):
        """Test that cascade delete works correctly."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=1
        )
        node_id = node.id

        # Delete pipeline
        self.pipeline.delete()

        # Node should be deleted due to CASCADE
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM transformation_nodes
                    WHERE id = %s
                );
            """, [str(node_id)])
            node_exists = cursor.fetchone()[0]
            self.assertFalse(node_exists, "Node should be deleted when pipeline is deleted")

