"""W2.4 (oss-release-remediation R2-D5/D6) — governance approval hardening.

Evidence pins for:

* **step-format fix** — ``{step, role, label}`` chain steps resolve their
  approvers BY ROLE at validation time (pre-fix the validator read
  ``step_def.get("approvers", [])`` — a key that never exists in that
  format — so EVERY approver was rejected);
* **chain on the live path** — ``approve_access_request`` executes the
  registered ``governance.approval.advance`` chain (pre-fix the chain was
  registered but never run: the P4 "designed-but-never-wired" class);
* **segregation of duties** — the same approver cannot clear two
  consecutive steps (pre-fix the rule's docstring promised it and the
  code never did it);
* **per-delegation usage recording (A-4)** — usage_count/last_used_at on
  the ApprovalDelegation row, incremented atomically (F()) on every use;
* **delegation role check for dict steps** — a dict step's ``role`` is
  enforced on the DELEGATOR (pre-fix only string steps were checked, so
  any delegation cleared any dict step);
* **is_active() call (A-5)** — the approval validator calls the custom
  ``User.is_active()`` METHOD (status-based), not the AbstractBaseUser
  ``is_active`` FIELD. Pre-fix the validator read ``user.is_active`` —
  which the User model SHADOWS with the method, so the bound method was
  truthy and the inactive check was vacuously green forever;
* **reject row lock (A-6)** — the reject path takes the same
  ``select_for_update`` row lock as approve (pre-fix two concurrent
  rejects both passed validation and both wrote);
* **dangling-approver re-routing (A-7)** — when a step's role resolves to
  ZERO eligible users, the request is re-routed to the tenant's
  TENANT_ADMINs instead of being stuck forever (pre-fix: nobody was
  authorized, not even admins);
* **KYC in the finalizer** — the order-approval finalizer checks the
  consumer tenant's KYC before approving the order (pre-fix the
  governance-driven path bypassed the marketplace view's KYC check);
* **marketplace approve delegates** — the marketplace approve action
  routes a linked PENDING AccessRequest through
  ``GovernanceService.approve_access_request`` (pre-fix it wrote
  ``status=APPROVED`` directly, skipping every governance check).

NO MOCKS at contract boundaries: real Postgres, real ORM, real services,
real business rules, real chains — the same convention as
``test_phase_272_multi_step_integration.py``. The concurrency pin uses
TransactionTestCase + real threads (TestCase rows are invisible to
sibling threads).
"""

from __future__ import annotations

import threading
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.governance.models import (
    AccessRequest,
    AccessRequestStatus,
    ApprovalDelegation,
)
from hub.apps.governance.services import GovernanceService
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
UserModel = get_user_model()


def _uid():
    return uuid.uuid4().hex[:8]


def _make_tenant(*, kyc="UNVERIFIED"):
    tenant = Tenant.objects.create(
        name=f"T-{_uid()}",
        slug=f"t-{_uid()}",
        status="ACTIVE",
        kyc_status=kyc,
    )
    _ensure_tenant_has_subscription(tenant)
    return tenant


def _ensure_tenant_has_subscription(tenant: Tenant) -> None:
    # billing is the paid layer — the sanctioned guard covers both
    # core-only absence forms (W7.1).
    try:
        from hub.apps.billing.models import Subscription, SubscriptionStatus
    except (RuntimeError, ModuleNotFoundError):
        pytest.skip("billing (paid layer) not installed in core-only mode")
    from hub.apps.tenants.models import PlanTier, TenantPlan

    if Subscription.objects.filter(
        tenant=tenant, status=SubscriptionStatus.ACTIVE
    ).exists():
        return
    plan, _ = TenantPlan.objects.get_or_create(
        slug=f"test-plan-{tenant.slug}",
        defaults={
            "name": f"Test Plan {tenant.slug}",
            "tier": PlanTier.FREE,
            "limits_json": {"max_assets": 100},
            "is_active": True,
        },
    )
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=365),
    )


def _make_user(tenant, *, email_prefix="u", role_name=None, status=UserStatus.ACTIVE):
    user = UserModel.objects.create_user(
        email=f"{email_prefix}-{_uid()}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=status,
    )
    if role_name:
        role, _ = Role.objects.get_or_create(
            tenant=tenant,
            name=role_name,
            defaults={"description": role_name},
        )
        UserRole.objects.get_or_create(user=user, role=role)
    return user


def _make_asset(tenant, created_by):
    return Asset.objects.create(
        tenant=tenant,
        key=f"asset-{_uid()}",
        name="Test Asset",
        status=AssetStatus.ACTIVE,
        created_by=created_by,
    )


def _make_access_request(tenant, requester, asset=None, *, approvers=None, chain=None):
    asset = asset or _make_asset(tenant, requester)
    ar = AccessRequest.objects.create(
        tenant=tenant,
        requested_by=requester,
        asset=asset,
        reason="W2.4 test",
        requested_access_type="READ",
        status=AccessRequestStatus.PENDING,
        approvers=approvers,
    )
    if chain is not None:
        ar.approval_workflow = chain
        ar.current_approval_step = 0
        ar.save(update_fields=["approval_workflow", "current_approval_step"])
    return ar


def _approve(tenant, ar, approver):
    return GovernanceService(
        tenant_id=str(tenant.id), user_id=str(approver.id)
    ).approve_access_request(
        access_request_id=str(ar.id),
        tenant_id=str(tenant.id),
        approver_id=str(approver.id),
    )


class StepFormatRoleResolutionTests(TestCase):
    """{step, role, label} dict steps resolve approvers by ROLE."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.requester = _make_user(self.tenant, email_prefix="req")
        self.cdo = _make_user(self.tenant, email_prefix="cdo", role_name="CDO")
        self.other = _make_user(self.tenant, email_prefix="other")

    def _dict_chain_ar(self, approvers=None):
        asset = _make_asset(self.tenant, self.requester)
        chain = [{"step": 1, "role": "CDO", "label": "CDO review"}]
        return _make_access_request(
            self.tenant, self.requester, asset, approvers=approvers, chain=chain
        )

    def test_dict_step_role_holder_is_authorized(self):
        ar = self._dict_chain_ar(approvers=[])
        result = _approve(self.tenant, ar, self.cdo)
        self.assertEqual(result.status, AccessRequestStatus.APPROVED)

    def test_dict_step_non_holder_is_rejected(self):
        ar = self._dict_chain_ar(approvers=[])
        with self.assertRaises(ServiceValidationError):
            _approve(self.tenant, ar, self.other)

    def test_legacy_approvers_key_still_supported(self):
        ar = _make_access_request(
            self.tenant,
            self.requester,
            _make_asset(self.tenant, self.requester),
            chain=[{"step": 1, "approvers": [str(self.other.id)], "required_count": 1}],
        )
        result = _approve(self.tenant, ar, self.other)
        self.assertEqual(result.status, AccessRequestStatus.APPROVED)

    def test_string_step_keeps_approvers_list_fallback(self):
        # Legacy string steps stay pinned to the AR approvers list.
        ar = _make_access_request(
            self.tenant,
            self.requester,
            _make_asset(self.tenant, self.requester),
            approvers=[str(self.cdo.id)],
            chain=["CDO"],
        )
        result = _approve(self.tenant, ar, self.cdo)
        self.assertEqual(result.status, AccessRequestStatus.APPROVED)


class SegregationOfDutiesTests(TestCase):
    """The same approver cannot clear two consecutive steps."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.requester = _make_user(self.tenant, email_prefix="req")
        self.u1 = _make_user(self.tenant, email_prefix="u1", role_name="DATA_OWNER")
        self.u2 = _make_user(self.tenant, email_prefix="u2", role_name="CDO")
        self.u3 = _make_user(self.tenant, email_prefix="u3", role_name="DPO")

    def _three_step_ar(self, approvers):
        chain = [
            {"step": 1, "role": "DATA_OWNER", "label": "Owner"},
            {"step": 2, "role": "CDO", "label": "CDO"},
            {"step": 3, "role": "DPO", "label": "DPO"},
        ]
        return _make_access_request(
            self.tenant,
            self.requester,
            _make_asset(self.tenant, self.requester),
            approvers=approvers,
            chain=chain,
        )

    def test_same_approver_cannot_clear_two_consecutive_steps(self):
        ar = self._three_step_ar([str(self.u1.id), str(self.u2.id), str(self.u3.id)])
        _approve(self.tenant, ar, self.u1)
        ar.refresh_from_db()
        self.assertEqual(ar.current_approval_step, 1)
        # u1 tries to clear the next step too — segregation blocks.
        with self.assertRaises(ServiceValidationError) as ctx:
            _approve(self.tenant, ar, self.u1)
        self.assertIn("consecutive", str(ctx.exception).lower())

    def test_different_approvers_advance_cleanly(self):
        ar = self._three_step_ar([str(self.u1.id), str(self.u2.id), str(self.u3.id)])
        _approve(self.tenant, ar, self.u1)
        _approve(self.tenant, ar, self.u2)
        result = _approve(self.tenant, ar, self.u3)
        self.assertEqual(result.status, AccessRequestStatus.APPROVED)

    def test_step_records_track_who_cleared_each_step(self):
        ar = self._three_step_ar([str(self.u1.id), str(self.u2.id), str(self.u3.id)])
        _approve(self.tenant, ar, self.u1)
        ar.refresh_from_db()
        self.assertEqual(len(ar.approval_step_records), 1)
        self.assertEqual(ar.approval_step_records[0]["cleared_by"], str(self.u1.id))
        self.assertEqual(ar.approval_step_records[0]["step"], 0)


class DanglingApproverRerouteTests(TestCase):
    """A step whose role resolves to ZERO users is re-routed, not stuck."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.requester = _make_user(self.tenant, email_prefix="req")
        self.admin = _make_user(
            self.tenant, email_prefix="adm", role_name="TENANT_ADMIN"
        )
        self.nobody = _make_user(self.tenant, email_prefix="nobody")

    def test_unassigned_role_reroutes_to_tenant_admin(self):
        ar = _make_access_request(
            self.tenant,
            self.requester,
            _make_asset(self.tenant, self.requester),
            approvers=[],
            chain=[{"step": 1, "role": "GHOST_ROLE", "label": "No holder exists"}],
        )
        result = _approve(self.tenant, ar, self.admin)
        self.assertEqual(result.status, AccessRequestStatus.APPROVED)

    def test_unassigned_role_still_rejects_unrelated_user(self):
        ar = _make_access_request(
            self.tenant,
            self.requester,
            _make_asset(self.tenant, self.requester),
            approvers=[],
            chain=[{"step": 1, "role": "GHOST_ROLE", "label": "No holder exists"}],
        )
        with self.assertRaises(ServiceValidationError):
            _approve(self.tenant, ar, self.nobody)


class DelegationUsageRecordingTests(TestCase):
    """A-4 — every delegation USE is recorded on the delegation row."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.requester = _make_user(self.tenant, email_prefix="req")
        self.delegator = _make_user(self.tenant, email_prefix="del", role_name="CDO")
        self.delegate = _make_user(self.tenant, email_prefix="deg")

    def _make_delegation(self, delegator):
        return ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=delegator,
            delegate=self.delegate,
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=1),
        )

    def _cd0_dict_step_ar(self):
        return _make_access_request(
            self.tenant,
            self.requester,
            _make_asset(self.tenant, self.requester),
            approvers=[],
            chain=[{"step": 1, "role": "CDO", "label": "CDO"}],
        )

    def test_delegation_use_increments_usage_count_and_last_used_at(self):
        delegation = self._make_delegation(self.delegator)
        _approve(self.tenant, self._cd0_dict_step_ar(), self.delegate)
        delegation.refresh_from_db()
        self.assertEqual(delegation.usage_count, 1)
        self.assertIsNotNone(delegation.last_used_at)

    def test_dict_step_enforces_role_on_delegator(self):
        # Pre-fix: the delegation role check only handled STRING steps, so a
        # delegation from a CDO-less user cleared a CDO dict step. With ONLY
        # the wrong delegation active, the approval must be rejected.
        self._make_delegation(_make_user(self.tenant, email_prefix="wrong"))
        ar = self._cd0_dict_step_ar()
        with self.assertRaises(ServiceValidationError):
            _approve(self.tenant, ar, self.delegate)

    def test_dict_step_qualifying_delegation_authorizes_among_many(self):
        # With BOTH a wrong and a right delegation active for the same
        # delegate, the role-qualifying one wins (pre-fix ``.first()``
        # picked an arbitrary row — order-dependent flake).
        self._make_delegation(_make_user(self.tenant, email_prefix="wrong"))
        right = self._make_delegation(self.delegator)
        result = _approve(self.tenant, self._cd0_dict_step_ar(), self.delegate)
        self.assertEqual(result.status, AccessRequestStatus.APPROVED)
        right.refresh_from_db()
        self.assertEqual(right.usage_count, 1)


class ActiveUserMethodTests(TestCase):
    """A-5 — the status-based User.is_active() METHOD gates approval."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.requester = _make_user(self.tenant, email_prefix="req")
        self.disabled = _make_user(
            self.tenant, email_prefix="dis", status=UserStatus.DISABLED
        )

    def test_disabled_user_cannot_approve_even_with_auth_field_true(self):
        # create_user sets the AbstractBaseUser is_active FIELD to True;
        # the custom status is DISABLED. The pre-fix validator read the
        # field-shadowing METHOD as a truthy value and let this through.
        self.assertTrue(self.disabled.is_active is not None)
        ar = _make_access_request(
            self.tenant,
            self.requester,
            _make_asset(self.tenant, self.requester),
            approvers=[str(self.disabled.id)],
        )
        with self.assertRaises(ServiceValidationError):
            _approve(self.tenant, ar, self.disabled)


class ChainExecutionTests(TestCase):
    """The registered governance.approval.advance chain runs on the live path."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.requester = _make_user(self.tenant, email_prefix="req")
        self.approver = _make_user(self.tenant, email_prefix="app")

    def test_approval_executes_the_registered_chain(self):
        ar = _make_access_request(
            self.tenant,
            self.requester,
            _make_asset(self.tenant, self.requester),
            approvers=[str(self.approver.id)],
        )
        _approve(self.tenant, ar, self.approver)
        self.assertTrue(
            AuditEvent.objects.filter(
                resource_type="RULE_CHAIN",
                action="RULE_CHAIN_COMPLETED",
                details_json__chain="governance.approval.advance",
            ).exists()
        )


class RejectLockTests(TransactionTestCase):
    """A-6 — concurrent rejects serialize: exactly one wins."""

    serialized_rollback = False

    def setUp(self):
        super().setUp()
        self.tenant = _make_tenant()
        self.requester = _make_user(self.tenant, email_prefix="req")
        self.rejector = _make_user(self.tenant, email_prefix="rej")
        self.ar = _make_access_request(
            self.tenant,
            self.requester,
            _make_asset(self.tenant, self.requester),
            approvers=[str(self.rejector.id)],
        )

    def test_concurrent_reject_exactly_one_wins(self):
        barrier = threading.Barrier(2)
        outcomes = []
        lock = threading.Lock()

        def do_reject():
            barrier.wait(timeout=10)
            try:
                # Each thread needs its own atomic block and its own DB view —
                # TransactionTestCase commits the fixture, so both threads see
                # the PENDING row and race the row lock honestly.
                with transaction.atomic():
                    GovernanceService(
                        tenant_id=str(self.tenant.id), user_id=str(self.rejector.id)
                    ).reject_access_request(
                        access_request_id=str(self.ar.id),
                        tenant_id=str(self.tenant.id),
                        approver_id=str(self.rejector.id),
                        reason="reject",
                    )
                with lock:
                    outcomes.append("ok")
            except ServiceValidationError:
                with lock:
                    outcomes.append("validation_error")

        threads = [threading.Thread(target=do_reject) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertCountEqual(outcomes, ["ok", "validation_error"])
        self.ar.refresh_from_db()
        self.assertEqual(self.ar.status, AccessRequestStatus.REJECTED)


# ── Marketplace integration ────────────────────────────────────────────


def _make_order_flow():
    """Provider tenant + REQUEST_APPROVAL listing + REQUESTED order with a
    linked PENDING AccessRequest — the marketplace approve surface."""
    # marketplace is the paid layer — the sanctioned guard covers both
    # core-only absence forms (W7.1).
    try:
        from hub.apps.marketplace.models import (
            Listing,
            ListingStatus,
            Order,
            OrderStatus,
            PricingModel,
        )
    except (RuntimeError, ModuleNotFoundError):
        pytest.skip("marketplace (paid layer) not installed in core-only mode")

    sfx = _uid()
    provider = Tenant.objects.create(
        name=f"P-{sfx}", slug=f"p-{sfx}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
    )
    consumer = Tenant.objects.create(
        name=f"C-{sfx}", slug=f"c-{sfx}", status="ACTIVE", kyc_status=KYCStatus.VERIFIED
    )
    _ensure_tenant_has_subscription(provider)
    _ensure_tenant_has_subscription(consumer)
    provider_user = UserModel.objects.create_user(
        email=f"pv-{sfx}@e.com", password="x", tenant=provider, status=UserStatus.ACTIVE
    )
    consumer_user = UserModel.objects.create_user(
        email=f"cs-{sfx}@e.com", password="x", tenant=consumer, status=UserStatus.ACTIVE
    )
    asset = Asset.objects.create(
        tenant=provider,
        key=f"as-{sfx}",
        name="A",
        status=AssetStatus.ACTIVE,
        created_by=provider_user,
    )
    listing = Listing.objects.create(
        tenant=provider,
        asset=asset,
        status=ListingStatus.PUBLISHED,
        pricing_model=PricingModel.REQUEST_APPROVAL,
        metadata_json={"title": "L", "price_amount": 5.0, "currency": "USD"},
        created_by=provider_user,
    )
    order = Order.objects.create(
        tenant=consumer,
        listing=listing,
        status=OrderStatus.REQUESTED,
        created_by=consumer_user,
    )
    ar = AccessRequest.objects.create(
        tenant=consumer,
        requested_by=consumer_user,
        asset=asset,
        reason="Marketplace access request",
        requested_access_type="READ",
        status=AccessRequestStatus.PENDING,
        approvers=[str(provider_user.id)],
    )
    order.access_request = ar
    order.save(update_fields=["access_request"])
    return provider, consumer, provider_user, order, ar


class MarketplaceApproveDelegationTests(TestCase):
    """The marketplace approve action routes the linked AR through
    GovernanceService (governance artifacts prove it ran)."""

    def setUp(self):
        (
            self.provider,
            self.consumer,
            self.provider_user,
            self.order,
            self.ar,
        ) = _make_order_flow()

    def test_marketplace_approve_delegates_to_governance_service(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.provider_user)
        r = client.post(f"/api/v1/marketplace/orders/{self.order.id}/approve/")
        self.assertEqual(r.status_code, 200, r.data)

        self.ar.refresh_from_db()
        self.assertEqual(self.ar.status, AccessRequestStatus.APPROVED)
        self.assertEqual(self.ar.approved_by, self.provider_user)
        # Governance machinery ran: step records written + chain executed.
        self.assertEqual(
            self.ar.approval_step_records[0]["cleared_by"], str(self.provider_user.id)
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="RULE_CHAIN_COMPLETED",
                details_json__chain="governance.approval.advance",
            ).exists()
        )

    def test_marketplace_approve_legacy_ar_without_approvers_still_works(self):
        # Legacy ARs created before the approvers-bridge: the marketplace
        # layer vouches for the provider and the delegation succeeds.
        from rest_framework.test import APIClient

        self.ar.approvers = []
        self.ar.save(update_fields=["approvers"])

        client = APIClient()
        client.force_authenticate(user=self.provider_user)
        r = client.post(f"/api/v1/marketplace/orders/{self.order.id}/approve/")
        self.assertEqual(r.status_code, 200, r.data)
        self.ar.refresh_from_db()
        self.assertEqual(self.ar.status, AccessRequestStatus.APPROVED)


class FinalizerKycTests(TestCase):
    """The order-approval finalizer enforces the consumer tenant's KYC."""

    def setUp(self):
        (
            self.provider,
            self.consumer,
            self.provider_user,
            self.order,
            self.ar,
        ) = _make_order_flow()
        self.consumer.kyc_status = KYCStatus.UNVERIFIED
        self.consumer.save(update_fields=["kyc_status"])

    @override_settings(MARKETPLACE_KYC_ALLOWLIST_TENANT_IDS=[])
    def test_governance_driven_approval_fails_without_consumer_kyc(self):
        # The marketplace VIEW checks KYC, but the governance-driven path
        # (final step → finalizer) bypassed it — pre-fix the order was
        # approved and fulfilled for an UNVERIFIED consumer.
        # marketplace is the paid layer — the sanctioned guard covers
        # both core-only absence forms (W7.1).
        try:
            from hub.apps.marketplace.models import OrderStatus
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("marketplace (paid layer) not installed in core-only mode")

        with self.assertRaises(ServiceValidationError) as ctx:
            _approve(self.consumer, self.ar, self.provider_user)
        self.assertIn("KYC", str(ctx.exception))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.REQUESTED)
