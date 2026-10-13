"""P7 (openspec add-databricks-cost-guardrails task 7.5, design D4) — the
exactly-once cost-recording battery.

ONE ledger row per executed query carrying the source attribution
(``query``/``export``/``ingestion``/``job``) — never a double-counted
pair; the pre-existing per-query cost fields stay read-only mirrors, the
ledger is the truth.

No mocks: real Postgres rows through the real models and the real seam
registry; the AST scans are the structural call-site battery (the 0.11
convention) because the connectors cannot be executed without their
drivers/clouds.

The double-count classes pinned away:
- ``reflect_schema`` delegating to ``execute_query`` must not record its
  own extra entry (the Databricks 0.11 fix, extended to Snowflake);
- non-executed paths (BigQuery dry-run estimate, Glue/Table.get metadata
  reads) keep the metric observability WITHOUT a ledger row — a dry-run
  estimate is not an executed query and must not consume budget.
"""

import ast
import logging
from decimal import Decimal
from pathlib import Path

import pytest

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.warehouses.connectors.databricks import DatabricksConnector
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

CONNECTOR_FILES = [
    "hub/apps/warehouses/connectors/databricks.py",
    "hub/apps/warehouses/connectors/snowflake.py",
    "hub/apps/warehouses/connectors/bigquery.py",
    "hub/apps/warehouses/connectors/athena.py",
]


def _method_calls(path: str, method: str, attr: str) -> int:
    """Count ``self.<attr>(...)`` calls in the AST of *method*."""
    tree = ast.parse(Path(path).read_text())
    target = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method
    )
    return sum(
        1
        for n in ast.walk(target)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == attr
    )


def _record_cost_counts_by_method(path: str) -> dict[str, int]:
    """Map method name → ``_record_cost`` call count for the whole file."""
    tree = ast.parse(Path(path).read_text())
    counts: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            counts[node.name] = sum(
                1
                for n in ast.walk(node)
                if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "_record_cost"
            )
    return counts


def _ledger(tenant):
    from hub.apps.databricks_admin.models import DatabricksCostLedger

    return DatabricksCostLedger.objects.filter(tenant_id=tenant.id)


class _Capture(logging.Handler):
    """A real logging handler attached to the seam's logger — the repo's
    JSON routing keeps caplog from seeing these records, so the pins
    capture the emitted messages directly (no mocks)."""

    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class _ConnectorMixin:
    def _connector(self, **kwargs):
        return DatabricksConnector(
            {"host": "h", "http_path": "/x", "pat_token": "t"},
            **kwargs,
        )


class TestLedgerExactlyOnce(_ConnectorMixin):
    """The spec scenario — 'The ledger records once per executed query':
    exactly ONE row for that execution, carrying the source attribution,
    never a double-counted pair."""

    def test_record_cost_writes_exactly_one_ledger_row(self):
        tenant = TenantFactory.create_tenant()
        connector = self._connector(tenant_id=str(tenant.id))
        connector._record_cost(str(tenant.id), 0.55, "dbu")

        rows = list(_ledger(tenant))
        assert len(rows) == 1, "exactly one ledger row per executed query"
        row = rows[0]
        assert row.source == "query", "the default source attribution is the query surface"
        assert row.units == Decimal("0.55"), "units land as exact decimals — no float noise"
        assert row.unit_label == "dbu"
        assert row.recorded_at is not None, "recorded_at defaults to now (the window reads it)"

    def test_source_attribution_rides_the_record(self):
        tenant = TenantFactory.create_tenant()
        connector = self._connector(tenant_id=str(tenant.id))
        connector._record_cost(str(tenant.id), 1.0, "DBU", source="export")

        row = _ledger(tenant).get()
        assert row.source == "export"

    def test_unknown_source_is_refused_with_no_row_and_no_raise(self):
        tenant = TenantFactory.create_tenant()
        connector = self._connector(tenant_id=str(tenant.id))
        handler = _Capture()
        logging.getLogger("hub.apps.warehouses.cost_recording").addHandler(handler)
        try:
            connector._record_cost(str(tenant.id), 1.0, "dbu", source="bogus")  # no raise
        finally:
            logging.getLogger("hub.apps.warehouses.cost_recording").removeHandler(handler)

        assert not _ledger(tenant).exists(), "an unknown source never lands a ledger row"
        assert any("warehouse_cost_record_failed" in message for message in handler.messages), (
            "the refusal is logged, never swallowed silently"
        )

    def test_negative_units_are_refused_with_no_row_and_no_raise(self):
        tenant = TenantFactory.create_tenant()
        connector = self._connector(tenant_id=str(tenant.id))
        handler = _Capture()
        logging.getLogger("hub.apps.warehouses.cost_recording").addHandler(handler)
        try:
            connector._record_cost(str(tenant.id), -1.0, "dbu")  # no raise
        finally:
            logging.getLogger("hub.apps.warehouses.cost_recording").removeHandler(handler)

        assert not _ledger(tenant).exists()
        assert any("warehouse_cost_record_failed" in message for message in handler.messages), (
            "the refusal is logged, never swallowed silently"
        )

    def test_meta_attribution_is_stored_and_connector_attribution_rides_along(self):
        tenant = TenantFactory.create_tenant()
        connector = DatabricksConnector(
            {"host": "h", "http_path": "/x", "pat_token": "t"},
            tenant_id=str(tenant.id),
            asset_id="asset-1",
            request_id="req-1",
        )
        connector._record_cost(str(tenant.id), 0.25, "dbu", meta={"job_id": "j-9"})

        row = _ledger(tenant).get()
        assert row.meta == {"asset_id": "asset-1", "request_id": "req-1", "job_id": "j-9"}

    def test_record_rides_the_callers_transaction(self):
        # D4 — recorded in the same transaction as the completion
        # bookkeeping where one exists: the row joins the caller's
        # transaction and rolls back with it.
        from django.db import transaction

        tenant = TenantFactory.create_tenant()
        connector = self._connector(tenant_id=str(tenant.id))
        with transaction.atomic():
            connector._record_cost(str(tenant.id), 0.5, "dbu")
            assert _ledger(tenant).count() == 1, "the row is visible inside the transaction"
            transaction.set_rollback(True)
        assert not _ledger(tenant).exists(), "the row rolls back with the caller's transaction"

    def test_an_unknown_tenant_never_breaks_the_query_path(self):
        missing = "00000000-0000-0000-0000-000000000000"
        connector = self._connector(tenant_id=missing)
        handler = _Capture()
        logging.getLogger("hub.apps.warehouses.cost_recording").addHandler(handler)
        try:
            connector._record_cost(missing, 1.0, "dbu")  # no raise — cost never breaks movement
        finally:
            logging.getLogger("hub.apps.warehouses.cost_recording").removeHandler(handler)

        assert not _ledger_row_exists_for(missing)
        assert any("warehouse_cost_record_failed" in message for message in handler.messages), (
            "the failure is logged, never swallowed silently"
        )

    def test_a_failed_backend_never_breaks_the_query_path(self, monkeypatch):
        from hub.apps.warehouses import cost_recording

        def _exploding(_record):
            raise RuntimeError("ledger down")

        # The seam registry is the injection point — the backend IS the seam.
        monkeypatch.setattr(cost_recording, "_registered_backends", [_exploding])
        tenant = TenantFactory.create_tenant()
        connector = self._connector(tenant_id=str(tenant.id))
        handler = _Capture()
        logging.getLogger("hub.apps.warehouses.cost_recording").addHandler(handler)
        try:
            connector._record_cost(str(tenant.id), 1.0, "dbu")  # no raise
        finally:
            logging.getLogger("hub.apps.warehouses.cost_recording").removeHandler(handler)

        assert not _ledger(tenant).exists()
        assert any("warehouse_cost_record_failed" in message for message in handler.messages), (
            "the backend failure is logged, never swallowed silently"
        )


def _ledger_row_exists_for(tenant_id: str) -> bool:
    from hub.apps.databricks_admin.models import DatabricksCostLedger

    return DatabricksCostLedger.objects.filter(tenant_id=tenant_id).exists()


class TestBackendRegistration(_ConnectorMixin):
    """The seam wiring — the databricks_admin ledger writer is registered
    at app-ready and writes real rows through the facade (the
    provider-boundary inversion: warehouses never imports databricks_admin)."""

    def test_the_databricks_ledger_backend_is_registered_and_writes(self):
        from hub.apps.warehouses.cost_recording import CostRecord, record_cost

        tenant = TenantFactory.create_tenant()
        record_cost(CostRecord(tenant_id=str(tenant.id), units=2.0, unit_label="DBU", source="job"))

        row = _ledger(tenant).get()
        assert row.source == "job"
        assert row.units == Decimal("2.0")
        assert row.unit_label == "DBU"

    def test_metric_only_observation_writes_no_ledger_row(self):
        tenant = TenantFactory.create_tenant()
        connector = self._connector(tenant_id=str(tenant.id))
        connector._emit_cost_metric(str(tenant.id), 0.0, "bytes_scanned")

        assert not _ledger(tenant).exists(), (
            "a metric-only observation (dry-run estimate, zero-cost metadata read) "
            "never lands a ledger row"
        )


class TestWorkspaceAttribution(_ConnectorMixin):
    """Workspace/warehouse attribution resolves to the real estate rows."""

    def _workspace(self, tenant, *, name="ws-attr"):
        from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

        return DatabricksWorkspace.objects.create(
            tenant=tenant,
            name=name,
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )

    def _warehouse(self, workspace):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        return DatabricksSqlWarehouse.objects.create(
            workspace=workspace,
            warehouse_id="wh-attr-1",
            name="analytics",
            state="RUNNING",
            serverless=True,
        )

    def test_workspace_attribution_resolves(self):
        require_dns()
        tenant = TenantFactory.create_tenant()
        workspace = self._workspace(tenant)
        connector = self._connector(tenant_id=str(tenant.id))
        connector._record_cost(str(tenant.id), 0.5, "dbu", workspace_id=str(workspace.id))

        row = _ledger(tenant).get()
        assert row.workspace_id == workspace.id

    def test_warehouse_attribution_resolves(self):
        require_dns()
        tenant = TenantFactory.create_tenant()
        workspace = self._workspace(tenant)
        warehouse = self._warehouse(workspace)
        connector = self._connector(tenant_id=str(tenant.id))
        connector._record_cost(
            str(tenant.id),
            0.5,
            "dbu",
            workspace_id=str(workspace.id),
            warehouse_id=str(warehouse.id),
        )

        row = _ledger(tenant).get()
        assert row.workspace_id == workspace.id
        assert row.warehouse_id == warehouse.id


class TestCallSiteContract:
    """The structural battery (the 0.11 convention) — one record call per
    completion path, none anywhere else."""

    def test_record_cost_lives_only_inside_execute_query(self):
        for path in CONNECTOR_FILES:
            nonzero = {
                method: count
                for method, count in _record_cost_counts_by_method(path).items()
                if count
            }
            assert nonzero == {"execute_query": 1}, (
                f"{path}: _record_cost must live ONLY inside execute_query, "
                f"exactly once — found {nonzero}"
            )

    def test_reflect_schema_never_records_its_own_entry(self):
        # The double-count class: reflect_schema delegating to execute_query
        # records the inner query's cost again. Zero extra calls.
        for path in CONNECTOR_FILES:
            assert _method_calls(path, "reflect_schema", "_record_cost") == 0, path

    def test_non_executed_paths_keep_metric_only(self):
        # Dry-run estimates and zero-cost metadata reads keep the metric
        # observability but must NOT consume budget through the ledger.
        cases = {
            "hub/apps/warehouses/connectors/bigquery.py": ["estimate_cost", "reflect_schema"],
            "hub/apps/warehouses/connectors/athena.py": ["reflect_schema"],
        }
        for path, methods in cases.items():
            for method in methods:
                assert _method_calls(path, method, "_record_cost") == 0, (path, method)
                assert _method_calls(path, method, "_emit_cost_metric") == 1, (path, method)


class TestWindowJoin:
    """The 7.4 recorder join — every per-query ledger write ALSO lands in
    the Redis rolling-hour window (the 7.4 note's "the 7.5 per-query
    chokepoint joins the same recorder"). Real Redis (the p313 runbook
    convention); db 12 — NOT the 7.4/7.6 suites' db 13 — so the
    documented cross-session flush collision class cannot reach us."""

    @pytest.fixture
    def redis_window(self):
        import os
        from urllib.parse import urlparse

        import redis

        from envpolicy import environment_guard

        # REDIS_URL-aware (the data_movement conftest pattern): in-container
        # batches carry redis://redis-cache-test:6379/0 — the hardcoded
        # 127.0.0.1:63799 is the host-side p313 mapping and a dead loopback
        # inside the container. db 12 stays pinned (NOT the 7.4/7.6 suites'
        # db 13).
        url = os.environ.get("REDIS_URL", "redis://127.0.0.1:63799/0")
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 63799
        try:
            redis.Redis(host=host, port=port, db=12).ping()
        except (redis.RedisError, ConnectionError, OSError):
            environment_guard(f"redis ({host}:{port}) unavailable — real Redis required")
            pytest.skip(f"redis ({host}:{port}) unavailable — real Redis required")
        client = redis.Redis(host=host, port=port, db=12, decode_responses=True)
        client.flushdb()
        try:
            yield client
        finally:
            client.flushdb()

    def test_the_per_query_write_joins_the_window_recorder(self, redis_window):
        from hub.apps.databricks_admin.budget_window import window_sum
        from hub.apps.databricks_admin.cost_ledger import record_ledger_cost
        from hub.apps.warehouses.cost_recording import CostRecord

        tenant = TenantFactory.create_tenant()
        # The writer's factory seam is the injection point (the 7.4
        # convention) — the production path builds the cache-pool client.
        row = record_ledger_cost(
            CostRecord(tenant_id=str(tenant.id), units=3.0, unit_label="dbu"),
            redis_client_factory=lambda: redis_window,
        )

        assert row.id is not None, "the ledger row still lands exactly once"
        assert window_sum(redis_window, str(tenant.id)) == Decimal("3.0"), (
            "the per-query cost lands in the rolling window the enforcement reads"
        )


class TestBaseAttribution:
    """The base __init__ carries the tenant/asset/request attribution for
    every connector (the restructure moves the shared state up)."""

    def test_base_init_carries_the_attribution_fields(self):
        connector = DatabricksConnector(
            {"host": "h"},
            tenant_id="t1",
            asset_id="a1",
            request_id="r1",
        )
        assert connector._tenant_id == "t1"
        assert connector._asset_id == "a1"
        assert connector._request_id == "r1"
