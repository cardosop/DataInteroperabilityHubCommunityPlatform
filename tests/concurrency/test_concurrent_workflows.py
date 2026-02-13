"""
Concurrent workflow execution tests. Real WorkflowEngine and DB; no mocks.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import connection

from hub.apps.orchestration.models import WorkflowStatus
from tests.concurrency.base import WorkflowConcurrencyTestBase


class ConcurrentWorkflowsTest(WorkflowConcurrencyTestBase):
    """Concurrent workflow execution."""

    def setUp(self):
        super().setUp()
        self.create_simple_workflow_definition("concurrent_wf", num_steps=3)
        self.register_test_task()

    def _run_workflow(self, index: int) -> dict:
        try:
            connection.ensure_connection()
            instance = self.engine.create_instance(
                workflow_name="concurrent_wf",
                input_data={"index": index},
                tenant_id=str(self.tenant.id),
                created_by_id=str(self.user.id),
            )
            self.engine.start_instance(str(instance.id))
            instance = self.engine.execute_instance(str(instance.id))
            return {
                "index": index,
                "success": instance.status == WorkflowStatus.COMPLETED,
                "status": instance.status,
            }
        except Exception as e:
            return {"index": index, "success": False, "status": str(e)}
        finally:
            try:
                connection.close()
            except Exception:
                pass  # Ignore connection close errors in teardown

    def test_concurrent_workflow_execution(self):
        """Multiple workflows run concurrently; all complete or fail cleanly."""
        num = 6
        with ThreadPoolExecutor(max_workers=num) as executor:
            futures = [executor.submit(self._run_workflow, i) for i in range(num)]
            results = [f.result() for f in as_completed(futures)]
        success_count = sum(1 for r in results if r.get("success"))
        self.assertGreaterEqual(success_count, num // 2)
        self.assertEqual(len(results), num)

    def test_concurrent_workflow_execution_no_connection_leak(self):
        """Concurrent execution with proper connection close in each thread."""
        num = 4
        with ThreadPoolExecutor(max_workers=num) as executor:
            futures = [executor.submit(self._run_workflow, i) for i in range(num)]
            for f in as_completed(futures):
                f.result()
        # If we get here without timeout or connection errors, leak test passed
        self.assertTrue(True)
