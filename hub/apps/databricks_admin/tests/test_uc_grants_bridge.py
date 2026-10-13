"""TDD pins for the UC grants bridge (openspec add-databricks-uc-write
task 2.6) — plan (ABAC) → diff → apply (REST PATCH; SQL fallback) →
verify, with the D5 contracts: OWNERSHIP never granted, model grants use
the FUNCTION securable, attribute-policy shadows mark OUT_OF_SYNC, and
the identity is the D12 INTERACTIVE purpose `grant_apply` (OBO).

No mocks: real Postgres policies/bindings/principals, the PRODUCTION
client against a REAL local HTTP server (exact PATCH/GET paths+bodies),
and the REAL SqlStatementExecutor for the SQL-fallback leg.
"""

import json

import pytest

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_views import _activate_billing
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _seed(port):
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.models import (
        DatabricksCloud,
        DatabricksWorkspace,
        UCPPrincipal,
        UCPPrincipalType,
    )
    from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor

    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name="ws-bridge",
        host="dbc-6710eb95-8fe1.cloud.databricks.com",
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )
    principal = UCPPrincipal.objects.create(
        workspace=workspace, name="data-team", principal_type=UCPPrincipalType.GROUP
    )
    client = DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id=str(tenant.id),
        credential_config={"token": "dapi-bridge"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
    )
    return workspace, principal, client, SqlStatementExecutor(client, warehouse_id="wh-1")


def _policy(tenant, grant_block, enabled=True):
    from hub.apps.governance.models import AccessPolicy

    return AccessPolicy.objects.create(
        tenant=tenant,
        name=f"pol-{grant_block.get('securable_full_name', 'x')}",
        conditions={"uc_grant": grant_block},
        effect="ALLOW",
        enabled=enabled,
    )


class TestGrantPlan:
    def test_plan_derives_bindings_from_policy_grant_blocks(self):
        from hub.apps.databricks_admin.uc_grants_bridge import plan_uc_grants

        workspace, _principal, _client, _sql = _seed(0)
        _policy(
            workspace.tenant,
            {
                "securable_type": "TABLE",
                "securable_full_name": "main.sales.orders",
                "principal": "data-team",
                "privileges": ["SELECT", "MODIFY"],
            },
        )
        intended = plan_uc_grants(workspace)
        assert intended == [
            {
                "securable_type": "TABLE",
                "securable_full_name": "main.sales.orders",
                "principal": "data-team",
                "privileges": ["SELECT", "MODIFY"],
            }
        ]

    def test_plan_refuses_ownership_fail_closed(self):
        from hub.apps.databricks_admin.uc_grants_bridge import (
            UCGrantBridgeError,
            plan_uc_grants,
        )

        workspace, _principal, _client, _sql = _seed(0)
        _policy(
            workspace.tenant,
            {
                "securable_type": "TABLE",
                "securable_full_name": "main.sales.orders",
                "principal": "data-team",
                "privileges": ["OWN"],
            },
        )
        with pytest.raises(UCGrantBridgeError) as excinfo:
            plan_uc_grants(workspace)
        assert excinfo.value.code == "DATABRICKS_GRANT_UNSUPPORTED"

    def test_disabled_policy_marks_existing_binding_out_of_sync(self):
        from hub.apps.databricks_admin.models import (
            UCGrantBinding,
            UCGrantBindingStatus,
            UCGrantSecurableType,
        )
        from hub.apps.databricks_admin.uc_grants_bridge import plan_uc_grants

        workspace, principal, _client, _sql = _seed(0)
        binding = UCGrantBinding.objects.create(
            workspace=workspace,
            principal=principal,
            securable_type=UCGrantSecurableType.TABLE,
            securable_full_name="main.sales.orders",
            privilege="SELECT",
            status=UCGrantBindingStatus.APPLIED,
            source_policy_id="pol-gone",
        )
        plan_uc_grants(workspace)
        binding.refresh_from_db()
        assert binding.status == UCGrantBindingStatus.OUT_OF_SYNC


class TestGrantDiff:
    def test_diff_computes_add_and_remove_sets(self):
        from hub.apps.databricks_admin.uc_grants_bridge import diff_grants

        intended = [("data-team", "SELECT"), ("data-team", "MODIFY")]
        live = [("data-team", "SELECT"), ("analysts", "READ_METADATA")]
        delta = diff_grants(intended, live)
        assert sorted(delta["add"]) == [("data-team", "MODIFY")]
        assert sorted(delta["remove"]) == [("analysts", "READ_METADATA")]


class TestGrantApply:
    def test_rest_patch_apply_hits_the_permissions_endpoint(self, local_http_server):
        from hub.apps.databricks_admin.uc_grants_bridge import apply_grant_delta

        _workspace, _principal, client, _sql = _seed(local_http_server)
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "privilege_assignments": [
                        {"principal": "data-team", "privileges": ["SELECT", "MODIFY"]}
                    ]
                }
            )
        ]
        result = apply_grant_delta(
            client,
            workspace=_workspace,
            securable_type="TABLE",
            securable_full_name="main.sales.orders",
            changes={"add": [("data-team", "MODIFY")], "remove": [("analysts", "READ_METADATA")]},
        )
        assert result is not None
        request = RecordingHandler.requests[-1]
        assert request["method"] == "PATCH"
        assert request["path"] == "/api/2.1/unity-catalog/permissions/table/main.sales.orders"
        body = json.loads(request["body"])
        assert body["changes"] == [
            {"principal": "analysts", "remove": ["READ_METADATA"]},
            {"principal": "data-team", "add": ["MODIFY"]},
        ]

    def test_model_grants_target_the_function_securable(self, local_http_server):
        from hub.apps.databricks_admin.uc_grants_bridge import apply_grant_delta

        _workspace, _principal, client, _sql = _seed(local_http_server)
        RecordingHandler.json_script = [json.dumps({"privilege_assignments": []})]
        apply_grant_delta(
            client,
            workspace=_workspace,
            securable_type="MODEL",
            securable_full_name="main.sales.churn",
            changes={"add": [("data-team", "EXECUTE")], "remove": []},
        )
        request = RecordingHandler.requests[-1]
        assert request["path"] == "/api/2.1/unity-catalog/permissions/function/main.sales.churn"

    def test_sql_fallback_grants_for_surfaces_without_rest(self, local_http_server):
        from hub.apps.databricks_admin.uc_grants_bridge import apply_grant_delta

        _workspace, _principal, client, sql = _seed(local_http_server)
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "statement_id": "stmt-grant",
                    "status": {"state": "SUCCEEDED"},
                    "manifest": {"schema": {"columns": []}},
                    "result": {"data_array": [], "row_count": 0},
                }
            )
        ]
        apply_grant_delta(
            client,
            workspace=_workspace,
            securable_type="CATALOG",
            securable_full_name="main",
            changes={"add": [("data-team", "USE_CATALOG")], "remove": []},
            statement_executor=sql,
        )
        statement_calls = [
            r for r in RecordingHandler.requests if r["path"] == "/api/2.0/sql/statements"
        ]
        assert len(statement_calls) == 1
        sql_text = json.loads(statement_calls[0]["body"]).get("statement", "")
        assert "GRANT USE_CATALOG" in sql_text
        assert "`data-team`" in sql_text


class TestGrantVerify:
    def test_verify_reads_back_and_compares(self, local_http_server):
        from hub.apps.databricks_admin.uc_grants_bridge import verify_grants

        _workspace, _principal, client, _sql = _seed(local_http_server)
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "privilege_assignments": [
                        {"principal": "data-team", "privileges": ["SELECT", "MODIFY"]}
                    ]
                }
            )
        ]
        verified = verify_grants(
            client,
            workspace=_workspace,
            securable_type="TABLE",
            securable_full_name="main.sales.orders",
            expected=[("data-team", "SELECT"), ("data-team", "MODIFY")],
        )
        assert verified is True
        request = RecordingHandler.requests[-1]
        assert request["method"] == "GET"
        assert request["path"] == "/api/2.1/unity-catalog/permissions/table/main.sales.orders"

    def test_verify_mismatch_is_reported(self, local_http_server):
        from hub.apps.databricks_admin.uc_grants_bridge import verify_grants

        _workspace, _principal, client, _sql = _seed(local_http_server)
        RecordingHandler.json_script = [
            json.dumps(
                {"privilege_assignments": [{"principal": "data-team", "privileges": ["SELECT"]}]}
            )
        ]
        assert (
            verify_grants(
                client,
                workspace=_workspace,
                securable_type="TABLE",
                securable_full_name="main.sales.orders",
                expected=[("data-team", "SELECT"), ("data-team", "MODIFY")],
            )
            is False
        )


class TestGrantApplyIdentity:
    def test_grant_apply_is_an_interactive_d12_purpose(self):
        from hub.apps.databricks_admin.identity import INTERACTIVE_PURPOSES

        assert "grant_apply" in INTERACTIVE_PURPOSES


class TestGrantPinDiscipline:
    def test_grant_pins_are_versioned_2_1(self):
        from hub.apps.databricks_admin.api_paths import API_PATH_VERSIONS, API_PATHS

        for operation in ("uc.permissions.get", "uc.grants.patch"):
            assert operation in API_PATHS, operation
            assert API_PATHS[operation].startswith("/api/2.1/unity-catalog/permissions/")
            assert API_PATH_VERSIONS[operation] == "2.1"


class TestGrantBridgeFailClosedRobustness:
    """Review-hardening pins (2.6 second review): the bridge must hold
    its fail-closed contracts for the REAL input shapes — disabled
    policies, unknown securables, junk live answers, hostile
    identifiers, empty principals."""

    def _seed(self, port):
        return _seed(port)

    def test_disabled_policy_grants_do_not_reach_the_intended_plan(self):
        from hub.apps.databricks_admin.models import UCGrantBindingStatus
        from hub.apps.databricks_admin.uc_grants_bridge import plan_uc_grants

        workspace, _principal, _client, _sql = _seed(0)
        _policy(
            workspace.tenant,
            {
                "securable_type": "TABLE",
                "securable_full_name": "main.sales.orders",
                "principal": "data-team",
                "privileges": ["SELECT"],
            },
            enabled=False,
        )
        intended = plan_uc_grants(workspace)
        assert intended == [], (
            "a DISABLED policy can no longer produce its grant — its grants "
            "must NEVER reach the intended plan (the bridge applies nothing)"
        )
        from hub.apps.databricks_admin.models import UCGrantBinding

        # Scoped to THIS workspace: the shared DB accumulates leaked
        # rows from parallel sessions (the 0.9 convention).
        binding = UCGrantBinding.objects.get(
            workspace=workspace, securable_full_name="main.sales.orders"
        )
        assert binding.status == UCGrantBindingStatus.OUT_OF_SYNC, (
            "the shadow marker still lands on the binding"
        )

    def test_unknown_securable_type_does_not_crash_the_plan(self):
        from hub.apps.databricks_admin.uc_grants_bridge import plan_uc_grants

        workspace, _principal, _client, _sql = _seed(0)
        _policy(
            workspace.tenant,
            {
                "securable_type": "BOGUS_SECURABLE",
                "securable_full_name": "main.sales.orders",
                "principal": "data-team",
                "privileges": ["SELECT"],
            },
        )
        intended = plan_uc_grants(workspace)
        assert intended == [], (
            "a securable the bridge cannot map must be SKIPPED (never applied, "
            "never crash the ABAC sweep)"
        )
        from hub.apps.databricks_admin.models import UCGrantBinding

        assert not UCGrantBinding.objects.filter(
            workspace=workspace, securable_full_name="main.sales.orders"
        ).exists(), "no binding row may be created for an unmappable securable"

    def test_non_dict_live_assignments_do_not_crash_verify(self, local_http_server):
        import json

        from hub.apps.databricks_admin.tests._http import RecordingHandler
        from hub.apps.databricks_admin.uc_grants_bridge import verify_grants

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "privilege_assignments": [
                        "junk-row",
                        {"principal": "data-team", "privileges": ["SELECT"]},
                    ]
                }
            )
        ]
        _workspace, _principal, client, _sql = _seed(local_http_server)
        # Junk rows are IGNORED (no crash); the valid assignment still
        # reads back — a REAL mismatch is reported (False), never masked,
        # never crashed.
        assert (
            verify_grants(
                client,
                workspace=_workspace,
                securable_type="TABLE",
                securable_full_name="main.sales.orders",
                expected=[("data-team", "MODIFY")],
            )
            is False
        )

    def test_sql_fallback_escapes_backticks_in_identifiers(self, local_http_server):
        import json

        from hub.apps.databricks_admin.tests._http import RecordingHandler
        from hub.apps.databricks_admin.uc_grants_bridge import apply_grant_delta

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
        _workspace, _principal, client, sql = _seed(local_http_server)
        apply_grant_delta(
            client,
            workspace=_workspace,
            securable_type="SCHEMA",
            securable_full_name="main.sales",
            changes={"add": [("group`x", "USAGE")], "remove": []},
            statement_executor=sql,
        )
        body = json.loads(RecordingHandler.requests[-1]["body"])
        assert "`group``x`" in body["statement"], (
            "the SQL fallback must DOUBLE backticks in principals "
            "(the 2.3 _quote discipline — the plan data is not "
            "identifier-validated before this leg)"
        )

    def test_unrepresentable_privilege_refuses_the_plan(self):
        from hub.apps.databricks_admin.uc_grants_bridge import (
            UCGrantBridgeError,
            plan_uc_grants,
        )

        workspace, _principal, _client, _sql = _seed(0)
        _policy(
            workspace.tenant,
            {
                "securable_type": "TABLE",
                "securable_full_name": "main.sales.orders",
                "principal": "data-team",
                "privileges": ["SELECT; DROP TABLE x"],
            },
        )
        with pytest.raises(UCGrantBridgeError):
            plan_uc_grants(workspace)

    def test_empty_principal_name_raises_without_creating_a_row(self):
        from hub.apps.databricks_admin.models import UCPPrincipal
        from hub.apps.databricks_admin.uc_grants_bridge import (
            UCGrantBridgeError,
            plan_uc_grants,
        )

        workspace, _principal, _client, _sql = _seed(0)
        _policy(
            workspace.tenant,
            {
                "securable_type": "TABLE",
                "securable_full_name": "main.sales.orders",
                "principal": "",
                "privileges": ["SELECT"],
            },
        )
        with pytest.raises(UCGrantBridgeError):
            plan_uc_grants(workspace)
        assert not UCPPrincipal.objects.filter(workspace=workspace, name="").exists(), (
            "the refusal must happen BEFORE the principal row is created — "
            "no orphan empty-name rows"
        )


class TestGrantLoopAcceptance:
    """Task 2.11 — the Phase 2 acceptance loop for grants, chained in ONE
    test: policy → plan → diff vs live → PATCH apply → verify reads back
    TRUE — every leg real (scripted HTTP, real Postgres rows)."""

    def test_plan_diff_apply_verify_loop(self, local_http_server):
        from hub.apps.databricks_admin.uc_grants_bridge import (
            apply_grant_delta,
            diff_grants,
            plan_uc_grants,
            verify_grants,
        )

        workspace, _principal, client, _sql = _seed(local_http_server)
        _policy(
            workspace.tenant,
            {
                "securable_type": "TABLE",
                "securable_full_name": "main.sales.orders",
                "principal": "data-team",
                "privileges": ["SELECT", "MODIFY"],
            },
        )
        intended = plan_uc_grants(workspace)
        pairs = [
            (grant["principal"], privilege)
            for grant in intended
            for privilege in grant["privileges"]
        ]
        assert pairs == [("data-team", "SELECT"), ("data-team", "MODIFY")]

        # Live state: SELECT already granted — only MODIFY is added.
        live = [("data-team", "SELECT")]
        delta = diff_grants(pairs, live)
        assert sorted(delta["add"]) == [("data-team", "MODIFY")]
        assert delta["remove"] == []

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "privilege_assignments": [
                        {"principal": "data-team", "privileges": ["SELECT", "MODIFY"]}
                    ]
                }
            )
        ]
        apply_grant_delta(
            client,
            workspace=workspace,
            securable_type="TABLE",
            securable_full_name="main.sales.orders",
            changes=delta,
        )
        patch = RecordingHandler.requests[-1]
        assert patch["method"] == "PATCH"
        assert patch["path"] == "/api/2.1/unity-catalog/permissions/table/main.sales.orders"

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "privilege_assignments": [
                        {"principal": "data-team", "privileges": ["SELECT", "MODIFY"]}
                    ]
                }
            )
        ]
        assert (
            verify_grants(
                client,
                workspace=workspace,
                securable_type="TABLE",
                securable_full_name="main.sales.orders",
                expected=pairs,
            )
            is True
        )
