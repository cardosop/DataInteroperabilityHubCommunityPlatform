"""6.3 — the REAL ``WarehouseQueryRunner._execute_single``.

The runner delegates to the production warehouse connectors through
``get_connector_for_connection`` (the D12 M2M background path — the
connection's own decrypted config IS the identity; a hand-built
credential is never consulted). A missing connection or an empty
credential config fails the run CLOSED with the classified
``WAREHOUSE_CONNECTION_REQUIRED`` error, BEFORE any factory/connector
work and WITHOUT entering the retry budget — never a silently empty
write. ``FakeWarehouseQueryRunner`` stays the non-network seam (pinned
in ``test_warehouse_query_runner.py``).

NO MOCKS: real Postgres rows (tenant + ``WarehouseConnection`` with a
real encrypt→decrypt config round-trip), the REAL runner; the
sanctioned patch points are the module's connector-FACTORY symbol (a
recording factory returning a REAL ``WarehouseConnector`` subclass —
the 5.3 convention) and the retry sleeper (the 4.4 convention).
"""

import uuid

import pytest

from hub.apps.warehouses.base import QueryResult, WarehouseConnector
from hub.apps.warehouses.models import WarehouseConnection, WarehouseType
from hub.data_movement import warehouse_query_runner as runner_module
from hub.data_movement.warehouse_query_runner import (
    WarehouseQueryRunner,
    WarehouseQueryRunnerError,
)

pytestmark = pytest.mark.django_db(transaction=True)

PLAINTEXT_CONFIG = {
    "host": "adb-123.azuredatabricks.net",
    "http_path": "/sql/1.0/warehouses/wh-1",
    "pat_token": "dapi-own-token",
}


def _mk_connection(tenant, *, config=PLAINTEXT_CONFIG, warehouse_type=WarehouseType.DATABRICKS):
    """A REAL WarehouseConnection row — the raw dict config is encrypted
    on save, so the runner's get_config() exercises the real decrypt."""
    return WarehouseConnection.objects.create(
        tenant=tenant,
        name=f"conn-{uuid.uuid4().hex[:8]}",
        warehouse_type=warehouse_type,
        config=config,
    )


def _patch_factory(monkeypatch, *, columns=None, rows=None, fail_on_query=False):
    """Patch the runner module's factory symbol with a recording factory
    returning a REAL WarehouseConnector subclass; the instance registry
    exposes the connector's received config/sql/params/limit and its
    connect/close flags."""
    columns = columns or []
    rows = rows or []
    registry = {"instances": [], "seen_types": []}

    class RecordingConnector(WarehouseConnector):
        warehouse_type = "recording"

        def __init__(self, connection_config, timeout_ms=30_000, tenant_id=""):
            super().__init__(connection_config, timeout_ms)
            self.tenant_id = tenant_id
            self.connected = False
            self.closed = False
            self.received = None
            registry["instances"].append(self)

        def connect(self):
            self.connected = True

        def execute_query(self, sql, params=None, limit=100):
            self.received = {"sql": sql, "params": params, "limit": limit}
            if fail_on_query:
                raise RuntimeError("transport failure")
            return QueryResult(columns=columns, rows=rows, row_count=len(rows))

        def reflect_schema(self, _table_name):
            return []

        def close(self):
            self.closed = True

    def recording_factory(warehouse_type):
        registry["seen_types"].append(warehouse_type)
        return RecordingConnector

    monkeypatch.setattr(runner_module, "get_connector_for_connection", recording_factory)
    return registry


def _no_retry_sleeps(monkeypatch):
    """The retry sleeper seam — any sleep means the classified error
    entered the retry budget, which the fail-closed path must never do."""

    def fail(s):
        raise AssertionError(f"the retry sleeper was consulted ({s}s) — the path must fail fast")

    monkeypatch.setattr(runner_module.time, "sleep", fail)


class TestFromConnectionBinding:
    def test_from_connection_binds_the_connection(self, tenant):
        connection = _mk_connection(tenant)
        runner = WarehouseQueryRunner.from_connection(connection, query_type="dq")
        assert runner.warehouse_type == connection.warehouse_type
        assert runner._connection is connection
        assert runner.query_type == "dq"


class TestRealExecutionDelegatesToTheProductionConnector:
    def test_the_factory_is_consulted_with_the_connection_warehouse_type(self, tenant, monkeypatch):
        connection = _mk_connection(tenant)
        registry = _patch_factory(monkeypatch, columns=["id"], rows=[[1]])
        runner = WarehouseQueryRunner.from_connection(connection)
        runner.execute("SELECT 1")
        assert registry["seen_types"] == [connection.warehouse_type]

    def test_the_connector_receives_the_connection_own_decrypted_config(self, tenant, monkeypatch):
        connection = _mk_connection(tenant)
        registry = _patch_factory(monkeypatch, columns=["id"], rows=[[1]])
        runner = WarehouseQueryRunner.from_connection(connection)
        runner.execute("SELECT 1")
        (instance,) = registry["instances"]
        # The real encrypt→decrypt round-trip — the connector gets the
        # connection's OWN plaintext config, never a hand-built credential.
        assert instance._config == PLAINTEXT_CONFIG
        assert instance.tenant_id == str(connection.tenant_id)

    def test_rows_map_to_dicts_by_the_result_columns(self, tenant, monkeypatch):
        connection = _mk_connection(tenant)
        _patch_factory(monkeypatch, columns=["id", "name"], rows=[[1, "alice"], [2, "bob"]])
        runner = WarehouseQueryRunner.from_connection(connection)
        result = runner.execute("SELECT id, name FROM t")
        assert result == [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]

    def test_params_pass_through_verbatim_and_the_read_is_uncapped(self, tenant, monkeypatch):
        connection = _mk_connection(tenant)
        registry = _patch_factory(monkeypatch, columns=["id"], rows=[[1]])
        runner = WarehouseQueryRunner.from_connection(connection)
        runner.execute("SELECT * FROM t WHERE region = :region", params={"region": "eu"})
        (instance,) = registry["instances"]
        assert instance.received["sql"] == "SELECT * FROM t WHERE region = :region"
        assert instance.received["params"] == {"region": "eu"}
        # limit=0 is the connectors' documented full-fetch convention —
        # the movement read is never silently truncated at 100 rows.
        assert instance.received["limit"] == 0

    def test_the_connector_connects_and_closes(self, tenant, monkeypatch):
        connection = _mk_connection(tenant)
        registry = _patch_factory(monkeypatch, columns=["id"], rows=[[1]])
        runner = WarehouseQueryRunner.from_connection(connection)
        runner.execute("SELECT 1")
        (instance,) = registry["instances"]
        assert instance.connected is True
        assert instance.closed is True

    def test_close_runs_even_when_the_query_raises(self, tenant, monkeypatch):
        # A transport failure retries (3 attempts), each attempt closing
        # the connector — the sleeper seam keeps the budget instant.
        monkeypatch.setattr(runner_module.time, "sleep", lambda _s: None)
        connection = _mk_connection(tenant)
        registry = _patch_factory(monkeypatch, fail_on_query=True)
        runner = WarehouseQueryRunner.from_connection(connection)
        with pytest.raises(RuntimeError, match="3 attempts"):
            runner.execute("SELECT 1")
        assert len(registry["instances"]) == 3
        assert all(instance.closed for instance in registry["instances"])


class TestFailClosedWithoutAConnection:
    def test_a_connection_less_runner_fails_closed_before_any_factory_work(self, monkeypatch):
        _no_retry_sleeps(monkeypatch)

        def factory(_type):
            raise AssertionError("the factory must never be consulted on the fail-closed path")

        monkeypatch.setattr(runner_module, "get_connector_for_connection", factory)
        # The legacy constructor binds no connection — the run must fail
        # with the classified error, never a NotImplementedError crash.
        runner = WarehouseQueryRunner("DATABRICKS", "legacy-credential-ref")
        with pytest.raises(WarehouseQueryRunnerError) as excinfo:
            runner.execute("SELECT 1")
        assert excinfo.value.code == "WAREHOUSE_CONNECTION_REQUIRED"

    def test_an_empty_credential_config_fails_closed_before_any_factory_work(
        self, tenant, monkeypatch
    ):
        _no_retry_sleeps(monkeypatch)

        def factory(_type):
            raise AssertionError("the factory must never be consulted on the fail-closed path")

        monkeypatch.setattr(runner_module, "get_connector_for_connection", factory)
        connection = _mk_connection(tenant, config={})
        runner = WarehouseQueryRunner.from_connection(connection)
        with pytest.raises(WarehouseQueryRunnerError) as excinfo:
            runner.execute("SELECT 1")
        assert excinfo.value.code == "WAREHOUSE_CONNECTION_REQUIRED"


class TestReadOnlyGuardOnTheRealPath:
    def test_write_sql_is_refused_before_any_factory_work(self, tenant, monkeypatch):
        def factory(_type):
            raise AssertionError("the factory must never be consulted for write SQL")

        monkeypatch.setattr(runner_module, "get_connector_for_connection", factory)
        connection = _mk_connection(tenant)
        runner = WarehouseQueryRunner.from_connection(connection)
        with pytest.raises(ValueError, match="DROP"):
            runner.execute("DROP TABLE t")
