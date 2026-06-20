"""
Workflow state consistency tests under concurrency. Real engine and DB; no mocks.
"""

from concurrent.futures import ThreadPoolExecutor

from django.db import connection

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from tests.concurrency.base import WorkflowConcurrencyTestBase


class WorkflowStateManagementTest(WorkflowConcurrencyTestBase):
    """Workflow state consistency under concurrency."""

    def setUp(self):
        super().setUp()
        self.create_simple_workflow_definition("state_wf", num_steps=2)
        self.register_test_task()

    def test_workflow_state_visible_after_create(self):
        """After create_instance, state is visible to other threads."""
        instance = self.engine.create_instance(
            workflow_name="state_wf",
            input_data={"test": 1},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        self.assertEqual(instance.status, WorkflowStatus.DRAFT)

        def read_state():
            connection.ensure_connection()
            try:
                inst = WorkflowInstance.objects.filter(id=instance.id).first()
                return inst.status if inst else None
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(read_state)
            f2 = executor.submit(read_state)
            s1, s2 = f1.result(), f2.result()
        self.assertEqual(s1, WorkflowStatus.DRAFT)
        self.assertEqual(s2, WorkflowStatus.DRAFT)

    def test_concurrent_status_transitions_consistent(self):
        """Start then execute in sequence; final status is COMPLETED."""
        instance = self.engine.create_instance(
            workflow_name="state_wf",
            input_data={"test": 2},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
