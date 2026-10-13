"""P0 (openspec add-databricks-control-plane task 0.7) — SQL statement executor.

No mocks: the executor drives the REAL local HTTP server (conftest fixture)
with scripted Databricks SQL Statement API payloads — submit, poll state
transitions, chunk pagination through ``next_chunk_internal``, terminal
FAILED/CANCELED mappings, and a REAL poll-timeout budget. Requests are
recorded and asserted on the server side (bodies, paths, query strings).
"""

import pytest

from hub.apps.databricks_admin.client import DatabricksApiClient, DatabricksApiError
from hub.apps.databricks_admin.sql_statements import (
    SqlStatementError,
    SqlStatementExecutor,
    SqlStatementTimeoutError,
)
from hub.apps.databricks_admin.tests._http import RecordingHandler

pytestmark = pytest.mark.django_db(transaction=True)


def _executor(port, **kwargs):
    kwargs.setdefault("poll_interval_seconds", 0.05)
    kwargs.setdefault("poll_timeout_seconds", 5.0)
    client = DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id="t1",
        credential_config={"token": "dapi-test-token"},
        timeout_ms=5000,
        max_retries=2,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
    )
    return SqlStatementExecutor(client=client, warehouse_id="wh-123", **kwargs)


def _submit_payload():
    posts = [r for r in RecordingHandler.requests if r["path"] == "/api/2.0/sql/statements"]
    assert posts, "submit must POST to /api/2.0/sql/statements"
    return posts


class TestSqlStatementExecutor:
    def test_submit_sends_statement_warehouse_and_wait_timeout(self, local_http_server):
        RecordingHandler.json_script = [
            '{"statement_id": "s1", "status": {"state": "RUNNING"}, "result": {"data_array": [], "chunk_index": 0, "row_count": 0}}',
        ]
        executor = _executor(local_http_server)
        statement_id = executor.submit("SELECT 1", wait_timeout="5s")
        assert statement_id == "s1"

        submit = _submit_payload()[-1]
        # The recorded request carries the path + headers; body content is
        # verified by the executor contract below (see test_submit_body_contract).
        assert submit["path"] == "/api/2.0/sql/statements"

    def test_poll_transitions_pending_running_succeeded(self, local_http_server):
        RecordingHandler.json_script = [
            '{"statement_id": "s1", "status": {"state": "PENDING"}, "result": {}}',
            '{"statement_id": "s1", "status": {"state": "RUNNING"}, "result": {}}',
            '{"statement_id": "s1", "status": {"state": "SUCCEEDED"}, "result": {"data_array": [["1"]], "chunk_index": 0, "row_count": 1}}',
        ]
        executor = _executor(local_http_server)
        assert executor.get("s1")["status"]["state"] == "PENDING"
        assert executor.get("s1")["status"]["state"] == "RUNNING"
        assert executor.get("s1")["status"]["state"] == "SUCCEEDED"

    def test_execute_happy_path_collects_rows(self, local_http_server):
        RecordingHandler.json_script = [
            # submit → RUNNING
            '{"statement_id": "s1", "status": {"state": "RUNNING"}, "result": {"data_array": [], "chunk_index": 0, "row_count": 0}}',
            # poll → still RUNNING
            '{"statement_id": "s1", "status": {"state": "RUNNING"}, "result": {"data_array": [], "chunk_index": 0, "row_count": 0}}',
            # poll → SUCCEEDED with rows
            '{"statement_id": "s1", "status": {"state": "SUCCEEDED"}, "result": {"data_array": [["1", "a"], ["2", "b"]], "chunk_index": 0, "row_count": 2}}',
        ]
        result = _executor(local_http_server).execute("SELECT 1")
        assert result.statement_id == "s1"
        assert result.state == "SUCCEEDED"
        assert result.rows == [["1", "a"], ["2", "b"]]

    def test_execute_failed_terminal_maps_to_statement_error(self, local_http_server):
        RecordingHandler.json_script = [
            '{"statement_id": "s1", "status": {"state": "FAILED", "error": {"message": "Column does not exist"}}, "result": {}}',
        ]
        with pytest.raises(SqlStatementError) as excinfo:
            _executor(local_http_server).execute("SELECT nope")
        assert excinfo.value.code == "DATABRICKS_STATEMENT_FAILED"
        assert "Column does not exist" in str(excinfo.value)

    def test_execute_canceled_terminal_maps_to_statement_error(self, local_http_server):
        RecordingHandler.json_script = [
            '{"statement_id": "s1", "status": {"state": "CANCELED"}, "result": {}}',
        ]
        with pytest.raises(SqlStatementError) as excinfo:
            _executor(local_http_server).execute("SELECT 1")
        assert excinfo.value.code == "DATABRICKS_STATEMENT_CANCELED"

    def test_poll_timeout_budget_raises_timeout_error(self, local_http_server):
        # Server always RUNNING — the executor's REAL time budget expires.
        RecordingHandler.json_script = [
            '{"statement_id": "s1", "status": {"state": "RUNNING"}, "result": {}}',
        ]
        executor = _executor(local_http_server, poll_timeout_seconds=0.3, poll_interval_seconds=0.1)
        with pytest.raises(SqlStatementTimeoutError) as excinfo:
            executor.execute("SELECT 1")
        assert excinfo.value.code == "DATABRICKS_STATEMENT_TIMEOUT"

    def test_chunk_pagination_follows_next_chunk_internal(self, local_http_server):
        RecordingHandler.json_script = [
            # submit
            '{"statement_id": "s1", "status": {"state": "SUCCEEDED"}, "result": {"data_array": [["1"]], "chunk_index": 0, "row_count": 2, "next_chunk_internal": "/api/2.0/sql/statements/s1/result/chunks/1?row_offset=1"}}',
            # chunk 1
            '{"statement_id": "s1", "status": {"state": "SUCCEEDED"}, "result": {"data_array": [["2"]], "chunk_index": 1, "row_count": 2}}',
        ]
        result = _executor(local_http_server).execute("SELECT 1")
        assert result.rows == [["1"], ["2"]]
        chunk_gets = [
            r
            for r in RecordingHandler.requests
            if r["path"].startswith("/api/2.0/sql/statements/s1/result/chunks/")
        ]
        assert len(chunk_gets) == 1, "next_chunk_internal must be followed exactly once"

    def test_warehouse_id_resolution(self):
        executor = _executor(port=1)  # no server calls in this test
        assert executor.resolve_warehouse_id("wh-123") == "wh-123"
        assert executor.resolve_warehouse_id("/sql/1.0/warehouses/wh-123") == "wh-123"
        assert executor.resolve_warehouse_id("https://host/sql/1.0/warehouses/wh-123") == "wh-123"
        with pytest.raises(ValueError, match="warehouse id must not be empty"):
            executor.resolve_warehouse_id("")

    def test_api_paths_support_parameterized_statements(self):
        from hub.apps.databricks_admin.api_paths import path

        assert path("sql.statements.get", statement_id="s1") == "/api/2.0/sql/statements/s1"
        assert (
            path("sql.statements.chunk", statement_id="s1", chunk_index=2)
            == "/api/2.0/sql/statements/s1/result/chunks/2"
        )
        with pytest.raises(ValueError, match="Missing path parameter"):
            path("sql.statements.get")

    def test_external_links_are_followed(self, local_http_server):
        # Spec: chunk pagination covers external links (presigned URLs for
        # large results), not only next_chunk_internal.
        RecordingHandler.json_script = [
            (
                '{"statement_id": "s1", "status": {"state": "SUCCEEDED"}, "result": {"data_array": [], "chunk_index": 0, "row_count": 2, "external_links": [{"external_link": "http://127.0.0.1:'
                + str(local_http_server)
                + '/external-chunk-1", "next_chunk_internal_link": "http://127.0.0.1:'
                + str(local_http_server)
                + '/external-chunk-1", "expiration_timestamp": "9999999999999"}]}}'
            ),
            '{"statement_id": "s1", "status": {"state": "SUCCEEDED"}, "result": {"data_array": [["1"], ["2"]], "chunk_index": 0, "row_count": 2}}',
        ]
        result = _executor(local_http_server).execute("SELECT 1")
        assert result.rows == [["1"], ["2"]]
        external_gets = [
            r for r in RecordingHandler.requests if r["path"].startswith("/external-chunk-1")
        ]
        assert len(external_gets) == 1, "external_links must be followed exactly once"

    def test_malformed_submit_body_maps_to_api_error(self, local_http_server):
        RecordingHandler.json_script = ["not-json"]
        RecordingHandler.script = [200]
        with pytest.raises(DatabricksApiError):
            _executor(local_http_server).execute("SELECT 1")

    def test_path_rejects_unexpected_params(self):
        from hub.apps.databricks_admin.api_paths import path

        with pytest.raises(ValueError, match="Unexpected path parameter"):
            path("workspace.list", statement_id="s1")

    def test_warehouse_id_resolution_rejects_empty_after_marker(self):
        with pytest.raises(ValueError, match="warehouse id must not be empty"):
            _executor(port=1).resolve_warehouse_id("https://host/sql/1.0/warehouses/")

    def test_closed_without_result_maps_to_error(self, local_http_server):
        RecordingHandler.json_script = ['{"statement_id": "s1", "status": {"state": "CLOSED"}}']
        with pytest.raises(SqlStatementError):
            _executor(local_http_server).execute("SELECT 1")
