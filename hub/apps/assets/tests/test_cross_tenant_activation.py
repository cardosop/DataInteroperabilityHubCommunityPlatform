"""
Phase 277.2.2 (P1-2) — Cross-tenant activation isolation.

Tenant A creates an Asset.  Tenant B attempts to POST activate it.
The ``AssetViewSet.get_queryset()`` is tenant-scoped, so Tenant B
receives 404 — the asset is invisible to Tenant B.
"""
from __future__ import annotations
import pytest

import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription


@pytest.mark.integration
class TestCrossTenantActivation(TestCase):
    """Tenant B cannot activate Tenant A's asset."""

    @classmethod
    def setUpTestData(cls):
        # Tenant A (owner)
        cls.tenant_a = Tenant.objects.create(
            name="Cross-Act A", slug=f"cross-act-a-{uuid.uuid4().hex[:8]}",
            status="ACTIVE", kyc_status=KYCStatus.VERIFIED,
        )
        cls.user_a = User.objects.create_user(
            email=f"act-a-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123", tenant=cls.tenant_a, status=UserStatus.ACTIVE,
        )
        cls.asset = Asset.objects.create(
            tenant=cls.tenant_a, key=f"asset-{uuid.uuid4().hex[:6]}",
            name="Asset A", status=AssetStatus.DRAFT, created_by=cls.user_a,
        )
        ensure_tenant_has_active_subscription(cls.tenant_a)

        # Tenant B (attacker)
        cls.tenant_b = Tenant.objects.create(
            name="Cross-Act B", slug=f"cross-act-b-{uuid.uuid4().hex[:8]}",
            status="ACTIVE", kyc_status=KYCStatus.VERIFIED,
        )
        cls.user_b = User.objects.create_user(
            email=f"act-b-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123", tenant=cls.tenant_b, status=UserStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(cls.tenant_b)
        # Grant user_b assets:write scope via DATA_PROVIDER role so the
        # HasScope permission check passes and the tenant-scoped queryset
        # returns 404 (not 403) for cross-tenant access.
        role_b = Role.objects.get_or_create(
            tenant=cls.tenant_b, name="DATA_PROVIDER",
        )[0]
        UserRole.objects.get_or_create(
            user=cls.user_b, tenant=cls.tenant_b, role=role_b,
        )

    # ── POST activate ──────────────────────────────────────────────

    @pytest.mark.integration
    def test_tenant_b_activate_returns_404(self):
        """Tenant B POST activate on Tenant A's asset → 404."""
        client = APIClient()
        client.force_authenticate(user=self.user_b)
        url = f"/api/v1/assets/{self.asset.id}/activate/"
        resp = client.post(url, {"version": self.asset.version}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── GET ────────────────────────────────────────────────────────

    @pytest.mark.integration
    def test_tenant_b_cannot_retrieve_asset(self):
        """Tenant B GET-ing Tenant A's asset → 404."""
        client = APIClient()
        client.force_authenticate(user=self.user_b)
        url = f"/api/v1/assets/{self.asset.id}/"
        resp = client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── PATCH ──────────────────────────────────────────────────────

    @pytest.mark.integration
    def test_tenant_b_patch_returns_404(self):
        """Tenant B PATCH-ing Tenant A's asset → 404."""
        client = APIClient()
        client.force_authenticate(user=self.user_b)
        url = f"/api/v1/assets/{self.asset.id}/"
        resp = client.patch(url, {"name": "Hijacked"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── Tenant A can still reach own asset ─────────────────────────

    @pytest.mark.integration
    def test_tenant_a_can_retrieve_own_asset(self):
        """Smoke: Tenant A retains read access to own asset."""
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        url = f"/api/v1/assets/{self.asset.id}/"
        resp = client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
