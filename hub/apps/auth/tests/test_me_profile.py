"""
Unit tests for PATCH /auth/me/ — User profile update (Phase 7 useronboardfix).

Tests cover:
- Profile update (display_name, avatar, preferences)
- Validation (invalid avatar URL, invalid preferences)
- Permissions (authenticated only; user can only update own profile)
- Cache invalidation after update

No mocks/stubs — uses real DB and auth.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MeProfileUpdateTest(TestCase):
    """Test PATCH /auth/me/ profile update."""

    def setUp(self):
        self.client = APIClient()
        call_command("seed_default_plans")

        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Profile Test Tenant {unique_id}",
            slug=f"profile-test-{unique_id}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        TenantConfig.objects.create(tenant=self.tenant)
        plan = TenantPlan.objects.get(slug="free", is_active=True)
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        Subscription.objects.create(
            tenant=self.tenant,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
        )

        self.user = User.objects.create_user(
            email="profileuser@example.com",
            password="SecurePass123",
            tenant=self.tenant,
            display_name="Original Name",
        )
        self.user.status = "ACTIVE"
        self.user.save()

    def _login(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "profileuser@example.com", "password": "SecurePass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return token

    def test_patch_display_name_updates_user(self):
        """PATCH with display_name updates user and returns updated data."""
        self._login()
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"display_name": "Updated Display Name"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Display Name")

        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "Updated Display Name")

    def test_patch_avatar_updates_user(self):
        """PATCH with avatar URL updates user.avatar_url."""
        self._login()
        avatar_url = "https://example.com/avatars/user123.png"
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"avatar": avatar_url},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["avatar"], avatar_url)

        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_url, avatar_url)

    def test_patch_preferences_updates_user(self):
        """PATCH with preferences updates user.preferences."""
        self._login()
        prefs = {"theme": "dark", "language": "en"}
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"preferences": prefs},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["preferences"], prefs)

        self.user.refresh_from_db()
        self.assertEqual(self.user.preferences, prefs)

    def test_patch_partial_update_preserves_other_fields(self):
        """PATCH with only display_name preserves avatar and preferences."""
        self.user.avatar_url = "https://example.com/old.png"
        self.user.preferences = {"theme": "light"}
        self.user.save()

        self._login()
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"display_name": "New Name Only"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "New Name Only")
        self.assertEqual(response.data["avatar"], "https://example.com/old.png")
        self.assertEqual(response.data["preferences"], {"theme": "light"})

        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "New Name Only")
        self.assertEqual(self.user.avatar_url, "https://example.com/old.png")
        self.assertEqual(self.user.preferences, {"theme": "light"})

    def test_patch_invalid_avatar_url_returns_400(self):
        """PATCH with invalid avatar URL returns 400."""
        self._login()
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"avatar": "not-a-valid-url"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("avatar", response.data)

    def test_patch_invalid_preferences_returns_400(self):
        """PATCH with non-dict preferences returns 400."""
        self._login()
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"preferences": ["not", "a", "dict"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("preferences", response.data)

    def test_patch_preferences_too_large_returns_400(self):
        """PATCH with preferences exceeding 10KB returns 400."""
        self._login()
        large_value = "x" * 10241
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"preferences": {"key": large_value}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("preferences", response.data)

    def test_patch_unauthenticated_returns_401(self):
        """PATCH without token returns 401."""
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"display_name": "Should Fail"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_empty_display_name_sets_null(self):
        """PATCH with empty display_name sets it to null."""
        self._login()
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"display_name": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["name"])

        self.user.refresh_from_db()
        self.assertIsNone(self.user.display_name)

    def test_patch_invalidates_cache(self):
        """PATCH invalidates GET cache so next GET returns fresh data."""
        self._login()
        # Prime cache
        self.client.get("/api/v1/auth/me/")
        # Update via PATCH
        self.client.patch(
            "/api/v1/auth/me/",
            {"display_name": "Cached Update"},
            format="json",
        )
        # Next GET must return updated data (not cached old)
        get_resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(get_resp.data["name"], "Cached Update")

    def test_get_me_includes_avatar_and_preferences(self):
        """GET /auth/me/ includes avatar and preferences in response."""
        self.user.avatar_url = "https://gravatar.com/avatar.png"
        self.user.preferences = {"notifications": True}
        self.user.save()

        self._login()
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["avatar"], "https://gravatar.com/avatar.png")
        self.assertEqual(response.data["preferences"], {"notifications": True})
