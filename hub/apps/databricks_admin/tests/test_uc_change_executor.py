"""TDD pins for UCChangeExecutor (openspec add-databricks-uc-write task
2.3) — REST-first UC DDL with the SQL fallback.

No mocks: every REST pin drives the PRODUCTION client in transport mode
against a REAL local HTTP server (the 1.5 `_local_client_factory`
pattern) and asserts the exact method/path/body; the SQL fallback pins
drive the REAL SqlStatementExecutor (0.7) against the same server with
scripted sql/statements envelopes and assert the identifier-quoted
statement. Version-pin discipline is pinned too: every DDL operation
must exist in API_PATHS + API_PATH_VERSIONS (2.1) — unknown operations
fail at development time, never against a live workspace.
"""

import json

import pytest

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST
from hub.apps.databricks_admin.tests._http import RecordingHandler

pytestmark = pytest.mark.django_db(transaction=True)

# (object_type, action, identifiers, body-keys) → (method, path)
_REST_DISPATCH_CASES = [
    (
        "CATALOG",
        "CREATE",
        ("main",),
        ("name", "comment", "properties"),
        ("POST", "/api/2.1/unity-catalog/catalogs"),
    ),
    (
        "CATALOG",
        "DROP",
        ("main",),
        (),
        ("DELETE", "/api/2.1/unity-catalog/catalogs/main"),
    ),
    (
        "SCHEMA",
        "CREATE",
        ("main", "sales"),
        ("name", "catalog_name", "comment", "properties"),
        ("POST", "/api/2.1/unity-catalog/schemas"),
    ),
    (
        "SCHEMA",
        "DROP",
        ("main", "sales"),
        (),
        ("DELETE", "/api/2.1/unity-catalog/schemas/main.sales"),
    ),
    (
        "TABLE",
        "CREATE",
        ("main", "sales", "orders"),
        ("name", "catalog_name", "schema_name", "table_type", "columns"),
        ("POST", "/api/2.1/unity-catalog/tables"),
    ),
    (
        "TABLE",
        "DROP",
        ("main", "sales", "orders"),
        (),
        ("DELETE", "/api/2.1/unity-catalog/tables/main.sales.orders"),
    ),
    (
        "VIEW",
        "CREATE",
        ("main", "sales", "v_orders"),
        ("name", "catalog_name", "schema_name", "view_definition"),
        ("POST", "/api/2.1/unity-catalog/views"),
    ),
    (
        "VIEW",
        "DROP",
        ("main", "sales", "v_orders"),
        (),
        ("DELETE", "/api/2.1/unity-catalog/views/main.sales.v_orders"),
    ),
    (
        "VOLUME",
        "CREATE",
        ("main", "sales", "raw"),
        ("name", "catalog_name", "schema_name", "volume_type"),
        ("POST", "/api/2.1/unity-catalog/volumes"),
    ),
    (
        "VOLUME",
        "DROP",
        ("main", "sales", "raw"),
        (),
        ("DELETE", "/api/2.1/unity-catalog/volumes/main.sales.raw"),
    ),
    (
        "EXTERNAL_LOCATION",
        "CREATE",
        ("s3_raw",),
        ("name", "url", "credential_name"),
        ("POST", "/api/2.1/unity-catalog/external-locations"),
    ),
    (
        "EXTERNAL_LOCATION",
        "DROP",
        ("s3_raw",),
        (),
        ("DELETE", "/api/2.1/unity-catalog/external-locations/s3_raw"),
    ),
    (
        "STORAGE_CREDENTIAL",
        "CREATE",
        ("cred_a",),
        ("name",),
        ("POST", "/api/2.1/unity-catalog/storage-credentials"),
    ),
    (
        "STORAGE_CREDENTIAL",
        "DROP",
        ("cred_a",),
        (),
        ("DELETE", "/api/2.1/unity-catalog/storage-credentials/cred_a"),
    ),
    (
        "MODEL",
        "CREATE",
        ("main", "sales", "churn"),
        ("name", "catalog_name", "schema_name"),
        ("POST", "/api/2.1/unity-catalog/models"),
    ),
    (
        "MODEL",
        "DROP",
        ("main", "sales", "churn"),
        (),
        ("DELETE", "/api/2.1/unity-catalog/models/main.sales.churn"),
    ),
]


def _client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id="t1",
        credential_config={"token": "dapi-exec"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
    )


def _executor(port, warehouse_id="wh-1", tenant=None):
    from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor
    from hub.apps.databricks_admin.uc_change_executor import UCChangeExecutor

    client = _client(port)
    return UCChangeExecutor(
        client=client,
        statement_executor=SqlStatementExecutor(client, warehouse_id=warehouse_id),
        warehouse_id=warehouse_id,
        tenant=tenant,
    )


def _flag_tenant(flag):
    """A tenant with the 2.4 destructive-DDL flag set — the DROP pins
    run under it (the flag-gated contract lands with 2.4; the flag-off
    rejection pins live in test_uc_change_guards.py)."""
    from tests.factories import TenantFactory

    tenant = TenantFactory.create_tenant()
    tenant.databricks_uc_destructive_ddl_enabled = flag
    tenant.save(update_fields=["databricks_uc_destructive_ddl_enabled"])
    return tenant


class TestRESTDdlDispatch:
    """Every REST-backed (type, action) resolves to its exact pin."""

    def test_every_rest_combination_hits_its_exact_pin(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
        )

        for object_type, action, identifiers, _body_keys, (method, path) in _REST_DISPATCH_CASES:
            RecordingHandler.json_script = ["{}"]
            # 2.4: DROP is in the destructive family — the pin runs under
            # a flag-ON tenant (the flag-off rejection is the guards
            # suite's contract).
            executor = _executor(
                local_http_server,
                tenant=_flag_tenant(True) if action == "DROP" else None,
            )
            result = executor.execute(
                UCDdlPayload(
                    object_type=UCObjectType(object_type),
                    action=UCChangeAction(action),
                    identifiers=identifiers,
                )
            )
            assert result.terminal == "EXECUTED", result
            assert RecordingHandler.requests, f"no request for {action} {object_type}"
            request = RecordingHandler.requests[-1]
            assert request["method"] == method, (object_type, action, request)
            assert request["path"] == path, (object_type, action, request)

    def test_create_bodies_carry_the_identifier_derived_fields(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
        )

        RecordingHandler.json_script = ["{}"]
        _executor(local_http_server).execute(
            UCDdlPayload(
                object_type=UCObjectType.TABLE,
                action=UCChangeAction.CREATE,
                identifiers=("main", "sales", "orders"),
                options={
                    "table_type": "MANAGED",
                    "columns": [{"name": "id", "type_name": "BIGINT"}],
                    "comment": "order fact",
                },
            )
        )
        body = json.loads(RecordingHandler.requests[-1]["body"])
        assert body["name"] == "orders"
        assert body["catalog_name"] == "main"
        assert body["schema_name"] == "sales"
        assert body["table_type"] == "MANAGED"
        assert body["columns"] == [{"name": "id", "type_name": "BIGINT"}]
        assert body["comment"] == "order fact"


class TestSQLDdlFallback:
    """MV/streaming-table DDL has no UC REST surface — the SQL fallback."""

    def test_materialized_view_falls_back_to_identifier_quoted_sql(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
        )

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "statement_id": "stmt-1",
                    "status": {"state": "SUCCEEDED"},
                    "manifest": {"schema": {"columns": []}},
                    "result": {"data_array": [], "row_count": 0},
                }
            )
        ]
        result = _executor(local_http_server).execute(
            UCDdlPayload(
                object_type=UCObjectType.MATERIALIZED_VIEW,
                action=UCChangeAction.CREATE,
                identifiers=("main", "sales", "mv_orders"),
                options={"query": "SELECT * FROM main.sales.orders"},
            )
        )
        assert result.terminal == "EXECUTED", result
        # The SQL fallback rides the 0.7 sql/statements surface — NO REST
        # DDL call may exist for this type.
        rest_calls = [r for r in RecordingHandler.requests if r["path"].startswith("/api/2.1/")]
        assert rest_calls == [], rest_calls
        statement_calls = [
            r for r in RecordingHandler.requests if r["path"] == "/api/2.0/sql/statements"
        ]
        assert len(statement_calls) == 1
        body = json.loads(statement_calls[0]["body"])
        sql = body.get("statement", "")
        assert "CREATE MATERIALIZED VIEW" in sql
        assert "`main`.`sales`.`mv_orders`" in sql, "identifiers must be quoted"

    def test_streaming_table_falls_back_with_the_column_list(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
        )

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "statement_id": "stmt-1",
                    "status": {"state": "SUCCEEDED"},
                    "manifest": {"schema": {"columns": []}},
                    "result": {"data_array": [], "row_count": 0},
                }
            )
        ]
        result = _executor(local_http_server).execute(
            UCDdlPayload(
                object_type=UCObjectType.STREAMING_TABLE,
                action=UCChangeAction.CREATE,
                identifiers=("main", "sales", "st_events"),
                options={"columns": [{"name": "ts", "type_name": "TIMESTAMP"}]},
            )
        )
        assert result.terminal == "EXECUTED"
        body = json.loads(RecordingHandler.requests[-1]["body"])
        assert "CREATE STREAMING TABLE" in body.get("statement", "")
        assert "`ts`" in body.get("statement", "")

    def test_missing_required_sql_option_raises_before_any_network(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCChangeExecutionError,
            UCDdlPayload,
            UCObjectType,
        )

        with pytest.raises(UCChangeExecutionError) as excinfo:
            _executor(local_http_server).execute(
                UCDdlPayload(
                    object_type=UCObjectType.MATERIALIZED_VIEW,
                    action=UCChangeAction.CREATE,
                    identifiers=("main", "sales", "mv_orders"),
                )
            )
        assert excinfo.value.code == "DATABRICKS_DDL_EXECUTION_FAILED"
        assert RecordingHandler.requests == [], "no network for a locally-detectable error"

    def test_sql_statement_failure_is_classified(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
        )

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "statement_id": "stmt-2",
                    "status": {
                        "state": "FAILED",
                        "error": {"message": "syntax error at 'FROM'"},
                    },
                }
            )
        ]
        result = _executor(local_http_server).execute(
            UCDdlPayload(
                object_type=UCObjectType.MATERIALIZED_VIEW,
                action=UCChangeAction.CREATE,
                identifiers=("main", "sales", "mv_orders"),
                options={"query": "SELECT 1"},
            )
        )
        assert result.terminal == "FAILED"
        assert "syntax error" in result.detail


class TestExecutorFailures:
    def test_unsupported_combination_raises_with_zero_network(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCChangeExecutionError,
            UCDdlPayload,
            UCObjectType,
        )

        # 2.4: DROP is denylist-gated — the combination check fires AFTER
        # the denylist, so the pin runs under a flag-ON tenant (the
        # flag-off → DENYLISTED path is the guards suite's contract).
        with pytest.raises(UCChangeExecutionError):
            _executor(local_http_server, tenant=_flag_tenant(True)).execute(
                UCDdlPayload(
                    object_type=UCObjectType.STREAMING_TABLE,
                    action=UCChangeAction.DROP,
                    identifiers=("main", "sales", "st_events"),
                )
            )
        assert RecordingHandler.requests == []

    def test_workspace_rejection_propagates_the_classified_error(self, local_http_server):
        from hub.apps.databricks_admin.client import DatabricksApiError
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
        )

        RecordingHandler.script = [400]
        RecordingHandler.json_script = [json.dumps({"error_code": "BAD_REQUEST"})]
        with pytest.raises(DatabricksApiError):
            _executor(local_http_server).execute(
                UCDdlPayload(
                    object_type=UCObjectType.CATALOG,
                    action=UCChangeAction.CREATE,
                    identifiers=("main",),
                )
            )


class TestDdlPinDiscipline:
    def test_every_ddl_pin_is_versioned_2_1(self):
        from hub.apps.databricks_admin.api_paths import API_PATH_VERSIONS, API_PATHS
        from hub.apps.databricks_admin.uc_change_executor import _REST_PINS

        for pin in _REST_PINS.values():
            operation, _method, _body_builder, _path_params_fn = pin
            assert operation in API_PATHS, f"{operation} missing from API_PATHS"
            assert API_PATHS[operation].startswith("/api/2.1/unity-catalog/"), operation
            assert API_PATH_VERSIONS[operation] == "2.1", operation

    def test_unknown_ddl_operation_fails_at_development_time(self):
        from hub.apps.databricks_admin.client import DatabricksApiClient

        with pytest.raises(ValueError, match=r"Unknown Databricks API operation"):
            DatabricksApiClient(
                host=REAL_HOST, tenant_id="t1", credential_config={"token": "x"}
            ).request("POST", "uc.not.a.real.operation", path_params={})


class TestExecutorBodyEdgeCases:
    """Task 2.11 mutmut triage — the survivors exposed REAL untested
    behavior: workspace-level identifier properties, option-key bodies,
    None-valued extras, and identifier quoting."""

    def test_workspace_level_payload_has_empty_catalog_and_schema_names(self):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
        )

        payload = UCDdlPayload(
            object_type=UCObjectType.CATALOG,
            action=UCChangeAction.CREATE,
            identifiers=("main",),
        )
        assert payload.catalog_name == ""
        assert payload.schema_name == ""
        assert payload.name == "main"

    def test_create_view_body_carries_the_view_definition(self):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
            _create_view,
        )

        payload = UCDdlPayload(
            object_type=UCObjectType.VIEW,
            action=UCChangeAction.CREATE,
            identifiers=("main", "sales", "v_orders"),
            options={"view_definition": "SELECT * FROM main.sales.orders"},
        )
        body = _create_view(payload)
        assert body["view_definition"] == "SELECT * FROM main.sales.orders"

    def test_external_location_body_carries_url_and_credential(self):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
            _create_external_location,
        )

        payload = UCDdlPayload(
            object_type=UCObjectType.EXTERNAL_LOCATION,
            action=UCChangeAction.CREATE,
            identifiers=("raw_landing",),
            options={"url": "s3://bucket/landing", "credential_name": "hub-s3"},
        )
        body = _create_external_location(payload)
        assert body["url"] == "s3://bucket/landing"
        assert body["credential_name"] == "hub-s3"

    def test_create_body_skips_none_valued_extras(self):
        from hub.apps.databricks_admin.uc_change_executor import (
            UCChangeAction,
            UCDdlPayload,
            UCObjectType,
            _create_body,
        )

        payload = UCDdlPayload(
            object_type=UCObjectType.TABLE,
            action=UCChangeAction.CREATE,
            identifiers=("main", "sales", "t"),
        )
        body = _create_body(payload, {"optional_option": None})
        assert "optional_option" not in body

    def test_quote_escapes_embedded_backticks(self):
        from hub.apps.databricks_admin.uc_change_executor import _quote

        assert _quote("plain") == "`plain`"
        assert _quote("tick`name") == "`tick``name`"
