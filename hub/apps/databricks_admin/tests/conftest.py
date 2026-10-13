"""Shared fixtures for databricks_admin tests.

``local_http_server`` lives here (conftest) so test modules use it by
parameter name without importing it — importing a fixture into a test
module redefines the name at every use site (ruff F811).
"""

import http.server
import threading

import pytest

from hub.apps.databricks_admin.tests._fixtures import redis_13_client
from hub.apps.databricks_admin.tests._http import RecordingHandler


@pytest.fixture(autouse=True)
def _reset_recording_handler():
    """Reset the class-level request recorder for EVERY test.

    Tests that assert zero/total network calls WITHOUT the
    ``local_http_server`` fixture (e.g. the 1.3 fail-closed pin) must
    never inherit a previous test's recorded requests — the reset used to
    live only inside the fixture, so fixture-less assertions saw stale
    state (1.3 review fix)."""
    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []


@pytest.fixture
def local_http_server():
    """A real local HTTP server on an ephemeral port (no mocks).

    Resets the class-level recording state per test so request counts are
    isolated (the script/requests lists are shared across handler threads).
    """
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


# Real Redis for the OBO/M2M cache + budget suites — ONE shared fixture
# (close-test-coverage-gaps 0.3): the endpoint resolves from REDIS_CACHE_URL
# (compose) with the host-side 127.0.0.1:63799/db13 as fallback, W16-gated.
redis_13 = pytest.fixture(redis_13_client)
