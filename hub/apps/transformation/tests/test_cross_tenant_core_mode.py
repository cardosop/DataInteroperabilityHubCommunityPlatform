"""
Phase 313.H.3 — transformation cross-tenant access validation boundary.

``TransformationBusinessRules._validate_cross_tenant_asset_access``
verifies marketplace entitlements through the commercial hook
``check_cross_tenant_entitlement`` (fail-closed in core-only mode).

NO MOCKS at contract boundaries: real Postgres, real ORM, real
business rules, real marketplace entitlements in full mode.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core import commercial_hooks
from hub.apps.governance.models import AccessPolicy
from hub.apps.marketplace.models import (
    Entitlement,
    EntitlementStatus,
    Listing,
    ListingStatus,
    PricingModel,
)
from hub.apps.tenants.models import Tenant
from hub.apps.transformation.business_rules import TransformationBusinessRules

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class CrossTenantTransformationValidationTests(TestCase):
    """Cross-tenant asset access validation — full-mode vs core-only."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.owner_tenant = Tenant.objects.create(
            name=f"Owner-{uid}", slug=f"owner-{uid}", status="ACTIVE"
        )
        self.consumer_tenant = Tenant.objects.create(
            name=f"Consumer-{uid}", slug=f"consumer-{uid}", status="ACTIVE"
        )
        self.owner = User.objects.create_user(
            email=f"owner-{uid}@meshant.test", password="testpass", tenant=self.owner_tenant
        )
        self.consumer = User.objects.create_user(
            email=f"consumer-{uid}@meshant.test", password="testpass", tenant=self.consumer_tenant
        )
        self.owner_asset = Asset.objects.create(
            tenant=self.owner_tenant,
            key=f"asset-{uid}",
            name="Cross-Tenant Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.owner,
        )

    def _rules(self):
        return TransformationBusinessRules(
            tenant_id=str(self.consumer_tenant.id),
            user_id=str(self.consumer.id),
        )

    def _allow_abac(self):
        # ABAC evaluates first and defaults to deny; an ALLOW policy
        # (empty conditions = match-all) routes evaluation to the
        # entitlement branch under test. The evaluation is scoped to
        # the ASSET's tenant (evaluate_access tenant_id arg), so the
        # policy lives on the owner tenant.
        AccessPolicy.objects.create(
            tenant=self.owner_tenant,
            name=f"allow-{uuid.uuid4().hex[:8]}",
            asset=self.owner_asset,
            effect="ALLOW",
            enabled=True,
            priority=0,
            conditions={},
        )

    def _validate(self, rules):
        return rules._validate_cross_tenant_asset_access(self.owner_asset, "READ")

    def test_core_only_entitlement_required(self):
        """Core-only: fail-closed — entitlement required, access denied."""
        self._allow_abac()
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            result = self._validate(self._rules())
        assert result["allowed"] is False
        assert result["entitlement_required"] is True
        assert "Entitlement required" in result["reason"]

    def test_full_mode_unentitled_denied(self):
        self._allow_abac()
        result = self._validate(self._rules())
        assert result["allowed"] is False
        assert result["entitlement_required"] is True

    def test_full_mode_entitled_allowed(self):
        self._allow_abac()
        listing = Listing.objects.create(
            tenant=self.owner_tenant,
            asset=self.owner_asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
        )
        Entitlement.objects.create(
            tenant=self.consumer_tenant,
            listing=listing,
            asset=self.owner_asset,
            status=EntitlementStatus.ACTIVE,
        )
        result = self._validate(self._rules())
        assert result["allowed"] is True
