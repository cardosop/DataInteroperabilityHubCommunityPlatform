"""
Phase 260.3.B — per-tenant ``datasets_enabled`` + ``files_enabled`` kill switches.

Mirrors the 250.6.A asset-creation pattern: ops flips flags to freeze the
respective REST surfaces; the backend returns HTTP 403 with structured
codes; ``GET /api/v1/capabilities/`` exposes ``datasets`` and ``files``
booleans for SPA route gates.

Tests use real Django ORM + DRF ``APIClient`` (no mocks).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import (
    ensure_user_has_data_provider_role,
    ensure_user_has_tenant_admin_role,
)
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _assert_kill_switch_403(resp, expected_api_code: str):
    """Hub error middleware wraps DRF exceptions in ``error.details``."""
    assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.content
    body = resp.json()
    if body.get("code") == expected_api_code:
        return
    nested = body.get("error", {}).get("details", {})
    assert nested.get("code") == expected_api_code, body


def _seed_tenant(
    *,
    datasets_enabled: bool = True,
    files_enabled: bool = True,
    slug_prefix: str = "t",
):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix} {uid}",
        slug=f"{slug_prefix}-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status="UNVERIFIED",
        datasets_enabled=datasets_enabled,
        files_enabled=files_enabled,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(user)
    return tenant, user


class TenantDatasetsFilesDefaultsTest(TestCase):
    """260.3.B.1 — BooleanField default True (existing + new tenants)."""

    @pytest.mark.integration
    def test_defaults_true_on_new_tenant(self):
        uid = uuid.uuid4().hex[:8]
        t = Tenant.objects.create(
            name=f"dftest {uid}",
            slug=f"dftest-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status="UNVERIFIED",
        )
        self.assertTrue(t.datasets_enabled)
        self.assertTrue(t.files_enabled)


class DatasetsFilesKillSwitchAPITest(TestCase):
    """260.3.B.3 — view dispatch gates entire viewsets."""

    @pytest.mark.integration
    def test_get_files_403_when_files_disabled(self):
        _, user = _seed_tenant(files_enabled=False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/files/")
        _assert_kill_switch_403(resp, "FILES_DISABLED")

    @pytest.mark.integration
    def test_get_datasets_403_when_datasets_disabled(self):
        _, user = _seed_tenant(datasets_enabled=False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/datasets/")
        _assert_kill_switch_403(resp, "DATASETS_DISABLED")

    @pytest.mark.integration
    def test_both_disabled_both_endpoints_403(self):
        _, user = _seed_tenant(datasets_enabled=False, files_enabled=False)
        client = APIClient()
        client.force_authenticate(user=user)
        r1 = client.get("/api/v1/files/")
        r2 = client.get("/api/v1/datasets/")
        _assert_kill_switch_403(r1, "FILES_DISABLED")
        _assert_kill_switch_403(r2, "DATASETS_DISABLED")

    @pytest.mark.integration
    def test_both_enabled_list_succeeds(self):
        _, user = _seed_tenant(datasets_enabled=True, files_enabled=True)
        client = APIClient()
        client.force_authenticate(user=user)
        rf = client.get("/api/v1/files/")
        rd = client.get("/api/v1/datasets/")
        self.assertEqual(rf.status_code, 200, rf.content)
        self.assertEqual(rd.status_code, 200, rd.content)


class DatasetsFilesFeatureFlagPatchWireTest(TestCase):
    """Admin PATCH /me/feature-flags/ must flip DB row and block API (260.3.B ops path)."""

    @pytest.mark.integration
    def test_patch_files_enabled_false_blocks_list_endpoint(self):
        tenant, user = _seed_tenant(files_enabled=True)
        ensure_user_has_tenant_admin_role(user)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.patch(
            "/api/v1/tenants/me/feature-flags/",
            data={"files_enabled": False},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK), resp.content
        tenant.refresh_from_db()
        self.assertFalse(tenant.files_enabled)

        r2 = client.get("/api/v1/files/")
        _assert_kill_switch_403(r2, "FILES_DISABLED")

    @pytest.mark.integration
    def test_patch_datasets_enabled_false_blocks_list_endpoint(self):
        tenant, user = _seed_tenant(datasets_enabled=True)
        ensure_user_has_tenant_admin_role(user)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.patch(
            "/api/v1/tenants/me/feature-flags/",
            data={"datasets_enabled": False},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK), resp.content
        tenant.refresh_from_db()
        self.assertFalse(tenant.datasets_enabled)

        r2 = client.get("/api/v1/datasets/")
        _assert_kill_switch_403(r2, "DATASETS_DISABLED")


class DatasetsFilesCapabilitiesWireTest(TestCase):
    """260.3.B.5 — capabilities map mirrors flags."""

    @pytest.mark.integration
    def test_capabilities_true_when_enabled(self):
        _, user = _seed_tenant(datasets_enabled=True, files_enabled=True)
        client = APIClient()
        client.force_authenticate(user=user)
        caps = client.get("/api/v1/capabilities/").json().get("capabilities", {})
        self.assertTrue(caps.get("datasets"))
        self.assertTrue(caps.get("files"))

    @pytest.mark.integration
    def test_capabilities_reflects_disabled_datasets(self):
        _, user = _seed_tenant(datasets_enabled=False, files_enabled=True)
        client = APIClient()
        client.force_authenticate(user=user)
        caps = client.get("/api/v1/capabilities/").json().get("capabilities", {})
        self.assertFalse(caps.get("datasets"))
        self.assertTrue(caps.get("files"))

    @pytest.mark.integration
    def test_capabilities_reflects_disabled_files(self):
        _, user = _seed_tenant(datasets_enabled=True, files_enabled=False)
        client = APIClient()
        client.force_authenticate(user=user)
        caps = client.get("/api/v1/capabilities/").json().get("capabilities", {})
        self.assertTrue(caps.get("datasets"))
        self.assertFalse(caps.get("files"))
