"""P.2c — governance↔marketplace order cascades in FULL mode.

``test_core_only_order_cascades.py`` pins the core-only direction (no
provider → the finalize/revoke cascades no-op). This module pins the
inverse: with the REAL paid providers registered (the default state of a
full-mode process), approving/rejecting/revoking a governance
``AccessRequest`` drives the linked marketplace ``Order`` through its
full lifecycle — REQUESTED → APPROVED → FULFILLED with an ACTIVE
``Entitlement``; REJECTED on rejection; entitlement revoked on revoke.

The cascade resolves the order through ``get_access_request_order``
(Order.access_request — the Phase 313 paid-ward FK) and mutates it
through ``finalize_order_approval`` / ``finalize_order_rejection`` /
``revoke_order_entitlement``. Every one of those hook paths was
previously exercised by NO test (the sibling's docstring claimed
"covered by the marketplace order-flow tests" — false; marketplace
tests never drive ``GovernanceService`` with a linked order).

NO MOCKS at contract boundaries: real Postgres, real ORM, real
GovernanceService, real marketplace providers. The hooks are the ones
marketplace's ``AppConfig.ready()`` registered at boot.

on_commit note: the cascade runs inside GovernanceService's
``transaction.atomic()`` synchronously — neither the finalizers nor
``create_entitlement_for_order`` defer with ``transaction.on_commit``
(verified by grep), so plain ``TestCase`` + ``transaction=True`` is the
correct wrapper here; no ``captureOnCommitCallbacks`` needed.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.governance.services import GovernanceService
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
UserModel = get_user_model()


def _import_paid_module(module_path: str):
    """GATE-29 — core-tree tests must not statically import paid modules.

    The dynamic import runs inside the test method that needs it: the paid
    apps ARE installed in the full-mode suite where this module runs, and
    core-only runs skip in setUp before ever reaching the call.
    """
    import importlib

    return importlib.import_module(module_path)


def _make_tenant(**kwargs) -> Tenant:
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"T-{uid}",
        slug=f"t-{uid}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
        **kwargs,
    )
    # Business rules resolve plan limits through the subscription — mirror
    # the multi-step integration setup from the core-only sibling.
    _billing = _import_paid_module("hub.apps.billing.models")
    Subscription, SubscriptionStatus = _billing.Subscription, _billing.SubscriptionStatus

    if not Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE).exists():
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
    return tenant


def _make_user(tenant, role_name="DATA_OWNER") -> UserModel:
    user = UserModel.objects.create_user(
        email=f"u-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name=role_name,
        defaults={"description": role_name},
    )
    UserRole.objects.get_or_create(user=user, role=role)
    return user


class FullModeOrderCascadeTests(TestCase):
    """Approve / reject / revoke drive the linked marketplace Order."""

    def setUp(self):
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest("marketplace order cascades exist only in full mode")

        # Provider tenant owns the listing + asset (VERIFIED KYC per the
        # marketplace publish rules).
        self.provider_tenant = _make_tenant()
        self.provider_user = _make_user(self.provider_tenant, role_name="DATA_PROVIDER")
        self.asset = Asset.objects.create(
            tenant=self.provider_tenant,
            key=f"asset-{uuid.uuid4().hex[:8]}",
            name="Listable Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.provider_user,
        )

        # Consumer tenant requests access through governance.
        self.consumer_tenant = _make_tenant()
        self.consumer_user = _make_user(self.consumer_tenant)

        self.service = GovernanceService(
            tenant_id=str(self.provider_tenant.id),
            user_id=str(self.provider_user.id),
        )

    def _make_order(self, access_request) -> object:
        _marketplace = _import_paid_module("hub.apps.marketplace.models")
        Listing = _marketplace.Listing
        ListingStatus = _marketplace.ListingStatus
        Order = _marketplace.Order
        OrderStatus = _marketplace.OrderStatus
        PricingModel = _marketplace.PricingModel

        listing = Listing.objects.create(
            tenant=self.provider_tenant,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE_AUTO_APPROVE,
            metadata_json={"title": "Full-mode cascade listing"},
        )
        return Order.objects.create(
            tenant=self.consumer_tenant,
            listing=listing,
            access_request=access_request,
            status=OrderStatus.REQUESTED,
            created_by=self.consumer_user,
            metadata_json={},
        )

    def _make_request(self) -> AccessRequest:
        return AccessRequest.objects.create(
            tenant=self.provider_tenant,
            requested_by=self.consumer_user,
            asset=self.asset,
            reason="Full-mode cascade integration test",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
            approvers=[str(self.provider_user.id)],
        )

    def test_approve_drives_order_to_fulfilled_with_entitlement(self):
        _marketplace = _import_paid_module("hub.apps.marketplace.models")
        Entitlement = _marketplace.Entitlement
        EntitlementStatus = _marketplace.EntitlementStatus
        OrderStatus = _marketplace.OrderStatus

        ar = self._make_request()
        order = self._make_order(ar)

        result = self.service.approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.provider_tenant.id),
            approver_id=str(self.provider_user.id),
        )

        ar.refresh_from_db()
        order.refresh_from_db()
        assert result.status == AccessRequestStatus.APPROVED
        assert ar.status == AccessRequestStatus.APPROVED
        assert order.status == OrderStatus.FULFILLED, (
            "the paid finalizer must approve + fulfill the linked order"
        )
        entitlement = Entitlement.objects.filter(
            tenant=self.consumer_tenant,
            listing=order.listing,
            order=order,
            status=EntitlementStatus.ACTIVE,
        ).first()
        assert entitlement is not None, "approval must create an ACTIVE entitlement"

    def test_reject_drives_order_to_rejected(self):
        OrderStatus = _import_paid_module("hub.apps.marketplace.models").OrderStatus

        ar = self._make_request()
        order = self._make_order(ar)

        self.service.reject_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.provider_tenant.id),
            approver_id=str(self.provider_user.id),
            reason="Not needed",
        )

        ar.refresh_from_db()
        order.refresh_from_db()
        assert ar.status == AccessRequestStatus.REJECTED
        assert order.status == OrderStatus.REJECTED, (
            "the paid rejection finalizer must reject the linked order"
        )

    def test_revoke_revokes_the_entitlement(self):
        _marketplace = _import_paid_module("hub.apps.marketplace.models")
        Entitlement = _marketplace.Entitlement
        EntitlementStatus = _marketplace.EntitlementStatus
        OrderStatus = _marketplace.OrderStatus

        ar = self._make_request()
        order = self._make_order(ar)
        self.service.approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.provider_tenant.id),
            approver_id=str(self.provider_user.id),
        )
        order.refresh_from_db()
        assert order.status == OrderStatus.FULFILLED

        result = self.service.revoke_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.provider_tenant.id),
            revoker_id=str(self.provider_user.id),
            reason="Access no longer needed",
        )

        ar.refresh_from_db()
        assert result.status == AccessRequestStatus.REVOKED
        assert ar.status == AccessRequestStatus.REVOKED
        entitlement = Entitlement.objects.filter(
            tenant=self.consumer_tenant,
            listing=order.listing,
            order=order,
        ).first()
        assert entitlement is not None
        assert entitlement.status == EntitlementStatus.REVOKED, (
            "the paid revoker must revoke the order's entitlement"
        )
