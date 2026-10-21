"""W10.2 (oss-release-remediation) — staging soak with RLS armed, pins.

Three tiers:

1. UNIT — always run, no staging: the soak engine's parsing/detection and
   response-assessment logic against REAL inputs — a scripted real-TCP HTTP
   server serves the fixture payloads (the repo's no-mock convention: the
   client is the real ApiClient; only the server-side payloads are
   scripted), and the signature detector runs over real JSONL/JSON log
   strings.
2. CONTRACT — always run, no staging: the wiring that makes the staging
   soak load-bearing — the enforced app role in docker-compose.staging.yml,
   the admin-alias management-command mode + owner-role migrate step in
   staging-compose-post-deploy.sh, and the meshant_app full-DML grants in
   init-db.sql.
3. LIVE — the real compose staging stack: the arming-settings probe, the
   DB enforcement probe (unarmed → 0, armed → tenant rows, kill GUC →
   forensic bypass) and the behavioural multi-tenant isolation probes.
   Gated by the W16 environment policy: local runs skip when the stack is
   down (docker absent / api down); CI raises — these pins are NOT wired
   into the CI lists (like the exit-clause drill pin, the real execution
   is the ops run itself).

Run (host-side, repo venv):
    venv/bin/python -m pytest scripts/tests/test_w102_staging_soak.py -q
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "infrastructure" / "scripts"))

# W16 environment policy (project root).
sys.path.insert(0, str(REPO_ROOT))
from envpolicy import api_available  # noqa: E402

import w102_staging_soak as soak  # noqa: E402

COMPOSE_STAGING = REPO_ROOT / "docker-compose.staging.yml"
POST_DEPLOY = REPO_ROOT / "infrastructure" / "scripts" / "staging-compose-post-deploy.sh"
INIT_DB_SQL = (
    REPO_ROOT
    / "infrastructure"
    / "staging"
    / "config-artifacts"
    / "scripts"
    / "init-db.sql"
)
STAGING_API = "http://localhost:8101/api/v1"


# ---------------------------------------------------------------------------
# Tier 1 — unit pins (scripted real-TCP server, no mocks)
# ---------------------------------------------------------------------------

class _ScriptedHandler(BaseHTTPRequestHandler):
    """Scripted server: fixed responses per path (real TCP, real parsing)."""

    routes: dict[str, tuple[int, dict | list]] = {}

    def do_GET(self):  # noqa: N802
        status, payload = self.routes.get(
            self.path.split("?", 1)[0], (404, {"detail": "not found"})
        )
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        status, payload = self.routes.get(self.path, (200, {"token": "t-1"}))
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # silence the per-request stderr line
        pass


@pytest.fixture(scope="module")
def scripted_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ScriptedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}/api/v1", server
    finally:
        server.shutdown()
        thread.join(timeout=5)


class TestLogParsing:
    def test_parse_json_structlog_line(self):
        line = (
            '{"timestamp": "2026-10-17T00:00:00Z", "level": "ERROR", '
            '"logger": "hub.apps.auth.middleware", '
            '"message": "rls_arming_failed", "service": "hub-api"}'
        )
        parsed = soak.parse_log_line(line)
        assert parsed is not None
        assert parsed["message"] == "rls_arming_failed"

    def test_parse_plain_line_returns_none(self):
        assert soak.parse_log_line("[INFO] plain text log") is None

    def test_arm_failure_marker_in_json_line(self):
        line = '{"message": "rls_arming_failed tenant=abc"}'
        assert soak.log_line_is_arm_failure(line) is True

    def test_arm_failure_marker_in_plain_traceback(self):
        line = "ERROR rls_arming_failed: set_config aborted (not a traceback)"
        assert soak.log_line_is_arm_failure(line) is True

    def test_benign_line_is_not_an_arm_failure(self):
        assert soak.log_line_is_arm_failure('{"message": "GET /health 200"}') is False


class TestSignatureDetection:
    EVIDENCE = [
        json.dumps(
            {
                "cycle": 1,
                "requests": [
                    {"kind": "assets", "status": 200, "count": 0},
                    {"kind": "login", "email": "a@example.com", "status": 200},
                ],
            }
        ),
        json.dumps(
            {
                "cycle": 2,
                "requests": [
                    {"kind": "assets", "status": 503, "arm_failed": True},
                    {
                        "kind": "isolation_violation",
                        "url": "/users/x/",
                        "status": 200,
                    },
                    {
                        "kind": "users",
                        "status": 200,
                        "count": 0,
                        "count_drop": {"expected_min": 5, "observed": 0},
                    },
                ],
            }
        ),
    ]

    def test_clean_window_is_all_pass(self):
        evidence = [
            json.dumps(
                {
                    "cycle": 1,
                    "requests": [{"kind": "assets", "status": 200, "count": 2}],
                }
            )
        ]
        summary = soak.detect_signatures(evidence, [], {"default": 1})
        assert summary["overall"] == "PASS"
        assert summary["window_cycles"] == 1

    def test_arm_failure_log_lines_fail_the_window(self):
        logs = ['{"message": "rls_arming_failed"}']
        summary = soak.detect_signatures([], logs, {})
        signals = {s["signature"]: s["verdict"] for s in summary["signals"]}
        assert summary["overall"] == "FAIL"
        assert signals["rls_arming_failed_logs"] == "FAIL"

    def test_arm_failure_503s_fail_the_window(self):
        summary = soak.detect_signatures(self.EVIDENCE, [], {})
        signals = {s["signature"]: s["verdict"] for s in summary["signals"]}
        assert signals["rls_arming_failed_503s"] == "FAIL"
        assert signals["tenant_isolation"] == "FAIL"
        assert signals["empty_result_spikes"] == "FAIL"
        assert summary["overall"] == "FAIL"

    def test_error_rate_spike_fails_the_window(self):
        evidence = [
            json.dumps({"cycle": 1, "requests": [{"kind": "x", "status": 500}]}),
            json.dumps({"cycle": 2, "requests": [{"kind": "x", "status": 200}]}),
        ]
        summary = soak.detect_signatures(evidence, [], {})
        signals = {s["signature"]: s["verdict"] for s in summary["signals"]}
        assert signals["error_rate"] == "FAIL"

    def test_non_json_evidence_lines_are_skipped(self):
        summary = soak.detect_signatures(["garbage", ""], [], {})
        assert summary["window_cycles"] == 0
        assert summary["overall"] == "PASS"


class TestAssess:
    def test_success_with_paginated_count(self):
        entry = soak.assess(
            "assets", 200, {"count": 3, "results": [{}, {}, {}]}
        )
        assert entry == {"kind": "assets", "status": 200, "count": 3}

    def test_5xx_with_arm_failure_code(self):
        entry = soak.assess(
            "assets", 503, {"code": "RLS_ARMING_FAILED", "message": "x"}
        )
        assert entry["error"] is True
        assert entry["arm_failed"] is True

    def test_5xx_without_arm_marker(self):
        entry = soak.assess("assets", 500, {"detail": "boom"})
        assert entry["error"] is True
        assert "arm_failed" not in entry

    def test_count_drop_vs_baseline(self):
        entry = soak.assess("users", 200, {"count": 0}, baseline=5)
        assert entry["count_drop"] == {"expected_min": 5, "observed": 0}

    def test_unexpected_status_is_an_error(self):
        entry = soak.assess("assets", 401, None)
        assert entry["error"] is True


class TestApiClientAgainstScriptedServer:
    def test_request_parses_json_body(self, scripted_server):
        base, server = scripted_server
        _ScriptedHandler.routes["/api/v1/assets/"] = (200, {"count": 7, "results": []})
        client = soak.ApiClient(base=base)
        status, body = client.request("GET", "/assets/")
        assert status == 200
        assert body["count"] == 7

    def test_http_error_is_evidence_not_exception(self, scripted_server):
        base, server = scripted_server
        _ScriptedHandler.routes["/api/v1/assets/"] = (503, {"code": "RLS_ARMING_FAILED"})
        client = soak.ApiClient(base=base)
        status, body = client.request("GET", "/assets/")
        assert status == 503
        assert body["code"] == "RLS_ARMING_FAILED"

    def test_login_stores_token_on_success(self, scripted_server):
        base, server = scripted_server
        _ScriptedHandler.routes["/api/v1/auth/login/"] = (200, {"token": "tok-123"})
        client = soak.ApiClient(base=base)
        status, _ = client.login("a@example.com", "pw")
        assert status == 200
        assert client.token == "tok-123"


# ---------------------------------------------------------------------------
# Tier 2 — contract pins (wiring that makes the soak load-bearing)
# ---------------------------------------------------------------------------

class TestComposeAppRoleContract:
    def test_api_service_uses_the_app_role_knob(self):
        text = COMPOSE_STAGING.read_text()
        assert "${POSTGRES_APP_USER:-" in text
        assert "${POSTGRES_APP_PASSWORD:-" in text

    def test_worker_service_is_not_app_role_flipped(self):
        """The worker flip is a separately-tracked decision (W10.2 scope:
        the request path). The worker block must keep the plain owner-role
        env so the two shapes stay distinguishable."""
        text = COMPOSE_STAGING.read_text()
        # Count occurrences: exactly ONE block may reference the APP knob.
        assert text.count("${POSTGRES_APP_USER:-") == 1


class TestPostDeployWiring:
    def test_management_commands_run_in_admin_db_mode(self):
        text = POST_DEPLOY.read_text()
        manage_fn = text.split("manage() {", 1)[1].split("\n}", 1)[0]
        assert "HUB_USE_ADMIN_DB_FOR_COMMANDS=1" in manage_fn
        manage_env_fn = text.split("manage_env() {", 1)[1].split("\n}", 1)[0]
        assert "HUB_USE_ADMIN_DB_FOR_COMMANDS=1" in manage_env_fn

    def test_migrate_runs_as_the_owner_role(self):
        text = POST_DEPLOY.read_text()
        migrate_fn = text.split("manage_migrate() {", 1)[1].split("\n}", 1)[0]
        assert "-e POSTGRES_USER=\"${PG_USER}\"" in migrate_fn
        assert "-e POSTGRES_PASSWORD=\"${PG_PASSWORD}\"" in migrate_fn
        assert "manage_migrate migrate --noinput" in text

    def test_meshant_app_password_and_grants_sync_step(self):
        text = POST_DEPLOY.read_text()
        assert "ALTER ROLE meshant_app WITH LOGIN PASSWORD" in text
        assert "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO meshant_app" in text


class TestInitDbGrants:
    def test_meshant_app_gets_full_dml(self):
        text = INIT_DB_SQL.read_text()
        assert (
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO meshant_app"
            in text
        )

    def test_meshant_app_gets_sequences(self):
        text = INIT_DB_SQL.read_text()
        assert (
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO meshant_app"
            in text
        )

    def test_default_privileges_cover_future_tables(self):
        text = INIT_DB_SQL.read_text()
        assert (
            "ALTER DEFAULT PRIVILEGES FOR ROLE hub_staging IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO meshant_app"
            in text
        )


# ---------------------------------------------------------------------------
# Tier 3 — live pins (the real staging stack; W16-gated)
# ---------------------------------------------------------------------------

def _staging_up() -> bool:
    return api_available(STAGING_API, timeout=5.0)


def _has_docker() -> bool:
    import shutil

    return shutil.which("docker") is not None


LIVE = pytest.mark.skipif(
    not _staging_up() or not _has_docker(),
    reason="W16: staging compose stack not reachable (local skip; CI raises)",
)


@LIVE
class TestStagingArmingLive:
    def test_api_runs_as_the_enforced_role_and_armed(self):
        report = soak.probe_arming_settings()
        assert report["verdict"] == "PASS", report
        assert report["checks"]["rls_armed"] is True
        assert report["checks"]["default_role_enforced"] is True

    def test_db_enforcement_is_live(self):
        env_map = soak.read_env_file(soak.STAGING_ENV_FILE)
        report = soak.probe_db_enforcement(env_map)
        assert report["verdict"] == "PASS", report
        assert report["counts"]["unarmed"] == 0          # fail closed
        assert report["counts"]["armed_default"] > 0
        assert report["counts"]["bypass_guc"] > report["counts"]["armed_default"]

    def test_behavioural_multi_tenant_isolation(self):
        report = soak._behavioural_isolation(
            soak.ApiClient(), soak.DEFAULT_CREDENTIALS
        )
        assert report["verdict"] == "PASS", report
        for check in report["checks"]:
            assert check["ok"], check
