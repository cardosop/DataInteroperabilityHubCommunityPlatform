"""Tests for federated-cascade and pricing-cache signal handlers.

Covers ``tombstone_federated_resources_on_tenant_delete`` and the
``public_pricing:v1`` cache invalidation handlers — all previously
untested at the signal level.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus, ExternalResourceReference
from hub.apps.tenants.models import (
    Tenant,
    TenantPlan,
    TenantStatus,
    TierProfile,
)

pytestmark = pytest.mark.django_db(transaction=True)


class TombstoneFederatedResourcesTests(TestCase):
    """Tests for the post_save handler that sets source_tenant_deleted_at
    on consumer-side ExternalResourceReference rows when the source
    tenant transitions to DELETED."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        # Source tenant (the one being deleted).
        self.source_tenant = Tenant.objects.create(
            name=f"FedSource {uid}",
            slug=f"fedsource-{uid}",
            status=TenantStatus.ACTIVE,
        )
        # Consumer tenant (imports a reference from source).
        Tenant.objects.create(
            name=f"FedConsumer {uid}",
            slug=f"fedconsumer-{uid}",
            status=TenantStatus.ACTIVE,
        )
        # Asset on the SOURCE tenant (federated out to consumer).
        self.asset = Asset.objects.create(
            tenant=self.source_tenant,
            key=f"fed-asset-{uid}",
            name="Federated Asset",
            status=AssetStatus.ACTIVE,
        )
        # Consumer-side reference pointing back to the source tenant.
        self.ref = ExternalResourceReference.objects.create(
            asset=self.asset,
            resource_id=f"ext-{uid}",
            name="External Ref",
            url=f"https://example.com/{uid}",
            format="CSV",
            marketplace_type="CKAN",
            connection_id=uuid.uuid4(),
            source_tenant_id=self.source_tenant.id,
        )

    def test_tombstone_sets_deleted_at_on_transition_to_deleted(self):
        """ACTIVE → DELETED sets source_tenant_deleted_at on references."""
        self.source_tenant.status = TenantStatus.DELETED
        self.source_tenant.save()
        self.ref.refresh_from_db()
        self.assertIsNotNone(
            self.ref.source_tenant_deleted_at,
            "source_tenant_deleted_at must be set on cascade",
        )

    def test_tombstone_skips_already_tombstoned_references(self):
        """References with source_tenant_deleted_at set are not updated."""
        already = timezone.now() - timedelta(days=10)
        self.ref.source_tenant_deleted_at = already
        self.ref.save()
        self.source_tenant.status = TenantStatus.DELETED
        self.source_tenant.save()
        self.ref.refresh_from_db()
        self.assertEqual(self.ref.source_tenant_deleted_at, already)

    def test_tombstone_noop_on_create(self):
        """Creating a new DELETED tenant should NOT trigger tombstone."""
        uid2 = uuid.uuid4().hex[:8]
        Tenant.objects.create(
            name=f"NewDel {uid2}",
            slug=f"newdel-{uid2}",
            status=TenantStatus.DELETED,
        )
        self.ref.refresh_from_db()
        self.assertIsNone(self.ref.source_tenant_deleted_at)

    def test_tombstone_noop_on_non_deleted_status_change(self):
        """ACTIVE → SUSPENDED must NOT trigger tombstone."""
        self.source_tenant.status = TenantStatus.SUSPENDED
        self.source_tenant.save()
        self.ref.refresh_from_db()
        self.assertIsNone(
            self.ref.source_tenant_deleted_at,
            "SUSPENDED should not trigger federated cascade",
        )

    def test_tombstone_grace_days_constant_is_positive(self):
        """TOMBSTONE_GRACE_DAYS is a positive integer constant."""
        self.assertGreater(ExternalResourceReference.TOMBSTONE_GRACE_DAYS, 0)


class PricingCacheInvalidationTests(TestCase):
    """Tests for public_pricing:v1 cache invalidation signals."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.plan = TenantPlan.objects.create(
            slug=f"price-cache-{uid}",
            name="Cache Test Plan",
            tier="PRO",
            order=1,
            is_active=True,
        )
        cache.set("public_pricing:v1", {"cached": True}, timeout=300)

    def test_plan_save_invalidates_pricing_cache(self):
        """Saving a TenantPlan deletes public_pricing:v1 cache key."""
        self.plan.name = "Updated Name"
        self.plan.save()
        self.assertIsNone(
            cache.get("public_pricing:v1"),
            "public_pricing:v1 must be invalidated on TenantPlan save",
        )

    def test_tier_profile_save_invalidates_pricing_cache(self):
        """Saving a TierProfile deletes public_pricing:v1 cache key."""
        tp = TierProfile.objects.create(
            plan=self.plan,
            headline="Test Profile",
            is_public=True,
        )
        cache.set("public_pricing:v1", {"cached": True}, timeout=300)
        tp.headline = "Updated"
        tp.save()
        self.assertIsNone(
            cache.get("public_pricing:v1"),
            "public_pricing:v1 must be invalidated on TierProfile save",
        )
