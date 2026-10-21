"""
Contract tests for scripts/verify_old_creds_dead.py (oss-release-remediation
W0.5).

The dead-check is the one-time in-window evidence generator that proves the
OLD credential values (the ones that leaked into git history) are now
REJECTED by their providers after rotation. These tests pin its contract
with real tmp files, a real tmp git repo, and real local HTTP servers — no
mocks or stubs:

- classification is pure string logic — PASS = provider rejects with a
  classified error, FAIL = provider ACCEPTS (still live — stop-the-line),
  SKIP = unverifiable (429/5xx/network/other);
- old values are collected from .env*.bak-* snapshots AND `git show` of
  the named leak commits, hash-deduplicated, and NEVER printed;
- the probe functions send the old value to a recording server and the
  value never appears in the report output;
- --strict (or CI=true) turns an unverifiable surface into exit 1.
"""

import http.server
import importlib.util
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

httpx = pytest.importorskip("httpx")

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

spec = importlib.util.spec_from_file_location(
    "verify_old_creds_dead", scripts_dir / "verify_old_creds_dead.py"
)
dead = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dead)

SECRET = "oldcreds-probe-secret-abc123"  # gitleaks:allow — fake probe fixture (never a real credential; the no-leak pins assert it is SENT, not printed)


class _RecordingHandler(http.server.BaseHTTPRequestHandler):
    """Real stdlib HTTP server that records what it received."""

    received = None

    def do_GET(self):
        _RecordingHandler.received = {
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
        }
        status = int(os.environ["PROBE_SERVER_STATUS"])
        body = json.dumps({"success": False}).encode()
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode() if length else ""
        _RecordingHandler.received = {
            "path": self.path,
            "body": dict(pair.split("=", 1) for pair in raw_body.split("&") if "=" in pair),
        }
        status = int(os.environ["PROBE_SERVER_STATUS"])
        body = json.dumps({"error": "invalid_client", "error_codes": [7000215]}).encode()
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence request logging
        pass


@pytest.fixture
def server(monkeypatch):
    _RecordingHandler.received = None
    monkeypatch.setenv("PROBE_SERVER_STATUS", "200")
    instance = http.server.HTTPServer(("127.0.0.1", 0), _RecordingHandler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    thread.join(timeout=5)


class TestClassifiers:
    """Pure verdict logic — PASS=rejected, FAIL=accepted, SKIP=unverifiable."""

    def test_http_rejection_codes_are_dead(self):
        assert dead.classify_http_status(401) == "PASS"
        assert dead.classify_http_status(403) == "PASS"

    def test_http_success_means_the_old_cred_is_still_live(self):
        for code in (200, 201, 204):
            assert dead.classify_http_status(code) == "FAIL"

    def test_http_transient_or_server_errors_are_unverifiable(self):
        for code in (429, 500, 502, 503, 302):
            assert dead.classify_http_status(code) == "SKIP"

    def test_aws_sts_rejection_codes_are_dead(self):
        for code in (
            "InvalidClientTokenId",
            "InvalidAccessKeyId",
            "AccessDenied",
            "ExpiredToken",
        ):
            assert dead.classify_aws_sts(code) == "PASS"

    def test_aws_sts_success_means_live(self):
        assert dead.classify_aws_sts("") == "FAIL"

    def test_aws_sts_unclassified_is_unverifiable(self):
        assert dead.classify_aws_sts("SomeUnknownCode") == "SKIP"

    def test_gcp_invalid_grant_is_dead(self):
        assert dead.classify_gcp_grant("invalid_grant") == "PASS"
        assert dead.classify_gcp_grant("400 invalid_grant: account disabled") == "PASS"

    def test_gcp_exchange_success_means_live(self):
        assert dead.classify_gcp_grant("") == "FAIL"

    def test_gcp_unknown_error_is_unverifiable(self):
        assert dead.classify_gcp_grant("ConnectionError") == "SKIP"

    def test_azure_invalid_client_is_dead(self):
        assert dead.classify_azure_token(401, "AADSTS7000215") == "PASS"
        assert dead.classify_azure_token(400, "AADSTS7000222") == "PASS"

    def test_azure_token_success_means_live(self):
        assert dead.classify_azure_token(200, "") == "FAIL"

    def test_azure_unknown_error_is_unverifiable(self):
        assert dead.classify_azure_token(503, "") == "SKIP"

    def test_snowflake_auth_rejection_is_dead(self):
        assert dead.classify_snowflake_auth("Invalid OAuth access token") == "PASS"
        assert dead.classify_snowflake_auth("Authentication failed") == "PASS"

    def test_snowflake_connected_means_live(self):
        assert dead.classify_snowflake_auth("") == "FAIL"

    def test_snowflake_connection_failure_is_unverifiable(self):
        assert dead.classify_snowflake_auth("Connection timeout") == "SKIP"


class TestSourceCollection:
    """Old values come from .bak snapshots + git show of the leak commits."""

    def test_parse_env_file_extracts_pairs_without_printing(self, tmp_path, capsys):
        path = tmp_path / ".env.test.bak"
        path.write_text(
            f"# comment\nAWS_ACCESS_KEY_ID={SECRET}\nAWS_SECRET_ACCESS_KEY=other\n"
            'SNOWFLAKE_TOKEN=\nGCP_CREDENTIALS_JSON={"k":"v"}\n'
        )
        parsed = dead.parse_env_file(path)
        assert parsed["AWS_ACCESS_KEY_ID"] == SECRET
        assert parsed["AWS_SECRET_ACCESS_KEY"] == "other"
        assert "SNOWFLAKE_TOKEN" not in parsed  # empty values are not sources
        assert parsed["GCP_CREDENTIALS_JSON"] == '{"k":"v"}'
        assert SECRET not in capsys.readouterr().out

    def test_git_show_sources_parse_from_a_real_commit(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
        (repo / ".env.test").write_text(f"AWS_ACCESS_KEY_ID={SECRET}\n")
        subprocess.run(["git", "-C", str(repo), "add", ".env.test"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "leak"], check=True)
        sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        parsed = dead.git_show(repo, sha, ".env.test")
        assert parsed["AWS_ACCESS_KEY_ID"] == SECRET

    def test_git_show_returns_none_for_missing_ref(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        assert dead.git_show(repo, "deadbeef", ".env.test") is None

    def test_collect_deduplicates_identical_values(self, tmp_path):
        bak = tmp_path / ".env.test.bak"
        bak.write_text(f"STRIPE_SECRET_KEY={SECRET}\n")
        other = tmp_path / ".env.test.bak-2"
        other.write_text(f"STRIPE_SECRET_KEY={SECRET}\n")
        collected = dead.collect_old_values([bak, other], git_sources=[])
        assert collected["stripe"] == [(SECRET,)]


class TestProbeNoLeak:
    """The probes SEND the old value but never PRINT it."""

    def test_stripe_dead_probe_reports_401_pass_without_leaking(self, server, monkeypatch, capsys):
        monkeypatch.setenv("PROBE_SERVER_STATUS", "401")
        status, detail = dead.probe_stripe_dead(
            SECRET, base=f"http://127.0.0.1:{server.server_address[1]}"
        )
        assert status == "PASS"
        assert SECRET not in detail
        assert SECRET not in capsys.readouterr().out

    def test_stripe_live_probe_reports_fail(self, server, monkeypatch):
        monkeypatch.setenv("PROBE_SERVER_STATUS", "200")
        status, _ = dead.probe_stripe_dead(
            SECRET, base=f"http://127.0.0.1:{server.server_address[1]}"
        )
        assert status == "FAIL"

    def test_databricks_dead_probe_sends_bearer_without_leaking(self, server, monkeypatch, capsys):
        monkeypatch.setenv("PROBE_SERVER_STATUS", "403")
        status, detail = dead.probe_databricks_dead(
            f"http://127.0.0.1:{server.server_address[1]}", SECRET
        )
        assert status == "PASS"
        assert _RecordingHandler.received["authorization"] == f"Bearer {SECRET}"
        assert "/api/2.0/clusters/list" in _RecordingHandler.received["path"]
        assert SECRET not in detail
        assert SECRET not in capsys.readouterr().out

    def test_azure_dead_probe_sends_secret_without_leaking(self, server, monkeypatch, capsys):
        monkeypatch.setenv("PROBE_SERVER_STATUS", "401")
        status, detail = dead.probe_azure_dead(
            "tenant",
            "client",
            SECRET,
            endpoint=f"http://127.0.0.1:{server.server_address[1]}/token",
        )
        assert status == "PASS"
        assert _RecordingHandler.received["body"]["client_secret"] == SECRET
        assert SECRET not in detail
        assert SECRET not in capsys.readouterr().out


class TestCliContract:
    def test_missing_sources_report_advisory_rows(self, tmp_path, monkeypatch, capsys):
        # Post-force-push shape: no baks, no git sources — the CLI must
        # report ADVISORY rows (frozen-evidence mode), not crash or
        # fabricate values, and exit 0 in advisory mode.
        monkeypatch.setenv("OLD_CREDS_BAK_FILES", str(tmp_path / "none.bak"))
        monkeypatch.setenv("OLD_CREDS_GIT_COMMITS", "")
        monkeypatch.setenv("OLD_CREDS_CURRENT_FILES", str(tmp_path / "none.env"))
        rc = dead.main([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "source-missing" in out

    def test_strict_turns_missing_sources_into_failure(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("OLD_CREDS_BAK_FILES", str(tmp_path / "none.bak"))
        monkeypatch.setenv("OLD_CREDS_GIT_COMMITS", "")
        monkeypatch.setenv("OLD_CREDS_CURRENT_FILES", str(tmp_path / "none.env"))
        rc = dead.main(["--strict"])
        assert rc == 1
        assert "source-missing" in capsys.readouterr().out

    def test_ci_environment_implies_strict(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CI", "true")
        monkeypatch.setenv("OLD_CREDS_BAK_FILES", str(tmp_path / "none.bak"))
        monkeypatch.setenv("OLD_CREDS_GIT_COMMITS", "")
        monkeypatch.setenv("OLD_CREDS_CURRENT_FILES", str(tmp_path / "none.env"))
        assert dead.main([]) == 1
