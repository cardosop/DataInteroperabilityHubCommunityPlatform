"""TDD pins for the P4 poller state machine (openspec add-databricks-jobs
task 4.8) — the run-now → poll → terminal round-trip driven from
AUDITABLE DATA fixtures through the PRODUCTION stack.

The fixtures (``tests/fixtures/databricks/job_run_state_matrix.json`` +
``job_run_state_machine.json``) are DATA, not mocks: tests serve them
through a REAL threaded HTTP server to the PRODUCTION 4.3 jobs client,
and the REAL 4.4 poller (``run_databricks_job_now``) follows the
scripted ``runs/get`` state machine with the REAL backoff against a
recording sleeper. REAL Postgres rows (tenant/workspace/job-mirror/Hub
Job/audit), the REAL audit chokepoint read back, the REAL OpenLineage
schema validator, the REAL cost estimator.

Pinned here (the cells 4.4 did not cover):

- the state-matrix integrity (vocabulary-only lifecycle/result states,
  numeric run ids, the machine's internal consistency);
- EVERY non-terminal lifecycle state keeps polling (a 9-state matrix);
- the anomalous terminals (INTERNAL_ERROR / SKIPPED) stop the poller;
- the WHOLE 9-result-state vocabulary → documented Hub JobStatus /
  audit action / lineage eventType / webhook contract (parametrized
  against a hardcoded table);
- fail-closed edges: an absent result at TERMINATED, a malformed (non
  dict / missing) state payload, a mid-poll classified error, a
  malformed run id in the run-now answer — never a stranded Job, never
  an invented success;
- the exact audit details/attribution per emission; the allowlist
  passthrough at the lifecycle boundary.

The sanctioned patch points are the repo's own outbound seams (the
lineage dispatch symbol, the webhook notifier) and the injectable
sleeper — the conventions of the 4.4 suite.
"""

import json

import pytest
from django.test import override_settings

from hub.apps.databricks_admin.tests._fixtures import (
    load_fixture_steps,
    require_dns,
)
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests._uc_fixtures import load_fixture
from hub.apps.databricks_admin.tests.test_job_runs import (
    _LineageRecorder,
    _RecordingSleeper,
    _seed_mirror_job,
    _seed_workspace,
    _WebhookRecorder,
)
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = pytest.mark.django_db(transaction=True)

STATE_MATRIX = "job_run_state_matrix"
STATE_MACHINE = "job_run_state_machine"

# The hardcoded result contract (the 4.4 mapping, restated independently):
# result state → (Hub JobStatus, audit action, lineage eventType, webhook
# fires, partial_failures flag).
RESULT_CELLS = [
    ("SUCCESS", "COMPLETED", "RUN_SUCCEEDED", "COMPLETE", False, False),
    ("SUCCESS_WITH_FAILURES", "COMPLETED", "RUN_SUCCEEDED", "COMPLETE", False, True),
    ("FAILED", "FAILED", "RUN_FAILED", "FAIL", True, False),
    ("TIMEDOUT", "FAILED", "RUN_FAILED", "FAIL", True, False),
    ("MAXIMUM_CONCURRENT_RUNS_REACHED", "FAILED", "RUN_FAILED", "FAIL", True, False),
    ("UPSTREAM_FAILED", "FAILED", "RUN_FAILED", "FAIL", True, False),
    ("CANCELED", "CANCELLED", "RUN_FAILED", "FAIL", True, False),
    ("UPSTREAM_CANCELED", "CANCELLED", "RUN_FAILED", "FAIL", True, False),
    ("EXCLUDED", "CANCELLED", "RUN_FAILED", "FAIL", True, False),
]

NON_TERMINAL_LIFECYCLE_STATES = [
    "PENDING",
    "QUEUED",
    "RUNNING",
    "TERMINATING",
    "WAITING_FOR_RETRY",
    "BLOCKED",
]


class TestJobRunStateFixtureIntegrity:
    """The state fixtures are the auditable contract — vocabulary-only
    payloads with internal consistency (the 3.10 fixture-integrity
    convention)."""

    def test_the_state_matrix_covers_the_whole_lifecycle_vocabulary(self):
        from hub.apps.databricks_admin.models import DatabricksJobRunLifecycleState

        matrix = load_fixture(STATE_MATRIX)
        vocabulary = set(DatabricksJobRunLifecycleState.values)
        for key, payload in matrix.items():
            state = payload["state"]
            assert state["life_cycle_state"] in vocabulary, key
            # The pure-lifecycle keys report exactly their key's state.
            if key in vocabulary:
                assert state["life_cycle_state"] == key, key

    def test_the_state_matrix_covers_the_whole_result_vocabulary(self):
        from hub.apps.databricks_admin.models import DatabricksJobRunResultState

        matrix = load_fixture(STATE_MATRIX)
        vocabulary = set(DatabricksJobRunResultState.values)
        terminated = [key for key in matrix if key.startswith("TERMINATED_")]
        assert {key.removeprefix("TERMINATED_") for key in terminated} == vocabulary
        for key in terminated:
            result = matrix[key]["state"]["result_state"]
            assert result in vocabulary, key
            assert key == f"TERMINATED_{result}", key

    def test_the_state_matrix_run_ids_are_numeric_and_consistent(self):
        # The matrix describes ONE run's alternative states — the run id
        # is numeric and shared across every payload.
        matrix = load_fixture(STATE_MATRIX)
        run_ids = {payload["run_id"] for payload in matrix.values()}
        assert len(run_ids) == 1
        assert all(isinstance(run_id, int) for run_id in run_ids)

    def test_the_state_machine_steps_resolve_to_payloads_in_the_same_file(self):
        machine = load_fixture(STATE_MACHINE)
        assert set(machine["steps"]) <= set(machine) - {"steps"}, (
            "every step must name a payload in the SAME file"
        )

    def test_the_state_machine_walks_to_a_terminal_success(self):
        machine = load_fixture(STATE_MACHINE)
        steps = machine["steps"]
        # The first step is the run-now answer; the last is a terminal.
        assert "run_id" in machine[steps[0]]
        assert "state" not in machine[steps[0]]
        terminal = machine[steps[-1]]
        assert terminal["state"]["life_cycle_state"] == "TERMINATED"
        assert terminal["state"]["result_state"] == "SUCCESS"


class TestJobRunPollStateMachine:
    """The poller follows the fixture's scripted ``runs/get`` state
    machine on the REAL stack (no mocks)."""

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

    def _audit_rows(self):
        from hub.apps.audit.models import AuditEvent

        return list(
            AuditEvent.objects.filter(tenant=self.tenant, resource_type="DATABRICKS_JOB").order_by(
                "timestamp"
            )
        )

    def _script(self, *payloads):
        RecordingHandler.json_script = [json.dumps(payload) for payload in payloads]

    @override_settings(
        CAPABILITY_FLAGS={"lineage.openlineage_export": True},
        OPENLINEAGE_PRODUCER_NAME="https://meshant.com/jobs/openlineage",
    )
    def test_run_now_poll_terminal_audit_roundtrip_on_the_fixture_state_machine(
        self, monkeypatch, local_http_server
    ):
        # The 4.8 acceptance: the FIXTURE's scripted state machine drives
        # the real poller to a terminal audit + lineage + cost estimate.
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = load_fixture_steps(STATE_MACHINE)

        job = self._run(client, poll_timeout_s=300)

        # The wire trail in order: run-now POST, then the poll GETs on
        # the pinned path carrying the run id.
        requests = RecordingHandler.requests
        assert requests[0]["method"] == "POST"
        assert requests[0]["path"] == "/api/2.1/jobs/run-now"
        assert json.loads(requests[0]["body"]) == {"job_id": self.mirror.job_id}
        gets = [r for r in requests[1:] if r["method"] == "GET"]
        assert len(gets) == 4, "the machine scripts four polls"
        assert all(r["path"] == "/api/2.1/jobs/runs/get?run_id=73001" for r in gets)

        # The real backoff: three sleeps (four polls) with the pinned
        # sequence 2.0 → 3.0 → 4.5.
        assert self.sleeper.delays == pytest.approx([2.0, 3.0, 4.5])

        # The Hub Job terminal state + the stored cost estimate from the
        # fixture's REAL run_duration / cluster_spec.
        from hub.apps.jobs.models import JobStatus

        assert job.databricks_run_id == 73001
        assert job.status == JobStatus.COMPLETED
        assert job.result_json["databricks_run_state"] == "SUCCESS"
        assert job.result_json["cost_estimate"]["duration_seconds"] == 90.0
        assert job.result_json["cost_estimate"]["size_factor"] == 2.0
        assert job.result_json["cost_estimate"]["estimated_cost"] == pytest.approx(
            90 / 3600 * 0.55 * 2.0
        )

        # The terminal audit: STARTED + SUCCEEDED, identifiers only.
        assert {e.action for e in self._audit_rows()} == {"RUN_STARTED", "RUN_SUCCEEDED"}

        # The OpenLineage COMPLETE event validates against the REAL schema.
        assert len(self.lineage.calls) == 1
        event = self.lineage.calls[0]["event"]
        from hub.apps.integrations.openlineage.translator import (
            validate_openlineage_event,
        )

        validate_openlineage_event(event)
        assert event["eventType"] == "COMPLETE"
        assert event["run"]["runId"] == f"databricks:{self.mirror.job_id}:73001"

        # A success fires NO webhook.
        assert self.webhooks.calls == []

    @pytest.mark.parametrize("lifecycle", NON_TERMINAL_LIFECYCLE_STATES)
    def test_every_non_terminal_lifecycle_state_keeps_polling(
        self, lifecycle, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        matrix = load_fixture(STATE_MATRIX)
        self._script(
            {"run_id": 9101},
            matrix[lifecycle],
            matrix[lifecycle],
            matrix[lifecycle],
            matrix["TERMINATED_SUCCESS"],
        )

        job = self._run(client, poll_timeout_s=300)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.COMPLETED, f"{lifecycle} must never end the poll"
        gets = [r for r in RecordingHandler.requests[1:] if r["method"] == "GET"]
        assert len(gets) == 4, "three state polls + the terminal poll"
        # The recorded backoff proves the state payloads were followed.
        assert self.sleeper.delays == pytest.approx([2.0, 3.0, 4.5])

    @pytest.mark.parametrize(
        ("lifecycle", "expected_status"),
        [
            # INTERNAL_ERROR carries a FAILED result — mapped, never invented.
            ("INTERNAL_ERROR", "FAILED"),
            # SKIPPED carries no result — absent result fails closed.
            ("SKIPPED", "FAILED"),
        ],
    )
    def test_anomalous_terminals_stop_the_poller_and_fail_closed(
        self, lifecycle, expected_status, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        matrix = load_fixture(STATE_MATRIX)
        self._script({"run_id": 9101}, matrix[lifecycle])

        job = self._run(client, poll_timeout_s=300)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert job.status == getattr(JobStatus, expected_status)
        assert job.result_json["databricks_run_state"] in ("FAILED", None)
        assert self.sleeper.delays == [], "the anomalous terminal ends the poll"
        gets = [r for r in RecordingHandler.requests[1:] if r["method"] == "GET"]
        assert len(gets) == 1, "exactly one poll before the anomalous terminal"

        if lifecycle == "SKIPPED":
            assert "terminal lifecycle state 'SKIPPED'" in job.error_message
            assert job.result_json["databricks_run_state"] is None

    @pytest.mark.parametrize(
        ("result", "job_status", "audit_action", "event_type", "webhook", "partial"),
        RESULT_CELLS,
    )
    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_the_whole_result_vocabulary_maps_to_documented_terminal_contracts(
        self,
        result,
        job_status,
        audit_action,
        event_type,
        webhook,
        partial,
        monkeypatch,
        local_http_server,
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        payload = load_fixture(STATE_MATRIX)[f"TERMINATED_{result}"]
        self._script({"run_id": 9101}, payload)

        job = self._run(client, poll_timeout_s=300)

        # The Hub Job status + the recorded result state.
        assert job.status == job_status, result
        assert job.result_json["databricks_run_state"] == result
        assert ("partial_failures" in job.result_json) is partial, result

        # The terminal audit action.
        assert {e.action for e in self._audit_rows()} == {"RUN_STARTED", audit_action}

        # The lineage event type + the error facet on failures.
        assert len(self.lineage.calls) == 1
        event = self.lineage.calls[0]["event"]
        assert event["eventType"] == event_type, result
        state_message = payload["state"].get("state_message")
        if event_type == "FAIL":
            expected_message = state_message or "the Databricks run failed"
            assert event["run"]["facets"]["errorMessage"]["message"] == expected_message

        # The webhook fires exactly once per terminal failure.
        assert len(self.webhooks.calls) == (1 if webhook else 0), result
        if webhook:
            notified = self.webhooks.calls[0]
            assert notified["result_state"] == result
            assert notified["run_id"] == "9101"

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_an_absent_result_at_terminated_fails_closed(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        self._script(
            {"run_id": 9101},
            {"job_id": "job-1", "run_id": 9101, "state": {"life_cycle_state": "TERMINATED"}},
        )

        job = self._run(client, poll_timeout_s=300)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "terminal lifecycle state 'TERMINATED'" in job.error_message
        assert job.result_json["databricks_run_state"] is None
        assert self.lineage.calls[0]["event"]["eventType"] == "FAIL"
        assert len(self.webhooks.calls) == 1

    @pytest.mark.parametrize(
        "state",
        [
            ["weird"],  # a non-object state is never a terminal state
            42,
        ],
    )
    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_a_non_object_state_payload_is_never_a_terminal_state(
        self, state, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        self._script({"run_id": 9101}, {"job_id": "job-1", "run_id": 9101, "state": state})

        job = self._run(client, poll_timeout_s=1)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "poll budget" in job.error_message, "the malformed payload fails closed"
        assert self.lineage.calls[0]["event"]["eventType"] == "FAIL"

    def test_a_missing_state_payload_is_never_a_terminal_state(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        self._script({"run_id": 9101}, {"job_id": "job-1", "run_id": 9101})

        job = self._run(client, poll_timeout_s=1)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "poll budget" in job.error_message

    def test_the_terminal_payload_wins_over_the_budget(self, monkeypatch, local_http_server):
        # The poller checks the terminal state BEFORE the budget — a
        # terminal answer on the first poll succeeds even at budget zero.
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        payload = load_fixture(STATE_MATRIX)["TERMINATED_SUCCESS"]
        self._script({"run_id": 9101}, payload)

        job = self._run(client, poll_timeout_s=0)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.COMPLETED
        assert self.sleeper.delays == []

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_a_mid_poll_classified_error_fails_the_job_closed(self, monkeypatch, local_http_server):
        # A persistent 5xx mid-poll (retry budget exhausted → classified
        # DatabricksServerError) must FAIL the Job closed — the poller
        # never strands a RUNNING Job with an unhandled client error.
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        self._script({"run_id": 9101})
        RecordingHandler.script = [200, 500]

        job = self._run(client, poll_timeout_s=300)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "DATABRICKS_SERVER_ERROR" in job.error_message
        assert job.databricks_run_id == 9101
        assert job.result_json["poll_error_code"] == "DATABRICKS_SERVER_ERROR"

        actions = {e.action for e in self._audit_rows()}
        assert actions == {"RUN_STARTED", "RUN_FAILED"}
        failed = next(e for e in self._audit_rows() if e.action == "RUN_FAILED")
        assert failed.details_json["reason"] == "poll_error"

        assert self.lineage.calls[0]["event"]["eventType"] == "FAIL"
        assert len(self.webhooks.calls) == 1

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_a_non_numeric_run_id_in_the_run_now_answer_fails_the_job_closed(
        self, monkeypatch, local_http_server
    ):
        # A malformed run-now answer (a non-numeric run id) must be a
        # classified dispatch failure — never a ValueError leak with the
        # Hub Job stranded in PENDING.
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        self._script({"run_id": "run-abc"})

        job = self._run(client, poll_timeout_s=300)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "DATABRICKS_API_ERROR" in job.error_message
        assert "run-abc" in job.error_message
        assert job.databricks_run_id is None
        assert job.result_json["dispatch_error_code"] == "DATABRICKS_API_ERROR"
        assert len(RecordingHandler.requests) == 1, "ZERO polling after the refusal"

        actions = {e.action for e in self._audit_rows()}
        assert actions == {"RUN_FAILED"}, "no STARTED row for a refused dispatch"
        failed = next(e for e in self._audit_rows() if e.action == "RUN_FAILED")
        assert failed.details_json["databricks_run_id"] == "run-abc", (
            "the raw id is kept for diagnosis — never invented"
        )

        assert self.lineage.calls[0]["event"]["eventType"] == "FAIL"
        assert len(self.webhooks.calls) == 1

    def test_an_out_of_range_run_id_fails_the_job_closed(self, monkeypatch, local_http_server):
        # An out-of-BigInteger-range id would raise a DataError on save —
        # classified instead, the Job fails closed.
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        huge_id = str(2**70)
        self._script({"run_id": huge_id})

        job = self._run(client, poll_timeout_s=300)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "DATABRICKS_API_ERROR" in job.error_message
        assert job.databricks_run_id is None
        assert len(RecordingHandler.requests) == 1

    @override_settings(
        CAPABILITY_FLAGS={"lineage.openlineage_export": True},
        OPENLINEAGE_PRODUCER_NAME="https://meshant.com/jobs/openlineage",
    )
    def test_a_dispatch_rejected_run_emits_the_fail_lineage_event(
        self, monkeypatch, local_http_server
    ):
        # The dispatch rejection is a terminal failure of the Hub Job —
        # the FAIL lineage event fires at ALL terminal-failure
        # chokepoints (dispatch rejection, terminal failure, budget).
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        self._script({"error_code": "PERMISSION_DENIED"})
        RecordingHandler.script = [403]

        job = self._run(client, poll_timeout_s=300)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert len(self.lineage.calls) == 1
        event = self.lineage.calls[0]["event"]
        from hub.apps.integrations.openlineage.translator import (
            validate_openlineage_event,
        )

        validate_openlineage_event(event)
        assert event["eventType"] == "FAIL"
        assert event["run"]["facets"]["errorMessage"]["message"] == job.error_message


class TestJobRunAuditTrail:
    """The run audit chokepoint's exact details + attribution."""

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

    def _rows(self, action):
        from hub.apps.audit.models import AuditEvent

        return list(
            AuditEvent.objects.filter(
                tenant=self.tenant, resource_type="DATABRICKS_JOB", action=action
            ).order_by("timestamp")
        )

    @override_settings(
        CAPABILITY_FLAGS={"lineage.openlineage_export": True},
        OPENLINEAGE_PRODUCER_NAME="https://meshant.com/jobs/openlineage",
    )
    def test_started_row_carries_the_exact_identifiers_and_actor(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = load_fixture_steps(STATE_MACHINE)

        job = self._run(client, poll_timeout_s=300)

        started = self._rows("RUN_STARTED")
        assert len(started) == 1
        row = started[0]
        assert row.actor_user_id == self.admin.id, "the dispatcher's attribution"
        assert str(row.resource_id) == str(job.id), "the Hub Job pk anchors the row"
        assert row.details_json == {
            "databricks_job_id": self.mirror.job_id,
            "databricks_run_id": "73001",
        }, "identifiers only — never task configuration material"

    @override_settings(
        CAPABILITY_FLAGS={"lineage.openlineage_export": True},
        OPENLINEAGE_PRODUCER_NAME="https://meshant.com/jobs/openlineage",
    )
    def test_terminal_row_carries_the_run_state_and_falls_back_to_the_creator(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = load_fixture_steps(STATE_MACHINE)

        job = self._run(client, poll_timeout_s=300)

        succeeded = self._rows("RUN_SUCCEEDED")
        assert len(succeeded) == 1
        row = succeeded[0]
        assert row.actor_user_id == job.created_by_id, (
            "the terminal row falls back to the Job's creator"
        )
        assert str(row.resource_id) == str(job.id)
        assert row.details_json == {
            "databricks_job_id": self.mirror.job_id,
            "databricks_run_id": "73001",
            "databricks_run_state": "SUCCESS",
        }

    def test_the_budget_row_carries_the_reason(self, monkeypatch, local_http_server):
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

        self._run(client, poll_timeout_s=1)

        failed = self._rows("RUN_FAILED")
        assert len(failed) == 1
        assert failed[0].details_json == {
            "databricks_job_id": self.mirror.job_id,
            "databricks_run_id": "9101",
            "reason": "poll_budget_exhausted",
        }

    def test_the_dispatch_rejection_row_carries_no_run_id(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [json.dumps({"error_code": "PERMISSION_DENIED"})]
        RecordingHandler.script = [403]

        job = self._run(client, poll_timeout_s=300)

        failed = self._rows("RUN_FAILED")
        assert len(failed) == 1
        assert str(failed[0].resource_id) == str(job.id)
        assert failed[0].details_json == {
            "databricks_job_id": self.mirror.job_id,
            "databricks_run_id": "[SANITIZED_EMPTY]",
        }, "a run that never dispatched carries NO invented run id (the audit"
        " sanitizer's empty-string sentinel — never a fabricated value)"

    def test_the_mid_poll_error_row_carries_the_reason(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        client = self._client(local_http_server)
        RecordingHandler.json_script = [json.dumps({"run_id": 9101})]
        RecordingHandler.script = [200, 500]

        self._run(client, poll_timeout_s=300)

        failed = self._rows("RUN_FAILED")
        assert len(failed) == 1
        assert failed[0].details_json == {
            "databricks_job_id": self.mirror.job_id,
            "databricks_run_id": "9101",
            "reason": "poll_error",
        }

    @override_settings(
        CAPABILITY_FLAGS={"lineage.openlineage_export": True},
        OPENLINEAGE_PRODUCER_NAME="https://meshant.com/jobs/openlineage",
    )
    def test_two_runs_of_the_same_job_emit_isolated_row_sets(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        client = self._client(local_http_server)

        RecordingHandler.json_script = load_fixture_steps(STATE_MACHINE)
        first = self._run(client, poll_timeout_s=300)
        RecordingHandler.json_script = load_fixture_steps(STATE_MACHINE)
        second = self._run(client, poll_timeout_s=300)

        for job in (first, second):
            rows = [
                e
                for e in self._rows("RUN_STARTED") + self._rows("RUN_SUCCEEDED")
                if str(e.resource_id) == str(job.id)
            ]
            assert len(rows) == 2, "one STARTED + one SUCCEEDED per run"
            started = next(e for e in rows if e.action == "RUN_STARTED")
            succeeded = next(e for e in rows if e.action == "RUN_SUCCEEDED")
            assert started.timestamp <= succeeded.timestamp, "the order is per-run"
            assert (
                started.details_json["databricks_run_id"]
                == succeeded.details_json["databricks_run_id"]
                == "73001"
            )


class TestAllowlistPassthrough:
    """The lifecycle boundary (4.6) passes the 4.3 allowlist through —
    a refused job definition performs ZERO operations and emits NOTHING."""

    def test_the_lifecycle_service_refuses_a_forbidden_kind_with_zero_calls_and_zero_audit(
        self, local_http_server
    ):
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.jobs_client import (
            DatabricksJobsClient,
            DatabricksJobTaskError,
        )
        from hub.apps.databricks_admin.jobs_lifecycle import create_databricks_job

        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)

        client = DatabricksJobsClient(
            DatabricksApiClient(
                base_url=f"http://127.0.0.1:{local_http_server}",
                tenant_id=str(self.tenant.id),
                credential_config={"token": "dapi-jobs"},
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
                use_breaker=False,
            )
        )

        with pytest.raises(DatabricksJobTaskError) as excinfo:
            create_databricks_job(
                self.workspace,
                client=client,
                name="dbt-job",
                tasks=[{"task_key": "dbt", "dbt_task": {"commands": ["run"]}}],
                actor_user=self.admin,
            )
        assert excinfo.value.code == "DATABRICKS_JOB_TASK_FORBIDDEN"
        assert RecordingHandler.requests == [], "ZERO jobs API calls"

        from hub.apps.audit.models import AuditEvent

        assert not AuditEvent.objects.filter(
            tenant=self.tenant, resource_type="DATABRICKS_JOB"
        ).exists(), "a refused job emits NOTHING"


class TestCostEstimateRateOverride:
    """The cost-estimate DBH rate comes from settings (the 4.4-review
    observation (2) — the override path is now pinned)."""

    def test_the_declared_settings_rate_feeds_the_estimate(self):
        from django.conf import settings

        from hub.apps.databricks_admin.job_runs import estimate_run_cost

        payload = load_fixture(STATE_MATRIX)["TERMINATED_SUCCESS"]
        estimate = estimate_run_cost(payload)
        assert estimate["dbh_rate"] == settings.DATABRICKS_JOB_COST_ESTIMATE_DBH_RATE

    @override_settings(DATABRICKS_JOB_COST_ESTIMATE_DBH_RATE=1.0)
    def test_the_rate_override_drives_the_stored_estimate(self):
        from hub.apps.databricks_admin.job_runs import estimate_run_cost

        payload = load_fixture(STATE_MATRIX)["TERMINATED_SUCCESS"]
        estimate = estimate_run_cost(payload)
        assert estimate["dbh_rate"] == 1.0
        # duration 60s / 3600 x 1.0 x (1 + 0.5 x 2 workers) = 0.033333
        # (the estimator rounds to 6 decimals — pinned at the rounded value)
        assert estimate["estimated_cost"] == round(60 / 3600 * 1.0 * 2.0, 6)
