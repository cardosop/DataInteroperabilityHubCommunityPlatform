"""
Security tests for versioning endpoints (Task 8.6.5).

- Authentication: unauthenticated requests to versioning endpoints return 401.
- Tenant isolation: user B cannot list/retrieve versions for tenant A's resources.

Uses real API client and backend; no mocks or stubs.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.security]


def _create_contract(tenant, asset=None, version=1, **kwargs):
    defaults = {
        "original_raw": '{"info": {"name": "c1"}}',
        "original_format": OriginalFormat.JSON,
        "original_spec_type": OriginalSpecType.ODCS,
        "original_spec_version": "3.0.2",
    }
    defaults.update(kwargs)
    return Contract.objects.create(
        tenant=tenant, asset=asset, version=version, status=ContractStatus.DRAFT, **defaults
    )


class VersioningSecurityTestBase(TestCase):
    """Base for versioning security tests: two tenants, two users."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(
            name="Versioning Security Tenant A",
            slug=f"versioning-security-tenant-a-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.tenant_b = Tenant.objects.create(
            name="Versioning Security Tenant B",
            slug=f"versioning-security-tenant-b-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user_a = self._create_user("verseca@example.com", self.tenant_a)
        self.user_b = self._create_user("versecb@example.com", self.tenant_b)

    def _create_user(self, email, tenant):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.create_user(
            email=email,
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )


class VersioningAuthenticationSecurityTest(VersioningSecurityTestBase):
    """Authentication: versioning endpoints require an authenticated user."""

    def test_versioning_list_unauthenticated_returns_401(self):
        """GET /api/v1/versioning/versions/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get(
            "/api/v1/versioning/versions/",
            {"resource_type": "contract", "resource_id": str(uuid.uuid4())},
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            "Versioning list must require authentication",
        )

    def test_versioning_retrieve_unauthenticated_returns_401(self):
        """GET /api/v1/versioning/versions/{id}/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get(
            f"/api/v1/versioning/versions/{uuid.uuid4()}/",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            "Versioning retrieve must require authentication",
        )

    def test_versioning_compare_unauthenticated_returns_401(self):
        """GET /api/v1/versioning/compare/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get(
            "/api/v1/versioning/compare/",
            {"resource_type": "contract", "id_a": str(uuid.uuid4()), "id_b": str(uuid.uuid4())},
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            "Versioning compare must require authentication",
        )


class VersioningTenantIsolationSecurityTest(VersioningSecurityTestBase):
    """Tenant isolation: user cannot see another tenant's versions."""

    def test_list_versions_tenant_b_gets_empty_for_tenant_a_asset(self):
        """User B listing versions for tenant A's asset gets empty (tenant-scoped)."""
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            key="versec-asset-a",
            name="Asset A",
            status=AssetStatus.DRAFT,
        )
        _create_contract(self.tenant_a, asset=asset_a, version=1)
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(
            "/api/v1/versioning/versions/",
            {"resource_type": "contract", "resource_id": str(asset_a.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = getattr(response, "data", None) or {}
        results = data.get("results") if isinstance(data, dict) else []
        results = results or []
        self.assertEqual(
            len(results),
            0,
            "Tenant B must not see tenant A's contract versions",
        )

    def test_retrieve_version_returns_404_for_other_tenant_contract(self):
        """GET .../versions/{id}/ for tenant A's contract as user B returns 404."""
        contract_a = _create_contract(self.tenant_a, asset=None, version=1)
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(
            f"/api/v1/versioning/versions/{contract_a.id}/",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Tenant B must not retrieve tenant A's version by id",
        )

    def test_compare_versions_returns_404_for_other_tenant_contracts(self):
        """GET .../compare/ with tenant A's contract IDs as user B returns 404."""
        contract_a1 = _create_contract(self.tenant_a, asset=None, version=1)
        contract_a2 = _create_contract(self.tenant_a, asset=None, version=2)
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(
            "/api/v1/versioning/compare/",
            {
                "resource_type": "contract",
                "id_a": str(contract_a1.id),
                "id_b": str(contract_a2.id),
            },
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Tenant B must not compare tenant A's versions",
        )
