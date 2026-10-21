"""
Security tests for social endpoints (Task 8.6.3).

- Authentication: unauthenticated requests to social endpoints return 401.
- Tenant isolation: user from tenant B cannot access ratings/communities of tenant A.

Uses real API client and backend; no mocks or stubs.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.social.models import Community
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class SocialSecurityTestBase(TestCase):
    """Base for social security tests: two tenants, two users."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(
            name="Social Security Tenant A",
            slug=f"social-security-tenant-a-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.tenant_b = Tenant.objects.create(
            name="Social Security Tenant B",
            slug=f"social-security-tenant-b-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user_a = self._create_user("socseca@example.com", self.tenant_a)
        self.user_b = self._create_user("socsecb@example.com", self.tenant_b)

    def _create_user(self, email, tenant):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.create_user(
            email=email,
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )


class SocialAuthenticationSecurityTest(SocialSecurityTestBase):
    """Authentication: social endpoints require an authenticated user."""

    def test_social_ratings_list_unauthenticated_returns_401(self):
        """GET /api/v1/social/ratings/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/social/ratings/")
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            "Social ratings list must require authentication",
        )

    def test_social_communities_list_unauthenticated_returns_401(self):
        """GET /api/v1/social/communities/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/social/communities/")
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            "Social communities list must require authentication",
        )


class SocialTenantIsolationSecurityTest(SocialSecurityTestBase):
    """Tenant isolation: user cannot access another tenant's social resources."""

    def test_rating_submit_tenant_b_cannot_rate_tenant_a_asset(self):
        """User B rating tenant A's asset gets 403/404 (asset not in tenant)."""
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            name="Asset A",
            status=AssetStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_b)
        response = self.client.post(
            "/api/v1/social/ratings/",
            {"asset_id": str(asset_a.id), "rating": 5},
            format="json",
        )
        self.assertIn(
            response.status_code,
            (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_400_BAD_REQUEST,
            ),
            "Cross-tenant rating on other tenant's asset must be rejected",
        )

    def test_community_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET .../communities/{id}/ for other tenant's community returns 403/404."""
        community_a = Community.objects.create(
            tenant=self.tenant_a,
            name="Community A",
            description="Tenant A community",
        )
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(f"/api/v1/social/communities/{community_a.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant community access must be 403 or 404",
        )
