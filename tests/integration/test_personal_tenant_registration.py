"""
Integration tests for personal tenant registration flow (useronboardfix 2.1.1).

Tests register → login → fetch me, asset creation, marketplace access, and isolation.
Uses real DB and auth; no mocks/stubs.
"""

import uuid

import pytest
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.integration,
]


class PersonalTenantRegistrationIntegrationTest(TestCase):
    """Integration tests: register without tenant_id → personal tenant → full platform use."""

    def setUp(self):
        """Ensure FREE plan exists for personal tenant creation."""
        call_command("seed_default_plans")
        self.client = APIClient()

    def test_register_then_login_then_fetch_me_has_tenant(self):
        """Register without tenant_id, login, GET /auth/me/ returns tenant_id."""
        email = f"int-{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass!123@Test"
        name = "Integration User"

        reg = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": password, "name": name},
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        self.assertIn("tenant_id", reg.data)
        self.assertIsNotNone(reg.data["tenant_id"])

        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        access_token = login.data["access_token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        me = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertIn("tenant_id", me.data)
        self.assertIsNotNone(me.data["tenant_id"])
        self.assertEqual(me.data["tenant_id"], reg.data["tenant_id"])

    def test_register_then_create_asset_in_personal_tenant(self):
        """Register without tenant_id, login, create asset in personal tenant."""
        email = f"asset-{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass!123@Test"
        name = "Asset User"

        reg = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": password, "name": name},
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)

        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")

        asset = self.client.post(
            "/api/v1/assets/",
            {"key": "personal-asset", "name": "Personal Asset", "domain": "test"},
            format="json",
        )
        self.assertEqual(asset.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", asset.data)
        self.assertEqual(asset.data["key"], "personal-asset")

    def test_register_then_access_marketplace_as_consumer(self):
        """Register without tenant_id, login, GET marketplace listings works (DATA_CONSUMER)."""
        email = f"consumer-{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass!123@Test"
        name = "Consumer User"

        reg = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": password, "name": name},
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)

        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")

        listings = self.client.get("/api/v1/marketplace/listings/")
        self.assertEqual(listings.status_code, status.HTTP_200_OK)
        self.assertIn("results", listings.data)

    def test_personal_tenant_isolation_from_other_tenants(self):
        """User with personal tenant cannot access another tenant's resources."""
        from django.db.models.signals import post_save

        from hub.apps.assets.models import Asset
        from hub.apps.contracts.models import Contract
        from hub.apps.semantic.signals import asset_saved, contract_saved

        try:
            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        try:
            email = f"isol-{uuid.uuid4().hex[:8]}@example.com"
            password = "SecurePass!123@Test"
            name = "Isolation User"

            reg = self.client.post(
                "/api/v1/auth/register/",
                {"email": email, "password": password, "name": name},
                format="json",
            )
            self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
            personal_tenant_id = reg.data["tenant_id"]

            login = self.client.post(
                "/api/v1/auth/login/",
                {"email": email, "password": password},
                format="json",
            )
            self.assertEqual(login.status_code, status.HTTP_200_OK)
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")

            other_tenant = Tenant.objects.create(
                name=f"Other Tenant {uuid.uuid4().hex[:8]}",
                slug=f"other-{uuid.uuid4().hex[:8]}",
                status="ACTIVE",
                kyc_status="UNVERIFIED",
            )
            other_asset = Asset.objects.create(
                tenant=other_tenant,
                key="other-asset",
                name="Other Asset",
                domain="test",
            )

            resp = self.client.get(f"/api/v1/assets/{other_asset.id}/")
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

            self.assertNotEqual(str(other_tenant.id), str(personal_tenant_id))
        finally:
            try:
                post_save.connect(contract_saved, sender=Contract, weak=False)
                post_save.connect(asset_saved, sender=Asset, weak=False)
            except (ImportError, AttributeError):
                pass

    def test_register_with_tenant_id_still_works(self):
        """Register with tenant_id provided: user associated with that tenant (unchanged)."""
        other_tenant = Tenant.objects.create(
            name=f"Provided Tenant {uuid.uuid4().hex[:8]}",
            slug=f"provided-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        email = f"provided-{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass!123@Test"
        name = "Provided User"

        reg = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": email,
                "password": password,
                "name": name,
                "tenant_id": str(other_tenant.id),
            },
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reg.data["tenant_id"], str(other_tenant.id))

        user = User.objects.get(email=email)
        self.assertEqual(user.tenant_id, other_tenant.id)
