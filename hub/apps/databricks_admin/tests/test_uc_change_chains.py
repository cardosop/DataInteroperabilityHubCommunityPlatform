"""TDD pins for the UC write chains (openspec add-databricks-uc-write
task 2.7) — `databricks.uc.change.request/approve/execute` and
`databricks.grant.apply` per the Phase 274 convention.

No mocks: real Postgres rows (UCChangeRequest from 2.2, AccessPolicy
rows for the grant plan), the REAL chain runner (atomic-context
requirement included), and the REAL 2.4 guards / 2.6 planner inside the
steps. Step ordering is pinned through the failures: the denylist is
OUTERMOST on the request chain (a flag-off destructive request fails
with DENYLISTED before the identifier step runs).
"""

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

CHAIN_NAMES = (
    "databricks.uc.change.request",
    "databricks.uc.change.approve",
    "databricks.uc.change.execute",
    "databricks.grant.apply",
)


def _seed_request(
    status="DRAFT", change_type="CREATE", securable_type="TABLE", full_name="main.sales.orders_v2"
):
    require_dns()
    from hub.apps.databricks_admin.models import (
        DatabricksCloud,
        DatabricksWorkspace,
        UCChangeRequest,
        UCChangeRequestStatus,
    )

    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    requester = _make_user(
        tenant, f"chain-req-{pytest.importorskip('uuid').uuid4().hex[:8]}@test.com"
    )
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"ws-chain-{pytest.importorskip('uuid').uuid4().hex[:8]}",
        host="dbc-6710eb95-8fe1.cloud.databricks.com",
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )
    request = UCChangeRequest.objects.create(
        tenant=tenant,
        workspace=workspace,
        requested_by=requester,
        change_type=change_type,
        securable_type=securable_type,
        full_name=full_name,
        status=UCChangeRequestStatus(status),
        definition={"identifiers": full_name.split("."), "options": {}},
    )
    return tenant, requester, workspace, request


class TestChainRegistration:
    def test_all_four_chains_are_registered(self):
        from hub.apps.core.business_rules.chains import get_chain

        for name in CHAIN_NAMES:
            assert get_chain(name) is not None, f"{name} not registered"


class TestAtomicContextRequirement:
    @pytest.mark.parametrize("chain_name", CHAIN_NAMES)
    def test_chain_requires_an_active_transaction(self, chain_name):
        from hub.apps.core.business_rules.chains import execute_chain

        with pytest.raises(RuntimeError, match="requires an active transaction"):
            execute_chain(chain_name, tenant_id="t1")


class TestUCChangeRequestChain:
    def test_valid_create_request_passes(self):
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request()
        with transaction.atomic():
            result = execute_chain("databricks.uc.change.request", tenant=tenant, request=request)
        assert result["outcome"] == "PASS", result

    def test_flag_off_destructive_request_fails_with_the_denylist_code(self):
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request(
            change_type="DROP", securable_type="CATALOG", full_name="main"
        )
        with transaction.atomic():
            result = execute_chain("databricks.uc.change.request", tenant=tenant, request=request)
        assert result["outcome"] == "FAIL"
        assert any("DATABRICKS_DDL_DENYLISTED" in err for err in result["errors"])

    def test_invalid_identifier_fails(self):
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request(full_name="main.sales.bad-name!")
        with transaction.atomic():
            result = execute_chain("databricks.uc.change.request", tenant=tenant, request=request)
        assert result["outcome"] == "FAIL"
        assert any("DATABRICKS_DDL_INVALID_IDENTIFIER" in err for err in result["errors"])


class TestUCChangeApproveChain:
    def test_authorized_approver_passes(self):
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, requester, _workspace, request = _seed_request(status="PENDING_APPROVAL")
        request.approval_workflow = [
            {"step": 1, "approvers": [str(requester.id)], "status": "PENDING"}
        ]
        request.save(update_fields=["approval_workflow"])
        approver = _make_user(
            tenant, f"chain-approver-{__import__('uuid').uuid4().hex[:8]}@test.com"
        )
        with transaction.atomic():
            result = execute_chain(
                "databricks.uc.change.approve",
                tenant=tenant,
                request=request,
                approver=approver,
            )
        assert result["outcome"] == "FAIL", result  # approver not in the workflow

    def test_workflow_approver_passes(self):
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request(status="PENDING_APPROVAL")
        approver = _make_user(tenant, f"chain-wf-{__import__('uuid').uuid4().hex[:8]}@test.com")
        request.approval_workflow = [
            {"step": 1, "approvers": [str(approver.id)], "status": "PENDING"}
        ]
        request.save(update_fields=["approval_workflow"])
        with transaction.atomic():
            result = execute_chain(
                "databricks.uc.change.approve",
                tenant=tenant,
                request=request,
                approver=approver,
            )
        assert result["outcome"] == "PASS", result

    def test_draft_request_fails_the_stage_step(self):
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request(status="DRAFT")
        approver = _make_user(tenant, f"chain-stage-{__import__('uuid').uuid4().hex[:8]}@test.com")
        with transaction.atomic():
            result = execute_chain(
                "databricks.uc.change.approve",
                tenant=tenant,
                request=request,
                approver=approver,
            )
        assert result["outcome"] == "FAIL"
        assert any("PENDING_APPROVAL" in err for err in result["errors"])

    def test_pending_next_approver_stage_passes_validation(self):
        """272.4 — the intermediate multi-step state is approvable too
        (the 2.2 service's approvable set includes PENDING_NEXT_APPROVER;
        the chain must not be stricter than the service it guards)."""
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request(status="PENDING_NEXT_APPROVER")
        approver = _make_user(tenant, f"chain-next-{__import__('uuid').uuid4().hex[:8]}@test.com")
        request.approval_workflow = [
            {"step": 1, "approvers": ["someone-else"], "status": "APPROVED"},
            {"step": 2, "approvers": [str(approver.id)], "status": "PENDING"},
        ]
        request.current_approval_step = 1
        request.save(update_fields=["approval_workflow", "current_approval_step"])
        with transaction.atomic():
            result = execute_chain(
                "databricks.uc.change.approve",
                tenant=tenant,
                request=request,
                approver=approver,
            )
        assert result["outcome"] == "PASS", result

    def test_delegated_approver_passes_via_active_delegation(self):
        """272.6 — the chain must reuse the SERVICE's delegation logic
        (an active ApprovalDelegation from an authorized step approver
        lets the delegate through)."""
        from hub.apps.core.business_rules.chains import execute_chain
        from hub.apps.governance.models import ApprovalDelegation

        tenant, requester, _workspace, request = _seed_request(status="PENDING_APPROVAL")
        request.approval_workflow = [
            {"step": 1, "approvers": [str(requester.id)], "status": "PENDING"}
        ]
        request.save(update_fields=["approval_workflow"])
        delegate = _make_user(
            tenant, f"chain-delegate-{__import__('uuid').uuid4().hex[:8]}@test.com"
        )
        now = timezone.now()
        ApprovalDelegation.objects.create(
            tenant=tenant,
            delegator=requester,
            delegate=delegate,
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2),
            reason="chain review pin",
        )
        with transaction.atomic():
            result = execute_chain(
                "databricks.uc.change.approve",
                tenant=tenant,
                request=request,
                approver=delegate,
            )
        assert result["outcome"] == "PASS", result

    def test_approve_failures_carry_distinct_codes(self):
        """Guard failures route on DISTINCT machine-readable codes (the
        DONE note's own claim) — a stage violation is not an invalid
        identifier, an unauthorized approver is not a stage violation."""
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request(status="DRAFT")
        approver = _make_user(tenant, f"chain-code-{__import__('uuid').uuid4().hex[:8]}@test.com")
        with transaction.atomic():
            result = execute_chain(
                "databricks.uc.change.approve",
                tenant=tenant,
                request=request,
                approver=approver,
            )
        assert result["outcome"] == "FAIL"
        assert any("uc_change_not_approvable" in err for err in result["errors"]), result

        tenant2, _requester2, _workspace2, request2 = _seed_request(status="PENDING_APPROVAL")
        stranger = _make_user(
            tenant2, f"chain-stranger-{__import__('uuid').uuid4().hex[:8]}@test.com"
        )
        with transaction.atomic():
            result = execute_chain(
                "databricks.uc.change.approve",
                tenant=tenant2,
                request=request2,
                approver=stranger,
            )
        assert result["outcome"] == "FAIL"
        assert any("uc_change_approver_unauthorized" in err for err in result["errors"]), result


class TestUCChangeExecuteChain:
    def test_approved_request_passes(self):
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request(status="APPROVED")
        with transaction.atomic():
            result = execute_chain("databricks.uc.change.execute", tenant=tenant, request=request)
        assert result["outcome"] == "PASS", result

    def test_draft_request_fails_the_stage_check(self):
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _requester, _workspace, request = _seed_request(status="DRAFT")
        with transaction.atomic():
            result = execute_chain("databricks.uc.change.execute", tenant=tenant, request=request)
        assert result["outcome"] == "FAIL"
        assert any("APPROVED" in err for err in result["errors"])


class TestGrantApplyChain:
    def test_valid_plan_passes_and_stashes_the_plan(self):
        from hub.apps.core.business_rules.base import RuleExecutionContext
        from hub.apps.core.business_rules.chains import execute_chain
        from hub.apps.governance.models import AccessPolicy

        require_dns()
        tenant = TenantFactory.create_tenant()
        _activate_billing(tenant)
        from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

        workspace = DatabricksWorkspace.objects.create(
            tenant=tenant,
            name="ws-grant-chain",
            host="dbc-6710eb95-8fe1.cloud.databricks.com",
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status="ACTIVE",
        )
        AccessPolicy.objects.create(
            tenant=tenant,
            name="pol-grant-chain",
            conditions={
                "uc_grant": {
                    "securable_type": "TABLE",
                    "securable_full_name": "main.sales.orders",
                    "principal": "data-team",
                    "privileges": ["SELECT"],
                }
            },
            effect="ALLOW",
        )
        ctx = RuleExecutionContext(tenant_id=str(tenant.id))
        with transaction.atomic():
            result = execute_chain(
                "databricks.grant.apply", context=ctx, tenant=tenant, workspace=workspace
            )
        assert result["outcome"] == "PASS", result
        assert ctx.metadata.get("uc_grant_plan")

    def test_ownership_plan_fails_with_the_grant_code(self):
        from hub.apps.core.business_rules.chains import execute_chain
        from hub.apps.governance.models import AccessPolicy

        require_dns()
        tenant = TenantFactory.create_tenant()
        _activate_billing(tenant)
        from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

        workspace = DatabricksWorkspace.objects.create(
            tenant=tenant,
            name="ws-grant-own",
            host="dbc-6710eb95-8fe1.cloud.databricks.com",
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status="ACTIVE",
        )
        AccessPolicy.objects.create(
            tenant=tenant,
            name="pol-grant-own",
            conditions={
                "uc_grant": {
                    "securable_type": "TABLE",
                    "securable_full_name": "main.sales.orders",
                    "principal": "data-team",
                    "privileges": ["OWN"],
                }
            },
            effect="ALLOW",
        )
        with transaction.atomic():
            result = execute_chain("databricks.grant.apply", tenant=tenant, workspace=workspace)
        assert result["outcome"] == "FAIL"
        assert any("DATABRICKS_GRANT_UNSUPPORTED" in err for err in result["errors"])
