"""W3.6 (oss-release-remediation R2-P4/F13) — cancel checkpoints in the
workflow engine.

The evidence contract: a cancellation landing MID-RUN stops the
workflow — the remaining steps never execute and the instance ends
CANCELLED.

Why the out-of-band signal exists (the design note behind the model):
``WorkflowEngine.execute_instance`` holds a ``select_for_update`` lock
on the WorkflowInstance row for the WHOLE step loop (one transaction) —
a same-row cancel write can never commit while a run is in flight, so
no in-transaction status re-read could ever observe it.  The
``WorkflowCancellationRequest`` row is written by the cancelling side
(its own row, no lock conflict) and consumed by the engine's between-
step checkpoint (a lock-free read of the requests table).

Pins (real DB, the REAL engine — no mocks; the step tasks write and
observe real state_data):

  1. Mid-run cancel: the second step's task creates the cancellation
     request (the same write the transformation cancel endpoint
     performs) — steps 3+ never run, the instance ends CANCELLED with
     the stop point recorded, and the request is consumed.
  2. Pre-run cancel: a request placed before ``execute_instance`` stops
     the run before the FIRST step.
  3. No-request control: an identical workflow without a request runs
     every step and completes — the checkpoint costs nothing.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.orchestration.models import (
    WorkflowCancellationRequest,
    WorkflowStatus,
)
from hub.apps.orchestration.registry import WorkflowRegistry, reset_workflow_definition_cache
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class WorkflowCancelCheckpointTest(TestCase):
    """The engine's between-step checkpoints honour a cancellation
    request."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"w36 tenant {uid}",
            slug=f"w36-tenant-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"w36-{uid}@example.com", password="testpass", tenant=self.tenant
        )
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        reset_workflow_definition_cache()

        self.steps_run: list[str] = []

        def record_task(input_data, instance, step):
            # The task records its marker in the REAL state_data (the
            # engine merges task outputs after each step) and in the
            # local list (which step functions ran at all).
            self.steps_run.append(step.step_name)
            return {f"ran_{step.step_name}": True}

        self.engine.register_task("w36.record", record_task)

    def _instance(self, workflow_name: str):
        instance = self.engine.create_instance(
            workflow_name=workflow_name,
            input_data={"key": "value"},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        return self.engine.start_instance(str(instance.id))

    def _cancel_request(self, instance_id):
        return WorkflowCancellationRequest.objects.create(
            workflow_instance_id=instance_id,
            tenant_id=str(self.tenant.id),
        )

    def test_mid_run_cancel_stops_remaining_steps(self):
        """A request created by step 2 must stop steps 3+ — the
        cancel-mid-run evidence pin."""
        captured: dict = {}

        def cancelling_task(input_data, instance, step):
            captured["instance_id"] = str(instance.id)
            # The write the transformation cancel endpoint performs for
            # a RUNNING workflow instance.
            WorkflowCancellationRequest.objects.create(
                workflow_instance_id=instance.id,
                tenant_id=str(self.tenant.id),
            )
            return {"ran_cancel_requestor": True}

        self.engine.register_task("w36.request_cancel", cancelling_task)
        self.registry.register_workflow(
            workflow_name="w36_midrun",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "first", "type": "task", "task": "w36.record"},
                    {"name": "second", "type": "task", "task": "w36.request_cancel"},
                    {"name": "third", "type": "task", "task": "w36.record"},
                    {"name": "fourth", "type": "task", "task": "w36.record"},
                ],
            },
        )

        instance = self._instance("w36_midrun")
        instance = self.engine.execute_instance(str(instance.id))

        assert instance.status == WorkflowStatus.CANCELLED, (
            "a mid-run cancellation must end the instance CANCELLED"
        )
        # Only the record tasks append to steps_run — the cancelling
        # task (second) writes the request instead.  The meaningful
        # signal is that the RECORD steps after it never ran.
        assert self.steps_run == ["first"], (
            "the record steps after the cancellation request must never execute"
        )
        assert "ran_cancel_requestor" in instance.state_data, (
            "the request-writing step itself ran to completion"
        )
        assert "ran_third" not in instance.state_data
        assert "ran_fourth" not in instance.state_data
        assert not WorkflowCancellationRequest.objects.filter(
            workflow_instance_id=instance.id
        ).exists(), "the consumed request must be removed"

    def test_pre_run_cancel_stops_before_the_first_step(self):
        self.registry.register_workflow(
            workflow_name="w36_prerun",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "first", "type": "task", "task": "w36.record"},
                    {"name": "second", "type": "task", "task": "w36.record"},
                ],
            },
        )

        instance = self._instance("w36_prerun")
        self._cancel_request(instance.id)

        instance = self.engine.execute_instance(str(instance.id))

        assert instance.status == WorkflowStatus.CANCELLED
        assert self.steps_run == [], "no step may run after a pre-run cancel"
        assert not WorkflowCancellationRequest.objects.filter(
            workflow_instance_id=instance.id
        ).exists()

    def test_no_request_control_completes_every_step(self):
        self.registry.register_workflow(
            workflow_name="w36_control",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "first", "type": "task", "task": "w36.record"},
                    {"name": "second", "type": "task", "task": "w36.record"},
                ],
            },
        )

        instance = self._instance("w36_control")
        instance = self.engine.execute_instance(str(instance.id))

        assert instance.status == WorkflowStatus.COMPLETED
        assert self.steps_run == ["first", "second"]
