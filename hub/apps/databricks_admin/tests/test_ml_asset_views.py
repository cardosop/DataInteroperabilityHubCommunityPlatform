"""TDD pins for the ML-assets management surface (openspec
add-databricks-ml-assets task 12.6) — the views + the audit events per
operation (design D5/D7):

- the ONE flag gate (`gate_ml_assets` in ``initial`` — a flag-off
  tenant gets 403 ``DATABRICKS_ML_ASSETS_DISABLED`` with ZERO workspace
  API calls on EVERY endpoint of the surface),
- model register (the UC-DB-019 error table's 404 code) + version log +
  alias set/remove driving the 12.2 service on the pinned client,
- feature-table tag mark/unmark driving the 12.3 service (the mark's
  404-idempotent unmark still emits the vocabulary's single tag event),
- serving/vector create/list/delete driving the 12.4 service — the
  lists are mirror-first (ZERO network reads),
- ONE audit row per performed operation (the D7 vocabulary,
  resource_type=``DATABRICKS_ML_ASSET``, identifiers only in details,
  the mirror row's pk anchors ``resource_id``); a refusal emits NOTHING.

No mocks: real Postgres rows (workspace → catalog → schema → model →
version chain), the PRODUCTION client against a REAL threaded local
HTTP server (the wire paths/bodies asserted), real AuditEvent rows.
The ONLY seam: the view module's client factory
(``_build_ml_assets_client``) redirected to the local transport (the
10.7/10.8 convention).
"""

import json
import threading
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _api_client, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

FULL_NAME = "ml_catalog.ml_schema.churn_model"


def _seed_chain(tenant, *, workspace_name="ws-ml-views"):
    from hub.apps.databricks_admin.models import UCCatalog, UCModel, UCSchema

    workspace = _make_workspace(tenant, name=f"{workspace_name}-{uuid.uuid4().hex[:8]}")
    catalog = UCCatalog.objects.create(workspace=workspace, name="ml_catalog")
    schema = UCSchema.objects.create(catalog=catalog, name="ml_schema")
    model = UCModel.objects.create(schema=schema, name="churn_model", full_name=FULL_NAME)
    return workspace, model


class _MlViewsBase(TestCase):
    """The shared seam: a REAL threaded local HTTP server + the
    production client factory redirected to it (the 10.7 convention)."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.tenant.databricks_ml_assets_enabled = True
        self.tenant.save(update_fields=["databricks_ml_assets_enabled"])
        self.workspace, self.model = _seed_chain(self.tenant)
        self.actor = _make_user(
            self.tenant, f"ml-views-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.client = _api_client(self.actor)

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = __import__("http.server", fromlist=["ThreadingHTTPServer"]).ThreadingHTTPServer(
            ("127.0.0.1", 0), RecordingHandler
        )
        self.server = server
        self.port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()

        def _local_client(_workspace, _credential=None):
            from hub.apps.databricks_admin.client import DatabricksApiClient

            return DatabricksApiClient(
                base_url=f"http://127.0.0.1:{self.port}",
                tenant_id=str(self.tenant.id),
                credential_config={"token": "dapi-ml"},
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
            )

        import hub.apps.databricks_admin.ml_asset_views as views_module

        views_module._build_ml_assets_client = _local_client

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _audit_rows(self, action):
        from hub.apps.audit.models import AuditEvent

        return list(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=action,
                resource_type="DATABRICKS_ML_ASSET",
            ).order_by("timestamp")
        )


class TestMlAssetEventRegistration:
    """The eight D7 vocabulary constants exist and are exported."""

    def test_all_eight_constants_are_registered(self):
        from hub.apps.audit import event_types

        expected = {
            "DATABRICKS_ML_MODEL_REGISTERED": "DATABRICKS_ML_MODEL_REGISTERED",
            "DATABRICKS_ML_VERSION_LOGGED": "DATABRICKS_ML_VERSION_LOGGED",
            "DATABRICKS_ML_ALIAS_SET": "DATABRICKS_ML_ALIAS_SET",
            "DATABRICKS_ML_ALIAS_REMOVED": "DATABRICKS_ML_ALIAS_REMOVED",
            "DATABRICKS_ML_FEATURE_TAG_SET": "DATABRICKS_ML_FEATURE_TAG_SET",
            "DATABRICKS_ML_SERVING_CREATED": "DATABRICKS_ML_SERVING_CREATED",
            "DATABRICKS_ML_SERVING_UPDATED": "DATABRICKS_ML_SERVING_UPDATED",
            "DATABRICKS_ML_SERVING_DELETED": "DATABRICKS_ML_SERVING_DELETED",
        }
        for name, value in expected.items():
            assert getattr(event_types, name) == value, name
        for value in expected.values():
            assert value in event_types.__all__, f"{value} must be exported in __all__"

    def test_the_error_catalogue_rows_exist(self):
        """The 12.6 classified codes are catalogued (the error-code
        catalogue gate — same-PR rows): the 403 flag code (12.4), the
        UC-DB-019 error table's 404, and the two 400 validation codes."""
        from pathlib import Path

        catalogue = Path("docs/api/error-codes.md").read_text()
        for row in (
            "| `DATABRICKS_ML_ASSETS_DISABLED` | 403 ",
            "| `DATABRICKS_UC_OBJECT_NOT_FOUND` | 404 ",
            "| `DATABRICKS_ML_INVALID_FULL_NAME` | 400 ",
            "| `DATABRICKS_ML_INVALID_CONFIG` | 400 ",
        ):
            assert row in catalogue, row


class TestMlAssetGate(_MlViewsBase):
    """The ONE flag gate — every endpoint refuses 403 with ZERO calls."""

    def _surface_endpoints(self):
        from django.urls import reverse

        ws = self.workspace.id
        return [
            ("get", reverse("ml-asset-models", kwargs={"workspace_id": ws}), {}),
            (
                "post",
                reverse("ml-asset-models", kwargs={"workspace_id": ws}),
                {"full_name": FULL_NAME},
            ),
            (
                "post",
                reverse(
                    "ml-asset-model-versions",
                    kwargs={"workspace_id": ws, "model_id": self.model.id},
                ),
                {"source": "dbfs:/ml/churn"},
            ),
            (
                "put",
                reverse(
                    "ml-asset-model-alias",
                    kwargs={"workspace_id": ws, "model_id": self.model.id, "alias": "champion"},
                ),
                {"version_num": 1},
            ),
            (
                "delete",
                reverse(
                    "ml-asset-model-alias",
                    kwargs={"workspace_id": ws, "model_id": self.model.id, "alias": "champion"},
                ),
                {},
            ),
            ("get", reverse("ml-asset-feature-tables", kwargs={"workspace_id": ws}), {}),
            (
                "post",
                reverse(
                    "ml-asset-feature-tag", kwargs={"workspace_id": ws, "table_id": uuid.uuid4()}
                ),
                {},
            ),
            (
                "delete",
                reverse(
                    "ml-asset-feature-tag", kwargs={"workspace_id": ws, "table_id": uuid.uuid4()}
                ),
                {},
            ),
            ("get", reverse("ml-asset-serving-endpoints", kwargs={"workspace_id": ws}), {}),
            (
                "post",
                reverse("ml-asset-serving-endpoints", kwargs={"workspace_id": ws}),
                {"name": "ep-1", "config": {}},
            ),
            (
                "delete",
                reverse(
                    "ml-asset-serving-endpoint-detail", kwargs={"workspace_id": ws, "name": "ep-1"}
                ),
                {},
            ),
            ("get", reverse("ml-asset-vector-search-endpoints", kwargs={"workspace_id": ws}), {}),
            (
                "post",
                reverse("ml-asset-vector-search-endpoints", kwargs={"workspace_id": ws}),
                {"name": "vep-1", "config": {}},
            ),
        ]

    def test_every_endpoint_refuses_403_with_zero_calls_while_the_flag_is_off(self):
        self.tenant.databricks_ml_assets_enabled = False
        self.tenant.save(update_fields=["databricks_ml_assets_enabled"])
        for method, url, payload in self._surface_endpoints():
            response = getattr(self.client, method)(
                url, data=json.dumps(payload) if payload else None, content_type="application/json"
            )
            assert response.status_code == 403, (method, url, response.json())
            assert response.json()["error"]["code"] == "DATABRICKS_ML_ASSETS_DISABLED", (
                method,
                url,
            )
        assert RecordingHandler.requests == [], "a flag-off surface makes ZERO workspace API calls"

    def test_a_flag_off_refusal_emits_nothing(self):
        self.tenant.databricks_ml_assets_enabled = False
        self.tenant.save(update_fields=["databricks_ml_assets_enabled"])
        response = self.client.post(
            f"/api/v1/databricks/workspaces/{self.workspace.id}/ml-assets/models/",
            data=json.dumps({"full_name": FULL_NAME}),
            content_type="application/json",
        )
        assert response.status_code == 403
        from hub.apps.audit.models import AuditEvent

        assert (
            AuditEvent.objects.filter(
                tenant=self.tenant, resource_type="DATABRICKS_ML_ASSET"
            ).count()
            == 0
        ), "a refusal emits NOTHING"


class TestMlAssetViews(_MlViewsBase):
    """The operations — wire paths/bodies, mirror writes, audit rows."""

    def _url(self, url_name, **kwargs):
        from django.urls import reverse

        return reverse(url_name, kwargs=kwargs)

    def test_model_list_is_mirror_first_with_zero_network(self):
        response = self.client.get(self._url("ml-asset-models", workspace_id=self.workspace.id))
        assert response.status_code == 200, response.json()
        results = response.json()["results"]
        assert [row["name"] for row in results] == ["churn_model"]
        assert results[0]["full_name"] == FULL_NAME
        assert results[0]["aliases"] == []
        assert RecordingHandler.requests == [], "the mirror-first list makes ZERO API calls"

    def test_register_creates_the_model_and_audits_with_the_mirror_row(self):
        RecordingHandler.script = [404, 200]
        RecordingHandler.json_script = [
            "{}",
            json.dumps({"registered_model": {"name": FULL_NAME}}),
        ]
        response = self.client.post(
            self._url("ml-asset-models", workspace_id=self.workspace.id),
            data=json.dumps({"full_name": FULL_NAME}),
            content_type="application/json",
        )
        assert response.status_code == 201, response.json()
        assert [r["path"] for r in RecordingHandler.requests] == [
            f"/api/2.0/mlflow/registered-models/get?name={FULL_NAME}",
            "/api/2.0/mlflow/registered-models/create",
        ]
        assert json.loads(RecordingHandler.requests[1]["body"]) == {"name": FULL_NAME}
        rows = self._audit_rows("DATABRICKS_ML_MODEL_REGISTERED")
        assert len(rows) == 1
        assert rows[0].actor_user_id == self.actor.id
        assert rows[0].resource_id == self.model.id, "the mirror row's pk anchors resource_id"
        assert rows[0].details_json == {
            "full_name": FULL_NAME,
            "workspace_id": str(self.workspace.id),
        }, "identifiers only"

    def test_register_an_existing_model_makes_no_create_call(self):
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [json.dumps({"registered_model": {"name": FULL_NAME}})]
        response = self.client.post(
            self._url("ml-asset-models", workspace_id=self.workspace.id),
            data=json.dumps({"full_name": FULL_NAME}),
            content_type="application/json",
        )
        assert response.status_code == 201, response.json()
        assert [r["method"] for r in RecordingHandler.requests] == ["GET"], (
            "an existing registered model skips the create"
        )
        assert len(self._audit_rows("DATABRICKS_ML_MODEL_REGISTERED")) == 1

    def test_register_with_a_malformed_full_name_refuses_400_with_zero_calls(self):
        response = self.client.post(
            self._url("ml-asset-models", workspace_id=self.workspace.id),
            data=json.dumps({"full_name": "only_two.parts"}),
            content_type="application/json",
        )
        assert response.status_code == 400, response.json()
        assert response.json()["error"]["code"] == "DATABRICKS_ML_INVALID_FULL_NAME"
        assert RecordingHandler.requests == []
        assert self._audit_rows("DATABRICKS_ML_MODEL_REGISTERED") == []

    def test_register_into_an_unmirrored_schema_refuses_the_classified_404(self):
        response = self.client.post(
            self._url("ml-asset-models", workspace_id=self.workspace.id),
            data=json.dumps({"full_name": "missing_catalog.ml_schema.some_model"}),
            content_type="application/json",
        )
        assert response.status_code == 404, response.json()
        assert response.json()["error"]["code"] == "DATABRICKS_UC_OBJECT_NOT_FOUND"
        assert RecordingHandler.requests == []

    def test_version_log_posts_mlflow_and_audits_the_version_row(self):
        RecordingHandler.script = [200, 200]
        RecordingHandler.json_script = [
            json.dumps({"registered_model": {"name": FULL_NAME}}),
            json.dumps(
                {
                    "model_version": {
                        "version": 7,
                        "source": "dbfs:/ml/churn",
                        "run_id": "run-abc",
                        "run_link": "https://adb-1/#mlflow/run/run-abc",
                        "status": "READY",
                    }
                }
            ),
        ]
        response = self.client.post(
            self._url(
                "ml-asset-model-versions", workspace_id=self.workspace.id, model_id=self.model.id
            ),
            data=json.dumps({"source": "dbfs:/ml/churn", "run_id": "run-abc"}),
            content_type="application/json",
        )
        assert response.status_code == 201, response.json()
        create_body = json.loads(RecordingHandler.requests[1]["body"])
        assert create_body == {"name": FULL_NAME, "source": "dbfs:/ml/churn", "run_id": "run-abc"}
        rows = self._audit_rows("DATABRICKS_ML_VERSION_LOGGED")
        assert len(rows) == 1
        from hub.apps.databricks_admin.models import UCModelVersion

        version_row = UCModelVersion.objects.get(model=self.model, version=7)
        assert rows[0].resource_id == version_row.id
        assert rows[0].details_json == {
            "full_name": FULL_NAME,
            "version": 7,
            "workspace_id": str(self.workspace.id),
        }
        self.model.refresh_from_db()
        assert self.model.latest_version == 7

    def test_version_log_on_an_unknown_model_refuses_the_classified_404(self):
        response = self.client.post(
            self._url(
                "ml-asset-model-versions", workspace_id=self.workspace.id, model_id=uuid.uuid4()
            ),
            data=json.dumps({"source": "dbfs:/ml/churn"}),
            content_type="application/json",
        )
        assert response.status_code == 404, response.json()
        assert response.json()["error"]["code"] == "DATABRICKS_UC_OBJECT_NOT_FOUND"
        assert RecordingHandler.requests == []

    def test_alias_set_puts_the_exact_path_and_audits(self):
        RecordingHandler.script = [200]
        RecordingHandler.json_script = ["{}"]
        response = self.client.put(
            self._url(
                "ml-asset-model-alias",
                workspace_id=self.workspace.id,
                model_id=self.model.id,
                alias="champion",
            ),
            data=json.dumps({"version_num": 7}),
            content_type="application/json",
        )
        assert response.status_code == 200, response.json()
        recorded = RecordingHandler.requests[0]
        assert recorded["method"] == "PUT"
        assert recorded["path"] == f"/api/2.1/unity-catalog/models/{FULL_NAME}/aliases/champion"
        assert json.loads(recorded["body"]) == {"version_num": 7}
        rows = self._audit_rows("DATABRICKS_ML_ALIAS_SET")
        assert len(rows) == 1
        assert rows[0].resource_id == self.model.id
        assert rows[0].details_json == {
            "full_name": FULL_NAME,
            "alias": "champion",
            "workspace_id": str(self.workspace.id),
        }
        self.model.refresh_from_db()
        assert self.model.aliases == [{"alias_name": "champion", "version_num": 7}]

    def test_alias_remove_deletes_and_audits(self):
        RecordingHandler.script = [200]
        response = self.client.delete(
            self._url(
                "ml-asset-model-alias",
                workspace_id=self.workspace.id,
                model_id=self.model.id,
                alias="champion",
            ),
        )
        assert response.status_code == 204, response.json() if response.content else "no body"
        recorded = RecordingHandler.requests[0]
        assert recorded["method"] == "DELETE"
        assert recorded["path"] == f"/api/2.1/unity-catalog/models/{FULL_NAME}/aliases/champion"
        rows = self._audit_rows("DATABRICKS_ML_ALIAS_REMOVED")
        assert len(rows) == 1
        assert rows[0].resource_id == self.model.id

    def test_a_workspace_404_on_alias_set_surfaces_the_classified_404(self):
        RecordingHandler.script = [404]
        response = self.client.put(
            self._url(
                "ml-asset-model-alias",
                workspace_id=self.workspace.id,
                model_id=self.model.id,
                alias="champion",
            ),
            data=json.dumps({"version_num": 7}),
            content_type="application/json",
        )
        assert response.status_code == 404, response.json()
        assert response.json()["error"]["code"] == "DATABRICKS_UC_OBJECT_NOT_FOUND"
        assert self._audit_rows("DATABRICKS_ML_ALIAS_SET") == [], "a rejection emits NOTHING"

    def test_feature_tables_list_is_mirror_derived_with_zero_network(self):
        from hub.apps.databricks_admin.models import UCTable

        UCTable.objects.create(
            schema=self.model.schema,
            name="churn_features",
            full_name=f"{self.model.schema.catalog.name}.{self.model.schema.name}.churn_features",
            tags=[{"key": "feature_store", "value": "true"}],
        )
        UCTable.objects.create(
            schema=self.model.schema,
            name="plain_table",
            full_name=f"{self.model.schema.catalog.name}.{self.model.schema.name}.plain_table",
            tags=[],
        )
        response = self.client.get(
            self._url("ml-asset-feature-tables", workspace_id=self.workspace.id)
        )
        assert response.status_code == 200, response.json()
        results = response.json()["results"]
        assert [row["name"] for row in results] == ["churn_features"], (
            "only the tagged table is a feature table"
        )
        assert RecordingHandler.requests == []

    def test_feature_tag_mark_posts_the_convention_and_audits(self):
        from hub.apps.databricks_admin.models import UCTable

        table = UCTable.objects.create(
            schema=self.model.schema,
            name="churn_features",
            full_name=f"{self.model.schema.catalog.name}.{self.model.schema.name}.churn_features",
        )
        RecordingHandler.script = [200]
        RecordingHandler.json_script = ["{}"]
        response = self.client.post(
            self._url("ml-asset-feature-tag", workspace_id=self.workspace.id, table_id=table.id),
            data="{}",
            content_type="application/json",
        )
        assert response.status_code == 200, response.json()
        recorded = RecordingHandler.requests[0]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.1/unity-catalog/entity-tag-assignments"
        assert json.loads(recorded["body"]) == {
            "entity_type": "tables",
            "entity_name": table.full_name,
            "tag_key": "feature_store",
            "tag_value": "true",
        }
        rows = self._audit_rows("DATABRICKS_ML_FEATURE_TAG_SET")
        assert len(rows) == 1
        assert rows[0].resource_id == table.id
        assert rows[0].details_json == {
            "full_name": table.full_name,
            "tag_key": "feature_store",
            "workspace_id": str(self.workspace.id),
        }

    def test_feature_tag_unmark_is_404_idempotent_and_still_audits(self):
        from hub.apps.databricks_admin.models import UCTable

        table = UCTable.objects.create(
            schema=self.model.schema,
            name="churn_features",
            full_name=f"{self.model.schema.catalog.name}.{self.model.schema.name}.churn_features",
        )
        RecordingHandler.script = [404]
        response = self.client.delete(
            self._url("ml-asset-feature-tag", workspace_id=self.workspace.id, table_id=table.id),
        )
        assert response.status_code == 204, response.json() if response.content else "no body"
        recorded = RecordingHandler.requests[0]
        assert recorded["method"] == "DELETE"
        assert (
            recorded["path"]
            == f"/api/2.1/unity-catalog/entity-tag-assignments/tables/{table.full_name}/tags/feature_store"
        )
        assert len(self._audit_rows("DATABRICKS_ML_FEATURE_TAG_SET")) == 1, (
            "the vocabulary's single tag event covers the unmark too"
        )

    def test_serving_create_posts_the_exact_body_and_audits_the_mirror_row(self):
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "name": "ep-1",
                    "state": {"ready": "READY"},
                    "config": {"served_models": []},
                }
            )
        ]
        response = self.client.post(
            self._url("ml-asset-serving-endpoints", workspace_id=self.workspace.id),
            data=json.dumps({"name": "ep-1", "config": {"served_models": []}}),
            content_type="application/json",
        )
        assert response.status_code == 201, response.json()
        recorded = RecordingHandler.requests[0]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.0/serving-endpoints"
        assert json.loads(recorded["body"]) == {"name": "ep-1", "config": {"served_models": []}}
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        mirror = DatabricksMlServingEndpoint.objects.get(workspace=self.workspace, name="ep-1")
        assert mirror.endpoint_type == "SERVING"
        assert mirror.state == "READY"
        rows = self._audit_rows("DATABRICKS_ML_SERVING_CREATED")
        assert len(rows) == 1
        assert rows[0].resource_id == mirror.id
        assert rows[0].details_json == {
            "name": "ep-1",
            "endpoint_type": "SERVING",
            "workspace_id": str(self.workspace.id),
        }

    def test_serving_create_without_a_name_refuses_400_with_zero_calls(self):
        response = self.client.post(
            self._url("ml-asset-serving-endpoints", workspace_id=self.workspace.id),
            data=json.dumps({"config": {}}),
            content_type="application/json",
        )
        assert response.status_code == 400, response.json()
        assert response.json()["error"]["code"] == "DATABRICKS_ML_INVALID_CONFIG"
        assert RecordingHandler.requests == []
        assert self._audit_rows("DATABRICKS_ML_SERVING_CREATED") == []

    def test_serving_list_is_mirror_first_with_zero_network(self):
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        DatabricksMlServingEndpoint.objects.create(
            workspace=self.workspace, endpoint_type="SERVING", name="ep-1", state="READY"
        )
        response = self.client.get(
            self._url("ml-asset-serving-endpoints", workspace_id=self.workspace.id)
        )
        assert response.status_code == 200, response.json()
        results = response.json()["results"]
        assert [row["name"] for row in results] == ["ep-1"]
        assert results[0]["endpoint_type"] == "SERVING"
        assert results[0]["state"] == "READY"
        assert RecordingHandler.requests == []

    def test_serving_delete_drops_the_mirror_row_and_audits(self):
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        DatabricksMlServingEndpoint.objects.create(
            workspace=self.workspace, endpoint_type="SERVING", name="ep-1", state="READY"
        )
        RecordingHandler.script = [200]
        response = self.client.delete(
            self._url(
                "ml-asset-serving-endpoint-detail", workspace_id=self.workspace.id, name="ep-1"
            ),
        )
        assert response.status_code == 204, response.json() if response.content else "no body"
        recorded = RecordingHandler.requests[0]
        assert recorded["method"] == "DELETE"
        assert recorded["path"] == "/api/2.0/serving-endpoints/ep-1"
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        assert not DatabricksMlServingEndpoint.objects.filter(
            workspace=self.workspace, name="ep-1"
        ).exists()
        rows = self._audit_rows("DATABRICKS_ML_SERVING_DELETED")
        assert len(rows) == 1
        assert rows[0].resource_id is None, "the mirror row is gone — identifiers live in details"
        assert rows[0].details_json == {
            "name": "ep-1",
            "endpoint_type": "SERVING",
            "workspace_id": str(self.workspace.id),
        }

    def test_vector_create_posts_the_vector_surface_and_audits(self):
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [
            json.dumps({"name": "vep-1", "state": {"config_update": "QUEUED"}, "config": {}})
        ]
        response = self.client.post(
            self._url("ml-asset-vector-search-endpoints", workspace_id=self.workspace.id),
            data=json.dumps({"name": "vep-1", "config": {}}),
            content_type="application/json",
        )
        assert response.status_code == 201, response.json()
        recorded = RecordingHandler.requests[0]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.0/vector-search/endpoints"
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        mirror = DatabricksMlServingEndpoint.objects.get(workspace=self.workspace, name="vep-1")
        assert mirror.endpoint_type == "VECTOR"
        assert mirror.state == "QUEUED"
        rows = self._audit_rows("DATABRICKS_ML_SERVING_CREATED")
        assert len(rows) == 1
        assert rows[0].resource_id == mirror.id
        assert rows[0].details_json["endpoint_type"] == "VECTOR"

    def test_vector_list_shows_only_vector_rows(self):
        from hub.apps.databricks_admin.models import DatabricksMlServingEndpoint

        DatabricksMlServingEndpoint.objects.create(
            workspace=self.workspace, endpoint_type="VECTOR", name="vep-1", state="READY"
        )
        DatabricksMlServingEndpoint.objects.create(
            workspace=self.workspace, endpoint_type="SERVING", name="ep-1", state="READY"
        )
        response = self.client.get(
            self._url("ml-asset-vector-search-endpoints", workspace_id=self.workspace.id)
        )
        assert response.status_code == 200, response.json()
        assert [row["name"] for row in response.json()["results"]] == ["vep-1"]
        assert RecordingHandler.requests == []
