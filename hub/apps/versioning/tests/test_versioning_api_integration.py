"""
Integration tests for Versioning API (GR-2).

GET /api/v1/versioning/versions/  — list versions (resource_type, resource_id)
GET /api/v1/versioning/versions/<id>/  — get version by id
GET /api/v1/versioning/compare/  — compare two versions (id_a, id_b, resource_type)

Tests use real DB (Contract, Dataset, Asset, File, Tenant, User); no mocks/stubs.
Covers: list versions, get version, compare, tenant isolation, auth, params validation.
"""

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _create_contract(tenant, asset=None, version=1, **kwargs):
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=version,
        original_raw=kwargs.get("original_raw", '{"info": {"name": "c1"}}'),
        original_format=kwargs.get("original_format", OriginalFormat.JSON),
        original_spec_type=kwargs.get("original_spec_type", OriginalSpecType.ODCS),
        original_spec_version=kwargs.get("original_spec_version", "3.0.2"),
        hub_contract_json=kwargs.get("hub_contract_json"),
    )


class VersioningListVersionsIntegrationTest(TestCase):
    """List versions: GET /api/v1/versioning/versions/?resource_type=contract&resource_id=<asset_uuid>."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="T1",
            slug="t1",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="u1@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="asset1",
            name="Asset1",
            status="DRAFT",
        )

    def test_list_contract_versions_returns_200_and_ordered_by_version(self):
        _create_contract(self.tenant, asset=self.asset, version=1)
        _create_contract(self.tenant, asset=self.asset, version=2)
        _create_contract(self.tenant, asset=self.asset, version=3)
        response = self.client.get(
            "/api/v1/versioning/versions/",
            {"resource_type": "contract", "resource_id": str(self.asset.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        versions = response.data["results"]
        self.assertEqual(len(versions), 3)
        self.assertEqual(versions[0]["version"], 3)
        self.assertEqual(versions[1]["version"], 2)
        self.assertEqual(versions[2]["version"], 1)

    def test_list_versions_missing_resource_type_returns_400(self):
        response = self.client.get(
            "/api/v1/versioning/versions/",
            {"resource_id": str(self.asset.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_versions_missing_resource_id_returns_400(self):
        response = self.client.get(
            "/api/v1/versioning/versions/",
            {"resource_type": "contract"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_versions_invalid_resource_type_returns_400(self):
        response = self.client.get(
            "/api/v1/versioning/versions/",
            {"resource_type": "invalid", "resource_id": str(self.asset.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_versions_tenant_isolation_returns_empty_for_other_tenant_asset(self):
        other_tenant = Tenant.objects.create(
            name="T2",
            slug="t2",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other",
            status="DRAFT",
        )
        _create_contract(other_tenant, asset=other_asset, version=1)
        response = self.client.get(
            "/api/v1/versioning/versions/",
            {"resource_type": "contract", "resource_id": str(other_asset.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_versions_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(
            "/api/v1/versioning/versions/",
            {"resource_type": "contract", "resource_id": str(self.asset.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_dataset_versions_returns_200_and_ordered_by_version(self):
        """List versions with resource_type=dataset; real File and Dataset (no mocks)."""
        file = File.objects.create(
            tenant=self.tenant,
            name="data.csv",
            content_type="text/csv",
            size=100,
            storage_path="test/data.csv",
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            is_current=False,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file,
            format="CSV",
            version=2,
            semantic_version="1.1.0",
            is_current=True,
        )
        response = self.client.get(
            "/api/v1/versioning/versions/",
            {"resource_type": "dataset", "resource_id": str(self.asset.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        versions = response.data["results"]
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["version"], 2)
        self.assertEqual(versions[0]["resource_type"], "dataset")
        self.assertEqual(versions[0]["semantic_version"], "1.1.0")
        self.assertEqual(versions[0]["is_current"], True)
        self.assertEqual(versions[1]["version"], 1)
        self.assertEqual(versions[1]["is_current"], False)


class VersioningGetVersionIntegrationTest(TestCase):
    """Get version: GET /api/v1/versioning/versions/<id>/."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="T1",
            slug="t1",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="u1@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)
        self.contract = _create_contract(self.tenant, asset=None, version=1)

    def test_get_version_contract_returns_200_and_shape(self):
        response = self.client.get(
            f"/api/v1/versioning/versions/{self.contract.id}/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.contract.id))
        self.assertEqual(response.data["resource_type"], "contract")
        self.assertIn("version", response.data)
        self.assertIn("created_at", response.data)

    def test_get_version_unknown_id_returns_404(self):
        response = self.client.get(
            "/api/v1/versioning/versions/00000000-0000-0000-0000-000000000000/",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_version_tenant_isolation_returns_404_for_other_tenant(self):
        other_tenant = Tenant.objects.create(
            name="T2",
            slug="t2",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        other_contract = _create_contract(other_tenant, asset=None, version=1)
        response = self.client.get(
            f"/api/v1/versioning/versions/{other_contract.id}/",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class VersioningCompareIntegrationTest(TestCase):
    """Compare: GET /api/v1/versioning/compare/?resource_type=contract&id_a=<uuid>&id_b=<uuid>."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="T1",
            slug="t1",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="u1@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="a1",
            name="A1",
            status="DRAFT",
        )
        self.c1 = _create_contract(
            self.tenant,
            asset=self.asset,
            version=1,
            hub_contract_json={"info": {"name": "v1"}},
        )
        self.c2 = _create_contract(
            self.tenant,
            asset=self.asset,
            version=2,
            hub_contract_json={"info": {"name": "v2"}},
        )

    def test_compare_contract_versions_returns_200_and_diff_summary(self):
        response = self.client.get(
            "/api/v1/versioning/compare/",
            {
                "resource_type": "contract",
                "id_a": str(self.c1.id),
                "id_b": str(self.c2.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("version_a", response.data)
        self.assertIn("version_b", response.data)
        self.assertEqual(response.data["version_a"], 1)
        self.assertEqual(response.data["version_b"], 2)

    def test_compare_missing_id_a_returns_400(self):
        response = self.client.get(
            "/api/v1/versioning/compare/",
            {"resource_type": "contract", "id_b": str(self.c2.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compare_tenant_isolation_returns_404_for_other_tenant_id(self):
        other_tenant = Tenant.objects.create(
            name="T2",
            slug="t2",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        other_c = _create_contract(other_tenant, asset=None, version=1)
        response = self.client.get(
            "/api/v1/versioning/compare/",
            {
                "resource_type": "contract",
                "id_a": str(self.c1.id),
                "id_b": str(other_c.id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
