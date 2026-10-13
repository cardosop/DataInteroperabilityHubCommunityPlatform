"""TDD pins for the P4 run-now flow (openspec add-databricks-jobs task
4.4) — run-now → Hub ``Job`` (`JobType.DATABRICKS_JOB_RUN`) → backoff
poller → terminal audit + OpenLineage + duration-x-size cost estimate.

No mocks: real Postgres rows (tenant/workspace/job mirror/Hub Job), the
PRODUCTION 4.3 ``DatabricksJobsClient`` over the REAL ``DatabricksApiClient``
against a REAL local HTTP server (the scripted runs/get state machine),
the REAL audit chokepoint rows read back, the REAL cost estimator, and
the OpenLineage event validated against the REAL 2.0.0 schema. The ONE
sanctioned patch point is the outbound lineage dispatch symbol (the
contracts/lineage_sync convention — the Marquez network boundary is
fail-soft by contract; the repo's own lineage pins patch the same
symbol).
"""

import json
import uuid

import pytest
from django.test import override_settings

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = pytest.mark.django_db(transaction=True)


def _seed_workspace(tenant):
    from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

    tenant.databricks_control_plane_enabled = True
    tenant.save(update_fields=["databricks_control_plane_enabled"])
    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"ws-jobs-{uuid.uuid4().hex[:6]}",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )


def _seed_mirror_job(workspace, job_id="job-42"):
    from hub.apps.databricks_admin.models import DatabricksJob

    # Unique-suffixed rows: the shared DB's flush teardown is unreliable
    # (suppressed sqlflush errors leak rows across runs) — a unique id
    # keeps leaked rows identifiable and cross-test collisions impossible.
    job_id = f"{job_id}-{uuid.uuid4().hex[:8]}"
    return DatabricksJob.objects.create(
        workspace=workspace,
        job_id=job_id,
        name="nightly-etl",
        task_config=[{"task_key": "etl", "sql_task": {"warehouse_id": "wh-1"}}],
    )


def _run_payload(
    *, lifecycle="TERMINATED", result="SUCCESS", run_id="7", state_message="", **extra
):
    payload = {
        "job_id": "job-42",
        "run_id": run_id,
        "state": {
            "life_cycle_state": lifecycle,
            "result_state": result,
            "state_message": state_message,
        },
        "run_duration": 60000,
        "cluster_spec": {"node_type_id": "i3.xlarge", "num_workers": 2},
    }
    payload.update(extra)
    return payload


class _RecordingSleeper:
    """The poller's sleep seam — records the requested delays so the
    backoff sequence is pinned exactly (the production default is
    ``time.sleep``)."""

    def __init__(self):
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class _LineageRecorder:
    """The sanctioned patch target for the outbound lineage dispatch
    (the contracts/lineage_sync convention)."""

    def __init__(self):
        self.calls: list[dict] = []

    def delay(self, **kwargs):
        self.calls.append(kwargs)


class _WebhookRecorder:
    """The sanctioned patch target for the 4.5 webhook notifier."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return 0


class TestJobTypeRegistration:
    def test_job_type_carries_the_databricks_job_run_value(self):
        from hub.apps.jobs.models import JobType

        assert JobType.DATABRICKS_JOB_RUN == "DATABRICKS_JOB_RUN"
        assert "DATABRICKS_JOB_RUN" in JobType.values


class TestJobRunColumn:
    def test_job_carries_the_additive_databricks_run_id_column(self):
        from django.db import models

        from hub.apps.jobs.models import Job

        field = next(f for f in Job._meta.fields if f.name == "databricks_run_id")
        assert isinstance(field, models.BigIntegerField)
        assert field.null is True


class TestJobRunAuditConstants:
    def test_run_audit_constants_are_registered_and_exported(self):
        from hub.apps.audit import event_types

        for name in (
            "DATABRICKS_JOB_RUN_STARTED",
            "DATABRICKS_JOB_RUN_SUCCEEDED",
            "DATABRICKS_JOB_RUN_FAILED",
        ):
            assert getattr(event_types, name, None) == name, f"{name} constant missing"
            assert name in event_types.__all__, f"{name} missing from __all__"


class TestTerminalStateMapping:
    def test_every_result_state_maps_to_a_documented_job_status(self):
        from hub.apps.databricks_admin.job_runs import _RESULT_TO_JOB_STATUS
        from hub.apps.databricks_admin.models import DatabricksJobRunResultState
        from hub.apps.jobs.models import JobStatus

        # The WHOLE vocabulary maps — never an invented status.
        assert set(_RESULT_TO_JOB_STATUS) == set(DatabricksJobRunResultState.values)
        assert set(_RESULT_TO_JOB_STATUS.values()) <= set(JobStatus.values)

        assert _RESULT_TO_JOB_STATUS["SUCCESS"] == JobStatus.COMPLETED
        assert _RESULT_TO_JOB_STATUS["SUCCESS_WITH_FAILURES"] == JobStatus.COMPLETED
        assert _RESULT_TO_JOB_STATUS["FAILED"] == JobStatus.FAILED
        assert _RESULT_TO_JOB_STATUS["TIMEDOUT"] == JobStatus.FAILED
        assert _RESULT_TO_JOB_STATUS["MAXIMUM_CONCURRENT_RUNS_REACHED"] == JobStatus.FAILED
        assert _RESULT_TO_JOB_STATUS["UPSTREAM_FAILED"] == JobStatus.FAILED
        assert _RESULT_TO_JOB_STATUS["CANCELED"] == JobStatus.CANCELLED
        assert _RESULT_TO_JOB_STATUS["UPSTREAM_CANCELED"] == JobStatus.CANCELLED
        assert _RESULT_TO_JOB_STATUS["EXCLUDED"] == JobStatus.CANCELLED

    def test_polling_stops_only_on_the_terminal_lifecycle_states(self):
        from hub.apps.databricks_admin.job_runs import _POLL_TERMINAL_LIFECYCLE_STATES

        assert {"TERMINATED", "INTERNAL_ERROR", "SKIPPED"} == _POLL_TERMINAL_LIFECYCLE_STATES


class TestEstimateRunCost:
    def test_run_duration_and_cluster_workers_drive_the_estimate(self):
        from hub.apps.databricks_admin.job_runs import estimate_run_cost

        estimate = estimate_run_cost(_run_payload(run_duration=3_600_000))
        assert estimate["duration_seconds"] == 3600.0
        assert estimate["size_factor"] == 2.0  # 1 + 0.5 x 2 workers
        assert estimate["dbh_rate"] == pytest.approx(0.55)
        assert estimate["estimated_cost"] == pytest.approx(1 * 0.55 * 2.0)
        assert estimate["formula"] == "duration_hours x dbh_rate x (1 + 0.5 x num_workers)"

    def test_missing_run_duration_falls_back_to_the_part_durations(self):
        from hub.apps.databricks_admin.job_runs import estimate_run_cost

        payload = _run_payload(run_duration=None)
        payload["setup_duration"] = 1000
        payload["execution_duration"] = 2000
        payload["cleanup_duration"] = 1000
        estimate = estimate_run_cost(payload)
        assert estimate["duration_seconds"] == 4.0

    def test_absent_cluster_spec_yields_the_single_node_factor(self):
        from hub.apps.databricks_admin.job_runs import estimate_run_cost

        payload = _run_payload(run_duration=3600000)
        payload.pop("cluster_spec")
        estimate = estimate_run_cost(payload)
        assert estimate["size_factor"] == 1.0

    def test_non_numeric_workers_fall_back_to_zero(self):
        from hub.apps.databricks_admin.job_runs import estimate_run_cost

        payload = _run_payload(run_duration=3600000)
        payload["cluster_spec"] = {"num_workers": "two"}
        estimate = estimate_run_cost(payload)
        assert estimate["size_factor"] == 1.0


class TestRunDatabricksJobNow:
    """The full run-now → poll → terminal round-trip on the REAL stack."""

    def _setup(self, monkeypatch):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)
        self.mirror = _seed_mirror_job(self.workspace)
        self.sleeper = _RecordingSleeper()
        self.lineage = _LineageRecorder()
        self.webhooks = _WebhookRecorder()

        from hub.apps.databricks_admin import job_runs

        monkeypatch.setattr(job_runs, "send_openlineage_event_async", self.lineage)
        monkeypatch.setattr(job_runs, "notify_job_run_failed", self.webhooks)

    def _client(self, port):
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.jobs_client import DatabricksJobsClient

        raw = DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id=str(self.tenant.id),
            credential_config={"token": "dapi-jobs"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
        )
        return DatabricksJobsClient(raw)

    def _run(self, client, **kwargs):
        from hub.apps.databricks_admin.job_runs import run_databricks_job_now

        return run_databricks_job_now(
            workspace=self.workspace,
            mirror_job=self.mirror,
            actor_user=self.admin,
            client=client,
            sleeper=self.sleeper,
            **kwargs,
        )

    @override_settings(
        CAPABILITY_FLAGS={"lineage.openlineage_export": True},
        OPENLINEAGE_PRODUCER_NAME="https://meshant.com/jobs/openlineage",
    )
    def test_success_roundtrip_polls_to_completion_and_emits_everything(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [
            json.dumps({"run_id": "7"}),  # the run-now answer
            json.dumps(_run_payload(lifecycle="PENDING")),
            json.dumps(_run_payload(lifecycle="RUNNING")),
            json.dumps(_run_payload(lifecycle="TERMINATED", result="SUCCESS")),
        ]

        job = self._run(client, poll_timeout_s=300)

        # The wire: run-now POST + the poll GETs on the pinned paths.
        requests = RecordingHandler.requests
        assert requests[0]["method"] == "POST"
        assert requests[0]["path"] == "/api/2.1/jobs/run-now"
        assert json.loads(requests[0]["body"]) == {"job_id": self.mirror.job_id}
        gets = [r for r in requests[1:] if r["method"] == "GET"]
        assert len(gets) == 3
        assert all(r["path"] == "/api/2.1/jobs/runs/get?run_id=7" for r in gets)

        # The Hub Job terminal state.
        from hub.apps.jobs.models import JobStatus

        assert job.databricks_run_id == 7
        assert job.status == JobStatus.COMPLETED
        assert job.started_at is not None
        assert job.completed_at is not None
        assert job.result_json["databricks_run_state"] == "SUCCESS"
        assert job.result_json["cost_estimate"]["duration_seconds"] == 60.0

        # The audit trail: STARTED + SUCCEEDED rows with attribution.
        from hub.apps.audit.models import AuditEvent

        events = AuditEvent.objects.filter(
            tenant=self.tenant, resource_type="DATABRICKS_JOB"
        ).order_by("timestamp")
        assert {e.action for e in events} == {"RUN_STARTED", "RUN_SUCCEEDED"}
        assert all(str(e.resource_id) == str(job.id) for e in events)
        assert all(str(e.details_json["databricks_run_id"]) == "7" for e in events)

        # The webhook fires only on terminal FAILURES — a success sends none.
        assert self.webhooks.calls == []

        # The OpenLineage COMPLETE event (validated against the schema).
        assert len(self.lineage.calls) == 1
        dispatched = self.lineage.calls[0]
        event = dispatched["event"]
        from hub.apps.integrations.openlineage.translator import (
            validate_openlineage_event,
        )

        validate_openlineage_event(event)
        assert event["eventType"] == "COMPLETE"
        assert event["run"]["runId"] == f"databricks:{self.mirror.job_id}:7"
        assert event["job"]["namespace"] == "meshant.databricks"
        assert dispatched["tenant_id"] == str(self.tenant.id)

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_failed_run_marks_the_job_and_emits_the_failure_event(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [
            json.dumps({"run_id": "7"}),
            json.dumps(
                _run_payload(
                    lifecycle="TERMINATED",
                    result="FAILED",
                    state_message="Task etl failed: OOM",
                )
            ),
        ]

        job = self._run(client)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "OOM" in job.error_message

        from hub.apps.audit.models import AuditEvent

        actions = {
            e.action
            for e in AuditEvent.objects.filter(tenant=self.tenant, resource_type="DATABRICKS_JOB")
        }
        assert actions == {"RUN_STARTED", "RUN_FAILED"}

        event = self.lineage.calls[0]["event"]
        assert event["eventType"] == "FAIL"
        assert event["run"]["facets"]["errorMessage"]["message"] == "Task etl failed: OOM"

        # The 4.5 webhook: exactly ONE call with the documented contract.
        assert len(self.webhooks.calls) == 1
        notified = self.webhooks.calls[0]
        assert notified["tenant_id"] == str(self.tenant.id)
        assert notified["workspace_id"] == str(self.workspace.id)
        assert notified["job_id"] == self.mirror.job_id
        assert notified["run_id"] == "7"
        assert notified["result_state"] == "FAILED"
        assert "OOM" in notified["error_message"]

    def test_canceled_run_marks_the_job_cancelled(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [
            json.dumps({"run_id": "7"}),
            json.dumps(_run_payload(lifecycle="TERMINATED", result="CANCELED")),
        ]

        job = self._run(client)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.CANCELLED
        assert job.result_json["databricks_run_state"] == "CANCELED"

    def test_poll_budget_exhaustion_fails_the_job_closed(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        # The server keeps answering RUNNING — the budget expires first.
        RecordingHandler.json_script = [json.dumps({"run_id": "7"})] + [
            json.dumps(_run_payload(lifecycle="RUNNING")) for _ in range(20)
        ]

        job = self._run(client, poll_timeout_s=5)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "poll budget" in job.error_message

        from hub.apps.audit.models import AuditEvent

        actions = {
            e.action
            for e in AuditEvent.objects.filter(tenant=self.tenant, resource_type="DATABRICKS_JOB")
        }
        assert actions == {"RUN_STARTED", "RUN_FAILED"}
        event = self.lineage.calls[0]["event"]
        assert event["eventType"] == "FAIL"
        assert len(self.webhooks.calls) == 1
        assert self.webhooks.calls[0]["result_state"] == ""

    def test_polling_backs_off_with_the_documented_sequence(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = (
            [json.dumps({"run_id": "7"})]
            + [json.dumps(_run_payload(lifecycle="RUNNING")) for _ in range(6)]
            + [json.dumps(_run_payload(lifecycle="TERMINATED", result="SUCCESS"))]
        )

        self._run(client, poll_timeout_s=300)

        # 2.0 → 3.0 → 4.5 → 6.75 → 10.125 → 15.1875 (factor 1.5).
        assert self.sleeper.delays == pytest.approx([2.0, 3.0, 4.5, 6.75, 10.125, 15.1875])

    def test_run_now_dispatch_failure_marks_the_job_failed_with_zero_polling(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [json.dumps({"error_code": "PERMISSION_DENIED"})]
        RecordingHandler.script = [403]

        job = self._run(client)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "DATABRICKS_AUTH_FAILED" in job.error_message
        assert job.databricks_run_id is None
        assert len(RecordingHandler.requests) == 1, "no polling after a failed dispatch"

        from hub.apps.audit.models import AuditEvent

        actions = {
            e.action
            for e in AuditEvent.objects.filter(tenant=self.tenant, resource_type="DATABRICKS_JOB")
        }
        assert actions == {"RUN_FAILED"}, "no STARTED row for a run that never dispatched"

    def test_audit_outage_never_blocks_the_terminal_transition(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [
            json.dumps({"run_id": "7"}),
            json.dumps(_run_payload(lifecycle="TERMINATED", result="SUCCESS")),
        ]

        def boom(*_args, **_kwargs):
            raise RuntimeError("audit DB down")

        import hub.apps.audit.utils as audit_utils

        monkeypatch.setattr(audit_utils, "create_audit_event", boom)

        job = self._run(client)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.COMPLETED, (
            "the terminal transition survives the audit outage"
        )
