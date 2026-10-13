"""TDD pins for the DLT pipelines client (openspec
add-databricks-dlt-pipelines task 10.3) — the CRUD + updates
(full_refresh/refresh_selection) + stop + events/state-polling surface
of the pinned pipelines API (``/api/2.0/pipelines``, all 2.0).

The client rides the PRODUCTION ``DatabricksApiClient`` (retries,
breaker, version-pinned paths) — no mocks: every test drives a REAL
threaded local HTTP server with scripted pipelines envelopes (the
0.5/3.2 convention). The contract pinned here:

- create/get/list/update/delete/updates/stop/events each hit their
  exact version-pinned path (``api_paths.py``, all 2.0).
- create ships the caller's settings EXACTLY and returns the response's
  pipeline id; update/delete/stop tolerate the API's legitimate
  empty-body 200.
- start_update ships ``full_refresh``/``refresh_selection`` exactly and
  returns the update id; the poll loop terminates ONLY on the API's
  terminal states and raises the poll-budget sentinel on timeout (the
  4.4 convention — no new catalogue code).
- Shape discipline: wrong TYPES raise TypeError, wrong VALUES raise
  ValueError (the repo's boundary convention) — always BEFORE any
  network call (pinned with ``RecordingHandler.requests == []``).
- Malformed/non-object 2xx bodies are classified ``DatabricksApiError``
  (the 0.7 discipline).

Pure-transport suite: the client performs ZERO ORM work (the caller
owns the client — the 3.2 mirror contract), so there is deliberately NO
``django_db`` mark.
"""

import json
from pathlib import Path

import pytest

from hub.apps.databricks_admin.tests._http import RecordingHandler

REPO_ROOT = Path(__file__).resolve().parents[4]


def _client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.pipelines_client import DatabricksPipelinesClient

    return DatabricksPipelinesClient(
        DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id="t1",
            credential_config={"token": "dapi-pipelines"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
        )
    )


def _server():
    import http.server
    import threading

    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return port, server, thread


@pytest.fixture
def served():
    port, server, thread = _server()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestApiPathPins:
    """The pipelines surface pins — one place, all 2.0, import-time
    validated."""

    def test_every_pipelines_operation_is_pinned_and_versioned(self):
        from hub.apps.databricks_admin.api_paths import API_PATH_VERSIONS, API_PATHS

        expected = {
            "pipelines.create": "/api/2.0/pipelines",
            "pipelines.list": "/api/2.0/pipelines",
            "pipelines.get": "/api/2.0/pipelines/{pipeline_id}",
            "pipelines.update": "/api/2.0/pipelines/{pipeline_id}",
            "pipelines.delete": "/api/2.0/pipelines/{pipeline_id}",
            "pipelines.updates.start": "/api/2.0/pipelines/{pipeline_id}/updates",
            "pipelines.updates.list": "/api/2.0/pipelines/{pipeline_id}/updates",
            "pipelines.updates.get": "/api/2.0/pipelines/{pipeline_id}/updates/{update_id}",
            "pipelines.stop": "/api/2.0/pipelines/{pipeline_id}/stop",
            "pipelines.events.list": "/api/2.0/pipelines/{pipeline_id}/events",
        }
        for operation, path in expected.items():
            assert API_PATHS.get(operation) == path, f"{operation} must pin {path}"
            assert API_PATH_VERSIONS.get(operation) == "2.0", (
                f"{operation} must document the 2.0 version (the import-time "
                "validate_version_pins guard)"
            )


class TestCreateGetListUpdateDelete:
    def test_create_ships_the_settings_and_returns_the_pipeline_id(self, served):
        RecordingHandler.json_script.append(json.dumps({"pipeline_id": "p-1"}))
        client = _client(served)
        settings = {"name": "nightly-dlt", "edition": "CORE", "continuous": False}
        pipeline_id = client.create_pipeline(settings)
        assert pipeline_id == "p-1"
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.0/pipelines"
        assert json.loads(recorded["body"]) == settings, (
            "the caller's settings ship EXACTLY (the 10.4 chain validates them first)"
        )

    def test_create_shape_discipline_runs_before_any_call(self, served):
        client = _client(served)
        with pytest.raises(TypeError):
            client.create_pipeline("not-a-dict")
        with pytest.raises(ValueError, match="non-empty"):
            client.create_pipeline({})
        assert RecordingHandler.requests == [], (
            "wrong shapes are refused BEFORE any pipelines API call"
        )

    def test_list_returns_the_statuses_array(self, served):
        RecordingHandler.json_script.append(
            json.dumps({"statuses": [{"pipeline_id": "p-1", "state": "IDLE"}]})
        )
        client = _client(served)
        statuses = client.list_pipelines()
        assert statuses == [{"pipeline_id": "p-1", "state": "IDLE"}]
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "GET"
        assert recorded["path"] == "/api/2.0/pipelines"

    def test_a_non_list_statuses_field_is_classified(self, served):
        RecordingHandler.json_script.append(json.dumps({"statuses": "bogus"}))
        client = _client(served)
        from hub.apps.databricks_admin.client import DatabricksApiError

        with pytest.raises(DatabricksApiError):
            client.list_pipelines()

    def test_get_uses_the_path_id(self, served):
        RecordingHandler.json_script.append(
            json.dumps({"pipeline_id": "p-1", "spec": {"name": "nightly-dlt"}, "state": "IDLE"})
        )
        client = _client(served)
        payload = client.get_pipeline("p-1")
        assert payload["state"] == "IDLE"
        recorded = RecordingHandler.requests[-1]
        assert recorded["path"] == "/api/2.0/pipelines/p-1"

    def test_update_is_empty_tolerant(self, served):
        RecordingHandler.json_script.append("")
        client = _client(served)
        client.update_pipeline("p-1", {"name": "renamed"})
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "PUT"
        assert recorded["path"] == "/api/2.0/pipelines/p-1"
        assert json.loads(recorded["body"]) == {"name": "renamed"}

    def test_delete_is_empty_tolerant(self, served):
        RecordingHandler.json_script.append("")
        client = _client(served)
        client.delete_pipeline("p-1")
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "DELETE"
        assert recorded["path"] == "/api/2.0/pipelines/p-1"

    def test_a_non_object_read_body_is_classified(self, served):
        RecordingHandler.json_script.append(json.dumps(["not-an-object"]))
        client = _client(served)
        from hub.apps.databricks_admin.client import DatabricksApiError

        with pytest.raises(DatabricksApiError):
            client.get_pipeline("p-1")


class TestUpdates:
    def test_start_ships_the_refresh_semantics_and_returns_the_update_id(self, served):
        RecordingHandler.json_script.append(json.dumps({"update_id": "u-1"}))
        client = _client(served)
        update_id = client.start_update(
            "p-1", full_refresh=True, refresh_selection={"tables": ["bronze_customers"]}
        )
        assert update_id == "u-1"
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.0/pipelines/p-1/updates"
        assert json.loads(recorded["body"]) == {
            "full_refresh": True,
            "refresh_selection": {"tables": ["bronze_customers"]},
        }, "the API's documented {tables, files} object ships verbatim"

    def test_start_without_a_selection_ships_a_plain_full_refresh(self, served):
        RecordingHandler.json_script.append(json.dumps({"update_id": "u-2"}))
        client = _client(served)
        client.start_update("p-1", full_refresh=False)
        recorded = RecordingHandler.requests[-1]
        assert json.loads(recorded["body"]) == {"full_refresh": False}

    def test_start_shape_discipline_runs_before_any_call(self, served):
        client = _client(served)
        with pytest.raises(TypeError):
            client.start_update("p-1", full_refresh="yes")
        with pytest.raises(ValueError, match="non-empty"):
            client.start_update("p-1", refresh_selection={})
        with pytest.raises(TypeError):
            client.start_update("p-1", refresh_selection="not-an-object")
        assert RecordingHandler.requests == [], "wrong shapes are refused BEFORE any call"

    def test_get_update_and_list_updates_hit_their_paths(self, served):
        RecordingHandler.json_script.append(
            json.dumps({"update_id": "u-1", "state": "COMPLETED", "full_refresh": True})
        )
        RecordingHandler.json_script.append(json.dumps({"updates": []}))
        client = _client(served)
        payload = client.get_update("p-1", "u-1")
        assert payload["state"] == "COMPLETED"
        assert RecordingHandler.requests[-1]["path"] == "/api/2.0/pipelines/p-1/updates/u-1"
        updates = client.list_updates("p-1")
        assert updates == []
        recorded = RecordingHandler.requests[-1]
        assert recorded["path"] == "/api/2.0/pipelines/p-1/updates"
        assert recorded["method"] == "GET"

    def test_list_updates_passes_the_page_token(self, served):
        RecordingHandler.json_script.append(json.dumps({"updates": []}))
        client = _client(served)
        client.list_updates("p-1", page_token="tok-9")
        assert "page_token=tok-9" in RecordingHandler.requests[-1]["path"]


class TestStopEventsPoll:
    def test_stop_is_empty_tolerant(self, served):
        RecordingHandler.json_script.append("")
        client = _client(served)
        client.stop_pipeline("p-1")
        recorded = RecordingHandler.requests[-1]
        assert recorded["method"] == "POST"
        assert recorded["path"] == "/api/2.0/pipelines/p-1/stop"

    def test_list_events_returns_the_events_array(self, served):
        RecordingHandler.json_script.append(
            json.dumps({"events": [{"event_type": "update_progress"}]})
        )
        client = _client(served)
        events = client.list_events("p-1")
        assert events == [{"event_type": "update_progress"}]
        assert RecordingHandler.requests[-1]["path"] == "/api/2.0/pipelines/p-1/events"

    def test_poll_update_returns_the_terminal_payload(self, served):
        RecordingHandler.json_script.append(json.dumps({"update_id": "u-1", "state": "RUNNING"}))
        RecordingHandler.json_script.append(json.dumps({"update_id": "u-1", "state": "COMPLETED"}))
        client = _client(served)
        payload = client.poll_update("p-1", "u-1", timeout_seconds=5.0, interval_seconds=0.0)
        assert payload["state"] == "COMPLETED"
        assert len(RecordingHandler.requests) == 2, "the poll stops exactly at the terminal state"

    def test_poll_returns_immediately_on_an_already_terminal_update(self, served):
        RecordingHandler.json_script.append(json.dumps({"update_id": "u-1", "state": "FAILED"}))
        client = _client(served)
        payload = client.poll_update("p-1", "u-1", timeout_seconds=5.0, interval_seconds=0.0)
        assert payload["state"] == "FAILED"
        assert len(RecordingHandler.requests) == 1

    def test_poll_budget_exhaustion_raises_the_sentinel(self, served):
        # Pre-fill the body queue so EVERY poll answer is RUNNING (the
        # interval is 0.0 and each round-trip is real — the script must
        # outlive the budget, else the dry default body would read a
        # None state).
        RecordingHandler.json_script.extend(
            [json.dumps({"update_id": "u-1", "state": "RUNNING"})] * 200
        )
        client = _client(served)
        from hub.apps.databricks_admin.pipelines_client import _PollBudgetExhausted

        with pytest.raises(_PollBudgetExhausted) as excinfo:
            client.poll_update("p-1", "u-1", timeout_seconds=0.05, interval_seconds=0.0)
        assert "poll budget exhausted" in str(excinfo.value)
        assert excinfo.value.last_state == "RUNNING"

    def test_poll_shape_discipline_runs_before_any_call(self, served):
        client = _client(served)
        with pytest.raises(ValueError, match="positive"):
            client.poll_update("p-1", "u-1", timeout_seconds=0, interval_seconds=0.0)
        with pytest.raises(ValueError, match="non-negative"):
            client.poll_update("p-1", "u-1", timeout_seconds=5.0, interval_seconds=-1)
        assert RecordingHandler.requests == []
