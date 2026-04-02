"""
Phase 68.3.1 — Workflow Auto-Retry Tests

Tests the recover_failed_workflows management command.
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)


@pytest.mark.django_db(transaction=True)
class WorkflowAutoRetryTest(TestCase):
    """Test recover_failed_workflows management command."""

    def setUp(self):
        self.definition = WorkflowDefinition.objects.create(
            name="test-workflow",
            version="1.0.0",
            dsl_yaml="version: '1.0.0'\nsteps:\n- name: s1\n  type: task\n  task: noop",
            dsl_json={"version": "1.0.0", "steps": [{"name": "s1", "type": "task", "task": "noop"}]},
        )

    def _create_instance(self, status, retry_count=0, max_retries=3,
                         minutes_ago=30):
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.definition,
            workflow_name="test-workflow",
            workflow_version="1.0.0",
            status=status,
            retry_count=retry_count,
            max_retries=max_retries,
        )
        # Bypass auto_now to set updated_at in the past
        past = timezone.now() - timedelta(minutes=minutes_ago)
        WorkflowInstance.objects.filter(id=instance.id).update(updated_at=past)
        instance.refresh_from_db()
        return instance

    def test_failed_workflow_retried_when_under_max_retries(self):
        """FAILED + retry_count < max_retries → status DRAFT, retry_count+1."""
        instance = self._create_instance(
            WorkflowStatus.FAILED, retry_count=0, max_retries=3,
        )
        out = StringIO()
        call_command("recover_failed_workflows", stdout=out)

        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowStatus.DRAFT)
        self.assertEqual(instance.retry_count, 1)

    def test_failed_workflow_not_retried_when_at_max(self):
        """retry_count == max_retries → status unchanged."""
        instance = self._create_instance(
            WorkflowStatus.FAILED, retry_count=3, max_retries=3,
        )
        out = StringIO()
        call_command("recover_failed_workflows", stdout=out)

        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowStatus.FAILED)
        self.assertEqual(instance.retry_count, 3)

    def test_compensation_incomplete_re_runs(self):
        """COMPENSATION_INCOMPLETE with no failed step → rolled back."""
        instance = self._create_instance(
            WorkflowStatus.COMPENSATION_INCOMPLETE,
            retry_count=0, max_retries=3,
        )
        # Set error_details and re-backdate updated_at (save resets auto_now)
        WorkflowInstance.objects.filter(id=instance.id).update(
            error_details={"compensation_failures": ["step1"]},
            updated_at=timezone.now() - timedelta(minutes=30),
        )
        instance.refresh_from_db()

        out = StringIO()
        call_command("recover_failed_workflows", stdout=out)

        instance.refresh_from_db()
        # No actual failed step → command sets ROLLED_BACK
        self.assertEqual(instance.status, WorkflowStatus.ROLLED_BACK)

    def test_recently_failed_workflow_skipped(self):
        """updated_at < 15 min ago → skipped (cooldown)."""
        instance = self._create_instance(
            WorkflowStatus.FAILED, retry_count=0, max_retries=3,
            minutes_ago=5,  # Only 5 min ago — within cooldown
        )
        out = StringIO()
        call_command("recover_failed_workflows", stdout=out)

        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowStatus.FAILED)
        self.assertEqual(instance.retry_count, 0)
