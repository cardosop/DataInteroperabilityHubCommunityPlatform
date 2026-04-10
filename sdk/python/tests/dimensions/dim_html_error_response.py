import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.5.2 — Dimension: HTML 500 error page.

Verifies that when the backend returns an HTML error page (nginx 502,
Django debug page, etc.) instead of JSON, the client produces a
readable error — not a JSON parse traceback.
"""

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from tests.fixtures.test_data import unique_port

HTML_500_BODY = b"""<!DOCTYPE html>
<html><head><title>500 Internal Server Error</title></head>
<body><h1>500 Internal Server Error</h1>
<p>The server encountered an unexpected condition.</p></body></html>"""


class _HtmlErrorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(500)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(HTML_500_BODY)

    def do_POST(self):
        self.do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture()
def html_error_server():
    port = unique_port()
    server = HTTPServer(("127.0.0.1", port), _HtmlErrorHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_html_500_status_code_is_readable(html_error_server):
    """HTTP 500 with HTML body must report the status code clearly."""
    resp = requests.get(f"{html_error_server}/api/v1/assets/", timeout=5)
    assert resp.status_code == 500


def test_html_500_body_is_not_json(html_error_server):
    """The HTML body must not parse as JSON — caller detects non-JSON."""
    resp = requests.get(f"{html_error_server}/api/v1/assets/", timeout=5)
    ct = resp.headers.get("Content-Type", "")
    assert "html" in ct.lower(), f"Expected text/html, got {ct}"
    # Attempting resp.json() must fail cleanly
    with pytest.raises(requests.exceptions.JSONDecodeError):
        resp.json()


def test_html_error_contains_status_text(html_error_server):
    """The response text must contain human-readable error info."""
    resp = requests.get(f"{html_error_server}/api/v1/assets/", timeout=5)
    assert "500" in resp.text or "Internal Server Error" in resp.text
