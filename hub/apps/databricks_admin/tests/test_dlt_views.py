"""TDD pins for the DLT pipeline management views (openspec
add-databricks-dlt-pipelines task 10.7) — the SAME API surface the DLT
page (U5) and the `dlt` CLI ride.

The views gate on the 0.12 flag discipline (`databricks_dlt_pipelines_enabled`
+ the master control-plane gate), list from the 10.2 mirror (zero
network reads), gate creates through the REGISTERED
`databricks.dlt.create` chain (the 10.4 registry — a refusal is the
chain's classified code with ZERO pipelines API calls), start with the
conflict gate fail-fast (a non-terminal update → 409
`DATABRICKS_DLT_UPDATE_CONFLICT`, zero API calls) shipping the refresh
semantics verbatim through the 10.3 client, and stop as a no-op when
the mirror reports IDLE (the D4 discipline).

No mocks: real Postgres rows (tenant/workspace/mirror rows + RBAC) and
the PRODUCTION client against a REAL threaded local HTTP server via the
view's client factory seam (the 0.8 `_build_probe_client` convention —
the factory is redirected to the local transport, the client itself is
production). The chain is the REAL registered chain
(`chain_registry`'s `databricks.dlt.create` → chains.py's steps).
"""

import json
import uuid

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

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


def _enable_flags(tenant):
    tenant.databricks_control_plane_enabled = True
    tenant.databricks_dlt_pipelines_enabled = True
    tenant.save(
        update_fields=["databricks_control_plane_enabled", "databricks_dlt_pipelines_enabled"]
    )


class TestDltViews(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant, name=f"ws-dlt-v-{uuid.uuid4().hex[:8]}")
        _enable_flags(self.tenant)
        self.admin = _make_user(
            self.tenant, f"dlt-admin-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.client = _api_client(self.admin)

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
        # local transport — the client itself is the production client.
        def _local_client(_workspace, _credential=None):
            from hub.apps.databricks_admin.client import DatabricksApiClient
            from hub.apps.databricks_admin.pipelines_client import DatabricksPipelinesClient

            return DatabricksPipelinesClient(
                DatabricksApiClient(
                    base_url=f"http://127.0.0.1:{self.port}",
                    tenant_id=str(self.tenant.id),
                    credential_config={"token": "dapi-views"},
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

    def _url(self, name, **kwargs):
        return reverse(name, kwargs=kwargs)

    def _list(self, workspace_id):
        return self.client.get(self._url("dlt-pipeline-list", workspace_id=workspace_id))

    def _start(self, workspace_id, pipeline_id, payload=None):
        return self.client.post(
            self._url("dlt-pipeline-start", workspace_id=workspace_id, pipeline_id=pipeline_id),
            data=json.dumps(payload or {"full_refresh": True}),
            content_type="application/json",
        )

    def _stop(self, workspace_id, pipeline_id):
        return self.client.post(
            self._url("dlt-pipeline-stop", workspace_id=workspace_id, pipeline_id=pipeline_id)
        )

    # ── flag gating ────────────────────────────────────────────────────

    def test_flag_registry_entry_exists_with_off_defaults(self):
        from hub.apps.tenants.feature_flag_registry import get_flag

        entry = get_flag("databricks_dlt_pipelines_enabled")
        assert entry is not None, "the D7 surface gate must be a registered flag"
        assert entry.default_new_tenants is False
        assert entry.default_existing_tenants is False

    def test_the_surface_refuses_while_the_flag_is_off(self):
        self.tenant.databricks_dlt_pipelines_enabled = False
        self.tenant.save(update_fields=["databricks_dlt_pipelines_enabled"])
        response = self._list(self.workspace.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_PIPELINES_DISABLED"

    # ── list (mirror-first) ────────────────────────────────────────────

    def test_list_returns_the_mirror_rows_with_latest_updates(self):
        pipeline = _make_pipeline(self.workspace)
        _make_update(pipeline, update_id="u-run", state="RUNNING")
        _make_update(pipeline, update_id="u-done", state="COMPLETED")
        _make_pipeline(self.workspace, pipeline_id="p-2", name="hourly-dlt", state="ACTIVE")

        response = self._list(self.workspace.id)

        assert response.status_code == 200
        items = response.json()["results"]
        assert len(items) == 2
        p1 = next(item for item in items if item["pipeline_id"] == "p-1")
        assert p1["state"] == "IDLE"
        assert p1["name"] == "nightly-dlt"
        assert p1["latest_update_state"] == "COMPLETED", (
            "the latest update state is the most recent reported terminal"
        )
        assert RecordingHandler.requests == [], "the list is mirror-first — ZERO network reads"

    def test_a_credential_less_workspace_passes_through_the_factory(self):
        # No credential rows on the workspace — the factory builds the
        # client WITHOUT auth kwargs (the 1.3 UC convention): the
        # workspace's own 401 classifies, never a misclassified 403.
        from hub.apps.databricks_admin.dlt_views import _build_dlt_client

        client = _build_dlt_client(self.workspace)
        assert client is not None

    def test_a_foreign_workspace_is_a_404(self):
        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        other_ws = _make_workspace(other_tenant, name=f"ws-other-{uuid.uuid4().hex[:8]}")
        response = self._list(other_ws.id)
        assert response.status_code == 404

    # ── create (chain-gated) ───────────────────────────────────────────

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

    def test_create_passes_the_chain_and_ships_the_settings_exactly(self):
        RecordingHandler.json_script.append(json.dumps({"pipeline_id": "p-new"}))
        response = self.client.post(
            self._url("dlt-pipeline-list", workspace_id=self.workspace.id),
            data=json.dumps(self._create_payload()),
            content_type="application/json",
        )
        assert response.status_code == 201, response.json()
        assert response.json()["pipeline_id"] == "p-new"
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.0/pipelines"
        assert json.loads(recorded["body"]) == self._create_payload(), (
            "the chain-validated settings ship EXACTLY"
        )

    def test_create_refuses_an_unallowlisted_setting_with_zero_calls(self):
        response = self.client.post(
            self._url("dlt-pipeline-list", workspace_id=self.workspace.id),
            data=json.dumps(self._create_payload(serverless=True)),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_SETTING_FORBIDDEN"
        assert "serverless" in response.json()["error"]["message"]
        assert RecordingHandler.requests == [], "a chain refusal makes ZERO pipelines API calls"

    def test_create_refuses_a_policy_less_cluster_with_zero_calls(self):
        payload = self._create_payload(clusters=[{"label": "default", "num_workers": 0}])
        response = self.client.post(
            self._url("dlt-pipeline-list", workspace_id=self.workspace.id),
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_CLUSTER_POLICY_REQUIRED"
        assert RecordingHandler.requests == [], "the policy gate refuses BEFORE any API call"

    # ── start (conflict gate + verbatim refresh semantics) ─────────────

    def test_start_conflicts_while_an_update_is_active(self):
        pipeline = _make_pipeline(self.workspace)
        _make_update(pipeline, state="RUNNING")
        response = self._start(self.workspace.id, pipeline.pipeline_id)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DATABRICKS_DLT_UPDATE_CONFLICT"
        assert RecordingHandler.requests == [], (
            "the conflict gate is the fail-fast — ZERO API calls"
        )

    def test_start_ships_the_refresh_semantics_verbatim(self):
        pipeline = _make_pipeline(self.workspace)
        RecordingHandler.json_script.append(json.dumps({"update_id": "u-new"}))
        response = self._start(
            self.workspace.id,
            pipeline.pipeline_id,
            {"full_refresh": False, "refresh_selection": {"tables": ["bronze_customers"]}},
        )
        assert response.status_code == 202, response.json()
        assert response.json()["update_id"] == "u-new"
        recorded = RecordingHandler.requests[-1]
        assert recorded["path"] == "/api/2.0/pipelines/p-1/updates"
        assert json.loads(recorded["body"]) == {
            "full_refresh": False,
            "refresh_selection": {"tables": ["bronze_customers"]},
        }

    def test_start_refuses_an_unknown_pipeline(self):
        response = self._start(self.workspace.id, "p-missing")
        assert response.status_code == 404

    # ── stop (IDLE no-op) ──────────────────────────────────────────────

    def test_stop_is_a_noop_when_the_mirror_reports_idle(self):
        pipeline = _make_pipeline(self.workspace, state="IDLE")
        response = self._stop(self.workspace.id, pipeline.pipeline_id)
        assert response.status_code == 200
        assert RecordingHandler.requests == [], (
            "an IDLE pipeline's stop issues ZERO API calls (the D4 discipline)"
        )

    def test_stop_stops_a_non_idle_pipeline(self):
        pipeline = _make_pipeline(self.workspace, state="ACTIVE")
        RecordingHandler.json_script.append("")
        response = self._stop(self.workspace.id, pipeline.pipeline_id)
        assert response.status_code == 200
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.0/pipelines/p-1/stop"
