"""P8 (openspec add-databricks-account-plane task 8.3, design D4) — the
DatabricksAccountClient battery.

The account client speaks the ACCOUNT host API
(``https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/...``)
with account operations ONLY — metastore create/list + workspace create
— built from the shared resilience primitives (the circuit breaker +
deterministic backoff, Appendix B) with PAT bearer auth from the account
credential. The workspace-side ``DatabricksApiClient`` is untouched.

No mocks: every pin drives the PRODUCTION client over a REAL threaded
local HTTP server (the ``_http.py`` RecordingHandler convention) whose
scripted bodies are the account API's envelope shapes; transport failures
use a REAL unreachable socket. Each test uses a FRESH account id — the
shared breaker keys its channel on the account id, so per-test ids give
per-test breaker isolation (the same isolation production gets per
account).
"""

import pytest

from hub.apps.databricks_admin.client import (
    DatabricksApiError,
    DatabricksAuthError,
    DatabricksConnectionError,
    DatabricksRateLimitError,
    DatabricksServerError,
    DatabricksUnavailableError,
)
from hub.apps.databricks_admin.tests._http import RecordingHandler

TOKEN = "dapi-account-token"


@pytest.fixture
def local_account_server():
    """A real local HTTP server on an ephemeral port (no mocks)."""
    import http.server
    import threading

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


@pytest.fixture
def account_id():
    """A fresh account id per test (see the module docstring)."""
    import uuid

    return str(uuid.uuid4())


def _client(port, *, account_id, **kwargs):
    from hub.apps.databricks_admin.account_client import DatabricksAccountClient

    defaults = {
        "account_id": account_id,
        "credential_config": {"token": TOKEN},
        "base_url": f"http://127.0.0.1:{port}",
        "retry_base_delay": 0.01,
        "retry_max_delay": 0.02,
    }
    defaults.update(kwargs)
    return DatabricksAccountClient(**defaults)


def _metastores_path(account_id: str) -> str:
    return f"/api/2.0/accounts/{account_id}/metastores"


def _workspaces_path(account_id: str) -> str:
    return f"/api/2.0/accounts/{account_id}/workspaces"


class TestMetastoreOps:
    def test_create_metastore_hits_the_pinned_account_path(self, local_account_server, account_id):
        RecordingHandler.json_script = [
            '{"metastore_id": "ms-1", "name": "meshant-shared", "region": "us-east-1"}',
        ]
        client = _client(local_account_server, account_id=account_id)
        result = client.create_metastore(
            "meshant-shared", "us-east-1", storage_root="s3://meshant/metastore"
        )

        assert result["metastore_id"] == "ms-1"
        recorded = RecordingHandler.requests
        assert len(recorded) == 1, "exactly one account-API call"
        request = recorded[0]
        assert request["method"] == "POST"
        assert request["path"] == _metastores_path(account_id), "the version-pinned account path"
        assert request["headers"]["Authorization"] == f"Bearer {TOKEN}"
        import json

        sent = json.loads(request["body"])
        assert sent == {
            "name": "meshant-shared",
            "region": "us-east-1",
            "storage_root": "s3://meshant/metastore",
        }, "the envelope carries exactly the given fields"

    def test_list_metastores_hits_the_pinned_account_path(self, local_account_server, account_id):
        RecordingHandler.json_script = [
            '{"metastores": [{"metastore_id": "ms-1"}, {"metastore_id": "ms-2"}]}',
        ]
        client = _client(local_account_server, account_id=account_id)
        result = client.list_metastores()

        assert [m["metastore_id"] for m in result] == ["ms-1", "ms-2"]
        recorded = RecordingHandler.requests
        assert len(recorded) == 1
        assert recorded[0]["method"] == "GET"
        assert recorded[0]["path"] == _metastores_path(account_id)

    def test_empty_metastore_name_is_refused_before_any_network(
        self, local_account_server, account_id
    ):
        client = _client(local_account_server, account_id=account_id)
        with pytest.raises(ValueError, match="metastore name is required"):
            client.create_metastore("", "us-east-1")

        assert RecordingHandler.requests == [], "shape discipline before any network call"


class TestWorkspaceProvisioning:
    def test_create_workspace_hits_the_pinned_account_path(self, local_account_server, account_id):
        RecordingHandler.json_script = [
            '{"workspace_id": 7000000000000001, "workspace_name": "meshant-ws", '
            '"deployment_name": "dbc-xyz", "workspace_url": "https://dbc-xyz.cloud.databricks.com", '
            '"workspace_status": "PROVISIONING"}',
        ]
        client = _client(local_account_server, account_id=account_id)
        result = client.create_workspace(
            "meshant-ws",
            deployment_name="dbc-xyz",
            aws_region="us-east-1",
            pricing_tier="ENTERPRISE",
        )

        assert result["workspace_id"] == 7000000000000001
        assert result["workspace_url"] == "https://dbc-xyz.cloud.databricks.com"
        recorded = RecordingHandler.requests
        assert len(recorded) == 1
        request = recorded[0]
        assert request["method"] == "POST"
        assert request["path"] == _workspaces_path(account_id)
        import json

        sent = json.loads(request["body"])
        assert sent == {
            "workspace_name": "meshant-ws",
            "deployment_name": "dbc-xyz",
            "aws_region": "us-east-1",
            "pricing_tier": "ENTERPRISE",
        }

    def test_empty_workspace_name_is_refused_before_any_network(
        self, local_account_server, account_id
    ):
        client = _client(local_account_server, account_id=account_id)
        with pytest.raises(ValueError, match="workspace_name is required"):
            client.create_workspace("")

        assert RecordingHandler.requests == [], "shape discipline before any network call"


class TestErrorClassification:
    def test_401_is_classified_and_never_retried(self, local_account_server, account_id):
        RecordingHandler.script = [401]
        client = _client(local_account_server, account_id=account_id)
        with pytest.raises(DatabricksAuthError) as excinfo:
            client.list_metastores()

        assert excinfo.value.code == "DATABRICKS_AUTH_FAILED"
        assert len(RecordingHandler.requests) == 1, "auth rejections are terminal — no retry"

    def test_429_retries_with_backoff_then_succeeds(self, local_account_server, account_id):
        RecordingHandler.script = [429, 200]
        RecordingHandler.json_script = ["{}", '{"metastores": [{"metastore_id": "ms-1"}]}']
        client = _client(local_account_server, account_id=account_id)
        result = client.list_metastores()

        assert result[0]["metastore_id"] == "ms-1"
        assert len(RecordingHandler.requests) == 2, "one retry for a transient 429"

    def test_retry_budget_exhausted_raises_rate_limit(self, local_account_server, account_id):
        RecordingHandler.script = [429, 429, 429]
        client = _client(local_account_server, account_id=account_id, max_retries=3)
        with pytest.raises(DatabricksRateLimitError) as excinfo:
            client.list_metastores()

        assert excinfo.value.status_code == 429
        assert len(RecordingHandler.requests) == 3, "exactly the retry budget"

    def test_5xx_exhaustion_raises_server_error(self, local_account_server, account_id):
        RecordingHandler.script = [503, 503, 503]
        client = _client(local_account_server, account_id=account_id, max_retries=3)
        with pytest.raises(DatabricksServerError) as excinfo:
            client.list_metastores()

        assert excinfo.value.status_code == 503

    def test_transport_failure_raises_connection_error(self, account_id):
        # A REAL unreachable socket — port 1 never answers.
        client = _client(
            1, account_id=account_id, max_retries=2, retry_base_delay=0.01, retry_max_delay=0.02
        )
        with pytest.raises(DatabricksConnectionError):
            client.list_metastores()

    def test_missing_token_raises_before_any_network(self, local_account_server, account_id):
        client = _client(local_account_server, account_id=account_id, credential_config={})
        with pytest.raises(DatabricksAuthError):
            client.list_metastores()

        assert RecordingHandler.requests == [], "no token, no network"

    def test_breaker_open_fails_fast_without_network(self, local_account_server, account_id):
        client = _client(
            local_account_server,
            account_id=account_id,
            breaker_failure_threshold=1,
            max_retries=1,  # a single attempt — the trip must not mask the classification
        )
        RecordingHandler.script = [503]
        with pytest.raises(DatabricksServerError):
            client.list_metastores()  # first failure trips the threshold-1 breaker
        RecordingHandler.script = [200]
        RecordingHandler.json_script = ['{"metastores": []}']
        with pytest.raises(DatabricksUnavailableError):
            client.list_metastores()  # the OPEN breaker fails fast — no network
        assert len(RecordingHandler.requests) == 1, "the second call never reached the wire"

    def test_malformed_body_raises_classified_error(self, local_account_server, account_id):
        RecordingHandler.json_script = ["not-json{{{"]
        client = _client(local_account_server, account_id=account_id)
        with pytest.raises(DatabricksApiError):
            client.list_metastores()


class TestAccountOpsOnly:
    def test_the_client_exposes_only_account_operations(self):
        from hub.apps.databricks_admin.account_client import DatabricksAccountClient

        public_ops = {
            name
            for name in dir(DatabricksAccountClient)
            if not name.startswith("_") and callable(getattr(DatabricksAccountClient, name))
        }
        assert public_ops <= {
            "create_metastore",
            "list_metastores",
            "create_workspace",
            # Phase 9 (task 9.2) — the sandbox lifecycle extension: still
            # ACCOUNT operations ONLY (list/delete on the account's own
            # resources), never workspace-level or UC surfaces.
            "list_workspaces",
            "delete_workspace",
            "delete_metastore",
            "request",
            "close",
        }, "account ops ONLY — no workspace/UC/jobs operations leak onto this client"
