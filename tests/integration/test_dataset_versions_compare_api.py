"""
Phase TR.B — API integration test for dataset versions/compare endpoint.

The compare endpoint was implemented as part of the Phase 230 dataset
versioning work. This test verifies the endpoint is wired and returns
a valid response for a dataset with version lineage.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserRole, UserStatus
from tests.fixtures.test_data_factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TestDatasetVersionsCompareApi(TestCase):
    """Integration test for GET /api/v1/datasets/{id}/versions/compare/"""

    def setUp(self):
        self.client = APIClient()
        _uid = uuid.uuid4().hex[:8]
        self.tenant = TenantFactory.create_tenant(
            name=f"Version Compare Tenant {_uid}",
            slug=f"version-compare-tenant-{_uid}",
        )
        self.user = User.objects.create_user(
            email=f"version-compare-{_uid}@example.com",
            tenant=self.tenant,
            password="testpass123",
            status=UserStatus.ACTIVE,
        )
        # Grant DATA_PROVIDER role for dataset operations
        from hub.apps.users.models import Role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.get_or_create(user=self.user, role=role)
        self.client.force_authenticate(user=self.user)

        # Create file + asset for dataset versioning.  Two versions exist
        # under the same asset with different ``version`` counters so they
        # satisfy unique_dataset_version_per_asset and share a lineage.
        self.file1 = File.objects.create(
            tenant=self.tenant,
            name="v1_file.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            storage_path=f"tenant/{self.tenant.id}/v1.csv",
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"vc-asset-{_uid}",
            name="VC Asset",
            domain="test",
        )
        # Parent dataset (version 1)
        self.parent_dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file1,
            asset=self.asset,
            format="CSV",
            version=1,
            schema_json={"fields": [{"name": "col_a", "type": "string"}]},
        )
        # Current dataset (version 2) — child of parent
        self.current_dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file1,
            asset=self.asset,
            format="CSV",
            version=2,
            parent_version=self.parent_dataset,
            schema_json={"fields": [{"name": "col_a", "type": "string"}, {"name": "col_b", "type": "int"}]},
        )

    def test_compare_with_explicit_version_ids(self):
        """Compare two explicit versions in the same lineage."""
        response = self.client.get(
            f"/api/v1/datasets/{self.current_dataset.id}/versions/compare/",
            {
                "version1": str(self.parent_dataset.id),
                "version2": str(self.current_dataset.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("changes", data)
        self.assertIn("compatibility_level", data)

    def test_compare_defaults_to_parent_vs_current(self):
        """Omitting version1/version2 defaults to parent vs current version."""
        response = self.client.get(
            f"/api/v1/datasets/{self.current_dataset.id}/versions/compare/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("changes", data)

    def test_compare_requires_valid_dataset_id(self):
        """Bogus dataset ID returns 404."""
        response = self.client.get(
            f"/api/v1/datasets/{uuid.uuid4()}/versions/compare/",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_compare_rejects_version_outside_lineage(self):
        """Comparing a version from a different lineage returns 400."""
        # Create an unrelated dataset (different parent lineage)
        other_file = File.objects.create(
            tenant=self.tenant,
            name="other_file.csv",
            content_type="text/csv",
            size=50,
            status=FileStatus.ACTIVE,
            storage_path=f"tenant/{self.tenant.id}/other.csv",
        )
        other_asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"vc-other-{uuid.uuid4().hex[:8]}",
            name="Other Asset",
            domain="test",
        )
        unrelated = Dataset.objects.create(
            tenant=self.tenant,
            file=other_file,
            asset=other_asset,
            format="CSV",
        )
        response = self.client.get(
            f"/api/v1/datasets/{self.current_dataset.id}/versions/compare/",
            {
                "version1": str(unrelated.id),
                "version2": str(self.current_dataset.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
