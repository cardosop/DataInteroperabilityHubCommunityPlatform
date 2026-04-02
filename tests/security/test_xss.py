"""Phase 98: XSS prevention tests — verify HTML escaping in API responses."""
import uuid
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.users.models import UserStatus, UserTenantMembership
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.security

XSS_PAYLOADS = [
    '<script>alert(1)</script>',
    '<img onerror=alert(1) src=x>',
    '"><script>alert(document.cookie)</script>',
    "javascript:alert('XSS')",
    '<svg onload=alert(1)>',
]


class XSSPreventionTest(TestCase):
    """Verify XSS payloads are safely stored and returned without execution."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"XSS Test {uid}", slug=f"xss-test-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"xss-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=self.user, tenant=self.tenant,
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
