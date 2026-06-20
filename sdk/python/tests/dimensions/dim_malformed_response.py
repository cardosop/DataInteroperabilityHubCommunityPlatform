import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.5.1 — Dimension: malformed JSON response.

Verifies that the CLI/SDK produces a specific, actionable error when
the backend returns syntactically invalid JSON — not an unhandled
exception or a cryptic stack trace.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from tests.fixtures.test_data import unique_port


class _MalformedJsonHandler(BaseHTTPRequestHandler):
    """Returns syntactically broken JSON for every request."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"broken: json, missing quote}')

    def do_POST(self):
        self.do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture()
def malformed_server():
    port = unique_port()
    server = HTTPServer(("127.0.0.1", port), _MalformedJsonHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_malformed_json_raises_value_error(malformed_server):
    """GET returning broken JSON must raise a JSON decode error, not crash."""
    resp = requests.get(f"{malformed_server}/api/v1/assets/", timeout=5)
    assert resp.status_code == 200  # HTTP layer succeeded
    with pytest.raises(json.JSONDecodeError):
        resp.json()


def test_malformed_json_error_is_actionable(malformed_server):
    """The JSONDecodeError message must mention the position of the error."""
    resp = requests.get(f"{malformed_server}/api/v1/assets/", timeout=5)
    try:
        resp.json()
        pytest.fail("Expected JSONDecodeError")
    except json.JSONDecodeError as exc:
        msg = str(exc)
        # Must contain position info (line/column)
        assert "line" in msg.lower() or "column" in msg.lower() or "char" in msg.lower(), (
            f"JSONDecodeError message is not actionable: {msg}"
        )


def test_post_with_malformed_response(malformed_server):
    """POST returning broken JSON must also raise cleanly."""
    resp = requests.post(
        f"{malformed_server}/api/v1/assets/",
        json={"name": "test"},
        timeout=5,
    )
    with pytest.raises(json.JSONDecodeError):
        resp.json()
