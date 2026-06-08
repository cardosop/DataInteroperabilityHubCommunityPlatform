"""
285.11.2.6 — Tests for DependencyAwareExecutor enforcement.
"""
import pytest

import uuid

from django.test import TestCase

from hub.apps.orchestration.dependency_executor import (
    DependencyAwareExecutor,
    handle_upstream_completed,
)
from hub.apps.orchestration.models import (
    DependencySource,
    DependencyType,
    PipelineDependency,
    PipelineType,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant(flag=True):
    from hub.apps.tenants.models import Tenant
    slug = f"t-{uuid.uuid4().hex[:8]}"
    return Tenant.objects.create(
        name=f"Test-{slug}", slug=slug, status="ACTIVE",
        pipeline_dependency_enabled=flag,
    )


@pytest.mark.integration
class TestDependencyEnforcement(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @pytest.mark.integration
    def test_enqueue_flag_disabled_passthrough(self):
        """When flag is off, enqueue_fn is called directly."""
        tenant = _make_tenant(flag=False)
        executor = DependencyAwareExecutor(str(tenant.id))
        called = []

        result = executor.enqueue_with_dependency_check(
            "dq", str(uuid.uuid4()),
            enqueue_fn=lambda: called.append(True) or {"status": "enqueued"},
        )
        self.assertTrue(called)
        self.assertEqual(result["status"], "enqueued")

    @pytest.mark.integration
    def test_enqueue_no_deps_proceeds(self):
        tenant = _make_tenant()
        executor = DependencyAwareExecutor(str(tenant.id))
        called = []

        result = executor.enqueue_with_dependency_check(
            "dq", str(uuid.uuid4()),
            enqueue_fn=lambda: called.append(True) or {"status": "RUNNING"},
        )
        self.assertTrue(called)
        self.assertEqual(result["status"], "RUNNING")

    @pytest.mark.integration
    def test_enqueue_deps_not_met_returns_pending(self):
        tenant = _make_tenant()
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        PipelineDependency.objects.create(
            tenant=tenant,
            pipeline_type=PipelineType.DQ,
            pipeline_id=upstream_id,
            dependency_type=DependencyType.DATA,
            downstream_pipeline_type=PipelineType.TRANSFORMATION,
            downstream_pipeline_id=downstream_id,
            created_by=DependencySource.MANUAL,
        )

        executor = DependencyAwareExecutor(str(tenant.id))
        called = []

        result = executor.enqueue_with_dependency_check(
            PipelineType.TRANSFORMATION, downstream_id,
            enqueue_fn=lambda: called.append(True) or {},
            resolve_upstream_statuses={},
        )
        self.assertFalse(called)
        self.assertEqual(result["status"], "PENDING_DEPENDENCY")
        self.assertGreater(len(result["waiting_on"]), 0)

    @pytest.mark.integration
    def test_handle_upstream_completed_triggers_downstream(self):
        tenant = _make_tenant()
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        PipelineDependency.objects.create(
            tenant=tenant,
            pipeline_type=PipelineType.DQ,
            pipeline_id=upstream_id,
            dependency_type=DependencyType.DATA,
            downstream_pipeline_type=PipelineType.TRANSFORMATION,
            downstream_pipeline_id=downstream_id,
            created_by=DependencySource.MANUAL,
        )

        count = handle_upstream_completed(
            str(tenant.id), PipelineType.DQ,
            upstream_id, upstream_id, "SUCCEEDED",
        )
        self.assertEqual(count, 1)

    @pytest.mark.integration
    def test_handle_upstream_failed_propagates(self):
        tenant = _make_tenant()
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        PipelineDependency.objects.create(
            tenant=tenant,
            pipeline_type=PipelineType.DQ,
            pipeline_id=upstream_id,
            dependency_type=DependencyType.DATA,
            downstream_pipeline_type=PipelineType.TRANSFORMATION,
            downstream_pipeline_id=downstream_id,
            created_by=DependencySource.MANUAL,
        )

        count = handle_upstream_completed(
            str(tenant.id), PipelineType.DQ,
            upstream_id, upstream_id, "FAILED",
        )
        self.assertEqual(count, 1)
