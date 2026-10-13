"""TDD pins for the SQL warehouse mirror (openspec
add-databricks-sql-warehouses task 3.2) — the `DatabricksSqlWarehouse`
model (indirect-FK RLS) + the live state mirror refresh.

The mirror is a READ cache of the Databricks-owned state: the refresh
maps the compute API's reported states, never invents one. No mocks:
real Postgres rows + RLS (policy scan + a runtime probe through the
1.12 helper), the PRODUCTION client against a REAL local HTTP server
for the refresh, and the real pagination/delta conventions of the 1.5
UC sync.
"""

import json
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _warehouse_payload(
    warehouse_id="wh-1",
    name="etl-warehouse",
    state="RUNNING",
    serverless=True,
    size=None,
    auto_stop_mins=30,
):
    payload = {
        "id": warehouse_id,
        "name": name,
        "state": state,
        "serverless": serverless,
        "auto_stop_mins": auto_stop_mins,
    }
    if size is not None:
        payload["size"] = size
    return payload


def _client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id="t1",
        credential_config={"token": "dapi-wh"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
    )


class TestDatabricksSqlWarehouseModel(TestCase):
    """The mirror model: identity, uniqueness, cascade, RLS."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant)

    def _make(self, warehouse_id="wh-1", **overrides):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        fields = {
            "workspace": self.workspace,
            "warehouse_id": warehouse_id,
            "name": "etl-warehouse",
            "state": "RUNNING",
        }
        fields.update(overrides)
        return DatabricksSqlWarehouse.objects.create(**fields)

    def test_unique_per_workspace_by_warehouse_id_and_name(self):
        from django.core.exceptions import ValidationError

        self._make()
        # The model's full_clean surfaces duplicates as clean
        # ValidationErrors (the 0.8 name-conflict pattern) before the
        # DB constraint ever fires.
        with pytest.raises(ValidationError):
            self._make()  # same warehouse_id → the (workspace, warehouse_id) uniqueness
        with pytest.raises(ValidationError):
            self._make(warehouse_id="wh-2")  # same name → the (workspace, name) uniqueness

    def test_workspace_delete_cascades_the_mirror(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        row = self._make()
        self.workspace.delete()
        assert not DatabricksSqlWarehouse.objects.filter(pk=row.pk).exists()

    def test_state_is_required_and_constrained(self):
        from django.core.exceptions import ValidationError

        for state in ("STARTING", "RUNNING", "STOPPING", "STOPPED", "DELETING"):
            row = self._make(warehouse_id=f"wh-{state}", name=f"etl-{state.lower()}", state=state)
            assert row.state == state
        with pytest.raises(ValidationError):
            self._make(warehouse_id="wh-nostate", state="BOGUS_STATE")

    def test_rls_policy_ships_for_the_mirror_table(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT policyname FROM pg_policies WHERE tablename = 'databricks_sql_warehouses'"
            )
            policies = [row[0] for row in cursor.fetchall()]
        assert policies, "the mirror table must ship a paired RLS policy"

    def test_runtime_rls_hides_foreign_tenant_rows(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import (
            _connection_bypasses_rls,
            _ensure_rls_probe_role,
            _visible_count_as,
        )

        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        self._make()
        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("GRANT SELECT ON databricks_sql_warehouses TO hub_rls_probe")
        probe = "hub_rls_probe" if _connection_bypasses_rls() else None
        assert _visible_count_as(probe, self.tenant.id, "databricks_sql_warehouses") == 1
        assert _visible_count_as(probe, other_tenant.id, "databricks_sql_warehouses") == 0, (
            "a foreign tenant must see ZERO mirror rows (RLS runtime enforcement)"
        )
        assert DatabricksSqlWarehouse.objects.filter(workspace=self.workspace).count() == 1


class TestSqlWarehouseMirrorRefresh(TestCase):
    """The live refresh delta-diffs the compute API into the mirror."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        _make_user(self.tenant, f"wh-req-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
        self.workspace = _make_workspace(self.tenant)

    def _refresh(self, port, workspace=None):
        from hub.apps.databricks_admin.sql_warehouses import refresh_sql_warehouse_mirror

        return refresh_sql_warehouse_mirror(workspace or self.workspace, client=_client(port))

    def _server(self):
        import http.server
        import threading

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        return port

    def test_refresh_creates_the_mirror_from_the_api_payload(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        port = self._server()
        RecordingHandler.json_script = [json.dumps({"warehouses": [_warehouse_payload()]})]
        counters = self._refresh(port)
        assert counters == {"created": 1, "updated": 0, "unchanged": 0, "deleted": 0}, counters

        row = DatabricksSqlWarehouse.objects.get(workspace=self.workspace)
        assert row.warehouse_id == "wh-1"
        assert row.name == "etl-warehouse"
        assert row.state == "RUNNING"
        assert row.serverless is True
        assert row.auto_stop_mins == 30

        request = RecordingHandler.requests[-1]
        assert request["path"] == "/api/2.0/sql/warehouses"

    def test_second_refresh_is_a_full_no_op_and_keeps_the_freshness_stamp(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        port = self._server()
        RecordingHandler.json_script = [json.dumps({"warehouses": [_warehouse_payload()]})]
        self._refresh(port)
        row = DatabricksSqlWarehouse.objects.get(workspace=self.workspace)
        original_stamp = row.synced_at

        RecordingHandler.json_script = [json.dumps({"warehouses": [_warehouse_payload()]})]
        counters = self._refresh(port)
        assert counters == {"created": 0, "updated": 0, "unchanged": 1, "deleted": 0}, counters

        row.refresh_from_db()
        assert row.synced_at == original_stamp, (
            "an unchanged mirror row must keep its synced_at freshness stamp"
        )

    def test_refresh_updates_changed_rows_and_deletes_absent_ones(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        port = self._server()
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "warehouses": [
                        _warehouse_payload(),
                        _warehouse_payload(warehouse_id="wh-2", name="ad-hoc"),
                    ]
                }
            )
        ]
        self._refresh(port)
        assert DatabricksSqlWarehouse.objects.filter(workspace=self.workspace).count() == 2

        # wh-1 stops, wh-2 is deleted on the Databricks side.
        RecordingHandler.json_script = [
            json.dumps({"warehouses": [_warehouse_payload(state="STOPPED")]})
        ]
        counters = self._refresh(port)
        assert counters == {"created": 0, "updated": 1, "unchanged": 0, "deleted": 1}, counters

        remaining = DatabricksSqlWarehouse.objects.get(workspace=self.workspace)
        assert remaining.warehouse_id == "wh-1"
        assert remaining.state == "STOPPED"

    def test_an_unknown_api_state_is_skipped_never_invented(self):
        # A compute API state the vocabulary does not know must be SKIPPED
        # with zero crash — the mirror never invents a state.
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        port = self._server()
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "warehouses": [
                        _warehouse_payload(),
                        _warehouse_payload(warehouse_id="wh-x", state="WARPING"),
                    ]
                }
            )
        ]
        counters = self._refresh(port)
        assert counters["created"] == 1, counters
        assert not DatabricksSqlWarehouse.objects.filter(
            workspace=self.workspace, warehouse_id="wh-x"
        ).exists(), "an unknown API state must never be invented into the mirror"

    def test_malformed_fields_are_skipped_never_invented(self):
        # Review hardening: the refresh must skip malformed rows (never
        # invent, never crash) — non-numeric auto-stop, a string-valued
        # serverless ("false" coerces to True in Python), a missing
        # name, and a non-scalar size must all leave ZERO mirror rows.
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        port = self._server()
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "warehouses": [
                        _warehouse_payload(warehouse_id="wh-ok"),
                        _warehouse_payload(warehouse_id="wh-bad-stop", auto_stop_mins="abc"),
                        _warehouse_payload(warehouse_id="wh-bad-serverless", serverless="false"),
                        _warehouse_payload(warehouse_id="wh-no-name", name=None),
                        _warehouse_payload(warehouse_id="wh-bad-size", size={"tier": "L"}),
                    ]
                }
            )
        ]
        counters = self._refresh(port)
        assert counters["created"] == 1, counters
        rows = DatabricksSqlWarehouse.objects.filter(workspace=self.workspace)
        assert list(rows.values_list("warehouse_id", flat=True)) == ["wh-ok"], (
            "malformed rows must be SKIPPED, never coerced into the mirror"
        )

    def test_a_non_object_payload_is_classified_never_a_leak(self):
        from hub.apps.databricks_admin.client import DatabricksApiError

        port = self._server()
        RecordingHandler.json_script = [json.dumps(["not", "an", "object"])]
        with pytest.raises(DatabricksApiError):
            self._refresh(port)
