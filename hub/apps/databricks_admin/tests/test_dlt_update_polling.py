"""TDD pins for the P10 test sweep (openspec
add-databricks-dlt-pipelines task 10.10) — the update-state polling
contracts the earlier suites left unpinned: the terminal-quartet
vocabulary agreement across the three shipped surfaces (the 10.3
client's poll, the 10.6 observability chokepoint, and the 10.2 model),
every quartet member terminating the production poll in ONE request,
a non-terminal state never terminating it (the budget sentinel), and
the terminal-semantics of the observability finalize for the
non-FAILED terminal states (CANCELED/TIMED_OUT).

No mocks: the poll pins drive the PRODUCTION ``DatabricksPipelinesClient``
over a REAL threaded local HTTP server (the 8.3 RecordingHandler
convention — scripted state envelopes, recorded paths asserted
exactly); the finalize pins run real Postgres rows + the REAL
observability chokepoint with the sanctioned seam recorders (the 10.6
convention).
"""

import json
import uuid

import pytest
from django.test import override_settings

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_dlt_update_observability import (
    _LineageRecorder,
    _seed_pipeline,
    _seed_update,
    _seed_workspace,
    _WebhookRecorder,
)
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = pytest.mark.django_db(transaction=True)


class TestTerminalVocabularyAgreement:
    """The terminal quartet is ONE set across every shipped surface —
    a drift between the layers is a silent mis-poll or a mis-billed
    update, never a runtime surprise."""

    def test_the_quartet_is_the_same_across_all_three_surfaces(self):
        from hub.apps.databricks_admin.dlt_update_observability import (
            _TERMINAL_UPDATE_STATES as observability_states,
        )
        from hub.apps.databricks_admin.models import (
            DatabricksDltPipelineUpdateState,
        )
        from hub.apps.databricks_admin.pipelines_client import (
            _TERMINAL_UPDATE_STATES as client_states,
        )

        quartet = {"COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"}
        assert set(client_states) == quartet, "the 10.3 poll's terminal set"
        assert set(observability_states) == quartet, "the 10.6 chokepoint's terminal set"
        model_terminal = {
            state for state in DatabricksDltPipelineUpdateState.values if state in quartet
        }
        assert model_terminal == quartet, (
            "the 10.2 model carries every quartet member in its reported vocabulary"
        )
        # Every OTHER reported state is still in flight — never terminal.
        for state in DatabricksDltPipelineUpdateState.values:
            if state not in quartet:
                assert state not in client_states
                assert state not in observability_states


class TestPollTerminatesOnEveryQuartetMember:
    """The production poll returns in ONE request for EACH terminal
    state — the vocabulary is the poll's only terminal authority."""

    def _client(self, port):
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.pipelines_client import DatabricksPipelinesClient

        return DatabricksPipelinesClient(
            DatabricksApiClient(
                base_url=f"http://127.0.0.1:{port}",
                tenant_id="t1",
                credential_config={"token": "dapi-poll"},
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
            )
        )

    @pytest.mark.parametrize(
        "terminal_state",
        ["COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"],
    )
    def test_each_quartet_member_terminates_the_poll(self, terminal_state, local_http_server):
        RecordingHandler.json_script = [json.dumps({"update_id": "u-1", "state": terminal_state})]
        payload = self._client(local_http_server).poll_update(
            "p-1", "u-1", timeout_seconds=5.0, interval_seconds=0.0
        )
        assert payload["state"] == terminal_state
        assert len(RecordingHandler.requests) == 1, (
            "an already-terminal update returns in ONE request"
        )

    def test_a_non_terminal_state_never_terminates_the_poll(self, local_http_server):
        # CREATING is a reported 12-state vocabulary member that is NOT
        # terminal — the poll must pass through it and exhaust the
        # budget with the sentinel (never a fabricated terminal).
        RecordingHandler.json_script.extend(
            [json.dumps({"update_id": "u-1", "state": "CREATING"})] * 200
        )
        from hub.apps.databricks_admin.pipelines_client import _PollBudgetExhausted

        with pytest.raises(_PollBudgetExhausted) as excinfo:
            self._client(local_http_server).poll_update(
                "p-1", "u-1", timeout_seconds=0.05, interval_seconds=0.0
            )
        assert excinfo.value.last_state == "CREATING", (
            "the sentinel reports the last REPORTED state — the poll never invents a terminal"
        )

    def test_list_events_carries_the_order_by_param(self, local_http_server):
        RecordingHandler.json_script = [json.dumps({"events": []})]
        self._client(local_http_server).list_events("p-1", order_by="timestamp")
        assert "order_by=timestamp" in RecordingHandler.requests[-1]["path"]


class TestFinalizeSemanticsForTheNonFailedTerminalStates:
    """CANCELED/TIMED_OUT are terminal but NOT failed: the chokepoint
    finalizes them (dbu + ledger row), the lineage reports FAIL (a
    terminal that did not complete is never a COMPLETE — the 4.4
    convention), and the webhook stays silent (the FAILED-only
    contract)."""

    def _setup(self, monkeypatch):
        require_dns()
        self.tenant, _admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)
        self.pipeline = _seed_pipeline(self.workspace, workers=0)
        self.lineage = _LineageRecorder()
        self.webhooks = _WebhookRecorder()

        from hub.apps.databricks_admin import dlt_update_observability

        monkeypatch.setattr(dlt_update_observability, "send_openlineage_event_async", self.lineage)
        monkeypatch.setattr(dlt_update_observability, "notify_dlt_update_failed", self.webhooks)

    def _finalize(self, update_row, events):
        from hub.apps.databricks_admin.dlt_update_observability import (
            finalize_terminal_update,
        )

        return finalize_terminal_update(
            workspace=self.workspace,
            pipeline=self.pipeline,
            update_row=update_row,
            events=events,
        )

    @pytest.mark.parametrize("terminal_state", ["CANCELED", "TIMED_OUT"])
    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_the_non_failed_terminal_states_finalize_with_fail_lineage_and_no_webhook(
        self, terminal_state, monkeypatch
    ):
        self._setup(monkeypatch)
        update = _seed_update(self.pipeline, state=terminal_state)
        events = [
            {
                "id": str(uuid.uuid4()),
                "sequence": {"sequence": 1},
                "timestamp": 0,
                "message": "update started",
                "event_type": "update_progress",
                "details": {"update_id": update.update_id},
            },
            {
                "id": str(uuid.uuid4()),
                "sequence": {"sequence": 2},
                "timestamp": 3_600_000,
                "message": f"update {terminal_state.lower()}",
                "event_type": "update_stopped",
                "details": {"update_id": update.update_id},
            },
        ]

        result = self._finalize(update, events)

        assert result["finalized"] is True
        update.refresh_from_db()
        assert float(update.dbu) == pytest.approx(1 * 0.55 * 1.0)  # 1h x rate x 1 worker-0 factor

        from hub.apps.databricks_admin.models import DatabricksCostLedger

        assert DatabricksCostLedger.objects.filter(tenant=self.tenant).count() == 1, (
            "every terminal state records its ledger row"
        )

        # The lineage: a non-COMPLETED terminal is a FAIL event (the 4.4
        # convention — never a fabricated COMPLETE).
        assert len(self.lineage.calls) == 1
        event = self.lineage.calls[0]["event"]
        assert event["eventType"] == "FAIL"
        assert "errorMessage" in event["run"]["facets"]

        # The webhook fires on FAILED ONLY — CANCELED/TIMED_OUT stay silent.
        assert self.webhooks.calls == []
