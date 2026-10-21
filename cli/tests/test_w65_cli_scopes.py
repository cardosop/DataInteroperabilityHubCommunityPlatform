"""W6.5 (oss-release-remediation, S1) — CLI scope-validation pins.

The vocabulary parity against the backend is pinned by the contract
test (scripts/tests/test_w65_scope_set_contract.py).  These pins cover
the CLI behaviour: `datahub auth api-keys create --scopes` validates
against the carried vocabulary BEFORE any network request — a typo'd
or unmintable scope exits 1 with a clear error naming the invalid scope
and the valid set, and a valid scope proceeds to the wire (real local
HTTP server, the W6.3 pattern).
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from click.testing import CliRunner

CLI_ROOT = Path(__file__).resolve().parents[1]
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from datahub_cli.scopes import (
    ALL_SCOPES,
    SCOPE_SCHEDULED_INGESTION_INTERNAL,
    validate_scopes,
)

# ---------------------------------------------------------------------------
# Real API-key server — the CLI's api_client talks to this over the wire.
# ---------------------------------------------------------------------------


class _ApiKeyHandler(BaseHTTPRequestHandler):
    requests: list[dict] = []  # noqa: RUF012 — class-level recorder, reset per test

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        type(self).requests.append({"path": self.path, "body": body})
        payload = json.dumps({"id": "key-1", "name": body.get("name")}).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        pass


@pytest.fixture
def api_key_server():
    _ApiKeyHandler.requests = []
    server = HTTPServer(("127.0.0.1", 0), _ApiKeyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/v1"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def pointed_config(api_key_server):
    """Point the GLOBAL config at the real local server (the W6.3 pattern)."""
    from datahub_cli.config import config as global_config

    global_config.set_api_base_url(api_key_server)
    yield global_config
    global_config.clear_auth()


@pytest.fixture
def runner():
    return CliRunner()


def _invoke_create(runner, scopes: str):
    """Invoke the real command tree (the W6.3 pattern)."""
    from datahub_cli.main import cli

    return runner.invoke(
        cli,
        ["auth", "api-keys", "create", "--name", "my-key", "--scopes", scopes],
    )


def test_validate_scopes_flags_unknown_and_internal():
    assert validate_scopes(["assets:read"]) == []
    assert validate_scopes(["nope:nope"]) == ["nope:nope"]
    assert validate_scopes([SCOPE_SCHEDULED_INGESTION_INTERNAL]) == [
        SCOPE_SCHEDULED_INGESTION_INTERNAL
    ]
    assert validate_scopes(["*"]) == []


def test_unknown_scope_exits_1_with_clear_error_and_no_request(
    runner, pointed_config
):
    """A typo'd scope fails fast: exit 1, the error names the invalid
    scope AND the valid vocabulary, and NOTHING reached the wire."""
    result = _invoke_create(runner, "nope:nope")

    assert result.exit_code == 1
    assert "Invalid scope(s): nope:nope" in result.output
    assert "Valid scopes:" in result.output
    assert "assets:read" in result.output
    assert _ApiKeyHandler.requests == []


def test_internal_scope_exits_1_with_no_request(runner, pointed_config):
    result = _invoke_create(runner, SCOPE_SCHEDULED_INGESTION_INTERNAL)

    assert result.exit_code == 1
    assert SCOPE_SCHEDULED_INGESTION_INTERNAL in result.output
    assert "never mintable" in result.output
    assert _ApiKeyHandler.requests == []


def test_valid_scope_reaches_the_wire(runner, pointed_config):
    """Valid scopes pass client validation and the request carries them."""
    result = _invoke_create(runner, "assets:read,contracts:write")

    assert result.exit_code == 0, result.output
    assert _ApiKeyHandler.requests == [
        {
            "path": "/api/v1/auth/api-keys/",
            "body": {
                "name": "my-key",
                "scopes": ["assets:read", "contracts:write"],
            },
        }
    ]


def test_wildcard_passes_client_validation_and_reaches_the_wire(
    runner, pointed_config
):
    """`*` is role-gated server-side (R2-B2) — the client lets it pass."""
    result = _invoke_create(runner, "*")

    assert result.exit_code == 0, result.output
    assert _ApiKeyHandler.requests[0]["body"]["scopes"] == ["*"]


def test_all_scopes_is_non_empty_and_wildcard_free():
    assert ALL_SCOPES
    assert "*" not in ALL_SCOPES
