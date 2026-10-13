"""TDD pins for the REAL dbt-as-job dispatcher (openspec
run-transformation-on-databricks task 11.2) — the registered provider
implementation of the transformation facade
(``hub.apps.transformation.execution_targets.dispatch_dbt_as_databricks_job``):

- resolves the tenant's workspace + the mirrored runner job
  (tenant-scoped, inside ``tenant_context`` — the CLAUDE.md worker
  contract),
- builds the PRODUCTION ``DatabricksJobsClient`` through the 0.8
  factory seam against a REAL threaded local HTTP server (the
  ``_build_dbt_dispatch_client`` symbol — the 10.7 view convention),
- rides the REAL 4.4 ``run_databricks_job_now`` spine: the Hub ``Job``
  row (``JobType.DATABRICKS_JOB_RUN``), the RUN_STARTED audit at
  dispatch, the backoff poll to the terminal state, the terminal audit
  + the lineage/webhook seams (the 4.4 sanctioned patch points — the
  recorders here are the SAME convention the 4.4 pins use).

Fail-closed: a missing workspace / a missing runner job refuses with
the classified code and ZERO API calls. No mocks beyond those
sanctioned seams — real Postgres rows, the production client over a
real HTTP server, real audit rows read back.
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.test import TestCase, override_settings

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_job_runs import (
    _LineageRecorder,
    _RecordingSleeper,
    _WebhookRecorder,
)
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.jobs.models import JobStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _seed_mirror_job(workspace, job_id=None):
    from hub.apps.databricks_admin.models import DatabricksJob

    job_id = job_id or f"dbt-runner-{uuid.uuid4().hex[:8]}"
    return DatabricksJob.objects.create(
        workspace=workspace,
        job_id=job_id,
        name="dbt-runner",
        task_config=[{"task_key": "dbt", "python_wheel_task": {"package_name": "dbt_runner"}}],
    )


def _run_payload(*, lifecycle="TERMINATED", result="SUCCESS", run_id="7"):
    return {
        "job_id": "job-42",
        "run_id": run_id,
        "state": {
            "life_cycle_state": lifecycle,
            "result_state": result,
            "state_message": "",
        },
        "run_duration": 60000,
        "cluster_spec": {"node_type_id": "i3.xlarge", "num_workers": 2},
    }


class TestDbtJobDispatch(TestCase):
    """The dispatcher end-to-end on the REAL stack."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.workspace = _make_workspace(self.tenant, name=f"ws-dbt-jrn-{uuid.uuid4().hex[:8]}")
        self.mirror = _seed_mirror_job(self.workspace)
        self.sleeper = _RecordingSleeper()
        self.lineage = _LineageRecorder()
        self.webhooks = _WebhookRecorder()

        import http.server
        import threading

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        self.server = server
        self.port = server.server_address[1]
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.thread.start()

        # The sanctioned seams (the 4.4 pin convention): the 0.8 client
        # factory → the local transport; the outbound lineage/webhook
        # boundaries → recorders. The dispatcher + the P4 spine are the
        # production code.
        import hub.apps.databricks_admin.dbt_job_dispatch as dispatch_mod
        import hub.apps.databricks_admin.job_runs as job_runs_mod

        def _local_client(_workspace):
            from hub.apps.databricks_admin.client import DatabricksApiClient
            from hub.apps.databricks_admin.jobs_client import DatabricksJobsClient

            return DatabricksJobsClient(
                DatabricksApiClient(
                    base_url=f"http://127.0.0.1:{self.port}",
                    tenant_id=str(self.tenant.id),
                    credential_config={"token": "dapi-dbt-dispatch"},
                    timeout_ms=5000,
                    max_retries=1,
                    retry_base_delay=0.05,
                    retry_max_delay=0.1,
                )
            )

        # Save the originals — the replacements MUST be restored in
        # tearDown. A leaked module-symbol assignment poisons every later
        # test in the process: the jobs journey's REAL webhook delivery
        # rides job_runs_mod.notify_job_run_failed, so a leaked recorder
        # here silently swallows the delivery ("delivery not recorded").
        self._patched_originals = (
            (dispatch_mod, "_build_dbt_dispatch_client", dispatch_mod._build_dbt_dispatch_client),
            (
                job_runs_mod,
                "send_openlineage_event_async",
                job_runs_mod.send_openlineage_event_async,
            ),
            (job_runs_mod, "notify_job_run_failed", job_runs_mod.notify_job_run_failed),
        )
        dispatch_mod._build_dbt_dispatch_client = _local_client
        job_runs_mod.send_openlineage_event_async = self.lineage
        job_runs_mod.notify_job_run_failed = self.webhooks

    def tearDown(self):
        for module, name, original in getattr(self, "_patched_originals", []):
            setattr(module, name, original)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _dispatch(self, **overrides):
        from hub.apps.databricks_admin.dbt_job_dispatch import dispatch_dbt_run_as_databricks_job

        kwargs = {
            "tenant_id": str(self.tenant.id),
            "workspace_id": str(self.workspace.id),
            "runner_job_id": self.mirror.job_id,
            "select": None,
            "target": "prod",
            "actor_user": self.admin,
            "sleeper": self.sleeper,
        }
        kwargs.update(overrides)
        return dispatch_dbt_run_as_databricks_job(**kwargs)

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": False})
    def test_dispatch_rides_the_p4_spine(self):
        """run-now → poll → terminal on the REAL 4.4 spine: the Hub Job
        row, the dispatch + terminal audit rows, the run id recorded."""
        RecordingHandler.json_script = [
            json.dumps({"run_id": "7"}),  # the run-now answer
            json.dumps(_run_payload(lifecycle="RUNNING", result=None)),  # poll 1
            json.dumps(_run_payload(lifecycle="TERMINATED", result="SUCCESS")),  # poll 2
        ]
        result = self._dispatch()

        assert result["run_id"] == 7
        assert result["status"] == JobStatus.COMPLETED
        assert result["resource_type"] == "DATABRICKS_JOB"

        from hub.apps.databricks_admin.models import DatabricksJob
        from hub.apps.jobs.models import Job

        job = Job.objects.get(id=result["job_id"])
        assert job.type == "DATABRICKS_JOB_RUN"
        assert job.status == JobStatus.COMPLETED
        assert job.resource_id == self.mirror.id
        assert job.databricks_run_id == 7

        recorded = RecordingHandler.requests
        assert recorded[0]["method"] == "POST"
        assert recorded[0]["path"] == "/api/2.1/jobs/run-now"
        body = json.loads(recorded[0]["body"])
        assert body == {"job_id": self.mirror.job_id}
        gets = [r for r in recorded if r["method"] == "GET"]
        assert all(r["path"] == "/api/2.1/jobs/runs/get?run_id=7" for r in gets)
        # The dispatcher passes the recorded sleeper through — the 4.4
        # backoff discipline is unchanged (pinned by the 4.4 suite).
        assert self.sleeper.delays

        from hub.apps.audit.models import AuditEvent

        events = AuditEvent.objects.filter(
            tenant=self.tenant, resource_type="DATABRICKS_JOB"
        ).order_by("timestamp")
        # The 4.4 convention: SHORT action verbs + the resource type
        # carries the estate identity (the 4.4 pin's exact assertion).
        assert {e.action for e in events} == {"RUN_STARTED", "RUN_SUCCEEDED"}
        assert all(str(e.resource_id) == str(job.id) for e in events)

        # The dispatched context lands on the job's details.
        assert job.details_json["databricks_job_id"] == str(self.mirror.job_id)
        # The runner mirror row is untouched (the dispatcher never
        # mutates the registry).
        assert DatabricksJob.objects.get(id=self.mirror.id).job_id == self.mirror.job_id

    def test_a_missing_runner_job_refuses_with_zero_network(self):
        from hub.apps.databricks_admin.dbt_job_dispatch import DatabricksDbtDispatchError

        with pytest.raises(DatabricksDbtDispatchError) as excinfo:
            self._dispatch(runner_job_id="does-not-exist")
        assert excinfo.value.code == "DATABRICKS_DBT_RUNNER_JOB_MISSING"
        assert RecordingHandler.requests == [], "the refusal makes ZERO API calls"

    def test_a_foreign_workspace_refuses_with_zero_network(self):
        from hub.apps.databricks_admin.dbt_job_dispatch import DatabricksDbtDispatchError

        other_tenant, _admin = _setup_tenant()
        other_ws = _make_workspace(other_tenant, name=f"ws-other-{uuid.uuid4().hex[:8]}")
        with pytest.raises(DatabricksDbtDispatchError) as excinfo:
            self._dispatch(workspace_id=str(other_ws.id))
        assert excinfo.value.code == "DATABRICKS_DBT_RUNNER_JOB_MISSING"
        assert RecordingHandler.requests == []

    def test_the_facade_is_registered_at_app_ready(self):
        """The provider registration lands at ``databricks_admin``
        app-ready — the transformation facade delegates to the REAL
        dispatcher (the 7.5 seam-registration convention)."""
        from hub.apps.transformation.execution_targets import get_dbt_job_dispatcher

        dispatcher = get_dbt_job_dispatcher()
        assert dispatcher is not None, "the dispatcher registers at app-ready"
        assert callable(dispatcher)
