"""
Task 1.7 (openspec add-databricks-control-plane) — delegation contract.

``DatabricksConnector._request_with_retry`` delegates its retry/backoff/
status-classification machinery to ``DatabricksApiClient`` while keeping
the connector's public contract (same exceptions, same breaker accounting,
same deterministic backoff policy).

No mocks: a real threaded HTTP server on an ephemeral port (the W16
pattern, reusing the shared ``RecordingHandler`` from
``hub.apps.databricks_admin.tests._http``) — real TCP, real retries, and a
real ``CircuitBreaker``. The only knobs touched are configuration:
``backoff_factor = 0`` (so the REAL retry loop runs without wall-clock
sleeps) and a low-threshold real breaker for the fail-fast pin. No
database — the suite is a plain transport contract.
"""

import http.server
import socket
import threading

import httpx
import pytest

from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    reset_circuit_breaker_by_name,
)
from hub.apps.core.services.base import NotFoundError
from hub.apps.databricks_admin.client import DatabricksApiClient
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector


@pytest.fixture
def connector_with_server():
    """A connector pointed at a real local HTTP server, fast backoff."""
    reset_circuit_breaker_by_name("databricks-connector")
    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connector = DatabricksConnector(
        host=f"http://127.0.0.1:{port}", token="dapi-delegation-test-token"
    )
    # Zero backoff delay — the REAL retry loop still runs, it just
    # does not sleep wall-clock seconds (configuration, not a mock).
    connector.backoff_factor = 0
    try:
        yield connector, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestDelegationContract:
    """The connector delegates to a REAL DatabricksApiClient (structural pins)."""

    def test_connector_builds_delegate_with_transport_and_credentials(self, connector_with_server):
        """The delegate carries the connector's host, PAT credential, retry
        budget, and — critically — its OWN httpx transport, with no
        client-side breaker (the connector's breaker owns accounting)."""
        connector, _port = connector_with_server
        delegate = connector._api_client
        assert isinstance(delegate, DatabricksApiClient)
        assert delegate._base_url == connector.host
        assert delegate._auth_mode == "PAT"
        assert delegate._credential_config == {"token": "dapi-delegation-test-token"}
        # The client's max_retries counts TOTAL attempts; the connector's
        # counts retries after the first attempt — +1 keeps 3 attempts.
        assert delegate._max_retries == connector.max_retries + 1
        assert delegate._client is connector.client
        assert delegate._breaker is None

    def test_authenticate_rebuilds_the_delegate(self, connector_with_server):
        """Rotating credentials through ``authenticate()`` must re-wire the
        delegate to the new transport/token (the old retry loop's behavior)."""
        connector, port = connector_with_server
        RecordingHandler.script = [200]  # the workspace/list connection probe
        result = connector.authenticate(
            {"host": f"http://127.0.0.1:{port}", "token": "dapi-rotated-token"}
        )
        assert result is True
        assert connector._api_client._credential_config == {"token": "dapi-rotated-token"}
        assert connector._api_client._client is connector.client


class TestDelegatedRequestBehavior:
    """Real HTTP: the delegated path keeps the connector's public contract."""

    def test_retries_transient_500_then_succeeds(self, connector_with_server):
        """Real retries through the delegate: 500, 500, 200 → success."""
        connector, _port = connector_with_server
        RecordingHandler.script = [500, 500, 200]
        response = connector._request_with_retry("GET", "/api/2.0/test")
        assert response.status_code == 200
        assert len(RecordingHandler.requests) == 3

    def test_bearer_token_sent_on_the_wire(self, connector_with_server):
        """The connector's token rides the wire as the Bearer header."""
        connector, _port = connector_with_server
        RecordingHandler.script = [200]
        connector._request_with_retry("GET", "/api/2.0/test")
        assert (
            RecordingHandler.requests[-1]["headers"].get("Authorization")
            == "Bearer dapi-delegation-test-token"
        )

    def test_404_maps_to_not_found_error_without_retry(self, connector_with_server):
        """Client errors are terminal and map onto the public contract."""
        connector, _port = connector_with_server
        RecordingHandler.script = [404]
        with pytest.raises(NotFoundError):
            connector._request_with_retry("GET", "/api/2.0/test")
        assert len(RecordingHandler.requests) == 1

    def test_403_maps_to_permission_error(self, connector_with_server):
        connector, _port = connector_with_server
        RecordingHandler.script = [403]
        with pytest.raises(PermissionError):
            connector._request_with_retry("GET", "/api/2.0/test")
        assert len(RecordingHandler.requests) == 1

    def test_400_maps_to_value_error(self, connector_with_server):
        connector, _port = connector_with_server
        RecordingHandler.script = [400]
        with pytest.raises(ValueError, match="Invalid request"):
            connector._request_with_retry("GET", "/api/2.0/test")

    def test_exhausted_500_maps_to_connection_error(self, connector_with_server):
        """Retry budget exhausted → the legacy ConnectionError message."""
        connector, _port = connector_with_server
        RecordingHandler.script = [500, 500, 500]
        with pytest.raises(ConnectionError) as excinfo:
            connector._request_with_retry("GET", "/api/2.0/test")
        assert "Transient Databricks error (500)" in str(excinfo.value)
        assert len(RecordingHandler.requests) == 3

    def test_open_circuit_breaker_fails_fast_without_network(self, connector_with_server):
        """The connector's REAL breaker (low threshold) rejects calls
        without touching the network once it opens."""
        connector, _port = connector_with_server
        connector._circuit_breaker = CircuitBreaker(
            service_name="delegation-open",
            failure_threshold=2,
            timeout_seconds=60,
            success_threshold=1,
        )
        RecordingHandler.script = [500] * 10
        for _ in range(2):
            with pytest.raises(ConnectionError):
                connector._request_with_retry("GET", "/api/2.0/test")
        assert connector._circuit_breaker._get_state() == CircuitBreakerState.OPEN
        hits = len(RecordingHandler.requests)
        with pytest.raises(ConnectionError) as excinfo:
            connector._request_with_retry("GET", "/api/2.0/test")
        assert "Circuit breaker is open" in str(excinfo.value)
        assert len(RecordingHandler.requests) == hits

    def test_runtime_max_retries_mutation_rewires_the_delegate(self, connector_with_server):
        """The pre-1.7 loop read ``max_retries`` PER CALL — a runtime
        mutation must change the retry budget, so the delegate has to be
        re-wired (a build-time snapshot would silently ignore it)."""
        connector, _port = connector_with_server
        RecordingHandler.script = [500, 500, 200]
        connector.max_retries = 1  # 1 retry → 2 total attempts
        with pytest.raises(ConnectionError):
            connector._request_with_retry("GET", "/api/2.0/test")
        # Exhausted after TWO attempts — the mutated budget, not the
        # build-time 3-attempt snapshot (which would have reached the 200).
        assert len(RecordingHandler.requests) == 2
        assert connector._api_client._max_retries == connector.max_retries + 1

    def test_401_maps_to_connection_error(self, connector_with_server):
        """Parity pin: 401 is NOT PermissionError (403's mapping) — the
        legacy mapping treats it as a generic connection error."""
        connector, _port = connector_with_server
        RecordingHandler.script = [401]
        with pytest.raises(ConnectionError) as excinfo:
            connector._request_with_retry("GET", "/api/2.0/test")
        assert "Databricks error (401)" in str(excinfo.value)
        assert len(RecordingHandler.requests) == 1

    def test_exhausted_429_maps_to_transient_connection_error(self, connector_with_server):
        """Parity pin: an exhausted 429 surfaces as the legacy transient
        message (never the client's DatabricksRateLimitError)."""
        connector, _port = connector_with_server
        RecordingHandler.script = [429, 429, 429]
        with pytest.raises(ConnectionError) as excinfo:
            connector._request_with_retry("GET", "/api/2.0/test")
        assert "Transient Databricks error (429)" in str(excinfo.value)
        assert len(RecordingHandler.requests) == 3

    def test_transport_failure_maps_to_network_connection_error(self, connector_with_server):
        """Parity pin: a REAL connection refusal (dead port) exhausts the
        transport retries and surfaces the legacy network message."""
        _connector, _port = connector_with_server
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
        sock.close()
        connector = DatabricksConnector(
            host=f"http://127.0.0.1:{dead_port}", token="dapi-dead-port"
        )
        connector.backoff_factor = 0
        with pytest.raises(ConnectionError) as excinfo:
            connector._request_with_retry("GET", "/api/2.0/test")
        assert "Network error connecting to Databricks" in str(excinfo.value)


class TestDatabricksApiClientDelegationSeams:
    """The client's new delegation surface (task 1.7): raw paths, injected
    transport, breaker-less mode, injected backoff policy."""

    def test_request_path_hits_a_raw_path_without_operation_pinning(self, connector_with_server):
        """``request_path`` is the seam for consumers whose endpoints are
        not version-pinned control-plane operations."""
        _connector, port = connector_with_server
        RecordingHandler.script = [200]
        client = DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            credential_config={"token": "dapi-raw"},
            max_retries=1,
            retry_base_delay=0.01,
            retry_max_delay=0.05,
        )
        response = client.request_path("GET", "/custom/raw/marketplace/path")
        assert response.status_code == 200
        assert RecordingHandler.requests[-1]["path"] == "/custom/raw/marketplace/path"
        client.close()

    def test_injected_transport_and_disabled_breaker(self, connector_with_server):
        """``client=`` + ``use_breaker=False`` — the delegation mode:
        the caller's transport executes, the caller's breaker accounts."""
        _connector, port = connector_with_server
        RecordingHandler.script = [500, 200]
        transport = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5.0)
        attempts: list[int] = []
        client = DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
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
        assert len(RecordingHandler.requests) == 2
        assert attempts == [0]
        client.close()

    def test_injected_backoff_waiter_controls_delays(self, connector_with_server):
        """``backoff_waiter=`` receives each zero-indexed retry attempt —
        the injection point the connector uses for its deterministic
        ``backoff_factor * 2**attempt`` policy."""
        _connector, port = connector_with_server
        attempts: list[int] = []
        RecordingHandler.script = [500, 500, 200]
        client = DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            credential_config={"token": "dapi-x"},
            use_breaker=False,
            max_retries=3,
            backoff_waiter=attempts.append,
        )
        client.request_path("GET", "/x")
        assert attempts == [0, 1]
        client.close()
