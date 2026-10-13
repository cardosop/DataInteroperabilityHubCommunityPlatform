"""TDD pins for the SQL-warehouse lifecycle endpoints (openspec
add-databricks-sql-warehouses task 3.7) — the API surface the
warehouse lifecycle page (U5) and the CLI consume.

Contracts pinned:
- the list is MIRROR-FIRST (the 3.2 rows — zero network), workspace-
  scoped + tenant-scoped (RLS), and paginated;
- start/stop drive the PRODUCTION 3.3 compute client against a REAL
  local HTTP server through the view's client-factory seam, under the
  D12 INTERACTIVE identity (purpose ``warehouse_lifecycle``, OBO,
  fail-closed without a binding — the browse precedent);
- the mirror row refreshes AFTER the action (the U5 non-blocking
  semantics — the row reports STARTING/STOPPING, never an invented
  state);
- state refusals propagate the classified
  ``DATABRICKS_WAREHOUSE_STATE_ERROR`` (409) with ZERO mutation calls;
- workspace rejections are MASKED (``DATABRICKS_AUTH_FAILED`` 502);
- the workspace-registry flag gate + kill switch + the Phase 273
  throttle scope apply.

No mocks: real Postgres mirror rows + tenants/users/bindings, real
RBAC + flag gating, the REAL OBO provider with the access token seeded
in the REAL Redis cache (get_bearer never touches the network), and
the PRODUCTION client against a REAL local HTTP server.
"""

import json
import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.databricks_admin.models import DatabricksSqlWarehouse
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _seed_workspace(tenant, name="ws-wh", flag=True):
    from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

    tenant.databricks_control_plane_enabled = flag
    tenant.save(update_fields=["databricks_control_plane_enabled"])
    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=name,
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )


def _seed_mirror(workspace, *, warehouse_id="wh-1", state="STOPPED", serverless=True, size=None):
    return DatabricksSqlWarehouse.objects.create(
        workspace=workspace,
        warehouse_id=warehouse_id,
        name=f"wh-{warehouse_id}",
        state=state,
        serverless=serverless,
        size=size,
    )


def _url(workspace_id, tail=""):
    return f"/api/v1/databricks/workspaces/{workspace_id}/sql-warehouses/{tail}"


def _client(user):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


class SqlWarehouseEndpointTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_user(self.tenant, f"wh-ep-{uuid.uuid4().hex[:8]}@test.com")
        self.workspace = _seed_workspace(self.tenant)

    def test_list_returns_the_tenant_mirror_rows_paginated(self):
        _seed_mirror(self.workspace, warehouse_id="wh-1", state="STOPPED")
        _seed_mirror(
            self.workspace, warehouse_id="wh-2", state="RUNNING", serverless=False, size="M"
        )

        response = _client(self.admin).get(_url(self.workspace.id))
        assert response.status_code == 200, response.content
        rows = {row["warehouse_id"]: row for row in response.json()["results"]}
        assert set(rows) == {"wh-1", "wh-2"}
        assert rows["wh-1"]["state"] == "STOPPED"
        assert rows["wh-1"]["serverless"] is True
        assert rows["wh-1"]["size"] is None
        assert rows["wh-2"]["size"] == "M"
        assert rows["wh-2"]["serverless"] is False
        assert "name" in rows["wh-1"]
        assert "auto_stop_mins" in rows["wh-1"]

    def test_list_is_tenant_and_workspace_scoped(self):
        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        foreign_workspace = _seed_workspace(other_tenant)
        _seed_mirror(foreign_workspace, warehouse_id="foreign-wh")

        # A foreign tenant's rows are never visible.
        response = _client(self.admin).get(_url(self.workspace.id))
        assert response.status_code == 200
        assert response.json()["results"] == []

        # A foreign workspace id is a 404 for this tenant.
        response = _client(self.admin).get(_url(foreign_workspace.id))
        assert response.status_code == 404, response.content

    def test_flag_off_returns_403(self):
        self.workspace.tenant.databricks_control_plane_enabled = False
        self.workspace.tenant.save(update_fields=["databricks_control_plane_enabled"])
        response = _client(self.admin).get(_url(self.workspace.id))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATABRICKS_CONTROL_PLANE_DISABLED"

    def test_unknown_warehouse_is_404(self):
        _seed_mirror(self.workspace, warehouse_id="wh-1")
        response = _client(self.admin).post(_url(self.workspace.id, "wh-9/start/"))
        assert response.status_code == 404, response.content

    def test_warehouse_lifecycle_is_an_interactive_purpose(self):
        from hub.apps.databricks_admin.identity import INTERACTIVE_PURPOSES

        assert "warehouse_lifecycle" in INTERACTIVE_PURPOSES


class TestSqlWarehouseActions:  # plain class (pytest fixtures cannot serve TestCase methods — 0.8); Test* prefix required by python_classes
    """The LIVE lifecycle actions — real identity + real local server."""

    def _setup(self, with_binding=True, with_cache=True, redis_client=None):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)
        self.mirror = _seed_mirror(self.workspace, warehouse_id="wh-1", state="STOPPED")
        self.binding = None
        if with_binding:
            from hub.apps.databricks_admin.models import DatabricksUserBinding

            self.binding = DatabricksUserBinding.objects.create(
                tenant=self.tenant,
                user=self.admin,
                workspace=self.workspace,
                databricks_sub=f"sub-{uuid.uuid4().hex[:8]}",
                databricks_email=self.admin.email,
            )
            from hub.apps.tenants.models import TenantConfig

            config = TenantConfig.objects.get_or_create(tenant=self.tenant)[0]
            sso = config.get_sso_config()
            sso["databricks"] = {
                "host": REAL_HOST,
                "client_id": "client-abc",
                "redirect_uri": "https://hub.example.com/auth/databricks/callback",
            }
            config.sso_config = sso
            config.save()
            if with_cache:
                from hub.apps.databricks_admin.obo_tokens import OBOAccessTokenCache

                OBOAccessTokenCache(redis_client=redis_client).set(
                    self.binding.id, "dapi-wh-access", 300
                )

    def _patch_client_factory(self, monkeypatch, port):
        from hub.apps.databricks_admin import sql_warehouse_views as views_module
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.obo_tokens import OBOTokenProvider

        def fake_factory(workspace, _identity):
            provider = OBOTokenProvider(
                binding=self.binding,
                oidc_client_id="client-abc",
                oidc_base_url=f"http://127.0.0.1:{port}",
            )
            return DatabricksApiClient(
                base_url=f"http://127.0.0.1:{port}",
                tenant_id=str(workspace.tenant_id),
                obo_provider=provider,
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
                # The transport is a local scripted server; the shared
                # breaker channels keyed by base_url collide across
                # reused ephemeral ports (a prior test's failures leave
                # the channel OPEN for the next test — the flake the
                # 3.8-review full run caught). The 1.7 delegation
                # convention: a caller with its own transport disables
                # breaker accounting.
                use_breaker=False,
            )

        monkeypatch.setattr(views_module, "_build_uc_client", fake_factory)

    @staticmethod
    def _warehouse_payload(warehouse_id="wh-1", state="STOPPED"):
        return {
            "id": warehouse_id,
            "name": f"wh-{warehouse_id}",
            "state": state,
            "serverless": True,
            "size": None,
            "auto_stop_mins": 30,
        }

    def test_start_stops_a_stopped_warehouse_and_refreshes_the_mirror(
        self, monkeypatch, local_http_server, redis_13
    ):
        self._setup(redis_client=redis_13)
        self._patch_client_factory(monkeypatch, local_http_server)
        RecordingHandler.json_script = [
            json.dumps(self._warehouse_payload(state="STOPPED")),  # the state GET
            "{}",  # the start POST's empty-body answer
            json.dumps(
                {"warehouses": [self._warehouse_payload(state="STARTING")]}
            ),  # the refresh LIST
        ]

        response = _client(self.admin).post(_url(self.workspace.id, "wh-1/start/"))
        assert response.status_code == 200, response.content
        started = [r for r in RecordingHandler.requests if r["method"] == "POST"]
        assert len(started) == 1
        assert started[0]["path"] == "/api/2.0/sql/warehouses/wh-1/start"

        self.mirror.refresh_from_db()
        assert self.mirror.state == "STARTING", (
            "the mirror follows the compute API (never invented)"
        )
        assert response.json()["state"] == "STARTING"

    def test_start_on_a_running_warehouse_is_a_no_op(
        self, monkeypatch, local_http_server, redis_13
    ):
        self._setup(redis_client=redis_13)
        self.mirror.state = "RUNNING"
        self.mirror.save(update_fields=["state"])
        self._patch_client_factory(monkeypatch, local_http_server)
        RecordingHandler.json_script = [
            json.dumps(self._warehouse_payload(state="RUNNING")),  # the state GET
            json.dumps(
                {"warehouses": [self._warehouse_payload(state="RUNNING")]}
            ),  # the refresh LIST
        ]

        response = _client(self.admin).post(_url(self.workspace.id, "wh-1/start/"))
        assert response.status_code == 200, response.content
        assert not [r for r in RecordingHandler.requests if r["method"] == "POST"], (
            "the idempotency contract: ZERO mutation calls"
        )

    def test_stop_stops_a_running_warehouse_and_refreshes(
        self, monkeypatch, local_http_server, redis_13
    ):
        self._setup(redis_client=redis_13)
        self.mirror.state = "RUNNING"
        self.mirror.save(update_fields=["state"])
        self._patch_client_factory(monkeypatch, local_http_server)
        RecordingHandler.json_script = [
            json.dumps(self._warehouse_payload(state="RUNNING")),
            "{}",
            json.dumps({"warehouses": [self._warehouse_payload(state="STOPPING")]}),
        ]

        response = _client(self.admin).post(_url(self.workspace.id, "wh-1/stop/"))
        assert response.status_code == 200, response.content
        posts = [r for r in RecordingHandler.requests if r["method"] == "POST"]
        assert len(posts) == 1
        assert posts[0]["path"] == "/api/2.0/sql/warehouses/wh-1/stop"
        self.mirror.refresh_from_db()
        assert self.mirror.state == "STOPPING"

    def test_state_refusal_propagates_the_classified_code_with_no_mutation(
        self, monkeypatch, local_http_server, redis_13
    ):
        self._setup(redis_client=redis_13)
        self._patch_client_factory(monkeypatch, local_http_server)
        RecordingHandler.json_script = [
            json.dumps(
                self._warehouse_payload(state="DELETING")
            ),  # START on DELETING → state error
        ]

        response = _client(self.admin).post(_url(self.workspace.id, "wh-1/start/"))
        assert response.status_code == 409, response.content
        assert response.json()["code"] == "DATABRICKS_WAREHOUSE_STATE_ERROR"
        assert not [r for r in RecordingHandler.requests if r["method"] == "POST"]

    def test_workspace_rejection_is_masked(self, monkeypatch, local_http_server, redis_13):
        self._setup(redis_client=redis_13)
        self._patch_client_factory(monkeypatch, local_http_server)
        RecordingHandler.json_script = [json.dumps({"error_code": "UNAUTHENTICATED"})]
        RecordingHandler.script = [401]

        response = _client(self.admin).post(_url(self.workspace.id, "wh-1/start/"))
        assert response.status_code == 502, response.content
        assert response.json()["code"] == "DATABRICKS_AUTH_FAILED"

    def test_fail_closed_without_a_binding(self):
        self._setup(with_binding=False)
        response = _client(self.admin).post(_url(self.workspace.id, "wh-1/start/"))
        assert response.status_code == 502, response.content
        assert response.json()["code"] == "DATABRICKS_OBO_REFRESH_FAILED"

    # ── 3.7 review pass (the action spine's fail-loud + succeeded-action
    # edge contracts — the 3.8 wiring + the 3.2 delta-diff interplay) ─

    def test_unknown_action_name_fails_loud_before_any_work(self):
        # The dispatch must NEVER silently map an unknown action to
        # STOP — a future delete endpoint routed through _run_action
        # would otherwise stop the warehouse. Fail at development time
        # (ValueError), zero identity/network work.
        from rest_framework.test import APIRequestFactory

        from hub.apps.databricks_admin.sql_warehouse_views import SqlWarehouseViewSet

        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)
        self.mirror = _seed_mirror(self.workspace, warehouse_id="wh-1", state="STOPPED")

        request = APIRequestFactory().post("/ignored")
        request.user = self.admin
        with pytest.raises(ValueError, match="unknown"):
            SqlWarehouseViewSet()._run_action(request, str(self.workspace.id), "wh-1", "delete")
        assert RecordingHandler.requests == []

    def test_succeeded_action_whose_refresh_removed_the_row_returns_the_last_known_state(
        self, monkeypatch, local_http_server, redis_13
    ):
        # The 3.2 delta-diff DELETES rows the compute API no longer
        # reports — a succeeded action followed by such a refresh must
        # NOT 500 on refresh_from_db (the row vanished); the response
        # carries the last-known state (the DB-005 freshness-marker
        # semantics), the action itself succeeded.
        self._setup(redis_client=redis_13)
        self._patch_client_factory(monkeypatch, local_http_server)
        RecordingHandler.json_script = [
            json.dumps(self._warehouse_payload(state="STOPPED")),  # the state GET
            "{}",  # the start POST's empty-body answer
            json.dumps({"warehouses": []}),  # the refresh LIST — row removed
        ]

        response = _client(self.admin).post(_url(self.workspace.id, "wh-1/start/"))
        assert response.status_code == 200, response.content
        assert response.json()["state"] == "STOPPED", (
            "the last-known state is returned (never invented)"
        )
        assert not DatabricksSqlWarehouse.objects.filter(
            workspace=self.workspace, warehouse_id="wh-1"
        ).exists(), "the mirror followed the compute API (row removed)"


class SqlWarehouseThrottleScopeTests(TestCase):
    def test_the_scope_and_rate_are_registered(self):
        from django.conf import settings

        from hub.apps.databricks_admin.sql_warehouse_views import SqlWarehouseViewSet

        assert SqlWarehouseViewSet.throttle_scope == "databricks_sql_warehouses"
        assert "databricks_sql_warehouses" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
