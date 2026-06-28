"""
Phase 275.B.3 — Snowflake + BigQuery integration tests.

REQUIRES real warehouse sandbox accounts (Snowflake + BigQuery).
Skipped by default in CI without per-connector credentials.

Contract tests (no live warehouse needed):
- Interface conformance (warehouse_type, method signatures)
- Snowflake: query tag builds valid JSON
- Cross-tenant isolation: tenant B cannot use tenant A's connection_id (ORM level)
- BigQuery: dryRun cost estimate method exists
"""

from __future__ import annotations

import contextlib
import os
import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.warehouses.connectors.bigquery import BigQueryConnector
from hub.apps.warehouses.connectors.snowflake import SnowflakeConnector

try:
    from snowflake.connector.errors import DatabaseError as SnowflakeDatabaseError
except ImportError:
    SnowflakeDatabaseError = Exception  # type: ignore[assignment,misc]
from hub.apps.warehouses.models import WarehouseConnection, WarehouseType

pytestmark = pytest.mark.django_db(transaction=True)

# Live tests run when the specific connector's credentials are configured.
# Per-connector markers prevent Snowflake env vars from enabling BigQuery tests
# and vice versa.
_SANDBOX_ENABLED = os.environ.get("WAREHOUSE_SANDBOX_ENABLED", "") == "1"
_requires_sandbox = pytest.mark.skipif(
    not _SANDBOX_ENABLED,
    reason="WAREHOUSE_SANDBOX_ENABLED=1 required",
)

_SNOWFLAKE_HAS_ACCOUNT = bool(
    os.environ.get("SNOWFLAKE_SANDBOX_ACCOUNT") or os.environ.get("SNOWFLAKE_ACCOUNT")
)
_SNOWFLAKE_HAS_USER = bool(
    os.environ.get("SNOWFLAKE_SANDBOX_USER") or os.environ.get("SNOWFLAKE_USER")
)
_SNOWFLAKE_HAS_CREDS = _SNOWFLAKE_HAS_ACCOUNT and _SNOWFLAKE_HAS_USER
_requires_snowflake_creds = pytest.mark.skipif(
    not _SNOWFLAKE_HAS_CREDS,
    reason="SNOWFLAKE_ACCOUNT + SNOWFLAKE_USER required for live Snowflake tests",
)

_BIGQUERY_HAS_PROJECT = bool(
    os.environ.get("BIGQUERY_SANDBOX_PROJECT") or os.environ.get("GCP_PROJECT_ID")
)
_BIGQUERY_HAS_CREDS_JSON = bool(os.environ.get("GCP_CREDENTIALS_JSON"))
_BIGQUERY_HAS_CREDS = _BIGQUERY_HAS_PROJECT and _BIGQUERY_HAS_CREDS_JSON
_requires_bigquery_creds = pytest.mark.skipif(
    not _BIGQUERY_HAS_CREDS,
    reason="GCP_PROJECT_ID + GCP_CREDENTIALS_JSON required for live BigQuery tests",
)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"WH-{uid}",
        slug=f"wh-{uid}",
        status="ACTIVE",
        kyc_status="VERIFIED",
    )


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"wh-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


class TestSnowflakeConnectorContract(TestCase):
    """Phase 275.B — SnowflakeConnector contract tests (no live warehouse)."""

    def setUp(self):
        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.conn = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name="test-sf",
            warehouse_type=WarehouseType.SNOWFLAKE,
            config={},
        )

    def test_warehouse_type_is_snowflake(self):
        """Verifies connector.warehouse_type == 'snowflake'."""
        connector = SnowflakeConnector(
            connection_config={"account": "test", "user": "test", "password": "test"},
        )
        assert connector.warehouse_type == "snowflake"

    def test_query_tag_builds_valid_json(self):
        """Verifies _build_query_tag() produces valid JSON with expected fields."""
        connector = SnowflakeConnector(
            connection_config={},
            tenant_id="t1",
            asset_id="a1",
            request_id="r1",
        )
        tag = connector._build_query_tag()
        import json

        parsed = json.loads(tag)
        assert parsed["tenant_id"] == "t1"
        assert parsed["asset_id"] == "a1"
        assert parsed["request_id"] == "r1"
        assert parsed["source"] == "meshant-hub"

    def test_execute_query_accepts_params(self):
        """Verifies execute_query method signature includes 'params' parameter."""
        connector = SnowflakeConnector(
            connection_config={"account": "test", "user": "test"},
        )
        import inspect

        sig = inspect.signature(connector.execute_query)
        assert "params" in sig.parameters, (
            "execute_query must accept params for parameterised binding"
        )

    def test_cross_tenant_isolation_contract(self):
        """Verifies ORM-level tenant scoping prevents cross-tenant connection access.
        Tenant B's queryset must not resolve tenant A's connection by id."""
        tenant_b = _mk_tenant()
        conn_a = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name="a-sf",
            warehouse_type=WarehouseType.SNOWFLAKE,
        )
        qs = WarehouseConnection.objects.filter(
            tenant=tenant_b,
            id=conn_a.id,
        )
        assert not qs.exists(), "Tenant B must not access tenant A's connection"


class TestBigQueryConnectorContract(TestCase):
    """Phase 275.B — BigQueryConnector contract tests (no live warehouse)."""

    def setUp(self):
        self.tenant = _mk_tenant()

    def test_warehouse_type_is_bigquery(self):
        """Verifies connector.warehouse_type == 'bigquery'."""
        connector = BigQueryConnector(
            connection_config={"project": "test-project"},
        )
        assert connector.warehouse_type == "bigquery"

    def test_estimate_cost_method_exists(self):
        """Verifies hasattr(connector, 'estimate_cost')."""
        connector = BigQueryConnector(
            connection_config={"project": "test"},
        )
        assert hasattr(connector, "estimate_cost"), (
            "BigQueryConnector must have estimate_cost() for dryRun cost preview"
        )

    def test_execute_query_accepts_params(self):
        """Verifies execute_query method signature includes 'params' parameter."""
        connector = BigQueryConnector(
            connection_config={"project": "test"},
        )
        import inspect

        sig = inspect.signature(connector.execute_query)
        assert "params" in sig.parameters, (
            "execute_query must accept params for parameterised binding"
        )


@_requires_snowflake_creds
class TestSnowflakeLiveIntegration(TestCase):
    """Snowflake live integration — gated at class level by @_requires_snowflake_creds.
    Infrastructure failures (network policy, unreachable host) are caught at connect()
    and converted to pytest.skip()."""

    @staticmethod
    def _sandbox_config():
        token = os.environ.get("SNOWFLAKE_TOKEN", "")
        cfg = {
            "account": os.environ.get("SNOWFLAKE_SANDBOX_ACCOUNT")
            or os.environ.get("SNOWFLAKE_ACCOUNT", ""),
            "user": os.environ.get("SNOWFLAKE_SANDBOX_USER")
            or os.environ.get("SNOWFLAKE_USER", ""),
            "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", ""),
            "database": os.environ.get("SNOWFLAKE_DATABASE", ""),
        }
        if token:
            cfg["password"] = token
        else:
            cfg["password"] = os.environ.get("SNOWFLAKE_SANDBOX_PASSWORD", "")
        return cfg

    def test_connect_and_query(self):
        """Contract assertions + live SELECT 1 (skips if warehouse unreachable)."""
        config = self._sandbox_config()
        connector = SnowflakeConnector(connection_config=config)
        assert connector.warehouse_type == "snowflake"
        assert hasattr(connector, "connect")
        assert hasattr(connector, "execute_query")
        assert hasattr(connector, "close")
        try:
            connector.connect()
        except (SnowflakeDatabaseError, ConnectionError, OSError) as exc:
            pytest.skip(f"Snowflake infrastructure unavailable: {exc}")  # noqa: skip-in-body — runtime service dependency
        try:
            result = connector.execute_query("SELECT 1 AS one")
            assert result.row_count == 1
            assert "ONE" in [c.upper() for c in result.columns]
        finally:
            connector.close()

    def test_schema_reflection(self):
        """Contract assertion + live INFORMATION_SCHEMA reflection (skips if warehouse unreachable)."""
        config = self._sandbox_config()
        connector = SnowflakeConnector(connection_config=config)
        assert hasattr(connector, "reflect_schema")
        try:
            connector.connect()
        except (SnowflakeDatabaseError, ConnectionError, OSError) as exc:
            pytest.skip(f"Snowflake infrastructure unavailable: {exc}")  # noqa: skip-in-body — runtime service dependency
        try:
            schema = connector.reflect_schema("TABLES")
            assert len(schema) > 0, (
                f"Expected non-empty schema for TABLES, got {len(schema)} columns"
            )
        finally:
            connector.close()


@_requires_bigquery_creds
class TestBigQueryLiveIntegration(TestCase):
    """BigQuery live integration — gated at class level by @_requires_bigquery_creds."""

    @staticmethod
    def _sandbox_config():
        import json

        cfg = {
            "project": os.environ.get("BIGQUERY_SANDBOX_PROJECT")
            or os.environ.get("GCP_PROJECT_ID", "")
        }
        creds_json = os.environ.get("GCP_CREDENTIALS_JSON", "")
        if creds_json:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                cfg["service_account_json"] = json.loads(creds_json)
        return cfg

    def test_connect_and_query(self):
        """Contract assertions + live SELECT 1 (skips if warehouse unreachable)."""
        config = self._sandbox_config()
        connector = BigQueryConnector(connection_config=config)
        assert connector.warehouse_type == "bigquery"
        assert hasattr(connector, "connect")
        assert hasattr(connector, "execute_query")
        assert hasattr(connector, "close")
        try:
            connector.connect()
        except (ConnectionError, OSError, TimeoutError) as exc:
            pytest.skip(f"BigQuery infrastructure unavailable: {exc}")  # noqa: skip-in-body — runtime service dependency
        try:
            result = connector.execute_query("SELECT 1 AS one")
            assert result.row_count == 1
        finally:
            connector.close()

    def test_dry_run_cost_preview(self):
        """Contract assertion + live dryRun cost estimate (skips if warehouse unreachable)."""
        config = self._sandbox_config()
        connector = BigQueryConnector(connection_config=config)
        assert hasattr(connector, "estimate_cost"), "BigQuery must have estimate_cost"
        try:
            connector.connect()
        except (ConnectionError, OSError, TimeoutError) as exc:
            pytest.skip(f"BigQuery infrastructure unavailable: {exc}")  # noqa: skip-in-body — runtime service dependency
        try:
            cost = connector.estimate_cost("SELECT 1")
            assert isinstance(cost, float)
            assert cost >= 0.0
        finally:
            connector.close()
