"""TDD pins for the Databricks credential resolution (openspec
add-databricks-control-plane Phase 11 task 11.3) — the Hub-model
paths that FEED the existing ``credential_resolver.py`` databricks
branch (``_build_dbt_profile`` / ``_databricks_output``).

- ``resolve_databricks_workspace_credentials`` — a registered
  ``DatabricksWorkspace``'s OWN credential (PAT token direct; OAUTH_M2M
  through the production exchange + the REAL M2M token cache) + the
  workspace host + the caller's SQL-warehouse http_path → a dbt
  profiles.yml dict.
- ``resolve_databricks_connection_credentials`` — a DATABRICKS
  ``WarehouseConnection``'s OWN decrypted config (host/http_path) +
  the PAT/M2M token material (the same cache + production-exchange
  primitives the 6.6 movement seam uses — composed, never
  reimplemented) → a dbt profiles.yml dict.

Fail-closed everywhere: no credential row, an empty token, a missing
host/http_path, or a non-Databricks connection refuses with
``CredentialResolverError`` (the module's own family) naming the bit
— ZERO network calls. The token value is never logged.

No mocks: REAL Postgres rows (workspace + credential + connection
through the REAL encryption), the REAL M2M token cache over a REAL
Redis client (a dedicated db — the shared db-13 is flushed per-test by
other suites), and the PRODUCTION M2M exchange
(``warehouses.connectors.databricks.resolve_access_token``) against a
REAL threaded local OIDC server.
"""

import http.server
import json
import threading
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _redis_client():
    """A REAL redis client on a dedicated db (12) — the shared db-13 is
    flushed per-test by other suites; the token pins must never collide
    (the 6.6 convention)."""
    import redis

    return redis.Redis.from_url("redis://127.0.0.1:63799/12")


def _token_cache():
    try:
        from hub.apps.databricks_admin.token_cache import M2MTokenCache
    except (RuntimeError, ModuleNotFoundError):
        pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

    client = _redis_client()
    cache = M2MTokenCache(redis_client=client)
    # Residue-proof: unique key prefixes per test via the caller's
    # workspace key — a stale entry from a prior run is never trusted
    # unless it matches the credential ref (a sha256 of client id+secret,
    # unique per test).
    return cache


def _oidc_server():
    """A REAL threaded local OIDC server (the 0b.5 convention) — serves
    one token envelope, records every request."""
    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = [
        json.dumps({"access_token": "m2m-bearer", "token_type": "Bearer", "expires_in": 3600})
    ]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


class TestWorkspaceResolution(TestCase):
    """The workspace path: PAT direct, M2M via the production exchange."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _make_workspace(self.tenant, name=f"ws-dbt-{uuid.uuid4().hex[:8]}")

    def _credential(self, *, auth_mode="PAT", config=None):
        try:
            from hub.apps.databricks_admin.models import DatabricksCredential
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        return DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=auth_mode,
            config=config or ({"token": "dapi-pat-token"} if auth_mode == "PAT" else {}),
        )

    def _resolve(self, **kwargs):
        from hub.apps.transformation.credential_resolver import (
            resolve_databricks_workspace_credentials,
        )

        return resolve_databricks_workspace_credentials(self.workspace, **kwargs)

    def test_a_pat_workspace_resolves_the_dbt_profile(self):
        self._credential()
        profile = self._resolve(
            http_path="/sql/1.0/warehouses/wh1", catalog="meshant", schema="gold"
        )

        output = profile["meshant_dbt"]["outputs"]["prod"]
        assert output["type"] == "databricks"
        assert output["host"] == self.workspace.host
        assert output["http_path"] == "/sql/1.0/warehouses/wh1"
        assert output["token"] == "dapi-pat-token", "the REAL decrypted PAT material"
        assert output["catalog"] == "meshant"
        assert output["schema"] == "gold"

    def test_m2m_resolves_the_bearer_through_the_production_exchange(self):
        self._credential(
            auth_mode="OAUTH_M2M", config={"client_id": "cid-1", "client_secret": "csecret-1"}
        )
        server, port = _oidc_server()
        self.addCleanup(server.shutdown)

        profile = self._resolve(
            http_path="/sql/1.0/warehouses/wh1",
            exchange_base_url=f"http://127.0.0.1:{port}",
            token_cache=_token_cache(),
        )
        assert profile["meshant_dbt"]["outputs"]["prod"]["token"] == "m2m-bearer"
        recorded = RecordingHandler.requests
        assert len(recorded) == 1
        assert recorded[0]["path"] == "/oidc/v1/token"

    def test_m2m_cache_hit_skips_the_exchange(self):
        self._credential(
            auth_mode="OAUTH_M2M", config={"client_id": "cid-c", "client_secret": "csecret-c"}
        )
        cache = _token_cache()
        cache.set(str(self.workspace.id), "cid-c|csecret-c", "cached-bearer")
        server, _port = _oidc_server()
        self.addCleanup(server.shutdown)

        profile = self._resolve(
            http_path="/sql/1.0/warehouses/wh1",
            exchange_base_url=f"http://127.0.0.1:{_port}",
            token_cache=cache,
        )
        assert profile["meshant_dbt"]["outputs"]["prod"]["token"] == "cached-bearer"
        assert RecordingHandler.requests == [], "a cache hit makes ZERO exchange calls"

    def test_a_workspace_without_a_credential_fails_closed(self):
        from hub.apps.transformation.credential_resolver import CredentialResolverError

        with pytest.raises(CredentialResolverError, match=r"no PAT\|OAUTH_M2M"):
            self._resolve(http_path="/sql/1.0/warehouses/wh1")

    def test_an_empty_pat_token_fails_closed(self):
        self._credential(config={"token": ""})
        from hub.apps.transformation.credential_resolver import CredentialResolverError

        with pytest.raises(CredentialResolverError, match="no 'token'"):
            self._resolve(http_path="/sql/1.0/warehouses/wh1")

    def test_a_missing_http_path_fails_closed(self):
        # The blank-string case — an absent kwarg is the language's own
        # keyword-only enforcement; the guard refuses the blank value.
        self._credential()
        from hub.apps.transformation.credential_resolver import CredentialResolverError

        with pytest.raises(CredentialResolverError, match="http_path"):
            self._resolve(http_path="   ")

    def test_m2m_without_client_secret_fails_closed(self):
        self._credential(auth_mode="OAUTH_M2M", config={"client_id": "cid-x"})
        from hub.apps.transformation.credential_resolver import CredentialResolverError

        with pytest.raises(CredentialResolverError, match="client_secret"):
            self._resolve(http_path="/sql/1.0/warehouses/wh1")


class TestConnectionResolution(TestCase):
    """The connection path: the connection's own config is the identity."""

    def setUp(self):
        self.tenant = TenantFactory.create_tenant()

    def _connection(self, **overrides):
        from hub.apps.warehouses.models import WarehouseConnection

        config = {
            "auth_mode": "PAT",
            "pat_token": "dapi-conn-pat",
            "host": "dbc-conn.cloud.databricks.com",
            "http_path": "/sql/1.0/warehouses/conn1",
            "catalog": "conn_catalog",
            "schema": "conn_schema",
        }
        config.update(overrides.pop("config", {}))
        return WarehouseConnection.objects.create(
            tenant=self.tenant,
            name=f"conn-{uuid.uuid4().hex[:8]}",
            warehouse_type=overrides.pop("warehouse_type", "DATABRICKS"),
            config=config,
            is_active=True,
            **overrides,
        )

    def _resolve(self, connection, **kwargs):
        from hub.apps.transformation.credential_resolver import (
            resolve_databricks_connection_credentials,
        )

        return resolve_databricks_connection_credentials(connection, **kwargs)

    def test_a_pat_connection_resolves_the_profile(self):
        connection = self._connection()
        profile = self._resolve(connection)

        output = profile["meshant_dbt"]["outputs"]["prod"]
        assert output["type"] == "databricks"
        assert output["host"] == "dbc-conn.cloud.databricks.com"
        assert output["http_path"] == "/sql/1.0/warehouses/conn1"
        assert output["token"] == "dapi-conn-pat"
        assert output["catalog"] == "conn_catalog"
        assert output["schema"] == "conn_schema"

    def test_m2m_resolves_through_the_cache_then_the_exchange(self):
        connection = self._connection(
            config={
                "auth_mode": "OAUTH_M2M",
                "client_id": "cid-conn",
                "client_secret": "csecret-conn",
            }
        )
        cache = _token_cache()
        cache.set(
            str(getattr(connection, "databricks_workspace_id", None) or "")
            or "dbc-conn.cloud.databricks.com",
            "cid-conn|csecret-conn",
            "conn-cached-bearer",
        )
        server, _port = _oidc_server()
        self.addCleanup(server.shutdown)

        profile = self._resolve(
            connection, exchange_base_url=f"http://127.0.0.1:{_port}", token_cache=cache
        )
        assert profile["meshant_dbt"]["outputs"]["prod"]["token"] == "conn-cached-bearer"
        assert RecordingHandler.requests == [], "the cached bearer skips the exchange"

    def test_a_non_databricks_connection_fails_closed(self):
        connection = self._connection(warehouse_type="SNOWFLAKE")
        from hub.apps.transformation.credential_resolver import CredentialResolverError

        with pytest.raises(CredentialResolverError, match="DATABRICKS"):
            self._resolve(connection)

    def test_a_connection_without_host_fails_closed_naming_the_key(self):
        connection = self._connection(config={"host": ""})
        from hub.apps.transformation.credential_resolver import CredentialResolverError

        with pytest.raises(CredentialResolverError, match="host"):
            self._resolve(connection)

    def test_a_connection_without_http_path_fails_closed(self):
        connection = self._connection(config={"http_path": ""})
        from hub.apps.transformation.credential_resolver import CredentialResolverError

        with pytest.raises(CredentialResolverError, match="http_path"):
            self._resolve(connection)

    def test_caller_catalog_schema_override_the_config_keys(self):
        connection = self._connection()
        profile = self._resolve(connection, catalog="override_catalog", schema="override_schema")
        output = profile["meshant_dbt"]["outputs"]["prod"]
        assert output["catalog"] == "override_catalog"
        assert output["schema"] == "override_schema"

    def test_the_profile_name_kwarg_drives_the_dict_key(self):
        connection = self._connection()
        profile = self._resolve(connection, profile_name="meshant_tenant1_run2")
        assert "meshant_tenant1_run2" in profile
        assert "meshant_dbt" not in profile
