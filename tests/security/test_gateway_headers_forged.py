"""
Phase 13: Forged gateway headers must not override tenant/user.

Regression test: a direct request to api-service with forged
X-Gateway-Tenant-ID and X-Gateway-User-ID must NOT change the authenticated
tenant or user. api-service derives tenant/user only from JWT, API key, or
session; it does not read gateway headers for auth.

Uses real DB, real API key, real API; no mocks.
"""
import pytest
from pathlib import Path

from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.auth.models import APIKey
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


# Security marker for all tests in this module
pytestmark = pytest.mark.security

# Hub root (project root / hub)
HUB_ROOT = Path(__file__).resolve().parent.parent.parent / "hub"
GATEWAY_HEADER_MARKERS = (
    "X-Gateway-Tenant-ID",
    "X-Gateway-User-ID",
    "HTTP_X_GATEWAY_TENANT_ID",
    "HTTP_X_GATEWAY_USER_ID",
)


def _hub_files_that_must_not_use_gateway_headers():
    """Paths under hub/ that set tenant/user from request (must not use gateway)."""
    return [
        HUB_ROOT / "apps/auth/middleware.py",
        HUB_ROOT / "apps/auth/authentication.py",
        HUB_ROOT / "apps/tenants/middleware.py",
    ]


class TestGatewayHeadersNotUsedForAuth:
    """
    Static check: hub (api-service) must not read X-Gateway-* headers for auth.
    No DB required; runs fast in any environment.
    """

    def test_auth_and_tenant_code_do_not_reference_gateway_headers(self):
        """Auth/middleware code must not read X-Gateway-Tenant-ID or X-Gateway-User-ID."""
        for path in _hub_files_that_must_not_use_gateway_headers():
            assert path.exists(), f"Expected file missing: {path}"
            content = path.read_text()
            for marker in GATEWAY_HEADER_MARKERS:
                assert marker not in content, (
                    f"{path.name} must not reference gateway header {marker!r}; "
                    "api-service derives tenant/user only from JWT, API key, or session."
                )

# Use local memory cache in tests to avoid Redis connection/blocking in
# container; asserts auth/tenant behavior, not cache behavior.
CACHES_LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "gateway-headers-test",
    }
}


@pytest.mark.django_db
@override_settings(CACHES=CACHES_LOCMEM)
class TestForgedGatewayHeadersDoNotOverrideAuth(TestCase):
    """
    Forged X-Gateway-Tenant-ID / X-Gateway-User-ID must not override
    authenticated tenant/user (no cross-tenant escalation).
    """

    def setUp(self):
        self.client = APIClient()

        # Tenant A and user A (owner of API key)
        self.tenant_a = Tenant.objects.create(
            name="Tenant A",
            slug="tenant-a-gateway-test",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user_a = User.objects.create_user(
            email="user-a@gateway-test.example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        self.api_key_a = APIKey.objects.create(
            tenant=self.tenant_a,
            user=self.user_a,
            key_hash=key_hash,
            name="API Key Tenant A",
            scopes=["assets:read", "assets:write"],
        )
        self.plaintext_key_a = plaintext_key

        # Asset belonging to tenant A (so we can assert scope)
        self.asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            key="asset-a-gateway-test",
            name="Asset A",
            description="Asset in tenant A",
            status=AssetStatus.ACTIVE,
        )

        # Tenant B and user B (used only as forged header values)
        self.tenant_b = Tenant.objects.create(
            name="Tenant B",
            slug="tenant-b-gateway-test",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user_b = User.objects.create_user(
            email="user-b@gateway-test.example.com",
            password="testpass123",
            tenant=self.tenant_b,
            status=UserStatus.ACTIVE,
        )
        # No asset in tenant B — so if api-service ever trusted forged
        # headers we would get empty list; we expect tenant A's asset.

    def test_forged_gateway_headers_ignored_by_middleware(self):
        """
        Middleware must set tenant from API key only; forged X-Gateway-Tenant-ID
        must be ignored (no code path reads it).
        """
        factory = RequestFactory()
        get_response = lambda r: None
        middleware = TenantScopingMiddleware(get_response)
        request = factory.get(
            "/api/v1/assets/",
            HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_key_a}",
            HTTP_X_GATEWAY_TENANT_ID=str(self.tenant_b.id),
            HTTP_X_GATEWAY_USER_ID=str(self.user_b.id),
            HTTP_X_GATEWAY_REQUEST_ID="forged-id",
        )
        middleware.process_request(request)
        self.assertTrue(
            hasattr(request, "tenant_id") and request.tenant_id,
            "Middleware must set tenant_id from API key",
        )
        self.assertEqual(
            str(request.tenant_id),
            str(self.tenant_a.id),
            "Tenant must come from API key (tenant A), not from forged "
            "X-Gateway-Tenant-ID (tenant B).",
        )

    def test_forged_gateway_headers_do_not_override_tenant_user_with_api_key(self):
        """
        Request with valid API key (tenant A) and forged X-Gateway-Tenant-ID /
        X-Gateway-User-ID (tenant B / user B) must be scoped to tenant A.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_key_a}")
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_GATEWAY_TENANT_ID=str(self.tenant_b.id),
            HTTP_X_GATEWAY_USER_ID=str(self.user_b.id),
            HTTP_X_GATEWAY_REQUEST_ID="forged-request-id",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Expected 200 with valid API key; got %s: %s"
            % (response.status_code, getattr(response, "data", response.content)),
        )
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        if not isinstance(results, list):
            results = [data] if data else []
        # Must see tenant A's asset; if api-service trusted forged headers we
        # would be scoped to tenant B and see no assets
        ids = [r.get("id") for r in results if r.get("id")]
        self.assertIn(
            str(self.asset_a.id),
            ids,
            "Response must include tenant A's asset; forged headers must not "
            "switch scope to tenant B.",
        )
        # Ensure returned asset is tenant A's
        for item in results:
            if str(item.get("id")) == str(self.asset_a.id):
                self.assertEqual(
                    str(item.get("tenant_id", item.get("tenant", ""))),
                    str(self.tenant_a.id),
                    "Returned asset must belong to tenant A (API key tenant), "
                    "not tenant B (forged header).",
                )
                break
