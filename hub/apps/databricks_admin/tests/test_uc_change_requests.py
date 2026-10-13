"""
Task 2.2 (openspec add-databricks-control-plane) — UCChangeRequest model +
state machine + multi-step approval (272.4) + delegation reuse (272.6).

D7 contract: ``UCChangeRequest``
DRAFT→PENDING_APPROVAL→APPROVED→EXECUTING→EXECUTED/FAILED/ROLLED_BACK,
modeled on governance's ``AccessRequest`` (NOT a reuse — access vs
mutation semantics): the required approval chain is SNAPSHOTTED into the
request on first approval (272.4) and approvals may be exercised through
an active ``ApprovalDelegation`` whose delegator is authorized for the
step (272.6).

No mocks: real Postgres rows, real users/roles/tenants/workspaces, the
REAL governance ``ApprovalDelegation`` model, and real transaction/row-lock
semantics (``select_for_update`` double-approve guard). RLS is verified at
the migration level (the policy row must exist on the live table — the
shared test DB's superuser role bypasses SQL-level RLS, the repo-wide
signature) plus service-level tenant scoping.
"""

import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone

from hub.apps.core.services.base import ValidationError
from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
    UCChangeAction,
    UCChangeRequest,
    UCChangeRequestStatus,
    UCObjectType,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.tenants.tests.factories import activate_billing
from hub.apps.users.models import Role, User, UserRole, UserStatus
from tests.factories import TenantFactory


def _make_user(tenant, email, role_name=None):
    # ``create_user`` leaves status=INVITED (the model default) — an
    # approver fixture must be ACTIVE or the approval service's REAL
    # is_active() check (a method, not an attribute) rejects them.
    email = f"{uuid.uuid4().hex[:8]}-{email}"
    user = User.objects.create_user(
        email=email, password="testpass123", tenant=tenant, status=UserStatus.ACTIVE
    )
    if role_name:
        role, _ = Role.objects.get_or_create(tenant=tenant, name=role_name)
        UserRole.objects.get_or_create(user=user, role=role)
    return user


def _make_workspace(tenant, name="ws-1", status=DatabricksWorkspaceStatus.ACTIVE):
    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=name,
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status=status,
    )


class UcChangeRequestTestBase(TestCase):
    """Real fixtures: a tenant with an ACTIVE workspace + two users."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        activate_billing(self.tenant)
        self.admin = _make_user(self.tenant, "uc-admin@test.com", "TENANT_ADMIN")
        self.member = _make_user(self.tenant, "uc-member@test.com")
        self.workspace = _make_workspace(self.tenant)
        self.other_tenant = TenantFactory.create_tenant()
        activate_billing(self.other_tenant)
        self.other_admin = _make_user(self.other_tenant, "other-admin@test.com", "TENANT_ADMIN")

    def _request(self, **overrides):
        defaults = {
            "tenant": self.tenant,
            "workspace": self.workspace,
            "requested_by": self.admin,
            "change_type": UCChangeAction.CREATE,
            "securable_type": UCObjectType.TABLE,
            "full_name": "main.sales.orders_v2",
            "definition": {
                "identifiers": ["main", "sales", "orders_v2"],
                "options": {"comment": "fact table"},
            },
        }
        defaults.update(overrides)
        return UCChangeRequest.objects.create(**defaults)

    def _active_delegation(
        self, delegator, delegate, start_offset_minutes=-30, end_offset_minutes=120
    ):
        """A REAL ApprovalDelegation window (governance 272.6) covering now
        by default; pass end_offset_minutes < 0 for an EXPIRED window."""
        from hub.apps.governance.models import ApprovalDelegation

        now = timezone.now()
        return ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=delegator,
            delegate=delegate,
            start_at=now + timedelta(minutes=start_offset_minutes),
            end_at=now + timedelta(minutes=end_offset_minutes),
            reason="test delegation",
        )


class TestUcChangeRequestModel(UcChangeRequestTestBase):
    """Model shape, defaults, and the transition spine."""

    def test_model_defaults(self):
        change_request = self._request()
        assert change_request.status == UCChangeRequestStatus.DRAFT
        assert change_request.requires_approval is True
        assert change_request.approval_workflow == []
        assert change_request.current_approval_step == 0
        assert change_request.required_approval_chain == []
        assert change_request.execution_error is None

    def test_transition_map_matches_the_documented_spine(self):
        """D7 pins the exact machine — the map is the single source of truth."""
        assert {
            UCChangeRequestStatus.DRAFT: {
                UCChangeRequestStatus.PENDING_APPROVAL,
                UCChangeRequestStatus.APPROVED,
            },
            UCChangeRequestStatus.PENDING_APPROVAL: {
                UCChangeRequestStatus.PENDING_NEXT_APPROVER,
                UCChangeRequestStatus.APPROVED,
                UCChangeRequestStatus.REJECTED,
            },
            UCChangeRequestStatus.PENDING_NEXT_APPROVER: {
                UCChangeRequestStatus.PENDING_NEXT_APPROVER,
                UCChangeRequestStatus.APPROVED,
                UCChangeRequestStatus.REJECTED,
            },
            UCChangeRequestStatus.APPROVED: {UCChangeRequestStatus.EXECUTING},
            # 2.5 contract evolution: EXECUTING → ROLLED_BACK is the
            # reaper's resolution hop (a stuck CREATE is rolled back
            # best-effort through the state machine).
            UCChangeRequestStatus.EXECUTING: {
                UCChangeRequestStatus.EXECUTED,
                UCChangeRequestStatus.FAILED,
                UCChangeRequestStatus.ROLLED_BACK,
            },
            UCChangeRequestStatus.FAILED: {UCChangeRequestStatus.ROLLED_BACK},
            UCChangeRequestStatus.EXECUTED: set(),
            UCChangeRequestStatus.ROLLED_BACK: set(),
            UCChangeRequestStatus.REJECTED: set(),
        } == UCChangeRequest.ALLOWED_TRANSITIONS

    def test_same_status_transition_is_a_noop(self):
        change_request = self._request()
        assert change_request.transition_to(UCChangeRequestStatus.DRAFT) is False

    def test_illegal_transitions_raise(self):
        """Hops outside the spine raise with the model-level code."""
        illegal_hops = [
            (UCChangeRequestStatus.DRAFT, UCChangeRequestStatus.EXECUTING),
            (UCChangeRequestStatus.PENDING_APPROVAL, UCChangeRequestStatus.EXECUTING),
            (UCChangeRequestStatus.APPROVED, UCChangeRequestStatus.ROLLED_BACK),
            (UCChangeRequestStatus.EXECUTED, UCChangeRequestStatus.EXECUTING),
            (UCChangeRequestStatus.REJECTED, UCChangeRequestStatus.APPROVED),
            (UCChangeRequestStatus.ROLLED_BACK, UCChangeRequestStatus.EXECUTING),
            (UCChangeRequestStatus.FAILED, UCChangeRequestStatus.EXECUTED),
            (UCChangeRequestStatus.EXECUTING, UCChangeRequestStatus.APPROVED),
        ]
        for from_status, to_status in illegal_hops:
            change_request = self._request(status=from_status)
            with pytest.raises(DjangoValidationError) as ctx:
                change_request.transition_to(to_status)
            assert ctx.value.code == "invalid_uc_change_status_transition", (
                from_status,
                to_status,
            )
            change_request.refresh_from_db()
            assert change_request.status == from_status, "a rejected hop must not persist"

    def test_clean_rejects_empty_full_name(self):
        # Built UNSAVED — save() itself full_cleans, so the guard must be
        # exercised on a bare instance (defense in depth for any writer).
        change_request = UCChangeRequest(
            tenant=self.tenant,
            workspace=self.workspace,
            requested_by=self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            full_name="",
            definition={"identifiers": ["x"], "options": {}},
        )
        with pytest.raises(DjangoValidationError):
            change_request.full_clean()

    def test_clean_rejects_non_dict_definition(self):
        change_request = UCChangeRequest(
            tenant=self.tenant,
            workspace=self.workspace,
            requested_by=self.admin,
            change_type=UCChangeAction.CREATE,
            securable_type=UCObjectType.TABLE,
            full_name="main.sales.x",
            definition="NOT A DICT",
        )
        with pytest.raises(DjangoValidationError):
            change_request.full_clean()


class TestCreateAndSubmit(UcChangeRequestTestBase):
    """Service-level creation + submission into the approval flow."""

    def test_create_assigns_defaults_and_persists(self):
        from hub.apps.databricks_admin.uc_changes import create_change_request

        change_request = create_change_request(
            tenant=self.tenant,
            workspace=self.workspace,
            requested_by=self.member,
            change_type=UCChangeAction.DROP,
            securable_type=UCObjectType.VOLUME,
            full_name="main.staging.raw_volume",
            definition={
                "identifiers": ["main", "staging", "raw_volume"],
                "options": {"owner": "data-eng"},
            },
        )
        assert change_request.status == UCChangeRequestStatus.DRAFT
        assert change_request.requested_by == self.member
        assert change_request.requires_approval is True
        assert UCChangeRequest.objects.filter(pk=change_request.pk).exists()

    def test_create_rejects_cross_tenant_workspace(self):
        from hub.apps.databricks_admin.uc_changes import create_change_request

        other_workspace = _make_workspace(self.other_tenant, name="ws-other")
        with pytest.raises(ValidationError) as ctx:
            create_change_request(
                tenant=self.tenant,
                workspace=other_workspace,
                requested_by=self.admin,
                change_type=UCChangeAction.CREATE,
                securable_type=UCObjectType.CATALOG,
                full_name="analytics",
                definition={"identifiers": ["analytics"], "options": {}},
            )
        assert ctx.value.code == "uc_change_workspace_tenant_mismatch"

    def test_submit_requires_approval_goes_to_pending_approval(self):
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        change_request = self._request()
        change_request = submit_change_request(change_request=change_request)
        assert change_request.status == UCChangeRequestStatus.PENDING_APPROVAL

    def test_build_ddl_payload_bridges_to_the_executor_vocabulary(self):
        """The 2.2↔2.3 hand-off: a request row becomes the executor's
        typed UCDdlPayload with no translation losses."""
        from hub.apps.databricks_admin.uc_changes import build_ddl_payload

        change_request = self._request()
        payload = build_ddl_payload(change_request)
        assert payload.object_type == UCObjectType.TABLE
        assert payload.action == UCChangeAction.CREATE
        assert payload.identifiers == ("main", "sales", "orders_v2")
        assert payload.full_name == change_request.full_name
        assert payload.options == {"comment": "fact table"}

    def test_build_ddl_payload_rejects_non_payload_definitions(self):
        from hub.apps.databricks_admin.uc_changes import build_ddl_payload

        with pytest.raises(ValidationError) as ctx:
            build_ddl_payload(self._request(definition={"name": "not-payload-shaped"}))
        assert ctx.value.code == "uc_change_invalid_definition"
        # identifiers disagreeing with full_name are rejected too.
        with pytest.raises(ValidationError) as ctx:
            build_ddl_payload(
                self._request(definition={"identifiers": ["other", "catalog", "x"], "options": {}})
            )
        assert ctx.value.code == "uc_change_invalid_definition"

    def test_submit_without_approval_goes_straight_to_approved(self):
        """requires_approval=False routes DRAFT → APPROVED (the executor's
        entry point when the tenant skips approval for the change)."""
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        change_request = self._request(requires_approval=False)
        change_request = submit_change_request(change_request=change_request)
        assert change_request.status == UCChangeRequestStatus.APPROVED

    def test_submit_twice_raises(self):
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        change_request = submit_change_request(change_request=self._request())
        with pytest.raises(ValidationError) as ctx:
            submit_change_request(change_request=change_request)
        assert ctx.value.code == "uc_change_invalid_submit_state"


class TestSingleStepApproval(UcChangeRequestTestBase):
    """The single-step flow: no chain → TENANT_ADMIN fallback (the
    AccessRequest semantics)."""

    def _submitted(self, **overrides):
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        return submit_change_request(change_request=self._request(**overrides))

    def test_single_step_approval_by_tenant_admin(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        change_request = approve_change_request(
            change_request=self._submitted(), approver=self.admin
        )
        assert change_request.status == UCChangeRequestStatus.APPROVED
        assert change_request.approved_by == self.admin
        assert change_request.approved_at is not None
        assert change_request.current_approval_step == 0
        assert change_request.approval_workflow == []

    def test_approval_rejects_non_admin_in_single_step(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=self._submitted(), approver=self.member)
        assert ctx.value.code == "uc_change_approver_unauthorized"

    def test_approval_rejects_cross_tenant_approver(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=self._submitted(), approver=self.other_admin)
        assert ctx.value.code == "uc_change_approver_tenant_mismatch"

    def test_approval_rejects_inactive_approver(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        inactive = _make_user(self.tenant, "inactive@test.com", "TENANT_ADMIN")
        inactive.status = UserStatus.DISABLED
        inactive.save(update_fields=["status", "updated_at"])
        assert not inactive.is_active()  # User.is_active is a METHOD
        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=self._submitted(), approver=inactive)
        assert ctx.value.code == "uc_change_approver_inactive"

    def test_approval_rejects_draft_status(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=self._request(), approver=self.admin)
        assert ctx.value.code == "uc_change_not_approvable"

    def test_approval_after_final_is_rejected(self):
        """The double-approve guard: an APPROVED request is not approvable."""
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        change_request = approve_change_request(
            change_request=self._submitted(), approver=self.admin
        )
        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=change_request, approver=self.admin)
        assert ctx.value.code == "uc_change_not_approvable"


class TestMultiStepApproval(UcChangeRequestTestBase):
    """272.4 — the chain snapshot + stepwise advancement."""

    def _chain(self):
        return [
            {"step": 1, "role": "TENANT_ADMIN", "label": "Admin"},
            {"step": 2, "approvers": [str(self.member.id)], "label": "Data engineer"},
        ]

    def _submitted_with_chain(self, **overrides):
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        kwargs = {"required_approval_chain": self._chain()}
        kwargs.update(overrides)
        return submit_change_request(
            change_request=self._request(**kwargs),
        )

    def test_first_approval_snapshots_chain_and_advances(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        change_request = approve_change_request(
            change_request=self._submitted_with_chain(), approver=self.admin
        )
        assert change_request.status == UCChangeRequestStatus.PENDING_NEXT_APPROVER
        assert change_request.approval_workflow == self._chain(), (
            "the required chain must be FROZEN into the workflow on first approval"
        )
        assert change_request.current_approval_step == 1

    def test_snapshot_is_frozen_against_later_chain_edits(self):
        """272.4 — after the snapshot, edits to required_approval_chain
        must not affect the in-flight workflow."""
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        change_request = approve_change_request(
            change_request=self._submitted_with_chain(), approver=self.admin
        )
        change_request.required_approval_chain = [
            {"step": 1, "approvers": [str(self.member.id)], "label": "Hijacked"}
        ]
        change_request.save(update_fields=["required_approval_chain"])
        change_request.refresh_from_db()
        assert change_request.approval_workflow == self._chain()

    def test_multi_step_final_approval_completes(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        change_request = approve_change_request(
            change_request=self._submitted_with_chain(), approver=self.admin
        )
        change_request = approve_change_request(change_request=change_request, approver=self.member)
        assert change_request.status == UCChangeRequestStatus.APPROVED
        assert change_request.current_approval_step == 2
        assert change_request.approved_by == self.member

    def test_three_step_chain_advances_intermediate_twice(self):
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            submit_change_request,
        )

        third = _make_user(self.tenant, "uc-third@test.com")
        chain = [
            {"step": 1, "role": "TENANT_ADMIN", "label": "Admin"},
            {"step": 2, "approvers": [str(self.member.id)], "label": "Member"},
            {"step": 3, "approvers": [str(third.id)], "label": "Third"},
        ]
        change_request = submit_change_request(
            change_request=self._request(required_approval_chain=chain)
        )
        change_request = approve_change_request(change_request=change_request, approver=self.admin)
        assert change_request.status == UCChangeRequestStatus.PENDING_NEXT_APPROVER
        assert change_request.current_approval_step == 1
        change_request = approve_change_request(change_request=change_request, approver=self.member)
        assert change_request.status == UCChangeRequestStatus.PENDING_NEXT_APPROVER
        assert change_request.current_approval_step == 2
        change_request = approve_change_request(change_request=change_request, approver=third)
        assert change_request.status == UCChangeRequestStatus.APPROVED
        assert change_request.current_approval_step == 3

    def test_out_of_step_approver_rejected(self):
        """Step 0 requires the TENANT_ADMIN role — the step-1 approver
        cannot jump the queue."""
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        with pytest.raises(ValidationError) as ctx:
            approve_change_request(
                change_request=self._submitted_with_chain(), approver=self.member
            )
        assert ctx.value.code == "uc_change_approver_unauthorized"

    def test_first_approval_empty_chain_is_single_step(self):
        """An EMPTY required chain collapses to single-step semantics."""
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        change_request = approve_change_request(
            change_request=self._submitted_with_chain(required_approval_chain=[]),
            approver=self.admin,
        )
        assert change_request.status == UCChangeRequestStatus.APPROVED
        assert change_request.approval_workflow == []

    def test_legacy_string_role_steps_are_honored(self):
        """String steps (the AccessPolicy legacy format) resolve as roles."""
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            submit_change_request,
        )

        change_request = submit_change_request(
            change_request=self._request(required_approval_chain=["TENANT_ADMIN", "TENANT_ADMIN"]),
        )
        change_request = approve_change_request(change_request=change_request, approver=self.admin)
        assert change_request.status == UCChangeRequestStatus.PENDING_NEXT_APPROVER
        change_request = approve_change_request(change_request=change_request, approver=self.admin)
        assert change_request.status == UCChangeRequestStatus.APPROVED


class TestDelegationReuse(UcChangeRequestTestBase):
    """272.6 — approval authority through an ACTIVE ApprovalDelegation."""

    def _chain(self):
        return [{"step": 1, "approvers": [str(self.admin.id)], "label": "Admin"}]

    def _submitted_with_chain(self, **overrides):
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        kwargs = {"required_approval_chain": self._chain()}
        kwargs.update(overrides)
        return submit_change_request(
            change_request=self._request(**kwargs),
        )

    def test_active_delegation_lets_delegate_approve(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        delegate = _make_user(self.tenant, "uc-delegate@test.com")
        self._active_delegation(self.admin, delegate)
        change_request = approve_change_request(
            change_request=self._submitted_with_chain(), approver=delegate
        )
        assert change_request.status == UCChangeRequestStatus.APPROVED

    def test_expired_delegation_rejected(self):
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        delegate = _make_user(self.tenant, "uc-delegate@test.com")
        self._active_delegation(
            self.admin, delegate, start_offset_minutes=-240, end_offset_minutes=-30
        )
        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=self._submitted_with_chain(), approver=delegate)
        assert ctx.value.code == "uc_change_approver_unauthorized"

    def test_delegation_from_unauthorized_delegator_rejected(self):
        """A delegation cannot MANUFACTURE authority: the delegator must
        themselves be authorized for the step."""
        from hub.apps.databricks_admin.uc_changes import approve_change_request

        delegate = _make_user(self.tenant, "uc-delegate@test.com")
        self._active_delegation(self.member, delegate)  # member is NOT a step approver
        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=self._submitted_with_chain(), approver=delegate)
        assert ctx.value.code == "uc_change_approver_unauthorized"

    def test_role_step_delegation_requires_the_delegate_role(self):
        """272.6 mirror of governance: for ROLE steps the delegate must
        hold the step role even when the delegator does."""
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            submit_change_request,
        )

        role_chain = [{"step": 1, "role": "TENANT_ADMIN", "label": "Admin"}]
        change_request = submit_change_request(
            change_request=self._request(required_approval_chain=role_chain),
        )
        plain_delegate = _make_user(self.tenant, "uc-delegate@test.com")  # NO role
        self._active_delegation(self.admin, plain_delegate)
        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=change_request, approver=plain_delegate)
        assert ctx.value.code == "uc_change_approver_unauthorized"
        # The same delegate WITH the role is accepted.
        role_delegate = _make_user(self.tenant, "uc-roled-delegate@test.com", "TENANT_ADMIN")
        self._active_delegation(self.admin, role_delegate)
        change_request = approve_change_request(
            change_request=change_request, approver=role_delegate
        )
        assert change_request.status == UCChangeRequestStatus.APPROVED


class TestRejection(UcChangeRequestTestBase):
    """The deny path — terminal, recorded, audit-safe."""

    def _submitted(self, **overrides):
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        return submit_change_request(change_request=self._request(**overrides))

    def test_reject_records_reason_and_is_terminal(self):
        from hub.apps.databricks_admin.uc_changes import reject_change_request

        change_request = reject_change_request(
            change_request=self._submitted(),
            approver=self.admin,
            reason="naming convention violation",
        )
        assert change_request.status == UCChangeRequestStatus.REJECTED
        assert change_request.rejection_reason == "naming convention violation"
        assert change_request.rejected_by == self.admin
        assert change_request.rejected_at is not None

    def test_reject_requires_reason(self):
        from hub.apps.databricks_admin.uc_changes import reject_change_request

        with pytest.raises(ValidationError) as ctx:
            reject_change_request(change_request=self._submitted(), approver=self.admin, reason="")
        assert ctx.value.code == "uc_change_rejection_reason_required"

    def test_approval_after_reject_raises(self):
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            reject_change_request,
        )

        change_request = reject_change_request(
            change_request=self._submitted(), approver=self.admin, reason="no"
        )
        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=change_request, approver=self.admin)
        assert ctx.value.code == "uc_change_not_approvable"


class TestExecutionSpine(UcChangeRequestTestBase):
    """APPROVED→EXECUTING→EXECUTED and APPROVED→EXECUTING→FAILED→ROLLED_BACK
    (the 2.3 executor consumes these guarded hooks)."""

    def _approved(self, **overrides):
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            submit_change_request,
        )

        change_request = submit_change_request(change_request=self._request(**overrides))
        return approve_change_request(change_request=change_request, approver=self.admin)

    def test_execution_hooks_follow_the_spine_to_executed(self):
        from hub.apps.databricks_admin.uc_changes import (
            mark_executed,
            mark_executing,
        )

        change_request = mark_executing(change_request=self._approved())
        assert change_request.status == UCChangeRequestStatus.EXECUTING
        change_request = mark_executed(change_request=change_request, executor=self.admin)
        assert change_request.status == UCChangeRequestStatus.EXECUTED
        assert change_request.executed_by == self.admin
        assert change_request.executed_at is not None

    def test_failed_then_rolled_back_spine(self):
        from hub.apps.databricks_admin.uc_changes import (
            mark_executing,
            mark_failed,
            mark_rolled_back,
        )

        change_request = mark_executing(change_request=self._approved())
        change_request = mark_failed(
            change_request=change_request,
            error="Databricks rejected the DDL (invalid options)",
        )
        assert change_request.status == UCChangeRequestStatus.FAILED
        assert "Databricks rejected" in change_request.execution_error
        change_request = mark_rolled_back(change_request=change_request, actor=self.admin)
        assert change_request.status == UCChangeRequestStatus.ROLLED_BACK
        assert change_request.rolled_back_by == self.admin
        assert change_request.rolled_back_at is not None

    def test_rollback_only_from_failed(self):
        """D7: rollback is a FAILED-state recovery — APPROVED cannot jump
        straight to ROLLED_BACK."""
        from hub.apps.databricks_admin.uc_changes import mark_rolled_back

        with pytest.raises(DjangoValidationError):
            mark_rolled_back(change_request=self._approved(), actor=self.admin)

    def test_mark_executed_on_failed_raises(self):
        from hub.apps.databricks_admin.uc_changes import (
            mark_executed,
            mark_executing,
            mark_failed,
        )

        change_request = mark_failed(
            change_request=mark_executing(change_request=self._approved()),
            error="boom",
        )
        with pytest.raises(DjangoValidationError):
            mark_executed(change_request=change_request, executor=self.admin)


class TestRlsContract(UcChangeRequestTestBase):
    """The CLAUDE.md tenant-isolation contract for the new table."""

    def test_rls_policy_is_attached_to_the_table(self):
        """The migration must have enabled RLS with the tenant_isolation
        policy on the LIVE table (pg_catalog metadata)."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relrowsecurity FROM pg_class "
                "WHERE oid = 'databricks_uc_change_requests'::regclass"
            )
            row = cursor.fetchone()
            assert row is not None, "table missing — migration not applied"
            assert row[0] is True, "RLS must be ENABLED on databricks_uc_change_requests"
            cursor.execute(
                "SELECT polname FROM pg_policy "
                "WHERE polrelid = 'databricks_uc_change_requests'::regclass"
            )
            policy_names = {r[0] for r in cursor.fetchall()}
            assert "tenant_isolation" in policy_names

    def test_service_tenant_scoping_isolates_tenants(self):
        """The service re-fetches rows tenant-scoped (select_for_update by
        id+tenant) — a request is only ever driven inside its own tenant."""
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            submit_change_request,
        )

        other_workspace = _make_workspace(self.other_tenant, name="ws-other")
        other_request = UCChangeRequest.objects.create(
            tenant=self.other_tenant,
            workspace=other_workspace,
            requested_by=self.other_admin,
            change_type=UCChangeAction.DROP,
            securable_type=UCObjectType.CATALOG,
            full_name="legacy",
            definition={"identifiers": ["legacy"], "options": {}},
        )
        other_request = submit_change_request(change_request=other_request)

        mine = submit_change_request(change_request=self._request())
        # The OTHER tenant's approver cannot approve MY pending request.
        with pytest.raises(ValidationError) as ctx:
            approve_change_request(change_request=mine, approver=self.other_admin)
        assert ctx.value.code == "uc_change_approver_tenant_mismatch"
        # My own admin then approves it normally.
        mine = approve_change_request(change_request=mine, approver=self.admin)
        assert mine.status == UCChangeRequestStatus.APPROVED
        # And the other tenant's request is untouched by my approvals.
        other_request.refresh_from_db()
        assert other_request.status == UCChangeRequestStatus.PENDING_APPROVAL
