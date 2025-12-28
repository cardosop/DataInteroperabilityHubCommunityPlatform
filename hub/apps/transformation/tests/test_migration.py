"""
Test migration 0001_initial for TransformationPipeline model.

Tests:
1. Migration forward (creates table, indexes, constraints)
2. Migration rollback (removes table, indexes, constraints)
3. Index creation verification
4. Constraint creation verification
5. Field creation verification

Note: Uses TestCase instead of TransactionTestCase to avoid flush issues with foreign key constraints.
"""
from django.test import TestCase
from django.db import connection
from django.core.management import call_command
from django.apps import apps
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus

User = get_user_model()


class TransformationPipelineMigrationTest(TestCase):
    """Test migration 0001_initial for TransformationPipeline model"""

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

    def test_migration_creates_table(self):
        """Test that migration creates the transformation_pipelines table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'transformation_pipelines'
                );
            """)
            table_exists = cursor.fetchone()[0]
            self.assertTrue(table_exists, "transformation_pipelines table should exist")

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
                WHERE t.relname = 'transformation_pipelines'
                AND t.relkind = 'r'
                GROUP BY i.relname
                ORDER BY i.relname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            # Verify indexes exist on required columns
            has_tenant_index = any('tenant_id' in cols for cols in indexes.values())
            has_created_by_index = any('created_by_id' in cols for cols in indexes.values())
            has_status_index = any('status' in cols for cols in indexes.values())
            has_created_at_index = any('created_at' in cols for cols in indexes.values())

            self.assertTrue(has_tenant_index, "Should have index on tenant_id")
            self.assertTrue(has_created_by_index, "Should have index on created_by_id")
            self.assertTrue(has_status_index, "Should have index on status")
            self.assertTrue(has_created_at_index, "Should have index on created_at")

    def test_migration_creates_unique_constraint(self):
        """Test that migration creates unique constraint on tenant, name, version."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT conname, contype
                FROM pg_constraint
                WHERE conrelid = 'transformation_pipelines'::regclass
                AND contype = 'u';
            """)
            constraints = cursor.fetchall()

            # Should have at least one unique constraint
            self.assertGreater(len(constraints), 0, "Should have unique constraint")

            # Check constraint name contains expected fields
            constraint_names = [row[0] for row in constraints]
            constraint_name_str = ' '.join(constraint_names)
            self.assertIn('unique_pipeline_name_version_per_tenant', constraint_name_str.lower())

    def test_migration_forward_creates_model(self):
        """Test that forward migration allows creating TransformationPipeline instances."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            description="Test description",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0",
            status=PipelineStatus.DRAFT
        )

        self.assertIsNotNone(pipeline.id)
        self.assertEqual(pipeline.name, "Test Pipeline")
        self.assertEqual(pipeline.tenant, self.tenant)
        self.assertEqual(pipeline.created_by, self.user)

    def test_migration_rollback_removes_table(self):
        """Test that migration rollback removes the table."""
        # First verify table exists
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'transformation_pipelines'
                );
            """)
            table_exists_before = cursor.fetchone()[0]
            self.assertTrue(table_exists_before, "Table should exist before rollback")

        # Rollback migration
        call_command('migrate', 'transformation', 'zero', verbosity=0, interactive=False)

        # Verify table is removed
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'transformation_pipelines'
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
                WHERE table_name = 'transformation_pipelines'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # Check required fields exist
            required_fields = [
                'id', 'tenant_id', 'created_by_id', 'name', 'description',
                'pipeline_definition', 'version', 'status', 'created_at',
                'updated_at', 'metadata'
            ]

            for field in required_fields:
                self.assertIn(field, columns, f"Field {field} should exist")

    def test_migration_jsonb_field_type(self):
        """Test that pipeline_definition and metadata are JSONB fields."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'transformation_pipelines'
                AND column_name IN ('pipeline_definition', 'metadata');
            """)
            json_fields = {row[0]: row[1] for row in cursor.fetchall()}

            # PostgreSQL JSONField maps to jsonb
            self.assertEqual(json_fields.get('pipeline_definition'), 'jsonb')
            self.assertEqual(json_fields.get('metadata'), 'jsonb')

    def test_migration_foreign_key_constraints(self):
        """Test that foreign key constraints are created correctly."""
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
                WHERE tc.table_name = 'transformation_pipelines'
                AND tc.constraint_type = 'FOREIGN KEY';
            """)
            foreign_keys = cursor.fetchall()

            # Should have foreign keys to tenants and users
            fk_tables = [fk[2] for fk in foreign_keys]
            self.assertIn('tenants', fk_tables, "Should have foreign key to tenants table")
            self.assertIn('users', fk_tables, "Should have foreign key to users table")

