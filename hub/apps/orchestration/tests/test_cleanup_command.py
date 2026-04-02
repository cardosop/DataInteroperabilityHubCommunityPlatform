"""
Tests for workflow state cleanup management command.
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowState,
    WorkflowStatus,
    WorkflowStep,
)
from hub.apps.tenants.models import KYCStatus, Tenant
import uuid

User = get_user_model()


class CleanupWorkflowStateCommandTest(TestCase):
    """Test workflow state cleanup command."""

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com", tenant=self.tenant, status="ACTIVE"
        )
        # Create workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={"version": "1.0", "steps": [{"name": "step1", "type": "task"}]},
        )

    def test_archive_completed_workflows(self):
        """Test archiving completed workflows."""
        # Create completed workflow older than archive threshold
        old_date = timezone.now() - timedelta(days=100)
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            completed_at=old_date,
        )

        # Run cleanup command
        out = StringIO()
        call_command("cleanup_workflow_state", "--archive-days=90", stdout=out)

        # Verify workflow is archived
        workflow.refresh_from_db()
        self.assertTrue(workflow.state_data.get("archived"))
        self.assertIsNotNone(workflow.state_data.get("archived_at"))

    def test_dry_run_mode(self):
        """Test dry run mode doesn't make changes."""
        old_date = timezone.now() - timedelta(days=100)
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            completed_at=old_date,
        )

        # Run cleanup command in dry run mode
        out = StringIO()
        call_command("cleanup_workflow_state", "--archive-days=90", "--dry-run", stdout=out)

        # Verify workflow is NOT archived
        workflow.refresh_from_db()
        self.assertFalse(workflow.state_data.get("archived", False))

    def test_delete_archived_workflows(self):
        """Test deleting archived workflows."""
        old_date = timezone.now() - timedelta(days=400)
        workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            completed_at=old_date,
            state_data={"archived": True, "archived_at": old_date.isoformat()},
        )

        # Create workflow steps and states
        step = WorkflowStep.objects.create(
            workflow_instance=workflow, step_index=0, step_name="test_step", step_type="task"
        )
        state = WorkflowState.objects.create(
            workflow_instance=workflow, snapshot_type="checkpoint", state_data={}
        )

        # Run cleanup command
        out = StringIO()
        call_command("cleanup_workflow_state", "--delete-days=365", stdout=out)

        # Verify workflow and related data are deleted
        self.assertFalse(WorkflowInstance.objects.filter(id=workflow.id).exists())
        self.assertFalse(WorkflowStep.objects.filter(id=step.id).exists())
        self.assertFalse(WorkflowState.objects.filter(id=state.id).exists())

    def test_cleanup_orphaned_states(self):
        """Test cleaning up orphaned workflow states."""
        # Create an orphaned state using raw SQL to bypass Django's FK validation
        # This simulates a state that references a deleted workflow instance
        import uuid

        from django.db import connection

        orphaned_state_id = uuid.uuid4()
        orphaned_workflow_id = uuid.uuid4()

        # Create orphaned state using raw SQL (bypasses FK constraint)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO workflow_states (id, workflow_instance_id, snapshot_type, state_data, step_states, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                [str(orphaned_state_id), str(orphaned_workflow_id), "checkpoint", "{}", "[]"],
            )

        # Verify orphaned state exists
        orphaned_state = WorkflowState.objects.filter(id=orphaned_state_id).first()
        self.assertIsNotNone(orphaned_state)

        # Run cleanup command
        out = StringIO()
        call_command("cleanup_workflow_state", "--cleanup-orphaned", stdout=out)

        # Verify orphaned state is deleted
        self.assertFalse(WorkflowState.objects.filter(id=orphaned_state_id).exists())

    def test_tenant_filtering(self):
        """Test tenant filtering in cleanup."""
        # Create tenant-specific workflows
        tenant1_workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            completed_at=timezone.now() - timedelta(days=100),
        )

        _uid = uuid.uuid4().hex[:8]
        tenant2 = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        tenant2_workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=tenant2,
            status=WorkflowStatus.COMPLETED,
            completed_at=timezone.now() - timedelta(days=100),
        )

        # Run cleanup for specific tenant
        out = StringIO()
        call_command(
            "cleanup_workflow_state",
            "--archive-days=90",
            f"--tenant-id={self.tenant.id}",
            stdout=out,
        )

        # Verify only tenant1 workflow is archived
        tenant1_workflow.refresh_from_db()
        tenant2_workflow.refresh_from_db()
        self.assertTrue(tenant1_workflow.state_data.get("archived"))
        self.assertFalse(tenant2_workflow.state_data.get("archived", False))

    def test_no_workflows_to_cleanup(self):
        """Test cleanup when no workflows match criteria."""
        # Create recent workflow (not old enough)
        recent_workflow = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            completed_at=timezone.now() - timedelta(days=30),
        )

        # Run cleanup command
        out = StringIO()
        call_command("cleanup_workflow_state", "--archive-days=90", stdout=out)

        # Verify workflow is not archived
        recent_workflow.refresh_from_db()
        self.assertFalse(recent_workflow.state_data.get("archived", False))

    def test_multiple_status_cleanup(self):
        """Test cleanup handles multiple terminal statuses."""
        old_date = timezone.now() - timedelta(days=100)

        # Create workflows with different terminal statuses
        completed = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="completed",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            completed_at=old_date,
        )
        failed = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="failed",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            completed_at=old_date,
        )
        cancelled = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="cancelled",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.CANCELLED,
            completed_at=old_date,
        )

        # Run cleanup command
        out = StringIO()
        call_command("cleanup_workflow_state", "--archive-days=90", stdout=out)

        # Verify all terminal workflows are archived
        completed.refresh_from_db()
        failed.refresh_from_db()
        cancelled.refresh_from_db()
        self.assertTrue(completed.state_data.get("archived"))
        self.assertTrue(failed.state_data.get("archived"))
        self.assertTrue(cancelled.state_data.get("archived"))
