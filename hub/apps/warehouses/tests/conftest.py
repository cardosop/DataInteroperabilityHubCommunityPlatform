"""Shared fixtures for warehouses tests (pytest auto-discovery).

``local_http_server`` lives here so test modules use it by parameter name
without importing it — importing a fixture into a test module redefines
the name at every use site (ruff F811).
"""

import http.server
import threading

import pytest


@pytest.fixture
def local_http_server():
    """A real local HTTP server on an ephemeral port (no mocks)."""
    try:
        from hub.apps.databricks_admin.tests._http import RecordingHandler
    except (RuntimeError, ModuleNotFoundError):
        pytest.skip("databricks estate (paid) not installed in core-only mode")

    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
