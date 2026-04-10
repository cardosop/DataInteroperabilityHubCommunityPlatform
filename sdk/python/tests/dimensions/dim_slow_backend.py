import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.5.7 — Dimension: slow backend (high latency, no timeout).

Verifies that the client handles high-latency responses correctly:
- A response that arrives within the configured timeout succeeds
- A response that exceeds the configured timeout raises ReadTimeout
- High latency does NOT cause silent data corruption or truncation
"""

import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from tests.fixtures.test_data import unique_port


class _SlowHandler(BaseHTTPRequestHandler):
    """Responds after a configurable delay."""

    delay_seconds: float = 3.0

    def do_GET(self):
        time.sleep(self.delay_seconds)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","delayed":true}')

    def log_message(self, *args):
        pass


@pytest.fixture()
def slow_server():
    port = unique_port()
    _SlowHandler.delay_seconds = 3.0
    server = HTTPServer(("127.0.0.1", port), _SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_slow_response_within_timeout_succeeds(slow_server):
    """A 3s-delayed response with a 10s timeout must succeed."""
    resp = requests.get(f"{slow_server}/api/v1/health/", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("delayed") is True


def test_slow_response_exceeding_timeout_raises(slow_server):
    """A 3s-delayed response with a 1s timeout must raise ReadTimeout."""
    with pytest.raises(requests.exceptions.ReadTimeout):
        requests.get(f"{slow_server}/api/v1/health/", timeout=1)


def test_slow_response_data_not_truncated(slow_server):
    """The full response body must be received despite the delay."""
    resp = requests.get(f"{slow_server}/api/v1/health/", timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body, "Response body was truncated"
    assert body["status"] == "ok"
