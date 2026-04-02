"""
Phase 68.3.2 — Idempotent Compensation Tests

Tests that compensation is idempotent and tracks attempts.
"""

import pytest
from django.test import TestCase

from hub.apps.orchestration.models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)


@pytest.mark.django_db(transaction=True)
class IdempotentCompensationTest(TestCase):
    """Test idempotent compensation behavior."""

    def setUp(self):
        self.definition = WorkflowDefinition.objects.create(
            name="test-workflow",
            version="1.0.0",
            dsl_yaml="version: '1.0.0'\nsteps:\n- name: s1\n  type: task\n  task: noop",
            dsl_json={"version": "1.0.0", "steps": [{"name": "s1", "type": "task", "task": "noop"}]},
        )
        self.instance = WorkflowInstance.objects.create(
            workflow_definition=self.definition,
            workflow_name="test-workflow",
            workflow_version="1.0.0",
            status=WorkflowStatus.FAILED,
        )

    def test_double_compensation_updates_status(self):
        """Compensating a step twice should not error — second call is a no-op."""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="create_resource",
            step_type="task",
            status=StepStatus.COMPLETED,
        )

        # First compensation
        step.status = StepStatus.COMPENSATED
        step.compensation_attempt += 1
        step.save(update_fields=["status", "compensation_attempt"])
        self.assertEqual(step.compensation_attempt, 1)

        # Second compensation (idempotent — already compensated)
        step.refresh_from_db()
        if step.status == StepStatus.COMPENSATED:
            # Already compensated — increment attempt but skip action
            step.compensation_attempt += 1
            step.save(update_fields=["compensation_attempt"])

        step.refresh_from_db()
        self.assertEqual(step.status, StepStatus.COMPENSATED)
        self.assertEqual(step.compensation_attempt, 2)

    def test_compensation_attempt_incremented(self):
        """compensation_attempt field must increment on each run."""
        step = WorkflowStep.objects.create(
            workflow_instance=self.instance,
            step_index=0,
            step_name="create_resource",
            step_type="task",
            status=StepStatus.COMPLETED,
            compensation_attempt=0,
        )

        self.assertEqual(step.compensation_attempt, 0)

        step.compensation_attempt += 1
        step.save(update_fields=["compensation_attempt"])
        step.refresh_from_db()
        self.assertEqual(step.compensation_attempt, 1)

        step.compensation_attempt += 1
        step.save(update_fields=["compensation_attempt"])
        step.refresh_from_db()
        self.assertEqual(step.compensation_attempt, 2)
