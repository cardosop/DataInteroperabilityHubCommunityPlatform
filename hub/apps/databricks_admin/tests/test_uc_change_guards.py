"""TDD pins for the DDL safety guards (openspec add-databricks-uc-write
task 2.4) — denylist, identifier regex, CREATE idempotency.

The three D3 guards are fail-closed and structural:

1. DENYLIST — the destructive family ((type, DROP) for every securable)
   requires the ``databricks_uc_destructive_ddl_enabled`` tenant flag
   (DRAFT, default-off). The denylist is the OUTERMOST guard: a
   flag-off tenant is rejected with ``DATABRICKS_DDL_DENYLISTED`` BEFORE
   identifier validation, BEFORE the unsupported-combination check, and
   with ZERO network calls. An unknown/missing tenant fails closed too.

2. IDENTIFIER REGEX — a UC pattern per securable level
   (catalog/schema/table/view/volume/model/alias), applied at request
   time (the exported ``validate_uc_identifier``) AND re-validated at
   EXECUTE time inside ``UCChangeExecutor.execute`` — malformed
   identifiers raise ``DATABRICKS_DDL_INVALID_IDENTIFIER`` with ZERO
   network calls (identifiers can never be injected past the executor).

3. IDEMPOTENCY — existence-check-by-name before CREATE: a retried
   CREATE whose name already exists in the workspace's list answer is a
   NO-OP (terminal ``SKIPPED``) with NO mutation call — only the pinned
   LIST request happened.

No mocks: real Postgres tenants for the flag, the PRODUCTION client in
transport mode against a REAL local HTTP server for every
network-observable assertion (request paths/query params counted on the
recorded server).
"""

import json

import pytest

from hub.apps.databricks_admin.tests._http import RecordingHandler
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _tenant(flag):
    tenant = TenantFactory.create_tenant()
    if flag is not None:
        tenant.databricks_uc_destructive_ddl_enabled = flag
        tenant.save(update_fields=["databricks_uc_destructive_ddl_enabled"])
    return tenant


def _client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id="t1",
        credential_config={"token": "dapi-guards"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
    )


def _executor(port, tenant=None):
    from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor
    from hub.apps.databricks_admin.uc_change_executor import UCChangeExecutor

    client = _client(port)
    return UCChangeExecutor(
        client=client,
        statement_executor=SqlStatementExecutor(client, warehouse_id="wh-1"),
        warehouse_id="wh-1",
        tenant=tenant,
    )


def _payload(object_type, action, identifiers, options=None):
    from hub.apps.databricks_admin.uc_change_executor import (
        UCChangeAction,
        UCDdlPayload,
        UCObjectType,
    )

    return UCDdlPayload(
        object_type=UCObjectType(object_type),
        action=UCChangeAction(action),
        identifiers=identifiers,
        options=options or {},
    )


class TestDenylistGuard:
    """The destructive family is flag-gated; the denylist is outermost."""

    def test_drop_catalog_requires_the_destructive_flag(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_guards import UCDdlSafetyError

        RecordingHandler.json_script = ["{}"]
        with pytest.raises(UCDdlSafetyError) as excinfo:
            _executor(local_http_server, tenant=_tenant(False)).execute(
                _payload("CATALOG", "DROP", ("main",))
            )
        assert excinfo.value.code == "DATABRICKS_DDL_DENYLISTED"
        assert RecordingHandler.requests == [], (
            "a flag-off destructive request must make ZERO network calls"
        )

    def test_the_whole_destructive_family_is_flag_gated(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_guards import UCDdlSafetyError

        RecordingHandler.json_script = ["{}"]
        executor = _executor(local_http_server, tenant=_tenant(False))
        cases = [
            ("CATALOG", ("main",)),
            ("SCHEMA", ("main", "sales")),
            ("TABLE", ("main", "sales", "orders")),
            ("VIEW", ("main", "sales", "v_orders")),
            ("MATERIALIZED_VIEW", ("main", "sales", "mv_orders")),
            ("STREAMING_TABLE", ("main", "sales", "st_events")),
            ("VOLUME", ("main", "sales", "raw")),
            ("EXTERNAL_LOCATION", ("s3_raw",)),
            ("STORAGE_CREDENTIAL", ("cred_a",)),
            ("MODEL", ("main", "sales", "churn")),
        ]
        for object_type, identifiers in cases:
            with pytest.raises(UCDdlSafetyError) as excinfo:
                executor.execute(_payload(object_type, "DROP", identifiers))
            assert excinfo.value.code == "DATABRICKS_DDL_DENYLISTED", object_type
        assert RecordingHandler.requests == [], "the whole family fails closed with zero network"

    def test_flag_on_tenant_executes_drop_catalog(self, local_http_server):
        RecordingHandler.json_script = ["{}"]
        result = _executor(local_http_server, tenant=_tenant(True)).execute(
            _payload("CATALOG", "DROP", ("main",))
        )
        assert result.terminal == "EXECUTED", result
        request = RecordingHandler.requests[-1]
        assert request["method"] == "DELETE"
        assert request["path"] == "/api/2.1/unity-catalog/catalogs/main"

    def test_missing_tenant_fails_closed(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_guards import UCDdlSafetyError

        RecordingHandler.json_script = ["{}"]
        with pytest.raises(UCDdlSafetyError) as excinfo:
            _executor(local_http_server, tenant=None).execute(
                _payload("CATALOG", "DROP", ("main",))
            )
        assert excinfo.value.code == "DATABRICKS_DDL_DENYLISTED"
        assert RecordingHandler.requests == []

    def test_create_never_hits_the_denylist(self, local_http_server):
        # CREATE is not in the destructive family — a flag-off tenant
        # still creates (the CREATE idempotency list call runs first).
        RecordingHandler.json_script = ["{}"]
        result = _executor(local_http_server, tenant=_tenant(False)).execute(
            _payload("CATALOG", "CREATE", ("main",))
        )
        assert result.terminal == "EXECUTED", result
        assert RecordingHandler.requests[-1]["method"] == "POST"

    def test_denylist_is_the_outermost_guard(self, local_http_server):
        # DROP STREAMING_TABLE is ALSO an unsupported combination — the
        # denylist must fire FIRST for a flag-off tenant (the 2.4
        # contract: the denylist is the outermost guard).
        from hub.apps.databricks_admin.uc_change_executor import UCChangeExecutionError
        from hub.apps.databricks_admin.uc_change_guards import UCDdlSafetyError

        RecordingHandler.json_script = ["{}"]
        with pytest.raises(UCDdlSafetyError) as excinfo:
            _executor(local_http_server, tenant=_tenant(False)).execute(
                _payload("STREAMING_TABLE", "DROP", ("main", "sales", "st_events"))
            )
        assert excinfo.value.code == "DATABRICKS_DDL_DENYLISTED"
        assert RecordingHandler.requests == []

        # Flag ON → the denylist passes and the COMBINATION check fires.
        with pytest.raises(UCChangeExecutionError):
            _executor(local_http_server, tenant=_tenant(True)).execute(
                _payload("STREAMING_TABLE", "DROP", ("main", "sales", "st_events"))
            )
        assert RecordingHandler.requests == []


class TestIdentifierValidation:
    """Per-level UC identifier regex — accept/reject tables."""

    def test_valid_identifiers_pass_at_every_level(self):
        from hub.apps.databricks_admin.uc_change_guards import validate_uc_identifier

        for level, value in (
            ("catalog", "main"),
            ("catalog", "_underscore_led"),
            ("schema", "sales"),
            ("schema", "a" * 255),  # the max length
            ("table", "orders"),
            ("table", "tbl_123"),
            ("view", "v_orders"),
            ("volume", "raw"),
            ("model", "churn"),
            ("external_location", "s3_raw"),
            ("storage_credential", "cred_a"),
        ):
            validate_uc_identifier(level, value)  # must not raise

    def test_alias_level_allows_hyphens(self):
        from hub.apps.databricks_admin.uc_change_guards import validate_uc_identifier

        validate_uc_identifier("alias", "champ-v2")  # Databricks model aliases allow '-'

    def test_malformed_identifiers_are_rejected(self):
        from hub.apps.databricks_admin.uc_change_guards import (
            UCDdlSafetyError,
            validate_uc_identifier,
        )

        for level, value in (
            ("catalog", "-leading-dash"),
            ("catalog", "1leading-digit"),
            ("catalog", "has space"),
            ("catalog", ""),
            ("catalog", "a" * 256),  # one over the max
            ("schema", "sch-ema"),  # hyphens are NOT valid UC identifiers
            ("table", "tbl;DROP--"),
            ("table", "tbl'quote"),
            ("view", "v_$"),
            ("volume", "raw."),
            ("model", "m/slash"),
            ("external_location", "loc?name"),
            ("storage_credential", "creds!"),
        ):
            with pytest.raises(UCDdlSafetyError) as excinfo:
                validate_uc_identifier(level, value)
            assert excinfo.value.code == "DATABRICKS_DDL_INVALID_IDENTIFIER", (level, value)
            assert value in str(excinfo.value), "the message must name the offending part"

    def test_arity_mismatch_is_rejected(self):
        from hub.apps.databricks_admin.uc_change_guards import (
            UCDdlSafetyError,
            validate_uc_identifiers,
        )

        for object_type, identifiers in (
            ("CATALOG", ("a", "b", "c")),  # catalogs take ONE part
            ("SCHEMA", ("only_catalog",)),  # schemas take TWO
            ("TABLE", ("only_catalog",)),  # tables take THREE
            ("EXTERNAL_LOCATION", ()),  # workspace-level takes ONE
        ):
            with pytest.raises(UCDdlSafetyError) as excinfo:
                validate_uc_identifiers(_payload(object_type, "CREATE", identifiers))
            assert excinfo.value.code == "DATABRICKS_DDL_INVALID_IDENTIFIER", object_type

    def test_executor_revalidates_at_execute_time_with_zero_network(self, local_http_server):
        # D3: identifiers are re-validated at EXECUTE time — a malformed
        # identifier can never be injected past the executor.
        from hub.apps.databricks_admin.uc_change_guards import UCDdlSafetyError

        RecordingHandler.json_script = ["{}"]
        with pytest.raises(UCDdlSafetyError) as excinfo:
            _executor(local_http_server, tenant=_tenant(False)).execute(
                _payload("TABLE", "CREATE", ("main", "sales", "bad;DROP--"))
            )
        assert excinfo.value.code == "DATABRICKS_DDL_INVALID_IDENTIFIER"
        assert RecordingHandler.requests == [], "malformed identifiers must never reach the network"


class TestCreateIdempotency:
    """Existence-check-by-name before CREATE — a retry is a no-op."""

    def _list_answer(self, surface, rows):
        return json.dumps({surface: rows, "next_page_token": None})

    def test_create_proceeds_when_the_name_is_absent(self, local_http_server):
        RecordingHandler.json_script = [
            self._list_answer("tables", []),  # the existence check: absent
            "{}",  # the CREATE
        ]
        result = _executor(local_http_server, tenant=_tenant(False)).execute(
            _payload("TABLE", "CREATE", ("main", "sales", "orders"))
        )
        assert result.terminal == "EXECUTED", result
        assert len(RecordingHandler.requests) == 2
        list_request, create_request = RecordingHandler.requests
        assert list_request["method"] == "GET"
        assert list_request["path"].startswith("/api/2.1/unity-catalog/tables?")
        assert create_request["method"] == "POST"

    def test_retried_create_is_a_no_op_without_a_mutation_call(self, local_http_server):
        RecordingHandler.json_script = [
            self._list_answer("tables", [{"name": "orders", "full_name": "main.sales.orders"}]),
        ]
        result = _executor(local_http_server, tenant=_tenant(False)).execute(
            _payload("TABLE", "CREATE", ("main", "sales", "orders"))
        )
        assert result.terminal == "SKIPPED", result
        assert "orders" in result.detail
        assert len(RecordingHandler.requests) == 1, (
            "a retried CREATE must make ONLY the existence-check GET — no CREATE call, no duplicate"
        )
        assert RecordingHandler.requests[0]["method"] == "GET"

    def test_existence_check_carries_the_parent_scope(self, local_http_server):
        RecordingHandler.json_script = [self._list_answer("tables", [])]
        _executor(local_http_server, tenant=_tenant(False)).execute(
            _payload("TABLE", "CREATE", ("main", "sales", "orders"))
        )
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(RecordingHandler.requests[0]["path"])
        query = parse_qs(parsed.query)
        assert query["catalog_name"] == ["main"]
        assert query["schema_name"] == ["sales"]
        assert query["max_results"] == ["100"]

        RecordingHandler.json_script = [self._list_answer("catalogs", [])]
        _executor(local_http_server, tenant=_tenant(False)).execute(
            _payload("CATALOG", "CREATE", ("main",))
        )
        parsed = urlparse(RecordingHandler.requests[-1]["path"])
        assert parse_qs(parsed.query) == {}, "a workspace-level CREATE has no parent params"

    def test_sql_only_types_skip_the_existence_check(self, local_http_server):
        # MATERIALIZED_VIEW/STREAMING_TABLE have NO UC REST list surface —
        # the idempotency check is a REST-surface feature (documented
        # limitation; the workspace's own duplicate rejection applies).
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
        result = _executor(local_http_server, tenant=_tenant(False)).execute(
            _payload(
                "MATERIALIZED_VIEW",
                "CREATE",
                ("main", "sales", "mv_orders"),
                options={"query": "SELECT 1"},
            )
        )
        assert result.terminal == "EXECUTED"
        rest_calls = [r for r in RecordingHandler.requests if r["path"].startswith("/api/2.1/")]
        assert rest_calls == [], "no REST list/DDL call for a SQL-only type"


class TestDestructiveFlagRegistration:
    """The tenant flag exists, default-off, registered in the lifecycle
    registry (the 0.12 registration contract)."""

    def test_tenant_field_defaults_off(self):
        tenant = TenantFactory.create_tenant()
        assert tenant.databricks_uc_destructive_ddl_enabled is False

    def test_flag_registered_draft_and_default_off(self):
        from hub.apps.tenants import feature_flag_registry

        flag = feature_flag_registry.get_flag("databricks_uc_destructive_ddl_enabled")
        assert flag is not None, "the flag must be registered in the lifecycle registry"
        assert flag.stage == "DRAFT"
        assert flag.default_new_tenants is False
        assert flag.default_existing_tenants is False


class TestGuardFailClosedRobustness:
    """The guards must hold fail-closed for the REAL input shapes the
    2.2 request model produces — never crash, never bypass.

    ``UCChangeRequest`` persists the enums as CHARFIELDS: the lifecycle
    hands the executor STRING-typed payloads ("CATALOG"/"DROP"), not
    enum members. A string payload must be coerced before ANY guard —
    otherwise the denylist's membership check compares strings against
    enum members, passes silently, and a destructive DROP executes on a
    flag-off tenant.
    """

    def _raw_payload(self, object_type, action, identifiers, options=None):
        from hub.apps.databricks_admin.uc_change_executor import UCDdlPayload

        # Deliberately RAW strings — the DB round-trip shape.
        return UCDdlPayload(
            object_type=object_type,
            action=action,
            identifiers=identifiers,
            options=options or {},
        )

    def test_string_typed_drop_is_denylisted_for_the_db_round_trip_shape(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_guards import UCDdlSafetyError

        RecordingHandler.json_script = ["{}"]
        with pytest.raises(UCDdlSafetyError) as excinfo:
            _executor(local_http_server, tenant=_tenant(False)).execute(
                self._raw_payload("CATALOG", "DROP", ("main",))
            )
        assert excinfo.value.code == "DATABRICKS_DDL_DENYLISTED", (
            "a string-typed DROP must NEVER bypass the denylist (enum coercion)"
        )
        assert RecordingHandler.requests == []

    def test_string_typed_create_flows_through_validation_and_the_pins(self, local_http_server):
        # The coercion must normalize BEFORE the pin lookup too — a
        # string-typed CREATE would otherwise miss its pin and surface
        # as "Unsupported".
        RecordingHandler.json_script = ["{}"]
        result = _executor(local_http_server, tenant=_tenant(False)).execute(
            self._raw_payload("TABLE", "CREATE", ("main", "sales", "orders"))
        )
        assert result.terminal == "EXECUTED", result
        assert RecordingHandler.requests[-1]["method"] == "POST"

    def test_unknown_object_type_is_refused_fail_closed(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_guards import UCDdlSafetyError

        RecordingHandler.json_script = ["{}"]
        with pytest.raises(UCDdlSafetyError):
            _executor(local_http_server, tenant=_tenant(False)).execute(
                self._raw_payload("BOGUS_TYPE", "CREATE", ("main",))
            )
        assert RecordingHandler.requests == [], (
            "an unclassifiable type must be refused, never crash, never reach the network"
        )

    def test_non_string_identifier_part_is_a_classified_rejection(self, local_http_server):
        from hub.apps.databricks_admin.uc_change_guards import UCDdlSafetyError

        RecordingHandler.json_script = ["{}"]
        with pytest.raises(UCDdlSafetyError) as excinfo:
            _executor(local_http_server, tenant=_tenant(False)).execute(
                self._raw_payload("TABLE", "CREATE", ("main", "sales", None))
            )
        assert excinfo.value.code == "DATABRICKS_DDL_INVALID_IDENTIFIER", (
            "a non-string identifier part must be the classified rejection, not a TypeError"
        )
        assert RecordingHandler.requests == []

    def test_non_dict_list_rows_do_not_crash_the_existence_check(self, local_http_server):
        # A workspace LIST answer whose rows are junk (non-dicts) must
        # not crash the existence check — unprovable rows simply do not
        # match, the CREATE proceeds, and the workspace's own duplicate
        # rejection applies.
        RecordingHandler.json_script = [
            json.dumps({"tables": ["junk-row", 42, {"name": "other"}], "next_page_token": None}),
            "{}",
        ]
        result = _executor(local_http_server, tenant=_tenant(False)).execute(
            self._raw_payload("TABLE", "CREATE", ("main", "sales", "orders"))
        )
        assert result.terminal == "EXECUTED", result
        assert len(RecordingHandler.requests) == 2
        assert RecordingHandler.requests[-1]["method"] == "POST"
