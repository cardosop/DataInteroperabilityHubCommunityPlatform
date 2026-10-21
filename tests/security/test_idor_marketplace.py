"""
Security tests: IDOR for Marketplace listings.

Per tasks 29.5.1. User from tenant A must not access tenant B's listing by ID
(when listing is DRAFT/UNLISTED; published listings may be visible per design).
Real APIClient; two tenants/users; assert 403 or 404 for cross-tenant GET.
"""

import pytest
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.marketplace.models import Listing, ListingStatus

from .base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceListingIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not access tenant B's draft listing by ID."""

    def test_listing_retrieve_returns_403_or_404_for_other_tenant_draft(self):
        """GET marketplace/listings/{id}/ for other tenant's DRAFT listing must return 403 or 404."""
        asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            name="Asset B",
            status=AssetStatus.ACTIVE,
        )
        listing_b = Listing.objects.create(
            tenant=self.tenant_b,
            asset=asset_b,
            status=ListingStatus.DRAFT,
            metadata_json={"title": "Listing B"},
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/marketplace/listings/{listing_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant draft listing access must be 403 or 404",
        )

    def test_listing_retrieve_succeeds_for_own_tenant(self):
        """GET marketplace/listings/{id}/ for own tenant's listing can return 200."""
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            name="Asset A",
            status=AssetStatus.ACTIVE,
        )
        listing_a = Listing.objects.create(
            tenant=self.tenant_a,
            asset=asset_a,
            status=ListingStatus.DRAFT,
            metadata_json={"title": "Listing A"},
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/marketplace/listings/{listing_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
