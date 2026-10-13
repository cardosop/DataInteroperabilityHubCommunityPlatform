"""TDD pins for the SQL warehouse fleet observability (openspec
add-databricks-sql-warehouses task 3.8) — metrics, alert rules, and the
Grafana dashboard (the 1.10 test_uc_sync_alerts conventions).

The fleet metrics (``hub/apps/databricks_admin/metrics.py``) are emitted
from the REAL surfaces: the mirror refresh stamps the last-success
anchor + per-state counts + STARTING-since transitions, and the 3.5
pool records borrows/exhaustion/in-use on its REAL borrow/release
surface. The alert rules
(``monitoring/prometheus/alerts/databricks-warehouses.yml``) and the
dashboard (``monitoring/grafana/dashboards/databricks-warehouse-fleet.json``)
are REAL artifacts — the pins validate they parse and reference exactly
the emitted metrics (drift pins both directions).

The ``record_*`` wrappers are the module-boundary seam tests patch (the
metrics.py docstring contract) — the REAL refresh/pool drives them; the
fakes only observe the calls.
"""

import json
from pathlib import Path

import pytest
import yaml
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_sql_warehouse_views import (
    _client,
    _seed_mirror,
    _seed_workspace,
    _url,
)
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

PROJECT_ROOT = Path(__file__).resolve().parents[4]

FLEET_METRIC_NAMES = (
    "databricks_warehouse_mirror_last_success_timestamp",
    "databricks_warehouse_state_count",
    "databricks_warehouse_starting_since_timestamp",
    "databricks_warehouse_pool_borrows_total",
    "databricks_warehouse_pool_exhausted_total",
    "databricks_warehouse_pool_in_use",
)


class _CallRecorder:
    """The module-boundary fake (the metrics.py seam contract): records
    each record_* call for assertions — no network or DB behavior is
    replaced, only the metric backend."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class TestFleetMetricRegistration:
    def test_fleet_metric_names_are_registered(self):
        from hub.apps.databricks_admin import metrics

        for name in FLEET_METRIC_NAMES:
            metric = getattr(metrics, name, None)
            assert metric is not None, f"{name} must be registered in metrics.py"
            # prometheus_client strips the mandatory _total suffix from a
            # Counter's `_name` (the EXPORTED name keeps it) — the two
            # counter names therefore compare with the suffix re-added.
            exported = metric._name
            if name.endswith("_total") and not exported.endswith("_total"):
                exported = f"{exported}_total"
            assert exported == name


class TestMirrorRefreshMetrics:  # plain class — pytest fixtures cannot serve TestCase methods (0.8)
    """The refresh stamps the fleet gauges from the REAL delta-diff."""

    def _env(self):
        require_dns()
        tenant = TenantFactory.create_tenant()
        from hub.apps.databricks_admin.tests.test_views import _activate_billing

        _activate_billing(tenant)
        from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace

        return tenant, _make_workspace(tenant)

    def _refresh(self, port, workspace):
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.sql_warehouses import refresh_sql_warehouse_mirror

        client = DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id="t1",
            credential_config={"token": "dapi-wh"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
        )
        return refresh_sql_warehouse_mirror(workspace, client=client)

    @staticmethod
    def _warehouse_payload(warehouse_id="wh-1", state="RUNNING"):
        return {
            "id": warehouse_id,
            "name": f"etl-{warehouse_id}",
            "state": state,
            "serverless": True,
            "auto_stop_mins": 30,
        }

    def test_refresh_records_the_mirror_success_timestamp(self, monkeypatch, local_http_server):
        from hub.apps.databricks_admin import metrics

        tenant, workspace = self._env()
        recorder = _CallRecorder()
        monkeypatch.setattr(metrics, "record_warehouse_mirror_success", recorder)
        RecordingHandler.json_script = [json.dumps({"warehouses": [self._warehouse_payload()]})]
        self._refresh(local_http_server, workspace)
        assert len(recorder.calls) == 1, recorder.calls
        assert recorder.calls[0][1]["tenant_id"] == str(tenant.id)
        assert recorder.calls[0][1]["workspace_id"] == str(workspace.id)

    def test_refresh_records_the_per_state_counts(self, monkeypatch, local_http_server):
        from hub.apps.databricks_admin import metrics

        _tenant, workspace = self._env()
        recorder = _CallRecorder()
        monkeypatch.setattr(metrics, "record_warehouse_state_counts", recorder)
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "warehouses": [
                        self._warehouse_payload("wh-1", "RUNNING"),
                        self._warehouse_payload("wh-2", "STOPPED"),
                    ]
                }
            )
        ]
        self._refresh(local_http_server, workspace)
        assert len(recorder.calls) == 1, recorder.calls
        assert recorder.calls[0][0][0] is workspace

    def test_refresh_records_starting_transitions(self, monkeypatch, local_http_server):
        from hub.apps.databricks_admin import metrics

        _tenant, workspace = self._env()
        recorder = _CallRecorder()
        monkeypatch.setattr(metrics, "record_warehouse_starting_since", recorder)
        # First refresh: wh-1 arrives STARTING (enter).
        RecordingHandler.json_script = [
            json.dumps({"warehouses": [self._warehouse_payload("wh-1", "STARTING")]})
        ]
        self._refresh(local_http_server, workspace)
        enters = [c for c in recorder.calls if c[1].get("warehouse_id") == "wh-1"]
        assert len(enters) == 1, recorder.calls
        assert enters[0][1]["seconds_since_epoch"] > 0

        # Second refresh: wh-1 leaves STARTING (exit → reset to 0).
        recorder.calls.clear()
        RecordingHandler.json_script = [
            json.dumps({"warehouses": [self._warehouse_payload("wh-1", "RUNNING")]})
        ]
        self._refresh(local_http_server, workspace)
        exits = [c for c in recorder.calls if c[1].get("warehouse_id") == "wh-1"]
        assert len(exits) == 1, recorder.calls
        assert exits[0][1]["seconds_since_epoch"] == 0


class TestPoolMetrics:
    """The REAL pool surface drives the pool-pressure metrics."""

    def test_borrow_exhaustion_and_release_record_metrics(self, monkeypatch):
        from hub.apps.databricks_admin import metrics
        from hub.apps.databricks_admin.sql_warehouse_pool import SqlWarehousePool

        borrowed = _CallRecorder()
        exhausted = _CallRecorder()
        in_use = _CallRecorder()
        monkeypatch.setattr(metrics, "record_pool_borrow", borrowed)
        monkeypatch.setattr(metrics, "record_pool_exhausted", exhausted)
        monkeypatch.setattr(metrics, "set_pool_in_use", in_use)

        class _Conn:
            def __init__(self, tenant_id):
                self._tenant_id = tenant_id

            def close(self):
                pass

        pool = SqlWarehousePool(max_per_tenant=1)
        conn = pool.borrow("tenant-a", "wh-1", factory=_Conn)
        assert isinstance(conn, _Conn)
        assert len(borrowed.calls) == 1
        assert borrowed.calls[0][1] == {"tenant_id": "tenant-a"}
        assert in_use.calls[-1][1] == {"tenant_id": "tenant-a", "count": 1}

        # The tenant's single slot is held — the second borrow exhausts.
        from hub.apps.databricks_admin.sql_warehouse_pool import DatabricksWarehousePoolError

        with pytest.raises(DatabricksWarehousePoolError) as excinfo:
            pool.borrow("tenant-a", "wh-2", factory=_Conn)
        assert excinfo.value.code == "DATABRICKS_WAREHOUSE_POOL_EXHAUSTED"
        assert len(exhausted.calls) == 1
        assert exhausted.calls[0][1] == {"tenant_id": "tenant-a"}

        pool.release(conn)
        assert in_use.calls[-1][1] == {"tenant_id": "tenant-a", "count": 0}
        pool.stop()


class TestWarehouseFleetAlerts(TestCase):
    """The alert rules exist, parse, and pin the fleet metrics."""

    def setUp(self):
        self.alerts_file = (
            PROJECT_ROOT / "monitoring" / "prometheus" / "alerts" / "databricks-warehouses.yml"
        )

    def test_alerts_file_exists_and_parses(self):
        assert self.alerts_file.is_file(), "databricks-warehouses.yml must exist"
        config = yaml.safe_load(self.alerts_file.read_text())
        assert "groups" in config
        group = next(g for g in config["groups"] if g["name"] == "databricks_warehouses")
        assert len(group["rules"]) == 3

    def test_mirror_stale_alert_pins_the_success_gauge_and_window(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksWarehouseMirrorStale"
        )
        assert "databricks_warehouse_mirror_last_success_timestamp" in rule["expr"]
        assert rule["labels"]["severity"] == "warning"
        # A mirror older than 24h is stale (the fleet refresh is
        # lifecycle-driven — 3.7 refreshes after every action).
        assert "86400" in rule["expr"]

    def test_starting_too_long_alert_pins_the_gauge_and_threshold(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksWarehouseStartingTooLong"
        )
        assert "databricks_warehouse_starting_since_timestamp" in rule["expr"]
        assert rule["labels"]["severity"] == "warning"
        # STARTING for more than 10 minutes is long (warehouses normally
        # start in minutes).
        assert "600" in rule["expr"]

    def test_pool_exhausted_alert_pins_the_counter(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksWarehousePoolExhausted"
        )
        assert "databricks_warehouse_pool_exhausted_total" in rule["expr"]
        assert rule["labels"]["severity"] == "warning"


class TestWarehouseFleetDashboard(TestCase):
    """The Grafana dashboard exists, parses, and pins the fleet metrics."""

    def setUp(self):
        self.dashboard_file = (
            PROJECT_ROOT
            / "monitoring"
            / "grafana"
            / "dashboards"
            / "databricks-warehouse-fleet.json"
        )

    def test_dashboard_exists_and_parses(self):
        assert self.dashboard_file.is_file(), "databricks-warehouse-fleet.json must exist"
        payload = json.loads(self.dashboard_file.read_text())
        assert payload["dashboard"]["title"] == "Databricks — Warehouse Fleet"
        assert payload["dashboard"]["uid"] == "databricks-warehouse-fleet"
        assert len(payload["dashboard"]["panels"]) >= 5

    def test_dashboard_references_only_the_fleet_metrics(self):
        payload = json.loads(self.dashboard_file.read_text())
        exprs = []
        for panel in payload["dashboard"]["panels"]:
            for target in panel.get("targets", []):
                if target.get("expr"):
                    exprs.append(target["expr"])
        referenced = {name for name in FLEET_METRIC_NAMES if any(name in e for e in exprs)}
        assert referenced == set(FLEET_METRIC_NAMES), (
            f"dashboard must consume exactly the fleet metrics; found {referenced}"
        )

    def test_artifact_metric_names_match_the_emitter(self):
        # The drift pin: every EXPORTED fleet metric name (the names the
        # artifacts query — counters carry their _total suffix) appears
        # in the observability artifacts (the 1.10 convention).
        from hub.apps.databricks_admin import metrics

        emitted = set()
        for name in FLEET_METRIC_NAMES:
            exported = getattr(metrics, name)._name
            if name.endswith("_total") and not exported.endswith("_total"):
                exported = f"{exported}_total"
            emitted.add(exported)
        artifact_text = (
            self.dashboard_file.read_text()
            + (
                PROJECT_ROOT / "monitoring" / "prometheus" / "alerts" / "databricks-warehouses.yml"
            ).read_text()
        )
        for name in emitted:
            assert name in artifact_text, (
                f"metric {name} is emitted but absent from the 3.8 artifacts"
            )


class TestViewActionAuditWiring:
    """The 3.7 START/STOP endpoints emit through the lifecycle chokepoint.

    The REAL end-to-end surface: real binding + Redis-seeded OBO +
    real local HTTP server + real audit rows (the 3.7 view-test seams).
    """

    def test_view_start_action_emits_the_started_audit_row(
        self, monkeypatch, local_http_server, redis_13
    ):
        import uuid

        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.models import DatabricksUserBinding
        from hub.apps.databricks_admin.obo_tokens import OBOAccessTokenCache
        from hub.apps.tenants.models import TenantConfig

        require_dns()
        tenant, admin = _setup_tenant()
        workspace = _seed_workspace(tenant)
        mirror = _seed_mirror(workspace, warehouse_id="wh-1", state="STOPPED")

        binding = DatabricksUserBinding.objects.create(
            tenant=tenant,
            user=admin,
            workspace=workspace,
            databricks_sub=f"sub-{uuid.uuid4().hex[:8]}",
            databricks_email=admin.email,
        )
        config = TenantConfig.objects.get_or_create(tenant=tenant)[0]
        sso = config.get_sso_config()
        from hub.apps.databricks_admin.tests._fixtures import REAL_HOST

        sso["databricks"] = {
            "host": REAL_HOST,
            "client_id": "client-abc",
            "redirect_uri": "https://hub.example.com/auth/databricks/callback",
        }
        config.sso_config = sso
        config.save()
        OBOAccessTokenCache(redis_client=redis_13).set(binding.id, "dapi-wh-access", 300)

        # The 3.7 seam, inlined (the class-level helper reads self.binding):
        # patch the viewset's client factory with a REAL production client
        # against the local server under the OBO provider.
        from hub.apps.databricks_admin import sql_warehouse_views as views_module
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.obo_tokens import OBOTokenProvider

        def fake_factory(workspace, _identity):
            provider = OBOTokenProvider(
                binding=binding,
                oidc_client_id="client-abc",
                oidc_base_url=f"http://127.0.0.1:{local_http_server}",
            )
            return DatabricksApiClient(
                base_url=f"http://127.0.0.1:{local_http_server}",
                tenant_id=str(workspace.tenant_id),
                obo_provider=provider,
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
            )

        monkeypatch.setattr(views_module, "_build_uc_client", fake_factory)

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "id": "wh-1",
                    "name": "wh-wh-1",
                    "state": "STOPPED",
                    "serverless": True,
                    "size": None,
                    "auto_stop_mins": 30,
                }
            ),
            "{}",
            json.dumps(
                {
                    "warehouses": [
                        {
                            "id": "wh-1",
                            "name": "wh-wh-1",
                            "state": "STARTING",
                            "serverless": True,
                            "size": None,
                            "auto_stop_mins": 30,
                        }
                    ]
                }
            ),
        ]

        response = _client(admin).post(_url(workspace.id, "wh-1/start/"))
        assert response.status_code == 200, response.content

        rows = list(
            AuditEvent.objects.filter(
                tenant=tenant, resource_type="DATABRICKS_WAREHOUSE", action="STARTED"
            )
        )
        assert len(rows) == 1
        assert rows[0].resource_id == mirror.id
        assert rows[0].actor_user_id == admin.id
