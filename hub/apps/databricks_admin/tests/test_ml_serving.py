"""TDD pins for the flag-gated ML serving surface (openspec
add-databricks-ml-assets task 12.4) — design D5.

- ONE flag `databricks_ml_assets_enabled` (default off for new AND
  existing tenants — the 0.12 discipline) gates EVERY ML-asset
  endpoint incl. the Vector Search + serving half; a flag-off request
  refuses 403 `DATABRICKS_ML_ASSETS_DISABLED` with ZERO API calls (the
  gate helper the 12.6 views consume).
- The serving/vector endpoints ride the PINNED client (NEW
  `serving_endpoints.*` + `vector_search.endpoints.*` pins, 2.0) with
  the scoped half: create / list / delete + the endpoint-state mirror
  (`DatabricksMlServingEndpoint`, workspace-scoped indirect-FK RLS,
  the API-reported state — never invented).

No mocks: real Postgres rows (tenant/workspace/mirror), the PRODUCTION
client against a REAL threaded local HTTP server (the wire paths and
bodies asserted), the pg_policies scan, the REAL flag registry entry.
"""

import http.server
import json
import threading
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _client(port, tenant_id):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id=tenant_id,
        credential_config={"token": "dapi-serving"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
        use_breaker=False,
    )


def _server():
    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


class TestFlagGate:
    def test_the_flag_registry_entry_exists_with_off_defaults(self):
        from hub.apps.tenants.feature_flag_registry import get_flag

        entry = get_flag("databricks_ml_assets_enabled")
        assert entry is not None, "the D5 surface gate must be a registered flag"
        assert entry.default_new_tenants is False
        assert entry.default_existing_tenants is False

    def test_the_gate_refuses_while_off_with_the_classified_403(self):
        from types import SimpleNamespace

        from hub.apps.databricks_admin.ml_assets import MlAssetsDisabled, gate_ml_assets

        tenant = SimpleNamespace(databricks_ml_assets_enabled=False)
        view = SimpleNamespace(request=SimpleNamespace(tenant=tenant))
        with pytest.raises(MlAssetsDisabled) as excinfo:
            gate_ml_assets(view)
        assert excinfo.value.status_code == 403
        assert excinfo.value.detail["code"] == "DATABRICKS_ML_ASSETS_DISABLED"

    def test_a_flag_on_tenant_passes_the_gate(self):
        from types import SimpleNamespace

        from hub.apps.databricks_admin.ml_assets import gate_ml_assets

        tenant = SimpleNamespace(databricks_ml_assets_enabled=True)
        view = SimpleNamespace(request=SimpleNamespace(tenant=tenant))
        assert gate_ml_assets(view) is None

    def test_the_error_catalogue_row_exists(self):
        from pathlib import Path

        catalogue = Path("docs/api/error-codes.md").read_text()
        assert "| `DATABRICKS_ML_ASSETS_DISABLED` | 403 " in catalogue


class TestServingPins:
    def test_the_serving_and_vector_pins_are_registered(self):
        from hub.apps.databricks_admin import api_paths

        expected = {
            "serving_endpoints.create": "/api/2.0/serving-endpoints",
            "serving_endpoints.list": "/api/2.0/serving-endpoints",
            "serving_endpoints.delete": "/api/2.0/serving-endpoints/{name}",
            "vector_search.endpoints.create": "/api/2.0/vector-search/endpoints",
            "vector_search.endpoints.list": "/api/2.0/vector-search/endpoints",
            "vector_search.endpoints.delete": "/api/2.0/vector-search/endpoints/{name}",
        }
        for key, path in expected.items():
            assert api_paths.API_PATHS[key] == path, key
            assert api_paths.API_PATH_VERSIONS[key] == "2.0", key


class TestServingEndpointMirror(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _make_workspace(self.tenant, name=f"ws-serve-{uuid.uuid4().hex[:8]}")

    def test_the_model_is_importable_and_registers(self):
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        assert DatabricksMlServingEndpoint is not None

    def test_a_row_carries_the_reported_shape(self):
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        row = DatabricksMlServingEndpoint.objects.create(
            workspace=self.workspace,
            endpoint_type="SERVING",
            name="churn-endpoint",
            state="READY",
        )
        assert row.workspace_id == self.workspace.id
        assert row.endpoint_type == "SERVING"
        assert row.state == "READY"

    def test_the_name_is_unique_per_workspace_and_type(self):
        from django.db import IntegrityError

        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        DatabricksMlServingEndpoint.objects.create(
            workspace=self.workspace, endpoint_type="SERVING", name="e1"
        )
        with pytest.raises(IntegrityError):
            DatabricksMlServingEndpoint.objects.create(
                workspace=self.workspace, endpoint_type="SERVING", name="e1"
            )

    def test_the_rls_policy_exists_on_the_table(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT policyname FROM pg_policies WHERE tablename = %s",
                ["databricks_ml_serving_endpoints"],
            )
            assert cursor.fetchone() is not None, "the mirror table carries its RLS policy"


class TestMlServingService(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _make_workspace(self.tenant, name=f"ws-servesvc-{uuid.uuid4().hex[:8]}")

    def _endpoint_payload(self, name="churn-endpoint", state="NOT_UPDATING"):
        return {"name": name, "state": {"ready": state, "config_update": state}}

    def test_create_posts_and_mirrors_the_reported_state(self):
        from hub.apps.databricks_admin.ml_assets import create_serving_endpoint
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.json_script = [json.dumps(self._endpoint_payload())]

        row = create_serving_endpoint(
            _client(port, str(self.tenant.id)),
            workspace=self.workspace,
            name="churn-endpoint",
            config={"served_models": [{"model_name": "churn_model", "model_version": "1"}]},
        )

        assert row.name == "churn-endpoint"
        assert row.state == "NOT_UPDATING"
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.0/serving-endpoints"
        assert json.loads(recorded["body"]) == {
            "name": "churn-endpoint",
            "config": {"served_models": [{"model_name": "churn_model", "model_version": "1"}]},
        }
        assert DatabricksMlServingEndpoint.objects.filter(
            workspace=self.workspace, name="churn-endpoint"
        ).exists()

    def test_list_returns_the_payloads_and_upserts_the_mirror(self):
        from hub.apps.databricks_admin.ml_assets import list_serving_endpoints
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.json_script = [
            json.dumps(
                {"endpoints": [self._endpoint_payload("e1"), self._endpoint_payload("e2", "READY")]}
            )
        ]

        endpoints = list_serving_endpoints(
            _client(port, str(self.tenant.id)), workspace=self.workspace
        )

        assert len(endpoints) == 2
        assert endpoints[1]["state"]["ready"] == "READY"
        assert DatabricksMlServingEndpoint.objects.filter(workspace=self.workspace).count() == 2
        assert (
            DatabricksMlServingEndpoint.objects.get(workspace=self.workspace, name="e2").state
            == "READY"
        )

    def test_delete_deletes_and_drops_the_mirror_row(self):
        from hub.apps.databricks_admin.ml_assets import (
            create_serving_endpoint,
            delete_serving_endpoint,
        )
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [200, 200]
        RecordingHandler.json_script = [
            json.dumps(self._endpoint_payload()),
            "{}",
        ]
        client = _client(port, str(self.tenant.id))
        create_serving_endpoint(client, workspace=self.workspace, name="churn-endpoint", config={})
        delete_serving_endpoint(client, workspace=self.workspace, name="churn-endpoint")

        assert not DatabricksMlServingEndpoint.objects.filter(
            workspace=self.workspace, name="churn-endpoint"
        ).exists()
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "DELETE"
        assert recorded["path"] == "/api/2.0/serving-endpoints/churn-endpoint"

    def test_create_vector_search_endpoint_posts_the_vector_surface(self):
        from hub.apps.databricks_admin.ml_assets import create_vector_search_endpoint
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.json_script = [json.dumps({"name": "churn-index"})]

        row = create_vector_search_endpoint(
            _client(port, str(self.tenant.id)),
            workspace=self.workspace,
            name="churn-index",
            config={"endpoint_type": "STANDARD"},
        )

        assert row.endpoint_type == "VECTOR"
        recorded = RecordingHandler.requests[-1]
        assert recorded["path"] == "/api/2.0/vector-search/endpoints"
        assert json.loads(recorded["body"]) == {
            "name": "churn-index",
            "config": {"endpoint_type": "STANDARD"},
        }
        assert DatabricksMlServingEndpoint.objects.filter(
            workspace=self.workspace, endpoint_type="VECTOR", name="churn-index"
        ).exists()

    def test_an_api_rejection_propagates_the_classified_error(self):
        from hub.apps.databricks_admin.client import DatabricksApiError
        from hub.apps.databricks_admin.ml_assets import create_serving_endpoint

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [400]
        RecordingHandler.json_script = [json.dumps({"error_code": "INVALID_PARAMETER_VALUE"})]

        with pytest.raises(DatabricksApiError) as excinfo:
            create_serving_endpoint(
                _client(port, str(self.tenant.id)),
                workspace=self.workspace,
                name="bad-endpoint",
                config={},
            )
        assert excinfo.value.status_code == 400
