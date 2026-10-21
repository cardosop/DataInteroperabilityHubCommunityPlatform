"""
285.11.2.6 — Tests for pipeline dependency migrations (forward, reverse, data preserved).
"""

import uuid

import pytest
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
        name=f"Test-{slug}",
        slug=slug,
        status="ACTIVE",
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
    def test_duplicate_pipeline_dependency_rejected_under_current_constraint(self):
        """Pin the CURRENT contract (Phase T.2 triage): migration 0010
        removed ``uq_pipeline_dependency_scope``, but migration 0014
        RE-ADDED it — the old assertion ("duplicates permitted") was stale
        prose and its failure was a live-database IntegrityError, not a
        silent skip. Duplicate (pipeline, downstream) pairs raise
        IntegrityError; if the constraint is removed again deliberately,
        this test must be updated in the same change."""
        import pytest
        from django.db import IntegrityError, transaction

        tenant = _make_tenant()
        pid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        first = PipelineDependency.objects.create(
            tenant=tenant,
            pipeline_type=PipelineType.DQ,
            pipeline_id=pid,
            dependency_type=DependencyType.DATA,
            downstream_pipeline_type=PipelineType.TRANSFORMATION,
            downstream_pipeline_id=did,
        )
        # The inner atomic() creates a savepoint so the failed INSERT
        # aborts only the savepoint, not the wrapping test transaction
        # (Phase T.2: the unguarded form broke the transaction and every
        # subsequent query failed).
        with pytest.raises(IntegrityError), transaction.atomic():
            PipelineDependency.objects.create(
                tenant=tenant,
                pipeline_type=PipelineType.DQ,
                pipeline_id=pid,
                dependency_type=DependencyType.DATA,
                downstream_pipeline_type=PipelineType.TRANSFORMATION,
                downstream_pipeline_id=did,
            )
        # The duplicate must be rejected: exactly ONE row exists.
        self.assertIsNotNone(first.id)
        count = PipelineDependency.objects.filter(
            tenant=tenant,
            pipeline_type=PipelineType.DQ,
            pipeline_id=pid,
            downstream_pipeline_type=PipelineType.TRANSFORMATION,
            downstream_pipeline_id=did,
        ).count()
        self.assertEqual(count, 1)
