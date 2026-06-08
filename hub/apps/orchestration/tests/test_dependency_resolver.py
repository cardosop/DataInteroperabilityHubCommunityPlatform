"""
285.11.2.6 — Tests for PipelineDependencyResolver.
"""
import pytest

import uuid

from django.test import TestCase

from hub.apps.orchestration.dependency_resolver import (
    CycleDetectedError,
    PipelineDependencyResolver,
    invalidate_pipeline_dependency_cache,
)
from hub.apps.orchestration.models import (
    DependencySource,
    DependencyType,
    PipelineDependency,
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


def _make_dep(tenant, upstream_type=PipelineType.DQ, upstream_id=None,
              downstream_type=PipelineType.TRANSFORMATION, downstream_id=None,
              **kwargs):
    return PipelineDependency.objects.create(
        tenant=tenant,
        pipeline_type=upstream_type,
        pipeline_id=upstream_id or str(uuid.uuid4()),
        dependency_type=kwargs.pop("dependency_type", DependencyType.DATA),
        downstream_pipeline_type=downstream_type,
        downstream_pipeline_id=downstream_id or str(uuid.uuid4()),
        created_by=kwargs.pop("created_by", DependencySource.MANUAL),
        priority=kwargs.pop("priority", 0),
        is_active=kwargs.pop("is_active", True),
        **kwargs,
    )


@pytest.mark.integration
class TestPipelineDependencyResolver(TestCase):
    """285.11.2.6 — resolver unit tests."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.resolver = PipelineDependencyResolver(str(self.tenant.id))

    # ── resolve_upstream ──────────────────────────────────────────

    @pytest.mark.integration
    def test_resolve_upstream_empty(self):
        result = self.resolver.resolve_upstream("dq", str(uuid.uuid4()))
        self.assertEqual(result, [])

    @pytest.mark.integration
    def test_resolve_upstream_finds_active(self):
        downstream_id = str(uuid.uuid4())
        upstream_id = str(uuid.uuid4())
        dep = _make_dep(self.tenant, upstream_id=upstream_id,
                        downstream_type=PipelineType.DQ,
                        downstream_id=downstream_id)
        result = self.resolver.resolve_upstream(PipelineType.DQ, downstream_id)
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result[0].id), str(dep.id))

    @pytest.mark.integration
    def test_resolve_upstream_skips_inactive(self):
        downstream_id = str(uuid.uuid4())
        _make_dep(self.tenant,
                  downstream_type=PipelineType.DQ,
                  downstream_id=downstream_id,
                  is_active=False)
        result = self.resolver.resolve_upstream(PipelineType.DQ, downstream_id)
        self.assertEqual(len(result), 0)

    # ── resolve_downstream ────────────────────────────────────────

    @pytest.mark.integration
    def test_resolve_downstream_finds_active(self):
        upstream_id = str(uuid.uuid4())
        _make_dep(self.tenant, upstream_id=upstream_id)
        result = self.resolver.resolve_downstream(PipelineType.DQ, upstream_id)
        self.assertEqual(len(result), 1)

    # ── are_dependencies_met ──────────────────────────────────────

    @pytest.mark.integration
    def test_are_dependencies_met_no_deps(self):
        self.assertTrue(
            self.resolver.are_dependencies_met("dq", str(uuid.uuid4()), {})
        )

    @pytest.mark.integration
    def test_are_dependencies_met_all_succeeded(self):
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        _make_dep(self.tenant, upstream_id=upstream_id,
                  downstream_type=PipelineType.DQ,
                  downstream_id=downstream_id)
        statuses = {(PipelineType.DQ, upstream_id): "SUCCEEDED"}
        self.assertTrue(
            self.resolver.are_dependencies_met(
                PipelineType.DQ, downstream_id, statuses,
            )
        )

    @pytest.mark.integration
    def test_are_dependencies_met_missing_status(self):
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        _make_dep(self.tenant, upstream_id=upstream_id,
                  downstream_type=PipelineType.DQ,
                  downstream_id=downstream_id)
        self.assertFalse(
            self.resolver.are_dependencies_met(
                PipelineType.DQ, downstream_id, {},
            )
        )

    # ── validate_no_cycles ────────────────────────────────────────

    @pytest.mark.integration
    def test_validate_no_cycles_empty_graph(self):
        self.resolver.validate_no_cycles()  # should not raise

    @pytest.mark.integration
    def test_validate_no_cycles_dag(self):
        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        _make_dep(self.tenant, upstream_type=PipelineType.DQ, upstream_id=a,
                  downstream_type=PipelineType.TRANSFORMATION, downstream_id=b)
        self.resolver.validate_no_cycles()

    @pytest.mark.integration
    def test_validate_no_cycles_detects_cycle(self):
        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        _make_dep(self.tenant, upstream_type=PipelineType.DQ, upstream_id=a,
                  downstream_type=PipelineType.COMPLIANCE, downstream_id=b)
        _make_dep(self.tenant, upstream_type=PipelineType.COMPLIANCE, upstream_id=b,
                  downstream_type=PipelineType.DQ, downstream_id=a)
        with self.assertRaises(CycleDetectedError):
            self.resolver.validate_no_cycles()

    # ── build_execution_graph ──────────────────────────────────────

    @pytest.mark.integration
    def test_build_execution_graph_single_level(self):
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        _make_dep(self.tenant, upstream_id=upstream_id,
                  downstream_type=PipelineType.DQ,
                  downstream_id=downstream_id,
                  priority=5)
        graph = self.resolver.build_execution_graph(
            PipelineType.DQ, downstream_id,
        )
        self.assertTrue(graph["cycle_free"])
        self.assertEqual(len(graph["dependencies"]), 1)
        self.assertEqual(graph["dependencies"][0]["priority"], 5)
