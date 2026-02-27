"""
Security tests for data mesh endpoints (Task 8.6.4).

- Authentication: unauthenticated requests to mesh endpoints return 401.
- Tenant isolation: user from tenant B cannot retrieve/list domains of tenant A.

Uses real API client and backend; no mocks or stubs.
"""

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.mesh.models import DataMeshDomain, DomainStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class DataMeshSecurityTestBase(TestCase):
    """Base for data mesh security tests: two tenants, two users."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(
            name="Mesh Security Tenant A",
            slug="mesh-security-tenant-a",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.tenant_b = Tenant.objects.create(
            name="Mesh Security Tenant B",
            slug="mesh-security-tenant-b",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user_a = self._create_user("meshseca@example.com", self.tenant_a)
        self.user_b = self._create_user("meshsecb@example.com", self.tenant_b)

    def _create_user(self, email, tenant):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            email=email,
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )


class DataMeshAuthenticationSecurityTest(DataMeshSecurityTestBase):
    """Authentication: data mesh endpoints require an authenticated user."""

    def test_mesh_domains_list_unauthenticated_returns_401(self):
        """GET /api/v1/mesh/domains/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/mesh/domains/")
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            "Mesh domains list must require authentication",
        )


class DataMeshTenantIsolationSecurityTest(DataMeshSecurityTestBase):
    """Tenant isolation: user cannot access another tenant's mesh domains."""

    def test_mesh_domain_retrieve_returns_404_for_other_tenant(self):
        """GET .../mesh/domains/{id}/ for other tenant's domain returns 404."""
        domain_a = DataMeshDomain.objects.create(
            tenant=self.tenant_a,
            name="Domain A",
            description="Tenant A domain",
            status=DomainStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(f"/api/v1/mesh/domains/{domain_a.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant mesh domain access must be 403 or 404",
        )

    def test_mesh_domains_list_returns_only_own_tenant(self):
        """GET /api/v1/mesh/domains/ as user B must not include tenant A's domains."""
        DataMeshDomain.objects.create(
            tenant=self.tenant_a,
            name="Domain A",
            description="Tenant A domain",
            status=DomainStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get("/api/v1/mesh/domains/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        if isinstance(data, dict):
            results = data.get("results") or []
        else:
            results = data if isinstance(data, list) else []
        ids = [str(r.get("id")) for r in results if isinstance(r, dict) and r.get("id")]
        domain_a_ids = list(
            DataMeshDomain.objects.filter(
                tenant=self.tenant_a
            ).values_list("id", flat=True)
        )
        for did in domain_a_ids:
            self.assertNotIn(
                str(did),
                ids,
                "Tenant B must not see tenant A's mesh domains in list",
            )
