"""
285.11.1.10 — Test fixtures for pipeline dependency tests.
"""
import uuid
from datetime import datetime, timezone

from hub.apps.orchestration.models import (
    DependencySource,
    DependencyType,
    PipelineDependency,
    PipelineRunDependency,
    PipelineType,
)
from hub.apps.tenants.models import Tenant


def make_tenant_with_pipelines(
    name: str = "test-tenant",
    slug: str | None = None,
) -> Tenant:
    """Create a tenant with pipeline_dependency_enabled set."""
    if slug is None:
        slug = f"t-{uuid.uuid4().hex[:8]}"
    return Tenant.objects.create(
        name=name,
        slug=slug,
        status="ACTIVE",
        pipeline_dependency_enabled=True,
    )


def make_pipeline_dependency(
    tenant: Tenant,
    pipeline_type: str = PipelineType.DQ,
    pipeline_id: str | None = None,
    downstream_pipeline_type: str = PipelineType.TRANSFORMATION,
    downstream_pipeline_id: str | None = None,
    dependency_type: str = DependencyType.DATA,
    created_by: str = DependencySource.MANUAL,
    priority: int = 0,
    is_active: bool = True,
    lineage_edge=None,
    alert_email: str | None = None,
) -> PipelineDependency:
    """Create a PipelineDependency for testing."""
    return PipelineDependency.objects.create(
        tenant=tenant,
        pipeline_type=pipeline_type,
        pipeline_id=pipeline_id or str(uuid.uuid4()),
        dependency_type=dependency_type,
        downstream_pipeline_type=downstream_pipeline_type,
        downstream_pipeline_id=downstream_pipeline_id or str(uuid.uuid4()),
        created_by=created_by,
        priority=priority,
        is_active=is_active,
        alert_email=alert_email or "",
    )


def make_pipeline_run_dependency(
    tenant: Tenant,
    pipeline_dependency: PipelineDependency,
    upstream_run_type: str = PipelineType.DQ,
    upstream_run_id: str | None = None,
    downstream_run_type: str = PipelineType.TRANSFORMATION,
    downstream_run_id: str | None = None,
    upstream_status: str = "SUCCEEDED",
) -> PipelineRunDependency:
    """Create a PipelineRunDependency for testing."""
    return PipelineRunDependency.objects.create(
        tenant=tenant,
        pipeline_dependency=pipeline_dependency,
        upstream_run_type=upstream_run_type,
        upstream_run_id=upstream_run_id or str(uuid.uuid4()),
        downstream_run_type=downstream_run_type,
        downstream_run_id=downstream_run_id or str(uuid.uuid4()),
        upstream_status=upstream_status,
    )
