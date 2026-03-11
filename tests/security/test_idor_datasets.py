"""
Security tests: IDOR for Datasets.

Per tasks 29.5.1. User from tenant A must not access tenant B's dataset by ID.
Per tasks 29.69.2.4. List API with asset_id filter must not leak cross-tenant data.
Real APIClient; two tenants/users; assert 403 or 404 for cross-tenant GET.
"""

import pytest
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

from .base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class DatasetIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not access tenant B's dataset by ID."""

    def setUp(self):
        super().setUp()
        ensure_tenant_has_active_subscription(self.tenant_a)
        ensure_tenant_has_active_subscription(self.tenant_b)

    def test_dataset_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET datasets/{id}/ for other tenant's dataset must return 403 or 404."""
        asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            name="Asset B",
            status=AssetStatus.ACTIVE,
        )
        file_b = File.objects.create(
            tenant=self.tenant_b,
            name="data.csv",
            content_type="text/csv",
            size=100,
            storage_path="tenant-b/data.csv",
            status=FileStatus.ACTIVE,
        )
        dataset_b = Dataset.objects.create(
            tenant=self.tenant_b,
            asset=asset_b,
            file=file_b,
            format="CSV",
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/datasets/{dataset_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant dataset access must be 403 or 404",
        )

    def test_dataset_retrieve_succeeds_for_own_tenant(self):
        """GET datasets/{id}/ for own tenant's dataset can return 200."""
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            name="Asset A",
            status=AssetStatus.ACTIVE,
        )
        file_a = File.objects.create(
            tenant=self.tenant_a,
            name="data.csv",
            content_type="text/csv",
            size=100,
            storage_path="tenant-a/data.csv",
            status=FileStatus.ACTIVE,
        )
        dataset_a = Dataset.objects.create(
            tenant=self.tenant_a,
            asset=asset_a,
            file=file_a,
            format="CSV",
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/datasets/{dataset_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_dataset_list_asset_id_filter_tenant_isolation(self):
        """List with asset_id from other tenant must not return tenant B datasets (29.69.2.4)."""
        asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            name="Asset B",
            status=AssetStatus.ACTIVE,
        )
        file_b = File.objects.create(
            tenant=self.tenant_b,
            name="data.csv",
            content_type="text/csv",
            size=100,
            storage_path="tenant-b/data.csv",
            status=FileStatus.ACTIVE,
        )
        Dataset.objects.create(
            tenant=self.tenant_b,
            asset=asset_b,
            file=file_b,
            format="CSV",
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/datasets/?asset_id={asset_b.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        self.assertEqual(len(results), 0, "Must not return other tenant's datasets when filtering by their asset_id")
