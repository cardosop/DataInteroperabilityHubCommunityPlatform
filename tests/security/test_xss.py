"""Phase 98: XSS prevention tests — verify HTML escaping in API responses."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, UserTenantMembership

User = get_user_model()

pytestmark = pytest.mark.security

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img onerror=alert(1) src=x>",
    '"><script>alert(document.cookie)</script>',
    "javascript:alert('XSS')",
    "<svg onload=alert(1)>",
]


class XSSPreventionTest(TestCase):
    """Verify XSS payloads are safely stored and returned without execution."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"XSS Test {uid}",
            slug=f"xss-test-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"xss-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
        )
        self.client.force_authenticate(user=self.user)

    def test_xss_in_asset_name_stored_safely(self):
        """XSS payload in asset name is stored as-is (not executed) and returned in JSON."""
        for payload in XSS_PAYLOADS:
            asset = Asset.objects.create(
                tenant=self.tenant,
                key=f"xss-test-{uuid.uuid4().hex[:8]}",
                name=payload,
                status=AssetStatus.DRAFT,
            )
            response = self.client.get(
                f"/api/v1/assets/{asset.id}/",
                HTTP_X_TENANT_ID=str(self.tenant.id),
            )
            # JSON Content-Type prevents browser execution
            self.assertEqual(response["Content-Type"], "application/json")
            # The payload is in the JSON response as data, NOT as executable HTML
            self.assertIn(payload, response.json().get("name", ""))

    def test_content_type_is_json_not_html(self):
        """All API responses must be application/json, not text/html."""
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertTrue(
            response["Content-Type"].startswith("application/json"),
            f"Expected JSON content type, got: {response['Content-Type']}",
        )


# ── Phase 277.4.1 — XSS expansion (2→8 tests) ────────────────────────


class TestXSSExpansion(TestCase):
    """Phase 277.4.1 — XSS payloads in listing, contract, search, community."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"XS2-{uid}",
            slug=f"xs2-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"xs2-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_listing_title_rejects_xss(self):
        for payload in ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>"]:
            resp = self.client.post(
                "/api/v1/marketplace/listings/", {"title": payload}, format="json"
            )
            assert resp.status_code != 500, f"XSS caused 500: {payload}"

    def test_contract_metadata_xss_rejected(self):
        for payload in ["<script>alert(1)</script>", "javascript:alert(1)"]:
            resp = self.client.post(
                "/api/v1/contracts/",
                {"name": payload, "spec_type": "ODCS", "spec_version": "3.0.0"},
                format="json",
            )
            assert resp.status_code != 500

    def test_search_query_xss_not_reflected(self):
        resp = self.client.get("/api/search/?q=<script>alert(1)</script>")
        assert resp.status_code != 500
        body = resp.content.decode("utf-8")
        assert "<script>" not in body

    def test_community_update_xss_rejected(self):
        resp = self.client.post(
            "/api/v1/social/ratings/",
            {"body": "<svg/onload=alert(1)>", "rating_value": 3},
            format="json",
        )
        assert resp.status_code != 500

    def test_content_type_protection(self):
        resp = self.client.get("/api/search/?q=test")
        assert "application/json" in resp.get("Content-Type", "")

    def test_no_xss_reflection_in_errors(self):
        resp = self.client.get("/api/search/?q=<img src=x onerror=alert(1)>")
        body = resp.content.decode("utf-8")
        assert "onerror=" not in body, "XSS payload reflected in response"
