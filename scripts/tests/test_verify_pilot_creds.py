"""
Contract tests for scripts/verify_pilot_creds.py (pilot-readiness 2.2).

The pilot verifier is the acquisition oracle for the CUSTOMER account —
every surface (Databricks workspace auth PAT/M2M, the SQL warehouse,
AWS keys, the dlt destination, and the budget caps) is probed LIVE, and
the budget probe is the first-query guardrail ("budget caps set on the
workspace/warehouses BEFORE the first query").

These tests pin the contract without mocks or stubs:

- real stdlib HTTP servers script the Databricks workspace and account
  API surfaces; the script's real httpx client runs against them over
  real TCP;
- real boto3 clients run against scripted STS/S3 servers via
  ``endpoint_url`` — the AWS wire protocol is exercised, not replaced;
- no probe ever prints a secret — the servers record the Authorization
  headers and token-exchange form fields they receive, so the no-leak
  assertions are not vacuous;
- the warehouse probe NEVER starts compute (no POST .../start on the
  wire) — the budget-cap guardrail forbids any query before the caps
  are verified.

The live surfaces (real AWS/Databricks) are env-gated per W16: local
runs without pilot credentials skip; CI raises (the nightly pilot
workflow runs this file with CI=true and the secrets present).
"""

import base64
import http.server
import importlib.util
import json
import os
import sys
import threading
import urllib.parse
from pathlib import Path

import pytest

httpx = pytest.importorskip("httpx")
boto3 = pytest.importorskip("boto3")

scripts_dir = Path(__file__).parent.parent
repo_root = scripts_dir.parent
sys.path.insert(0, str(scripts_dir))
sys.path.insert(0, str(repo_root))

script_path = scripts_dir / "verify_pilot_creds.py"
spec = importlib.util.spec_from_file_location("verify_pilot_creds", script_path)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

TOKEN = "pilotprobe-token-abc123"
CLIENT_SECRET = "pilotprobe-client-secret-xyz789"
AWS_SECRET_KEY = "pilotprobe-aws-secret-key-42"
ACCOUNT_PASSWORD = "pilotprobe-account-password-007"


class _ScriptedServer:
    """A real stdlib HTTP server that records every request it serves."""

    def __init__(self, handler):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.requests: list[dict] = []
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()


class _WorkspaceHandler(http.server.BaseHTTPRequestHandler):
    """Scripts the Databricks WORKSPACE API surface: clusters/list,
    sql/warehouses/{id} (state only — no start), and the OIDC M2M
    token endpoint. Every request is recorded server-side."""

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _record(self, body=b""):
        self.server.server_holder.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": urllib.parse.parse_qs(body.decode() or ""),
            }
        )

    def _authorized(self):
        expected = self.server.server_holder.expected_bearer
        if expected is None:
            return True
        return self.headers.get("Authorization") == f"Bearer {expected}"

    def do_GET(self):
        self._record()
        path = urllib.parse.urlsplit(self.path).path
        holder = self.server.server_holder
        if not self._authorized():
            return self._json({"error_code": "UNAUTHENTICATED"}, 401)
        if path in ("/api/2.0/budgets/limits", "/api/2.0/budgets", "/api/2.1/budgets"):
            payload, status = (
                ({}, 200) if holder.budget_surfaces else ({"error_code": "NOT_FOUND"}, 404)
            )
        elif path == "/api/2.0/clusters/list":
            payload, status = {}, 200
        elif path.startswith("/api/2.0/sql/warehouses/"):
            warehouse_id = path.rsplit("/", 1)[-1]
            if warehouse_id == holder.warehouse_id:
                payload, status = {"id": warehouse_id, "state": holder.warehouse_state}, 200
            else:
                payload, status = {"error_code": "RESOURCE_DOES_NOT_EXIST"}, 404
        else:
            payload, status = {"error_code": "NOT_FOUND"}, 404
        return self._json(payload, status)

    def do_POST(self):
        body = self._read_body()
        self._record(body)
        path = urllib.parse.urlsplit(self.path).path
        holder = self.server.server_holder
        if path == "/oidc/v1/token":
            form = urllib.parse.parse_qs(body.decode() or "")
            if (
                form.get("grant_type") == ["client_credentials"]
                and form.get("scope") == ["all-apis"]
                and form.get("client_id") == [holder.m2m_client_id]
                and form.get("client_secret") == [holder.m2m_client_secret]
            ):
                return self._json({"access_token": holder.m2m_access_token})
            return self._json(
                {"error": "invalid_client", "error_description": "bad credentials"}, 400
            )
        # Anything else (notably .../start) is served 501 — a probe that
        # starts compute is a contract violation and the tests assert the
        # recorded paths never contain it.
        return self._json({"error_code": "NOT_IMPLEMENTED"}, 501)

    def log_message(self, *args):  # silence request logging
        pass


class _Workspace:
    def __init__(
        self,
        *,
        bearer=None,
        warehouse_id="wh-pilot-1",
        warehouse_state="RUNNING",
        m2m_client_id=None,
        m2m_client_secret=None,
        m2m_access_token="m2m-access-token-123",
        budget_surfaces=False,
    ):
        self.requests: list[dict] = []
        self.expected_bearer = bearer
        self.warehouse_id = warehouse_id
        self.warehouse_state = warehouse_state
        self.m2m_client_id = m2m_client_id
        self.m2m_client_secret = m2m_client_secret
        self.m2m_access_token = m2m_access_token
        self.budget_surfaces = budget_surfaces
        self.server = _ScriptedServer(_WorkspaceHandler)
        self.server.server.server_holder = self  # handler → holder hop

    @property
    def base(self):
        return self.server.base

    def close(self):
        self.server.close()


@pytest.fixture
def workspace():
    ws = _Workspace()
    yield ws
    ws.close()


class _AccountHandler(http.server.BaseHTTPRequestHandler):
    """Scripts the Databricks ACCOUNT API surface: the budget-policies
    endpoints (2.1 first, 2.0 fallback) and the account OIDC M2M
    token endpoint. Records Authorization headers and bodies."""

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _record(self, body=b""):
        self.server.server_holder.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": urllib.parse.parse_qs(body.decode() or ""),
            }
        )

    def _authorized(self):
        holder = self.server.server_holder
        if holder.expected_bearer is not None:
            return self.headers.get("Authorization") == f"Bearer {holder.expected_bearer}"
        if holder.expected_basic is not None:
            return self.headers.get("Authorization") == f"Basic {holder.expected_basic}"
        return True

    def do_GET(self):
        self._record()
        path = urllib.parse.urlsplit(self.path).path
        holder = self.server.server_holder
        if not self._authorized():
            return self._json({"error_code": "UNAUTHENTICATED"}, 401)
        expected_21 = f"/api/2.1/accounts/{holder.account_id}/budget-policies"
        expected_20 = f"/api/2.0/accounts/{holder.account_id}/budget-policies"
        if path == expected_21:
            status, payload = holder.policies_21
            return self._json(payload, status)
        if path == expected_20:
            status, payload = holder.policies_20
            return self._json(payload, status)
        return self._json({"error_code": "NOT_FOUND"}, 404)

    def do_POST(self):
        body = self._read_body()
        self._record(body)
        path = urllib.parse.urlsplit(self.path).path
        holder = self.server.server_holder
        if path == "/oidc/v1/token":
            form = urllib.parse.parse_qs(body.decode() or "")
            if (
                form.get("grant_type") == ["client_credentials"]
                and form.get("scope") == ["all-apis"]
                and form.get("client_id") == [holder.m2m_client_id]
                and form.get("client_secret") == [holder.m2m_client_secret]
            ):
                return self._json({"access_token": holder.m2m_access_token})
            return self._json({"error": "invalid_client"}, 400)
        return self._json({"error_code": "NOT_IMPLEMENTED"}, 501)

    def log_message(self, *args):  # silence request logging
        pass


class _Account:
    def __init__(
        self,
        *,
        account_id="acct-pilot-1",
        policies_21=(200, {"policies": []}),
        policies_20=(404, {}),
        expected_bearer=None,
        expected_basic=None,
        m2m_client_id=None,
        m2m_client_secret=None,
        m2m_access_token="acct-m2m-token-456",
    ):
        self.requests: list[dict] = []
        self.account_id = account_id
        self.policies_21 = policies_21
        self.policies_20 = policies_20
        self.expected_bearer = expected_bearer
        self.expected_basic = expected_basic
        self.m2m_client_id = m2m_client_id
        self.m2m_client_secret = m2m_client_secret
        self.m2m_access_token = m2m_access_token
        self.server = _ScriptedServer(_AccountHandler)
        self.server.server.server_holder = self

    @property
    def base(self):
        return self.server.base

    def close(self):
        self.server.close()


@pytest.fixture
def account():
    acct = _Account()
    yield acct
    acct.close()


class _StsHandler(http.server.BaseHTTPRequestHandler):
    """Scripts the AWS STS Query API: GetCallerIdentity succeeds or
    fails with InvalidClientTokenId per the server state."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(length).decode() or "")
        self.server.server_holder.actions.append(form.get("Action", [""])[0])
        self.send_response(self.server.server_holder.status)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(self.server.server_holder.body)

    def log_message(self, *args):  # silence request logging
        pass


class _Sts:
    def __init__(self, status=200):
        self.status = status
        self.actions: list[str] = []
        self.body = (
            b'<GetCallerIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">'
            b"<GetCallerIdentityResult>"
            b"<Arn>arn:aws:iam::123456789012:user/pilot</Arn>"
            b"<UserId>AIDAPILOT</UserId>"
            b"<Account>123456789012</Account>"
            b"</GetCallerIdentityResult>"
            b"<ResponseMetadata><RequestId>req-1</RequestId></ResponseMetadata>"
            b"</GetCallerIdentityResponse>"
        )
        self.error_body = (
            b'<ErrorResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">'
            b"<Error><Type>Sender</Type>"
            b"<Code>InvalidClientTokenId</Code>"
            b"<Message>The security token included in the request is invalid</Message>"
            b"</Error><RequestId>req-1</RequestId></ErrorResponse>"
        )
        self.server = _ScriptedServer(_StsHandler)
        self.server.server.server_holder = self

    @property
    def base(self):
        return self.server.base

    def close(self):
        self.server.close()


@pytest.fixture
def sts():
    srv = _Sts()
    yield srv
    srv.close()


class _S3Handler(http.server.BaseHTTPRequestHandler):
    """Scripts the S3 wire surface: HEAD bucket, GET object, PUT object,
    DELETE object. Records every object key and serves failure states."""

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _record(self):
        holder = self.server.server_holder
        holder.keys_seen.append(self.path)
        holder.auth_headers.append(self.headers.get("Authorization"))

    def _xml_error(self, code, status):
        body = f"<Error><Code>{code}</Code><Message>x</Message></Error>".encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self._record()
        holder = self.server.server_holder
        if holder.bucket_exists:
            self.send_response(200)
            self.send_header("x-amz-request-id", "req-1")
            self.end_headers()
        else:
            self._xml_error("NoSuchBucket", 404)

    def do_PUT(self):
        self._record()
        holder = self.server.server_holder
        if holder.put_denied:
            self._xml_error("AccessDenied", 403)
            return
        self._read_body()
        holder.objects[urllib.parse.unquote(self.path)] = b""
        self.send_response(200)
        self.send_header("ETag", '"abc"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._record()
        holder = self.server.server_holder
        key = urllib.parse.unquote(self.path)
        if "list-type=2" in self.path:
            if not holder.bucket_exists:
                return self._xml_error("NoSuchBucket", 404)
            body = (
                b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                b"<Name>bucket</Name><KeyCount>0</KeyCount></ListBucketResult>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if key in holder.objects:
            body = b"probe"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._xml_error("NoSuchKey", 404)

    def do_DELETE(self):
        self._record()
        holder = self.server.server_holder
        holder.deleted.append(urllib.parse.unquote(self.path))
        holder.objects.pop(urllib.parse.unquote(self.path), None)
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):  # silence request logging
        pass


class _S3:
    def __init__(self, *, bucket_exists=True, put_denied=False):
        self.bucket_exists = bucket_exists
        self.put_denied = put_denied
        self.keys_seen: list[str] = []
        self.deleted: list[str] = []
        self.objects: dict[str, bytes] = {}
        self.auth_headers: list = []
        self.server = _ScriptedServer(_S3Handler)
        self.server.server.server_holder = self

    @property
    def base(self):
        return self.server.base

    def close(self):
        self.server.close()


@pytest.fixture
def s3():
    srv = _S3()
    yield srv
    srv.close()


class TestApiBase:
    """The .env.test convention carries a SCHEME-LESS host while the
    scripted servers need an explicit http:// — both forms must work."""

    def test_bare_host_gets_https_prefixed(self):
        # Databricks API endpoints are TLS-only; a bare host from
        # .env.test must not produce an UnsupportedProtocol request.
        assert verify._api_base("abc.cloud.databricks.com") == "https://abc.cloud.databricks.com"

    def test_explicit_scheme_is_preserved(self):
        assert verify._api_base("http://127.0.0.1:1/") == "http://127.0.0.1:1"
        assert (
            verify._api_base("https://x.cloud.databricks.com/") == "https://x.cloud.databricks.com"
        )


def _clear_pilot_env(monkeypatch):
    """Unset every pilot-credential key so probes SKIP rather than drift."""
    for key in (
        "DATABRICKS_PILOT_HOST",
        "DATABRICKS_PILOT_TOKEN",
        "DATABRICKS_PILOT_CLIENT_ID",
        "DATABRICKS_PILOT_CLIENT_SECRET",
        "DATABRICKS_PILOT_HTTP_PATH",
        "DATABRICKS_PILOT_WAREHOUSE_ID",
        "DATABRICKS_PILOT_WORKSPACE_ID",
        "DATABRICKS_HOST",
        "DATABRICKS_TOKEN",
        "DATABRICKS_SANDBOX_WAREHOUSE_ID",
        "DATABRICKS_CLUSTER_ID",
        "DATABRICKS_ACCOUNT_HOST",
        "DATABRICKS_ACCOUNT_ID",
        "DATABRICKS_ACCOUNT_CLIENT_ID",
        "DATABRICKS_ACCOUNT_CLIENT_SECRET",
        "DATABRICKS_ACCOUNT_USERNAME",
        "DATABRICKS_ACCOUNT_PASSWORD",
        "AWS_PILOT_ACCESS_KEY_ID",
        "AWS_PILOT_SECRET_ACCESS_KEY",
        "AWS_PILOT_REGION",
        "AWS_PILOT_ENDPOINT_URL",
        "AWS_PILOT_S3_ENDPOINT_URL",
        "AWS_PILOT_S3_ACCESS_KEY_ID",
        "AWS_PILOT_S3_SECRET_ACCESS_KEY",
        "AWS_PILOT_S3_REGION",
        "DLT_PILOT_BUCKET_URL",
        "DLT_FILESYSTEM_BUCKET_URL",
        "PILOT_BUDGET_CAPS_RESCOPE",
    ):
        monkeypatch.delenv(key, raising=False)


class TestDatabricksPatProbe:
    def test_pass_sends_bearer_and_reports_pass(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        workspace.expected_bearer = TOKEN
        verify._probe_databricks()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert TOKEN not in out
        auth = [r for r in workspace.requests if "/clusters/list" in r["path"]]
        assert auth
        assert auth[0]["authorization"] == f"Bearer {TOKEN}"

    def test_401_fails_with_http_status_and_no_leak(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        workspace.expected_bearer = "the-wrong-token"
        verify._probe_databricks()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "401" in out
        assert TOKEN not in out

    def test_missing_creds_skips_naming_the_keys(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        verify._probe_databricks()
        out = capsys.readouterr().out
        assert "SKIP" in out
        assert "DATABRICKS_PILOT_HOST" in out
        assert "DATABRICKS_PILOT_TOKEN" in out

    def test_host_wiring_mismatch_fails_before_probing(self, workspace, monkeypatch, capsys):
        # The live suites consume DATABRICKS_HOST; if it differs from the
        # pilot host they would run against the WRONG workspace. The probe
        # must fail fast (no request sent — the sandbox must not be probed
        # as if it were the customer).
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("DATABRICKS_HOST", "https://sandbox.cloud.databricks.com")
        verify._probe_databricks()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "mismatch" in out
        assert TOKEN not in out
        assert workspace.requests == [], "mismatch must short-circuit before any request"

    def test_matching_generic_host_is_not_a_mismatch(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_HOST", f"{workspace.base}/")  # scheme+slash normalize
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        workspace.expected_bearer = TOKEN
        verify._probe_databricks()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "mismatch" not in out


class TestDatabricksM2MProbe:
    def test_m2m_exchange_then_bearer_probe_passes(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_CLIENT_ID", "sp-client-id")
        monkeypatch.setenv("DATABRICKS_PILOT_CLIENT_SECRET", CLIENT_SECRET)
        workspace.m2m_client_id = "sp-client-id"
        workspace.m2m_client_secret = CLIENT_SECRET
        workspace.expected_bearer = "m2m-access-token-123"
        verify._probe_databricks()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert CLIENT_SECRET not in out
        exchange = [r for r in workspace.requests if "/oidc/v1/token" in r["path"]]
        assert exchange, "the probe must exchange client credentials first"
        form = exchange[0]["body"]
        assert form.get("grant_type") == ["client_credentials"]
        assert form.get("scope") == ["all-apis"]
        auth = [r for r in workspace.requests if "/clusters/list" in r["path"]]
        assert auth
        assert auth[0]["authorization"] == "Bearer m2m-access-token-123"

    def test_m2m_exchange_failure_fails_without_leaking_the_secret(
        self, workspace, monkeypatch, capsys
    ):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_CLIENT_ID", "sp-client-id")
        monkeypatch.setenv("DATABRICKS_PILOT_CLIENT_SECRET", CLIENT_SECRET)
        workspace.m2m_client_id = "sp-client-id"
        workspace.m2m_client_secret = "wrong"
        verify._probe_databricks()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "400" in out
        assert CLIENT_SECRET not in out

    def test_pat_wins_when_both_auth_modes_are_set(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("DATABRICKS_PILOT_CLIENT_ID", "sp-client-id")
        monkeypatch.setenv("DATABRICKS_PILOT_CLIENT_SECRET", CLIENT_SECRET)
        workspace.expected_bearer = TOKEN
        verify._probe_databricks()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert [r for r in workspace.requests if "/oidc/v1/token" in r["path"]] == []

    def test_unreachable_host_reports_error_class_without_secrets(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", "http://127.0.0.1:1")
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        verify._probe_databricks()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "ConnectError" in out
        assert TOKEN not in out


class TestWarehouseProbe:
    def test_pass_reports_the_warehouse_state(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("DATABRICKS_PILOT_WAREHOUSE_ID", "wh-pilot-1")
        workspace.expected_bearer = TOKEN
        workspace.warehouse_state = "RUNNING"
        verify._probe_warehouse()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "RUNNING" in out

    def test_stopped_warehouse_passes_with_the_state(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("DATABRICKS_PILOT_WAREHOUSE_ID", "wh-pilot-1")
        workspace.expected_bearer = TOKEN
        workspace.warehouse_state = "STOPPED"
        verify._probe_warehouse()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "STOPPED" in out

    def test_never_starts_compute(self, workspace, monkeypatch, capsys):
        # The budget-cap guardrail: no query before the caps are verified.
        # A STOPPED warehouse must be REPORTED, never started.
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("DATABRICKS_PILOT_WAREHOUSE_ID", "wh-pilot-1")
        workspace.expected_bearer = TOKEN
        workspace.warehouse_state = "STOPPED"
        verify._probe_warehouse()
        out = capsys.readouterr().out
        assert "STOPPED" in out
        assert all("/start" not in r["path"] for r in workspace.requests), (
            "the warehouse probe must never POST .../start"
        )

    def test_unknown_warehouse_fails_with_not_found(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("DATABRICKS_PILOT_WAREHOUSE_ID", "wh-wrong-id")
        workspace.expected_bearer = TOKEN
        verify._probe_warehouse()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "404" in out

    def test_missing_warehouse_id_skips(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", "http://127.0.0.1:1")
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        verify._probe_warehouse()
        out = capsys.readouterr().out
        assert "SKIP" in out
        assert "DATABRICKS_PILOT_WAREHOUSE_ID" in out

    def test_sandbox_warehouse_id_mismatch_fails(self, workspace, monkeypatch, capsys):
        # The nightly workflow maps the pilot warehouse into
        # DATABRICKS_SANDBOX_WAREHOUSE_ID — a divergent local value means
        # the live suites would start the WRONG warehouse.
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("DATABRICKS_PILOT_WAREHOUSE_ID", "wh-pilot-1")
        monkeypatch.setenv("DATABRICKS_SANDBOX_WAREHOUSE_ID", "wh-sandbox-9")
        verify._probe_warehouse()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "mismatch" in out
        assert workspace.requests == []

    def test_http_path_warehouse_mismatch_fails(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("DATABRICKS_PILOT_WAREHOUSE_ID", "wh-pilot-1")
        monkeypatch.setenv("DATABRICKS_PILOT_HTTP_PATH", "/sql/1.0/warehouses/wh-other")
        verify._probe_warehouse()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "mismatch" in out

    def test_matching_http_path_passes(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("DATABRICKS_PILOT_WAREHOUSE_ID", "wh-pilot-1")
        monkeypatch.setenv("DATABRICKS_PILOT_HTTP_PATH", "/sql/1.0/warehouses/wh-pilot-1")
        workspace.expected_bearer = TOKEN
        verify._probe_warehouse()
        out = capsys.readouterr().out
        assert "PASS" in out


class TestAwsProbe:
    def test_missing_keys_skips_naming_them(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        verify._probe_aws()
        out = capsys.readouterr().out
        assert "SKIP" in out
        assert "AWS_PILOT_ACCESS_KEY_ID" in out

    def test_valid_keys_pass_via_real_sts(self, sts, monkeypatch, capsys):
        # A real boto3 STS client against a scripted server (endpoint_url)
        # — the AWS Query protocol is exercised over real TCP.
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAPILOTTEST")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", sts.base)
        verify._probe_aws()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "account=123456789012" in out, "the probe must name WHICH account"
        assert AWS_SECRET_KEY not in out
        assert sts.actions == ["GetCallerIdentity"]

    def test_invalid_keys_fail_with_the_error_class(self, sts, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAPILOTTEST")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", sts.base)
        sts.status = 403
        sts.body = sts.error_body
        verify._probe_aws()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "InvalidClientTokenId" in out
        assert AWS_SECRET_KEY not in out
        assert "AKIAPILOTTEST" not in out


class TestDltProbe:
    def test_missing_bucket_url_skips(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "SKIP" in out
        assert "DLT_PILOT_BUCKET_URL" in out

    def test_s3_roundtrip_passes_and_cleans_up(self, s3, monkeypatch, capsys):
        # The destination must be able to RECEIVE data — a list-only probe
        # would miss the write-permission landmine. The probe object is
        # written to a reserved prefix and deleted in the same roundtrip.
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAPILOTTEST")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", s3.base)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", "s3://pilot-bucket/dlt-staging")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert AWS_SECRET_KEY not in out
        put_keys = [
            k
            for k in s3.keys_seen
            if k.startswith("/pilot-bucket/dlt-staging/.datahub-pilot-probe/")
        ]
        assert put_keys, "the probe must write a probe object under the reserved prefix"
        assert put_keys[0] in s3.deleted, "the probe object must be deleted"
        assert s3.objects == {}, "no probe objects may remain in the bucket"

    def test_s3_specific_credential_pair_wins_for_the_dlt_probe(self, s3, monkeypatch, capsys):
        # The dlt destination's credentials are INDEPENDENT of the AWS
        # identity pair: the dev stack's MinIO rejects the Athena keys
        # (InvalidAccessKeyId — hit live 2026-10-05) — the S3-only pair
        # must be used when set.
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAHOSTILE")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", "hostile-secret")
        monkeypatch.setenv("AWS_PILOT_S3_ACCESS_KEY_ID", "AKIAS3PAIR")
        monkeypatch.setenv("AWS_PILOT_S3_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", s3.base)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", "s3://pilot-bucket/staging")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "PASS" in out
        creds = [a for a in s3.auth_headers if a and "Credential=" in a]
        assert creds, "the roundtrip must be signed"
        assert "AKIAS3PAIR" in creds[0], "the S3-only pair must be the one signed"

    def test_dlt_session_region_is_independent_of_the_identity_region(
        self, s3, monkeypatch, capsys
    ):
        # MinIO's default region is us-east-1; the identity pair's region
        # (eu-central-1) breaks the destination signature
        # (InvalidAccessKeyId — hit live 2026-10-05). The dlt session
        # must NOT inherit the identity region.
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAIDENTITY")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_REGION", "eu-central-1")
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", s3.base)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", "s3://pilot-bucket/staging")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "PASS" in out
        creds = [a for a in s3.auth_headers if a and "Credential=" in a]
        assert creds, "the roundtrip must be signed"
        assert "us-east-1" in creds[0], "the dlt session must not inherit eu-central-1"

    def test_s3_specific_region_wins_for_the_dlt_probe(self, s3, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAIDENTITY")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_REGION", "eu-central-1")
        monkeypatch.setenv("AWS_PILOT_S3_REGION", "eu-west-1")
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", s3.base)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", "s3://pilot-bucket/staging")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "PASS" in out
        creds = [a for a in s3.auth_headers if a and "Credential=" in a]
        assert creds
        assert "eu-west-1" in creds[0]

    def test_s3_specific_endpoint_override_wins_for_the_dlt_probe(self, s3, monkeypatch, capsys):
        # The STS identity check and the dlt S3 roundtrip must be
        # INDEPENDENT: pointing dlt at an S3-compatible store (MinIO on
        # the dev stack) must not redirect the AWS identity probe.
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAPILOTTEST")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", "http://127.0.0.1:1")
        monkeypatch.setenv("AWS_PILOT_S3_ENDPOINT_URL", s3.base)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", "s3://pilot-bucket/staging")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "PASS" in out

    def test_filesystem_setting_is_the_fallback(self, s3, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAPILOTTEST")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", s3.base)
        monkeypatch.setenv("DLT_FILESYSTEM_BUCKET_URL", "s3://pilot-bucket/from-setting")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "PASS" in out

    def test_no_such_bucket_fails_with_the_class(self, s3, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAPILOTTEST")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", s3.base)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", "s3://missing-bucket/staging")
        s3.bucket_exists = False
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "NoSuchBucket" in out

    def test_write_denied_fails_with_the_class(self, s3, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAPILOTTEST")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("AWS_PILOT_ENDPOINT_URL", s3.base)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", "s3://pilot-bucket/staging")
        s3.put_denied = True
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "AccessDenied" in out

    def test_s3_needs_the_aws_keys(self, s3, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", "s3://pilot-bucket/staging")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "SKIP" in out
        assert "AWS_PILOT_ACCESS_KEY_ID" in out

    def test_writable_file_destination_passes(self, tmp_path, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", f"file://{tmp_path}")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert list(tmp_path.iterdir()) == [], "the file probe must clean up"

    def test_missing_file_destination_dir_fails(self, tmp_path, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", f"file://{tmp_path}/does-not-exist")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "FAIL" in out

    def test_unsupported_scheme_fails_honestly(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("AWS_PILOT_ACCESS_KEY_ID", "AKIAPILOTTEST")
        monkeypatch.setenv("AWS_PILOT_SECRET_ACCESS_KEY", AWS_SECRET_KEY)
        monkeypatch.setenv("DLT_PILOT_BUCKET_URL", "gs://pilot-bucket/staging")
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "unsupported" in out


class TestBudgetsFreeEditionRescope:
    """The two-account-class contract (product-owner decision
    2026-10-05): PAID accounts must show REAL caps via the account
    budget-policies API; FREE-EDITION accounts (P1 dev) have no budget
    surface at all — the probe must DETECT the absent surface by
    evidence (workspace budget endpoints 404) and report a declared
    RESCOPE state, never a silent skip and never a faked PASS."""

    def _free_edition_env(self, workspace, monkeypatch):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        workspace.expected_bearer = TOKEN

    def test_absent_surface_with_declared_rescope_reports_rescope(
        self, workspace, monkeypatch, capsys
    ):
        self._free_edition_env(workspace, monkeypatch)
        monkeypatch.setenv("PILOT_BUDGET_CAPS_RESCOPE", "free-edition-no-billing")
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "RESCOPE" in out
        assert "free-edition-no-billing" in out
        assert TOKEN not in out
        # the evidence must be named: the workspace budget surfaces were
        # probed and ALL were absent
        probed = [r for r in workspace.requests if "budgets" in r["path"]]
        assert len(probed) == 3, "all three workspace budget surfaces must be probed"

    def test_absent_surface_without_declaration_fails_loudly(self, workspace, monkeypatch, capsys):
        # No re-scope declared: the gate must BLOCK (never silently pass)
        # and tell the operator exactly what to do for each account class.
        self._free_edition_env(workspace, monkeypatch)
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "PILOT_BUDGET_CAPS_RESCOPE" in out
        assert "account credentials" in out

    def test_unknown_rescope_class_fails(self, workspace, monkeypatch, capsys):
        self._free_edition_env(workspace, monkeypatch)
        monkeypatch.setenv("PILOT_BUDGET_CAPS_RESCOPE", "bogus-class")
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "bogus-class" in out
        assert "free-edition-no-billing" in out  # the supported class is named

    def test_existing_workspace_budget_surface_blocks_without_account_creds(
        self, workspace, monkeypatch, capsys
    ):
        # A PAID workspace: the surface EXISTS, so the free-edition class
        # does not apply — the operator must provide account credentials.
        self._free_edition_env(workspace, monkeypatch)
        monkeypatch.setenv("PILOT_BUDGET_CAPS_RESCOPE", "free-edition-no-billing")
        workspace.budget_surfaces = True
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "DATABRICKS_ACCOUNT_ID" in out

    def test_rescope_requires_workspace_creds(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("PILOT_BUDGET_CAPS_RESCOPE", "free-edition-no-billing")
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "SKIP" in out
        assert "DATABRICKS_PILOT_HOST" in out

    def test_account_credentials_path_ignores_the_rescope_var(self, account, monkeypatch, capsys):
        # When account credentials EXIST the real caps path runs and the
        # re-scope switch is irrelevant (a paid account must show caps).
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_USERNAME", "acct-admin@example.com")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_PASSWORD", ACCOUNT_PASSWORD)
        monkeypatch.setenv("PILOT_BUDGET_CAPS_RESCOPE", "free-edition-no-billing")
        account.policies_21 = (200, {"policies": []})
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "no budget policies" in out
        assert "RESCOPE" not in out


class TestBudgetsProbe:
    """The first-query guardrail: no compute until the account has a
    budget policy that covers the pilot workspace."""

    def test_account_m2m_and_policy_list_passes(self, account, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_CLIENT_ID", "acct-sp-id")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_CLIENT_SECRET", CLIENT_SECRET)
        account.m2m_client_id = "acct-sp-id"
        account.m2m_client_secret = CLIENT_SECRET
        account.expected_bearer = "acct-m2m-token-456"
        account.policies_21 = (
            200,
            {
                "policies": [
                    {"policy_name": "pilot-monthly-cap", "binding_workspace_ids": []},
                    {"policy_name": "other-team-cap", "binding_workspace_ids": ["ws-other"]},
                ]
            },
        )
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "pilot-monthly-cap" in out
        assert CLIENT_SECRET not in out
        exchange = [r for r in account.requests if "/oidc/v1/token" in r["path"]]
        assert exchange, "the account API needs the M2M exchange"
        assert exchange[0]["body"].get("scope") == ["all-apis"]
        listing = [r for r in account.requests if "budget-policies" in r["path"]]
        assert listing
        assert listing[0]["authorization"] == "Bearer acct-m2m-token-456"

    def test_empty_policy_list_fails_the_guardrail(self, account, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_USERNAME", "acct-admin@example.com")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_PASSWORD", ACCOUNT_PASSWORD)
        account.expected_basic = base64.b64encode(
            f"acct-admin@example.com:{ACCOUNT_PASSWORD}".encode()
        ).decode()
        account.policies_21 = (200, {"policies": []})
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "no budget policies" in out
        assert ACCOUNT_PASSWORD not in out

    def test_21_404_falls_back_to_the_20_path(self, account, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_USERNAME", "acct-admin@example.com")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_PASSWORD", ACCOUNT_PASSWORD)
        account.expected_basic = base64.b64encode(
            f"acct-admin@example.com:{ACCOUNT_PASSWORD}".encode()
        ).decode()
        account.policies_21 = (404, {})
        account.policies_20 = (
            200,
            {"policies": [{"policy_name": "legacy-cap", "binding_workspace_ids": []}]},
        )
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "legacy-cap" in out
        paths = [r["path"] for r in account.requests if "budget-policies" in r["path"]]
        assert "/api/2.1/accounts/acct-pilot-1/budget-policies" in paths[0]
        assert "/api/2.0/accounts/acct-pilot-1/budget-policies" in paths[1]

    def test_both_surfaces_404_fail_unverifiable(self, account, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_USERNAME", "acct-admin@example.com")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_PASSWORD", ACCOUNT_PASSWORD)
        account.policies_21 = (404, {})
        account.policies_20 = (404, {})
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "unverifiable" in out

    def test_account_exchange_400_hints_workspace_issued_sp(self, account, monkeypatch, capsys):
        # Live-discriminated (2026-10-05): a WORKSPACE-issued SP gets 200
        # on the workspace token endpoint but 400 on the ACCOUNT endpoint.
        # The probe must name that class so the operator goes to the right
        # console (ACCOUNT, not workspace) instead of retrying the secret.
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_CLIENT_ID", "acct-sp-id")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_CLIENT_SECRET", CLIENT_SECRET)
        account.m2m_client_id = "acct-sp-id"
        account.m2m_client_secret = "wrong"
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "400" in out
        assert "ACCOUNT console" in out
        assert CLIENT_SECRET not in out

    def test_401_fails_auth_without_leaking_credentials(self, account, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_USERNAME", "acct-admin@example.com")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_PASSWORD", ACCOUNT_PASSWORD)
        account.expected_basic = base64.b64encode(b"acct-admin@example.com:wrong").decode()
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "401" in out
        assert ACCOUNT_PASSWORD not in out

    def test_policies_bound_to_other_workspaces_fail(self, account, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_USERNAME", "acct-admin@example.com")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_PASSWORD", ACCOUNT_PASSWORD)
        account.policies_21 = (
            200,
            {"policies": [{"policy_name": "other-cap", "binding_workspace_ids": ["ws-other"]}]},
        )
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "pilot workspace" in out

    def test_policy_bound_to_the_pilot_workspace_passes(self, account, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_USERNAME", "acct-admin@example.com")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_PASSWORD", ACCOUNT_PASSWORD)
        monkeypatch.setenv("DATABRICKS_PILOT_WORKSPACE_ID", "ws-pilot")
        account.policies_21 = (
            200,
            {"policies": [{"policy_name": "pilot-cap", "binding_workspace_ids": ["ws-pilot"]}]},
        )
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "pilot-cap" in out

    def test_missing_account_creds_skips_naming_them(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "SKIP" in out
        assert "DATABRICKS_ACCOUNT_ID" in out


class TestMainContract:
    def _argv(self, monkeypatch, args):
        monkeypatch.setattr(sys, "argv", ["verify_pilot_creds.py", *args])

    def test_unknown_probe_exits_2(self, monkeypatch):
        self._argv(monkeypatch, ["bogus"])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 2

    def test_all_skips_exit_0_advisory(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        self._argv(monkeypatch, [])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        for surface in ("databricks", "warehouse", "aws", "dlt", "budgets"):
            assert surface in out

    def test_fail_exits_1(self, workspace, monkeypatch):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        workspace.expected_bearer = "wrong"
        self._argv(monkeypatch, ["databricks"])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 1

    def test_strict_turns_skip_into_exit_1(self, monkeypatch):
        _clear_pilot_env(monkeypatch)
        self._argv(monkeypatch, ["databricks", "--strict"])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 1

    def test_require_budgets_without_budget_pass_exits_1(self, monkeypatch):
        # The first-query gate: even an otherwise-green advisory run must
        # refuse when the budget caps are not VERIFIED.
        _clear_pilot_env(monkeypatch)
        self._argv(monkeypatch, ["--require-budgets"])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 1

    def test_require_budgets_accepts_a_declared_rescope(self, workspace, monkeypatch, capsys):
        # The product-owner re-scope (free-edition account): the gate
        # accepts the DECLARED RESCOPE state — never a faked PASS, and
        # the re-scope is printed on every run.
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("PILOT_BUDGET_CAPS_RESCOPE", "free-edition-no-billing")
        workspace.expected_bearer = TOKEN
        self._argv(monkeypatch, ["budgets", "--require-budgets"])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "RESCOPE" in out

    def test_strict_does_not_fail_a_declared_rescope(self, workspace, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_PILOT_HOST", workspace.base)
        monkeypatch.setenv("DATABRICKS_PILOT_TOKEN", TOKEN)
        monkeypatch.setenv("PILOT_BUDGET_CAPS_RESCOPE", "free-edition-no-billing")
        workspace.expected_bearer = TOKEN
        self._argv(monkeypatch, ["budgets", "--strict"])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 0

    def test_require_budgets_with_budget_pass_exits_0(self, account, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_HOST", account.base)
        monkeypatch.setenv("DATABRICKS_ACCOUNT_ID", "acct-pilot-1")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_USERNAME", "acct-admin@example.com")
        monkeypatch.setenv("DATABRICKS_ACCOUNT_PASSWORD", ACCOUNT_PASSWORD)
        account.policies_21 = (
            200,
            {"policies": [{"policy_name": "cap", "binding_workspace_ids": []}]},
        )
        self._argv(monkeypatch, ["budgets", "--require-budgets"])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 0

    def test_subset_selection_runs_only_the_named_probe(self, monkeypatch, capsys):
        _clear_pilot_env(monkeypatch)
        self._argv(monkeypatch, ["budgets"])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "budgets" in out
        assert "databricks" not in out


class TestLiveSurfaces:
    """Real-surface probes (W16): run only when pilot credentials exist.

    Local runs without the credentials skip gracefully; under CI they
    RAISE (the nightly pilot workflow is the CI consumer). These are the
    same probes the acquisition run itself executes — the scripted-server
    contract above pins behavior; these pin the real surface.
    """

    def _skip_unless(self, *keys):
        missing = [k for k in keys if not os.environ.get(k)]
        if missing:
            from envpolicy import skip_or_fail

            skip_or_fail(f"pilot credentials not set: {', '.join(missing)}")

    def test_live_aws_keys_resolve_the_pilot_account(self, monkeypatch, capsys):
        self._skip_unless("AWS_PILOT_ACCESS_KEY_ID", "AWS_PILOT_SECRET_ACCESS_KEY")
        monkeypatch.delenv("AWS_PILOT_ENDPOINT_URL", raising=False)
        verify._probe_aws()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "account=" in out

    def test_live_dlt_destination_roundtrip(self, monkeypatch, capsys):
        self._skip_unless(
            "AWS_PILOT_ACCESS_KEY_ID",
            "AWS_PILOT_SECRET_ACCESS_KEY",
            "DLT_PILOT_BUCKET_URL",
        )
        monkeypatch.delenv("AWS_PILOT_ENDPOINT_URL", raising=False)
        verify._probe_dlt()
        out = capsys.readouterr().out
        assert "PASS" in out

    def test_live_databricks_workspace_and_warehouse(self, monkeypatch, capsys):
        self._skip_unless(
            "DATABRICKS_PILOT_HOST",
            "DATABRICKS_PILOT_WAREHOUSE_ID",
        )
        verify._probe_databricks()
        verify._probe_warehouse()
        out = capsys.readouterr().out
        assert "PASS" in out

    def test_live_budget_caps_exist_before_any_query(self, monkeypatch, capsys):
        # Two account classes: a PAID account must show REAL caps (PASS);
        # the free-edition P1 account reports the declared RESCOPE. Only
        # when NEITHER applies (no account creds, no re-scope) does the
        # W16 policy fire — an undeclared class must never go green.
        if not os.environ.get("DATABRICKS_ACCOUNT_ID"):
            if os.environ.get("PILOT_BUDGET_CAPS_RESCOPE"):
                verify._probe_budgets()
                out = capsys.readouterr().out
                assert "RESCOPE" in out
                return
            self._skip_unless("DATABRICKS_ACCOUNT_ID")
        verify._probe_budgets()
        out = capsys.readouterr().out
        assert "PASS" in out
