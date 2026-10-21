"""
W6.4 (oss-release-remediation) — CLI RFC-8594 deprecation interceptor pins.

The CLI must surface the backend's standard deprecation headers
(``Deprecation: true`` / ``Sunset`` / ``Link rel="deprecation"``) on
stderr — once per (path-prefix, sunset-date) pair — on every response,
error responses included, and stay silent without the headers. REAL
requests against a REAL local HTTP server through the REAL api_client
auth path (an API key skips the token refresh), no mocks.
"""

import contextlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from datahub_cli.api_client import api_client
from datahub_cli.config import config


class _DepHandler(BaseHTTPRequestHandler):
    # RESPONSE headers (never echo the request's — copying its
    # Connection: keep-alive without a Content-Length makes the client
    # read forever).
    response_headers: dict = {}  # noqa: RUF012 — class-level responder state, mutated per test
    status = 200
    body = b"{}"

    def do_GET(self):
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.body)))
        for k, v in self.response_headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *_args):
        pass


@pytest.fixture
def dep_server():
    server = HTTPServer(("127.0.0.1", 0), _DepHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/api/v1", server
    server.shutdown()
    server.server_close()


@pytest.fixture
def pointed_api(dep_server, temp_config_dir):
    base_url, server = dep_server
    server.RequestHandlerClass.response_headers = {}
    server.RequestHandlerClass.status = 200
    config.set_api_base_url(base_url)
    config.set_api_key("cli-test-key")
    # Reset the interceptor's dedup registry between tests.
    import datahub_cli.deprecation as dep

    dep._SEEN.clear()
    yield
    config.clear_auth()


def test_warns_once_per_endpoint_sunset_pair(dep_server, pointed_api, capsys):
    _base, server = dep_server
    server.RequestHandlerClass.response_headers = {
        "Deprecation": "true",
        "Sunset": "Sat, 01 Nov 2031 00:00:00 GMT",
        "Link": '<https://docs.example.com/deprecations/assets-v1>; rel="deprecation"',
    }
    api_client.get("assets/")
    api_client.get("assets/")  # dedup
    err = capsys.readouterr().err
    warnings_lines = [line for line in err.splitlines() if "is deprecated" in line]
    assert len(warnings_lines) == 1  # dedup: two requests, ONE warning
    assert "assets" in warnings_lines[0]
    assert "2031" in warnings_lines[0]


def test_silent_without_headers(dep_server, pointed_api, capsys):
    api_client.get("assets/")
    assert "deprecat" not in capsys.readouterr().err


def test_warns_on_error_responses_too(dep_server, pointed_api, capsys):
    """A 4xx on a deprecated endpoint still surfaces the deprecation."""
    _base, server = dep_server
    server.RequestHandlerClass.response_headers = {"Deprecation": "true"}
    server.RequestHandlerClass.status = 404
    server.RequestHandlerClass.body = b'{"error": {"message": "gone"}}'
    with contextlib.suppress(Exception):  # the error class is out of scope; the WARNING is the pin
        api_client.get("assets/missing/")
    assert "deprecat" in capsys.readouterr().err.lower()
