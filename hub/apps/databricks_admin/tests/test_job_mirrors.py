"""TDD pins for the Databricks job/run mirror (openspec
add-databricks-jobs task 4.2) — the `DatabricksJob`/`DatabricksJobRun`
models (indirect-FK RLS) + the live registry sync.

The mirror is a READ cache of the Databricks-owned state: the sync maps
the jobs API's reported job/run payloads into tenant-scoped rows and
never invents one. No mocks: real Postgres rows + RLS (policy scans +
a runtime probe through the 1.12 helper), the PRODUCTION client against
a REAL local HTTP server for the sync, and the UC-sync pagination
conventions (``next_page_token`` chains with the repeating-token guard).
"""

import json
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _job_payload(job_id="12345", name="nightly-etl", tasks=None, schedule=True):
    """A jobs/list item the way the 2.1 API reports it."""
    settings = {"name": name}
    if tasks is not None:
        settings["tasks"] = tasks
    else:
        settings["tasks"] = [{"task_key": "ingest", "spark_sql_task": {"query": "SELECT 1"}}]
    if schedule is True:
        settings["schedule"] = {
            "quartz_cron_expression": "0 0 3 * * ?",
            "timezone_id": "UTC",
        }
    elif schedule:
        # An explicit non-True value passes through verbatim (a string
        # schedule exercises the sync's malformed-shape guard).
        settings["schedule"] = schedule
    return {"job_id": job_id, "settings": settings}


def _run_payload(
    run_id="67890",
    job_id="12345",
    life_cycle_state="TERMINATED",
    result_state="SUCCESS",
    duration_ms=45000,
    state_message="",
):
    """A runs/list item the way the 2.1 API reports it."""
    return {
        "run_id": run_id,
        "job_id": job_id,
        "state": {
            "life_cycle_state": life_cycle_state,
            "result_state": result_state,
            "state_message": state_message,
        },
        "run_duration": duration_ms,
    }


def _client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id="t1",
        credential_config={"token": "dapi-jobs"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
    )


class TestDatabricksJobModel(TestCase):
    """The job mirror: identity, uniqueness, cascade, RLS."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant)

    def _make(self, job_id="12345", **overrides):
        from hub.apps.databricks_admin.models import DatabricksJob

        fields = {"workspace": self.workspace, "job_id": job_id, "name": "nightly-etl"}
        fields.update(overrides)
        return DatabricksJob.objects.create(**fields)

    def test_unique_per_workspace_by_job_id(self):
        from django.core.exceptions import ValidationError

        self._make()
        # The model's full_clean surfaces duplicates as clean
        # ValidationErrors (the 0.8 name-conflict pattern) before the
        # DB constraint ever fires.
        with pytest.raises(ValidationError):
            self._make()  # same job_id → the (workspace, job_id) uniqueness
        # The SAME job id on a SIBLING workspace is a distinct row.
        from hub.apps.databricks_admin.models import DatabricksJob

        sibling = _make_workspace(self.tenant, name="ws-sibling")
        assert DatabricksJob.objects.create(workspace=sibling, job_id="12345", name="nightly-etl")

    def test_job_id_and_name_are_required(self):
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            self._make(job_id="")
        with pytest.raises(ValidationError):
            self._make(name="")

    def test_task_config_and_schedule_defaults(self):
        row = self._make()
        assert row.task_config == []
        assert row.schedule is None
        row = self._make(job_id="23456", task_config=[{"task_key": "t"}], schedule={"cron": "x"})
        assert row.task_config == [{"task_key": "t"}]
        assert row.schedule == {"cron": "x"}

    def test_workspace_delete_cascades_the_job_mirror(self):
        from hub.apps.databricks_admin.models import DatabricksJob

        row = self._make()
        self.workspace.delete()
        assert not DatabricksJob.objects.filter(pk=row.pk).exists()

    def test_rls_policy_ships_for_the_jobs_table(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT policyname FROM pg_policies WHERE tablename = 'databricks_jobs'")
            policies = [row[0] for row in cursor.fetchall()]
        assert policies, "the jobs mirror table must ship a paired RLS policy"


class TestDatabricksJobRunModel(TestCase):
    """The run mirror: identity, the reported-state vocabularies, cascade."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant)
        from hub.apps.databricks_admin.models import DatabricksJob

        self.job = DatabricksJob.objects.create(
            workspace=self.workspace, job_id="12345", name="nightly-etl"
        )

    def _make(self, run_id="67890", **overrides):
        from hub.apps.databricks_admin.models import DatabricksJobRun

        fields = {
            "job": self.job,
            "run_id": run_id,
            "lifecycle_state": "TERMINATED",
            "result_state": "SUCCESS",
            "duration_ms": 45000,
        }
        fields.update(overrides)
        return DatabricksJobRun.objects.create(**fields)

    def test_unique_per_job_by_run_id(self):
        from django.core.exceptions import ValidationError

        self._make()
        with pytest.raises(ValidationError):
            self._make()  # same run_id on the same job → the (job, run_id) uniqueness

    def test_lifecycle_states_are_the_reported_vocabulary(self):
        from django.core.exceptions import ValidationError

        for state in (
            "PENDING",
            "QUEUED",
            "RUNNING",
            "TERMINATING",
            "TERMINATED",
            "SKIPPED",
            "INTERNAL_ERROR",
            "WAITING_FOR_RETRY",
            "BLOCKED",
        ):
            row = self._make(run_id=f"r-{state}", lifecycle_state=state, result_state=None)
            assert row.lifecycle_state == state
        with pytest.raises(ValidationError):
            self._make(run_id="r-bogus", lifecycle_state="WARPING", result_state=None)

    def test_result_state_is_constrained_and_nullable_pre_terminal(self):
        from django.core.exceptions import ValidationError

        for state in (
            "SUCCESS",
            "FAILED",
            "TIMEDOUT",
            "CANCELED",
            "MAXIMUM_CONCURRENT_RUNS_REACHED",
            "EXCLUDED",
            "SUCCESS_WITH_FAILURES",
            "UPSTREAM_FAILED",
            "UPSTREAM_CANCELED",
        ):
            row = self._make(run_id=f"r-{state}", result_state=state)
            assert row.result_state == state
        # A RUNNING run carries NO result state yet — that is the API's
        # own shape, never invented into one.
        row = self._make(run_id="r-running", lifecycle_state="RUNNING", result_state=None)
        assert row.result_state is None
        with pytest.raises(ValidationError):
            self._make(run_id="r-bad-result", result_state="SORTA_DONE")

    def test_job_delete_cascades_its_runs(self):
        from hub.apps.databricks_admin.models import DatabricksJobRun

        row = self._make()
        self.job.delete()
        assert not DatabricksJobRun.objects.filter(pk=row.pk).exists()

    def test_rls_policy_ships_for_the_runs_table(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT policyname FROM pg_policies WHERE tablename = 'databricks_job_runs'"
            )
            policies = [row[0] for row in cursor.fetchall()]
        assert policies, "the job runs mirror table must ship a paired RLS policy"


class TestJobMirrorRuntimeRLS(TestCase):
    """The indirect-FK policies FILTER at runtime, not just exist."""

    def setUp(self):
        require_dns()
        self.tenant_a = TenantFactory.create_tenant()
        _activate_billing(self.tenant_a)
        self.tenant_b = TenantFactory.create_tenant()
        _activate_billing(self.tenant_b)
        self.workspace = _make_workspace(self.tenant_a, name=f"ws-jobs-{uuid.uuid4().hex[:8]}")
        from hub.apps.databricks_admin.models import DatabricksJob, DatabricksJobRun

        self.job = DatabricksJob.objects.create(
            workspace=self.workspace, job_id="12345", name="nightly-etl"
        )
        DatabricksJobRun.objects.create(
            job=self.job,
            run_id="67890",
            lifecycle_state="TERMINATED",
            result_state="SUCCESS",
            duration_ms=45000,
        )

    def _probe_role(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import (
            _connection_bypasses_rls,
            _ensure_rls_probe_role,
        )

        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            return "hub_rls_probe"
        return None

    def test_job_rows_are_hidden_from_foreign_tenants(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import _visible_count_as

        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, "databricks_jobs") == 1
        assert _visible_count_as(probe, self.tenant_b.id, "databricks_jobs") == 0, (
            "tenant B must see ZERO of tenant A's jobs (RLS runtime enforcement)"
        )

    def test_run_rows_are_hidden_from_foreign_tenants(self):
        # The 2-hop chain: runs → jobs → workspaces.tenant_id.
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import _visible_count_as

        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, "databricks_job_runs") == 1
        assert _visible_count_as(probe, self.tenant_b.id, "databricks_job_runs") == 0, (
            "the job→workspace chain policy must hide the run from tenant B"
        )

    def test_no_tenant_context_hides_all_mirror_rows(self):
        # An UNSET tenant GUC (the fail-closed default) must surface
        # NOTHING through either policy.
        from django.db import connection

        probe = self._probe_role()
        with connection.cursor() as cursor:
            try:
                if probe:
                    cursor.execute(f"SET ROLE {probe}")
                for table in ("databricks_jobs", "databricks_job_runs"):
                    cursor.execute(f"SELECT count(*) FROM {table}")
                    assert cursor.fetchone()[0] == 0, (
                        f"without a tenant context the {table} policy must hide everything"
                    )
            finally:
                if probe:
                    cursor.execute("RESET ROLE")


class TestJobsMirrorSync(TestCase):
    """The live registry sync delta-diffs the jobs API into the mirror."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant)

    def _sync(self, port, workspace=None):
        from hub.apps.databricks_admin.jobs_mirror import refresh_jobs_mirror

        return refresh_jobs_mirror(workspace or self.workspace, client=_client(port))

    def _server(self):
        import http.server
        import threading

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        return port

    def _scripted(self, *payloads):
        RecordingHandler.json_script = [json.dumps(p) for p in payloads]

    def test_sync_creates_the_job_and_run_mirror_from_api_payloads(self):
        from hub.apps.databricks_admin.models import DatabricksJob, DatabricksJobRun

        port = self._server()
        self._scripted(
            {"jobs": [_job_payload()], "has_more": False},
            {"runs": [_run_payload()], "has_more": False},
        )
        counters = self._sync(port)
        assert counters == {
            "jobs": {"created": 1, "updated": 0, "unchanged": 0, "deleted": 0},
            "runs": {"created": 1, "updated": 0, "unchanged": 0, "deleted": 0},
        }, counters

        job = DatabricksJob.objects.get(workspace=self.workspace)
        assert job.job_id == "12345"
        assert job.name == "nightly-etl"
        assert job.task_config == [{"task_key": "ingest", "spark_sql_task": {"query": "SELECT 1"}}]
        assert job.schedule == {"quartz_cron_expression": "0 0 3 * * ?", "timezone_id": "UTC"}

        run = DatabricksJobRun.objects.get(job=job)
        assert run.run_id == "67890"
        assert run.lifecycle_state == "TERMINATED"
        assert run.result_state == "SUCCESS"
        assert run.duration_ms == 45000

        paths = [r["path"] for r in RecordingHandler.requests]
        assert paths == ["/api/2.1/jobs/list", "/api/2.1/jobs/runs/list"], paths

    def test_second_sync_is_a_full_no_op_and_keeps_the_freshness_stamps(self):
        from hub.apps.databricks_admin.models import DatabricksJob, DatabricksJobRun

        port = self._server()
        self._scripted(
            {"jobs": [_job_payload()], "has_more": False},
            {"runs": [_run_payload()], "has_more": False},
        )
        self._sync(port)
        job = DatabricksJob.objects.get(workspace=self.workspace)
        run = DatabricksJobRun.objects.get(job=job)
        job_stamp, run_stamp = job.synced_at, run.synced_at

        self._scripted(
            {"jobs": [_job_payload()], "has_more": False},
            {"runs": [_run_payload()], "has_more": False},
        )
        counters = self._sync(port)
        assert counters == {
            "jobs": {"created": 0, "updated": 0, "unchanged": 1, "deleted": 0},
            "runs": {"created": 0, "updated": 0, "unchanged": 1, "deleted": 0},
        }, counters

        job.refresh_from_db()
        run.refresh_from_db()
        assert job.synced_at == job_stamp, "an unchanged job row must keep its synced_at stamp"
        assert run.synced_at == run_stamp, "an unchanged run row must keep its synced_at stamp"

    def test_sync_updates_changed_rows_and_deletes_absent_ones(self):
        from hub.apps.databricks_admin.models import DatabricksJob, DatabricksJobRun

        port = self._server()
        self._scripted(
            {
                "jobs": [_job_payload(), _job_payload(job_id="23456", name="ad-hoc")],
                "has_more": False,
            },
            {
                "runs": [
                    _run_payload(
                        run_id="67890",
                        life_cycle_state="RUNNING",
                        result_state=None,
                        duration_ms=None,
                    ),
                    _run_payload(run_id="88888", result_state="TIMEDOUT"),
                    _run_payload(run_id="77777", job_id="23456"),
                ],
                "has_more": False,
            },
        )
        self._sync(port)
        assert DatabricksJob.objects.filter(workspace=self.workspace).count() == 2
        assert DatabricksJobRun.objects.filter(job__workspace=self.workspace).count() == 3

        # job 23456 disappears on the Databricks side; job 12345 renames;
        # run 67890 terminates FAILED with a message; run 88888 vanishes.
        self._scripted(
            {"jobs": [_job_payload(name="nightly-etl-v2")], "has_more": False},
            {
                "runs": [
                    _run_payload(
                        run_id="67890",
                        result_state="FAILED",
                        state_message="cluster lost",
                    ),
                ],
                "has_more": False,
            },
        )
        counters = self._sync(port)
        assert counters == {
            "jobs": {"created": 0, "updated": 1, "unchanged": 0, "deleted": 1},
            "runs": {"created": 0, "updated": 1, "unchanged": 0, "deleted": 1},
        }, counters

        job = DatabricksJob.objects.get(workspace=self.workspace)
        assert job.name == "nightly-etl-v2"
        assert not DatabricksJob.objects.filter(job_id="23456").exists(), (
            "an absent workspace job must leave the mirror"
        )
        run = DatabricksJobRun.objects.get(run_id="67890")
        assert run.lifecycle_state == "TERMINATED"
        assert run.result_state == "FAILED"
        assert run.error_message == "cluster lost"
        assert not DatabricksJobRun.objects.filter(run_id="88888").exists(), (
            "an absent run must leave the mirror (derived, never compensated)"
        )
        assert not DatabricksJobRun.objects.filter(run_id="77777").exists(), (
            "the deleted job's runs die with it via the mirror cascade"
        )

    def test_unknown_run_states_are_skipped_never_invented(self):
        # A lifecycle or result state the vocabulary does not know must be
        # SKIPPED with zero crash — the mirror never invents a state.
        from hub.apps.databricks_admin.models import DatabricksJobRun

        port = self._server()
        self._scripted(
            {"jobs": [_job_payload()], "has_more": False},
            {
                "runs": [
                    _run_payload(run_id="67890"),
                    _run_payload(run_id="r-warp", life_cycle_state="WARPING", result_state=None),
                    _run_payload(run_id="r-bad-result", result_state="MOSTLY_OK"),
                ],
                "has_more": False,
            },
        )
        counters = self._sync(port)
        assert counters["runs"] == {"created": 1, "updated": 0, "unchanged": 0, "deleted": 0}, (
            counters
        )
        assert list(
            DatabricksJobRun.objects.filter(job__workspace=self.workspace).values_list(
                "run_id", flat=True
            )
        ) == ["67890"], "unknown reported states must never be invented into the mirror"

    def test_a_run_of_an_unmirrored_job_is_skipped(self):
        # A run whose job is not mirrored (job not reported, or deleted
        # on the workspace side) must be SKIPPED — the mirror never
        # invents a job to hang the run on.
        from hub.apps.databricks_admin.models import DatabricksJobRun

        port = self._server()
        self._scripted(
            {"jobs": [_job_payload()], "has_more": False},
            {"runs": [_run_payload(job_id="99999")], "has_more": False},
        )
        counters = self._sync(port)
        assert counters["runs"]["created"] == 0, counters
        assert not DatabricksJobRun.objects.filter(job__workspace=self.workspace).exists()

    def test_malformed_fields_are_skipped_never_invented(self):
        # The "never invent" principle extends to SHAPES: a missing name,
        # non-list tasks, a non-object schedule, a non-numeric duration,
        # and a non-string state message must all leave ZERO mirror rows.
        from hub.apps.databricks_admin.models import DatabricksJob, DatabricksJobRun

        port = self._server()
        self._scripted(
            {
                "jobs": [
                    _job_payload(),
                    _job_payload(job_id="j-no-name", name=None),
                    _job_payload(job_id="j-bad-tasks", tasks={"not": "a list"}),
                    _job_payload(job_id="j-bad-schedule", schedule="every night"),
                ],
                "has_more": False,
            },
            {
                "runs": [
                    _run_payload(run_id="67890"),
                    {
                        "job_id": "12345",
                        "state": {
                            "life_cycle_state": "TERMINATED",
                            "result_state": "SUCCESS",
                            "state_message": "",
                        },
                        "run_duration": 45000,
                    },
                    _run_payload(run_id="r-bad-duration", duration_ms="45s"),
                    _run_payload(run_id="r-bool-duration", duration_ms=True),
                    _run_payload(run_id="r-bad-message", state_message={"boom": True}),
                ],
                "has_more": False,
            },
        )
        counters = self._sync(port)
        assert counters == {
            "jobs": {"created": 1, "updated": 0, "unchanged": 0, "deleted": 0},
            "runs": {"created": 1, "updated": 0, "unchanged": 0, "deleted": 0},
        }, counters
        assert list(
            DatabricksJob.objects.filter(workspace=self.workspace).values_list("job_id", flat=True)
        ) == ["12345"]
        assert list(
            DatabricksJobRun.objects.filter(job__workspace=self.workspace).values_list(
                "run_id", flat=True
            )
        ) == ["67890"]

    def test_pagination_follows_next_page_token_chains(self):
        from hub.apps.databricks_admin.models import DatabricksJob, DatabricksJobRun

        port = self._server()
        self._scripted(
            {"jobs": [_job_payload()], "has_more": True, "next_page_token": "jt1"},
            {"jobs": [_job_payload(job_id="23456", name="ad-hoc")], "has_more": False},
            {"runs": [_run_payload(run_id="67890")], "has_more": True, "next_page_token": "rt1"},
            {"runs": [_run_payload(run_id="88888")], "has_more": False},
        )
        counters = self._sync(port)
        assert counters == {
            "jobs": {"created": 2, "updated": 0, "unchanged": 0, "deleted": 0},
            "runs": {"created": 2, "updated": 0, "unchanged": 0, "deleted": 0},
        }, counters
        assert DatabricksJob.objects.filter(workspace=self.workspace).count() == 2
        assert DatabricksJobRun.objects.filter(job__workspace=self.workspace).count() == 2

        page_paths = [r["path"] for r in RecordingHandler.requests]
        assert page_paths == [
            "/api/2.1/jobs/list",
            "/api/2.1/jobs/list?page_token=jt1",
            "/api/2.1/jobs/runs/list",
            "/api/2.1/jobs/runs/list?page_token=rt1",
        ], page_paths

    def test_a_repeating_next_page_token_is_classified_never_a_loop(self):
        # The 1.12 pagination hardening: a repeating token (a real
        # workspace bug surface) must fail the sync classified, never
        # hang the worker.
        from hub.apps.databricks_admin.client import DatabricksApiError

        port = self._server()
        self._scripted(
            {"jobs": [_job_payload()], "has_more": True, "next_page_token": "tok-x"},
            {"jobs": [_job_payload()], "has_more": True, "next_page_token": "tok-x"},
        )
        with pytest.raises(DatabricksApiError):
            self._sync(port)

    def test_a_non_object_payload_is_classified_never_a_leak(self):
        from hub.apps.databricks_admin.client import DatabricksApiError

        port = self._server()
        self._scripted(["not", "an", "object"])
        with pytest.raises(DatabricksApiError):
            self._sync(port)

        self._scripted(
            {"jobs": [_job_payload()], "has_more": False},
            ["still", "not", "an", "object"],
        )
        with pytest.raises(DatabricksApiError):
            self._sync(port)
