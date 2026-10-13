"""TDD pins for the DLT update terminal-transition observability
(openspec add-databricks-dlt-pipelines task 10.6) — the OpenLineage run
event, the events-derived DBU estimate into the P7 ledger through the
provider-agnostic cost-recording seam, and the
``databricks.dlt.update.failed`` webhook (design D6).

No mocks: real Postgres rows (tenant/workspace/pipeline/update mirror),
the PRODUCTION ``DatabricksApiClient`` against a REAL threaded local
HTTP server (scripted pipelines events envelopes), the REAL
cost-recording seam (the 7.5 registry with the registered ledger
writer — the ledger rows are read back), the REAL OpenLineage event
validated against the REAL schema, and the webhook fanned out through
the module-level seam (the ONE sanctioned patch point — the same
contracts/lineage_sync convention the 4.4 pins use).
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
        name=f"ws-dlt-{uuid.uuid4().hex[:6]}",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )


def _seed_pipeline(workspace, pipeline_id="dlp-1", workers=2):
    from hub.apps.databricks_admin.models import DatabricksDltPipeline

    # Unique-suffixed ids: the shared DB's flush teardown is unreliable
    # (suppressed sqlflush errors leak rows across runs) — a unique id
    # keeps leaked rows identifiable and cross-test collisions impossible.
    pipeline_id = f"{pipeline_id}-{uuid.uuid4().hex[:8]}"
    return DatabricksDltPipeline.objects.create(
        workspace=workspace,
        pipeline_id=pipeline_id,
        name="nightly-dlt",
        state="IDLE",
        channel="CURRENT",
        settings={
            "name": "nightly-dlt",
            "clusters": [{"label": "default", "num_workers": workers}],
        },
    )


def _seed_update(pipeline, update_id="upd-1", state="COMPLETED", dbu=None):
    from hub.apps.databricks_admin.models import DatabricksDltPipelineUpdate

    return DatabricksDltPipelineUpdate.objects.create(
        pipeline=pipeline,
        update_id=f"{update_id}-{uuid.uuid4().hex[:8]}",
        state=state,
        dbu=dbu,
    )


def _event(
    *, update_id="upd-1", timestamp=1000, message="update progressed", event_type="update_progress"
):
    return {
        "id": str(uuid.uuid4()),
        "sequence": {"sequence": 1},
        "timestamp": timestamp,
        "message": message,
        "event_type": event_type,
        "details": {"update_id": update_id},
    }


class _LineageRecorder:
    """The sanctioned seam recorder — captures every dispatch call."""

    def __init__(self, *, raise_on_call: bool = False):
        self.calls = []
        self.raise_on_call = raise_on_call

    def __call__(self, *, event, target_url, tenant_id):
        if self.raise_on_call:
            raise RuntimeError("lineage backend down")
        self.calls.append({"event": event, "target_url": target_url, "tenant_id": tenant_id})

    def delay(self, *, event, target_url, tenant_id):
        return self(event=event, target_url=target_url, tenant_id=tenant_id)


class _WebhookRecorder:
    def __init__(self, *, raise_on_call: bool = False):
        self.calls = []
        self.raise_on_call = raise_on_call

    def __call__(self, **kwargs):
        if self.raise_on_call:
            raise RuntimeError("webhook delivery down")
        self.calls.append(kwargs)
        return len(self.calls)


class TestEstimateDltUpdateCost:
    """The pure duration-x-size-x-rate estimate (design D6)."""

    def test_duration_workers_and_rate_drive_the_estimate(self):
        from hub.apps.databricks_admin.dlt_update_observability import (
            estimate_dlt_update_cost,
        )

        estimate = estimate_dlt_update_cost(duration_seconds=3600.0, workers=2, dbh_rate=0.55)
        assert estimate["duration_seconds"] == 3600.0
        assert estimate["size_factor"] == 2.0  # 1 + 0.5 x 2 workers
        assert estimate["dbh_rate"] == pytest.approx(0.55)
        assert estimate["estimated_cost"] == pytest.approx(1 * 0.55 * 2.0)
        assert estimate["formula"] == "duration_hours x dbh_rate x (1 + 0.5 x workers)"

    def test_malformed_workers_clamp_to_zero(self):
        from hub.apps.databricks_admin.dlt_update_observability import (
            estimate_dlt_update_cost,
        )

        estimate = estimate_dlt_update_cost(duration_seconds=3600.0, workers=-3, dbh_rate=0.55)
        assert estimate["size_factor"] == 1.0


class TestDeriveUpdateMetrics:
    """The events-derived duration + error message (never invented)."""

    def test_duration_spans_the_updates_events(self):
        from hub.apps.databricks_admin.dlt_update_observability import (
            derive_update_metrics,
        )

        metrics = derive_update_metrics(
            update_id="upd-1",
            state="COMPLETED",
            events=[_event(timestamp=1000), _event(timestamp=46000)],
            workers=2,
            dbh_rate=0.55,
        )
        assert metrics["duration_seconds"] == pytest.approx(45.0)
        assert metrics["matched_events"] == 2
        assert metrics["error_message"] is None

    def test_events_for_other_updates_are_excluded(self):
        from hub.apps.databricks_admin.dlt_update_observability import (
            derive_update_metrics,
        )

        metrics = derive_update_metrics(
            update_id="upd-1",
            state="COMPLETED",
            events=[
                _event(update_id="other", timestamp=0),
                _event(timestamp=1000),
                _event(timestamp=46000),
            ],
            workers=0,
            dbh_rate=0.55,
        )
        assert metrics["matched_events"] == 2
        assert metrics["duration_seconds"] == pytest.approx(45.0)

    def test_malformed_timestamps_and_junk_events_are_skipped(self):
        from hub.apps.databricks_admin.dlt_update_observability import (
            derive_update_metrics,
        )

        metrics = derive_update_metrics(
            update_id="upd-1",
            state="COMPLETED",
            events=[
                "junk",
                {"timestamp": "garbage", "details": {"update_id": "upd-1"}},
                {"timestamp": 1000, "details": "junk-details"},
                _event(timestamp=1000),
                _event(timestamp=46000),
            ],
            workers=0,
            dbh_rate=0.55,
        )
        assert metrics["matched_events"] == 2
        assert metrics["duration_seconds"] == pytest.approx(45.0)

    def test_no_events_yield_a_zero_duration_estimate(self):
        from hub.apps.databricks_admin.dlt_update_observability import (
            derive_update_metrics,
        )

        metrics = derive_update_metrics(
            update_id="upd-1", state="COMPLETED", events=[], workers=2, dbh_rate=0.55
        )
        assert metrics["duration_seconds"] == 0.0
        assert metrics["estimated_cost"] == 0.0
        assert metrics["matched_events"] == 0

    def test_the_error_message_is_the_updates_last_reported_event_message(self):
        from hub.apps.databricks_admin.dlt_update_observability import (
            derive_update_metrics,
        )

        metrics = derive_update_metrics(
            update_id="upd-1",
            state="FAILED",
            events=[
                _event(timestamp=1000, message="update started"),
                _event(timestamp=2000, message="Task failed: OOM", event_type="update_failed"),
            ],
            workers=0,
            dbh_rate=0.55,
        )
        assert metrics["error_message"] == "Task failed: OOM"

    def test_the_settings_rate_overrides_the_default(self):
        from hub.apps.databricks_admin.dlt_update_observability import (
            derive_update_metrics,
        )

        with override_settings(DATABRICKS_DLT_UPDATE_COST_ESTIMATE_DBH_RATE=1.10):
            metrics = derive_update_metrics(
                update_id="upd-1",
                state="COMPLETED",
                events=[_event(timestamp=1000), _event(timestamp=3601000)],
                workers=0,
                dbh_rate=None,
            )
        assert metrics["dbh_rate"] == pytest.approx(1.10)
        assert metrics["estimated_cost"] == pytest.approx(1 * 1.10 * 1.0)


class TestFinalizeTerminalUpdate:
    """The terminal-transition chokepoint on the REAL stack."""

    def _setup(self, monkeypatch, *, lineage=None, webhooks=None):
        require_dns()
        self.tenant, _admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)
        self.pipeline = _seed_pipeline(self.workspace)
        self.lineage = lineage if lineage is not None else _LineageRecorder()
        self.webhooks = webhooks if webhooks is not None else _WebhookRecorder()

        from hub.apps.databricks_admin import dlt_update_observability

        monkeypatch.setattr(dlt_update_observability, "send_openlineage_event_async", self.lineage)
        monkeypatch.setattr(dlt_update_observability, "notify_dlt_update_failed", self.webhooks)

    def _finalize(self, update_row, events, **kwargs):
        from hub.apps.databricks_admin.dlt_update_observability import (
            finalize_terminal_update,
        )

        return finalize_terminal_update(
            workspace=self.workspace,
            pipeline=self.pipeline,
            update_row=update_row,
            events=events,
            **kwargs,
        )

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_a_completed_update_sets_the_dbu_and_records_exactly_one_ledger_row(self, monkeypatch):
        self._setup(monkeypatch)
        update = _seed_update(self.pipeline, state="COMPLETED")
        events = [
            _event(update_id=update.update_id, timestamp=0),
            _event(update_id=update.update_id, timestamp=3_600_000),
        ]

        result = self._finalize(update, events)
        result_again = self._finalize(update, events)

        assert result["finalized"] is True
        assert result_again["finalized"] is False
        assert result_again["reason"] == "already_billed"

        update.refresh_from_db()
        # 1h x 0.55 x (1 + 0.5 x 2 workers) = 1.10
        assert float(update.dbu) == pytest.approx(1.10)
        assert update.error_message is None

        from hub.apps.databricks_admin.models import DatabricksCostLedger

        rows = list(DatabricksCostLedger.objects.filter(tenant=self.tenant))
        assert len(rows) == 1, "EXACTLY ONE ledger row per terminal update"
        row = rows[0]
        assert row.source == "dlt_update"
        assert float(row.units) == pytest.approx(1.10)
        assert row.workspace.id == self.workspace.id
        assert row.meta["pipeline_id"] == self.pipeline.pipeline_id
        assert row.meta["update_id"] == update.update_id
        assert row.meta["duration_seconds"] == pytest.approx(3600.0)

        # The COMPLETE lineage event (validated against the schema).
        assert len(self.lineage.calls) == 1
        event = self.lineage.calls[0]["event"]
        from hub.apps.integrations.openlineage.translator import (
            validate_openlineage_event,
        )

        validate_openlineage_event(event)
        assert event["eventType"] == "COMPLETE"
        assert event["run"]["runId"] == f"databricks:{self.pipeline.pipeline_id}:{update.update_id}"
        assert event["job"]["namespace"] == "meshant.databricks"
        assert self.lineage.calls[0]["tenant_id"] == str(self.tenant.id)

        # A COMPLETED update never fires the failure webhook.
        assert self.webhooks.calls == []

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_a_failed_update_fires_the_webhook_and_the_fail_lineage(self, monkeypatch):
        self._setup(monkeypatch)
        update = _seed_update(self.pipeline, state="FAILED")
        events = [
            _event(update_id=update.update_id, timestamp=1000, message="update started"),
            _event(
                update_id=update.update_id,
                timestamp=2000,
                message="Task failed: OOM",
                event_type="update_failed",
            ),
        ]

        self._finalize(update, events)

        update.refresh_from_db()
        assert update.error_message == "Task failed: OOM"

        # The FAIL lineage event carries the errorMessage facet.
        event = self.lineage.calls[0]["event"]
        from hub.apps.integrations.openlineage.translator import (
            validate_openlineage_event,
        )

        validate_openlineage_event(event)
        assert event["eventType"] == "FAIL"
        assert event["run"]["facets"]["errorMessage"]["message"] == "Task failed: OOM"

        # The databricks.dlt.update.failed webhook fired with attribution.
        assert len(self.webhooks.calls) == 1
        payload = self.webhooks.calls[0]
        assert payload["tenant_id"] == str(self.tenant.id)
        assert payload["workspace_id"] == str(self.workspace.id)
        assert payload["pipeline_id"] == self.pipeline.pipeline_id
        assert payload["update_id"] == update.update_id
        assert payload["state"] == "FAILED"
        assert payload["error_message"] == "Task failed: OOM"

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": False})
    def test_the_capability_gate_skips_lineage_when_disabled(self, monkeypatch):
        # The flag is explicitly OFF — the dispatch seam must never be
        # called (the fail-soft gate). (The test-env default is ON, so
        # the pin disables it explicitly rather than relying on the
        # environment.)
        self._setup(monkeypatch)
        update = _seed_update(self.pipeline, state="COMPLETED")
        events = [
            _event(update_id=update.update_id, timestamp=0),
            _event(update_id=update.update_id, timestamp=1000),
        ]

        self._finalize(update, events)

        assert self.lineage.calls == []
        update.refresh_from_db()
        assert update.dbu is not None, "the row still finalizes without lineage"

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_a_lineage_dispatch_failure_never_blocks_the_transition(self, monkeypatch):
        self._setup(monkeypatch, lineage=_LineageRecorder(raise_on_call=True))
        update = _seed_update(self.pipeline, state="COMPLETED")
        events = [
            _event(update_id=update.update_id, timestamp=0),
            _event(update_id=update.update_id, timestamp=1000),
        ]

        result = self._finalize(update, events)

        assert result["finalized"] is True
        update.refresh_from_db()
        assert update.dbu is not None
        from hub.apps.databricks_admin.models import DatabricksCostLedger

        assert DatabricksCostLedger.objects.filter(tenant=self.tenant).count() == 1

    def test_a_webhook_failure_never_blocks_the_transition(self, monkeypatch):
        self._setup(monkeypatch, webhooks=_WebhookRecorder(raise_on_call=True))
        update = _seed_update(self.pipeline, state="FAILED")
        events = [
            _event(update_id=update.update_id, timestamp=0),
            _event(update_id=update.update_id, timestamp=1000),
        ]

        result = self._finalize(update, events)

        assert result["finalized"] is True
        update.refresh_from_db()
        assert update.error_message is not None

    def test_a_non_terminal_update_is_a_no_op(self, monkeypatch):
        self._setup(monkeypatch)
        update = _seed_update(self.pipeline, state="RUNNING")
        events = [_event(update_id=update.update_id, timestamp=0)]

        result = self._finalize(update, events)

        assert result["finalized"] is False
        assert result["reason"] == "non_terminal"
        update.refresh_from_db()
        assert update.dbu is None
        assert self.lineage.calls == []
        assert self.webhooks.calls == []
        from hub.apps.databricks_admin.models import DatabricksCostLedger

        assert DatabricksCostLedger.objects.filter(tenant=self.tenant).count() == 0

    def test_an_already_billed_row_is_never_rebilled(self, monkeypatch):
        self._setup(monkeypatch)
        update = _seed_update(self.pipeline, state="COMPLETED", dbu="0.5")
        events = [
            _event(update_id=update.update_id, timestamp=0),
            _event(update_id=update.update_id, timestamp=3_600_000),
        ]

        result = self._finalize(update, events)

        assert result["finalized"] is False
        assert result["reason"] == "already_billed"
        update.refresh_from_db()
        assert float(update.dbu) == pytest.approx(0.5)
        from hub.apps.databricks_admin.models import DatabricksCostLedger

        assert DatabricksCostLedger.objects.filter(tenant=self.tenant).count() == 0


class TestFinalizePendingTerminalUpdates:
    """The observability pass over the mirrored fleet (the REAL client
    against a REAL local HTTP server)."""

    def _setup(self, monkeypatch):
        require_dns()
        self.tenant, _admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)
        self.lineage = _LineageRecorder()
        self.webhooks = _WebhookRecorder()

        from hub.apps.databricks_admin import dlt_update_observability

        monkeypatch.setattr(dlt_update_observability, "send_openlineage_event_async", self.lineage)
        monkeypatch.setattr(dlt_update_observability, "notify_dlt_update_failed", self.webhooks)

    def _client(self, port):
        from hub.apps.databricks_admin.client import DatabricksApiClient

        return DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id=str(self.tenant.id),
            credential_config={"token": "dapi-observability"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
        )

    def _run(self, port):
        from hub.apps.databricks_admin.dlt_update_observability import (
            finalize_pending_terminal_updates,
        )

        return finalize_pending_terminal_updates(
            workspace=self.workspace, client=self._client(port)
        )

    def test_the_pass_finalizes_every_terminal_unbilled_update(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        pipeline = _seed_pipeline(self.workspace)
        completed = _seed_update(pipeline, state="COMPLETED")
        failed = _seed_update(pipeline, state="FAILED")
        running = _seed_update(pipeline, state="RUNNING")
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "events": [
                        _event(update_id=completed.update_id, timestamp=0),
                        _event(update_id=completed.update_id, timestamp=1_800_000),
                        _event(update_id=failed.update_id, timestamp=0),
                        _event(
                            update_id=failed.update_id,
                            timestamp=900_000,
                            message="pipeline failure",
                            event_type="update_failed",
                        ),
                        _event(update_id=running.update_id, timestamp=0),
                    ]
                }
            )
        ]

        result = self._run(local_http_server)

        assert result == {"pipelines": 1, "finalized": 2, "already_billed": 0}
        completed.refresh_from_db()
        failed.refresh_from_db()
        running.refresh_from_db()
        # 0.5h x 0.55 x 2.0 = 0.55
        assert float(completed.dbu) == pytest.approx(0.55)
        assert float(failed.dbu) == pytest.approx(0.275)  # 0.25h x 0.55 x 2.0
        assert failed.error_message == "pipeline failure"
        assert running.dbu is None, "a non-terminal update is never finalized"

        from hub.apps.databricks_admin.models import DatabricksCostLedger

        assert DatabricksCostLedger.objects.filter(tenant=self.tenant).count() == 2
        assert len(self.lineage.calls) == 2
        assert {c["event"]["eventType"] for c in self.lineage.calls} == {"COMPLETE", "FAIL"}
        assert len(self.webhooks.calls) == 1
        assert self.webhooks.calls[0]["update_id"] == failed.update_id

    def test_the_pass_follows_event_page_tokens(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        pipeline = _seed_pipeline(self.workspace)
        update = _seed_update(pipeline, state="COMPLETED")
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "events": [_event(update_id=update.update_id, timestamp=0)],
                    "next_page_token": "tok-9",
                }
            ),
            json.dumps({"events": [_event(update_id=update.update_id, timestamp=3_600_000)]}),
        ]

        self._run(local_http_server)

        assert "page_token=tok-9" in RecordingHandler.requests[-1]["path"], (
            "the second page request carries the reported token"
        )
        update.refresh_from_db()
        assert float(update.dbu) == pytest.approx(1.10), "the duration spans BOTH pages"

    def test_a_repeating_page_token_fails_classified(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        pipeline = _seed_pipeline(self.workspace)
        update = _seed_update(pipeline, state="COMPLETED")
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "events": [_event(update_id=update.update_id, timestamp=0)],
                    "next_page_token": "stuck",
                }
            ),
            json.dumps(
                {
                    "events": [],
                    "next_page_token": "stuck",
                }
            ),
        ]

        from hub.apps.databricks_admin.client import DatabricksApiError

        with pytest.raises(DatabricksApiError) as excinfo:
            self._run(local_http_server)
        assert "repeating" in str(excinfo.value).lower(), (
            "the seen-token guard must fail classified, never loop forever"
        )
        update.refresh_from_db()
        assert update.dbu is None, "a failed pass never half-bills an update"

    def test_already_billed_rows_are_skipped(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        pipeline = _seed_pipeline(self.workspace)
        billed = _seed_update(pipeline, state="COMPLETED", dbu="0.25")
        unbilled = _seed_update(pipeline, state="COMPLETED")
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "events": [
                        _event(update_id=billed.update_id, timestamp=0),
                        _event(update_id=billed.update_id, timestamp=3_600_000),
                        _event(update_id=unbilled.update_id, timestamp=0),
                        _event(update_id=unbilled.update_id, timestamp=3_600_000),
                    ]
                }
            )
        ]

        result = self._run(local_http_server)

        assert result["finalized"] == 1
        billed.refresh_from_db()
        assert float(billed.dbu) == pytest.approx(0.25), "a billed row keeps its recorded DBU"
        from hub.apps.databricks_admin.models import DatabricksCostLedger

        assert DatabricksCostLedger.objects.filter(tenant=self.tenant).count() == 1

    def test_junk_event_shapes_are_skipped(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        pipeline = _seed_pipeline(self.workspace)
        update = _seed_update(pipeline, state="COMPLETED")
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "events": [
                        "junk",
                        {"no_timestamp": True},
                        _event(update_id=update.update_id, timestamp=0),
                        _event(update_id=update.update_id, timestamp=1_800_000),
                    ]
                }
            )
        ]

        self._run(local_http_server)

        update.refresh_from_db()
        assert float(update.dbu) == pytest.approx(0.55), "only the well-formed events measure"

    def test_the_ledger_source_is_registered(self):
        from hub.apps.databricks_admin.models import DatabricksCostLedgerSource

        assert DatabricksCostLedgerSource.DLT_UPDATE == "dlt_update"
        assert "dlt_update" in DatabricksCostLedgerSource.values

    def test_the_dlt_update_metric_is_registered(self):
        from hub.apps.databricks_admin import metrics

        # prometheus_client strips the `_total` suffix in the Python-side
        # name (the wire/PromQL name keeps it) — the drift pin reads
        # what prometheus actually reports.
        assert metrics.databricks_dlt_updates_total._name == "databricks_dlt_updates"
        # Best-effort by contract — never raises, even for an unknown outcome.
        metrics.record_dlt_update_outcome(
            "COMPLETED", tenant_id="t-metrics", workspace_id="w-metrics"
        )
