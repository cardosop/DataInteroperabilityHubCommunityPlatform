"""
Security tests: IDOR (Insecure Direct Object Reference).

Per UPDATE_PLAN_MISSING_COVERAGE_5_6_1 §2 and SECURITY_REVIEW_PHASE_5_2.
Real APIClient; two tenants/users; try to access other tenant's resource;
assert 404 or 403 for cross-tenant or wrong user.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class IDORSecurityTestBase(TestCase):
    """Base for IDOR tests. Two tenants, two users; real client."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(
            name="IDOR Tenant A",
            slug="idor-tenant-a",
        )
        self.tenant_b = Tenant.objects.create(
            name="IDOR Tenant B",
            slug="idor-tenant-b",
        )
        self.user_a = User.objects.create_user(
            email="idora@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        self.user_b = User.objects.create_user(
            email="idorb@example.com",
            password="testpass123",
            tenant=self.tenant_b,
            status=UserStatus.ACTIVE,
        )


class AssetIDORTest(IDORSecurityTestBase):
    """IDOR: user from tenant A must not access tenant B's asset by ID."""

    def test_asset_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET assets/{id}/ for other tenant's asset must return 403 or 404."""
        asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            name="Asset in Tenant B",
            status=AssetStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/assets/{asset_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant asset access must be 403 or 404",
        )

    def test_asset_retrieve_succeeds_for_own_tenant(self):
        """GET assets/{id}/ for own tenant's asset can return 200."""
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            name="Asset in Tenant A",
            status=AssetStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/assets/{asset_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AuditEventIDORTest(IDORSecurityTestBase):
    """IDOR: user from tenant A must not access tenant B's audit event by ID."""

    def test_audit_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET audit-events/{id}/ for other tenant's event must return 403 or 404."""
        event_b = AuditEvent.objects.create(
            tenant=self.tenant_b,
            actor_user=self.user_b,
            resource_type="ASSET",
            action="CREATED",
            details_json={},
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/audit/audit-events/{event_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant audit event access must be 403 or 404",
        )
