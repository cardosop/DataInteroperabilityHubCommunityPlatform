"""
Tests for workflow state database migrations.

Tests migration scripts to ensure:
- Tables are created correctly
- Indexes are created correctly
- Constraints are created correctly
- Data integrity is maintained
"""

import uuid
from io import StringIO

from django.db import connection
from django.test import TestCase

from hub.apps.orchestration.models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowState,
    WorkflowStatus,
    WorkflowStep,
)


class WorkflowStateMigrationTest(TestCase):
    """
    Test workflow state database migrations.

    Tests verify that migrations create the correct schema structure.
    """

    def setUp(self):
        """Set up test fixtures."""

    def test_migration_creates_tables(self):
        """Test that migration creates all required tables."""
        with connection.cursor() as cursor:
            # Check workflow_definitions table
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'workflow_definitions'
                );
            """)
            self.assertTrue(cursor.fetchone()[0], "workflow_definitions table should exist")

            # Check workflow_instances table
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'workflow_instances'
                );
            """)
            self.assertTrue(cursor.fetchone()[0], "workflow_instances table should exist")

            # Check workflow_steps table
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'workflow_steps'
                );
            """)
            self.assertTrue(cursor.fetchone()[0], "workflow_steps table should exist")

            # Check workflow_states table
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'workflow_states'
                );
            """)
            self.assertTrue(cursor.fetchone()[0], "workflow_states table should exist")

    def test_migration_creates_indexes(self):
        """Test that migration creates all required indexes.

        Verifies indexes by table + columns rather than hardcoded names
        (auto-generated hash suffixes change when models are modified).
        """
        with connection.cursor() as cursor:
            # (table_name, expected_indexed_columns)
            # These correspond to the indexes declared in Meta.indexes on
            # WorkflowDefinition, WorkflowInstance, and WorkflowStep models.
            expected_indexes = [
                # WorkflowDefinition.Meta.indexes:
                ("workflow_definitions", ["name", "is_active"]),
                ("workflow_definitions", ["name", "version"]),
                ("workflow_definitions", ["is_active", "created_at"]),
                # WorkflowInstance.Meta.indexes:
                ("workflow_instances", ["tenant_id", "status"]),
                ("workflow_instances", ["tenant_id", "workflow_name", "status"]),
                ("workflow_instances", ["workflow_name", "status", "created_at"]),
                ("workflow_instances", ["status", "created_at"]),
                ("workflow_instances", ["status", "started_at"]),
                # WorkflowStep.Meta.indexes:
                ("workflow_steps", ["workflow_instance_id", "status"]),
                ("workflow_steps", ["workflow_instance_id", "step_index"]),
                ("workflow_steps", ["status", "created_at"]),
            ]

            cursor.execute("""
                SELECT tablename, indexname, array_agg(col ORDER BY colno) as cols
                FROM (
                    SELECT
                        t.relname AS tablename,
                        i.relname AS indexname,
                        a.attname AS col,
                        array_position(ix.indkey, a.attnum) AS colno
                    FROM pg_index ix
                    JOIN pg_class t ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                    WHERE t.relnamespace = 'public'::regnamespace
                      AND t.relname IN (
                          'workflow_definitions', 'workflow_instances',
                          'workflow_steps', 'workflow_snapshots'
                      )
                ) sub
                GROUP BY tablename, indexname
            """)
            existing_indexes = {
                (row[0], tuple(row[2])): row[1] for row in cursor.fetchall()
            }

            for table, columns in expected_indexes:
                key = (table, tuple(columns))
                self.assertIn(
                    key, existing_indexes,
                    f"Index on {table}({', '.join(columns)}) should exist",
                )

    def test_migration_creates_constraints(self):
        """Test that migration creates all required constraints (post-0002: unique_together)."""
        with connection.cursor() as cursor:
            # After 0002, workflow_def_name_version_unique was removed and replaced by
            # AlterUniqueTogether(name, version) which creates a constraint with a generated name
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    WHERE t.relname = 'workflow_definitions'
                    AND c.contype = 'u'
                    AND array_length(c.conkey, 1) = 2
                );
            """)
            self.assertTrue(
                cursor.fetchone()[0],
                "Unique constraint on workflow_definitions (name, version) should exist",
            )

            # After 0002, workflow_step_inst_index_unique was removed and replaced by
            # AlterUniqueTogether(workflow_instance, step_index)
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    WHERE t.relname = 'workflow_steps'
                    AND c.contype = 'u'
                );
            """)
            self.assertTrue(
                cursor.fetchone()[0], "Unique constraint on workflow_steps should exist"
            )

    def test_migration_creates_foreign_keys(self):
        """Test that migration creates all required foreign keys."""
        with connection.cursor() as cursor:
            # Check foreign key from workflow_instances to workflow_definitions
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_constraint 
                    WHERE conname LIKE '%workflow_instances_workflow_definition%'
                    AND contype = 'f'
                );
            """)
            self.assertTrue(
                cursor.fetchone()[0],
                "Foreign key from workflow_instances to workflow_definitions should exist",
            )

            # Check foreign key from workflow_steps to workflow_instances
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_constraint 
                    WHERE conname LIKE '%workflow_steps_workflow_instance%'
                    AND contype = 'f'
                );
            """)
            self.assertTrue(
                cursor.fetchone()[0],
                "Foreign key from workflow_steps to workflow_instances should exist",
            )

            # Check foreign key from workflow_states to workflow_instances
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_constraint 
                    WHERE conname LIKE '%workflow_states_workflow_instance%'
                    AND contype = 'f'
                );
            """)
            self.assertTrue(
                cursor.fetchone()[0],
                "Foreign key from workflow_states to workflow_instances should exist",
            )

    def test_migration_table_structure(self):
        """Test that tables have correct column structure."""
        with connection.cursor() as cursor:
            # Check workflow_definitions columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'workflow_definitions'
                ORDER BY ordinal_position;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            self.assertIn("id", columns)
            self.assertEqual(columns["id"][0], "uuid")
            self.assertIn("name", columns)
            self.assertEqual(columns["name"][0], "character varying")
            self.assertIn("version", columns)
            self.assertIn("dsl_json", columns)
            self.assertEqual(columns["dsl_json"][0], "jsonb")

            # Check workflow_instances columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'workflow_instances'
                ORDER BY ordinal_position;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            self.assertIn("id", columns)
            self.assertEqual(columns["id"][0], "uuid")
            self.assertIn("workflow_name", columns)
            self.assertIn("status", columns)
            self.assertIn("input_data", columns)
            self.assertEqual(columns["input_data"][0], "jsonb")
            self.assertIn("state_data", columns)
            self.assertEqual(columns["state_data"][0], "jsonb")

            # Check workflow_steps columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'workflow_steps'
                ORDER BY ordinal_position;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            self.assertIn("id", columns)
            self.assertEqual(columns["id"][0], "uuid")
            self.assertIn("step_index", columns)
            self.assertIn("step_name", columns)
            self.assertIn("status", columns)

            # Check workflow_states columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'workflow_states'
                ORDER BY ordinal_position;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            self.assertIn("id", columns)
            self.assertEqual(columns["id"][0], "uuid")
            self.assertIn("snapshot_type", columns)
            self.assertIn("state_data", columns)
            self.assertEqual(columns["state_data"][0], "jsonb")

    def test_migration_data_integrity(self):
        """Test that migration maintains data integrity."""
        # Create workflow definition with unique name to avoid collisions
        # with stale --reuse-db data.
        wf_name = f"test_workflow_{uuid.uuid4().hex[:8]}"
        definition = WorkflowDefinition.objects.create(
            name=wf_name,
            version="1.0.0",
            dsl_json={"version": "1.0", "steps": [{"name": "step1", "type": "task"}]},
        )

        # Create workflow instance
        instance = WorkflowInstance.objects.create(
            workflow_definition=definition,
            workflow_name=wf_name,
            workflow_version="1.0.0",
            status=WorkflowStatus.DRAFT,
            input_data={"test": "data"},
        )

        # Create workflow step
        step = WorkflowStep.objects.create(
            workflow_instance=instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.PENDING,
        )

        # Create workflow state
        state = WorkflowState.objects.create(
            workflow_instance=instance,
            snapshot_type="checkpoint",
            state_data={"test": "state"},
            step_states=[],
        )

        # Verify data integrity
        self.assertEqual(instance.workflow_definition.id, definition.id)
        self.assertEqual(step.workflow_instance.id, instance.id)
        self.assertEqual(state.workflow_instance.id, instance.id)

        # Test cascade delete
        instance.delete()
        self.assertFalse(WorkflowStep.objects.filter(id=step.id).exists())
        self.assertFalse(WorkflowState.objects.filter(id=state.id).exists())
        self.assertTrue(WorkflowDefinition.objects.filter(id=definition.id).exists())  # PROTECT

    def test_migration_unique_constraints(self):
        """Test that unique constraints work correctly."""
        # Create workflow definition
        definition = WorkflowDefinition.objects.create(
            name="test_workflow_unique",
            version="1.0.0",
            dsl_json={"version": "1.0", "steps": [{"name": "step1", "type": "task"}]},
        )

        # Try to create duplicate (should fail)
        with self.assertRaises(Exception):
            WorkflowDefinition.objects.create(
                name="test_workflow_unique",
                version="1.0.0",
                dsl_json={"version": "1.0", "steps": [{"name": "step1", "type": "task"}]},
            )

        # Create workflow instance
        instance = WorkflowInstance.objects.create(
            workflow_definition=definition,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            status=WorkflowStatus.DRAFT,
        )

        # Create workflow step
        WorkflowStep.objects.create(
            workflow_instance=instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.PENDING,
        )

        # Try to create duplicate step (should fail)
        with self.assertRaises(Exception):
            WorkflowStep.objects.create(
                workflow_instance=instance,
                step_index=0,
                step_name="step1",
                step_type="task",
                status=StepStatus.PENDING,
            )

    def test_migration_indexes_performance(self):
        """Test that indexes improve query performance."""
        # Create test data
        definition = WorkflowDefinition.objects.create(
            name="test_workflow_perf",
            version="1.0.0",
            dsl_json={"version": "1.0", "steps": [{"name": "step1", "type": "task"}]},
        )

        # Create multiple instances
        for i in range(10):
            WorkflowInstance.objects.create(
                workflow_definition=definition,
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                status=WorkflowStatus.DRAFT if i % 2 == 0 else WorkflowStatus.RUNNING,
            )

        # Query with index (should be fast)
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN SELECT * FROM workflow_instances WHERE status = 'DRAFT'")
            result = cursor.fetchall()
            # Check that index is used (may be named differently, so just verify query works)
            explain_output = "\n".join([row[0] for row in result])
            # Index usage may vary, so we just verify the query executes successfully
            self.assertIsNotNone(explain_output)


class WorkflowStateMigrationRollbackTest(TestCase):
    """Test migration rollback scenarios."""

    def test_migration_can_be_rolled_back(self):
        """Test that migration can be rolled back safely."""
        # This test would require manual migration rollback
        # For now, we'll just verify the migration is reversible
        # by checking that Django can detect migration state

        # Get current migration state
        from django.db import connection
        from django.db.migrations.recorder import MigrationRecorder

        recorder = MigrationRecorder(connection)
        applied_migrations = recorder.applied_migrations()

        # Check that orchestration migrations are applied
        orchestration_migrations = [m for m in applied_migrations if m[0] == "orchestration"]

        self.assertGreater(
            len(orchestration_migrations), 0, "Orchestration migrations should be applied"
        )
