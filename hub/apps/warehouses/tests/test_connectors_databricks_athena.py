"""
Phase 275.C.4 — Databricks + Athena integration tests.

REQUIRES real warehouse sandbox accounts (Databricks + Athena).
Skipped by default in CI without per-connector credentials.

Contract tests (no live warehouse needed):
- Databricks: interface conformance (warehouse_type, method signatures)
- Athena: interface conformance, async polling constants, method signatures
"""

from __future__ import annotations

import contextlib
import os
import uuid
from typing import TYPE_CHECKING

import pytest
from django.test import TestCase

from envpolicy import api_available, skip_or_fail
from hub.apps.tenants.models import Tenant

if TYPE_CHECKING:
    from collections.abc import Mapping
from hub.apps.warehouses.connectors.athena import (
    ATHENA_MAX_POLL_S,
    ATHENA_POLL_INTERVAL_S,
    ATHENA_TERMINAL_STATES,
    AthenaConnector,
)
from hub.apps.warehouses.connectors.databricks import DatabricksConnector
from hub.apps.warehouses.exceptions import WarehouseConnectionError

pytestmark = pytest.mark.django_db(transaction=True)

_DATABRICKS_HOST_SET = bool(os.environ.get("DATABRICKS_HOST"))
_DATABRICKS_SANDBOX_HOST_SET = bool(os.environ.get("DATABRICKS_SANDBOX_HOST"))
_DATABRICKS_HAS_HOST = _DATABRICKS_HOST_SET or _DATABRICKS_SANDBOX_HOST_SET
_DATABRICKS_HAS_TOKEN = bool(
    os.environ.get("DATABRICKS_SANDBOX_TOKEN") or os.environ.get("DATABRICKS_TOKEN")
)
# HTTP path may be provided explicitly, or resolved from the sandbox
# warehouse id / legacy cluster id (see _resolve_http_path — the
# warehouse id wins; the cluster id is the stale-400 last resort).
_DATABRICKS_HAS_HTTP_PATH = bool(
    os.environ.get("DATABRICKS_SANDBOX_HTTP_PATH")
    or os.environ.get("DATABRICKS_HTTP_PATH")
    or os.environ.get("DATABRICKS_SANDBOX_WAREHOUSE_ID")
    or os.environ.get("DATABRICKS_CLUSTER_ID")
)
_DATABRICKS_HAS_CREDS = _DATABRICKS_HAS_HOST and _DATABRICKS_HAS_HTTP_PATH and _DATABRICKS_HAS_TOKEN


def _require_databricks_creds() -> None:
    """W1 (W0.10): the env-gating site applies the W16 policy — plain
    skip markers silently skip in CI, so a mis-configured runner reports
    green while the live suites never ran. ``skip_or_fail`` raises in CI
    and skips gracefully locally."""
    if not _DATABRICKS_HAS_CREDS:
        skip_or_fail("DATABRICKS_HOST + DATABRICKS_HTTP_PATH + DATABRICKS_TOKEN all required")


_ATHENA_HAS_ACCESS_KEY = bool(os.environ.get("ATHENA_AWS_ACCESS_KEY_ID"))
_ATHENA_HAS_SECRET_KEY = bool(os.environ.get("ATHENA_AWS_SECRET_ACCESS_KEY"))
_ATHENA_SANDBOX_ENABLED = bool(os.environ.get("ATHENA_SANDBOX_ENABLED"))
_ATHENA_HAS_CREDS = _ATHENA_SANDBOX_ENABLED and _ATHENA_HAS_ACCESS_KEY and _ATHENA_HAS_SECRET_KEY


def _require_athena_sandbox() -> None:
    """W1 (W0.10): same policy as ``_require_databricks_creds``."""
    if not _ATHENA_HAS_CREDS:
        skip_or_fail(
            "ATHENA_SANDBOX_ENABLED + ATHENA_AWS_ACCESS_KEY_ID + "
            "ATHENA_AWS_SECRET_ACCESS_KEY all required"
        )

# botocore error codes treated as environment failures (W16): the sandbox
# rejects us (bad/expired creds, missing IAM permissions) or the service is
# down. skip_or_fail decides: raise in CI, graceful skip locally.
_ATHENA_ENV_FAILURE_CODES = frozenset(
    {
        # not authenticated / not authorized
        "AccessDeniedException",
        "AccessDenied",
        "UnauthorizedException",
        "UnrecognizedClientException",
        "InvalidClientTokenId",
        "SignatureDoesNotMatch",
        "InvalidSignatureException",
        "ExpiredToken",
        "ExpiredTokenException",
        # service unavailable
        "ServiceUnavailableException",
        "InternalServerException",
    }
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
            f"Expected warehouse_type={expected_warehouse_type}, got {connector.warehouse_type}"
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



def _connect_bounded(connector, timeout_s: float = 45.0):
    """Bounded connector.connect().

    The workspace probe may succeed (401 from a reachable host) while
    the SQL handshake still hangs for minutes — a stopped or
    auto-starting sandbox warehouse holds the request open and no
    client-side socket timeout fires. Run connect in a worker thread
    and convert a cap breach into the W16 skip.
    """
    import threading

    # A daemon thread + join(timeout): ThreadPoolExecutor's context
    # manager JOINS hung worker threads on exit (defeating the bound),
    # while a daemon thread never blocks process exit.
    errors: list[BaseException] = []

    def _connect():
        try:
            connector.connect()
        except BaseException as exc:  # noqa: BLE001 — re-raised below
            errors.append(exc)

    worker = threading.Thread(target=_connect, daemon=True)
    worker.start()
    worker.join(timeout=timeout_s)
    if worker.is_alive():
        with contextlib.suppress(Exception):
            connector.close()
        skip_or_fail(
            f"Databricks connect did not complete within {timeout_s:g}s "
            "(sandbox warehouse may be stopped or auto-starting)"
        )
    if errors:
        exc = errors[0]
        if isinstance(exc, (ConnectionError, OSError, TimeoutError, ValueError, WarehouseConnectionError)):
            # A raised failure IS a real connector error (auth, config).
            skip_or_fail(f"Databricks infrastructure unavailable: {exc}")
        raise exc

# ── pilot-readiness 2.1: the live-surface fixes (RED-first pins) ──────
#
# Live reproduction against the sandbox (2026-10-05) classified two code
# bugs: (1) _sandbox_config ignored DATABRICKS_SANDBOX_WAREHOUSE_ID and
# derived the SQL http_path from the STALE DATABRICKS_CLUSTER_ID (400
# INVALID_PARAMETER_VALUE — the cluster is deleted), and (2) the live
# test connected to a STOPPED serverless warehouse without starting it,
# so the 45s bound breached on every cold sandbox (serverless start
# takes 1-3 min). These pins hold both fixes — no mocks: the start
# helper runs against a real scripted HTTP server over real httpx.


def _resolve_http_path(env: Mapping[str, str]) -> str:
    """The SQL http_path resolution order (bug 1 fix).

    Priority: explicit http path > the SANDBOX warehouse id (the
    warehouse the sandbox actually provisions) > the legacy cluster id.
    The legacy cluster id was the historical fallback, but sandbox
    clusters are ephemeral — a stale id yields a 400 and the connect
    hangs, so it is the LAST resort only.
    """
    explicit = env.get("DATABRICKS_SANDBOX_HTTP_PATH") or env.get("DATABRICKS_HTTP_PATH", "")
    if explicit:
        return explicit
    warehouse_id = env.get("DATABRICKS_SANDBOX_WAREHOUSE_ID", "")
    if warehouse_id:
        return f"/sql/1.0/warehouses/{warehouse_id}"
    cluster_id = env.get("DATABRICKS_CLUSTER_ID", "")
    if cluster_id:
        return f"/sql/1.0/warehouses/{cluster_id}"
    return ""


def _ensure_warehouse_running(
    base_url: str,
    warehouse_id: str,
    poll_s: float = 5.0,
    timeout_s: float = 240.0,
) -> tuple[bool, str]:
    """Start a STOPPED warehouse and wait for RUNNING (bug 2 fix).

    The sandbox warehouse auto-stops after 10 idle minutes; connecting
    to a STOPPED serverless warehouse hangs inside the SQL handshake
    long enough to breach the bounded connect, so the live tests must
    start it first. GET the state, POST start when STOPPED, then poll
    until RUNNING or the bound. A DENIED start (>=400, e.g. the
    sandbox's DENY_NEW_AND_EXISTING_RESOURCES quota block) fails FAST
    with the API's error_code instead of polling a warehouse that can
    never start. Returns (ok, detail). Real HTTP via httpx — no mocks.
    """
    import time

    import httpx

    states = f"{base_url}/api/2.0/sql/warehouses/{warehouse_id}"
    start = f"{states}/start"
    deadline = time.monotonic() + timeout_s
    with httpx.Client(timeout=10.0) as client:
        r = client.get(states)
        state = (r.json().get("state", "") if r.status_code == 200 else "").upper()
        if state == "RUNNING":
            return True, ""
        start_resp = client.post(start)
        if start_resp.status_code >= 400:
            error_code = ""
            with contextlib.suppress(ValueError):
                error_code = start_resp.json().get("error_code", "")
            if error_code:
                return False, error_code
            if start_resp.status_code in (401, 403):
                return False, (
                    f"start denied: HTTP {start_resp.status_code} "
                    "(PAT may lack warehouse start permission or be expired)"
                )
            return False, f"start denied (HTTP {start_resp.status_code})"
        while time.monotonic() < deadline:
            time.sleep(poll_s)  # noqa: sleep-needed  # INTENTIONAL: poll interval inside the deadline-bounded warehouse-start status loop
            r = client.get(states)
            state = (r.json().get("state", "") if r.status_code == 200 else "").upper()
            if state == "RUNNING":
                return True, ""
    return False, "did not reach RUNNING within the start bound"


class _WarehouseServer:
    """A real HTTP server scripted through the warehouse lifecycle."""

    def __init__(self, state: str = "STOPPED", start_status: int = 200, start_body: str = "{}"):
        import http.server
        import threading

        self.state = state
        self.start_status = start_status
        self.start_body = start_body
        self.start_calls: list[str] = []

        class _H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):  # keep pytest output clean
                pass

            def do_GET(self):
                import json

                body = json.dumps({"state": self.server.api_state()}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                self.server.api_start(self.path)
                body = self.server.api_start_body().encode()
                self.send_response(self.server.api_start_status())
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
        server.api_state = lambda: self.state  # type: ignore[attr-defined]
        server.api_start = self.start_calls.append  # type: ignore[attr-defined]
        server.api_start_status = lambda: self.start_status  # type: ignore[attr-defined]
        server.api_start_body = lambda: self.start_body  # type: ignore[attr-defined]
        self.server = server
        threading.Thread(target=server.serve_forever, daemon=True).start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()


def _start_advisory(started: bool, detail: str) -> str:
    """The explicit-start outcome is ADVISORY, not a verdict.

    Live (2026-10-05, free-edition account): the start endpoint 401s
    while a direct SQL connect still works — serverless warehouses
    auto-resume on connect (test_schema_reflection passed with the
    warehouse STOPPED). A denied start must therefore not skip the
    test; the bounded connect is the verdict.
    """
    if started:
        return ""
    return (
        f"explicit warehouse start denied/not RUNNING ({detail}) — "
        "attempting the bounded connect (serverless auto-resume may "
        "still serve SQL)"
    )


class TestSessionConfigTags:
    """pilot-readiness 2.3: the free-edition workspace rejects the
    queryTag session keys with CONFIG_NOT_AVAILABLE (live finding) —
    ``session_tags_enabled: false`` is the explicit opt-out."""

    @staticmethod
    def _session_config(config, *, tenant_id="", asset_id=""):
        return DatabricksConnector(
            connection_config=config, tenant_id=tenant_id, asset_id=asset_id
        )._session_config()

    def test_tags_are_set_by_default(self):
        cfg = self._session_config({"host": "h"}, tenant_id="t-1", asset_id="a-1")
        assert cfg == {
            "spark.databricks.queryTag.tenant_id": "t-1",
            "spark.databricks.queryTag.asset_id": "a-1",
        }

    def test_explicit_disable_skips_all_tags(self):
        cfg = self._session_config(
            {"host": "h", "session_tags_enabled": False}, tenant_id="t-1", asset_id="a-1"
        )
        assert cfg == {}

    def test_disable_is_strictly_the_false_value(self):
        # A truthy/absent flag must NOT disable tags — the escape is
        # opt-out, never accidental.
        cfg = self._session_config(
            {"host": "h", "session_tags_enabled": True}, tenant_id="t-1"
        )
        assert "spark.databricks.queryTag.tenant_id" in cfg


class TestStartAdvisory:
    def test_started_warehouse_has_no_advisory(self):
        assert _start_advisory(True, "") == ""

    def test_denied_start_is_an_advisory_that_names_the_reason(self):
        note = _start_advisory(False, "HTTP 401")
        assert "HTTP 401" in note
        assert "bounded connect" in note


class TestHttpPathResolution:
    """Bug 1: the sandbox warehouse id must win over the stale cluster id."""

    def test_sandbox_warehouse_id_beats_cluster_id(self):
        path = _resolve_http_path(
            {"DATABRICKS_SANDBOX_WAREHOUSE_ID": "wh-123", "DATABRICKS_CLUSTER_ID": "stale-cl"}
        )
        assert path == "/sql/1.0/warehouses/wh-123"

    def test_explicit_http_path_wins(self):
        path = _resolve_http_path(
            {
                "DATABRICKS_SANDBOX_HTTP_PATH": "/sql/1.0/warehouses/explicit",
                "DATABRICKS_SANDBOX_WAREHOUSE_ID": "wh-123",
            }
        )
        assert path == "/sql/1.0/warehouses/explicit"

    def test_cluster_id_is_the_last_resort(self):
        path = _resolve_http_path({"DATABRICKS_CLUSTER_ID": "cl-9"})
        assert path == "/sql/1.0/warehouses/cl-9"

    def test_empty_when_nothing_is_set(self):
        assert _resolve_http_path({}) == ""


class TestWarehouseStartHelper:
    """Bug 2: a STOPPED serverless warehouse must be started BEFORE connect."""

    def test_running_warehouse_is_not_started_again(self):
        srv = _WarehouseServer(state="RUNNING")
        try:
            ok, _ = _ensure_warehouse_running(srv.base, "wh-1", poll_s=0.05, timeout_s=2)
            assert ok is True
            assert srv.start_calls == []
        finally:
            srv.close()

    def test_stopped_warehouse_is_started_and_awaited(self):
        srv = _WarehouseServer(state="STOPPED")
        try:
            import threading

            def flip_to_running():
                import time

                time.sleep(0.4)  # noqa: sleep-needed  # INTENTIONAL: fake-server state flip delay (RUNNING transition timing under test)
                srv.state = "RUNNING"

            threading.Thread(target=flip_to_running, daemon=True).start()
            ok, _ = _ensure_warehouse_running(srv.base, "wh-1", poll_s=0.05, timeout_s=5)
            assert ok is True
            assert srv.start_calls == ["/api/2.0/sql/warehouses/wh-1/start"]
        finally:
            srv.close()

    def test_never_running_reports_false_at_the_bound(self):
        srv = _WarehouseServer(state="STOPPED")
        try:
            ok, _ = _ensure_warehouse_running(srv.base, "wh-1", poll_s=0.05, timeout_s=0.3)
            assert ok is False
            assert len(srv.start_calls) == 1
        finally:
            srv.close()

    def test_denied_start_fails_fast_with_the_reason(self):
        # The real sandbox returned 400 DENY_NEW_AND_EXISTING_RESOURCES —
        # a denied start must fail FAST (no 240s polling) and surface the
        # API's error_code in the detail.
        srv = _WarehouseServer(
            state="STOPPED",
            start_status=400,
            start_body='{"error_code": "DENY_NEW_AND_EXISTING_RESOURCES"}',
        )
        try:
            import time

            t0 = time.monotonic()
            ok, detail = _ensure_warehouse_running(srv.base, "wh-1", poll_s=0.05, timeout_s=5)
            assert ok is False
            assert time.monotonic() - t0 < 2, "denied start must not poll to the bound"
            assert "DENY_NEW_AND_EXISTING_RESOURCES" in detail
            assert len(srv.start_calls) == 1
        finally:
            srv.close()

    def test_unauthorized_start_explains_the_permission_hint(self):
        srv = _WarehouseServer(state="STOPPED", start_status=401, start_body="unauthorized")
        try:
            ok, detail = _ensure_warehouse_running(srv.base, "wh-1", poll_s=0.05, timeout_s=2)
            assert ok is False
            assert "401" in detail
            assert "permission" in detail
        finally:
            srv.close()


class TestDatabricksLiveIntegration(TestCase):
    """Databricks live integration — gated at class setup by
    ``_require_databricks_creds`` (W16: raise in CI, skip locally).
    Contract assertions always run within the live methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _require_databricks_creds()

    @staticmethod
    def _sandbox_config():
        host = os.environ.get("DATABRICKS_SANDBOX_HOST") or os.environ.get("DATABRICKS_HOST", "")
        host = host.removeprefix("https://").removeprefix("http://").rstrip("/")
        # pilot-readiness 2.1: resolution order = explicit path > sandbox
        # warehouse id > legacy cluster id (the stale-cluster 400 trap).
        http_path = _resolve_http_path(os.environ)
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
        # Bounded pre-flight: a black-holed sandbox host hangs inside
        # sql.connect (the handshake path can outlive the socket
        # timeout), so probe reachability FIRST — a fast W16 skip
        # instead of a 300s pytest-timeout kill.

        if not api_available(f"https://{config['host']}/api/2.0/clusters/list", timeout=5.0):
            skip_or_fail("Databricks infrastructure unavailable (pre-flight probe failed)")
        # pilot-readiness 2.1: a STOPPED serverless sandbox warehouse
        # hangs the SQL handshake past the bounded connect — start it
        # first (real start call + state polling, bounded). pilot-
        # readiness 2.3: a DENIED start is advisory only — the account
        # can 401 the explicit start endpoint while a direct SQL connect
        # still works (serverless auto-resume, proven live), so the
        # bounded connect is the verdict, never the start call.
        if "/sql/1.0/warehouses/" in config["http_path"]:
            warehouse_id = config["http_path"].rsplit("/", 1)[-1]
            started, detail = _ensure_warehouse_running(f"https://{config['host']}", warehouse_id)
            note = _start_advisory(started, detail)
            if note:
                print(note)
        _connect_bounded(connector)
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
        # Bounded pre-flight: a black-holed sandbox host hangs inside
        # sql.connect (the handshake path can outlive the socket
        # timeout), so probe reachability FIRST — a fast W16 skip
        # instead of a 300s pytest-timeout kill.

        if not api_available(f"https://{config['host']}/api/2.0/clusters/list", timeout=5.0):
            skip_or_fail("Databricks infrastructure unavailable (pre-flight probe failed)")
        _connect_bounded(connector)
        try:
            schema = connector.reflect_schema("samples.nyctaxi.trips")
            assert len(schema) > 0
        finally:
            connector.close()


class TestAthenaLiveIntegration(TestCase):
    """Athena live integration — gated at class setup by
    ``_require_athena_sandbox`` (W16: raise in CI, skip locally)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _require_athena_sandbox()

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
        from botocore.exceptions import ClientError  # lazy — boto3 optional for contract tests

        config = self._sandbox_config()
        connector = AthenaConnector(connection_config=config)
        assert connector.warehouse_type == "athena"
        assert hasattr(connector, "connect")
        assert hasattr(connector, "execute_query")
        assert hasattr(connector, "close")
        try:
            connector.connect()
        except (ConnectionError, OSError, TimeoutError) as exc:
            skip_or_fail(f"Athena infrastructure unavailable: {exc}")
        try:
            result = connector.execute_query("SELECT 1 AS one")
            assert result.row_count == 1
        except ClientError as exc:
            # boto3 clients are lazy — connect() never touches AWS, so the
            # first real call (start_query_execution) surfaces authn/authz
            # and availability failures here.
            code = exc.response.get("Error", {}).get("Code", "")
            if code in _ATHENA_ENV_FAILURE_CODES:
                skip_or_fail(
                    f"Athena sandbox rejected the query ({code}) — "
                    "check IAM permissions for the sandbox key"
                )
            raise
        finally:
            connector.close()
