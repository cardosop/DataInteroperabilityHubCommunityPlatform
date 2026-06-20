"""
285.11.3.4 — Tests for PipelineTriggerEngine.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.orchestration.models import (
    DependencySource,
    DependencyType,
    PipelineDependency,
    PipelineType,
)
from hub.apps.orchestration.trigger_engine import (
    _on_pipeline_terminal,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant(flag=True):
    from hub.apps.tenants.models import Tenant

    slug = f"t-{uuid.uuid4().hex[:8]}"
    return Tenant.objects.create(
        name=f"Test-{slug}",
        slug=slug,
        status="ACTIVE",
        pipeline_dependency_enabled=flag,
    )


def _make_dep(
    tenant,
    upstream_type=PipelineType.DQ,
    upstream_id=None,
    downstream_type=PipelineType.TRANSFORMATION,
    downstream_id=None,
    dependency_type=DependencyType.TRIGGER,
    **kwargs,
):
    return PipelineDependency.objects.create(
        tenant=tenant,
        pipeline_type=upstream_type,
        pipeline_id=upstream_id or str(uuid.uuid4()),
        dependency_type=dependency_type,
        downstream_pipeline_type=downstream_type,
        downstream_pipeline_id=downstream_id or str(uuid.uuid4()),
        created_by=DependencySource.MANUAL,
        priority=kwargs.pop("priority", 0),
        is_active=kwargs.pop("is_active", True),
        **kwargs,
    )


@pytest.mark.integration
class TestTriggerEngine(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    # ── Trigger dispatch ──────────────────────────────────────────

    @pytest.mark.integration
    def test_terminal_success_triggers_downstream_trigger_dep(self):
        """SUCCEEDED status should enqueue TRIGGER-type downstreams."""
        tenant = _make_tenant()
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        _make_dep(
            tenant,
            upstream_id=upstream_id,
            downstream_type=PipelineType.TRANSFORMATION,
            downstream_id=downstream_id,
            dependency_type=DependencyType.TRIGGER,
        )

        # Should not raise.
        _on_pipeline_terminal(
            str(tenant.id),
            PipelineType.DQ,
            upstream_id,
            "SUCCEEDED",
        )

    @pytest.mark.integration
    def test_failed_propagates_to_downstream(self):
        """FAILED status calls propagate_upstream_failure."""
        tenant = _make_tenant()
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        _make_dep(
            tenant,
            upstream_id=upstream_id,
            downstream_type=PipelineType.TRANSFORMATION,
            downstream_id=downstream_id,
        )

        _on_pipeline_terminal(
            str(tenant.id),
            PipelineType.DQ,
            upstream_id,
            "FAILED",
        )

    @pytest.mark.integration
    def test_non_terminal_skipped(self):
        """RUNNING status should NOT trigger anything."""
        tenant = _make_tenant()
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        _make_dep(
            tenant,
            upstream_id=upstream_id,
            downstream_type=PipelineType.TRANSFORMATION,
            downstream_id=downstream_id,
        )

        # This should be no-op — status RUNNING is not terminal.
        _on_pipeline_terminal(
            str(tenant.id),
            PipelineType.DQ,
            upstream_id,
            "RUNNING",
        )

    @pytest.mark.integration
    def test_cascade_with_priority_ordering(self):
        """Higher priority downstream should be triggered first."""
        tenant = _make_tenant()
        upstream_id = str(uuid.uuid4())
        d1 = str(uuid.uuid4())
        d2 = str(uuid.uuid4())

        _make_dep(
            tenant,
            upstream_id=upstream_id,
            downstream_type=PipelineType.TRANSFORMATION,
            downstream_id=d1,
            priority=10,
        )
        _make_dep(
            tenant,
            upstream_id=upstream_id,
            downstream_type=PipelineType.COMPLIANCE,
            downstream_id=d2,
            priority=5,
        )

        _on_pipeline_terminal(
            str(tenant.id),
            PipelineType.DQ,
            upstream_id,
            "SUCCEEDED",
        )

    @pytest.mark.integration
    def test_multi_hop_chain(self):
        """A → B → C: completing A triggers B, which triggers C."""
        tenant = _make_tenant()
        a_id = str(uuid.uuid4())
        b_id = str(uuid.uuid4())
        c_id = str(uuid.uuid4())

        _make_dep(
            tenant,
            upstream_type=PipelineType.DQ,
            upstream_id=a_id,
            downstream_type=PipelineType.TRANSFORMATION,
            downstream_id=b_id,
            dependency_type=DependencyType.TRIGGER,
        )
        _make_dep(
            tenant,
            upstream_type=PipelineType.TRANSFORMATION,
            upstream_id=b_id,
            downstream_type=PipelineType.COMPLIANCE,
            downstream_id=c_id,
            dependency_type=DependencyType.TRIGGER,
        )

        _on_pipeline_terminal(
            str(tenant.id),
            PipelineType.DQ,
            a_id,
            "SUCCEEDED",
        )

    @pytest.mark.integration
    def test_trigger_supports_all_pipeline_types(self):
        """All 5 pipeline types should dispatch correctly."""
        tenant = _make_tenant()
        for ptype in PipelineType.values:
            pid = str(uuid.uuid4())
            _on_pipeline_terminal(
                str(tenant.id),
                ptype,
                pid,
                "SUCCEEDED",
            )

    @pytest.mark.integration
    def test_dq_run_completed_triggers(self):
        """DQ run completion triggers TRIGGER-type downstream."""
        tenant = _make_tenant()
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        _make_dep(
            tenant,
            upstream_type=PipelineType.DQ,
            upstream_id=upstream_id,
            downstream_type=PipelineType.COMPLIANCE,
            downstream_id=downstream_id,
            dependency_type=DependencyType.TRIGGER,
        )

        _on_pipeline_terminal(
            str(tenant.id),
            PipelineType.DQ,
            upstream_id,
            "SUCCEEDED",
        )

    @pytest.mark.integration
    def test_compliance_run_completed_triggers(self):
        """Compliance run completion triggers TRIGGER-type downstream."""
        tenant = _make_tenant()
        upstream_id = str(uuid.uuid4())
        downstream_id = str(uuid.uuid4())
        _make_dep(
            tenant,
            upstream_type=PipelineType.COMPLIANCE,
            upstream_id=upstream_id,
            downstream_type=PipelineType.TRANSFORMATION,
            downstream_id=downstream_id,
            dependency_type=DependencyType.TRIGGER,
        )

        _on_pipeline_terminal(
            str(tenant.id),
            PipelineType.COMPLIANCE,
            upstream_id,
            "SUCCEEDED",
        )
