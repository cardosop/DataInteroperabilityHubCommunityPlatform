"""
Phase 313.H.3 — marketplace cache invalidation on compliance-run saves.

The compliance post-save signal delegates to the commercial hook
``invalidate_listing_caches_for_asset`` (registered by the paid
marketplace app's ``AppConfig.ready()``). Core-only mode has no
provider → no invalidation, and the paid imports never execute.

NO MOCKS at contract boundaries: real Postgres, real Django cache,
real signal receivers — core-only mode is simulated by unregistering
the paid providers (the exact runtime shape of a core-only process).

NOTE: this module uses a plain pytest class (NOT ``django.test.TestCase``)
on purpose — the invalidation runs in ``transaction.on_commit``, and
TestCase's rollback wrapper would never fire it. ``transaction=True``
gives TransactionTestCase semantics: saves commit, on_commit runs.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.core import commercial_hooks
from hub.apps.datasets.models import Dataset
from hub.apps.marketplace.caching import get_marketplace_detail_cache_key
from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TestMarketplaceCacheInvalidationSignal:
    """Full-mode and core-only contracts for the compliance-run signal."""

    def setup_method(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T-{uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
        )
        self.user = User.objects.create_user(
            email=f"u-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ListingStatus.DRAFT,
            pricing_model=PricingModel.FREE,
        )
        self.detail_key = get_marketplace_detail_cache_key(str(self.listing.pk))

    def _prime_cache(self):
        cache.set(self.detail_key, {"sentinel": "cached-listing"})

    def _create_asset_run(self, run_status):
        return ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=run_status,
            risk_level="LOW",
            allowed_to_store=True,
        )

    def test_succeeded_run_invalidates_listing_detail_cache(self):
        """Full mode: a SUCCEEDED run on a listed asset busts the detail cache."""
        self._prime_cache()
        self._create_asset_run(ComplianceRunStatus.SUCCEEDED)
        assert cache.get(self.detail_key) is None

    def test_core_only_run_leaves_cache_untouched(self):
        """Core-only: no marketplace provider → no invalidation at all."""
        self._prime_cache()
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            self._create_asset_run(ComplianceRunStatus.SUCCEEDED)
        assert cache.get(self.detail_key) == {"sentinel": "cached-listing"}

    def test_non_succeeded_run_does_not_invalidate(self):
        """FAILED runs never reach the cache-busting branch."""
        self._prime_cache()
        self._create_asset_run(ComplianceRunStatus.FAILED)
        assert cache.get(self.detail_key) == {"sentinel": "cached-listing"}

    def test_run_without_asset_does_not_invalidate(self):
        """A dataset-bound run (asset_id None) has nothing to bust."""
        self._prime_cache()
        dataset = Dataset.objects.create(tenant=self.tenant)
        ComplianceRun.objects.create(
            tenant=self.tenant,
            dataset=dataset,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level="LOW",
            allowed_to_store=True,
        )
        assert cache.get(self.detail_key) == {"sentinel": "cached-listing"}
