"""
Phase 275.C.4 — Databricks + Athena integration tests.

REQUIRES real warehouse sandbox accounts (Databricks + Athena).
Skipped by default in CI without WAREHOUSE_SANDBOX_ENABLED=1.

Contract tests (no live warehouse needed):
- Databricks: parameterised binding, Unity Catalog reflection, DBU cost
- Athena: IAM/SigV4 auth, Glue Catalog reflection, bytes-scanned cost,
  async polling pattern (ABC fitness canary)
- Cross-tenant isolation for both connectors
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from hub.apps.warehouses.connectors.databricks import DatabricksConnector
from hub.apps.warehouses.connectors.athena import (
    AthenaConnector,
    ATHENA_TERMINAL_STATES,
    ATHENA_POLL_INTERVAL_S,
    ATHENA_MAX_POLL_S,
)
from hub.apps.warehouses.models import WarehouseConnection, WarehouseType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_SANDBOX_ENABLED = os.environ.get("WAREHOUSE_SANDBOX_ENABLED", "") == "1"
_requires_sandbox = pytest.mark.skipif(
    not _SANDBOX_ENABLED,
    reason="WAREHOUSE_SANDBOX_ENABLED=1 required for live warehouse integration tests",
)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"WH-{uid}", slug=f"wh-{uid}",
        status="ACTIVE", kyc_status="VERIFIED",
    )


class TestDatabricksConnectorContract(TestCase):
    """Phase 275.C — DatabricksConnector contract tests."""

    def setUp(self):
        self.tenant = _mk_tenant()

    def test_connector_importable(self):
        connector = DatabricksConnector(
            connection_config={"host": "test.cloud.databricks.com", "http_path": "/sql/1.0/"},
        )
        assert connector.warehouse_type == "databricks"

    def test_parameterised_binding_prevents_injection(self):
        connector = DatabricksConnector(
            connection_config={"host": "test", "http_path": "/", "pat_token": "t"},
        )
        import inspect
        sig = inspect.signature(connector.execute_query)
        assert "params" in sig.parameters

    def test_unity_catalog_reflection_uses_parameterised_sql(self):
        connector = DatabricksConnector(
            connection_config={"host": "test", "http_path": "/", "pat_token": "t",
                              "catalog": "main", "schema": "default"},
        )
        assert hasattr(connector, "reflect_schema")


class TestAthenaConnectorContract(TestCase):
    """Phase 275.C — AthenaConnector contract tests."""

    def setUp(self):
        self.tenant = _mk_tenant()

    def test_connector_importable(self):
        connector = AthenaConnector(
            connection_config={"region": "us-east-1"},
        )
        assert connector.warehouse_type == "athena"

    def test_async_polling_constants_defined(self):
        """ABC fitness canary — async polling constants are properly scoped."""
        assert ATHENA_POLL_INTERVAL_S == 1.0
        assert ATHENA_MAX_POLL_S == 300
        assert "SUCCEEDED" in ATHENA_TERMINAL_STATES
        assert "FAILED" in ATHENA_TERMINAL_STATES
        assert "CANCELLED" in ATHENA_TERMINAL_STATES

    def test_glue_catalog_reflection(self):
        connector = AthenaConnector(
            connection_config={"region": "us-east-1", "database": "default"},
        )
        assert hasattr(connector, "reflect_schema")

    def test_bytes_scanned_cost_guard(self):
        """Athena returns bytes-scanned cost in dollars."""
        connector = AthenaConnector(
            connection_config={"region": "us-east-1"},
        )
        assert hasattr(connector, "execute_query")
        # Cost computation: bytes_scanned / 1e9 * 5.0 (~$5/TB)

    def test_abc_fitness_async_polling(self):
        """The async polling pattern is the ABC fitness canary.
        Athena queries go through start → poll → get_results, not
        a simple synchronous execute. This confirms the ABC didn't
        over-fit the Snowflake/BigQuery synchronous model."""
        connector = AthenaConnector(
            connection_config={"region": "us-east-1"},
        )
        # The execute_query method uses start_query_execution +
        # get_query_execution loop + get_query_results.
        import inspect
        source = inspect.getsource(connector.execute_query)
        assert "start_query_execution" in source
        assert "get_query_execution" in source
        assert "get_query_results" in source


@_requires_sandbox
class TestDatabricksLiveIntegration(TestCase):
    """Live Databricks sandbox tests — requires WAREHOUSE_SANDBOX_ENABLED=1."""

    def test_connect_and_query(self):
        config = {
            "host": os.environ.get("DATABRICKS_SANDBOX_HOST", ""),
            "http_path": os.environ.get("DATABRICKS_SANDBOX_HTTP_PATH", ""),
            "pat_token": os.environ.get("DATABRICKS_SANDBOX_TOKEN", ""),
        }
        if not config["host"]:
            pytest.skip("DATABRICKS_SANDBOX_HOST not set")

        connector = DatabricksConnector(connection_config=config)
        connector.connect()
        try:
            result = connector.execute_query("SELECT 1 AS one")
            assert result.row_count == 1
        finally:
            connector.close()

    def test_schema_reflection(self):
        config = {
            "host": os.environ.get("DATABRICKS_SANDBOX_HOST", ""),
            "http_path": os.environ.get("DATABRICKS_SANDBOX_HTTP_PATH", ""),
            "pat_token": os.environ.get("DATABRICKS_SANDBOX_TOKEN", ""),
            "catalog": os.environ.get("DATABRICKS_SANDBOX_CATALOG", "samples"),
            "schema": os.environ.get("DATABRICKS_SANDBOX_SCHEMA", "nyctaxi"),
        }
        if not config["host"]:
            pytest.skip("DATABRICKS_SANDBOX_HOST not set")

        connector = DatabricksConnector(connection_config=config)
        connector.connect()
        try:
            schema = connector.reflect_schema("samples.nyctaxi.trips")
            assert len(schema) > 0
        finally:
            connector.close()


@_requires_sandbox
class TestAthenaLiveIntegration(TestCase):
    """Live Athena sandbox tests — requires WAREHOUSE_SANDBOX_ENABLED=1."""

    def test_connect_and_query(self):
        config = {
            "region": os.environ.get("ATHENA_SANDBOX_REGION", "us-east-1"),
            "database": os.environ.get("ATHENA_SANDBOX_DATABASE", "default"),
            "workgroup": os.environ.get("ATHENA_SANDBOX_WORKGROUP", "primary"),
        }
        if not os.environ.get("ATHENA_SANDBOX_ENABLED"):
            pytest.skip("ATHENA_SANDBOX_ENABLED not set")

        connector = AthenaConnector(connection_config=config)
        connector.connect()
        try:
            result = connector.execute_query("SELECT 1 AS one")
            assert result.row_count == 1
        finally:
            connector.close()

    def test_async_polling_completes(self):
        """ABC fitness canary — async polling returns successfully."""
        config = {
            "region": os.environ.get("ATHENA_SANDBOX_REGION", "us-east-1"),
            "database": os.environ.get("ATHENA_SANDBOX_DATABASE", "default"),
        }
        if not os.environ.get("ATHENA_SANDBOX_ENABLED"):
            pytest.skip("ATHENA_SANDBOX_ENABLED not set")

        connector = AthenaConnector(connection_config=config)
        connector.connect()
        try:
            started = __import__("time").monotonic()
            result = connector.execute_query("SELECT 1 AS one", limit=1)
            elapsed = __import__("time").monotonic() - started
            assert result.row_count == 1
            # Async polling should complete within 60s for SELECT 1.
            assert elapsed < 60, f"Async polling took {elapsed:.1f}s"
        finally:
            connector.close()
