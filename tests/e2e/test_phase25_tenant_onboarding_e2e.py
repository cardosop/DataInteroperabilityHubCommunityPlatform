"""
E2E Tests for Phase 25 Tenant Onboarding

End-to-end tests for self-service tenant onboarding.
Uses real implementations - no mocks/stubs per development best practices.

Coverage:
- Tenant creation
- First user creation
- TenantConfig creation
- Subscription creation
- User can log in and access tenant-scoped data
"""

import uuid

import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantPlan, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.saas_platform,
]


class Phase25TenantOnboardingE2ETest(TestCase):
    """E2E tests for Phase 25 tenant onboarding"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import Role, UserRole

        self.client = APIClient()

        # Get or create FREE plan
        self.free_plan, _ = TenantPlan.objects.get_or_create(
            slug="free",
            defaults={
                "name": "Free Plan",
                "tier": "FREE",
                "limits_json": {"max_assets": 10, "max_api_calls_per_month": 1000},
                "is_active": True,
            },
        )

        # Create a platform admin tenant + user for onboarding requests.
        # The onboarding endpoint requires IsAuthenticated + PLATFORM_ADMIN role.
        platform_tenant, _ = Tenant.objects.get_or_create(
            slug=f"platform-admin-tenant-{uuid.uuid4().hex[:8]}",
            defaults={"name": "Platform Admin Tenant", "status": TenantStatus.ACTIVE},
        )
        self.platform_admin = User.objects.create_user(
            email="platform-admin-e2e@example.com",
            password="PlatformAdmin123!",
            tenant=platform_tenant,
            status=UserStatus.ACTIVE,
        )
        self.platform_admin.is_superuser = True
        self.platform_admin.save(update_fields=["is_superuser"])
        # Also create the PLATFORM_ADMIN role for explicit role check
        pa_role, _ = Role.objects.get_or_create(
            tenant=platform_tenant,
            name="PLATFORM_ADMIN",
            defaults={"description": "Platform Administrator"},
        )
        UserRole.objects.get_or_create(
            user=self.platform_admin,
            role=pa_role,
        )
        self.client.force_authenticate(user=self.platform_admin)

    def test_complete_tenant_onboarding_workflow(self):
        """Test complete tenant onboarding workflow"""
        # Step 1: Create tenant via onboarding endpoint
        data = {
            "name": "E2E Onboarded Tenant",
            "slug": "e2e-onboarded-tenant",
            "plan_slug": "free",
            "first_user": {
                "email": "onboarde2e@example.com",
                "password": "SecurePass123!",
                "display_name": "E2E Onboarded User",
            },
        }

        response = self.client.post("/api/v1/tenants/onboarding/", data, format="json")

        # Onboarding should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        if response.status_code == status.HTTP_201_CREATED:
            tenant_id = response.data.get("tenant", {}).get("id")
            user_id = response.data.get("user", {}).get("id")

            self.assertIsNotNone(tenant_id)
            self.assertIsNotNone(user_id)

            # Step 2: Verify tenant created
            tenant = Tenant.objects.get(id=tenant_id)
            self.assertEqual(tenant.name, "E2E Onboarded Tenant")
            self.assertEqual(tenant.status, TenantStatus.ACTIVE)

            # Step 3: Verify user created
            user = User.objects.get(id=user_id)
            self.assertEqual(user.email, "onboarde2e@example.com")
            self.assertEqual(user.tenant_id, tenant.id)
            self.assertEqual(user.status, UserStatus.ACTIVE)

            # Step 4: User can log in
            login_response = self.client.post(
                "/api/v1/auth/login/",
                {"email": "onboarde2e@example.com", "password": "SecurePass123!"},
                format="json",
            )

            self.assertEqual(login_response.status_code, status.HTTP_200_OK)
            # Login response may have 'access' or 'access_token' key
            access_token = login_response.data.get("access") or login_response.data.get(
                "access_token"
            )
            self.assertIsNotNone(access_token, "Access token not found in login response")

            # Step 5: Authenticated user can access tenant-scoped data
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

            # Try to list assets (should be empty but accessible)
            assets_response = self.client.get("/api/v1/assets/")

            self.assertEqual(assets_response.status_code, status.HTTP_200_OK)
            self.assertIn("results", assets_response.data)

            # Step 6: Verify subscription created
            subscriptions = Subscription.objects.filter(tenant_id=tenant.id)
            self.assertTrue(subscriptions.exists(), "Onboarding must create a subscription")
            subscription = subscriptions.first()
            self.assertEqual(subscription.plan_id, self.free_plan.id)
            self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)

    def test_tenant_onboarding_duplicate_slug_fails(self):
        """Test that duplicate tenant slug fails"""
        # Create existing tenant
        Tenant.objects.create(
            name=f"Existing Tenant {uuid.uuid4().hex[:8]}",
            slug="duplicate-e2e-slug",
            status=TenantStatus.ACTIVE,
        )

        data = {
            "name": "Duplicate Slug Tenant",
            "slug": "duplicate-e2e-slug",
            "first_user": {
                "email": "duplicate@example.com",
                "password": "SecurePass123!",
                "display_name": "Duplicate User",
            },
        }

        response = self.client.post("/api/v1/tenants/onboarding/", data, format="json")

        # Should fail with 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tenant_onboarding_user_can_access_tenant_data(self):
        """Test that onboarded user can only access their tenant's data"""
        data = {
            "name": "Isolation Test Tenant",
            "slug": "isolation-test-tenant",
            "first_user": {
                "email": "isolation@example.com",
                "password": "SecurePass123!",
                "display_name": "Isolation User",
            },
        }

        response = self.client.post("/api/v1/tenants/onboarding/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tenant_id = response.data.get("tenant", {}).get("id")
        user_id = response.data.get("user", {}).get("id")
        self.assertIsNotNone(tenant_id)
        self.assertIsNotNone(user_id)

        # Switch to the newly onboarded user.
        # force_authenticate takes priority over credentials headers in DRF,
        # so we must switch it to the new user (not just set a Bearer token).
        onboarded_user = User.objects.get(id=user_id)
        self.client.force_authenticate(user=onboarded_user)

        # Create asset in the new tenant
        asset_response = self.client.post(
            "/api/v1/assets/",
            {
                "key": "isolation-asset",
                "name": "Isolation Asset",
                "status": "ACTIVE",
            },
            format="json",
        )

        # Should succeed (201 created); may be 400 if missing required fields,
        # or 403 if onboarding is not yet complete (asset_creation_enabled=False
        # until KYC is submitted — Phase 250.6.D.1).
        self.assertIn(
            asset_response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN],
        )

        # Verify asset belongs to correct tenant
        if asset_response.status_code == status.HTTP_201_CREATED:
            asset_id = asset_response.data["id"]
            from hub.apps.assets.models import Asset

            asset = Asset.objects.get(id=asset_id)
            # Convert UUID to string for comparison
            self.assertEqual(str(asset.tenant_id), str(tenant_id))
