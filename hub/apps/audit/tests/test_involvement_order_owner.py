"""
Phase 313.H.3 — audit involvement ORDER ownership boundary.

``user_is_involved`` resolves ORDER ownership through the commercial
hook ``is_order_owner`` (marketplace registers the provider). Core-only
mode has no provider → nobody owns an order (no orders exist).

NO MOCKS at contract boundaries: real Postgres, real ORM, real
audit trail, real marketplace orders in full mode.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.involvement import user_is_involved
from hub.apps.core import commercial_hooks
from hub.apps.marketplace.models import Listing, ListingStatus, Order, PricingModel
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class OrderOwnerInvolvementTests(TestCase):
    """ORDER ownership resolution — full-mode vs core-only."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T-{uid}", slug=f"t-{uid}", status="ACTIVE")
        self.owner = User.objects.create_user(
            email=f"owner-{uid}@meshant.test", password="testpass", tenant=self.tenant
        )
        self.other = User.objects.create_user(
            email=f"other-{uid}@meshant.test", password="testpass", tenant=self.tenant
        )
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.owner,
        )
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
        )
        self.order = Order.objects.create(
            tenant=self.tenant,
            listing=listing,
            created_by=self.owner,
        )

    def _involved(self, user):
        return user_is_involved(
            user,
            resource_type="ORDER",
            resource_id=self.order.id,
            tenant_id=str(self.tenant.id),
        )

    def test_full_mode_owner_is_involved(self):
        assert self._involved(self.owner) is True

    def test_full_mode_non_owner_is_not_involved(self):
        assert self._involved(self.other) is False

    def test_core_only_nobody_owns_an_order(self):
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            assert self._involved(self.owner) is False
