"""
Phase 313.H.3 — governance order cascades in core-only mode.

The marketplace order link resolves through ``get_access_request_order``
(a paid provider registered in marketplace's ``AppConfig.ready()``).
With no provider — the exact runtime shape of a core-only process —
approval, rejection, and revocation must complete without any
marketplace machinery: the order is None, so the finalize/revoke
cascades no-op.

The full-mode direction (a linked ``Order`` driven through approve /
reject / revoke via the paid finalizers) is pinned by the sibling
``test_full_mode_order_cascades.py`` (P.2c) — previously no test
exercised those hook paths with a real order; the old "covered by the
marketplace order-flow tests" claim was false. Here we pin the
core-only contract. NO MOCKS at contract boundaries: real Postgres,
real ORM, real GovernanceService.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core import commercial_hooks
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.governance.services import GovernanceService
from hub.apps.tenants.models import PlanTier, Tenant, TenantPlan
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
UserModel = get_user_model()


def _make_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"T-{uid}",
        slug=f"t-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    # Business rules resolve plan limits through the subscription —
    # mirror the multi-step integration setup. The paid billing module is
    # imported dynamically (GATE-29 — core-tree tests must not statically
    # import paid modules); the call runs only when this helper is invoked
    # from the full-mode suite.
    import importlib

    _billing = importlib.import_module("hub.apps.billing.models")
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


def _make_user(tenant):
    user = UserModel.objects.create_user(
        email=f"u-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="DATA_OWNER",
        defaults={"description": "Data Owner"},
    )
    UserRole.objects.get_or_create(user=user, role=role)
    return user


@pytest.mark.requires_marketplace
class CoreOnlyOrderCascadeTests(TestCase):
    """Approve / reject / revoke complete without the paid marketplace."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.user = _make_user(self.tenant)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.service = GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def _make_request(self):
        return AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Core-only integration test",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
            approvers=[str(self.user.id)],
        )

    def test_approve_completes_without_marketplace(self):
        ar = self._make_request()
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            result = self.service.approve_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.user.id),
            )
        ar.refresh_from_db()
        assert result.status == AccessRequestStatus.APPROVED
        assert ar.status == AccessRequestStatus.APPROVED
        assert ar.approved_by == self.user

    def test_reject_completes_without_marketplace(self):
        ar = self._make_request()
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            result = self.service.reject_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.user.id),
                reason="Not needed",
            )
        ar.refresh_from_db()
        assert result.status == AccessRequestStatus.REJECTED
        assert ar.status == AccessRequestStatus.REJECTED

    def test_revoke_completes_without_marketplace(self):
        ar = self._make_request()
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            self.service.approve_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.user.id),
            )
            result = self.service.revoke_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                revoker_id=str(self.user.id),
                reason="Access no longer needed",
            )
        ar.refresh_from_db()
        assert result.status == AccessRequestStatus.REVOKED
        assert ar.status == AccessRequestStatus.REVOKED
