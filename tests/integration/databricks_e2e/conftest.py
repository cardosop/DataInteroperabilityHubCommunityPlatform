"""Shared fixtures for the live E2E sandbox suites (9.3/9.4).

The local-server fixture mirrors the 8.3 ``RecordingHandler`` convention
(real threaded HTTP, scripted responses, recorded requests — no mocks).
The live-client fixtures follow the W16 environment policy: the live
sandbox credentials come from the environment (``DATABRICKS_E2E=1`` +
``DATABRICKS_E2E_WORKSPACE_HOST/TOKEN``); local runs skip, CI raises —
never a silent pass.
"""

import http.server
import threading

import pytest

from envpolicy import environment_guard
from hub.apps.databricks_admin.tests._http import RecordingHandler


@pytest.fixture
def local_http_server():
    """A real local HTTP server on an ephemeral port (no mocks)."""
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


def _require_live_sandbox():
    """W16 — the live sandbox gate: CI raises, local runs skip."""
    import os

    if os.environ.get("DATABRICKS_E2E") == "1" and os.environ.get("DATABRICKS_E2E_WORKSPACE_HOST"):
        return
    environment_guard(
        "DATABRICKS_E2E live sandbox unavailable "
        "(DATABRICKS_E2E=1 + DATABRICKS_E2E_WORKSPACE_HOST/TOKEN required)"
    )
    pytest.skip("live Databricks sandbox unavailable — the nightly workflow arms the gate")


@pytest.fixture
def live_workspace_client():
    """The PRODUCTION workspace client against the live sandbox (W16)."""
    import os

    from hub.apps.databricks_admin.client import DatabricksApiClient

    _require_live_sandbox()
    return DatabricksApiClient(
        host=os.environ["DATABRICKS_E2E_WORKSPACE_HOST"],
        credential_config={"token": os.environ.get("DATABRICKS_E2E_WORKSPACE_TOKEN", "")},
    )
