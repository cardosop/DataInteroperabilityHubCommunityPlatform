"""Phase 4 (openspec add-databricks-jobs task 4.5) — the Databricks job
fleet endpoints (the API surface the U5 jobs page consumes).

- LIST JOBS — mirror-first (the 4.2 rows, ZERO network), workspace-
  scoped + tenant-scoped (RLS), paginated (the browse convention).
- LIST RUNS — nests under a job (the job_id is the Databricks-side
  string id, NOT a uuid), same mirror-first + RLS + pagination shape.

Nested under the workspace registry; gated by the workspace-registry
flag + kill switch (the 0.12 ``_gate_control_plane``); throttled per
the Phase 273 contract (tenant-scoped scope).
"""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.databricks_admin.models import DatabricksJob, DatabricksJobRun, DatabricksWorkspace
from hub.apps.databricks_admin.views import _gate_control_plane

_JOB_FIELDS = (
    "job_id",
    "name",
    "task_config",
    "schedule",
    "synced_at",
)

_RUN_FIELDS = (
    "run_id",
    "lifecycle_state",
    "result_state",
    "duration_ms",
    "error_message",
    "synced_at",
)


def _job_to_dict(row: DatabricksJob) -> dict:
    return {field: getattr(row, field) for field in _JOB_FIELDS}


def _run_to_dict(row: DatabricksJobRun) -> dict:
    return {field: getattr(row, field) for field in _RUN_FIELDS}


class DatabricksJobViewSet(viewsets.ViewSet):
    """Job-fleet reads (authenticated users, flag-gated)."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "databricks_jobs"

    def get_permissions(self):
        return [IsAuthenticated()]

    def initial(self, request, *args, **kwargs):
        _gate_control_plane(self)
        return super().initial(request, *args, **kwargs)

    def _workspace(self, request, workspace_id) -> DatabricksWorkspace:
        workspace = DatabricksWorkspace.objects.filter(
            tenant=getattr(request, "tenant", None) or getattr(request.user, "tenant", None),
            id=workspace_id,
        ).first()
        if workspace is None:
            raise NotFound()
        return workspace

    def _job(self, workspace: DatabricksWorkspace, job_id: str) -> DatabricksJob:
        row = DatabricksJob.objects.filter(workspace=workspace, job_id=job_id).first()
        if row is None:
            raise NotFound()
        return row

    # ── listings (mirror-first) ──────────────────────────────────────

    def list(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(
            DatabricksJob.objects.filter(workspace=workspace), request
        )
        return paginator.get_paginated_response(
            [_job_to_dict(row) for row in (page if page is not None else [])]
        )

    def runs(self, request, workspace_id, job_id):
        workspace = self._workspace(request, workspace_id)
        job = self._job(workspace, job_id)
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(DatabricksJobRun.objects.filter(job=job), request)
        return paginator.get_paginated_response(
            [_run_to_dict(row) for row in (page if page is not None else [])]
        )
