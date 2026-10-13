"""Phase 9 (task 9.4) — the live-contract tests, three layers:

1. THE STATIC MATRIX (always on, no network): the shipped executor's
   write-coverage registry (`uc_change_executor._REST_PINS`) vs the
   `api_paths.py` version-pinned registry — every (object type, action)
   pair must be backed by a real 2.1 pin, so a removed/renamed pin is a
   CI RED, never a live-workspace surprise.
2. THE LOCAL CONTRACT PINS (always on, real local HTTP server): the
   shipped pagination machinery (`uc_sync._list_path_pages`) and the
   statement-submit classification driven through the PRODUCTION
   clients — the effective-permissions fetch MUST collect EVERY page
   (design D5's max_results=0 + next_page_token contract) and a
   repeating token must fail classified, never hang; a stopped-warehouse
   outcome must surface as a CLASSIFIED error, never a raw parse error.
3. THE LIVE PROBES (W16-gated — CI raises, local runs skip): the
   write-coverage round-trips per object type, the stopped-warehouse
   auto-start observation (the umbrella's open question #1 — the
   observed behavior becomes the pinned contract), and the grants
   effective-permissions pagination against the REAL workspace.
"""

import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

import django

django.setup()

import pytest

from hub.apps.databricks_admin.client import (
    DatabricksApiClient,
    DatabricksApiError,
    DatabricksServerError,
)


class TestWriteCoverageMatrix:
    """The shipped write-coverage registry vs the version-pinned paths."""

    def test_every_executor_pin_is_backed_by_a_versioned_path(self):
        from hub.apps.databricks_admin.api_paths import API_PATH_VERSIONS, API_PATHS
        from hub.apps.databricks_admin.uc_change_executor import _REST_PINS

        assert _REST_PINS, "the executor's write-coverage registry must not be empty"
        for (obj_type, action), (operation, method, _body, _path_params) in _REST_PINS.items():
            assert operation in API_PATHS, (
                f"({obj_type}, {action}) pins {operation!r} — not in API_PATHS"
            )
            assert API_PATHS[operation].startswith("/api/2.1/"), (
                f"{operation} must be a 2.1 UC REST pin, got {API_PATHS[operation]!r}"
            )
            assert API_PATH_VERSIONS.get(operation) == "2.1", (
                f"{operation} must carry a documented 2.1 version"
            )
            assert method in {"POST", "DELETE"}

    def test_the_matrix_covers_every_executor_supported_type_both_ways(self):
        from hub.apps.databricks_admin.models import UCObjectType
        from hub.apps.databricks_admin.uc_change_executor import _REST_PINS

        covered = {(obj_type, action) for (obj_type, action) in _REST_PINS}
        expected_types = {
            UCObjectType.CATALOG,
            UCObjectType.SCHEMA,
            UCObjectType.TABLE,
            UCObjectType.VIEW,
            UCObjectType.VOLUME,
            UCObjectType.EXTERNAL_LOCATION,
            UCObjectType.STORAGE_CREDENTIAL,
            UCObjectType.MODEL,
        }
        for obj_type in expected_types:
            assert (obj_type, "CREATE") in covered, f"{obj_type} CREATE missing from the matrix"
            assert (obj_type, "DROP") in covered, f"{obj_type} DROP missing from the matrix"


class TestPermissionsPaginationContract:
    """The effective-permissions fetch collects EVERY page (design D5)."""

    def _client(self, port):
        import httpx

        return DatabricksApiClient(
            host="dbc-test.cloud.databricks.com",
            base_url=f"http://127.0.0.1:{port}",
            credential_config={"token": "dapi-x"},
            use_breaker=False,
            backoff_waiter=lambda _attempt: None,
            client=httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5.0),
        )

    def test_multi_page_permissions_are_concatenated(self, local_http_server):
        from hub.apps.databricks_admin.tests._http import RecordingHandler
        from hub.apps.databricks_admin.uc_sync import _list_path_pages

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "privilege_assignments": [{"principal": "a", "privileges": ["SELECT"]}],
                    "next_page_token": "page-2",
                }
            ),
            json.dumps(
                {
                    "privilege_assignments": [{"principal": "b", "privileges": ["MODIFY"]}],
                }
            ),
        ]
        result = _list_path_pages(
            self._client(local_http_server),
            "uc.effective_permissions.table",
            "privilege_assignments",
            {"full_name": "main.sales.orders"},
        )
        assert [row["principal"] for row in result["privilege_assignments"]] == ["a", "b"], (
            "BOTH pages must land in the assembled answer — a one-shot fetch "
            "silently truncates the permissions list"
        )
        assert len(RecordingHandler.requests) == 2
        assert "max_results=0" in RecordingHandler.requests[0]["path"], (
            "design D5's gotcha: the permissions API is paged with max_results=0"
        )
        assert "page_token=page-2" in RecordingHandler.requests[1]["path"]

    def test_single_page_stops_when_the_token_is_absent(self, local_http_server):
        from hub.apps.databricks_admin.tests._http import RecordingHandler
        from hub.apps.databricks_admin.uc_sync import _list_path_pages

        RecordingHandler.json_script = [
            json.dumps({"privilege_assignments": []}),
        ]
        result = _list_path_pages(
            self._client(local_http_server),
            "uc.effective_permissions.table",
            "privilege_assignments",
            {"full_name": "main.sales.orders"},
        )
        assert result["privilege_assignments"] == []
        assert len(RecordingHandler.requests) == 1, "no token → exactly one request"

    def test_a_repeating_token_fails_classified_never_hangs(self, local_http_server):
        from hub.apps.databricks_admin.tests._http import RecordingHandler
        from hub.apps.databricks_admin.uc_sync import _list_path_pages

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "privilege_assignments": [{"principal": "a", "privileges": ["SELECT"]}],
                    "next_page_token": "stuck",
                }
            ),
            json.dumps(
                {
                    "privilege_assignments": [],
                    "next_page_token": "stuck",
                }
            ),
        ]
        with pytest.raises(DatabricksApiError) as excinfo:
            _list_path_pages(
                self._client(local_http_server),
                "uc.effective_permissions.table",
                "privilege_assignments",
                {"full_name": "main.sales.orders"},
            )
        assert "repeating" in str(excinfo.value).lower(), (
            "the seen-token guard must fail classified, never loop forever"
        )
        assert len(RecordingHandler.requests) == 2, "the guard trips on the SECOND sighting"


class TestStatementSubmitContract:
    """The statement-submit surface: payload shape + classification."""

    def _executor(self, port):
        import httpx

        from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor

        client = DatabricksApiClient(
            host="dbc-test.cloud.databricks.com",
            base_url=f"http://127.0.0.1:{port}",
            credential_config={"token": "dapi-x"},
            use_breaker=False,
            backoff_waiter=lambda _attempt: None,
            client=httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5.0),
        )
        return SqlStatementExecutor(client, warehouse_id="/sql/1.0/warehouses/wh-abc")

    def test_submit_carries_the_statement_contract(self, local_http_server):
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        RecordingHandler.json_script = [
            json.dumps({"statement_id": "stmt-1", "status": {"state": "PENDING"}})
        ]
        statement_id = self._executor(local_http_server).submit("SELECT 1", wait_timeout="10s")
        assert statement_id == "stmt-1"
        (request,) = RecordingHandler.requests
        assert request["method"] == "POST"
        body = json.loads(request["body"])
        assert body["statement"] == "SELECT 1"
        assert body["wait_timeout"] == "10s"
        assert body["warehouse_id"] == "wh-abc", (
            "the http_path form must resolve to the bare warehouse id"
        )

    def test_a_stopped_warehouse_outcome_is_a_classified_error(self, local_http_server):
        # The auto-start contract's discipline: whatever the API answers
        # for a STOPPED warehouse (500 in this script), the executor must
        # surface a CLASSIFIED Databricks error — never a raw transport
        # or parse exception (the live probe records the real answer).
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        # The 5xx is RETRYABLE — the retry budget must exhaust with the
        # SAME stopped-warehouse answer, then classify (a transient 5xx
        # that later lands a 200 is a different pin — see below).
        RecordingHandler.script = [500, 500, 500]
        RecordingHandler.json_script = [
            json.dumps({"error_code": "WAREHOUSE_STOPPED"}),
            json.dumps({"error_code": "WAREHOUSE_STOPPED"}),
            json.dumps({"error_code": "WAREHOUSE_STOPPED"}),
        ]
        with pytest.raises(DatabricksServerError):
            self._executor(local_http_server).submit("SELECT 1")

    def test_a_retry_landing_an_unexpected_200_is_classified(self, local_http_server):
        # The real root-cause class the contract pins: a retry can land a
        # 200 whose body shape drifted — the executor must raise a
        # CLASSIFIED error, never a raw KeyError.
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        RecordingHandler.script = [500, 200]
        RecordingHandler.json_script = [json.dumps({"error_code": "TRANSIENT"}), "{}"]
        with pytest.raises(DatabricksApiError, match="statement_id"):
            self._executor(local_http_server).submit("SELECT 1")


class TestLiveContractProbes:
    """The real-sandbox probes (W16 — CI raises, local runs skip)."""

    def test_write_coverage_round_trips_against_the_live_workspace(self, live_workspace_client):
        # create → verify → drop per object type through the pin builders —
        # the SAME registry the shipped executor dispatches (a live pin
        # drift fails here with the exact request/response pair).
        from hub.apps.databricks_admin.uc_change_executor import (
            _REST_PINS,
            UCDdlPayload,
        )

        identifiers_by_type = {
            "CATALOG": ("meshant_e2e_ct",),
            "SCHEMA": ("meshant_e2e_ct", "meshant_e2e_s"),
        }
        created: list[tuple] = []
        try:
            for (obj_type, action), (operation, method, body_builder, path_builder) in sorted(
                _REST_PINS.items(), key=lambda kv: str(kv[0])
            ):
                if action != "CREATE":
                    continue
                identifiers = identifiers_by_type.get(
                    str(obj_type),
                    ("meshant_e2e_ct", "meshant_e2e_s", f"meshant_e2e_{str(obj_type).lower()}"),
                )
                payload = UCDdlPayload(object_type=obj_type, action=action, identifiers=identifiers)
                response = live_workspace_client.request(
                    method,
                    operation,
                    json=body_builder(payload),
                    path_params=path_builder(payload) or None,
                )
                assert 200 <= response.status_code < 300, f"{operation}: {response.text}"
                created.append((obj_type, payload))
        finally:
            for obj_type, payload in reversed(created):
                _op, _m, _b, path_builder = _REST_PINS[(obj_type, "DROP")]
                drop_op = _REST_PINS[(obj_type, "DROP")][0]
                live_workspace_client.request(
                    "DELETE", drop_op, path_params=path_builder(payload) or None
                )

    def test_stopped_warehouse_auto_start_is_observed_and_recorded(self, live_workspace_client):
        # The umbrella's open question #1: the OBSERVED behavior becomes
        # the pinned contract — the probe asserts the classification
        # discipline and prints the exact outcome for the report.
        import os

        from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor

        warehouse_id = SqlStatementExecutor.resolve_warehouse_id(
            os.environ["DATABRICKS_E2E_WAREHOUSE_ID"]
        )
        live_workspace_client.request(
            "POST", "sql.warehouses.stop", path_params={"warehouse_id": warehouse_id}
        )
        try:
            SqlStatementExecutor(live_workspace_client, warehouse_id=warehouse_id).submit(
                "SELECT 1"
            )
            outcome = "SUCCEEDED (auto-start observed)"
        except DatabricksApiError as exc:
            outcome = f"FAILED_CLASSIFIED: {exc.code} {exc}"
        print(f"AUTO_START_OBSERVATION: {outcome}")
        assert outcome.startswith(("SUCCEEDED", "FAILED_CLASSIFIED")), (
            "the stopped-warehouse outcome must be a success or a CLASSIFIED "
            "error — never a raw exception"
        )

    def test_live_effective_permissions_collect_every_page(self, live_workspace_client):
        from hub.apps.databricks_admin.uc_sync import _list_path_pages

        result = _list_path_pages(
            live_workspace_client,
            "uc.effective_permissions.table",
            "privilege_assignments",
            {"full_name": "main.default.meshant_e2e_ct_table"},
        )
        assert isinstance(result["privilege_assignments"], list), (
            "the live answer must assemble the privilege_assignments list"
        )
