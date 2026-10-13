"""TDD pins for the UC-write audit contract (openspec add-databricks-uc-write
task 2.9) — the "UC Write Observability" requirement.

The contracts pinned here:

- One audit row per lifecycle transition (resource_type=
  ``DATABRICKS_UC_CHANGE``, action REQUESTED/APPROVED/REJECTED/
  EXECUTING/EXECUTED/FAILED/ROLLED_BACK) with tenant, workspace,
  requester/approver attribution — including the reaper's terminal
  resolutions (FAILED/ROLLED_BACK, system actor).
- DDL payloads carry IDENTIFIERS ONLY — ``definition.options`` can hold
  credential material (storage-credential CREATEs); it must never reach
  an audit row.
- The grants bridge emits PLAN_COMPUTED / APPLIED / REVOKED / VERIFIED
  (resource_type=``DATABRICKS_GRANT``, workspace-scoped).
- The ``databricks.uc.change.execute`` chain's stage check carries the
  machine-readable ``DATABRICKS_DDL_APPROVAL_REQUIRED`` (403) code.

No mocks: real Postgres rows (requests/policies/bindings), the REAL
service + reaper + chain runner, the PRODUCTION client against a REAL
local HTTP server for the bridge/reaper legs, and REAL audit rows read
back from the DB.
"""

import json
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.models import (
    UCChangeAction,
    UCChangeRequestStatus,
    UCObjectType,
)
from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_change_chains import _seed_request
from hub.apps.databricks_admin.tests.test_uc_change_reaper import (
    _make_request,
    _ReaperSetupMixin,
)
from hub.apps.databricks_admin.tests.test_uc_change_requests import (
    _make_user,
    _make_workspace,
)
from hub.apps.databricks_admin.tests.test_uc_grants_bridge import _policy, _seed
from hub.apps.tenants.tests.factories import activate_billing
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _seed_lifecycle():
    """A tenant with a requester, an approver, and an ACTIVE workspace."""
    require_dns()
    tenant = TenantFactory.create_tenant()
    activate_billing(tenant)
    requester = _make_user(tenant, f"audit-req-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    approver = _make_user(tenant, f"audit-app-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    workspace = _make_workspace(tenant)
    return tenant, requester, approver, workspace


def _create(tenant, requester, workspace, *, requires_approval=True, options=None, **overrides):
    """A DRAFT request through the 2.2 SERVICE (the emission owner)."""
    from hub.apps.databricks_admin.uc_changes import create_change_request

    defaults = {
        "tenant": tenant,
        "workspace": workspace,
        "requested_by": requester,
        "change_type": UCChangeAction.CREATE,
        "securable_type": UCObjectType.TABLE,
        "full_name": "main.sales.orders",
        "definition": {
            "identifiers": ["main", "sales", "orders"],
            "options": options or {},
        },
        "requires_approval": requires_approval,
    }
    defaults.update(overrides)
    return create_change_request(**defaults)


def _rows(request_row, action=None):
    """The request's change-audit rows, oldest first (the shared test DB
    accumulates foreign rows — scope by resource_type AND resource_id)."""
    from hub.apps.audit.models import AuditEvent

    qs = AuditEvent.objects.filter(resource_type="DATABRICKS_UC_CHANGE", resource_id=request_row.id)
    if action is not None:
        qs = qs.filter(action=action)
    return qs.order_by("timestamp")


class TestUcChangeLifecycleAudit(TestCase):
    def test_create_emits_nothing_but_submit_emits_requested(self):
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        tenant, requester, _approver, workspace = _seed_lifecycle()
        request = _create(tenant, requester, workspace)
        # DRAFT creation is not a lifecycle EVENT (the transition set
        # starts at submission) — no row may exist yet.
        assert _rows(request).count() == 0

        submit_change_request(change_request=request)
        rows = _rows(request, action="REQUESTED")
        assert rows.count() == 1, "submission must emit one REQUESTED row"
        row = rows.get()
        assert row.tenant_id == tenant.id
        assert row.actor_user_id == requester.id, "the requester is attributed"
        details = row.details_json
        assert details["full_name"] == "main.sales.orders"
        assert details["object_type"] == "TABLE"
        assert details["change_action"] == "CREATE"
        assert details["target_status"] == "PENDING_APPROVAL"
        assert "options" not in details, "DDL options never reach audit rows"

    def test_submit_without_approval_flags_the_skip(self):
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        tenant, requester, _approver, workspace = _seed_lifecycle()
        request = _create(tenant, requester, workspace, requires_approval=False)
        submit_change_request(change_request=request)

        row = _rows(request, action="REQUESTED").get()
        assert row.details_json["target_status"] == "APPROVED"
        assert row.details_json["approval_skipped"] is True

    def test_approve_emits_approved_with_approver_attribution(self):
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            submit_change_request,
        )

        tenant, requester, approver, workspace = _seed_lifecycle()
        request = _create(tenant, requester, workspace)
        submit_change_request(change_request=request)
        approve_change_request(change_request=request, approver=approver)

        rows = _rows(request, action="APPROVED")
        assert rows.count() == 1
        row = rows.get()
        assert row.tenant_id == tenant.id
        assert row.actor_user_id == approver.id, "the approver is attributed"
        assert row.details_json["final"] is True

    def test_reject_emits_rejected_with_reason(self):
        from hub.apps.databricks_admin.uc_changes import (
            reject_change_request,
            submit_change_request,
        )

        tenant, requester, approver, workspace = _seed_lifecycle()
        request = _create(tenant, requester, workspace)
        submit_change_request(change_request=request)
        reject_change_request(
            change_request=request, approver=approver, reason="schema drift detected"
        )

        row = _rows(request, action="REJECTED").get()
        assert row.actor_user_id == approver.id
        assert row.details_json["reason"] == "schema drift detected"

    def test_execution_marks_emit_executing_and_executed(self):
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            mark_executed,
            mark_executing,
            submit_change_request,
        )

        tenant, requester, approver, workspace = _seed_lifecycle()
        request = _create(tenant, requester, workspace)
        submit_change_request(change_request=request)
        approve_change_request(change_request=request, approver=approver)

        mark_executing(change_request=request)
        executing = _rows(request, action="EXECUTING").get()
        assert executing.actor_user_id is None, "the executor is the system"

        mark_executed(change_request=request, executor=requester)
        executed = _rows(request, action="EXECUTED").get()
        assert executed.actor_user_id == requester.id, "the executor is attributed"

    def test_failed_and_rolled_back_emit_rows(self):
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            mark_executing,
            mark_failed,
            mark_rolled_back,
            submit_change_request,
        )

        tenant, requester, approver, workspace = _seed_lifecycle()
        request = _create(tenant, requester, workspace)
        submit_change_request(change_request=request)
        approve_change_request(change_request=request, approver=approver)
        mark_executing(change_request=request)

        mark_failed(change_request=request, error="workspace rejected the DDL")
        failed = _rows(request, action="FAILED").get()
        assert failed.details_json["error"] == "workspace rejected the DDL"

        mark_rolled_back(change_request=request, actor=requester)
        rolled_back = _rows(request, action="ROLLED_BACK").get()
        assert rolled_back.actor_user_id == requester.id

    def test_full_flow_emits_one_row_per_transition(self):
        """The spec scenario: DRAFT → PENDING_APPROVAL → APPROVED →
        EXECUTING → EXECUTED yields exactly one row per transition, in
        order."""
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            mark_executed,
            mark_executing,
            submit_change_request,
        )

        tenant, requester, approver, workspace = _seed_lifecycle()
        request = _create(tenant, requester, workspace)
        submit_change_request(change_request=request)
        approve_change_request(change_request=request, approver=approver)
        mark_executing(change_request=request)
        mark_executed(change_request=request, executor=requester)

        assert [row.action for row in _rows(request)] == [
            "REQUESTED",
            "APPROVED",
            "EXECUTING",
            "EXECUTED",
        ]
        assert all(row.tenant_id == tenant.id for row in _rows(request))

    def test_audit_details_never_carry_ddl_options(self):
        """IDENTIFIERS ONLY: a storage-credential CREATE carries
        credential material in its options — no audit row may hold it."""
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        tenant, requester, _approver, workspace = _seed_lifecycle()
        request = _create(
            tenant,
            requester,
            workspace,
            securable_type=UCObjectType.STORAGE_CREDENTIAL,
            full_name="main.svc",
            definition={
                "identifiers": ["main", "svc"],
                "options": {
                    "aws_iam_role": "arn:aws:iam::123456789012:role/ingest",
                    "credential": "s3-secret-material-abc123",
                },
            },
        )
        submit_change_request(change_request=request)

        for row in _rows(request):
            assert "options" not in row.details_json
            serialized = json.dumps(row.details_json)
            assert "s3-secret-material-abc123" not in serialized
            assert "arn:aws:iam" not in serialized


class TestReaperTerminalAudit(TestCase, _ReaperSetupMixin):
    def setUp(self):
        self._setup()

    def test_destructive_stuck_request_emits_failed_row(self):
        from hub.apps.databricks_admin.uc_change_reaper import resolve_stuck_request

        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.DROP,
            securable_type=UCObjectType.CATALOG,
            identifiers=("main",),
        )
        result = resolve_stuck_request(request)
        assert result["terminal"] == UCChangeRequestStatus.FAILED

        row = _rows(request, action="FAILED").first()
        assert row is not None, "the reaper's terminal resolution must be audited"
        assert row.tenant_id == self.tenant.id
        assert row.actor_user_id is None, "the reaper is a system actor"
        assert "never auto-rolled-back" in row.details_json["reason"]

    def test_create_rollback_emits_rolled_back_row(self):
        from hub.apps.databricks_admin.uc_change_reaper import resolve_stuck_request

        port = self._start_local_server()
        self._patch_factory(port)
        request = _make_request(
            self.tenant,
            self.workspace,
            self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            identifiers=("main", "sales", "orders"),
        )
        result = resolve_stuck_request(request)
        assert result["terminal"] == UCChangeRequestStatus.ROLLED_BACK

        row = _rows(request, action="ROLLED_BACK").first()
        assert row is not None, "the reaper's rollback must be audited"
        assert row.tenant_id == self.tenant.id
        assert row.actor_user_id is None
        # Identifiers only — the compensating DROP's details never leak
        # the request's options.
        assert row.details_json["full_name"] == "main.sales.orders"


class TestGrantBridgeAudit:
    def _grant_rows(self, workspace, action):
        from hub.apps.audit.models import AuditEvent

        return AuditEvent.objects.filter(
            resource_type="DATABRICKS_GRANT", action=action, tenant=workspace.tenant
        ).order_by("timestamp")

    def test_plan_emits_plan_computed_row(self):
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
        # One policy block → ONE intended entry (its privileges are a
        # list — the 2.6 planner's contract).
        assert len(intended) == 1

        rows = self._grant_rows(workspace, "PLAN_COMPUTED")
        assert rows.count() == 1
        details = rows.get().details_json
        assert details["grant_count"] == 1
        assert "main.sales.orders" in details["securables"]
        assert "data-team" in details["principals"]

    def test_rest_apply_emits_applied_and_revoked_rows(self, local_http_server):
        from hub.apps.databricks_admin.uc_grants_bridge import apply_grant_delta

        workspace, _principal, client, _sql = _seed(local_http_server)
        RecordingHandler.json_script = [json.dumps({"privilege_assignments": []})]
        result = apply_grant_delta(
            client,
            workspace=workspace,
            securable_type="TABLE",
            securable_full_name="main.sales.orders",
            changes={
                "add": [("data-team", "MODIFY")],
                "remove": [("analysts", "READ_METADATA")],
            },
        )
        assert result is not None

        applied = self._grant_rows(workspace, "APPLIED")
        revoked = self._grant_rows(workspace, "REVOKED")
        assert applied.count() == 1
        assert revoked.count() == 1
        applied_details = applied.get().details_json
        assert applied_details["securable_full_name"] == "main.sales.orders"
        assert applied_details["add_count"] == 1
        revoked_details = revoked.get().details_json
        assert revoked_details["remove_count"] == 1
        # The pairs are OBJECTS — the audit pipeline's redact_pii
        # stringifies non-dict list items, so pair-lists would arrive as
        # str() noise (the emitter's contract).
        assert revoked_details["removed"] == [
            {"principal": "analysts", "privilege": "READ_METADATA"}
        ]

    def test_sql_apply_emits_rows_for_the_fallback_leg(self, local_http_server):
        from hub.apps.databricks_admin.uc_grants_bridge import apply_grant_delta

        workspace, _principal, client, sql = _seed(local_http_server)
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "statement_id": "stmt-grant-audit",
                    "status": {"state": "SUCCEEDED"},
                    "manifest": {"schema": {"columns": []}},
                    "result": {"data_array": [], "row_count": 0},
                }
            )
        ]
        apply_grant_delta(
            client,
            workspace=workspace,
            securable_type="CATALOG",
            securable_full_name="main",
            changes={
                "add": [("data-team", "USE_CATALOG")],
                "remove": [("analysts", "USE_CATALOG")],
            },
            statement_executor=sql,
        )
        assert self._grant_rows(workspace, "APPLIED").count() == 1
        assert self._grant_rows(workspace, "REVOKED").count() == 1

    def test_verify_emits_verified_rows_for_match_and_mismatch(self, local_http_server):
        from hub.apps.databricks_admin.uc_grants_bridge import verify_grants

        workspace, _principal, client, _sql = _seed(local_http_server)
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
                expected=[("data-team", "SELECT"), ("data-team", "MODIFY")],
            )
            is True
        )
        matched = self._grant_rows(workspace, "VERIFIED")
        assert matched.count() == 1
        assert matched.get().details_json["matched"] is True
        assert matched.get().details_json["expected_count"] == 2

        RecordingHandler.json_script = [
            json.dumps(
                {"privilege_assignments": [{"principal": "data-team", "privileges": ["SELECT"]}]}
            )
        ]
        assert (
            verify_grants(
                client,
                workspace=workspace,
                securable_type="TABLE",
                securable_full_name="main.sales.orders",
                expected=[("data-team", "SELECT"), ("data-team", "MODIFY")],
            )
            is False
        )
        # Both rows share one transaction timestamp — assert the SET of
        # outcomes, not a specific row's order.
        rows = self._grant_rows(workspace, "VERIFIED")
        assert rows.count() == 2
        assert sorted(row.details_json["matched"] for row in rows) == [False, True]


class TestDdlApprovalRequired:
    def test_execute_chain_stage_check_carries_the_code(self):
        from django.db import transaction

        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request(status="DRAFT")
        with transaction.atomic():
            result = execute_chain("databricks.uc.change.execute", tenant=tenant, request=request)
        assert result["outcome"] == "FAIL"
        assert any("[DATABRICKS_DDL_APPROVAL_REQUIRED]" in err for err in result["errors"]), result[
            "errors"
        ]
