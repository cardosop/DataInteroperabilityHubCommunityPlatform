"""
Comprehensive unit tests for Dataset ViewSet endpoints.

Tests cover:
- CRUD operations (list, retrieve, create, update, destroy)
- Version operations (list versions, create version, compare versions)
- Schema evolution endpoints
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling
- Tenant isolation
- Permission checks

All tests use real implementations (no mocks of hub services).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DatasetViewSetTest(DatasetsAPITestBase):
    """Comprehensive tests for Dataset ViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        uid = str(uuid.uuid4())[:8]

        # Create another tenant and user for isolation tests
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uid}",
            slug=f"other-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.other_user = User.objects.create_user(
            email=f"other-{uid}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status="ACTIVE",
        )

        # Ensure other_tenant has active subscription so tenant-isolation tests (PUT/DELETE as other_user) reach the view and get 404, not 403
        ensure_tenant_has_active_subscription(self.other_tenant)

        # Create test dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            created_by=self.user,
        )

    # ========== LIST ENDPOINT TESTS ==========

    def test_list_datasets_success_returns_200(self):
        """Test listing datasets successfully returns 200 status code"""
        response = self.client.get("/api/v1/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_datasets_success_returns_results_list(self):
        """Test listing datasets successfully returns results list"""
        response = self.client.get("/api/v1/datasets/")

        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_list_datasets_unauthenticated(self):
        """Test listing datasets without authentication"""
        # Unauthenticate client to test unauthenticated access
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/datasets/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_datasets_tenant_isolation_returns_200(self):
        """Test tenant isolation returns 200 status code"""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get("/api/v1/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_datasets_tenant_isolation_excludes_other_tenant_datasets(self):
        """Test tenant isolation excludes datasets from other tenant"""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get("/api/v1/datasets/")

        # Other user should not see datasets from different tenant
        dataset_ids = [d["id"] for d in response.data.get("results", [])]
        self.assertNotIn(str(self.dataset.id), dataset_ids)

    def test_list_datasets_filtering_by_asset_id_returns_200(self):
        """Test filtering datasets by asset_id returns 200 status code"""
        # Create asset and attach dataset
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            asset=asset,
            format="CSV",
            schema_json={"fields": []},
            created_by=self.user,
        )

        # Filter by asset_id
        response = self.client.get(f"/api/v1/datasets/?asset_id={asset.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_datasets_filtering_by_asset_id_includes_matching_datasets(self):
        """Test filtering datasets by asset_id includes matching datasets"""
        # Create asset and attach dataset
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        dataset_with_asset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            asset=asset,
            format="CSV",
            schema_json={"fields": []},
            created_by=self.user,
        )

        # Filter by asset_id
        response = self.client.get(f"/api/v1/datasets/?asset_id={asset.id}")

        results = response.data.get("results", [])
        dataset_ids = [d["id"] for d in results]
        self.assertIn(str(dataset_with_asset.id), dataset_ids)

    def test_list_datasets_filtering_by_invalid_asset_id_returns_empty(self):
        """Test invalid asset_id returns 200 with empty results, not 500 (29.69.2)."""
        response = self.client.get("/api/v1/datasets/?asset_id=not-a-valid-uuid")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", [])), 0)

    def test_list_datasets_asset_id_filter_tenant_isolation(self):
        """Test asset_id filter enforces tenant isolation (IDOR prevention).
        User from tenant B filtering by asset_id from tenant A must get empty results."""
        # Create asset in other tenant
        other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-asset",
            name="Other Asset",
            created_by=self.other_user,
        )
        # Create dataset in other tenant linked to that asset
        other_file = File.objects.create(
            tenant=self.other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.other_tenant.id}/other.csv",
            created_by=self.other_user,
        )
        Dataset.objects.create(
            tenant=self.other_tenant,
            file=other_file,
            asset=other_asset,
            format="CSV",
            schema_json={"fields": []},
            created_by=self.other_user,
        )
        # User from other_tenant requests datasets filtered by their asset
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f"/api/v1/datasets/?asset_id={other_asset.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see their own dataset
        results = response.data.get("results", [])
        self.assertEqual(len(results), 1)
        # User from our tenant requests datasets filtered by other_tenant's asset (IDOR attempt)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/v1/datasets/?asset_id={other_asset.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Must get empty - cannot see other tenant's data via asset_id filter
        self.assertEqual(len(response.data.get("results", [])), 0)

    def test_list_datasets_filtering_by_format(self):
        """Test filtering datasets by format (29.69.2). Uses dataset_format to avoid DRF ?format= conflict."""
        Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="JSON",
            schema_json={"fields": []},
            created_by=self.user,
        )
        response = self.client.get("/api/v1/datasets/?dataset_format=JSON")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for d in response.data.get("results", []):
            self.assertEqual(d["format"], "JSON")

    def test_list_datasets_search_by_file_name(self):
        """Test searching datasets by file name (29.69.2)."""
        file_searchable = File.objects.create(
            tenant=self.tenant,
            name="searchable-report.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant.id}/searchable.csv",
            created_by=self.user,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            file=file_searchable,
            format="CSV",
            schema_json={"fields": []},
            created_by=self.user,
        )
        response = self.client.get("/api/v1/datasets/?search=searchable")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [d.get("name", "") for d in response.data.get("results", [])]
        self.assertTrue(any("searchable" in n for n in names))

    def test_list_datasets_ordering(self):
        """Ascending ordering returns earlier rows first; descending reverses."""
        from datetime import timedelta
        from django.utils import timezone

        # Create two datasets with explicitly staggered created_at so
        # ordering is deterministic.
        file_a = File.objects.create(
            id=uuid.uuid4(), tenant=self.tenant, name="order-a.csv",
            content_type="text/csv", size=10, status=FileStatus.ACTIVE,
        )
        file_b = File.objects.create(
            id=uuid.uuid4(), tenant=self.tenant, name="order-b.csv",
            content_type="text/csv", size=10, status=FileStatus.ACTIVE,
        )
        earlier = Dataset.objects.create(
            tenant=self.tenant, file=file_a, format="CSV",
            created_by=self.user, version=1,
        )
        Dataset.objects.filter(id=earlier.id).update(
            created_at=timezone.now() - timedelta(hours=1),
        )
        later = Dataset.objects.create(
            tenant=self.tenant, file=file_b, format="CSV",
            created_by=self.user, version=1,
        )

        # Ascending: earlier first
        asc = self.client.get("/api/v1/datasets/?ordering=created_at")
        self.assertEqual(asc.status_code, status.HTTP_200_OK)
        asc_ids = [d["id"] for d in asc.data.get("results", [])]
        self.assertIn(str(earlier.id), asc_ids)
        self.assertIn(str(later.id), asc_ids)
        self.assertLess(
            asc_ids.index(str(earlier.id)), asc_ids.index(str(later.id)),
            "Ascending ordering must place earlier-created dataset first",
        )

        # Descending: later first
        desc = self.client.get("/api/v1/datasets/?ordering=-created_at")
        self.assertEqual(desc.status_code, status.HTTP_200_OK)
        desc_ids = [d["id"] for d in desc.data.get("results", [])]
        self.assertIn(str(earlier.id), desc_ids)
        self.assertIn(str(later.id), desc_ids)
        self.assertLess(
            desc_ids.index(str(later.id)), desc_ids.index(str(earlier.id)),
            "Descending ordering must place later-created dataset first",
        )

    def test_list_datasets_pagination_returns_200(self):
        """Test pagination returns 200 status code"""
        # Create multiple datasets
        for i in range(15):
            file_id = uuid.uuid4()
            file_obj = File.objects.create(
                id=file_id,
                tenant=self.tenant,
                name=f"test{i}.csv",
                content_type="text/csv",
                size=1024,
                status=FileStatus.ACTIVE,
                storage_path=f"{self.tenant.id}/{file_id}/test{i}.csv",
                created_by=self.user,
            )
            Dataset.objects.create(
                tenant=self.tenant,
                file=file_obj,
                format="CSV",
                schema_json={"fields": []},
                created_by=self.user,
            )

        response = self.client.get("/api/v1/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_datasets_pagination_includes_results_and_count(self):
        """Test pagination includes results and count fields"""
        # Create multiple datasets
        for i in range(15):
            file_id = uuid.uuid4()
            file_obj = File.objects.create(
                id=file_id,
                tenant=self.tenant,
                name=f"test{i}.csv",
                content_type="text/csv",
                size=1024,
                status=FileStatus.ACTIVE,
                storage_path=f"{self.tenant.id}/{file_id}/test{i}.csv",
                created_by=self.user,
            )
            Dataset.objects.create(
                tenant=self.tenant,
                file=file_obj,
                format="CSV",
                schema_json={"fields": []},
                created_by=self.user,
            )

        response = self.client.get("/api/v1/datasets/")

        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertGreaterEqual(response.data["count"], 15)

    # ========== RETRIEVE ENDPOINT TESTS ==========

    def test_retrieve_dataset_success_returns_200(self):
        """Test retrieving a dataset successfully returns 200 status code"""
        response = self.client.get(f"/api/v1/datasets/{self.dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_dataset_success_returns_correct_data(self):
        """Test retrieving a dataset successfully returns correct data"""
        response = self.client.get(f"/api/v1/datasets/{self.dataset.id}/")

        self.assertEqual(response.data["id"], str(self.dataset.id))
        self.assertIn("schema_json", response.data)

    def test_retrieve_dataset_includes_asset_id_and_asset_name_when_linked(self):
        """Test GET dataset returns asset_id and asset_name when dataset has linked asset (29.66.12)"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="linked-asset",
            name="My Linked Asset",
            created_by=self.user,
        )
        self.dataset.asset = asset
        self.dataset.save()

        response = self.client.get(f"/api/v1/datasets/{self.dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["asset_id"], str(asset.id))
        self.assertEqual(response.data["asset_name"], "My Linked Asset")
        self.assertEqual(response.data["asset"], str(asset.id))

    def test_retrieve_dataset_not_found(self):
        """Test retrieving non-existent dataset"""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/datasets/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_dataset_tenant_isolation(self):
        """Test tenant isolation - user cannot retrieve other tenant's dataset"""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(f"/api/v1/datasets/{self.dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_dataset_invalid_uuid(self):
        """Test retrieving dataset with invalid UUID format (edge case)"""
        response = self.client.get("/api/v1/datasets/invalid-uuid/")

        # View validates UUID format and returns 400 for invalid format
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== CREATE ENDPOINT TESTS ==========

    def test_create_dataset_success(self):
        """Test creating a dataset successfully"""
        # Use self.file from the base setUp — it already has S3 content
        # uploaded, so schema inference succeeds.
        data = {"file_id": str(self.file.id)}

        response = self.client.post("/api/v1/datasets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["file"], str(self.file.id))
        # Verify persisted to DB
        self.assertTrue(Dataset.objects.filter(id=response.data["id"]).exists())

    def test_create_dataset_missing_file_id(self):
        """Test creating dataset with missing file_id (error handling)"""

        data = {}  # Missing file_id

        response = self.client.post("/api/v1/datasets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_dataset_invalid_file_id(self):
        """Test creating dataset with invalid file_id (error handling)"""
        data = {"file_id": "invalid-uuid"}

        response = self.client.post("/api/v1/datasets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_dataset_file_not_found(self):
        """Test creating dataset with non-existent file_id (error handling)"""
        fake_file_id = str(uuid.uuid4())
        data = {"file_id": fake_file_id}

        response = self.client.post("/api/v1/datasets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_dataset_unauthenticated(self):
        """Test creating dataset without authentication"""
        self.client.force_authenticate(user=None)
        data = {"file_id": str(self.file.id)}

        response = self.client.post("/api/v1/datasets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== UPDATE ENDPOINT TESTS ==========

    def test_update_dataset_success(self):
        """Test updating a dataset successfully"""

        updated_data = {"format": "JSON"}

        response = self.client.put(
            f"/api/v1/datasets/{self.dataset.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify response body reflects the update
        self.assertEqual(response.data["format"], "JSON")
        # Verify DB was actually updated (independent query)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.format, "JSON")

    def test_partial_update_dataset_success(self):
        """Test partial update (PATCH) of a dataset"""

        updated_data = {"format": "PARQUET"}

        response = self.client.patch(
            f"/api/v1/datasets/{self.dataset.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify response body reflects the update
        self.assertEqual(response.data["format"], "PARQUET")
        # Verify DB was actually updated
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.format, "PARQUET")

    def test_update_dataset_not_found(self):
        """Test updating non-existent dataset"""

        fake_id = str(uuid.uuid4())
        updated_data = {"format": "JSON"}

        response = self.client.put(f"/api/v1/datasets/{fake_id}/", updated_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_dataset_tenant_isolation(self):
        """Test tenant isolation - user cannot update other tenant's dataset"""
        self.client.force_authenticate(user=self.other_user)

        updated_data = {"format": "JSON"}

        response = self.client.put(
            f"/api/v1/datasets/{self.dataset.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_dataset_accepts_asset(self):
        """Test DatasetSerializer/update accepts asset; linking dataset to asset via PATCH"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-link",
            name="Test Asset for Link",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.assertIsNone(self.dataset.asset_id)

        response = self.client.patch(
            f"/api/v1/datasets/{self.dataset.id}/",
            {"asset": str(asset.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.asset_id, asset.id)
        self.assertEqual(response.data.get("asset"), str(asset.id))

    def test_update_dataset_unlink_asset(self):
        """Test dataset update can unlink asset by setting asset to null"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-unlink",
            name="Test Asset for Unlink",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.dataset.asset = asset
        self.dataset.save()
        self.assertEqual(self.dataset.asset_id, asset.id)

        response = self.client.patch(
            f"/api/v1/datasets/{self.dataset.id}/",
            {"asset": None},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.dataset.refresh_from_db()
        self.assertIsNone(self.dataset.asset_id)

    def test_update_dataset_invalid_asset_uuid_returns_400(self):
        """Test PATCH with invalid asset UUID returns 400"""
        response = self.client.patch(
            f"/api/v1/datasets/{self.dataset.id}/",
            {"asset": "not-a-valid-uuid"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_dataset_nonexistent_asset_returns_400(self):
        """Test PATCH with valid UUID format but non-existent asset returns 400"""
        fake_asset_id = str(uuid.uuid4())
        response = self.client.patch(
            f"/api/v1/datasets/{self.dataset.id}/",
            {"asset": fake_asset_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== DESTROY ENDPOINT TESTS ==========

    def test_destroy_dataset_success(self):
        """Test deleting a dataset successfully"""
        response = self.client.delete(f"/api/v1/datasets/{self.dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify dataset was deleted
        self.assertFalse(Dataset.objects.filter(id=self.dataset.id).exists())

    def test_destroy_dataset_not_found(self):
        """Test deleting non-existent dataset"""

        fake_id = str(uuid.uuid4())
        response = self.client.delete(f"/api/v1/datasets/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_destroy_dataset_tenant_isolation(self):
        """Test tenant isolation - user cannot delete other tenant's dataset"""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.delete(f"/api/v1/datasets/{self.dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== VERSION OPERATIONS TESTS ==========

    def test_list_versions_success(self):
        """Test listing dataset versions successfully"""
        response = self.client.get(f"/api/v1/datasets/{self.dataset.id}/versions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_list_versions_not_found(self):
        """Test listing versions for non-existent dataset"""

        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/datasets/{fake_id}/versions/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_version_success(self):
        """Test creating a new dataset version successfully"""

        data = {"semantic_version": "1.1.0", "version_tags": ["production"]}

        response = self.client.post(
            f"/api/v1/datasets/{self.dataset.id}/versions/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["semantic_version"], "1.1.0")

    def test_create_version_rejected_when_versioning_disabled(self):
        """Phase 12: Creating a version returns 403 when versioning_enabled=False."""
        TenantConfig.objects.update_or_create(
            tenant=self.tenant,
            defaults={"versioning_enabled": False},
        )
        data = {"semantic_version": "1.1.0"}

        response = self.client.post(
            f"/api/v1/datasets/{self.dataset.id}/versions/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "VERSIONING_DISABLED")
        self.assertIn("disabled", (response.data.get("detail") or "").lower())

    def test_create_version_defaults_with_empty_payload(self):
        """Creating a version with an empty payload succeeds by applying defaults."""
        data = {}
        response = self.client.post(
            f"/api/v1/datasets/{self.dataset.id}/versions/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_compare_versions_success(self):
        """Test comparing dataset versions successfully"""

        # Create another version
        version2 = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
            parent_version=self.dataset,
            version=2,
            created_by=self.user,
        )

        response = self.client.get(
            f"/api/v1/datasets/{self.dataset.id}/versions/compare/"
            f"?version1={self.dataset.id}&version2={version2.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict,
                              "Version comparison response must be a dict")
        self.assertIn("version1", response.data,
                      "Version comparison response must include 'version1'")
        self.assertIn("version2", response.data,
                      "Version comparison response must include 'version2'")

    def test_compare_versions_missing_params(self):
        """Test comparing versions with missing parameters (error handling)"""
        response = self.client.get(f"/api/v1/datasets/{self.dataset.id}/versions/compare/")

        # Missing required parameters must return 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== ADDITIONAL AUTHORIZATION TESTS ==========

    def test_partial_update_dataset_tenant_isolation(self):
        """Tenant isolation: user cannot PATCH another tenant's dataset."""
        self.client.force_authenticate(user=self.other_user)
        response = self.client.patch(
            f"/api/v1/datasets/{self.dataset.id}/",
            {"format": "JSON"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_destroy_dataset_unauthenticated(self):
        """Unauthenticated DELETE request must return 401."""
        self.client.force_authenticate(user=None)
        response = self.client.delete(
            f"/api/v1/datasets/{self.dataset.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_dataset_requires_tenant_admin(self):
        """A non-TENANT_ADMIN user gets 403 when calling refresh."""
        response = self.client.post(
            f"/api/v1/datasets/{self.dataset.id}/refresh/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== EDGE CASES ==========

    def test_list_datasets_empty_result(self):
        """Test listing datasets when none exist (edge case)"""
        # Delete all datasets
        Dataset.objects.filter(tenant=self.tenant).delete()

        response = self.client.get("/api/v1/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", [])), 0)

    def test_create_dataset_with_asset_id(self):
        """Test creating dataset with asset_id (edge case)"""

        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        data = {"file_id": str(self.file.id), "asset_id": str(asset.id)}

        response = self.client.post("/api/v1/datasets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ========== ERROR HANDLING ==========

    def test_create_dataset_validation_error_handling(self):
        """Test error handling for validation errors"""

        # Missing required fields
        data = {}

        response = self.client.post("/api/v1/datasets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file_id", str(response.data) or response.data)
