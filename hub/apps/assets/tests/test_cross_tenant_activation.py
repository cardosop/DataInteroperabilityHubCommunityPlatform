"""
Phase 277.2.2 (P1-2) — Cross-tenant activation isolation.

Tenant A creates an Asset.  Tenant B attempts to POST activate it.
The ``AssetViewSet.get_queryset()`` is tenant-scoped, so Tenant B
receives 404 — the asset is invisible to Tenant B.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus


@pytest.mark.integration
class TestCrossTenantActivation(TestCase):
    """Tenant B cannot activate Tenant A's asset."""

    def setUp(self):
        # Tenant A (owner)
        self.tenant_a = Tenant.objects.create(
            name="Cross-Act A",
            slug=f"cross-act-a-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user_a = User.objects.create_user(
            email=f"act-a-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant_a,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="Asset A",
            status=AssetStatus.DRAFT,
            created_by=self.user_a,
        )
        ensure_tenant_has_active_subscription(self.tenant_a)
        # Grant user_a DATA_PROVIDER role so the user context resolves
        # correctly through the auth middleware pipeline — without a
        # role, get_request_tenant_id() cannot determine the tenant and
        # the queryset collapses to Asset.objects.none() → 404.
        role_a = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="DATA_PROVIDER",
        )[0]
        UserRole.objects.get_or_create(
            user=self.user_a,
            tenant=self.tenant_a,
            role=role_a,
        )

        # Tenant B (attacker)
        self.tenant_b = Tenant.objects.create(
            name="Cross-Act B",
            slug=f"cross-act-b-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user_b = User.objects.create_user(
            email=f"act-b-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant_b,
            status=UserStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(self.tenant_b)
        # Grant user_b assets:write scope via DATA_PROVIDER role so the
        # HasScope permission check passes and the tenant-scoped queryset
        # returns 404 (not 403) for cross-tenant access.
        role_b = Role.objects.get_or_create(
            tenant=self.tenant_b,
            name="DATA_PROVIDER",
        )[0]
        UserRole.objects.get_or_create(
            user=self.user_b,
            tenant=self.tenant_b,
            role=role_b,
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
        self.assertIn("error", resp.json())

    # ── GET ────────────────────────────────────────────────────────

    @pytest.mark.integration
    def test_tenant_b_cannot_retrieve_asset(self):
        """Tenant B GET-ing Tenant A's asset → 404."""
        client = APIClient()
        client.force_authenticate(user=self.user_b)
        url = f"/api/v1/assets/{self.asset.id}/"
        resp = client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", resp.json())

    # ── PATCH ──────────────────────────────────────────────────────

    @pytest.mark.integration
    def test_tenant_b_patch_returns_404(self):
        """Tenant B PATCH-ing Tenant A's asset → 404."""
        client = APIClient()
        client.force_authenticate(user=self.user_b)
        url = f"/api/v1/assets/{self.asset.id}/"
        resp = client.patch(url, {"name": "Hijacked"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", resp.json())

    # ── Tenant A can still reach own asset ─────────────────────────

    @pytest.mark.integration
    def test_tenant_a_can_retrieve_own_asset(self):
        """Smoke: Tenant A retains read access to own asset."""
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        url = f"/api/v1/assets/{self.asset.id}/"
        resp = client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["key"], self.asset.key)
        self.assertEqual(resp.json()["name"], self.asset.name)
