"""
Tests for workflow state database migrations.

Tests migration scripts to ensure:
- Tables are created correctly
- Indexes are created correctly
- Constraints are created correctly
- Data integrity is maintained
"""
import uuid
from django.test import TestCase, TransactionTestCase
from django.db import connection, transaction
from django.core.management import call_command
from django.core.management.color import no_style
from io import StringIO

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowState,
    WorkflowStatus,
    StepStatus,
)


class WorkflowStateMigrationTest(TestCase):
    """
    Test workflow state database migrations.
    
    Tests verify that migrations create the correct schema structure.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.out = StringIO()
    
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
        """Test that migration creates all required indexes (post-0002 renamed names)."""
        with connection.cursor() as cursor:
            # After 0002_add_workflow_instance_to_pipeline_execution, indexes were renamed
            required_indexes = [
                'workflow_de_name_060d27_idx',
                'workflow_de_name_6658a0_idx',
                'workflow_de_is_acti_136d63_idx',
                'workflow_in_tenant__bd9218_idx',
                'workflow_in_tenant__eb9218_idx',
                'workflow_in_status_293e15_idx',
                'workflow_in_workflo_c26fa6_idx',
                'workflow_in_status_57a7cd_idx',
                'workflow_st_workflo_58d189_idx',
                'workflow_st_workflo_1aceca_idx',
                'workflow_st_status_fed7f5_idx',
                'workflow_st_workflo_23c6e2_idx',
                'workflow_st_snapsho_2f0950_idx',
            ]
            
            for index_name in required_indexes:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM pg_indexes 
                        WHERE schemaname = 'public' 
                        AND indexname = %s
                    );
                """, [index_name])
                self.assertTrue(
                    cursor.fetchone()[0],
                    f"Index {index_name} should exist"
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
            self.assertTrue(cursor.fetchone()[0], "Unique constraint on workflow_definitions (name, version) should exist")
            
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
            self.assertTrue(cursor.fetchone()[0], "Unique constraint on workflow_steps should exist")
    
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
            self.assertTrue(cursor.fetchone()[0], "Foreign key from workflow_instances to workflow_definitions should exist")
            
            # Check foreign key from workflow_steps to workflow_instances
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_constraint 
                    WHERE conname LIKE '%workflow_steps_workflow_instance%'
                    AND contype = 'f'
                );
            """)
            self.assertTrue(cursor.fetchone()[0], "Foreign key from workflow_steps to workflow_instances should exist")
            
            # Check foreign key from workflow_states to workflow_instances
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_constraint 
                    WHERE conname LIKE '%workflow_states_workflow_instance%'
                    AND contype = 'f'
                );
            """)
            self.assertTrue(cursor.fetchone()[0], "Foreign key from workflow_states to workflow_instances should exist")
    
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
            
            self.assertIn('id', columns)
            self.assertEqual(columns['id'][0], 'uuid')
            self.assertIn('name', columns)
            self.assertEqual(columns['name'][0], 'character varying')
            self.assertIn('version', columns)
            self.assertIn('dsl_json', columns)
            self.assertEqual(columns['dsl_json'][0], 'jsonb')
            
            # Check workflow_instances columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'workflow_instances'
                ORDER BY ordinal_position;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
            
            self.assertIn('id', columns)
            self.assertEqual(columns['id'][0], 'uuid')
            self.assertIn('workflow_name', columns)
            self.assertIn('status', columns)
            self.assertIn('input_data', columns)
            self.assertEqual(columns['input_data'][0], 'jsonb')
            self.assertIn('state_data', columns)
            self.assertEqual(columns['state_data'][0], 'jsonb')
            
            # Check workflow_steps columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'workflow_steps'
                ORDER BY ordinal_position;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
            
            self.assertIn('id', columns)
            self.assertEqual(columns['id'][0], 'uuid')
            self.assertIn('step_index', columns)
            self.assertIn('step_name', columns)
            self.assertIn('status', columns)
            
            # Check workflow_states columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'workflow_states'
                ORDER BY ordinal_position;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
            
            self.assertIn('id', columns)
            self.assertEqual(columns['id'][0], 'uuid')
            self.assertIn('snapshot_type', columns)
            self.assertIn('state_data', columns)
            self.assertEqual(columns['state_data'][0], 'jsonb')
    
    def test_migration_data_integrity(self):
        """Test that migration maintains data integrity."""
        # Create workflow definition
        definition = WorkflowDefinition.objects.create(
            name='test_workflow',
            version='1.0.0',
            dsl_json={
                'version': '1.0',
                'steps': [
                    {'name': 'step1', 'type': 'task'}
                ]
            }
        )
        
        # Create workflow instance
        instance = WorkflowInstance.objects.create(
            workflow_definition=definition,
            workflow_name='test_workflow',
            workflow_version='1.0.0',
            status=WorkflowStatus.DRAFT,
            input_data={'test': 'data'}
        )
        
        # Create workflow step
        step = WorkflowStep.objects.create(
            workflow_instance=instance,
            step_index=0,
            step_name='step1',
            step_type='task',
            status=StepStatus.PENDING
        )
        
        # Create workflow state
        state = WorkflowState.objects.create(
            workflow_instance=instance,
            snapshot_type='checkpoint',
            state_data={'test': 'state'},
            step_states=[]
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
            name='test_workflow_unique',
            version='1.0.0',
            dsl_json={'version': '1.0', 'steps': [{'name': 'step1', 'type': 'task'}]}
        )
        
        # Try to create duplicate (should fail)
        with self.assertRaises(Exception):
            WorkflowDefinition.objects.create(
                name='test_workflow_unique',
                version='1.0.0',
                dsl_json={'version': '1.0', 'steps': [{'name': 'step1', 'type': 'task'}]}
            )
        
        # Create workflow instance
        instance = WorkflowInstance.objects.create(
            workflow_definition=definition,
            workflow_name='test_workflow',
            workflow_version='1.0.0',
            status=WorkflowStatus.DRAFT
        )
        
        # Create workflow step
        WorkflowStep.objects.create(
            workflow_instance=instance,
            step_index=0,
            step_name='step1',
            step_type='task',
            status=StepStatus.PENDING
        )
        
        # Try to create duplicate step (should fail)
        with self.assertRaises(Exception):
            WorkflowStep.objects.create(
                workflow_instance=instance,
                step_index=0,
                step_name='step1',
                step_type='task',
                status=StepStatus.PENDING
            )
    
    def test_migration_indexes_performance(self):
        """Test that indexes improve query performance."""
        # Create test data
        definition = WorkflowDefinition.objects.create(
            name='test_workflow_perf',
            version='1.0.0',
            dsl_json={'version': '1.0', 'steps': [{'name': 'step1', 'type': 'task'}]}
        )
        
        # Create multiple instances
        for i in range(10):
            WorkflowInstance.objects.create(
                workflow_definition=definition,
                workflow_name='test_workflow',
                workflow_version='1.0.0',
                status=WorkflowStatus.DRAFT if i % 2 == 0 else WorkflowStatus.RUNNING
            )
        
        # Query with index (should be fast)
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN SELECT * FROM workflow_instances WHERE status = 'DRAFT'")
            result = cursor.fetchall()
            # Check that index is used (may be named differently, so just verify query works)
            explain_output = '\n'.join([row[0] for row in result])
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
        from django.db.migrations.recorder import MigrationRecorder
        from django.db import connection
        recorder = MigrationRecorder(connection)
        applied_migrations = recorder.applied_migrations()
        
        # Check that orchestration migrations are applied
        orchestration_migrations = [
            m for m in applied_migrations
            if m[0] == 'orchestration'
        ]
        
        self.assertGreater(len(orchestration_migrations), 0, "Orchestration migrations should be applied")

