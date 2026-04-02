"""
Phase 26-OB: Dataset versioning tests (is_current, parent_version, version counter).

Tests dataset attachment via the API endpoint and verifies that
versioning fields are set correctly.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class DatasetVersioningTest(TestCase):
    """Test dataset versioning on attachment to an asset."""

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Ver Tenant {uid}",
            slug=f"ver-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"ver-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name=f"Asset {uid}",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    # -- helpers ----------------------------------------------------------

    def _make_file(self):
        uid = uuid.uuid4().hex[:6]
        return File.objects.create(
            tenant=self.tenant,
            name=f"file-{uid}.csv",
            content_type="text/csv",
            size=512,
            storage_path=f"tenants/{self.tenant.id}/files/{uid}.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

    def _make_unattached_dataset(self):
        """Create a dataset belonging to the same tenant but not yet attached to the asset."""
        f = self._make_file()
        return Dataset.objects.create(
            tenant=self.tenant,
            asset=None,
            file=f,
            format="CSV",
            row_count=5,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            created_by=self.user,
        )

    def _attach(self, dataset):
        return self.client.post(
            f"/api/v1/assets/{self.asset.id}/datasets/",
            {"dataset_id": str(dataset.id)},
            format="json",
        )

    # -- tests ------------------------------------------------------------

    def test_first_attachment_version_1_is_current(self):
        """First attached dataset gets version=1 and is_current=True."""
        ds = self._make_unattached_dataset()
        resp = self._attach(ds)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        ds.refresh_from_db()
        self.assertEqual(ds.version, 1)
        self.assertTrue(ds.is_current)

    def test_second_attachment_increments_version(self):
        """Second attached dataset gets version=2."""
        ds1 = self._make_unattached_dataset()
        self._attach(ds1)
        ds2 = self._make_unattached_dataset()
        resp = self._attach(ds2)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        ds2.refresh_from_db()
        self.assertEqual(ds2.version, 2)
        self.assertTrue(ds2.is_current)

    def test_previous_dataset_not_current(self):
        """After attaching a second dataset the first is no longer current."""
        ds1 = self._make_unattached_dataset()
        self._attach(ds1)
        ds2 = self._make_unattached_dataset()
        self._attach(ds2)
        ds1.refresh_from_db()
        self.assertFalse(ds1.is_current)

    def test_parent_version_set(self):
        """Second dataset's parent_version points to the first dataset."""
        ds1 = self._make_unattached_dataset()
        self._attach(ds1)
        ds2 = self._make_unattached_dataset()
        self._attach(ds2)
        ds2.refresh_from_db()
        self.assertEqual(ds2.parent_version_id, ds1.id)

    def test_only_one_current_per_asset(self):
        """After three attachments only the last has is_current=True."""
        datasets = []
        for _ in range(3):
            ds = self._make_unattached_dataset()
            self._attach(ds)
            datasets.append(ds)
        for ds in datasets:
            ds.refresh_from_db()
        self.assertFalse(datasets[0].is_current)
        self.assertFalse(datasets[1].is_current)
        self.assertTrue(datasets[2].is_current)

    def test_attachment_cross_tenant_rejected(self):
        """Attaching a dataset from a different tenant returns 400."""
        other_uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {other_uid}",
            slug=f"other-tenant-{other_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_user = User.objects.create_user(
            email=f"other-{other_uid}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        other_file = File.objects.create(
            tenant=other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=100,
            storage_path=f"tenants/{other_tenant.id}/files/other.csv",
            status=FileStatus.ACTIVE,
            created_by=other_user,
        )
        other_ds = Dataset.objects.create(
            tenant=other_tenant,
            asset=None,
            file=other_file,
            format="CSV",
            row_count=1,
            schema_json={"fields": []},
            created_by=other_user,
        )
        resp = self._attach(other_ds)
        self.assertIn(resp.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND))
