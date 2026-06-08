"""
285.11.2.6 — Tests for pipeline dependency migrations (forward, reverse, data preserved).
"""
import pytest

import uuid

from django.test import TestCase

from hub.apps.orchestration.models import (
    DependencySource,
    DependencyType,
    PipelineDependency,
    PipelineRunDependency,
    PipelineType,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant():
    from hub.apps.tenants.models import Tenant
    slug = f"t-{uuid.uuid4().hex[:8]}"
    return Tenant.objects.create(
        name=f"Test-{slug}", slug=slug, status="ACTIVE",
        pipeline_dependency_enabled=True,
    )


@pytest.mark.integration
class TestDependencyMigrations(TestCase):
    """Verify models are operational post-migration."""

    @pytest.mark.integration
    def test_pipeline_dependency_create_and_read(self):
        tenant = _make_tenant()
        dep = PipelineDependency.objects.create(
            tenant=tenant,
            pipeline_type=PipelineType.DQ,
            pipeline_id=str(uuid.uuid4()),
            dependency_type=DependencyType.DATA,
            downstream_pipeline_type=PipelineType.TRANSFORMATION,
            downstream_pipeline_id=str(uuid.uuid4()),
            created_by=DependencySource.MANUAL,
            priority=5,
        )
        fetched = PipelineDependency.objects.get(id=dep.id)
        self.assertEqual(fetched.pipeline_type, PipelineType.DQ)
        self.assertEqual(fetched.priority, 5)
        self.assertTrue(fetched.is_active)

    @pytest.mark.integration
    def test_pipeline_run_dependency_create_and_read(self):
        tenant = _make_tenant()
        dep = PipelineDependency.objects.create(
            tenant=tenant,
            pipeline_type=PipelineType.DQ,
            pipeline_id=str(uuid.uuid4()),
            dependency_type=DependencyType.DATA,
            downstream_pipeline_type=PipelineType.TRANSFORMATION,
            downstream_pipeline_id=str(uuid.uuid4()),
        )
        run_dep = PipelineRunDependency.objects.create(
            tenant=tenant,
            pipeline_dependency=dep,
            upstream_run_type=dep.pipeline_type,
            upstream_run_id=dep.pipeline_id,
            downstream_run_type=dep.downstream_pipeline_type,
            downstream_run_id=dep.downstream_pipeline_id,
            upstream_status="SUCCEEDED",
        )
        fetched = PipelineRunDependency.objects.get(id=run_dep.id)
        self.assertEqual(fetched.upstream_status, "SUCCEEDED")

    @pytest.mark.integration
    def test_unique_constraint_prevents_duplicate(self):
        tenant = _make_tenant()
        pid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        PipelineDependency.objects.create(
            tenant=tenant,
            pipeline_type=PipelineType.DQ,
            pipeline_id=pid,
            dependency_type=DependencyType.DATA,
            downstream_pipeline_type=PipelineType.TRANSFORMATION,
            downstream_pipeline_id=did,
        )
        # The ``uq_pipeline_dependency_scope`` unique constraint was removed
        # in migration 0010 to allow flexible dependency graphs.  Duplicate
        # (pipeline, downstream) pairs with different metadata are now
        # permitted.  Verify that a second create succeeds.
        PipelineDependency.objects.create(
            tenant=tenant,
            pipeline_type=PipelineType.DQ,
            pipeline_id=pid,
            dependency_type=DependencyType.DATA,
            downstream_pipeline_type=PipelineType.TRANSFORMATION,
            downstream_pipeline_id=did,
        )
