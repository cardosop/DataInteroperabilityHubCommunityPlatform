"""TDD pins for the Databricks job-fleet endpoints (openspec
add-databricks-jobs task 4.5) — the API surface the U5 jobs page
consumes.

Contracts pinned:
- the lists are MIRROR-FIRST (the 4.2 rows — zero network), workspace-
  scoped + tenant-scoped (RLS), and paginated;
- the runs list nests under a job (the job_id is the Databricks-side
  string id, NOT a uuid);
- a foreign tenant (or a sibling workspace of the same tenant) gets
  404, never a leak;
- the workspace-registry flag gate + kill switch + the Phase 273
  throttle scope apply.

No mocks: real Postgres mirror rows + tenants/users, real RBAC + flag
gating.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.databricks_admin.models import DatabricksJob, DatabricksJobRun
from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_sql_warehouse_views import _seed_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _seed_job(workspace, *, job_id="12345", name="nightly-etl"):
    return DatabricksJob.objects.create(
        workspace=workspace,
        job_id=job_id,
        name=name,
        task_config=[{"task_key": "ingest", "spark_sql_task": {"query": "SELECT 1"}}],
        schedule={"quartz_cron_expression": "0 0 3 * * ?", "timezone_id": "UTC"},
    )


def _seed_run(job, *, run_id="67890", lifecycle_state="TERMINATED", result_state="SUCCESS"):
    return DatabricksJobRun.objects.create(
        job=job,
        run_id=run_id,
        lifecycle_state=lifecycle_state,
        result_state=result_state,
        duration_ms=45000,
    )


def _jobs_url(workspace_id, tail=""):
    return f"/api/v1/databricks/workspaces/{workspace_id}/jobs/{tail}"


def _client(user):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


class DatabricksJobEndpointTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_user(self.tenant, f"jobs-ep-{uuid.uuid4().hex[:8]}@test.com")
        self.workspace = _seed_workspace(self.tenant, name="ws-jobs")

    def test_jobs_list_returns_the_tenant_mirror_rows_paginated(self):
        _seed_job(self.workspace, job_id="12345", name="nightly-etl")
        _seed_job(self.workspace, job_id="23456", name="ad-hoc")

        response = _client(self.admin).get(_jobs_url(self.workspace.id))
        assert response.status_code == 200, response.content
        rows = {row["job_id"]: row for row in response.json()["results"]}
        assert set(rows) == {"12345", "23456"}
        assert rows["12345"]["name"] == "nightly-etl"
        assert rows["12345"]["task_config"] == [
            {"task_key": "ingest", "spark_sql_task": {"query": "SELECT 1"}}
        ]
        assert rows["12345"]["schedule"] == {
            "quartz_cron_expression": "0 0 3 * * ?",
            "timezone_id": "UTC",
        }
        assert "synced_at" in rows["12345"]

    def test_runs_list_nests_under_the_job(self):
        job = _seed_job(self.workspace)
        _seed_run(job)
        _seed_run(job, run_id="88888", lifecycle_state="RUNNING", result_state=None)

        response = _client(self.admin).get(_jobs_url(self.workspace.id, f"{job.job_id}/runs/"))
        assert response.status_code == 200, response.content
        rows = {row["run_id"]: row for row in response.json()["results"]}
        assert set(rows) == {"67890", "88888"}
        assert rows["67890"]["lifecycle_state"] == "TERMINATED"
        assert rows["67890"]["result_state"] == "SUCCESS"
        assert rows["67890"]["duration_ms"] == 45000
        assert rows["88888"]["result_state"] is None

    def test_an_unknown_job_id_404s(self):
        _seed_job(self.workspace)
        response = _client(self.admin).get(_jobs_url(self.workspace.id, "99999/runs/"))
        assert response.status_code == 404

    def test_lists_are_tenant_and_workspace_scoped(self):
        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        foreign_workspace = _seed_workspace(other_tenant, name="ws-foreign")
        _seed_job(foreign_workspace)

        foreign_admin = _make_user(other_tenant, f"jobs-foreign-{uuid.uuid4().hex[:8]}@test.com")
        assert _client(foreign_admin).get(_jobs_url(self.workspace.id)).status_code == 404
        assert _client(self.admin).get(_jobs_url(foreign_workspace.id)).status_code == 404

        # A sibling workspace surfaces ONLY its own mirror rows — the
        # other workspace's jobs never bleed across.
        sibling = _seed_workspace(self.tenant, name="ws-sibling")
        _seed_job(sibling, job_id="77777")
        response = _client(self.admin).get(_jobs_url(sibling.id))
        assert response.status_code == 200, response.content
        assert [row["job_id"] for row in response.json()["results"]] == ["77777"]

    def test_the_control_plane_flag_and_kill_switch_gate(self):
        self.tenant.databricks_control_plane_enabled = False
        self.tenant.save(update_fields=["databricks_control_plane_enabled"])
        response = _client(self.admin).get(_jobs_url(self.workspace.id))
        assert response.status_code == 403, response.content

        self.tenant.databricks_control_plane_enabled = True
        self.tenant.databricks_workspaces_kill_switch = True
        self.tenant.save(
            update_fields=["databricks_control_plane_enabled", "databricks_workspaces_kill_switch"]
        )
        response = _client(self.admin).get(_jobs_url(self.workspace.id))
        assert response.status_code == 403, response.content

    def test_the_phase_273_throttle_scope_applies(self):
        from hub.apps.databricks_admin.job_views import DatabricksJobViewSet

        assert DatabricksJobViewSet.throttle_scope == "databricks_jobs"
        assert DatabricksJobViewSet.throttle_classes

    def test_unauthenticated_requests_are_refused(self):
        response = _client(None).get(_jobs_url(self.workspace.id))
        assert response.status_code == 401
