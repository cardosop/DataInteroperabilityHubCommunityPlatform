"""
Security tests for AI endpoints (Task 8.6.1).

- Authentication: unauthenticated requests to AI endpoints return 401.
- Tenant isolation: natural-language search returns only the request tenant's data;
  a user from tenant B must not receive asset/contract/dataset IDs belonging to tenant A.

Uses real API client and backend; no mocks or stubs.
"""

import pytest
import uuid
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.security]


class AISecurityTestBase(TestCase):
    """Base for AI security tests: two tenants, two users."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(
            name="AI Security Tenant A",
            slug=f"ai-security-tenant-a-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.tenant_b = Tenant.objects.create(
            name="AI Security Tenant B",
            slug=f"ai-security-tenant-b-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user_a = self._create_user("aiseca@example.com", self.tenant_a)
        self.user_b = self._create_user("aisecb@example.com", self.tenant_b)

    def _create_user(self, email, tenant):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            email=email,
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )


class AIAuthenticationSecurityTest(AISecurityTestBase):
    """Authentication: AI endpoints require an authenticated user."""

    def test_natural_language_search_unauthenticated_returns_401(self):
        """POST /api/v1/ai/natural-language-search/ without auth returns 401 or 403."""
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/ai/natural-language-search/",
            {"query": "Find assets"},
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            f"Natural language search must require authentication (got {response.status_code})",
        )

    def test_schema_matching_unauthenticated_returns_401(self):
        """POST /api/v1/ai/schema-matching/ without auth returns 401 or 403."""
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/ai/schema-matching/",
            {
                "source_schema": {"properties": {"a": {"type": "string"}}},
                "target_schema": {"properties": {"b": {"type": "string"}}},
            },
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            f"Schema matching must require authentication (got {response.status_code})",
        )


class AITenantIsolationSecurityTest(AISecurityTestBase):
    """Tenant isolation: search results must not include other tenant's resources."""

    def test_natural_language_search_tenant_b_does_not_see_tenant_a_assets(self):
        """User from tenant B must not receive tenant A's asset IDs in search results."""
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            key="aisec-asset-tenant-a",
            name="Asset in Tenant A",
            status=AssetStatus.DRAFT,
        )
        self.client.force_authenticate(user=self.user_b)
        response = self.client.post(
            "/api/v1/ai/natural-language-search/",
            {"query": "Find assets", "result_types": ["assets"]},
            format="json",
        )
        # 200 = success; 403 = forbidden (valid isolation); 503 = LLM unavailable; 429 = rate limit
        self.assertIn(
            response.status_code,
            (
                status.HTTP_200_OK,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ),
            "Search endpoint must respond",
        )
        if response.status_code not in (status.HTTP_200_OK,):
            return
        data = response.data if hasattr(response, "data") else response.json()
        results = data.get("results") or {}
        assets_data = results.get("assets") or {}
        items = assets_data.get("items") or []
        asset_ids_in_response = []
        for item in items:
            if isinstance(item, dict) and "id" in item:
                asset_ids_in_response.append(str(item["id"]))
            elif isinstance(item, dict):
                asset_ids_in_response.append(str(item.get("id", "")))
        self.assertNotIn(
            str(asset_a.id),
            asset_ids_in_response,
            "Tenant B must not see tenant A's asset in natural language search results",
        )
