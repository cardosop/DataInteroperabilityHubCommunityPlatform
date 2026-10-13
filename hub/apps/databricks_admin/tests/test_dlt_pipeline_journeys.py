"""Journey pins for the P10 DLT pipeline management surface (openspec
add-databricks-dlt-pipelines task 10.9) — JOURNEY-DB-017 (Manage a DLT
Pipeline) + UC-DB-017 (Manage DLT Pipeline).

Class/method names are PINNED by the UC doc's "Phase P10 Test" field
(docs/mvpdocs/use-cases/UC-DB-017.md) — renaming them breaks the
docs↔test drift gates (GATE-28).

The journey spans the shipped P10 surface with NO mocks — real Postgres
rows (tenant/workspace/pipeline/update mirror + audit + ledger), the
REGISTERED `databricks.dlt.create` chain, and the PRODUCTION pipelines
client against a REAL threaded local HTTP server via the view's client
factory seam (the 0.8 `_build_probe_client` convention — the factory is
redirected to the local transport, the client itself is production).
The create → start → poll → stop round-trip runs through the shipped
views (the SAME surface the DLT page (U5) and the `dlt` CLI ride); the
conflict gate and the chain refusals fail fast with ZERO API calls; the
terminal transition goes through the REAL observability pass
(`finalize_pending_terminal_updates`) — exactly one terminal audit
event and EXACTLY ONE `dlt_update` ledger row per terminal update
(the 10.6 exactly-once discipline). The OpenLineage leg stays
capability-off under test settings (the REAL capability gate), so no
dispatch seam is patched — the journey runs the unmodified services.
"""

from __future__ import annotations

import http.server
import json
import threading
import uuid

import pytest
from django.test import TestCase, override_settings
from django.urls import reverse

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _api_client, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _make_pipeline(workspace, *, pipeline_id="p-1", state="IDLE", name="nightly-dlt"):
    from hub.apps.databricks_admin.models import DatabricksDltPipeline

    # Unique-suffixed ids: the shared DB's flush teardown is unreliable
    # (suppressed sqlflush errors leak rows across runs) — a unique id
    # keeps leaked rows identifiable and cross-test collisions impossible.
    return DatabricksDltPipeline.objects.create(
        workspace=workspace,
        pipeline_id=f"{pipeline_id}-{uuid.uuid4().hex[:8]}",
        name=name,
        state=state,
    )


def _make_update(pipeline, *, update_id="u-1", state="RUNNING"):
    from hub.apps.databricks_admin.models import DatabricksDltPipelineUpdate

    return DatabricksDltPipelineUpdate.objects.create(
        pipeline=pipeline,
        update_id=f"{update_id}-{uuid.uuid4().hex[:8]}",
        state=state,
    )


def _event(*, update_id, timestamp, sequence, message):
    return {
        "id": str(uuid.uuid4()),
        "sequence": {"sequence": sequence},
        "timestamp": timestamp,
        "message": message,
        "event_type": "update_progress",
        "details": {"update_id": update_id},
    }


@pytest.mark.journey("JOURNEY-DB-017")
@pytest.mark.uc("UC-DB-017")
class TestJOURNEYDB017ManageDLTPipeline(TestCase):
    """The shipped P10 journey: define → start → poll → stop with the
    chain, the conflict gate, the mirror, and the observability pass."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant, name=f"ws-dlt-jrn-{uuid.uuid4().hex[:8]}")
        self.tenant.databricks_control_plane_enabled = True
        self.tenant.databricks_dlt_pipelines_enabled = True
        self.tenant.save(
            update_fields=["databricks_control_plane_enabled", "databricks_dlt_pipelines_enabled"]
        )
        self.de = _make_user(
            self.tenant, f"dlt-jrn-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.client = _api_client(self.de)

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        self.server = server
        self.port = server.server_address[1]
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.thread.start()

        # The sanctioned seam: redirect the view's client factory to the
        # local transport — the client itself is the production client
        # (the 10.7 pin convention).
        def _local_client(_workspace, _credential=None):
            from hub.apps.databricks_admin.client import DatabricksApiClient
            from hub.apps.databricks_admin.pipelines_client import DatabricksPipelinesClient

            return DatabricksPipelinesClient(
                DatabricksApiClient(
                    base_url=f"http://127.0.0.1:{self.port}",
                    tenant_id=str(self.tenant.id),
                    credential_config={"token": "dapi-journey"},
                    timeout_ms=5000,
                    max_retries=1,
                    retry_base_delay=0.05,
                    retry_max_delay=0.1,
                )
            )

        from hub.apps.databricks_admin import dlt_views as dv

        dv._build_dlt_client = _local_client

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    # ── helpers ────────────────────────────────────────────────────────

    def _base_client(self):
        """The BASE client for the mirror/observability services (they
        take ``DatabricksApiClient``, not the pipelines wrapper)."""
        from hub.apps.databricks_admin.client import DatabricksApiClient

        return DatabricksApiClient(
            base_url=f"http://127.0.0.1:{self.port}",
            tenant_id=str(self.tenant.id),
            credential_config={"token": "dapi-journey"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
        )

    def _create_payload(self, **overrides):
        payload = {
            "name": "managed-dlt",
            "edition": "CORE",
            "channel": "CURRENT",
            "catalog": "meshant",
            "target": "gold",
            "continuous": False,
            "development": False,
            "clusters": [{"label": "default", "num_workers": 0, "policy_id": "pol-1"}],
        }
        payload.update(overrides)
        return payload

    def _start(self, pipeline_id, payload=None):
        return self.client.post(
            reverse(
                "dlt-pipeline-start",
                kwargs={"workspace_id": self.workspace.id, "pipeline_id": pipeline_id},
            ),
            data=json.dumps(payload or {"full_refresh": True}),
            content_type="application/json",
        )

    def _audit_rows(self, action):
        from hub.apps.audit.models import AuditEvent

        return list(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=action,
                resource_type="DATABRICKS_DLT_PIPELINE",
            ).order_by("timestamp")
        )

    def _refresh_mirror(self, *, pipeline_id, state, updates):
        """Script the mirror's read legs (list → get → updates) and run
        the REAL refresh — the rows land exactly as the API reported."""
        from hub.apps.databricks_admin.pipelines_mirror import refresh_dlt_mirror

        RecordingHandler.json_script.append(
            json.dumps({"statuses": [{"pipeline_id": pipeline_id}]})
        )
        RecordingHandler.json_script.append(
            json.dumps(
                {
                    "pipeline_id": pipeline_id,
                    "name": "managed-dlt",
                    "state": state,
                    "spec": {"channel": "CURRENT"},
                }
            )
        )
        RecordingHandler.json_script.append(json.dumps({"updates": updates}))
        return refresh_dlt_mirror(self.workspace, client=self._base_client())

    # ── the journey ────────────────────────────────────────────────────

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": False})
    def test_update_polling(self):
        """The acceptance round-trip on the REAL stack: the chain-gated
        create ships the settings exactly; the mirror records the
        pipeline; the start dispatches through the conflict gate; the
        poller follows the update to COMPLETED; the observability pass
        finalizes EXACTLY ONE terminal audit event + EXACTLY ONE
        `dlt_update` ledger row; the page's list leg answers
        mirror-first with the latest update state and ZERO network."""
        pipeline_id = "p-jrn"
        update_id = "u-jrn"

        # 1. create — the REGISTERED chain passes, the settings ship
        # EXACTLY, and one CREATED audit row lands.
        RecordingHandler.json_script.append(json.dumps({"pipeline_id": pipeline_id}))
        response = self.client.post(
            reverse("dlt-pipeline-list", kwargs={"workspace_id": self.workspace.id}),
            data=json.dumps(self._create_payload()),
            content_type="application/json",
        )
        assert response.status_code == 201, response.json()
        assert response.json()["pipeline_id"] == pipeline_id
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.0/pipelines"
        assert json.loads(recorded["body"]) == self._create_payload()
        assert len(self._audit_rows("DATABRICKS_DLT_PIPELINE_CREATED")) == 1

        # 2. the mirror reflects the workspace's pipelines (the API's
        # reported values, never invented).
        counters = self._refresh_mirror(pipeline_id=pipeline_id, state="IDLE", updates=[])
        assert counters["pipelines"]["created"] == 1

        # 3. start — the conflict gate passes (no active update), the
        # refresh semantics ship verbatim, and one STARTED row lands.
        RecordingHandler.json_script.append(json.dumps({"update_id": update_id}))
        response = self._start(pipeline_id)
        assert response.status_code == 202, response.json()
        assert response.json()["update_id"] == update_id
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == f"/api/2.0/pipelines/{pipeline_id}/updates"
        assert json.loads(recorded["body"]) == {"full_refresh": True}
        assert len(self._audit_rows("DATABRICKS_DLT_UPDATE_STARTED")) == 1

        # 4. poll — the production poller follows the reported states to
        # the terminal COMPLETED (the 12-state vocabulary's terminal
        # quartet, TIMED_OUT included).
        from hub.apps.databricks_admin.pipelines_client import DatabricksPipelinesClient

        RecordingHandler.json_script.append(
            json.dumps({"update_id": update_id, "state": "RUNNING"})
        )
        RecordingHandler.json_script.append(
            json.dumps({"update_id": update_id, "state": "COMPLETED"})
        )
        poller = DatabricksPipelinesClient(self._base_client())
        terminal = poller.poll_update(pipeline_id, update_id, interval_seconds=0)
        assert terminal["state"] == "COMPLETED"

        # 5. the mirror records the terminal update as reported.
        counters = self._refresh_mirror(
            pipeline_id=pipeline_id,
            state="IDLE",
            updates=[{"update_id": update_id, "state": "COMPLETED", "full_refresh": True}],
        )
        assert counters["updates"]["created"] == 1

        # 6. the observability pass finalizes the terminal update —
        # EXACTLY ONE terminal audit event (the exactly-once discipline)
        # and EXACTLY ONE `dlt_update` ledger row (stored, not billed).
        RecordingHandler.json_script.append(
            json.dumps(
                {
                    "events": [
                        _event(update_id=update_id, timestamp=0, sequence=1, message="started"),
                        _event(
                            update_id=update_id,
                            timestamp=3_600_000,
                            sequence=2,
                            message="completed",
                        ),
                    ]
                }
            )
        )
        from hub.apps.databricks_admin.dlt_update_observability import (
            finalize_pending_terminal_updates,
        )

        counters = finalize_pending_terminal_updates(
            workspace=self.workspace, client=self._base_client()
        )
        assert counters["finalized"] == 1

        from hub.apps.databricks_admin.models import (
            DatabricksCostLedger,
            DatabricksDltPipelineUpdate,
        )

        update_row = DatabricksDltPipelineUpdate.objects.get(update_id=update_id)
        assert update_row.state == "COMPLETED"
        # 1h x 0.55 x (1 + 0.5 x 0 workers... policy cluster carries
        # num_workers 0 → size factor 1) — the estimate is duration x
        # rate x size, derived from the reported events.
        assert float(update_row.dbu) > 0
        assert len(self._audit_rows("DATABRICKS_DLT_UPDATE_SUCCEEDED")) == 1
        assert len(self._audit_rows("DATABRICKS_DLT_UPDATE_FAILED")) == 0
        ledger_rows = list(DatabricksCostLedger.objects.filter(tenant=self.tenant))
        assert len(ledger_rows) == 1, "EXACTLY ONE ledger row per terminal update"
        assert ledger_rows[0].source == "dlt_update"

        # 7. the page's list leg answers mirror-first — the latest
        # update state resolves from the mirror with ZERO network reads.
        RecordingHandler.requests = []
        response = self.client.get(
            reverse("dlt-pipeline-list", kwargs={"workspace_id": self.workspace.id})
        )
        assert response.status_code == 200
        items = response.json()["results"]
        assert len(items) == 1
        assert items[0]["pipeline_id"] == pipeline_id
        assert items[0]["latest_update_state"] == "COMPLETED"
        assert RecordingHandler.requests == [], "the list is mirror-first — ZERO network reads"
        assert RecordingHandler.json_script == [], (
            "every API leg consumed exactly its scripted response — no stray calls"
        )

    def test_refusals_fail_fast_with_zero_network(self):
        """The chain refusals (unallowlisted setting, policy-less
        cluster, invalid channel) and the conflict gate answer with the
        classified codes and ZERO Pipelines API calls — and emit
        NOTHING (a refusal is not a performed operation)."""
        # unallowlisted setting
        response = self.client.post(
            reverse("dlt-pipeline-list", kwargs={"workspace_id": self.workspace.id}),
            data=json.dumps(self._create_payload(serverless=True)),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_SETTING_FORBIDDEN"

        # policy-less cluster
        response = self.client.post(
            reverse("dlt-pipeline-list", kwargs={"workspace_id": self.workspace.id}),
            data=json.dumps(self._create_payload(clusters=[{"label": "default"}])),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_CLUSTER_POLICY_REQUIRED"

        # invalid channel
        response = self.client.post(
            reverse("dlt-pipeline-list", kwargs={"workspace_id": self.workspace.id}),
            data=json.dumps(self._create_payload(channel="EXPERIMENTAL")),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_CHANNEL_INVALID"

        assert RecordingHandler.requests == [], "a chain refusal makes ZERO pipelines API calls"

        # the conflict gate — a non-terminal update on the mirror blocks
        # a second start with 409 and ZERO API calls.
        pipeline = _make_pipeline(self.workspace)
        _make_update(pipeline, state="RUNNING")
        response = self._start(pipeline.pipeline_id)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_UPDATE_CONFLICT"
        assert RecordingHandler.requests == [], (
            "the conflict gate is the fail-fast — ZERO API calls"
        )

        assert self._audit_rows("DATABRICKS_DLT_PIPELINE_CREATED") == []
        assert self._audit_rows("DATABRICKS_DLT_UPDATE_STARTED") == []

    def test_the_flag_gate_disables_the_surface(self):
        """With the D7 flag off, every leg answers the classified 403 —
        the page and the CLI alike are inert."""
        self.tenant.databricks_dlt_pipelines_enabled = False
        self.tenant.save(update_fields=["databricks_dlt_pipelines_enabled"])

        response = self.client.get(
            reverse("dlt-pipeline-list", kwargs={"workspace_id": self.workspace.id})
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_PIPELINES_DISABLED"

        pipeline = _make_pipeline(self.workspace)
        response = self._start(pipeline.pipeline_id)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_PIPELINES_DISABLED"
        assert RecordingHandler.requests == []

    def test_stop_cancels_an_active_update_and_is_a_noop_when_idle(self):
        """Stop cancels the active update through the stop endpoint; an
        IDLE pipeline's stop is a no-op with ZERO API calls."""
        from hub.apps.databricks_admin.models import DatabricksDltPipelineState

        idle = _make_pipeline(self.workspace, state=DatabricksDltPipelineState.IDLE)
        response = self.client.post(
            reverse(
                "dlt-pipeline-stop",
                kwargs={"workspace_id": self.workspace.id, "pipeline_id": idle.pipeline_id},
            )
        )
        assert response.status_code == 200
        assert response.json() == {"stopped": False, "reason": "idle"}
        assert RecordingHandler.requests == [], "the IDLE stop issues ZERO API calls"

        active = _make_pipeline(self.workspace, state=DatabricksDltPipelineState.ACTIVE)
        response = self.client.post(
            reverse(
                "dlt-pipeline-stop",
                kwargs={"workspace_id": self.workspace.id, "pipeline_id": active.pipeline_id},
            )
        )
        assert response.status_code == 200
        assert response.json() == {"stopped": True}
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == f"/api/2.0/pipelines/{active.pipeline_id}/stop"
