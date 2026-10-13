"""TDD pins for the SQL warehouse compute client (openspec
add-databricks-sql-warehouses task 3.3) — the CRUD + start/stop surface
of the pinned compute API (`/api/2.0/sql/warehouses`, 2.0).

The client rides the PRODUCTION ``DatabricksApiClient`` (retries,
breaker, version-pinned paths) — no mocks: every test drives a REAL
threaded local HTTP server with scripted compute envelopes (the 0.5/3.2
convention). The contract pinned here:

- list/get/create/update/delete/start/stop each hit their exact
  version-pinned path (``api_paths.py``).
- ``serverless`` + ``auto_stop_mins`` are first-class payload fields —
  a create sends them EXACTLY (the spec scenario), a classic create
  carries the size tier instead.
- Start/stop are idempotent-state aware: START on a RUNNING (or
  STARTING) warehouse is a no-op success, STOP on a STOPPED/STOPPING/
  DELETING warehouse is a no-op success — the spec scenario.
- Workspace rejections propagate the classified ``Databricks*Error``
  family; the Hub's OWN state failures (unknown/missing states, START
  on DELETING) carry ``DATABRICKS_WAREHOUSE_STATE_ERROR``.
- Shape violations (serverless+size contradictions, classic without a
  size, non-positive auto-stop) fail with ValueError and ZERO network
  calls.

Pure-transport suite: the client performs ZERO ORM work (the caller owns
the client — the 3.2 mirror contract), so there is deliberately NO
``django_db`` mark — no test-DB setup, no per-test truncation on the
shared database. A future test that touches the DB must add the mark.
"""

import json
from pathlib import Path

import pytest

from hub.apps.databricks_admin.tests._http import RecordingHandler

REPO_ROOT = Path(__file__).resolve().parents[4]


def _compute_client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.sql_warehouse_client import DatabricksComputeClient

    return DatabricksComputeClient(
        DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id="t1",
            credential_config={"token": "dapi-wh"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
        )
    )


def _warehouse_payload(warehouse_id="wh-1", state="RUNNING", **extra):
    payload = {
        "id": warehouse_id,
        "name": "etl-warehouse",
        "state": state,
        "serverless": True,
        "auto_stop_mins": 30,
    }
    payload.update(extra)
    return payload


class TestComputeApiPaths:
    """Every 3.3 operation resolves to its exact version-pinned path."""

    def test_every_operation_is_version_pinned_2_0(self):
        from hub.apps.databricks_admin.api_paths import API_PATH_VERSIONS, API_PATHS, path

        expected = {
            "sql.warehouses.list": "/api/2.0/sql/warehouses",
            "sql.warehouses.get": "/api/2.0/sql/warehouses/wh-1",
            "sql.warehouses.create": "/api/2.0/sql/warehouses",
            "sql.warehouses.update": "/api/2.0/sql/warehouses/wh-1",
            "sql.warehouses.delete": "/api/2.0/sql/warehouses/wh-1",
            "sql.warehouses.start": "/api/2.0/sql/warehouses/wh-1/start",
            "sql.warehouses.stop": "/api/2.0/sql/warehouses/wh-1/stop",
        }
        for operation, pinned in expected.items():
            # Key the params on the TEMPLATE (the API_PATHS entry still
            # carries the {warehouse_id} placeholder — the expected value
            # is already formatted).
            params = {"warehouse_id": "wh-1"} if "{warehouse_id}" in API_PATHS[operation] else {}
            assert path(operation, **params) == pinned, operation
            assert API_PATH_VERSIONS.get(operation) == "2.0", operation


class TestComputeClientReads:
    """list/get ride the pinned path with the 0.7 JSON discipline."""

    def test_list_returns_the_warehouse_array(self, local_http_server):
        RecordingHandler.json_script = [
            json.dumps({"warehouses": [_warehouse_payload(), _warehouse_payload("wh-2")]})
        ]
        result = _compute_client(local_http_server).list()
        assert [row["id"] for row in result] == ["wh-1", "wh-2"]

        request = RecordingHandler.requests[-1]
        assert request["method"] == "GET"
        assert request["path"] == "/api/2.0/sql/warehouses"

    def test_list_classifies_non_object_bodies(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.json_script = ["[1, 2]"]
        with pytest.raises(DatabricksApiError):
            _compute_client(local_http_server).list()

    def test_list_classifies_non_list_warehouses(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.json_script = [json.dumps({"warehouses": "not-a-list"})]
        with pytest.raises(DatabricksApiError):
            _compute_client(local_http_server).list()

    def test_get_returns_the_warehouse_payload(self, local_http_server):
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="STOPPED"))]
        result = _compute_client(local_http_server).get("wh-1")
        assert result["id"] == "wh-1"
        assert result["state"] == "STOPPED"

        request = RecordingHandler.requests[-1]
        assert request["method"] == "GET"
        assert request["path"] == "/api/2.0/sql/warehouses/wh-1"

    def test_get_classifies_non_json_bodies(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.json_script = ["not-json"]
        with pytest.raises(DatabricksApiError):
            _compute_client(local_http_server).get("wh-1")

    def test_get_404_propagates_classified(self, local_http_server):
        # A workspace rejection on a READ surface propagates the
        # classified family (400-family, never retried, never raw).
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.script = [404]
        with pytest.raises(DatabricksApiError) as excinfo:
            _compute_client(local_http_server).get("wh-missing")
        assert excinfo.value.status_code == 404
        assert len(RecordingHandler.requests) == 1

    def test_list_retries_a_transient_500_through_the_surface(self, local_http_server):
        # The compute surface rides the production client's retry loop:
        # a transient 500 then success → the payload arrives, exactly
        # two requests.
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.sql_warehouse_client import DatabricksComputeClient

        client = DatabricksComputeClient(
            DatabricksApiClient(
                base_url=f"http://127.0.0.1:{local_http_server}",
                tenant_id="t1",
                credential_config={"token": "dapi-wh"},
                timeout_ms=5000,
                max_retries=2,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
            )
        )
        RecordingHandler.script = [500, 200]
        # RecordingHandler pops json_script per request REGARDLESS of
        # status (the 0.11 review note) — the 500 consumes one body.
        RecordingHandler.json_script = [
            json.dumps({}),
            json.dumps({"warehouses": [_warehouse_payload()]}),
        ]
        result = client.list()
        assert [row["id"] for row in result] == ["wh-1"]
        assert len(RecordingHandler.requests) == 2, "the transient 500 must be retried"

    def test_empty_warehouse_ids_are_rejected_before_any_call(self, local_http_server):
        # An empty id would format into /api/2.0/sql/warehouses/ — a
        # silently wrong URL (the 0.7 resolve_warehouse_id discipline).
        # Whitespace-only ids are the same trap.
        client = _compute_client(local_http_server)
        for call in (
            lambda: client.get(""),
            lambda: client.update("", auto_stop_mins=30),
            lambda: client.delete(""),
            lambda: client.start(""),
            lambda: client.stop(""),
            lambda: client.get("   "),
        ):
            with pytest.raises(ValueError, match="warehouse id"):
                call()
        assert RecordingHandler.requests == []


class TestComputeClientCreate:
    """create() — the spec scenario: serverless + auto-stop ship exactly."""

    def test_create_sends_serverless_and_auto_stop_exactly(self, local_http_server):
        # Spec scenario: create with serverless:true + auto_stop_mins:30 →
        # the compute API receives those EXACT fields and the response's
        # warehouse id is returned.
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload("wh-new", name="etl-serverless"))
        ]
        result = _compute_client(local_http_server).create(
            name="etl-serverless", serverless=True, auto_stop_mins=30
        )
        assert result == "wh-new"

        request = RecordingHandler.requests[-1]
        assert request["method"] == "POST"
        assert request["path"] == "/api/2.0/sql/warehouses"
        assert request["headers"]["Authorization"] == "Bearer dapi-wh"
        assert json.loads(request["body"]) == {
            "name": "etl-serverless",
            "serverless": True,
            "auto_stop_mins": 30,
        }

    def test_create_classic_carries_the_size_tier(self, local_http_server):
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload("wh-c", serverless=False, size="L"))
        ]
        result = _compute_client(local_http_server).create(
            name="etl-classic", serverless=False, size="L", auto_stop_mins=60
        )
        assert result == "wh-c"
        assert json.loads(RecordingHandler.requests[-1]["body"]) == {
            "name": "etl-classic",
            "serverless": False,
            "size": "L",
            "auto_stop_mins": 60,
        }

    def test_create_rejects_serverless_with_a_size(self, local_http_server):
        # A serverless warehouse has no size tier — the mirror invariant
        # (serverless rows carry NULL size) must not be contradicted at
        # the write boundary. ValueError BEFORE any network call.
        with pytest.raises(ValueError, match="serverless"):
            _compute_client(local_http_server).create(
                name="etl", serverless=True, size="L", auto_stop_mins=30
            )
        assert RecordingHandler.requests == [], "shape violations must never reach the network"

    def test_create_rejects_classic_without_a_size(self, local_http_server):
        # A MISSING size is a value problem; a wrong-typed size is a
        # type problem — both refuse BEFORE any network call.
        with pytest.raises(ValueError, match="classic"):
            _compute_client(local_http_server).create(
                name="etl", serverless=False, auto_stop_mins=30
            )
        with pytest.raises(TypeError, match="size"):
            _compute_client(local_http_server).create(
                name="etl",
                serverless=False,
                size=5,  # type: ignore[arg-type] — negative pin
                auto_stop_mins=30,
            )
        assert RecordingHandler.requests == []

    def test_create_rejects_non_positive_auto_stop(self, local_http_server):
        for bad in (0, -5):
            with pytest.raises(ValueError, match="positive"):
                _compute_client(local_http_server).create(
                    name="etl", serverless=True, auto_stop_mins=bad
                )
        assert RecordingHandler.requests == []

    def test_create_rejects_non_integer_auto_stop(self, local_http_server):
        # Wrong TYPES raise TypeError (the repo's boundary convention) —
        # including bools, which would otherwise smuggle through the
        # int isinstance check.
        for bad in ("30", 3.5, True):
            with pytest.raises(TypeError, match="integer"):
                _compute_client(local_http_server).create(
                    name="etl",
                    serverless=True,
                    auto_stop_mins=bad,  # type: ignore[arg-type] — negative pin
                )
        assert RecordingHandler.requests == []

    def test_create_rejects_blank_names(self, local_http_server):
        for bad_name in ("", "   "):
            with pytest.raises(ValueError, match="non-empty"):
                _compute_client(local_http_server).create(
                    name=bad_name, serverless=True, auto_stop_mins=30
                )
        assert RecordingHandler.requests == []

    def test_create_classifies_non_object_responses(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.json_script = ["[1, 2]"]
        with pytest.raises(DatabricksApiError):
            _compute_client(local_http_server).create(
                name="etl", serverless=True, auto_stop_mins=30
            )

    def test_create_classifies_a_missing_id(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.json_script = [json.dumps({"state": "RUNNING"})]
        with pytest.raises(DatabricksApiError):
            _compute_client(local_http_server).create(
                name="etl", serverless=True, auto_stop_mins=30
            )

    def test_create_classifies_a_whitespace_only_id(self, local_http_server):
        # A whitespace-only id must never be returned as the warehouse
        # identity (the mirror would store it verbatim).
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.json_script = [json.dumps({"id": "   ", "state": "RUNNING"})]
        with pytest.raises(DatabricksApiError):
            _compute_client(local_http_server).create(
                name="etl", serverless=True, auto_stop_mins=30
            )

    def test_create_classifies_non_json_responses(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.json_script = ["oops"]
        with pytest.raises(DatabricksApiError):
            _compute_client(local_http_server).create(
                name="etl", serverless=True, auto_stop_mins=30
            )

    def test_create_workspace_rejection_propagates_classified(self, local_http_server):
        # Workspace rejections propagate the client's classified family —
        # never a raw status code.
        from hub.apps.databricks_admin.client import DatabricksAuthError

        RecordingHandler.script = [401]
        with pytest.raises(DatabricksAuthError):
            _compute_client(local_http_server).create(
                name="etl", serverless=True, auto_stop_mins=30
            )


class TestComputeClientUpdate:
    """update() — PATCH semantics: only the given fields ship."""

    def test_update_patches_only_the_given_fields(self, local_http_server):
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(auto_stop_mins=45))]
        result = _compute_client(local_http_server).update("wh-1", auto_stop_mins=45)
        assert result["auto_stop_mins"] == 45

        request = RecordingHandler.requests[-1]
        assert request["method"] == "PATCH"
        assert request["path"] == "/api/2.0/sql/warehouses/wh-1"
        assert json.loads(request["body"]) == {"auto_stop_mins": 45}

    def test_update_requires_at_least_one_field(self, local_http_server):
        with pytest.raises(ValueError, match="at least one"):
            _compute_client(local_http_server).update("wh-1")
        assert RecordingHandler.requests == []

    def test_update_rejects_a_serverless_size_contradiction(self, local_http_server):
        with pytest.raises(ValueError, match="serverless"):
            _compute_client(local_http_server).update("wh-1", serverless=True, size="L")
        assert RecordingHandler.requests == []

    def test_update_rejects_non_positive_auto_stop(self, local_http_server):
        with pytest.raises(ValueError, match="positive"):
            _compute_client(local_http_server).update("wh-1", auto_stop_mins=-1)
        assert RecordingHandler.requests == []

    def test_update_rejects_non_integer_auto_stop(self, local_http_server):
        with pytest.raises(TypeError, match="integer"):
            _compute_client(local_http_server).update(
                "wh-1",
                auto_stop_mins="45",  # type: ignore[arg-type] — negative pin
            )
        assert RecordingHandler.requests == []

    def test_update_tolerates_an_empty_body(self, local_http_server):
        # The compute API's edit endpoint may answer 200 with no body —
        # that is a successful update, never a parse crash.
        RecordingHandler.json_script = [""]
        assert _compute_client(local_http_server).update("wh-1", name="renamed") == {}

    def test_update_tolerates_a_null_body(self, local_http_server):
        RecordingHandler.json_script = ["null"]
        assert _compute_client(local_http_server).update("wh-1", name="renamed") == {}

    def test_update_workspace_rejection_propagates_classified(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksAuthError

        RecordingHandler.script = [401]
        with pytest.raises(DatabricksAuthError):
            _compute_client(local_http_server).update("wh-1", auto_stop_mins=45)


class TestComputeClientDelete:
    """delete() — the pinned path; no body expected back."""

    def test_delete_hits_the_pinned_path(self, local_http_server):
        RecordingHandler.json_script = [""]
        assert _compute_client(local_http_server).delete("wh-1") is None

        request = RecordingHandler.requests[-1]
        assert request["method"] == "DELETE"
        assert request["path"] == "/api/2.0/sql/warehouses/wh-1"


class TestComputeClientStartStop:
    """Idempotent-state aware start/stop (the spec scenario)."""

    def test_start_on_running_is_a_no_op(self, local_http_server):
        # Spec scenario: START on a RUNNING warehouse → no-op success.
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="RUNNING"))]
        assert _compute_client(local_http_server).start("wh-1") is None
        assert len(RecordingHandler.requests) == 1
        assert RecordingHandler.requests[0]["method"] == "GET"
        assert RecordingHandler.requests[0]["path"] == "/api/2.0/sql/warehouses/wh-1"

    def test_start_on_starting_is_a_no_op(self, local_http_server):
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="STARTING"))]
        assert _compute_client(local_http_server).start("wh-1") is None
        assert len(RecordingHandler.requests) == 1

    def test_stop_on_stopped_is_a_no_op(self, local_http_server):
        # Spec scenario: STOP on a STOPPED warehouse → no-op success.
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="STOPPED"))]
        assert _compute_client(local_http_server).stop("wh-1") is None
        assert len(RecordingHandler.requests) == 1

    def test_stop_on_stopping_is_a_no_op(self, local_http_server):
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="STOPPING"))]
        assert _compute_client(local_http_server).stop("wh-1") is None
        assert len(RecordingHandler.requests) == 1

    def test_stop_on_deleting_is_a_no_op(self, local_http_server):
        # The desired end state (not running) is already being reached.
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="DELETING"))]
        assert _compute_client(local_http_server).stop("wh-1") is None
        assert len(RecordingHandler.requests) == 1

    def test_start_on_stopped_posts_start(self, local_http_server):
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload(state="STOPPED")),
            "",  # the start endpoint answers 200 with no body
        ]
        result = _compute_client(local_http_server).start("wh-1")
        assert result == {}

        requests = RecordingHandler.requests
        assert [r["method"] for r in requests] == ["GET", "POST"]
        assert requests[1]["path"] == "/api/2.0/sql/warehouses/wh-1/start"
        assert requests[1]["body"] == "", "the start endpoint takes NO request body"

    def test_stop_on_running_posts_stop(self, local_http_server):
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload(state="RUNNING")),
            "",
        ]
        assert _compute_client(local_http_server).stop("wh-1") == {}
        assert RecordingHandler.requests[1]["path"] == "/api/2.0/sql/warehouses/wh-1/stop"
        assert RecordingHandler.requests[1]["body"] == "", "the stop endpoint takes NO request body"

    def test_stop_on_starting_posts_stop(self, local_http_server):
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload(state="STARTING")),
            "",
        ]
        assert _compute_client(local_http_server).stop("wh-1") == {}

    def test_start_on_stopping_attempts_the_start_call(self, local_http_server):
        # A warehouse mid-STOP cannot be judged idempotent — the request
        # is forwarded and the workspace's own rejection (if any)
        # propagates as a classified error.
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload(state="STOPPING")),
            "",
        ]
        assert _compute_client(local_http_server).start("wh-1") == {}

    def test_start_on_deleting_raises_the_state_error(self, local_http_server):
        from hub.apps.databricks_admin.sql_warehouse_client import (
            DatabricksWarehouseStateError,
        )

        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="DELETING"))]
        with pytest.raises(DatabricksWarehouseStateError) as excinfo:
            _compute_client(local_http_server).start("wh-1")
        assert excinfo.value.code == "DATABRICKS_WAREHOUSE_STATE_ERROR"
        assert len(RecordingHandler.requests) == 1, "no START may be issued on DELETING"

    def test_unknown_state_raises_the_state_error(self, local_http_server):
        from hub.apps.databricks_admin.sql_warehouse_client import (
            DatabricksWarehouseStateError,
        )

        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="WARPING"))]
        with pytest.raises(DatabricksWarehouseStateError):
            _compute_client(local_http_server).start("wh-1")
        assert len(RecordingHandler.requests) == 1

        # The recorder is cumulative across the test — pin the DELTA for
        # the second half (one more state GET, nothing else).
        requests_before = len(RecordingHandler.requests)
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="WARPING"))]
        with pytest.raises(DatabricksWarehouseStateError):
            _compute_client(local_http_server).stop("wh-1")
        assert len(RecordingHandler.requests) == requests_before + 1

    def test_missing_state_raises_the_state_error(self, local_http_server):
        from hub.apps.databricks_admin.sql_warehouse_client import (
            DatabricksWarehouseStateError,
        )

        RecordingHandler.json_script = [json.dumps({"id": "wh-1"})]
        with pytest.raises(DatabricksWarehouseStateError):
            _compute_client(local_http_server).start("wh-1")

    def test_start_post_rejection_propagates_classified(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksAuthError

        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="STOPPED"))]
        RecordingHandler.script = [200, 401]
        with pytest.raises(DatabricksAuthError):
            _compute_client(local_http_server).start("wh-1")


class TestDatabricksWarehouseStateError:
    """The Hub's own state failures carry the catalogued code."""

    def test_is_a_classified_databricks_error(self):
        from hub.apps.databricks_admin.client import DatabricksApiError
        from hub.apps.databricks_admin.sql_warehouse_client import (
            DatabricksWarehouseStateError,
        )

        error = DatabricksWarehouseStateError("Warehouse 'wh-1' is DELETING")
        assert isinstance(error, DatabricksApiError)
        assert error.code == "DATABRICKS_WAREHOUSE_STATE_ERROR"
        assert "wh-1" in str(error)

    def test_the_code_is_catalogued(self):
        catalogue = (REPO_ROOT / "docs/api/error-codes.md").read_text()
        assert "`DATABRICKS_WAREHOUSE_STATE_ERROR`" in catalogue, (
            "DATABRICKS_WAREHOUSE_STATE_ERROR must be a row in docs/api/error-codes.md"
        )
