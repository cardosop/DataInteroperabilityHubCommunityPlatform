"""Phase 6 (openspec wire-databricks-dlt-movement task 6.11) — the
incremental-state round-trip pins (design D5, the spec's "A re-run
resumes from the incremental cursor" scenario): the REAL
``execute_dlt_ingestion`` DATABRICKS_SOURCE path runs twice against the
same real dlt pipeline state store — the second run's read SQL carries
the advanced cursor bound, never a full re-read.

NO MOCKS: real Postgres rows (tenant/ingestion/WarehouseConnection),
the REAL cursor machinery (dlt_incremental's read/advance over the REAL
dlt pipeline state, isolated per test via ``DLT_PIPELINES_DIR``), the
REAL ``WarehouseQueryRunner`` + the REAL dlt filesystem pipeline; the
sanctioned patch point is the connector-factory symbol (a REAL
``WarehouseConnector`` subclass recording the SQL/params it executes —
the 5.3/6.3 recording convention).
"""

from __future__ import annotations

import uuid
from typing import ClassVar
from unittest import mock

import pytest

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus
from hub.apps.warehouses.base import QueryResult, WarehouseConnector
from hub.apps.warehouses.models import WarehouseConnection, WarehouseType

pytestmark = pytest.mark.django_db(transaction=True)

_CONNECTOR_FACTORY = "hub.data_movement.warehouse_query_runner.get_connector_for_connection"

_ROWS = [
    [1, "2026-01-01T00:00:00Z"],
    [2, "2026-01-02T00:00:00Z"],
    [3, "2026-01-03T00:00:00Z"],
]


class RecordingDatabricksConnector(WarehouseConnector):
    """A REAL WarehouseConnector subclass recording every query — the
    connector-factory seam returns it, so the runner executes against
    the recording surface instead of dialing Databricks."""

    warehouse_type = "databricks"
    queries: ClassVar[list[dict]] = []

    def __init__(self, connection_config, timeout_ms=30000, tenant_id=""):
        super().__init__(connection_config, timeout_ms)
        self._tenant_id = tenant_id

    def connect(self):
        self._connected = True

    def execute_query(self, sql, params=None, limit=100):
        type(self).queries.append({"sql": sql, "params": dict(params or {}), "limit": limit})
        return QueryResult(columns=["id", "updated_at"], rows=list(_ROWS), row_count=len(_ROWS))

    def reflect_schema(self, _table_name):
        return []

    def close(self):
        self._connected = False


@pytest.fixture
def recording_connector():
    def factory(_warehouse_type):
        return RecordingDatabricksConnector

    RecordingDatabricksConnector.queries = []
    with mock.patch(_CONNECTOR_FACTORY, factory):
        yield RecordingDatabricksConnector


@pytest.fixture
def isolated_dlt_env(tmp_path, monkeypatch):
    """The real dlt state store isolated per test: the pipeline state
    persists across the two runs INSIDE the test, never across tests."""
    import dlt

    pipelines_dir = tmp_path / "dlt_pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setenv("DLT_PIPELINES_DIR", str(pipelines_dir))
    monkeypatch.setenv("DLT_DATA_DIR", str(tmp_path / "dlt_data"))
    monkeypatch.delenv("DLT_PROJECT_DIR", raising=False)
    try:
        previous_bucket = dlt.config["destination.filesystem.bucket_url"]
    except KeyError:
        previous_bucket = None
    dlt.config["destination.filesystem.bucket_url"] = str(tmp_path / "bucket")
    yield tmp_path
    if previous_bucket is None:
        dlt.config["destination.filesystem.bucket_url"] = None
    else:
        dlt.config["destination.filesystem.bucket_url"] = previous_bucket


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"incr-rt-{uid}",
        slug=f"incr-rt-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_ingestion(tenant, user, connection):
    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"incr-{uuid.uuid4().hex[:8]}",
        source_type="DATABRICKS_SOURCE",
        source_config={
            "warehouse_connection_id": str(connection.id),
            "table": "src.events",
            "cursor_field": "updated_at",
        },
        schedule_type="DAILY",
        schedule_config={"time": "00:00"},
        file_pattern=".*",
        status=ScheduledIngestionStatus.ACTIVE,
        created_by=user,
    )


def _mk_connection(tenant):
    return WarehouseConnection.objects.create(
        tenant=tenant,
        name=f"conn-{uuid.uuid4().hex[:8]}",
        warehouse_type=WarehouseType.DATABRICKS,
        config={"host": "adb-fixture.cloud.databricks.com", "pat_token": "dapi-src"},
    )


class TestIncrementalRoundTrip:
    @pytest.mark.usefixtures("isolated_dlt_env")
    def test_a_rerun_reads_only_after_the_advanced_cursor(
        self, recording_connector, w38_catalog_seams
    ):
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        tenant = _mk_tenant()
        user = User.objects.create_user(
            email=f"incr-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        connection = _mk_connection(tenant)
        scheduled_ingestion = _mk_ingestion(tenant, user, connection)

        first = execute_dlt_ingestion(str(scheduled_ingestion.id))
        second = execute_dlt_ingestion(str(scheduled_ingestion.id))

        assert first.get("error_message") is None, first
        assert second.get("error_message") is None, second
        assert len(recording_connector.queries) == 2

        first_query = recording_connector.queries[0]
        second_query = recording_connector.queries[1]

        # The FIRST run reads unbounded — no cursor bound in the SQL or
        # the parameters.
        assert first_query["params"] == {}, "the first run is a full read — no cursor bound"
        assert "WHERE" not in first_query["sql"]

        # The SECOND run resumes from the advanced cursor — the max
        # cursor value rides as the :last_cursor parameter, never in the
        # SQL text.
        assert second_query["params"] == {"last_cursor": "2026-01-03T00:00:00Z"}
        assert '"updated_at" > :last_cursor' in second_query["sql"]
        assert "2026-01-03" not in second_query["sql"], (
            "the cursor value never rides in the SQL text"
        )
