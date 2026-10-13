"""P0 (openspec add-databricks-control-plane task 0.5) — DatabricksApiClient.

No mocks: every test drives a REAL threaded HTTP server on localhost (the
W16 pattern from ``scripts/tests/test_env_policy_py.py``) — real TCP, real
HTTP, real retries, and the REAL shared circuit breaker (in-memory fallback
when Redis is down, which is the supported degraded mode). One W16-gated
test hits the REAL Databricks workspace from ``.env.test`` with a garbage
token and asserts the deterministic 401 → auth-error mapping.
"""

import socket

import httpx
import pytest

from hub.apps.databricks_admin.client import (
    DatabricksApiClient,
    DatabricksAuthError,
    DatabricksConnectionError,
    DatabricksRateLimitError,
    DatabricksUnavailableError,
)
from hub.apps.databricks_admin.tests._fixtures import require_dns

pytestmark = pytest.mark.django_db(transaction=True)


from hub.apps.databricks_admin.tests._http import RecordingHandler


def _client(port, **kwargs):
    kwargs.setdefault("timeout_ms", 5000)
    kwargs.setdefault("max_retries", 3)
    kwargs.setdefault("retry_base_delay", 0.05)
    kwargs.setdefault("retry_max_delay", 0.2)
    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id="t1",
        credential_config={"token": "dapi-test-token"},
        **kwargs,
    )


class TestDatabricksApiClient:
    def test_pat_bearer_header_sent(self, local_http_server):
        RecordingHandler.script = [200]
        _client(local_http_server).request("GET", "workspace.list")
        assert RecordingHandler.requests[-1]["headers"]["Authorization"] == "Bearer dapi-test-token"

    def test_retries_transient_500_then_succeeds(self, local_http_server):
        RecordingHandler.script = [500, 500, 200]
        response = _client(local_http_server).request("GET", "workspace.list")
        assert response.status_code == 200
        assert len(RecordingHandler.requests) == 3, "real retries with backoff expected"

    def test_401_is_not_retried_and_maps_to_auth_error(self, local_http_server):
        RecordingHandler.script = [401]
        with pytest.raises(DatabricksAuthError) as excinfo:
            _client(local_http_server).request("GET", "workspace.list")
        assert excinfo.value.code == "DATABRICKS_AUTH_FAILED"
        assert len(RecordingHandler.requests) == 1, "client errors must not be retried"

    def test_persistent_429_maps_to_rate_limit_error(self, local_http_server):
        RecordingHandler.script = [429, 429, 429]
        with pytest.raises(DatabricksRateLimitError) as excinfo:
            _client(local_http_server, max_retries=3).request("GET", "workspace.list")
        assert excinfo.value.code == "DATABRICKS_RATE_LIMITED"
        assert len(RecordingHandler.requests) == 3

    def test_circuit_breaker_opens_after_failures_and_fails_fast(self, local_http_server):
        # failure_threshold=2, short retry budget — real shared breaker state.
        client = _client(local_http_server, breaker_failure_threshold=2, breaker_timeout_seconds=30)
        RecordingHandler.script = [500, 500, 500]

        with pytest.raises((DatabricksUnavailableError, DatabricksConnectionError)):
            client.request("GET", "workspace.list")

        # Breaker is OPEN now: the next call must fail fast WITHOUT a request.
        hits_before = len(RecordingHandler.requests)
        with pytest.raises(DatabricksUnavailableError):
            client.request("GET", "workspace.list")
        assert len(RecordingHandler.requests) == hits_before, "OPEN breaker must not hit the server"

    def test_connection_refused_maps_to_connection_error(self):
        # Grab a port and close it — nothing listens there.
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
        sock.close()

        with pytest.raises(DatabricksConnectionError):
            _client(dead_port, max_retries=2).request("GET", "workspace.list")

    def test_unknown_operation_raises_value_error(self, local_http_server):
        with pytest.raises(ValueError, match="Unknown Databricks API operation"):
            _client(local_http_server).request("GET", "does.not.exist")

    def test_request_path_serves_raw_paths_without_operation_pinning(self, local_http_server):
        """Task 1.7 — the delegation seam: literal paths bypass the
        operation map while keeping the retry/classification machinery."""
        RecordingHandler.script = [500, 200]
        client = _client(local_http_server)
        response = client.request_path("GET", "/custom/raw/marketplace/path")
        assert response.status_code == 200
        assert len(RecordingHandler.requests) == 2, "raw paths must retry like operations"
        assert RecordingHandler.requests[-1]["path"] == "/custom/raw/marketplace/path"

    def test_delegation_mode_seams(self, local_http_server):
        """Task 1.7 — injected transport + breaker-less mode + injected
        backoff waiter compose (the marketplace connector's wiring)."""
        RecordingHandler.script = [500, 200]
        attempts = []
        transport = httpx.Client(base_url=f"http://127.0.0.1:{local_http_server}", timeout=5.0)
        client = DatabricksApiClient(
            base_url=f"http://127.0.0.1:{local_http_server}",
            credential_config={"token": "dapi-x"},
            client=transport,
            use_breaker=False,
            max_retries=2,
            backoff_waiter=attempts.append,
        )
        assert client._client is transport
        assert client._breaker is None
        response = client.request_path("GET", "/x")
        assert response.status_code == 200
        assert attempts == [0], "the injected waiter receives the retry attempts"
        client.close()

    def test_api_paths_are_version_pinned(self):
        from hub.apps.databricks_admin.api_paths import API_PATHS, path

        assert path("workspace.list") == "/api/2.0/workspace/list"
        assert path("oidc.token") == "/oidc/v1/token"
        assert all(p.startswith(("/api/", "/oidc/")) for p in API_PATHS.values())


class TestRealDatabricksIntegration:
    def test_real_workspace_401_maps_to_auth_error(self):
        """REAL network call: the .env.test workspace rejects a garbage PAT
        with 401 — deterministic, no credentials, no data touched. Also
        proves workspace-mode dispatch validation (real DNS) runs."""
        require_dns()
        from hub.apps.databricks_admin.tests._fixtures import REAL_HOST

        client = DatabricksApiClient(
            host=REAL_HOST,
            tenant_id="t1",
            credential_config={"token": "dapi-invalid-token-for-e2e"},
            timeout_ms=15000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
        )
        with pytest.raises(DatabricksAuthError):
            client.request("GET", "workspace.list")
