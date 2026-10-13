"""TDD pins for task 3.10 — the compute client driven by DATA fixture
responses (the 1.12 convention).

The payloads live in ``tests/fixtures/databricks/`` as auditable JSON
artifacts — ``sql_warehouses_estate.json`` (the list envelope),
``sql_warehouse_state_matrix.json`` (one payload per lifecycle state)
and ``sql_warehouse_roundtrip.json`` (the create→start→query→stop
script). Tests serve these files through a REAL threaded HTTP server to
the PRODUCTION ``DatabricksComputeClient`` — the transport is real, the
responses come from files, so the estate the client is pinned against
is a single auditable artifact (never an inline payload that can drift
from the round-trip suite's view of the same data).

The integrity pins first: the fixtures are contract data, so their shape
is pinned (states within the vocabulary, unique ids, the serverless↔size
invariant, the round-trip script's internal consistency). Then the
client pins: every operation driven against those fixtures.

Pure-transport suite — no ``django_db`` mark (the 3.3 convention: the
client performs ZERO ORM work).
"""

import json
from pathlib import Path

import pytest

from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests._uc_fixtures import load_fixture

REPO_ROOT = Path(__file__).resolve().parents[4]

ESTATE = "sql_warehouses_estate"
STATE_MATRIX = "sql_warehouse_state_matrix"
ROUNDTRIP = "sql_warehouse_roundtrip"


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
            use_breaker=False,  # the 1.7 delegation convention — the test owns the transport
        )
    )


class TestFixtureIntegrity:
    """The fixtures are contract data — drift must fail here, loudly."""

    def test_estate_carries_only_vocabulary_rows(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouseState

        envelope = load_fixture(ESTATE)
        assert isinstance(envelope, dict)
        rows = envelope["warehouses"]
        assert isinstance(rows, list)
        assert rows
        seen: set[str] = set()
        for row in rows:
            assert isinstance(row, dict), row
            assert str(row.get("id") or ""), "every estate row carries an id"
            assert row.get("state") in DatabricksSqlWarehouseState.values, row
            assert isinstance(row.get("serverless"), bool), row
            assert isinstance(row.get("name"), str), row
            assert row["name"].strip(), row
            assert isinstance(row.get("auto_stop_mins"), int), row
            if row["serverless"]:
                assert row.get("size") is None, "serverless rows carry NULL size"
            else:
                assert isinstance(row.get("size"), str), row
                assert row["size"].strip(), row
            assert row["id"] not in seen, f"duplicate estate id {row['id']}"
            seen.add(row["id"])

    def test_state_matrix_covers_all_five_states(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouseState

        matrix = load_fixture(STATE_MATRIX)
        warehouses = matrix["warehouses"]
        assert isinstance(warehouses, dict)
        assert set(warehouses) == {f"wh-{state}" for state in DatabricksSqlWarehouseState.values}, (
            "the matrix must carry exactly one warehouse per lifecycle state"
        )
        for warehouse_id, payload in warehouses.items():
            assert payload["id"] == warehouse_id, "the key IS the warehouse id"
            assert payload["state"] == warehouse_id.removeprefix("wh-"), (
                "a matrix payload's state must match its key (the idempotency "
                "decision reads THIS payload's state)"
            )

    def test_roundtrip_script_is_internally_consistent(self):
        fixture = load_fixture(ROUNDTRIP)
        steps = fixture["steps"]
        assert isinstance(steps, list)
        assert steps
        for step_name in steps:
            assert step_name in fixture, (
                f"round-trip step {step_name!r} must reference a named payload"
            )

        create = fixture["create"]
        assert str(create.get("id") or ""), "the create answer carries the new id"
        warehouse_id = create["id"]
        # The script's list envelopes and state GETs all describe the SAME
        # warehouse the create just made — never a different id.
        for step_name in steps:
            payload = fixture[step_name]
            if payload is None:
                continue  # the empty-body mutation answers
            if isinstance(payload, dict) and "warehouses" in payload:
                for row in payload["warehouses"]:
                    assert row["id"] == warehouse_id, step_name
            if isinstance(payload, dict) and payload.get("id") == warehouse_id:
                assert payload.get("state") in (
                    "STARTING",
                    "RUNNING",
                    "STOPPING",
                    "STOPPED",
                    "DELETING",
                ), step_name

        statement = fixture["statement_succeeded"]
        assert statement["status"]["state"] == "SUCCEEDED", (
            "the query leg's submit answer is terminal (no polling needed)"
        )
        assert statement["result"]["data_array"], "the query leg returns rows"

    def test_the_fixture_paths_stay_within_the_compute_surface(self):
        # Every fixture payload the client parses must keep matching the
        # 2.0 compute surface's fields — the fixtures pin the payload
        # SHAPE the client contract promises (id/state/name/serverless/
        # size/auto_stop_mins — nothing else is consumed).
        estate = load_fixture(ESTATE)
        matrix = load_fixture(STATE_MATRIX)
        roundtrip = load_fixture(ROUNDTRIP)
        allowed = {"id", "name", "state", "serverless", "size", "auto_stop_mins"}
        rows = list(estate["warehouses"]) + list(matrix["warehouses"].values())
        rows.append(roundtrip["create"])
        for row in rows:
            assert set(row) <= allowed, f"unexpected field(s) in {row}: {set(row) - allowed}"


class TestComputeClientAgainstFixtures:
    """Every client operation driven by the fixture responses."""

    def test_list_returns_the_fixture_estate(self, local_http_server):
        estate = load_fixture(ESTATE)
        RecordingHandler.json_script = [json.dumps(estate)]
        result = _compute_client(local_http_server).list()
        assert [(r["id"], r["name"], r["state"]) for r in result] == [
            (row["id"], row["name"], row["state"]) for row in estate["warehouses"]
        ]
        request = RecordingHandler.requests[-1]
        assert request["method"] == "GET"
        assert request["path"] == "/api/2.0/sql/warehouses"

    def test_get_returns_the_fixture_payload_per_state(self, local_http_server):
        matrix = load_fixture(STATE_MATRIX)
        client = _compute_client(local_http_server)
        for warehouse_id, payload in matrix["warehouses"].items():
            RecordingHandler.json_script = [json.dumps(payload)]
            result = client.get(warehouse_id)
            assert result == payload, warehouse_id
            assert RecordingHandler.requests[-1]["path"] == (
                f"/api/2.0/sql/warehouses/{warehouse_id}"
            )

    def test_create_sends_the_exact_payload_and_returns_the_fixture_id(self, local_http_server):
        # The pin requests a CLASSIC create so the request shape matches
        # the round-trip fixture's create payload (serverless:false +
        # size:S) that answers it — the fixture is the canonical create.
        roundtrip = load_fixture(ROUNDTRIP)
        RecordingHandler.json_script = [json.dumps(roundtrip["create"])]
        result = _compute_client(local_http_server).create(
            name="roundtrip-wh", serverless=False, size="S", auto_stop_mins=30
        )
        assert result == roundtrip["create"]["id"]

        request = RecordingHandler.requests[-1]
        assert request["method"] == "POST"
        assert request["path"] == "/api/2.0/sql/warehouses"
        assert json.loads(request["body"]) == {
            "name": "roundtrip-wh",
            "serverless": False,
            "size": "S",
            "auto_stop_mins": 30,
        }

    def test_start_on_a_fixture_running_warehouse_is_a_no_op(self, local_http_server):
        matrix = load_fixture(STATE_MATRIX)
        RecordingHandler.json_script = [json.dumps(matrix["warehouses"]["wh-RUNNING"])]
        assert _compute_client(local_http_server).start("wh-RUNNING") is None
        assert [r["method"] for r in RecordingHandler.requests] == ["GET"]

    def test_stop_on_a_fixture_stopped_warehouse_is_a_no_op(self, local_http_server):
        matrix = load_fixture(STATE_MATRIX)
        RecordingHandler.json_script = [json.dumps(matrix["warehouses"]["wh-STOPPED"])]
        assert _compute_client(local_http_server).stop("wh-STOPPED") is None
        assert [r["method"] for r in RecordingHandler.requests] == ["GET"]

    def test_start_on_a_fixture_deleting_warehouse_raises_the_state_error(self, local_http_server):
        from hub.apps.databricks_admin.sql_warehouse_client import (
            DatabricksWarehouseStateError,
        )

        matrix = load_fixture(STATE_MATRIX)
        RecordingHandler.json_script = [json.dumps(matrix["warehouses"]["wh-DELETING"])]
        with pytest.raises(DatabricksWarehouseStateError) as excinfo:
            _compute_client(local_http_server).start("wh-DELETING")
        assert excinfo.value.code == "DATABRICKS_WAREHOUSE_STATE_ERROR"
        assert len(RecordingHandler.requests) == 1, "no START may be issued on DELETING"

    def test_stop_on_a_fixture_running_warehouse_posts_stop(self, local_http_server):
        matrix = load_fixture(STATE_MATRIX)
        roundtrip = load_fixture(ROUNDTRIP)
        RecordingHandler.json_script = [
            json.dumps(matrix["warehouses"]["wh-RUNNING"]),
            "",  # the stop endpoint's empty-body answer (roundtrip["stop_answer"])
        ]
        assert _compute_client(local_http_server).stop("wh-RUNNING") == {}
        requests = RecordingHandler.requests
        assert [r["method"] for r in requests] == ["GET", "POST"]
        assert requests[1]["path"] == "/api/2.0/sql/warehouses/wh-RUNNING/stop"
        assert requests[1]["body"] == ""
        # The mutation leg answers with the round-trip's own stop payload
        # shape — empty (the fixture's stop_answer entry is None).
        assert roundtrip["stop_answer"] is None

    def test_fixture_driven_404_propagates_classified(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiError

        RecordingHandler.script = [404]
        RecordingHandler.json_script = [json.dumps(load_fixture(ESTATE))]
        with pytest.raises(DatabricksApiError) as excinfo:
            _compute_client(local_http_server).list()
        assert excinfo.value.status_code == 404
        assert len(RecordingHandler.requests) == 1

    def test_the_error_code_catalogue_carries_the_state_error(self):
        catalogue = (REPO_ROOT / "docs/api/error-codes.md").read_text()
        assert "`DATABRICKS_WAREHOUSE_STATE_ERROR`" in catalogue
