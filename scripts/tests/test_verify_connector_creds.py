"""
Contract tests for scripts/verify_connector_creds.py.

The verify script is the credential-probe oracle used by the pilot-readiness
rehearsals (openspec/changes/pilot-readiness task 1.4). These tests pin its
contract without mocks or stubs:

- probes NEVER print secret values — a live local HTTP server records the
  Authorization header it received, so the no-leak assertion is not vacuous;
- PASS / FAIL / SKIP reporting is driven by real HTTP status codes and real
  environment state;
- CKAN_TEST_BASE_URL overrides the compose-internal default host, which makes
  the probe runnable host-side (a host cannot resolve `ckan-test`).
"""

import http.server
import importlib.util
import json
import os
import sys
import threading
from pathlib import Path

import pytest

httpx = pytest.importorskip("httpx")

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "verify_connector_creds.py"
spec = importlib.util.spec_from_file_location("verify_connector_creds", script_path)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

SECRET = "verifyprobe-secret-abc123"  # gitleaks:allow — fake probe fixture (never a real credential; the no-leak pins assert it is SENT, not printed)


class _RecordingHandler(http.server.BaseHTTPRequestHandler):
    """Real stdlib HTTP server that records the Authorization header."""

    received = None

    def do_GET(self):
        _RecordingHandler.received = {
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
        }
        status = int(os.environ["PROBE_SERVER_STATUS"])
        success = os.environ.get("PROBE_SERVER_BODY_SUCCESS", "true") == "true"
        body = json.dumps({"success": success}).encode()
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        """Token-endpoint stand-in: records the form body it received."""
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode() if length else ""
        _RecordingHandler.received = {
            "path": self.path,
            "body": dict(pair.split("=", 1) for pair in raw_body.split("&") if "=" in pair),
        }
        status = int(os.environ["PROBE_SERVER_STATUS"])
        body = json.dumps({"access_token": "probe-token"}).encode()
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence request logging
        pass


@pytest.fixture
def probe_server(monkeypatch):
    """A real HTTP server on an ephemeral port standing in for CKAN."""
    _RecordingHandler.received = None
    monkeypatch.setenv("PROBE_SERVER_STATUS", "200")
    server = http.server.HTTPServer(("127.0.0.1", 0), _RecordingHandler)
    monkeypatch.setenv("CKAN_TEST_BASE_URL", f"http://127.0.0.1:{server.server_address[1]}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    thread.join(timeout=5)


def _serve(monkeypatch):
    """Start a recording server; the test points the probe at it."""
    _RecordingHandler.received = None
    monkeypatch.setenv("PROBE_SERVER_STATUS", "200")
    server = http.server.HTTPServer(("127.0.0.1", 0), _RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture
def azure_server(monkeypatch):
    """A real HTTP server standing in for the Azure token endpoint."""
    yield from _serve(monkeypatch)


@pytest.fixture
def databricks_server(monkeypatch):
    """A real HTTP server standing in for the Databricks workspace."""
    yield from _serve(monkeypatch)


class TestNoSecretLeakage:
    """The probe's core safety contract: the key is sent, never printed."""

    def test_pass_path_never_prints_the_key(self, probe_server, monkeypatch, capsys):
        monkeypatch.setenv("CKAN_TEST_API_KEY", SECRET)
        verify._probe_ckan()
        out = capsys.readouterr().out
        assert "PASS" in out
        assert SECRET not in out
        # The server really received the key — the no-leak check is not vacuous.
        assert _RecordingHandler.received["authorization"] == SECRET
        # The probe must hit an auth-required action with the admin user_id:
        # package_list is public (a bogus token also gets 200 there).
        assert "/api/3/action/api_token_list" in _RecordingHandler.received["path"]
        assert "user_id=admin" in _RecordingHandler.received["path"]

    def test_http_200_with_success_false_is_a_failure(self, probe_server, monkeypatch, capsys):
        # CKAN action API returns 200 with {"success": false} on denied
        # actions — a status-only check would wrongly report PASS.
        monkeypatch.setenv("CKAN_TEST_API_KEY", SECRET)
        monkeypatch.setenv("PROBE_SERVER_STATUS", "200")
        monkeypatch.setenv("PROBE_SERVER_BODY_SUCCESS", "false")
        verify._probe_ckan()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert SECRET not in out

    def test_fail_path_never_prints_the_key(self, probe_server, monkeypatch, capsys):
        monkeypatch.setenv("CKAN_TEST_API_KEY", SECRET)
        monkeypatch.setenv("PROBE_SERVER_STATUS", "403")
        verify._probe_ckan()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "403" in out
        assert SECRET not in out

    def test_unreachable_host_reports_error_class_without_key(self, monkeypatch, capsys):
        monkeypatch.setenv("CKAN_TEST_API_KEY", SECRET)
        monkeypatch.setenv("CKAN_TEST_BASE_URL", "http://127.0.0.1:1")  # closed port
        verify._probe_ckan()
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "ConnectError" in out
        assert SECRET not in out


class TestCkanProbeResult:
    """The extracted pure probe (status, detail) reused by other tooling."""

    def test_pass_returns_status_tuple(self, probe_server, monkeypatch):
        monkeypatch.setenv("CKAN_TEST_API_KEY", SECRET)
        status, detail = verify.ckan_probe_result(SECRET)
        assert status == "PASS"
        assert detail == ""
        assert _RecordingHandler.received["authorization"] == SECRET

    def test_fail_returns_http_status_detail(self, probe_server, monkeypatch):
        monkeypatch.setenv("PROBE_SERVER_STATUS", "403")
        status, detail = verify.ckan_probe_result(SECRET)
        assert status == "FAIL"
        assert detail == "HTTP 403"
        assert SECRET not in detail

    def test_missing_key_skips(self, monkeypatch):
        monkeypatch.delenv("CKAN_TEST_API_KEY", raising=False)
        status, detail = verify.ckan_probe_result(None)
        assert status == "SKIP"
        assert "CKAN_TEST_API_KEY" in detail

    def test_http_200_success_false_is_a_failure(self, probe_server, monkeypatch):
        monkeypatch.setenv("PROBE_SERVER_STATUS", "200")
        monkeypatch.setenv("PROBE_SERVER_BODY_SUCCESS", "false")
        status, detail = verify.ckan_probe_result(SECRET)
        assert status == "FAIL"
        assert detail == "HTTP 200"

    def test_base_url_and_admin_user_overrides(self, probe_server, monkeypatch):
        monkeypatch.setenv("CKAN_TEST_ADMIN_USER", "customuser")
        status, _ = verify.ckan_probe_result(SECRET, admin_user="customuser")
        assert status == "PASS"
        assert "user_id=customuser" in _RecordingHandler.received["path"]

    def test_unreachable_reports_error_class(self, monkeypatch):
        status, detail = verify.ckan_probe_result(SECRET, base="http://127.0.0.1:1")
        assert status == "FAIL"
        assert "ConnectError" in detail


class TestCkanBaseUrlOverride:
    def test_default_base_url_is_compose_internal_host(self):
        assert verify._CKAN_DEFAULT_BASE_URL == "http://ckan-test:5000"

    def test_env_override_is_used_for_the_request(self, probe_server, monkeypatch, capsys):
        monkeypatch.setenv("CKAN_TEST_API_KEY", SECRET)
        verify._probe_ckan()
        out = capsys.readouterr().out
        # The local server answered — proof the request went to the override,
        # not to the compose-internal host the host machine cannot resolve.
        assert "PASS" in out


class TestSkipWhenKeyMissing:
    @pytest.mark.parametrize(
        ("probe", "keys"),
        [
            (verify._probe_ckan, ("CKAN_TEST_API_KEY",)),
            (verify._probe_snowflake, ("SNOWFLAKE_TOKEN",)),
            (verify._probe_stripe, ("STRIPE_SECRET_KEY",)),
            (verify._probe_azure, ("AZURE_MARKETPLACE_API_KEY", "AZURE_CATALOG_API_KEY")),
            (
                verify._probe_dados,
                ("DADOS_GOV_BR_API_KEY", "CKAN_DADOS_GOV_BR_API_KEY"),
            ),
            (verify._probe_gcp, ("GCP_CREDENTIALS_JSON", "GCP_SERVICE_ACCOUNT_JSON")),
            (verify._probe_azure_sp, ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_CLIENT_SECRET")),
            (verify._probe_databricks, ("DATABRICKS_HOST", "DATABRICKS_TOKEN")),
        ],
        ids=["ckan", "snowflake", "stripe", "azure", "dados", "gcp", "azure-sp", "databricks"],
    )
    def test_probe_skips_when_key_is_unset(self, probe, keys, monkeypatch, capsys):
        for key in keys:
            monkeypatch.delenv(key, raising=False)
        probe()
        out = capsys.readouterr().out
        assert "SKIP" in out
        assert SECRET not in out


class TestGcpProbe:
    """The gcp probe: SA-key JSON validity, never the key material."""

    def test_missing_key_returns_skip_tuple(self, monkeypatch):
        monkeypatch.delenv("GCP_CREDENTIALS_JSON", raising=False)
        monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
        status, detail = verify.gcp_probe_result(None)
        assert status == "SKIP"
        assert "GCP_CREDENTIALS_JSON" in detail

    def test_malformed_json_fails_without_leaking(self, capsys):
        status, detail = verify.gcp_probe_result("not-json{{")
        assert status == "FAIL"
        assert "not-json{{" not in detail
        assert "not-json{{" not in capsys.readouterr().out

    def test_fallback_to_gcp_service_account_json(self, monkeypatch):
        monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", "{}")
        status, _detail = verify.gcp_probe_result(None)
        # An empty SA dict is a ValueError-class failure, not a SKIP — the
        # fallback env var was read (missing key would have skipped).
        assert status == "FAIL"


class TestAzureSpProbe:
    """The azure-sp probe: client_credentials exchange, no secret leakage."""

    def test_missing_credentials_skip(self, monkeypatch):
        monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
        monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
        status, detail = verify.azure_sp_probe_result(None, None, None)
        assert status == "SKIP"
        assert "AZURE_CLIENT_SECRET" in detail or "AZURE_CLIENT_ID" in detail

    def test_endpoint_override_hits_the_local_server(self, azure_server, monkeypatch, capsys):
        monkeypatch.setenv(
            "AZURE_TOKEN_ENDPOINT",
            f"http://127.0.0.1:{azure_server.server_address[1]}/token",
        )
        monkeypatch.setenv("PROBE_SERVER_STATUS", "200")
        status, detail = verify.azure_sp_probe_result("tenant", "client", SECRET)
        assert status == "PASS"
        assert SECRET not in detail
        assert SECRET not in capsys.readouterr().out
        # The secret really was sent (no-leak check is not vacuous).
        assert _RecordingHandler.received["body"].get("client_secret") == SECRET

    def test_invalid_client_secret_fails(self, azure_server, monkeypatch):
        monkeypatch.setenv(
            "AZURE_TOKEN_ENDPOINT",
            f"http://127.0.0.1:{azure_server.server_address[1]}/token",
        )
        monkeypatch.setenv("PROBE_SERVER_STATUS", "401")
        status, detail = verify.azure_sp_probe_result("tenant", "client", SECRET)
        assert status == "FAIL"
        assert SECRET not in detail


class TestDatabricksProbe:
    """The databricks probe: sandbox workspace auth (host + PAT)."""

    def test_missing_credentials_skip(self, monkeypatch):
        monkeypatch.delenv("DATABRICKS_HOST", raising=False)
        monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
        status, detail = verify.databricks_probe_result(None, None)
        assert status == "SKIP"
        assert "DATABRICKS_TOKEN" in detail or "DATABRICKS_HOST" in detail

    def test_passes_on_200_without_leaking(self, databricks_server, monkeypatch, capsys):
        monkeypatch.setenv("PROBE_SERVER_STATUS", "200")
        status, detail = verify.databricks_probe_result(
            f"http://127.0.0.1:{databricks_server.server_address[1]}", SECRET
        )
        assert status == "PASS"
        assert SECRET not in detail
        assert SECRET not in capsys.readouterr().out
        assert _RecordingHandler.received["authorization"] == f"Bearer {SECRET}"
        assert "/api/2.0/clusters/list" in _RecordingHandler.received["path"]

    def test_forbidden_fails(self, databricks_server, monkeypatch):
        monkeypatch.setenv("PROBE_SERVER_STATUS", "403")
        status, detail = verify.databricks_probe_result(
            f"http://127.0.0.1:{databricks_server.server_address[1]}", SECRET
        )
        assert status == "FAIL"
        assert "403" in detail
        assert SECRET not in detail

    def test_schemeless_host_gets_https_prefix(self):
        # The env files carry bare hosts ("xxx.cloud.databricks.com") —
        # the probe must add the scheme itself (the live PRE run found
        # the UnsupportedProtocol failure this pin locks out).
        assert verify._normalize_host("adb-123.azuredatabricks.net") == (
            "https://adb-123.azuredatabricks.net"
        )

    def test_host_with_scheme_is_untouched(self):
        assert verify._normalize_host("http://127.0.0.1:1") == "http://127.0.0.1:1"
        assert verify._normalize_host("https://x.example") == "https://x.example"


class TestStrictMode:
    """--strict turns a SKIP into exit 1 (the gate mode)."""

    def test_strict_skips_fail_the_cli(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["verify_connector_creds.py", "ckan", "--strict"])
        monkeypatch.delenv("CKAN_TEST_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 1
        assert "SKIP" in capsys.readouterr().out

    def test_advisory_mode_skips_still_exit_zero(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["verify_connector_creds.py", "ckan"])
        monkeypatch.delenv("CKAN_TEST_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 0

    def test_ci_environment_implies_strict(self, monkeypatch):
        monkeypatch.setenv("CI", "true")
        monkeypatch.setattr(sys, "argv", ["verify_connector_creds.py", "ckan"])
        monkeypatch.delenv("CKAN_TEST_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 1


class TestMainContract:
    def test_unknown_connector_exits_2(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["verify_connector_creds.py", "bogus"])
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 2

    def test_single_connector_runs_only_that_probe(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["verify_connector_creds.py", "ckan"])
        monkeypatch.delenv("CKAN_TEST_API_KEY", raising=False)
        # main() exits 0 on success — the CLI contract, not a failure.
        with pytest.raises(SystemExit) as exc_info:
            verify.main()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "ckan" in out
        assert "SKIP" in out
        assert "snowflake" not in out
        assert "stripe" not in out
