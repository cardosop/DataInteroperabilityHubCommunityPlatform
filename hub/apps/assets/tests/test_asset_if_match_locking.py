"""
Phase 250.7.B — PATCH If-Match optimistic-lock contract.

TDD coverage for:
1) stale If-Match -> 412 PRECONDITION_FAILED,
2) current If-Match -> 200,
3) missing If-Match in non-strict mode -> 200 + deprecation warning.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetPatchIfMatchContractTest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Tenant {uid}",
            slug=f"tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create(
            email=f"ifmatch-{uid}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)
        self.client.force_authenticate(user=self.user)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Original",
            created_by=self.user,
        )

    @override_settings(OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=True)
    def test_patch_with_stale_if_match_returns_412(self) -> None:
        response = self.client.patch(
            f"/api/v1/assets/{self.asset.id}/",
            {"name": "Renamed"},
            format="json",
            HTTP_IF_MATCH=str(self.asset.version + 1),
        )

        self.assertEqual(response.status_code, status.HTTP_412_PRECONDITION_FAILED)
        payload = response.json()
        self.assertEqual(payload.get("code"), "PRECONDITION_FAILED")
        details = payload.get("details") or {}
        self.assertEqual(details.get("expected_version"), self.asset.version)
        self.assertEqual(details.get("provided_version"), self.asset.version + 1)

    @override_settings(OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=True)
    def test_patch_with_current_if_match_returns_200(self) -> None:
        response = self.client.patch(
            f"/api/v1/assets/{self.asset.id}/",
            {"name": "Renamed"},
            format="json",
            HTTP_IF_MATCH=str(self.asset.version),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["name"], "Renamed")
        self.assertEqual(payload["version"], self.asset.version + 1)

    @override_settings(OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=False)
    def test_patch_without_if_match_non_strict_returns_200_and_logs_deprecation(self) -> None:
        with self.assertLogs("hub.apps.assets.views", level="WARNING") as captured:
            response = self.client.patch(
                f"/api/v1/assets/{self.asset.id}/",
                {"name": "Renamed"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any("asset_patch_missing_if_match_deprecated" in line for line in captured.output)
        )

    @override_settings(OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=True)
    def test_patch_without_if_match_strict_returns_428(self) -> None:
        response = self.client.patch(
            f"/api/v1/assets/{self.asset.id}/",
            {"name": "Renamed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_428_PRECONDITION_REQUIRED)
        self.assertEqual(response.json().get("code"), "PRECONDITION_REQUIRED")

    def test_db_trigger_increments_version_on_direct_update(self) -> None:
        original_version = self.asset.version
        Asset.objects.filter(pk=self.asset.pk).update(name="Renamed by SQL update")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.version, original_version + 1)

    @override_settings(OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=True)
    def test_patch_with_conflicting_if_match_and_body_version_returns_400(self) -> None:
        response = self.client.patch(
            f"/api/v1/assets/{self.asset.id}/",
            {"name": "Renamed", "version": self.asset.version + 1},
            format="json",
            HTTP_IF_MATCH=str(self.asset.version),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json().get("code"), "VALIDATION_ERROR")
