"""Journey pins for JOURNEY-DB-019 / UC-DB-019 (openspec
add-databricks-ml-assets task 12.7) — the UC doc's pinned Phase P12
Test path (``TestJOURNEYDB019RegisterUCModel::test_mlflow_version_log``,
the GATE-28 contract).

The acceptance round-trip (the spec R7 scenario): register →
version-log → alias-set end to end on the REAL local transport (zero
mocked transport layers — the P3 statement-executor convention) with
the THREE audit rows landing (resource_type=``DATABRICKS_ML_ASSET``,
identifiers-only details, the mirror rows anchor ``resource_id`` — the
spec's audit scenario). The wire trails are asserted IN ORDER — the
MLflow registered-model GET-404-then-create, the version-create with
the exact body, the UC alias PUT path with the exact body.

No mocks: real Postgres rows through the REAL chain (workspace →
catalog → schema → model → version), the PRODUCTION client against a
REAL threaded local HTTP server, real ``AuditEvent`` rows. The ONLY
seam: the view module's client factory redirected to the local
transport (the 10.7/12.6 convention).
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

FULL_NAME = "ml_catalog.ml_schema.churn_model"

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.journey("JOURNEY-DB-019"),
    pytest.mark.uc("UC-DB-019"),
]


class TestJOURNEYDB019RegisterUCModel(TestCase):
    """The register → version-log → alias round-trip (the UC doc's
    pinned class name)."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.tenant.databricks_ml_assets_enabled = True
        self.tenant.save(update_fields=["databricks_ml_assets_enabled"])
        self.workspace = _make_workspace(self.tenant, name=f"ws-db019-{uuid.uuid4().hex[:8]}")
        from hub.apps.databricks_admin.models import UCCatalog, UCModel, UCSchema

        self.catalog = UCCatalog.objects.create(workspace=self.workspace, name="ml_catalog")
        self.schema = UCSchema.objects.create(catalog=self.catalog, name="ml_schema")
        self.model = UCModel.objects.create(
            schema=self.schema, name="churn_model", full_name=FULL_NAME
        )
        self.actor = _make_user(
            self.tenant, f"db019-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
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

    def test_mlflow_version_log(self):
        """The pinned leg — a version logs through the MLflow surface on
        the pinned client: the registered-model GET (200 — no create),
        the version-create POST with the exact body, the mirror version
        row lands as REPORTED, ``latest_version`` advances, and
        ``DATABRICKS_ML_VERSION_LOGGED`` emits with the mirror row's pk
        anchoring ``resource_id``."""
        from django.urls import reverse

        RecordingHandler.script = [200, 200]
        RecordingHandler.json_script = [
            json.dumps({"registered_model": {"name": FULL_NAME}}),
            json.dumps(
                {
                    "model_version": {
                        "version": 9,
                        "source": "dbfs:/ml/churn",
                        "run_id": "run-abc",
                        "run_link": "https://adb-1/#mlflow/run/run-abc",
                        "status": "READY",
                    }
                }
            ),
        ]
        response = self.client.post(
            reverse(
                "ml-asset-model-versions",
                kwargs={"workspace_id": self.workspace.id, "model_id": self.model.id},
            ),
            data=json.dumps({"source": "dbfs:/ml/churn", "run_id": "run-abc"}),
            content_type="application/json",
        )
        assert response.status_code == 201, response.json()
        trails = [(r["method"], r["path"]) for r in RecordingHandler.requests]
        assert trails == [
            ("GET", f"/api/2.0/mlflow/registered-models/get?name={FULL_NAME}"),
            ("POST", "/api/2.0/mlflow/model-versions/create"),
        ]
        assert json.loads(RecordingHandler.requests[1]["body"]) == {
            "name": FULL_NAME,
            "source": "dbfs:/ml/churn",
            "run_id": "run-abc",
        }
        from hub.apps.databricks_admin.models import UCModelVersion

        version_row = UCModelVersion.objects.get(model=self.model, version=9)
        assert version_row.source == "dbfs:/ml/churn"
        assert version_row.status == "READY"
        self.model.refresh_from_db()
        assert self.model.latest_version == 9
        rows = self._audit_rows("DATABRICKS_ML_VERSION_LOGGED")
        assert len(rows) == 1
        assert rows[0].actor_user_id == self.actor.id
        assert rows[0].resource_id == version_row.id
        assert rows[0].details_json == {
            "full_name": FULL_NAME,
            "version": 9,
            "workspace_id": str(self.workspace.id),
        }, "identifiers only"

    def test_the_register_alias_round_trip_lands_three_audit_rows(self):
        """The spec R7 acceptance scenario — register (the GET's 404
        creates, never a blind create) → version-log → alias-set, end to
        end on the REAL transport with the three audit rows landing
        (tenant + workspace + mirror-row attribution, identifiers-only
        details)."""
        from django.urls import reverse

        RecordingHandler.script = [404, 200, 200, 200, 200]
        RecordingHandler.json_script = [
            "{}",
            json.dumps({"registered_model": {"name": FULL_NAME}}),
            json.dumps({"registered_model": {"name": FULL_NAME}}),
            json.dumps(
                {
                    "model_version": {
                        "version": 3,
                        "source": "dbfs:/ml/churn",
                        "run_id": "run-round",
                        "run_link": "",
                        "status": "READY",
                    }
                }
            ),
            "{}",
        ]
        register = self.client.post(
            reverse("ml-asset-models", kwargs={"workspace_id": self.workspace.id}),
            data=json.dumps({"full_name": FULL_NAME}),
            content_type="application/json",
        )
        assert register.status_code == 201, register.json()
        version = self.client.post(
            reverse(
                "ml-asset-model-versions",
                kwargs={"workspace_id": self.workspace.id, "model_id": self.model.id},
            ),
            data=json.dumps({"source": "dbfs:/ml/churn", "run_id": "run-round"}),
            content_type="application/json",
        )
        assert version.status_code == 201, version.json()
        alias = self.client.put(
            reverse(
                "ml-asset-model-alias",
                kwargs={
                    "workspace_id": self.workspace.id,
                    "model_id": self.model.id,
                    "alias": "champion",
                },
            ),
            data=json.dumps({"version_num": 3}),
            content_type="application/json",
        )
        assert alias.status_code == 200, alias.json()

        trails = [(r["method"], r["path"]) for r in RecordingHandler.requests]
        assert trails == [
            ("GET", f"/api/2.0/mlflow/registered-models/get?name={FULL_NAME}"),
            ("POST", "/api/2.0/mlflow/registered-models/create"),
            ("GET", f"/api/2.0/mlflow/registered-models/get?name={FULL_NAME}"),
            ("POST", "/api/2.0/mlflow/model-versions/create"),
            ("PUT", f"/api/2.1/unity-catalog/models/{FULL_NAME}/aliases/champion"),
        ], "the round-trip rides the pinned client IN ORDER"
        assert json.loads(RecordingHandler.requests[4]["body"]) == {"version_num": 3}

        from hub.apps.audit.models import AuditEvent

        events = list(
            AuditEvent.objects.filter(
                tenant=self.tenant, resource_type="DATABRICKS_ML_ASSET"
            ).order_by("timestamp")
        )
        assert [e.action for e in events] == [
            "DATABRICKS_ML_MODEL_REGISTERED",
            "DATABRICKS_ML_VERSION_LOGGED",
            "DATABRICKS_ML_ALIAS_SET",
        ], "one row per performed operation, in order"
        assert events[0].resource_id == self.model.id, "the mirror row anchors resource_id"
        assert events[0].details_json == {
            "full_name": FULL_NAME,
            "workspace_id": str(self.workspace.id),
        }
        assert events[1].resource_id is not None
        assert events[1].details_json["full_name"] == FULL_NAME
        assert events[2].resource_id == self.model.id
        assert events[2].details_json == {
            "full_name": FULL_NAME,
            "alias": "champion",
            "workspace_id": str(self.workspace.id),
        }
        for event in events:
            assert event.actor_user_id == self.actor.id, "every row carries the actor"
        self.model.refresh_from_db()
        assert self.model.aliases == [{"alias_name": "champion", "version_num": 3}]
