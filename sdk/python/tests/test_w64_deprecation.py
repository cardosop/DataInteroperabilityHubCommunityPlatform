"""
W6.4 (oss-release-remediation) — SDK RFC-8594 deprecation interceptor pins.

The backend emits the standard deprecation headers on sunsetting
surfaces (``Deprecation: true``, ``Sunset: <RFC-7231 date>``,
``Link: <url>; rel="deprecation"`` — the same contract the frontend
interceptor surfaces as a toast). The SDK must surface them the Python
way: a ``DeprecationWarning`` fired ONCE per (path-prefix, sunset-date)
pair, on EVERY response — including error responses — and silent when
the headers are absent.

REAL httpx client against a REAL local HTTP server — no mocks of the
interceptor or the transport.
"""

import asyncio
import re
import threading
import warnings
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from datahub_interoperability.client import DataHubClient, DataHubClientConfig


class _DepHandler(BaseHTTPRequestHandler):
    # RESPONSE headers (never echo the request's — copying its
    # Connection: keep-alive without a Content-Length makes the client
    # read forever).
    response_headers: dict = {}
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
def sdk_client(dep_server):
    base_url, _server = dep_server
    config = DataHubClientConfig(base_url=base_url, api_token="tok")
    return DataHubClient(config)


def _run(coro):
    return asyncio.run(coro)


def test_warns_once_per_endpoint_sunset_pair(dep_server, sdk_client):
    _base, server = dep_server
    server.RequestHandlerClass.response_headers = {
        "Deprecation": "true",
        "Sunset": "Sat, 01 Nov 2031 00:00:00 GMT",
        "Link": "<https://docs.example.com/deprecations/assets-v1>; rel=\"deprecation\"",
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _run(sdk_client.get("/assets/"))
        _run(sdk_client.get("/assets/"))  # same endpoint+sunset — dedup
        assert len(caught) == 1
        msg = str(caught[0].message)
        assert "assets" in msg
        assert "2031" in msg


def test_no_warning_without_headers(dep_server, sdk_client):
    _base, server = dep_server
    server.RequestHandlerClasses = _DepHandler
    server.RequestHandlerClass.response_headers = {}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _run(sdk_client.get("/assets/"))
        assert caught == []


def test_warns_on_error_responses_too(dep_server, sdk_client):
    """The frontend contract inspects EVERY response — a 4xx on a
    deprecated endpoint must still surface the deprecation."""
    _base, server = dep_server
    server.RequestHandlerClass.response_headers = {"Deprecation": "true"}
    server.RequestHandlerClass.status = 404
    server.RequestHandlerClass.body = b'{"error": {"message": "gone"}}'
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            _run(sdk_client.get("/assets/missing/"))
        except Exception:
            pass  # the error class is out of scope; the WARNING is the pin
        assert any(
            "deprecat" in str(w.message).lower() for w in caught
        )


def test_module_exposes_structured_check():
    """The check is a reusable function (path, headers) → bool warned."""
    from datahub_interoperability.deprecation import check_deprecation_headers

    assert callable(check_deprecation_headers)
    # Reset the dedup registry so the direct call warns afresh.
    import datahub_interoperability.deprecation as dep

    dep._SEEN.clear()
    warned = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        check_deprecation_headers(
            "http://api.example.com/api/v1/assets/",
            {
                "Deprecation": "true",
                "Sunset": "Sun, 02 Nov 2031 00:00:00 GMT",
            },
        )
        warned = [str(w.message) for w in caught]
    assert warned
    assert re.search(r"2031|deprecat", warned[0], re.I)
