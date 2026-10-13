"""Shared real-HTTP test server for databricks_admin client tests.

No mocks: a threaded ``http.server`` on an ephemeral port with proper
HTTP/1.1 semantics (Content-Length + Connection: close). Scripted status
sequences + optional JSON token body for the OAuth endpoint.
"""

import http.server
import json
from typing import ClassVar


class RecordingHandler(http.server.BaseHTTPRequestHandler):
    """Serves a scripted status sequence; records requests + headers."""

    # class-level state shared per server instance (reset by the fixture)
    script: ClassVar[list] = []
    requests: ClassVar[list] = []
    token_body: ClassVar[bytes] = b'{"access_token": "tok-abc"}'
    # Scripted JSON response bodies — popped per request when non-empty,
    # taking priority over token_body / the default "{}".
    json_script: ClassVar[list[str]] = []

    def _handle(self):
        # Record the request BODY as well as path/headers — form-body
        # assertions (e.g. the OIDC token exchange in task 0b.1) need the
        # exact parameters the client sent.
        content_length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(content_length) if content_length else b""
        body = raw_body.decode("utf-8", errors="replace")
        type(self).requests.append(
            {"method": self.command, "path": self.path, "headers": dict(self.headers), "body": body}
        )
        status = type(self).script.pop(0) if type(self).script else 200
        if type(self).json_script:
            body = type(self).json_script.pop(0).encode()
        elif self.path == "/oidc/v1/token" and status == 200:
            body = type(self).token_body
        else:
            body = b"{}"
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_PATCH(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def log_message(self, *_args):
        pass


class UCEstateHandler(http.server.BaseHTTPRequestHandler):
    """Path-routed scripted UC REST server for the 1.5 sync tests.

    No mocks: a real threaded HTTP server serving scripted UC list
    envelopes. ``routes`` maps a request path (e.g.
    ``/api/2.1/unity-catalog/catalogs``) to an ORDERED list of response
    bodies — page 1 first. The sync's pagination loop consumes them in
    order, so ``next_page_token`` chains are exercised with the exact
    payload sequence a real workspace would return. The OAuth token
    endpoint answers from ``token_body``. Every request (path, query,
    Authorization header) is recorded for assertions.
    """

    routes: ClassVar[dict[str, list[dict]]] = {}
    requests: ClassVar[list[dict]] = []
    token_body: ClassVar[bytes] = b'{"access_token": "tok-sync-abc", "expires_in": 3600}'
    status: ClassVar[int] = 200

    def _handle(self):
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(self.path)
        type(self).requests.append(
            {
                "path": parsed.path,
                "query": parse_qs(parsed.query),
                "authorization": self.headers.get("Authorization"),
            }
        )
        if parsed.path == "/oidc/v1/token":
            body = type(self).token_body
        else:
            pages = type(self).routes.get(parsed.path)
            body = json.dumps(pages.pop(0)).encode() if pages else b"{}"
        status = type(self).status
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def log_message(self, *_args):
        pass
