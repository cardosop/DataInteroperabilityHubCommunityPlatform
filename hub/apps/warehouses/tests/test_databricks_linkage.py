"""P0 (openspec add-databricks-control-plane task 0.10) — connection linkage.

``WarehouseConnection`` gains OPTIONAL FKs to the control-plane workspace
and credential, plus a derive helper that builds a ready-to-save connection
from a workspace + PAT credential. No mocks: real Postgres, real Fernet
encryption, real SET_NULL cascade behavior.
"""

import json
import uuid

import pytest
from django.db import connection
from django.test import TestCase

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksCredential,
    DatabricksCredentialAuthMode,
    DatabricksSqlWarehouse,
    DatabricksWorkspace,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.warehouses.models import WarehouseConnection, WarehouseType
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class WarehouseConnectionDatabricksLinkageTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="prod",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        self.credential = DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-link-secret"},
        )

    def _connection(self, **overrides):
        kwargs = {
            "tenant": self.tenant,
            "name": "linked",
            "warehouse_type": WarehouseType.DATABRICKS,
            "config": {
                "host": REAL_HOST,
                "http_path": "/sql/1.0/warehouses/wh-1",
                "pat_token": "dapi-own-token",
            },
        }
        kwargs.update(overrides)
        return WarehouseConnection.objects.create(**kwargs)

    def test_linkage_fields_are_optional(self):
        conn = self._connection()
        assert conn.databricks_workspace is None
        assert conn.databricks_credential is None

    def test_linkage_roundtrip(self):
        conn = self._connection(
            databricks_workspace=self.workspace,
            databricks_credential=self.credential,
        )
        conn.refresh_from_db()
        assert conn.databricks_workspace_id == self.workspace.id
        assert conn.databricks_credential_id == self.credential.id

    def test_workspace_delete_sets_null_and_keeps_connection(self):
        conn = self._connection(
            databricks_workspace=self.workspace,
            databricks_credential=self.credential,
        )
        self.workspace.delete()

        conn.refresh_from_db()
        assert conn.databricks_workspace is None, "linkage is SET_NULL — the connection survives"
        # The connection's OWN encrypted config is untouched by the unlink.
        assert conn.get_config().get("pat_token") == "dapi-own-token"

    def test_credential_delete_sets_null(self):
        conn = self._connection(
            databricks_workspace=self.workspace,
            databricks_credential=self.credential,
        )
        self.credential.delete()

        conn.refresh_from_db()
        assert conn.databricks_credential is None
        assert conn.databricks_workspace_id == self.workspace.id


class DeriveHelperTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="prod",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        self.credential = DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-derive-secret"},
        )

    def _raw_config_column(self, conn) -> str:
        with connection.cursor() as cursor:
            cursor.execute("SELECT config FROM warehouse_connections WHERE id = %s", [conn.id])
            row = cursor.fetchone()
        assert row is not None
        return row[0]

    def test_derive_builds_ready_to_save_connection(self):
        conn = WarehouseConnection.derive_from_databricks(
            self.workspace,
            self.credential,
            http_path="/sql/1.0/warehouses/wh-9",
        )
        # pk is NOT None here — UUIDField(default=uuid.uuid4) assigns at
        # instantiation; the real unsaved check is Django's adding flag.
        assert conn._state.adding is True, "derive returns an unsaved instance"
        assert conn.tenant_id == self.tenant.id
        assert conn.warehouse_type == WarehouseType.DATABRICKS
        assert conn.databricks_workspace_id == self.workspace.id
        assert conn.databricks_credential_id == self.credential.id
        assert conn.region == "us-east-1"
        assert conn.name

        # The config is ALREADY encrypted in-memory (wrapper shape), and
        # decodes through the real chain to the connector's expected keys.
        assert conn.get_config() == {
            "host": REAL_HOST,
            "http_path": "/sql/1.0/warehouses/wh-9",
            "pat_token": "dapi-derive-secret",
        }

    def test_derive_persists_ciphertext_only(self):
        conn = WarehouseConnection.derive_from_databricks(
            self.workspace,
            self.credential,
            http_path="/sql/1.0/warehouses/wh-9",
        )
        conn.save()

        raw = self._raw_config_column(conn)
        raw_text = raw if isinstance(raw, str) else json.dumps(raw)
        # WarehouseConnection stores the BARE Fernet ciphertext (its own
        # set_config convention — the {"_encrypted": ...} wrapper is the
        # MarketplaceConnection shape). The security contract is identical:
        # no plaintext ever reaches the column.
        assert "dapi-derive-secret" not in raw_text, "credential token must never reach the column"
        assert conn.get_config().get("pat_token") == "dapi-derive-secret", "real-chain round-trip"

    def test_derive_rejects_foreign_credential(self):
        other_workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="other",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        foreign_credential = DatabricksCredential.objects.create(
            workspace=other_workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-foreign"},
        )
        with pytest.raises(ValueError, match="does not belong"):
            WarehouseConnection.derive_from_databricks(self.workspace, foreign_credential)


class DeriveGuardTests(TestCase):
    """0.10 review — "PAT only for now" must be ENFORCED, not documented:
    an M2M credential, a credential without a token, or an empty http_path
    must fail at derivation — a silently-degraded connection (empty
    pat_token / empty http_path) fails only later, at connect time."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="prod",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )

    def test_derive_rejects_m2m_credential(self):
        credential = DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M,
            config={"client_id": "cid-1", "client_secret": "secret-1"},
        )
        with pytest.raises(ValueError, match="PAT"):
            WarehouseConnection.derive_from_databricks(
                self.workspace, credential, http_path="/sql/1.0/warehouses/wh-1"
            )

    def test_derive_rejects_credential_without_token(self):
        credential = DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"comment": "token missing"},
        )
        with pytest.raises(ValueError, match="token"):
            WarehouseConnection.derive_from_databricks(
                self.workspace, credential, http_path="/sql/1.0/warehouses/wh-1"
            )

    def test_derive_rejects_empty_http_path(self):
        credential = DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-ok"},
        )
        with pytest.raises(ValueError, match="http_path"):
            WarehouseConnection.derive_from_databricks(self.workspace, credential)
        with pytest.raises(ValueError, match="http_path"):
            WarehouseConnection.derive_from_databricks(self.workspace, credential, http_path="")


class DeriveFromSqlWarehouseTests(TestCase):
    """P3 (openspec add-databricks-sql-warehouses task 3.6) — the http_path
    derivation at the linkage boundary.

    The spec scenario: a mirror row with id W derives the connection's
    http_path as ``/sql/1.0/warehouses/W`` — the connector's canonical
    form. The path is DERIVED, never stored twice: the mirror row stays
    the source of the id (no http_path field on the mirror), the
    connection stores the derived path in its encrypted config.

    The classmethod duck-reads the warehouse row (``warehouse_id``/
    ``workspace_id``/``name`` attributes) — the provider-boundary
    contract forbids importing ``databricks_admin`` models into this
    app; the 0.10 string-comparison discipline.
    """

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="prod",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        self.credential = DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-p3-secret"},
        )
        self.sql_warehouse = DatabricksSqlWarehouse.objects.create(
            workspace=self.workspace,
            warehouse_id="wh-p3",
            name="etl-p3",
            state="RUNNING",
        )

    def _raw_config_column(self, conn) -> str:
        with connection.cursor() as cursor:
            cursor.execute("SELECT config FROM warehouse_connections WHERE id = %s", [conn.id])
            row = cursor.fetchone()
        assert row is not None
        return row[0]

    def test_derive_builds_the_canonical_http_path(self):
        # Spec scenario: a mirror row with id W derives
        # /sql/1.0/warehouses/W.
        conn = WarehouseConnection.derive_from_sql_warehouse(
            self.workspace, self.credential, self.sql_warehouse
        )
        assert conn._state.adding is True, "derive returns an unsaved instance"
        assert conn.tenant_id == self.tenant.id
        assert conn.warehouse_type == WarehouseType.DATABRICKS
        assert conn.databricks_workspace_id == self.workspace.id
        assert conn.databricks_credential_id == self.credential.id
        assert conn.name == "etl-p3 connection"
        assert conn.get_config() == {
            "host": REAL_HOST,
            "http_path": "/sql/1.0/warehouses/wh-p3",
            "pat_token": "dapi-p3-secret",
        }

    def test_derive_persists_ciphertext_only(self):
        conn = WarehouseConnection.derive_from_sql_warehouse(
            self.workspace, self.credential, self.sql_warehouse
        )
        conn.save()

        raw = self._raw_config_column(conn)
        raw_text = raw if isinstance(raw, str) else json.dumps(raw)
        assert "dapi-p3-secret" not in raw_text, "credential token must never reach the column"
        assert "/sql/1.0/warehouses/wh-p3" not in raw_text, (
            "the derived path must never reach the column in plaintext"
        )
        assert conn.get_config().get("http_path") == "/sql/1.0/warehouses/wh-p3"

    def test_the_derived_path_round_trips_the_executor_parser(self):
        # The producer of the form (the linkage) and the consumer (the SQL
        # executor's resolve_warehouse_id) must agree on the canonical
        # /sql/1.0/warehouses/{id} shape — a drift here breaks queries.
        from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor

        conn = WarehouseConnection.derive_from_sql_warehouse(
            self.workspace, self.credential, self.sql_warehouse
        )
        assert SqlStatementExecutor.resolve_warehouse_id(conn.get_config()["http_path"]) == "wh-p3"

    def test_derive_rejects_a_foreign_workspace_warehouse(self):
        other_workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="other",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        foreign_warehouse = DatabricksSqlWarehouse.objects.create(
            workspace=other_workspace,
            warehouse_id="wh-foreign",
            name="etl-foreign",
            state="RUNNING",
        )
        with pytest.raises(ValueError, match="does not belong"):
            WarehouseConnection.derive_from_sql_warehouse(
                self.workspace, self.credential, foreign_warehouse
            )

    def test_derive_rejects_an_empty_warehouse_id(self):
        # The mirror MODEL already rejects blank ids (full_clean's
        # blank=False default — a real row cannot carry one), so the
        # guard is pinned against duck-typed stand-ins (the 3.4
        # dangling-plan convention): the derivation boundary must refuse
        # an empty id from ANY object shape, never format a bare
        # /sql/1.0/warehouses/ path.
        import types

        for bad_id in ("", "   "):
            duck = types.SimpleNamespace(
                warehouse_id=bad_id, workspace_id=self.workspace.id, name="blank"
            )
            with pytest.raises(ValueError, match="warehouse id"):
                WarehouseConnection.derive_from_sql_warehouse(self.workspace, self.credential, duck)

    def test_derive_rejects_a_non_string_warehouse_id(self):
        import types

        duck = types.SimpleNamespace(warehouse_id=123, workspace_id=self.workspace.id, name="duck")
        with pytest.raises(TypeError, match="string"):
            WarehouseConnection.derive_from_sql_warehouse(self.workspace, self.credential, duck)

    def test_derive_rejects_a_slash_bearing_warehouse_id(self):
        # A slash in the id would produce /sql/1.0/warehouses/wh/1 — a
        # structurally broken path the executor's resolve_warehouse_id
        # mis-parses to "wh" (the producer/consumer contract breach).
        import types

        duck = types.SimpleNamespace(
            warehouse_id="wh/1", workspace_id=self.workspace.id, name="slashy"
        )
        with pytest.raises(ValueError, match="/"):
            WarehouseConnection.derive_from_sql_warehouse(self.workspace, self.credential, duck)

    def test_foreign_workspace_guard_tolerates_an_idless_duck(self):
        # The guard's error message must not REQUIRE the duck's id
        # attribute — a stand-in without one still gets the classified
        # ValueError, never an AttributeError.
        import types

        duck = types.SimpleNamespace(workspace_id=uuid.uuid4(), warehouse_id="wh-x", name="x")
        with pytest.raises(ValueError, match="does not belong"):
            WarehouseConnection.derive_from_sql_warehouse(self.workspace, self.credential, duck)

    def test_derive_inherits_the_pat_contract(self):
        # The composed 0.10 guard still applies: the P3 linkage must not
        # bypass the PAT-only contract with an M2M credential.
        m2m_credential = DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M,
            config={"client_id": "cid-1", "client_secret": "secret-1"},
        )
        with pytest.raises(ValueError, match="PAT"):
            WarehouseConnection.derive_from_sql_warehouse(
                self.workspace, m2m_credential, self.sql_warehouse
            )

    def test_derive_respects_an_explicit_name(self):
        conn = WarehouseConnection.derive_from_sql_warehouse(
            self.workspace, self.credential, self.sql_warehouse, name="custom-name"
        )
        assert conn.name == "custom-name"

    def test_the_mirror_stores_no_http_path_field(self):
        # The path is DERIVED, never stored twice — the mirror row carries
        # only the id (D5).
        field_names = [f.name for f in DatabricksSqlWarehouse._meta.get_fields()]
        assert "http_path" not in field_names
