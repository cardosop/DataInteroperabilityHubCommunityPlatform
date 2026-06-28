"""
Phase 275.C.4 — Databricks + Athena integration tests.

REQUIRES real warehouse sandbox accounts (Databricks + Athena).
Skipped by default in CI without per-connector credentials.

Contract tests (no live warehouse needed):
- Databricks: interface conformance (warehouse_type, method signatures)
- Athena: interface conformance, async polling constants, method signatures
"""

from __future__ import annotations

import os
import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.warehouses.connectors.athena import (
    ATHENA_MAX_POLL_S,
    ATHENA_POLL_INTERVAL_S,
    ATHENA_TERMINAL_STATES,
    AthenaConnector,
)
from hub.apps.warehouses.connectors.databricks import DatabricksConnector

pytestmark = pytest.mark.django_db(transaction=True)

_SANDBOX_ENABLED = os.environ.get("WAREHOUSE_SANDBOX_ENABLED", "") == "1"
_requires_sandbox = pytest.mark.skipif(
    not _SANDBOX_ENABLED,
    reason="WAREHOUSE_SANDBOX_ENABLED=1 required",
)

_DATABRICKS_HOST_SET = bool(os.environ.get("DATABRICKS_HOST"))
_DATABRICKS_SANDBOX_HOST_SET = bool(os.environ.get("DATABRICKS_SANDBOX_HOST"))
_DATABRICKS_HAS_HOST = _DATABRICKS_HOST_SET or _DATABRICKS_SANDBOX_HOST_SET
_DATABRICKS_HAS_TOKEN = bool(
    os.environ.get("DATABRICKS_SANDBOX_TOKEN")
    or os.environ.get("DATABRICKS_TOKEN")
)
# HTTP path may be provided explicitly, or auto-constructed from
# DATABRICKS_CLUSTER_ID + the workspace ID extracted from DATABRICKS_HOST.
_DATABRICKS_HAS_HTTP_PATH = bool(
    os.environ.get("DATABRICKS_SANDBOX_HTTP_PATH")
    or os.environ.get("DATABRICKS_HTTP_PATH")
    or os.environ.get("DATABRICKS_CLUSTER_ID")
)
_DATABRICKS_HAS_CREDS = (
    _DATABRICKS_HAS_HOST and _DATABRICKS_HAS_HTTP_PATH and _DATABRICKS_HAS_TOKEN
)
_requires_databricks_creds = pytest.mark.skipif(
    not _DATABRICKS_HAS_CREDS,
    reason="DATABRICKS_HOST + DATABRICKS_HTTP_PATH + DATABRICKS_TOKEN all required",
)

_ATHENA_HAS_ACCESS_KEY = bool(os.environ.get("ATHENA_AWS_ACCESS_KEY_ID"))
_ATHENA_HAS_SECRET_KEY = bool(os.environ.get("ATHENA_AWS_SECRET_ACCESS_KEY"))
_ATHENA_SANDBOX_ENABLED = bool(os.environ.get("ATHENA_SANDBOX_ENABLED"))
_ATHENA_HAS_CREDS = (
    _ATHENA_SANDBOX_ENABLED and _ATHENA_HAS_ACCESS_KEY and _ATHENA_HAS_SECRET_KEY
)
_requires_athena_sandbox = pytest.mark.skipif(
    not _ATHENA_HAS_CREDS,
    reason="ATHENA_SANDBOX_ENABLED + ATHENA_AWS_ACCESS_KEY_ID + ATHENA_AWS_SECRET_ACCESS_KEY all required",
)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"WH-{uid}",
        slug=f"wh-{uid}",
        status="ACTIVE",
        kyc_status="VERIFIED",
    )


class _ConnectorContractMixin:
    """Shared assertions for all connector contract tests — eliminates
    copy-paste across the four connector contract test classes."""

    def assert_has_standard_interface(self, connector, expected_warehouse_type):
        """Every connector must expose warehouse_type + connect/execute_query/close."""
        assert connector.warehouse_type == expected_warehouse_type, (
            f"Expected warehouse_type={expected_warehouse_type}, "
            f"got {connector.warehouse_type}"
        )
        assert hasattr(connector, "connect"), "Connector must have connect()"
        assert hasattr(connector, "execute_query"), "Connector must have execute_query()"
        assert hasattr(connector, "close"), "Connector must have close()"

    @staticmethod
    def assert_execute_query_accepts_params(connector):
        """execute_query method signature must include 'params' for parameterised binding."""
        import inspect

        sig = inspect.signature(connector.execute_query)
        assert "params" in sig.parameters, (
            "execute_query must accept 'params' for parameterised query binding"
        )


class TestDatabricksConnectorContract(_ConnectorContractMixin, TestCase):
    """Phase 275.C — DatabricksConnector contract tests."""

    def setUp(self):
        self.tenant = _mk_tenant()

    def test_warehouse_type_is_databricks(self):
        """Verifies connector.warehouse_type == 'databricks'."""
        connector = DatabricksConnector(
            connection_config={"host": "test.cloud.databricks.com", "http_path": "/sql/1.0/"},
        )
        assert connector.warehouse_type == "databricks"

    def test_execute_query_accepts_params(self):
        """Verifies execute_query method signature includes 'params' parameter."""
        connector = DatabricksConnector(
            connection_config={"host": "test", "http_path": "/", "pat_token": "t"},
        )
        self.assert_execute_query_accepts_params(connector)

    def test_reflect_schema_method_exists(self):
        """Verifies hasattr(connector, 'reflect_schema')."""
        connector = DatabricksConnector(
            connection_config={
                "host": "test",
                "http_path": "/",
                "pat_token": "t",
                "catalog": "main",
                "schema": "default",
            },
        )
        assert hasattr(connector, "reflect_schema")


class TestAthenaConnectorContract(_ConnectorContractMixin, TestCase):
    """Phase 275.C — AthenaConnector contract tests."""

    def setUp(self):
        self.tenant = _mk_tenant()

    def test_warehouse_type_is_athena(self):
        """Verifies connector.warehouse_type == 'athena'."""
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

    def test_reflect_schema_method_exists(self):
        """Verifies hasattr(connector, 'reflect_schema')."""
        connector = AthenaConnector(
            connection_config={"region": "us-east-1", "database": "default"},
        )
        assert hasattr(connector, "reflect_schema")

    def test_execute_query_method_exists(self):
        """Verifies hasattr(connector, 'execute_query')."""
        connector = AthenaConnector(
            connection_config={"region": "us-east-1"},
        )
        assert hasattr(connector, "execute_query")

    def test_async_polling_constants_and_signature(self):
        """Verifies polling constants are positive, terminal states are defined,
        and execute_query method signature is callable."""
        connector = AthenaConnector(
            connection_config={"region": "us-east-1"},
        )
        assert hasattr(connector, "execute_query")
        assert callable(connector.execute_query)
        assert ATHENA_MAX_POLL_S > 0, "Async polling must have a max poll duration"
        assert ATHENA_POLL_INTERVAL_S > 0, "Async polling must have a poll interval"
        assert "SUCCEEDED" in ATHENA_TERMINAL_STATES
        assert "FAILED" in ATHENA_TERMINAL_STATES
        assert "CANCELLED" in ATHENA_TERMINAL_STATES


@_requires_databricks_creds
class TestDatabricksLiveIntegration(TestCase):
    """Databricks live integration — gated at class level by @_requires_databricks_creds.
    Contract assertions always run within the live methods."""

    @staticmethod
    def _sandbox_config():
        host = os.environ.get("DATABRICKS_SANDBOX_HOST") or os.environ.get("DATABRICKS_HOST", "")
        http_path = (
            os.environ.get("DATABRICKS_SANDBOX_HTTP_PATH")
            or os.environ.get("DATABRICKS_HTTP_PATH", "")
        )
        # Auto-construct HTTP path from cluster ID + host if no explicit path set.
        # For SQL warehouses: /sql/1.0/warehouses/<cluster_id>
        if not http_path:
            cluster_id = os.environ.get("DATABRICKS_CLUSTER_ID", "")
            if cluster_id:
                http_path = f"/sql/1.0/warehouses/{cluster_id}"
        return {
            "host": host,
            "http_path": http_path,
            "pat_token": os.environ.get("DATABRICKS_SANDBOX_TOKEN")
            or os.environ.get("DATABRICKS_TOKEN", ""),
            "catalog": os.environ.get("DATABRICKS_SANDBOX_CATALOG", "samples"),
            "schema": os.environ.get("DATABRICKS_SANDBOX_SCHEMA", "nyctaxi"),
        }

    def test_connect_and_query(self):
        """Contract assertions + live SELECT 1 (skips if warehouse unreachable)."""
        config = self._sandbox_config()
        connector = DatabricksConnector(connection_config=config)
        assert connector.warehouse_type == "databricks"
        assert hasattr(connector, "connect")
        assert hasattr(connector, "execute_query")
        assert hasattr(connector, "close")
        try:
            connector.connect()
        except (ConnectionError, OSError, TimeoutError, ValueError) as exc:
            pytest.skip(f"Databricks infrastructure unavailable: {exc}")  # noqa: skip-in-body — runtime service dependency
        try:
            result = connector.execute_query("SELECT 1 AS one")
            assert result.row_count == 1
        finally:
            connector.close()

    def test_schema_reflection(self):
        """Contract assertion + live Unity Catalog reflection (skips if warehouse unreachable)."""
        config = self._sandbox_config()
        connector = DatabricksConnector(connection_config=config)
        assert hasattr(connector, "reflect_schema")
        try:
            connector.connect()
        except (ConnectionError, OSError, TimeoutError, ValueError) as exc:
            pytest.skip(f"Databricks infrastructure unavailable: {exc}")  # noqa: skip-in-body — runtime service dependency
        try:
            schema = connector.reflect_schema("samples.nyctaxi.trips")
            assert len(schema) > 0
        finally:
            connector.close()


@_requires_athena_sandbox
class TestAthenaLiveIntegration(TestCase):
    """Athena live integration — gated at class level by @_requires_athena_sandbox."""

    @staticmethod
    def _sandbox_config():
        cfg = {
            "region": os.environ.get("ATHENA_SANDBOX_REGION", "us-east-1"),
            "database": os.environ.get("ATHENA_SANDBOX_DATABASE", "default"),
            "workgroup": os.environ.get("ATHENA_SANDBOX_WORKGROUP", "primary"),
            "output_location": os.environ.get("ATHENA_OUTPUT_LOCATION", ""),
        }
        if os.environ.get("ATHENA_AWS_ACCESS_KEY_ID"):
            cfg["aws_access_key_id"] = os.environ["ATHENA_AWS_ACCESS_KEY_ID"]
            cfg["aws_secret_access_key"] = os.environ["ATHENA_AWS_SECRET_ACCESS_KEY"]
        return cfg

    def test_connect_and_query(self):
        """Contract assertions + live SELECT 1 (skips if warehouse unreachable)."""
        config = self._sandbox_config()
        connector = AthenaConnector(connection_config=config)
        assert connector.warehouse_type == "athena"
        assert hasattr(connector, "connect")
        assert hasattr(connector, "execute_query")
        assert hasattr(connector, "close")
        try:
            connector.connect()
        except (ConnectionError, OSError, TimeoutError) as exc:
            pytest.skip(f"Athena infrastructure unavailable: {exc}")  # noqa: skip-in-body — runtime service dependency
        try:
            result = connector.execute_query("SELECT 1 AS one")
            assert result.row_count == 1
        finally:
            connector.close()
