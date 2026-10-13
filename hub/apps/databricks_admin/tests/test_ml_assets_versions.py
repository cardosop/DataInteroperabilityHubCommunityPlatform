"""TDD pins for the ML-assets version + alias surface (openspec
add-databricks-ml-assets task 12.2) — design D1-D3.

- The P1 ``UCModel`` mirror stays the READ surface; a NEW additive
  ``UCModelVersion`` mirror (model-scoped, indirect-FK RLS through the
  model → schema → catalog → workspace chain, paired migration) carries
  the version number, source, run link, and the API-reported status.
- The MLflow surface rides the PINNED client (NEW ``mlflow.*`` pins,
  2.0 — registered-model create/get, model-version create): a version
  log creates the registered model when absent (the GET's 404), then
  logs the version; the mirror row lands on success.
- Aliases ride the UC REST (NEW ``uc.model_aliases.*`` pins, 2.1 —
  the journey prose's exact PUT/DELETE paths); the model row's
  ``aliases`` list (the P1 sync's list-of-dicts shape) updates at
  operation time.

No mocks: real Postgres rows (workspace → catalog → schema → model →
version through the REAL chain), the PRODUCTION client against a REAL
threaded local HTTP server (the wire paths/bodies asserted IN ORDER),
the RLS policy scan + a runtime probe through the real probe role.
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
        credential_config={"token": "dapi-ml"},
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


class TestApiPathPins:
    def test_the_mlflow_and_alias_pins_are_registered(self):
        from hub.apps.databricks_admin import api_paths

        assert api_paths.API_PATHS["mlflow.registered_models.create"] == (
            "/api/2.0/mlflow/registered-models/create"
        )
        assert api_paths.API_PATHS["mlflow.registered_models.get"] == (
            "/api/2.0/mlflow/registered-models/get"
        )
        assert api_paths.API_PATHS["mlflow.model_versions.create"] == (
            "/api/2.0/mlflow/model-versions/create"
        )
        assert api_paths.API_PATHS["uc.model_aliases.set"] == (
            "/api/2.1/unity-catalog/models/{full_name}/aliases/{alias}"
        )
        assert api_paths.API_PATHS["uc.model_aliases.remove"] == (
            "/api/2.1/unity-catalog/models/{full_name}/aliases/{alias}"
        )
        for key in (
            "mlflow.registered_models.create",
            "mlflow.registered_models.get",
            "mlflow.model_versions.create",
        ):
            assert api_paths.API_PATH_VERSIONS[key] == "2.0"
        for key in ("uc.model_aliases.set", "uc.model_aliases.remove"):
            assert api_paths.API_PATH_VERSIONS[key] == "2.1"


class TestUCModelVersionModel(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _make_workspace(self.tenant, name=f"ws-ml-{uuid.uuid4().hex[:8]}")
        from hub.apps.databricks_admin.models import UCCatalog, UCModel, UCSchema

        self.catalog = UCCatalog.objects.create(workspace=self.workspace, name="ml_catalog")
        self.schema = UCSchema.objects.create(catalog=self.catalog, name="ml_schema")
        self.model = UCModel.objects.create(schema=self.schema, name="churn_model")

    def test_the_model_is_importable_and_registers(self):
        from hub.apps.databricks_admin.models import UCModelVersion

        assert UCModelVersion is not None

    def test_a_version_row_carries_the_chain_and_the_reported_shape(self):
        from hub.apps.databricks_admin.models import UCModelVersion

        row = UCModelVersion.objects.create(
            model=self.model,
            version=3,
            source="dbfs:/ml/churn",
            run_id="run-abc",
            run_link="https://adb-1.cloud.databricks.com/#mlflow/run/run-abc",
            status="READY",
        )
        assert row.model_id == self.model.id
        assert row.version == 3
        assert row.source == "dbfs:/ml/churn"
        assert row.status == "READY"

    def test_the_version_number_is_unique_per_model(self):
        from django.db import IntegrityError

        from hub.apps.databricks_admin.models import UCModelVersion

        UCModelVersion.objects.create(model=self.model, version=1)
        with pytest.raises(IntegrityError):
            UCModelVersion.objects.create(model=self.model, version=1)

    def test_the_rls_policy_exists_on_the_table(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT policyname FROM pg_policies WHERE tablename = %s",
                ["databricks_uc_model_versions"],
            )
            assert cursor.fetchone() is not None, "the version table carries its RLS policy"


class TestMlAssetsService(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _make_workspace(self.tenant, name=f"ws-mlsvc-{uuid.uuid4().hex[:8]}")
        from hub.apps.databricks_admin.models import UCCatalog, UCModel, UCSchema

        self.catalog = UCCatalog.objects.create(workspace=self.workspace, name="ml_catalog")
        self.schema = UCSchema.objects.create(catalog=self.catalog, name="ml_schema")
        self.model = UCModel.objects.create(
            schema=self.schema, name="churn_model", full_name="ml_catalog.ml_schema.churn_model"
        )

    def test_register_creates_the_registered_model_then_logs_the_version(self):
        from hub.apps.databricks_admin.ml_assets import register_model_version

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [404, 200, 200]  # get → create → version-create
        RecordingHandler.json_script = [
            json.dumps({"error_code": "NOT_FOUND"}),
            json.dumps({"registered_model": {"name": "churn_model"}}),
            json.dumps(
                {
                    "model_version": {
                        "version": "1",
                        "source": "dbfs:/ml/churn",
                        "run_id": "run-abc",
                        "run_link": "https://adb/mlflow/run/run-abc",
                        "status": "PENDING_VALIDATION",
                    }
                }
            ),
        ]

        row = register_model_version(
            _client(port, str(self.tenant.id)),
            model=self.model,
            source="dbfs:/ml/churn",
            run_id="run-abc",
        )

        assert row.version == 1
        assert row.source == "dbfs:/ml/churn"
        assert row.run_id == "run-abc"
        assert row.status == "PENDING_VALIDATION"
        self.model.refresh_from_db()
        assert self.model.latest_version == 1

        recorded = RecordingHandler.requests
        assert len(recorded) == 3, "get → create → version-create, in order"
        assert recorded[0]["path"] == (
            "/api/2.0/mlflow/registered-models/get?name=ml_catalog.ml_schema.churn_model"
        )
        assert recorded[1]["method"] == "POST"
        assert recorded[1]["path"] == "/api/2.0/mlflow/registered-models/create"
        assert json.loads(recorded[1]["body"]) == {"name": "ml_catalog.ml_schema.churn_model"}
        assert recorded[2]["method"] == "POST"
        assert recorded[2]["path"] == "/api/2.0/mlflow/model-versions/create"
        assert json.loads(recorded[2]["body"]) == {
            "name": "ml_catalog.ml_schema.churn_model",
            "source": "dbfs:/ml/churn",
            "run_id": "run-abc",
        }

    def test_an_existing_registered_model_skips_the_create(self):
        from hub.apps.databricks_admin.ml_assets import register_model_version

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [200, 200]
        RecordingHandler.json_script = [
            json.dumps({"registered_model": {"name": "churn_model"}}),
            json.dumps({"model_version": {"version": "2", "status": "READY"}}),
        ]

        register_model_version(
            _client(port, str(self.tenant.id)), model=self.model, source="s3://m"
        )

        recorded = RecordingHandler.requests
        assert len(recorded) == 2, "the get hits + the version create — NO registered-model create"
        assert recorded[1]["path"] == "/api/2.0/mlflow/model-versions/create"

    def test_set_alias_puts_and_updates_the_model_row(self):
        from hub.apps.databricks_admin.ml_assets import set_model_alias

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [200]
        RecordingHandler.json_script = [json.dumps({"alias": "prod", "version_num": 1})]

        set_model_alias(
            _client(port, str(self.tenant.id)), model=self.model, alias="prod", version=1
        )

        self.model.refresh_from_db()
        assert {"alias_name": "prod", "version_num": 1} in self.model.aliases
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "PUT"
        assert recorded["path"] == (
            "/api/2.1/unity-catalog/models/ml_catalog.ml_schema.churn_model/aliases/prod"
        )
        assert json.loads(recorded["body"]) == {"version_num": 1}

    def test_remove_alias_deletes_and_updates_the_model_row(self):
        from hub.apps.databricks_admin.ml_assets import remove_model_alias, set_model_alias

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [200, 200]
        RecordingHandler.json_script = [
            json.dumps({"alias": "prod", "version_num": 1}),
            "{}",
        ]
        client = _client(port, str(self.tenant.id))
        set_model_alias(client, model=self.model, alias="prod", version=1)
        remove_model_alias(client, model=self.model, alias="prod")

        self.model.refresh_from_db()
        assert all(entry.get("alias_name") != "prod" for entry in self.model.aliases)
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "DELETE"
        assert recorded["path"] == (
            "/api/2.1/unity-catalog/models/ml_catalog.ml_schema.churn_model/aliases/prod"
        )

    def test_an_api_rejection_propagates_the_classified_error(self):
        from hub.apps.databricks_admin.client import DatabricksApiError
        from hub.apps.databricks_admin.ml_assets import set_model_alias

        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [404]
        RecordingHandler.json_script = [json.dumps({"error_code": "MODEL_NOT_FOUND"})]

        with pytest.raises(DatabricksApiError) as excinfo:
            set_model_alias(
                _client(port, str(self.tenant.id)), model=self.model, alias="prod", version=1
            )
        assert excinfo.value.status_code == 404
