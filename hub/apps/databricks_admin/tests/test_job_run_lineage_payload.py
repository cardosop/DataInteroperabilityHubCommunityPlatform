"""TDD pins for the terminal OpenLineage run event (openspec
add-databricks-jobs task 4.8) — the payload SHAPE, the capability gate,
and the dispatch contract.

No mocks: REAL Postgres rows (tenant/workspace/job-mirror/Hub Job), the
REAL 4.4 service over a REAL local HTTP server for the flow-level pins,
the REAL ``_emit_run_lineage`` chokepoint for the shape pins, the REAL
2.0.0 schema validator on every emitted variant, and REAL settings
overrides for the capability gate. The sanctioned patch points are the
module-level lineage dispatch symbol (the repo's own outbound-seam
convention) and the capability settings — never the unit under test.
"""

import json

import pytest
from django.test import override_settings

from hub.apps.databricks_admin.tests._fixtures import load_fixture_steps
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_job_runs import (
    _LineageRecorder,
    _RecordingSleeper,
    _seed_mirror_job,
    _seed_workspace,
)
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = pytest.mark.django_db(transaction=True)

CAPABILITY_ON = override_settings(
    CAPABILITY_FLAGS={"lineage.openlineage_export": True},
    OPENLINEAGE_PRODUCER_NAME="https://meshant.com/jobs/openlineage",
    OPENLINEAGE_URL="https://lineage.example.com/api/v1/lineage",
)


def _validate(event):
    from hub.apps.integrations.openlineage.translator import (
        validate_openlineage_event,
    )

    validate_openlineage_event(event)


class _Base:
    """The shared seeding + client factory (the 4.4 convention)."""

    def _setup(self, monkeypatch):
        from hub.apps.databricks_admin.tests._fixtures import require_dns

        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)
        self.mirror = _seed_mirror_job(self.workspace)
        self.sleeper = _RecordingSleeper()
        self.lineage = _LineageRecorder()

        from hub.apps.databricks_admin import job_runs

        monkeypatch.setattr(job_runs, "send_openlineage_event_async", self.lineage)
        monkeypatch.setattr(job_runs, "notify_job_run_failed", lambda **_kwargs: 0)

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
            use_breaker=False,
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

    def _seed_hub_job(self, *, failed=False, error_message=""):
        from hub.apps.jobs.models import Job, JobStatus, JobType

        return Job.objects.create(
            tenant=self.tenant,
            type=JobType.DATABRICKS_JOB_RUN,
            status=JobStatus.FAILED if failed else JobStatus.COMPLETED,
            resource_type="DATABRICKS_JOB",
            resource_id=self.mirror.id,
            created_by=self.admin,
            timeout_seconds=300,
            databricks_run_id=73001,
            error_message=error_message,
            details_json={
                "workspace_id": str(self.workspace.id),
                "databricks_job_id": self.mirror.job_id,
                "job_name": self.mirror.name,
            },
        )


class TestOpenLineageCompleteShape(_Base):
    """The COMPLETE event's exact payload shape (flow-level)."""

    @CAPABILITY_ON
    def test_the_complete_event_carries_the_exact_shape(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = load_fixture_steps("job_run_state_machine")

        job = self._run(client, poll_timeout_s=300)
        assert job.status == "COMPLETED"

        assert len(self.lineage.calls) == 1
        dispatched = self.lineage.calls[0]
        event = dispatched["event"]
        _validate(event)

        # The payload SHAPE — the exact key set, nothing invented.
        assert set(event) == {
            "eventType",
            "eventTime",
            "producer",
            "schemaURL",
            "run",
            "job",
            "inputs",
            "outputs",
        }
        assert event["eventType"] == "COMPLETE"
        assert event["producer"] == "https://meshant.com/jobs/openlineage"
        from hub.apps.integrations.openlineage.translator import OPENLINEAGE_SCHEMA_URL

        assert event["schemaURL"] == OPENLINEAGE_SCHEMA_URL
        assert set(event["run"]) == {"runId", "facets"}
        assert event["run"]["runId"] == f"databricks:{self.mirror.job_id}:73001"
        assert event["run"]["facets"] == {}, "a success carries NO errorMessage facet"
        assert event["job"] == {
            "namespace": "meshant.databricks",
            "name": self.mirror.name,
        }
        assert event["inputs"] == []
        assert event["outputs"] == []

        # The dispatch contract: target_url + tenant_id + .delay (the RQ
        # task dispatch) with the event as the payload.
        assert dispatched["target_url"] == "https://lineage.example.com/api/v1/lineage"
        assert dispatched["tenant_id"] == str(self.tenant.id)

    @CAPABILITY_ON
    def test_the_complete_event_time_is_an_iso_timestamp(self, monkeypatch, local_http_server):
        from datetime import datetime

        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = load_fixture_steps("job_run_state_machine")

        self._run(client, poll_timeout_s=300)

        event = self.lineage.calls[0]["event"]
        datetime.fromisoformat(event["eventTime"])


class TestOpenLineageFailureShape(_Base):
    """The FAIL event's errorMessage facet across the failure legs."""

    @CAPABILITY_ON
    def test_the_failed_run_event_carries_the_error_message_facet(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [
            json.dumps({"run_id": 9101}),
            json.dumps(
                {
                    "job_id": "job-1",
                    "run_id": 9101,
                    "state": {
                        "life_cycle_state": "TERMINATED",
                        "result_state": "FAILED",
                        "state_message": "Task etl failed: OOM",
                    },
                }
            ),
        ]

        job = self._run(client, poll_timeout_s=300)
        assert job.status == "FAILED"

        assert len(self.lineage.calls) == 1
        event = self.lineage.calls[0]["event"]
        _validate(event)
        assert event["eventType"] == "FAIL"
        assert event["run"]["facets"]["errorMessage"] == {
            "message": "Task etl failed: OOM",
            "programmingLanguage": None,
            "stackTrace": None,
        }, "the facet is the exact documented dict — the run's reported error"

    @CAPABILITY_ON
    def test_the_budget_exhaustion_event_carries_the_budget_message(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [json.dumps({"run_id": 9101})] + [
            json.dumps(
                {
                    "job_id": "job-1",
                    "run_id": 9101,
                    "state": {"life_cycle_state": "RUNNING"},
                }
            )
            for _ in range(5)
        ]

        job = self._run(client, poll_timeout_s=1)
        assert "poll budget" in job.error_message

        event = self.lineage.calls[0]["event"]
        _validate(event)
        assert event["eventType"] == "FAIL"
        assert event["run"]["facets"]["errorMessage"]["message"] == job.error_message

    def test_the_fail_event_run_id_carries_the_reported_run_id(
        self, monkeypatch, local_http_server
    ):
        # The runId format is databricks:{job_id}:{run_id} — the FAIL
        # leg carries the same shape as the COMPLETE leg.
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [
            json.dumps({"run_id": 9101}),
            json.dumps(
                {
                    "job_id": "job-1",
                    "run_id": 9101,
                    "state": {
                        "life_cycle_state": "TERMINATED",
                        "result_state": "FAILED",
                        "state_message": "boom",
                    },
                }
            ),
        ]

        self._run(client, poll_timeout_s=300)

        event = self.lineage.calls[0]["event"]
        assert event["run"]["runId"] == f"databricks:{self.mirror.job_id}:9101"


class TestOpenLineageCapabilityGate(_Base):
    """The capability gate: OFF silences the dispatch; the terminal
    transition is NEVER blocked by lineage."""

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": False})
    def test_a_disabled_capability_emits_no_lineage_event(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = load_fixture_steps("job_run_state_machine")

        job = self._run(client, poll_timeout_s=300)
        assert job.status == "COMPLETED", "the transition is independent of lineage"
        assert self.lineage.calls == [], "the gate OFF silences the dispatch"

    @CAPABILITY_ON
    def test_a_raising_dispatch_never_blocks_the_terminal_transition(
        self, monkeypatch, local_http_server
    ):
        from hub.apps.databricks_admin import job_runs

        self._setup(monkeypatch)

        class _ExplodingDispatch:
            def delay(self, **_kwargs):
                raise RuntimeError("lineage backend down")

        monkeypatch.setattr(job_runs, "send_openlineage_event_async", _ExplodingDispatch())
        client = self._client(local_http_server)
        RecordingHandler.json_script = load_fixture_steps("job_run_state_machine")

        job = self._run(client, poll_timeout_s=300)
        assert job.status == "COMPLETED", "a lineage outage is fail-soft — never a failed run"

    @CAPABILITY_ON
    def test_a_missing_dispatch_seam_is_a_silent_no_op(self, monkeypatch, local_http_server):
        from hub.apps.databricks_admin import job_runs

        self._setup(monkeypatch)
        monkeypatch.setattr(job_runs, "send_openlineage_event_async", None)
        client = self._client(local_http_server)
        RecordingHandler.json_script = load_fixture_steps("job_run_state_machine")

        job = self._run(client, poll_timeout_s=300)
        assert job.status == "COMPLETED"
        assert self.lineage.calls == []


class TestOpenLineageDispatchContract(_Base):
    """The dispatch seam contract (direct chokepoint pins on REAL rows)."""

    @CAPABILITY_ON
    def test_the_dispatch_prefers_the_rq_delay_entrypoint(self, monkeypatch):
        from hub.apps.databricks_admin import job_runs

        self._setup(monkeypatch)
        job = self._seed_hub_job(failed=True, error_message="boom")

        job_runs._emit_run_lineage(job, failed=True)

        assert len(self.lineage.calls) == 1, "the .delay entrypoint is used when present"

    @CAPABILITY_ON
    def test_a_seam_without_delay_is_called_directly(self, monkeypatch):
        from hub.apps.databricks_admin import job_runs

        self._setup(monkeypatch)

        class _DirectCall:
            def __init__(self):
                self.calls = []

            def __call__(self, **kwargs):
                self.calls.append(kwargs)

        direct = _DirectCall()
        monkeypatch.setattr(job_runs, "send_openlineage_event_async", direct)
        job = self._seed_hub_job(failed=True, error_message="boom")

        job_runs._emit_run_lineage(job, failed=True)

        assert len(direct.calls) == 1

    @CAPABILITY_ON
    def test_the_fail_event_error_facet_falls_back_to_a_documented_message(self, monkeypatch):
        from hub.apps.databricks_admin import job_runs

        self._setup(monkeypatch)
        job = self._seed_hub_job(failed=True, error_message="")

        job_runs._emit_run_lineage(job, failed=True)

        event = self.lineage.calls[0]["event"]
        _validate(event)
        assert event["run"]["facets"]["errorMessage"]["message"] == ("the Databricks run failed")

    @override_settings(
        CAPABILITY_FLAGS={"lineage.openlineage_export": True},
        OPENLINEAGE_PRODUCER_NAME="https://meshant.example/producer",
        OPENLINEAGE_URL=None,
    )
    def test_the_producer_and_target_come_from_settings(self, monkeypatch):
        from hub.apps.databricks_admin import job_runs

        self._setup(monkeypatch)
        job = self._seed_hub_job()

        job_runs._emit_run_lineage(job, failed=False)

        dispatched = self.lineage.calls[0]
        assert dispatched["event"]["producer"] == "https://meshant.example/producer"
        assert dispatched["target_url"] is None, (
            "OPENLINEAGE_URL is unset — the dispatch ships None"
        )
