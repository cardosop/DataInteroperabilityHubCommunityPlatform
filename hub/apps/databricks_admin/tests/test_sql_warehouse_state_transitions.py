"""TDD pins for task 3.10 — the exhaustive state-transition matrix.

Two tables, both pinned as matrices (never as scattered one-off pins):

- **The client idempotency matrix** — every lifecycle state x every
  action (the 5x2 table). START: no-op on STARTING/RUNNING, a real POST
  on STOPPING/STOPPED, the classified ``DATABRICKS_WAREHOUSE_STATE_ERROR``
  on DELETING (no POST issued). STOP: a real POST on STARTING/RUNNING,
  no-op on STOPPING/STOPPED/DELETING. Driven by the
  ``sql_warehouse_state_matrix.json`` fixture through a REAL local HTTP
  server — the state each decision reads IS the fixture payload.
- **The mirror transition table** — created → updated → unchanged →
  deleted, driven by mutations of the ``sql_warehouses_estate.json``
  fixture (the fixture is the single data source; the table mutates the
  LOADED rows, never an inline payload literal).

No mocks: the production client and the production mirror against real
transports (threaded HTTP + real Postgres rows).
"""

import copy
import json

import pytest

from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests._uc_fixtures import load_fixture

# ── the client idempotency matrix (the 3.3 contract, exhaustively) ──────────

# state → (expected kind, expected extra requests)
#   kind "noop"        — returns None, exactly ONE request (the state GET)
#   kind "post"        — returns {}, TWO requests (state GET + the action POST)
#   kind "state_error" — raises DATABRICKS_WAREHOUSE_STATE_ERROR, ONE request
START_MATRIX = {
    "STARTING": ("noop", 0),
    "RUNNING": ("noop", 0),
    "STOPPING": ("post", 1),
    "STOPPED": ("post", 1),
    "DELETING": ("state_error", 0),
}

STOP_MATRIX = {
    "STARTING": ("post", 1),
    "RUNNING": ("post", 1),
    "STOPPING": ("noop", 0),
    "STOPPED": ("noop", 0),
    "DELETING": ("noop", 0),
}

ACTION_POST_PATHS = {
    "start": "/api/2.0/sql/warehouses/wh-{state}/start",
    "stop": "/api/2.0/sql/warehouses/wh-{state}/stop",
}


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


def _matrix_payload(state):
    return json.dumps(load_fixture("sql_warehouse_state_matrix")["warehouses"][f"wh-{state}"])


class TestClientStateTransitionMatrix:
    """Every (state, action) cell of the idempotency matrix."""

    @pytest.mark.parametrize("state", sorted(START_MATRIX))
    def test_start_matrix(self, local_http_server, state):
        from hub.apps.databricks_admin.sql_warehouse_client import (
            DatabricksWarehouseStateError,
        )

        kind, extra = START_MATRIX[state]
        RecordingHandler.json_script = [_matrix_payload(state)]
        if kind == "post":
            RecordingHandler.json_script.append("")
        client = _compute_client(local_http_server)

        if kind == "state_error":
            with pytest.raises(DatabricksWarehouseStateError) as excinfo:
                client.start(f"wh-{state}")
            assert excinfo.value.code == "DATABRICKS_WAREHOUSE_STATE_ERROR"
            assert len(RecordingHandler.requests) == 1
            return
        result = client.start(f"wh-{state}")
        if kind == "noop":
            assert result is None, state
        else:
            assert result == {}, state
        requests = RecordingHandler.requests
        assert len(requests) == 1 + extra, state
        assert requests[0]["path"] == f"/api/2.0/sql/warehouses/wh-{state}"
        if kind == "post":
            assert requests[1]["method"] == "POST"
            assert requests[1]["path"] == ACTION_POST_PATHS["start"].format(state=state)
            assert requests[1]["body"] == "", "the start endpoint takes NO request body"

    @pytest.mark.parametrize("state", sorted(STOP_MATRIX))
    def test_stop_matrix(self, local_http_server, state):
        kind, extra = STOP_MATRIX[state]
        RecordingHandler.json_script = [_matrix_payload(state)]
        if kind == "post":
            RecordingHandler.json_script.append("")
        client = _compute_client(local_http_server)

        result = client.stop(f"wh-{state}")
        if kind == "noop":
            assert result is None, state
        else:
            assert result == {}, state
        requests = RecordingHandler.requests
        assert len(requests) == 1 + extra, state
        assert requests[0]["path"] == f"/api/2.0/sql/warehouses/wh-{state}"
        if kind == "post":
            assert requests[1]["method"] == "POST"
            assert requests[1]["path"] == ACTION_POST_PATHS["stop"].format(state=state)
            assert requests[1]["body"] == "", "the stop endpoint takes NO request body"

    def test_the_matrix_covers_the_entire_vocabulary(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouseState

        assert set(START_MATRIX) == set(DatabricksSqlWarehouseState.values)
        assert set(STOP_MATRIX) == set(DatabricksSqlWarehouseState.values)


@pytest.mark.django_db(transaction=True)
class TestMirrorTransitionTable:
    """created → updated → unchanged → deleted across the five states.

    Real Postgres rows; every envelope the mirror reads is a mutation of
    the estate fixture (the single auditable data source).
    """

    def _refresh(self, port, envelope, workspace=None):
        from hub.apps.databricks_admin.sql_warehouses import refresh_sql_warehouse_mirror
        from hub.apps.databricks_admin.tests.test_sql_warehouse_mirror import _client

        RecordingHandler.json_script = [json.dumps(envelope)]
        return refresh_sql_warehouse_mirror(workspace or self.workspace, client=_client(port))

    def _seed_workspace(self):
        from hub.apps.databricks_admin.tests._fixtures import require_dns
        from hub.apps.databricks_admin.tests.test_sql_warehouse_mirror import _make_workspace
        from tests.factories import TenantFactory

        require_dns()
        tenant = TenantFactory.create_tenant()
        self.workspace = _make_workspace(tenant)
        self.tenant = tenant

    def _states(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        return dict(
            DatabricksSqlWarehouse.objects.filter(workspace=self.workspace).values_list(
                "warehouse_id", "state"
            )
        )

    def test_the_full_transition_table(self, local_http_server):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        self._seed_workspace()
        estate = load_fixture("sql_warehouses_estate")

        # Refresh 1 — every estate row is CREATED.
        counters = self._refresh(local_http_server, estate)
        assert counters == {"created": 3, "updated": 0, "unchanged": 0, "deleted": 0}, counters
        assert self._states() == {
            "wh-estate-1": "RUNNING",
            "wh-estate-2": "STOPPED",
            "wh-estate-3": "STARTING",
        }

        # Refresh 2 — every existing row TRANSITIONS to a different state
        # (RUNNING→STOPPED, STOPPED→STARTING, STARTING→RUNNING — each of the
        # five states participates) and a NEW row arrives.
        changed = copy.deepcopy(estate)
        changed["warehouses"][0]["state"] = "STOPPED"
        changed["warehouses"][1]["state"] = "STARTING"
        changed["warehouses"][2]["state"] = "RUNNING"
        changed["warehouses"].append(
            {
                "id": "wh-estate-4",
                "name": "adhoc-new",
                "state": "STOPPED",
                "serverless": True,
                "size": None,
                "auto_stop_mins": 20,
            }
        )
        counters = self._refresh(local_http_server, changed)
        assert counters == {"created": 1, "updated": 3, "unchanged": 0, "deleted": 0}, counters
        assert self._states() == {
            "wh-estate-1": "STOPPED",
            "wh-estate-2": "STARTING",
            "wh-estate-3": "RUNNING",
            "wh-estate-4": "STOPPED",
        }

        # Refresh 3 — the two untouched rows are UNCHANGED; the two absent
        # rows are DELETED (no compensating action — the mirror just forgets).
        final = copy.deepcopy(changed)
        final["warehouses"] = [
            row for row in changed["warehouses"] if row["id"] in ("wh-estate-1", "wh-estate-3")
        ]
        counters = self._refresh(local_http_server, final)
        assert counters == {"created": 0, "updated": 0, "unchanged": 2, "deleted": 2}, counters
        assert self._states() == {"wh-estate-1": "STOPPED", "wh-estate-3": "RUNNING"}
        assert DatabricksSqlWarehouse.objects.filter(workspace=self.workspace).count() == 2

    def test_a_row_arriving_already_starting_is_created_not_updated(self, local_http_server):
        """A warehouse that arrives ALREADY STARTING is CREATED (the
        created counter carries it — the long-STARTING timer anchors at
        first sight); a second identical refresh leaves it UNCHANGED —
        never re-created, never re-anchored."""
        self._seed_workspace()
        estate = load_fixture("sql_warehouses_estate")
        counters = self._refresh(local_http_server, estate)
        assert counters == {"created": 3, "updated": 0, "unchanged": 0, "deleted": 0}, counters
        assert self._states()["wh-estate-3"] == "STARTING"

        counters = self._refresh(local_http_server, estate)
        assert counters == {"created": 0, "updated": 0, "unchanged": 3, "deleted": 0}, counters
        assert self._states()["wh-estate-3"] == "STARTING"

    def test_unknown_state_rows_never_enter_the_transition_table(self, local_http_server):
        """A reported state outside the vocabulary is SKIPPED — the
        transition table only ever contains the five known states."""
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        self._seed_workspace()
        estate = load_fixture("sql_warehouses_estate")
        estate["warehouses"].append(
            {
                "id": "wh-warping",
                "name": "warp-drive",
                "state": "WARPING",
                "serverless": False,
                "size": "S",
                "auto_stop_mins": 30,
            }
        )
        counters = self._refresh(local_http_server, estate)
        assert counters == {"created": 3, "updated": 0, "unchanged": 0, "deleted": 0}, counters
        assert not DatabricksSqlWarehouse.objects.filter(
            workspace=self.workspace, warehouse_id="wh-warping"
        ).exists()

    def test_the_mirror_never_invents_a_state_the_fixture_did_not_report(self, local_http_server):
        """The table's guarantee end-to-end: after every refresh, each row's
        state is EXACTLY one of the states the fixture reported — the
        mirror's state column can never hold a value the API didn't send."""
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouseState

        self._seed_workspace()
        estate = load_fixture("sql_warehouses_estate")
        self._refresh(local_http_server, estate)
        for state in self._states().values():
            assert state in DatabricksSqlWarehouseState.values
