"""TDD pins for the connection-backed dlt credential resolver (openspec
wire-databricks-dlt-movement task 6.6) — PAT/M2M resolution from the
``WarehouseConnection``'s encrypted config (design D3).

No mocks: REAL Postgres ``WarehouseConnection`` rows through the REAL
KMS+Fernet encryption chain, REAL Redis (the shared test cache db 13 —
the runbook convention, the ``M2MTokenCache`` store), and the REAL M2M
oidc exchange (the warehouses connector's production
``resolve_access_token`` — retried/jittered/classified) against a REAL
threaded local HTTP server. The sanctioned seams are the injectable
token cache + the ``exchange_base_url`` transport seam (both REAL in
production; the injection pins the failure/caching contracts).
"""

from __future__ import annotations

import http.server
import json
import logging
import threading
import uuid

import pytest

from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.warehouses.exceptions import (
    WarehouseConnectionError,
    WarehouseUnsupportedTypeError,
)
from hub.apps.warehouses.models import WarehouseConnection, WarehouseType
from hub.data_movement.dlt_credentials import resolve_connection_credentials
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

_PAT_CONFIG = {
    "host": "adb-123.azuredatabricks.net",
    "http_path": "/sql/1.0/warehouses/wh-1",
    "pat_token": "dapi-own-token",
}

_M2M_CONFIG = {
    "host": "adb-123.azuredatabricks.net",
    "http_path": "/sql/1.0/warehouses/wh-1",
    "auth_mode": "OAUTH_M2M",
    "client_id": "svc-6-6-client",
    "client_secret": "dose6-6-secret",
}

_M2M_TOKEN = "dapi-m2m-token"


@pytest.fixture(autouse=True)
def redis_13(test_redis_endpoint):
    """The shared test cache on db 13 (the runbook convention; flushed
    per fixture — autouse so every test starts with a clean cache
    namespace).  The endpoint follows the environment: the compose
    stack's ``redis-cache-test`` in-container, the host-side
    ``p313-redis`` mapping on host runs — see ``test_redis_endpoint``."""
    import redis

    host, port = test_redis_endpoint
    client = redis.Redis(host=host, port=port, db=13, decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def local_http_server():
    """A REAL threaded HTTP server on an ephemeral port serving the oidc
    token endpoint (the RecordingHandler convention — request bodies and
    paths recorded for the wire pins)."""
    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []
    RecordingHandler.token_body = json.dumps(
        {"access_token": _M2M_TOKEN, "token_type": "Bearer", "expires_in": 3600}
    ).encode()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield port
    server.shutdown()
    server.server_close()


def _mk_connection(
    *,
    config,
    warehouse_type=WarehouseType.DATABRICKS,
    workspace_id=None,
    tenant=None,
):
    """A REAL WarehouseConnection row — the raw dict config is encrypted
    on save, so the resolver's get_config() exercises the real decrypt."""
    tenant = tenant or TenantFactory.create_tenant()
    return WarehouseConnection.objects.create(
        tenant=tenant,
        name=f"conn-{uuid.uuid4().hex[:8]}",
        warehouse_type=warehouse_type,
        config=config,
        databricks_workspace_id=workspace_id,
    )


def _m2m_cache(redis_13):
    from hub.apps.databricks_admin.token_cache import M2MTokenCache

    return M2MTokenCache(redis_client=redis_13)


def _token_requests():
    return [r for r in RecordingHandler.requests if r["path"] == "/oidc/v1/token"]


# ── PAT leg ───────────────────────────────────────────────────────────


def test_pat_resolves_from_the_encrypted_config():
    connection = _mk_connection(config=_PAT_CONFIG)

    # Never-plaintext AT REST: the persisted JSONField is the REAL
    # encryption chain's ciphertext (a bare base64 string — the actual
    # encrypt_json_field contract) — none of the raw config values may
    # appear in it, and the resolver reads them back through the real
    # decrypt round-trip.
    stored = connection.config
    assert isinstance(stored, str), "the stored config must be ciphertext, never a plain dict"
    for secret_value in (_PAT_CONFIG["pat_token"], _PAT_CONFIG["host"]):
        assert secret_value not in stored
    assert connection.get_config() == _PAT_CONFIG

    creds = resolve_connection_credentials(connection)
    assert creds == {"access_token": _PAT_CONFIG["pat_token"]}


def test_pat_without_a_token_fails_closed():
    connection = _mk_connection(
        config={**_PAT_CONFIG, "pat_token": ""},
    )

    with pytest.raises(WarehouseConnectionError) as excinfo:
        resolve_connection_credentials(connection)

    assert "no 'pat_token' value" in str(excinfo.value)


def test_a_non_databricks_connection_is_refused():
    connection = _mk_connection(
        config={"account": "ab12345", "database": "DB", "schema": "PUBLIC"},
        warehouse_type=WarehouseType.SNOWFLAKE,
    )

    with pytest.raises(WarehouseUnsupportedTypeError):
        resolve_connection_credentials(connection)


# ── M2M leg ───────────────────────────────────────────────────────────


def test_m2m_exchanges_once_then_serves_the_cache(local_http_server, redis_13):
    connection = _mk_connection(config=_M2M_CONFIG)
    cache = _m2m_cache(redis_13)

    first = resolve_connection_credentials(
        connection,
        exchange_base_url=f"http://127.0.0.1:{local_http_server}",
        token_cache=cache,
    )
    second = resolve_connection_credentials(
        connection,
        exchange_base_url=f"http://127.0.0.1:{local_http_server}",
        token_cache=cache,
    )

    assert first == {"access_token": _M2M_TOKEN}
    assert second == first

    # The cached layer owns the token lifecycle: exactly ONE real
    # client-credentials exchange across both resolutions.
    exchanges = _token_requests()
    assert len(exchanges) == 1
    body = exchanges[0]["body"]
    assert "grant_type=client_credentials" in body
    assert "scope=all-apis" in body
    assert f"client_id={_M2M_CONFIG['client_id']}" in body
    assert f"client_secret={_M2M_CONFIG['client_secret']}" in body

    # The bearer sits in the REAL cache under the connection's host
    # channel (the workspace-scoped key convention when no workspace row
    # is linked — matching the client's host channel).
    key = cache.key_for(_M2M_CONFIG["host"], "svc-6-6-client|dose6-6-secret")
    assert redis_13.get(key) == _M2M_TOKEN


def test_m2m_prefers_the_linked_workspace_channel(local_http_server, redis_13):
    from hub.apps.databricks_admin.models import DatabricksWorkspace

    tenant = TenantFactory.create_tenant()
    # bulk_create skips save() — the workspace host is a fixture value,
    # never dialed; the save-time SSRF/DNS guard is irrelevant to the
    # resolver's FK-id read.
    workspace = DatabricksWorkspace.objects.bulk_create(
        [
            DatabricksWorkspace(
                tenant=tenant,
                name=f"ws-{uuid.uuid4().hex[:8]}",
                host="dbc-fixture.cloud.databricks.com",
                cloud="AWS",
                region="us-west-2",
            )
        ]
    )[0]
    connection = _mk_connection(config=_M2M_CONFIG, workspace_id=workspace.id, tenant=tenant)
    cache = _m2m_cache(redis_13)

    resolve_connection_credentials(
        connection,
        exchange_base_url=f"http://127.0.0.1:{local_http_server}",
        token_cache=cache,
    )

    # The cache entry lives under the WORKSPACE channel (the client's
    # workspace-scoped key) — and never under the bare host.
    credential_ref = "svc-6-6-client|dose6-6-secret"
    assert redis_13.get(cache.key_for(str(workspace.id), credential_ref)) == _M2M_TOKEN
    assert redis_13.get(cache.key_for(_M2M_CONFIG["host"], credential_ref)) is None


def test_m2m_missing_client_credentials_fail_before_any_exchange(local_http_server, redis_13):
    connection = _mk_connection(config={**_M2M_CONFIG, "client_id": ""})
    cache = _m2m_cache(redis_13)

    with pytest.raises(WarehouseConnectionError) as excinfo:
        resolve_connection_credentials(
            connection,
            exchange_base_url=f"http://127.0.0.1:{local_http_server}",
            token_cache=cache,
        )

    assert "client_id" in str(excinfo.value)
    assert RecordingHandler.requests == [], "no exchange may fire for a broken credential"
    assert redis_13.keys() == [], "a failed resolution must never poison the cache"


def test_m2m_exchange_failure_propagates_and_never_caches(local_http_server, redis_13):
    connection = _mk_connection(config=_M2M_CONFIG)
    cache = _m2m_cache(redis_13)
    # The connector's retry discipline: 429/5xx are retryable, three
    # attempts total — a persistently failing endpoint exhausts them and
    # fails closed with the classified error.
    RecordingHandler.script = [500, 500, 500]

    with pytest.raises(WarehouseConnectionError) as excinfo:
        resolve_connection_credentials(
            connection,
            exchange_base_url=f"http://127.0.0.1:{local_http_server}",
            token_cache=cache,
        )

    assert "token exchange failed with 500" in str(excinfo.value)
    assert len(_token_requests()) == 3
    assert redis_13.keys() == [], "a failed exchange must never cache a token"


def test_a_cache_outage_never_blocks_resolution(local_http_server):
    connection = _mk_connection(config=_M2M_CONFIG)

    class _DownCache:
        """The injectable-seam failure double: a cache whose store is
        unreachable — the resolver must proceed through the real exchange
        (best-effort cache reads/writes, the Phase 273 discipline)."""

        def get(self, *_args, **_kwargs):
            raise ConnectionError("redis unreachable")

        def set(self, *_args, **_kwargs):
            raise ConnectionError("redis unreachable")

    creds = resolve_connection_credentials(
        connection,
        exchange_base_url=f"http://127.0.0.1:{local_http_server}",
        token_cache=_DownCache(),
    )

    assert creds == {"access_token": _M2M_TOKEN}
    assert len(_token_requests()) == 1


def test_an_unknown_auth_mode_is_refused():
    connection = _mk_connection(config={**_M2M_CONFIG, "auth_mode": "NONSENSE"})

    with pytest.raises(WarehouseConnectionError) as excinfo:
        resolve_connection_credentials(connection)

    assert "Unsupported Databricks auth_mode 'NONSENSE'" in str(excinfo.value)


# ── Never-plaintext discipline ────────────────────────────────────────


class _CaptureHandler(logging.Handler):
    """Real logging instrumentation — collects emitted record messages
    from the resolvers' loggers (never replaces a production path)."""

    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def test_resolution_never_logs_the_token(local_http_server, redis_13):
    import hub.apps.warehouses.connectors.databricks as connector_module
    import hub.data_movement.dlt_credentials as credentials_module

    pat_connection = _mk_connection(config=_PAT_CONFIG)
    m2m_connection = _mk_connection(config=_M2M_CONFIG)
    cache = _m2m_cache(redis_13)

    capture = _CaptureHandler()
    loggers = [
        logging.getLogger(credentials_module.__name__),
        logging.getLogger(connector_module.__name__),
    ]
    for lg in loggers:
        lg.addHandler(capture)

    try:
        resolve_connection_credentials(pat_connection)
        resolve_connection_credentials(
            m2m_connection,
            exchange_base_url=f"http://127.0.0.1:{local_http_server}",
            token_cache=cache,
        )
    finally:
        for lg in loggers:
            lg.removeHandler(capture)

    joined = "\n".join(capture.messages)
    assert _PAT_CONFIG["pat_token"] not in joined
    assert _M2M_TOKEN not in joined
    assert _M2M_CONFIG["client_secret"] not in joined
