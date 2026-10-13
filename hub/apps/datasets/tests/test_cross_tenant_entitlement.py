"""
Phase 313.H.3 — cross-tenant dataset access through the entitlement hook.

``DatasetViewSet._get_via_entitlement`` delegates the marketplace
entitlement check to the commercial hook ``check_entitlement``
(marketplace registers ``require_entitlement`` from its
``AppConfig.ready()``). Core-only mode has no provider → fail-open
(the documented OSS contract: no paywall).

NO MOCKS at contract boundaries: real Postgres, real ORM, real
marketplace entitlement checks in full mode; core-only simulated by
unregistering the paid providers (the exact runtime shape of a
core-only process).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core import commercial_hooks
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.views import DatasetViewSet
from hub.apps.marketplace.models import (
    Entitlement,
    EntitlementStatus,
    Listing,
    ListingStatus,
    PricingModel,
)
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class CrossTenantDatasetEntitlementTests(TestCase):
    """Entitlement-gated cross-tenant dataset resolution."""

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
        self.asset = Asset.objects.create(
            tenant=self.owner_tenant,
            key=f"asset-{uid}",
            name="Entitled Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.owner,
        )
        self.dataset = Dataset.objects.create(
            tenant=self.owner_tenant,
            asset=self.asset,
            created_by=self.owner,
        )

    def _consumer_request(self):
        request = RequestFactory().get("/irrelevant")
        request.user = self.consumer
        request.tenant_id = str(self.consumer_tenant.id)
        return request

    def _resolve(self, request):
        view = DatasetViewSet()
        return view._get_via_entitlement(request, str(self.dataset.id))

    def test_full_mode_entitled_consumer_resolves_dataset(self):
        listing = Listing.objects.create(
            tenant=self.owner_tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
        )
        Entitlement.objects.create(
            tenant=self.consumer_tenant,
            listing=listing,
            asset=self.asset,
            status=EntitlementStatus.ACTIVE,
        )
        resolved = self._resolve(self._consumer_request())
        assert resolved is not None
        assert resolved.id == self.dataset.id

    def test_full_mode_unentitled_consumer_gets_none(self):
        """No entitlement → None (caller raises 404 — no existence leak)."""
        resolved = self._resolve(self._consumer_request())
        assert resolved is None

    def test_core_only_fails_open(self):
        """Core-only: no paywall — the hook returns without raising."""
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            resolved = self._resolve(self._consumer_request())
        assert resolved is not None
        assert resolved.id == self.dataset.id
