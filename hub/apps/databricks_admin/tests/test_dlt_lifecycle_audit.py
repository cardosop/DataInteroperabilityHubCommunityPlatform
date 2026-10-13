"""TDD pins for the DLT pipeline audit vocabulary (openspec
add-databricks-dlt-pipelines task 10.8) — the six
``DATABRICKS_DLT_*`` event constants + the emission chokepoints:

- PIPELINE_CREATED/UPDATED/DELETED emit from the DLT view actions
  (``databricks_admin.dlt_views`` — one row per PERFORMED operation;
  a chain/conflict refusal emits NOTHING),
- UPDATE_STARTED emits from the start action after the client's
  ``start_update`` succeeds,
- UPDATE_SUCCEEDED/FAILED emit from the terminal chokepoint
  (``dlt_update_observability.finalize_terminal_update`` —
  SUCCEEDED for COMPLETED; FAILED for FAILED/CANCELED/TIMED_OUT —
  the status != COMPLETED convention).

Emission is BEST-EFFORT (D5 / the Phase 273 contract): an audit-DB
outage never blocks the operation.

No mocks except the documented module-boundary seam patches (the 3.8
audit-outage convention — ``unittest.mock`` on ``audit.utils`` /
the observability dispatch seams, never on the unit under test): real
Postgres audit rows, real mirror rows, the REAL registered chain, and
the PRODUCTION client against a REAL threaded local HTTP server (the
10.7 view pin convention).
"""

import json
import uuid
from unittest import mock

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

    return DatabricksDltPipeline.objects.create(
        workspace=workspace, pipeline_id=pipeline_id, name=name, state=state
    )


def _make_update(pipeline, *, update_id="u-1", state="RUNNING"):
    from hub.apps.databricks_admin.models import DatabricksDltPipelineUpdate

    return DatabricksDltPipelineUpdate.objects.create(
        pipeline=pipeline, update_id=update_id, state=state
    )


class TestDltAuditEventRegistration:
    """All six constants exist with the exact values and are exported."""

    def test_all_six_constants_are_registered(self):
        from hub.apps.audit import event_types

        expected = {
            "DATABRICKS_DLT_PIPELINE_CREATED": "DATABRICKS_DLT_PIPELINE_CREATED",
            "DATABRICKS_DLT_PIPELINE_UPDATED": "DATABRICKS_DLT_PIPELINE_UPDATED",
            "DATABRICKS_DLT_PIPELINE_DELETED": "DATABRICKS_DLT_PIPELINE_DELETED",
            "DATABRICKS_DLT_UPDATE_STARTED": "DATABRICKS_DLT_UPDATE_STARTED",
            "DATABRICKS_DLT_UPDATE_SUCCEEDED": "DATABRICKS_DLT_UPDATE_SUCCEEDED",
            "DATABRICKS_DLT_UPDATE_FAILED": "DATABRICKS_DLT_UPDATE_FAILED",
        }
        for name, value in expected.items():
            assert getattr(event_types, name) == value, name
        for value in expected.values():
            assert value in event_types.__all__, f"{value} must be exported in __all__"

    def test_the_two_catalogue_rows_exist(self):
        """The error-code rows (DATABRICKS_DLT_UPDATE_CONFLICT 409 +
        DATABRICKS_DLT_PIPELINES_DISABLED 403) are catalogued — the
        task's error-code half ships WITH the audit half."""
        from pathlib import Path

        catalogue = Path("docs/api/error-codes.md").read_text()
        assert "| `DATABRICKS_DLT_UPDATE_CONFLICT` | 409 " in catalogue
        assert "| `DATABRICKS_DLT_PIPELINES_DISABLED` | 403 " in catalogue


class TestDltViewsAuditEmission(TestCase):
    """The view actions emit one row per performed operation."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant, name=f"ws-dlt-aud-{uuid.uuid4().hex[:8]}")
        self.tenant.databricks_control_plane_enabled = True
        self.tenant.databricks_dlt_pipelines_enabled = True
        self.tenant.save(
            update_fields=["databricks_control_plane_enabled", "databricks_dlt_pipelines_enabled"]
        )
        self.actor = _make_user(
            self.tenant, f"dlt-audit-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.client = _api_client(self.actor)

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
                    credential_config={"token": "dapi-audit"},
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

    def _audit_rows(self, action, resource_type="DATABRICKS_DLT_PIPELINE"):
        from hub.apps.audit.models import AuditEvent

        return list(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=action,
                resource_type=resource_type,
            ).order_by("timestamp")
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

    def test_create_emits_pipeline_created_with_identifiers_only(self):
        RecordingHandler.json_script.append(json.dumps({"pipeline_id": "p-new"}))
        response = self.client.post(
            reverse("dlt-pipeline-list", kwargs={"workspace_id": self.workspace.id}),
            data=json.dumps(self._create_payload()),
            content_type="application/json",
        )
        assert response.status_code == 201, response.json()

        rows = self._audit_rows("DATABRICKS_DLT_PIPELINE_CREATED")
        assert len(rows) == 1
        row = rows[0]
        assert row.actor_user_id == self.actor.id
        assert row.resource_id is None, "no mirror row exists yet — the id lives in details"
        assert row.details_json == {
            "pipeline_id": "p-new",
            "workspace_id": str(self.workspace.id),
        }, "identifiers only — never settings material"

    def test_a_chain_refusal_emits_nothing(self):
        response = self.client.post(
            reverse("dlt-pipeline-list", kwargs={"workspace_id": self.workspace.id}),
            data=json.dumps(self._create_payload(serverless=True)),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert self._audit_rows("DATABRICKS_DLT_PIPELINE_CREATED") == []
        assert RecordingHandler.requests == [], "a chain refusal makes ZERO pipelines API calls"

    def test_update_emits_pipeline_updated_with_the_mirror_row_id(self):
        mirror = _make_pipeline(self.workspace, pipeline_id="p-1")
        RecordingHandler.json_script.append("")
        response = self.client.put(
            reverse(
                "dlt-pipeline-detail",
                kwargs={"workspace_id": self.workspace.id, "pipeline_id": "p-1"},
            ),
            data=json.dumps(self._create_payload(name="managed-dlt-v2")),
            content_type="application/json",
        )
        assert response.status_code == 200, response.json()

        rows = self._audit_rows("DATABRICKS_DLT_PIPELINE_UPDATED")
        assert len(rows) == 1
        assert rows[0].resource_id == mirror.id, "the mirror row's pk anchors the event"
        assert rows[0].details_json == {
            "pipeline_id": "p-1",
            "workspace_id": str(self.workspace.id),
        }

    def test_update_runs_the_chain_and_refuses_with_zero_calls(self):
        """The D3 contract: an edit goes through the SAME allowlist
        validation — a refusal emits NOTHING and makes zero API calls."""
        _make_pipeline(self.workspace, pipeline_id="p-1")
        response = self.client.put(
            reverse(
                "dlt-pipeline-detail",
                kwargs={"workspace_id": self.workspace.id, "pipeline_id": "p-1"},
            ),
            data=json.dumps(self._create_payload(serverless=True)),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_SETTING_FORBIDDEN"
        assert self._audit_rows("DATABRICKS_DLT_PIPELINE_UPDATED") == []
        assert RecordingHandler.requests == []

    def test_destroy_emits_pipeline_deleted(self):
        mirror = _make_pipeline(self.workspace, pipeline_id="p-1")
        RecordingHandler.json_script.append("")
        response = self.client.delete(
            reverse(
                "dlt-pipeline-detail",
                kwargs={"workspace_id": self.workspace.id, "pipeline_id": "p-1"},
            )
        )
        assert response.status_code == 204, response.json() if response.content else response

        rows = self._audit_rows("DATABRICKS_DLT_PIPELINE_DELETED")
        assert len(rows) == 1
        assert rows[0].resource_id == mirror.id

    def test_start_emits_update_started(self):
        pipeline = _make_pipeline(self.workspace, pipeline_id="p-1")
        RecordingHandler.json_script.append(json.dumps({"update_id": "u-new"}))
        response = self.client.post(
            reverse(
                "dlt-pipeline-start",
                kwargs={"workspace_id": self.workspace.id, "pipeline_id": "p-1"},
            ),
            data=json.dumps({"full_refresh": True}),
            content_type="application/json",
        )
        assert response.status_code == 202, response.json()

        rows = self._audit_rows("DATABRICKS_DLT_UPDATE_STARTED")
        assert len(rows) == 1
        assert rows[0].details_json == {
            "pipeline_id": "p-1",
            "update_id": "u-new",
            "workspace_id": str(self.workspace.id),
        }
        assert rows[0].resource_id == pipeline.id, "the mirror pipeline row anchors the event"

    def test_the_conflict_refusal_emits_nothing(self):
        pipeline = _make_pipeline(self.workspace, pipeline_id="p-1")
        _make_update(pipeline, state="RUNNING")
        response = self.client.post(
            reverse(
                "dlt-pipeline-start",
                kwargs={"workspace_id": self.workspace.id, "pipeline_id": "p-1"},
            ),
            data=json.dumps({"full_refresh": True}),
            content_type="application/json",
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_UPDATE_CONFLICT"
        assert self._audit_rows("DATABRICKS_DLT_UPDATE_STARTED") == []
        assert RecordingHandler.requests == [], "the conflict gate fails fast — ZERO API calls"

    def test_audit_outage_never_blocks_the_create(self):
        # The Phase 273 best-effort contract: an audit-DB failure must
        # never fail the lifecycle operation itself (unittest.mock as a
        # context manager on the audit-utils seam — the 3.8 convention).
        import hub.apps.audit.utils as audit_utils

        def _explode(*_args, **_kwargs):
            raise RuntimeError("audit DB down")

        RecordingHandler.json_script.append(json.dumps({"pipeline_id": "p-new"}))
        with mock.patch.object(audit_utils, "create_audit_event", _explode):
            response = self.client.post(
                reverse("dlt-pipeline-list", kwargs={"workspace_id": self.workspace.id}),
                data=json.dumps(self._create_payload()),
                content_type="application/json",
            )
        assert response.status_code == 201, "the create completes even with the audit DB down"


class TestTerminalUpdateAudit(TestCase):
    """The terminal chokepoint emits SUCCEEDED/FAILED exactly once."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant, name=f"ws-dlt-term-{uuid.uuid4().hex[:8]}")
        self.pipeline = _make_pipeline(self.workspace, pipeline_id="p-1")

        from hub.apps.databricks_admin import dlt_update_observability

        # The observability dispatch seams are sanctioned patch points
        # (the 10.6 pin convention) — this suite asserts the AUDIT leg;
        # the lineage/webhook legs are the 10.6 suite's.
        self._lineage_patch = mock.patch.object(
            dlt_update_observability, "send_openlineage_event_async"
        )
        self._webhook_patch = mock.patch.object(
            dlt_update_observability, "notify_dlt_update_failed"
        )
        self._lineage_patch.start()
        self._webhook_patch.start()
        self.addCleanup(self._lineage_patch.stop)
        self.addCleanup(self._webhook_patch.stop)

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

    def _terminal_rows(self, action):
        from hub.apps.audit.models import AuditEvent

        return list(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=action,
                resource_type="DATABRICKS_DLT_PIPELINE",
            ).order_by("timestamp")
        )

    def _event(self, timestamp=1000):
        return {
            "id": str(uuid.uuid4()),
            "sequence": {"sequence": 1},
            "timestamp": timestamp,
            "message": "update progressed",
            "event_type": "update_progress",
            "details": {},
        }

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_a_completed_update_emits_succeeded(self):
        update = _make_update(self.pipeline, update_id="u-c", state="COMPLETED")
        result = self._finalize(update, [self._event()])
        assert result["finalized"] is True

        rows = self._terminal_rows("DATABRICKS_DLT_UPDATE_SUCCEEDED")
        assert len(rows) == 1
        assert rows[0].resource_id == update.id
        assert rows[0].details_json == {
            "pipeline_id": "p-1",
            "update_id": update.update_id,
            "workspace_id": str(self.workspace.id),
        }
        assert self._terminal_rows("DATABRICKS_DLT_UPDATE_FAILED") == []

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_a_failed_update_emits_failed(self):
        update = _make_update(self.pipeline, update_id="u-f", state="FAILED")
        result = self._finalize(update, [self._event()])
        assert result["finalized"] is True

        assert len(self._terminal_rows("DATABRICKS_DLT_UPDATE_FAILED")) == 1
        assert self._terminal_rows("DATABRICKS_DLT_UPDATE_SUCCEEDED") == []

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_canceled_and_timed_out_emit_failed(self):
        """The status != COMPLETED convention — the terminal quartet maps
        onto the two audit outcomes."""
        for state in ("CANCELED", "TIMED_OUT"):
            update = _make_update(self.pipeline, update_id=f"u-{state.lower()}", state=state)
            result = self._finalize(update, [self._event()])
            assert result["finalized"] is True

        assert len(self._terminal_rows("DATABRICKS_DLT_UPDATE_FAILED")) == 2
        assert self._terminal_rows("DATABRICKS_DLT_UPDATE_SUCCEEDED") == []

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_the_terminal_audit_never_blocks_the_transition(self):
        import hub.apps.audit.utils as audit_utils

        def _explode(*_args, **_kwargs):
            raise RuntimeError("audit DB down")

        update = _make_update(self.pipeline, update_id="u-o", state="COMPLETED")
        with mock.patch.object(audit_utils, "create_audit_event", _explode):
            result = self._finalize(update, [self._event()])
        assert result["finalized"] is True, (
            "an audit-DB outage never blocks the terminal transition"
        )

    @override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": True})
    def test_a_second_finalize_is_a_noop_and_emits_nothing_more(self):
        """The exactly-once guard: the second finalize returns early
        (already billed) — no second terminal audit row."""
        update = _make_update(self.pipeline, update_id="u-twice", state="COMPLETED")
        self._finalize(update, [self._event()])
        result = self._finalize(update, [self._event()])
        assert result["finalized"] is False

        assert len(self._terminal_rows("DATABRICKS_DLT_UPDATE_SUCCEEDED")) == 1
