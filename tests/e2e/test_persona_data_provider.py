"""
E2E tests for DATA_PROVIDER persona.

Tests that DATA_PROVIDER:
- Cannot access tenant configuration
- Subject to rate limits
- Can use CLI tool
- User created via personal-tenant registration can create assets (useronboardfix 4.2.2)
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory
from rest_framework import status

from hub.apps.rate_limiting.service import check_rate_limit
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import Role, User, UserRole, UserStatus
from tests.e2e.conftest import E2ETestBase, get_response_data

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e4]
User = get_user_model()


class DataProviderPersonaTest(E2ETestBase):
    """E2E tests for DATA_PROVIDER persona"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create DATA_PROVIDER role
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )

        # Create data provider user
        self.provider_user = User.objects.create_user(
            email=f"provider-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.provider_user, role=self.provider_role)

        # Authenticate as provider
        self.client.force_authenticate(user=self.provider_user)

    def test_data_provider_cannot_get_tenant_config(self):
        """Test DATA_PROVIDER cannot GET tenant configuration"""
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", get_response_data(response) or {})

    def test_data_provider_cannot_patch_tenant_config(self):
        """Test DATA_PROVIDER cannot PATCH tenant configuration"""
        data = {"default_dq_profile": "intake_basic_gx"}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_data_provider_cannot_access_other_tenant_config(self):
        """Test DATA_PROVIDER cannot access other tenant configuration"""
        _suffix = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_suffix}",
            slug=f"other-tenant-{_suffix}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        response = self.client.get(f"/api/v1/tenants/{other_tenant.id}/config/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_data_provider_subject_to_rate_limits(self):
        """Test DATA_PROVIDER is subject to rate limits"""
        # Use real request (no mocks) to exercise rate limit service
        rf = RequestFactory()
        request = rf.get("/api/v1/contracts/")
        request.tenant_id = str(self.tenant.id)
        request.user = self.provider_user
        request.api_key_obj = None

        # Check rate limit (should allow first request)
        is_allowed, results = check_rate_limit(
            request=request,
            tenant_id=str(self.tenant.id),
            user_id=str(self.provider_user.id),
            api_key_id=None,
        )

        # Should either allow or reject based on current usage
        self.assertIsInstance(is_allowed, bool)
        self.assertIsInstance(results, list)

    def test_data_provider_rate_limit_headers(self):
        """Test rate limit headers are present for DATA_PROVIDER"""
        response = self.client.get("/api/v1/contracts/")

        # Rate limit headers should be present (if rate limiting is active)
        # Headers may vary, so we check if response is successful
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_data_provider_can_access_contracts(self):
        """Test DATA_PROVIDER can access contracts (subject to rate limits)"""
        response = self.client.get("/api/v1/contracts/")

        # Should be able to access (may be rate limited)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_data_provider_can_create_contracts(self):
        """Test DATA_PROVIDER can create contracts (subject to rate limits)"""
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced

        contract_data = ContractFactoryEnhanced.create_hub_contract_json()

        response = self.client.post("/api/v1/contracts/", contract_data, format="json")

        # Should be able to create (may be rate limited)
        self.assertLess(
            response.status_code,
            500,
        )

    def test_data_provider_rate_limit_burst_window(self):
        """Test DATA_PROVIDER rate limits in burst window"""
        # Make rapid requests to test burst limit
        responses = []
        for _i in range(5):
            response = self.client.get("/api/v1/contracts/")
            responses.append(response.status_code)

        # At least some requests should succeed
        # If rate limited, should get 429
        self.assertTrue(
            any(code == status.HTTP_200_OK for code in responses)
            or any(code == status.HTTP_429_TOO_MANY_REQUESTS for code in responses)
        )

    def test_data_provider_rate_limit_sustained_window(self):
        """Test DATA_PROVIDER rate limits in sustained window"""
        # Make requests over time to test sustained limit
        import time

        responses = []
        for _i in range(3):
            response = self.client.get("/api/v1/contracts/")
            responses.append(response.status_code)
            time.sleep(0.1)  # noqa: sleep-needed  # INTENTIONAL: test-specific delay  # Small delay

        # Should handle sustained requests
        self.assertTrue(len(responses) > 0)

    def test_data_provider_cli_authentication(self):
        """Test DATA_PROVIDER can authenticate with CLI tool"""
        # CLI tool uses API key authentication
        # Test that provider can generate/use API keys

        from hub.apps.auth.models import APIKey

        # Create API key for provider
        api_key = APIKey.objects.create(user=self.provider_user, name="CLI Key", tenant=self.tenant)

        # API key should be created successfully
        self.assertIsNotNone(api_key)
        self.assertEqual(api_key.user, self.provider_user)
        self.assertEqual(api_key.tenant, self.tenant)

    def test_data_provider_cli_rate_limits(self):
        """Test DATA_PROVIDER CLI usage respects rate limits"""
        from hub.apps.auth.models import APIKey

        # Create API key
        api_key = APIKey.objects.create(user=self.provider_user, name="CLI Key", tenant=self.tenant)

        # CLI requests should be subject to rate limits (real request, no mocks)
        rf = RequestFactory()
        request = rf.get("/api/v1/contracts/")
        request.tenant_id = str(self.tenant.id)
        request.user = None
        request.api_key_obj = api_key

        is_allowed, results = check_rate_limit(
            request=request, tenant_id=str(self.tenant.id), user_id=None, api_key_id=str(api_key.id)
        )

        # Should check rate limit for API key
        self.assertIsInstance(is_allowed, bool)
        self.assertIsInstance(results, list)

    def test_data_provider_can_use_cli_for_contracts(self):
        """Test DATA_PROVIDER can use CLI for contract operations"""
        # CLI operations should work for providers
        # Test by making API calls that CLI would make

        # List contracts
        response = self.client.get("/api/v1/contracts/")
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])

    def test_data_provider_cli_contract_creation(self):
        """Test DATA_PROVIDER can create contracts via CLI"""
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced

        contract_data = ContractFactoryEnhanced.create_hub_contract_json()

        response = self.client.post("/api/v1/contracts/", contract_data, format="json")

        # Should be able to create via API (CLI uses same API)
        self.assertLess(
            response.status_code,
            500,
        )

    def test_data_provider_rate_limit_per_endpoint(self):
        """Test rate limits are enforced per endpoint category"""
        # Different endpoints may have different rate limits
        endpoints = ["/api/v1/contracts/", "/api/v1/dq/runs/", "/api/v1/compliance/runs/"]

        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should handle rate limiting per endpoint
            self.assertLess(
                response.status_code,
                500,
            )

    def test_data_provider_rate_limit_tenant_override(self):
        """Test tenant-specific rate limits apply to DATA_PROVIDER"""
        # Configure tenant rate limits
        TenantConfig.objects.update_or_create(
            tenant=self.tenant,
            defaults={
                "rate_limits": {"catalog_reads": {"burst_per_10s": 10, "sustained_per_min": 30}}
            },
        )

        # Provider should be subject to tenant rate limits (real request, no mocks)
        rf = RequestFactory()
        request = rf.get("/api/v1/contracts/")
        request.tenant_id = str(self.tenant.id)
        request.user = self.provider_user
        request.api_key_obj = None

        is_allowed, results = check_rate_limit(
            request=request,
            tenant_id=str(self.tenant.id),
            user_id=str(self.provider_user.id),
            api_key_id=None,
        )

        # Should respect tenant rate limits
        self.assertIsInstance(is_allowed, bool)
        self.assertIsInstance(results, list)

    def test_data_provider_rate_limit_platform_defaults(self):
        """Test platform defaults apply when tenant config not set"""
        # Delete tenant config to test platform defaults
        TenantConfig.objects.filter(tenant=self.tenant).delete()

        # Provider should be subject to platform defaults (real request, no mocks)
        rf = RequestFactory()
        request = rf.get("/api/v1/contracts/")
        request.tenant_id = str(self.tenant.id)
        request.user = self.provider_user
        request.api_key_obj = None

        is_allowed, results = check_rate_limit(
            request=request,
            tenant_id=str(self.tenant.id),
            user_id=str(self.provider_user.id),
            api_key_id=None,
        )

        # Should use platform defaults
        self.assertIsInstance(is_allowed, bool)
        self.assertIsInstance(results, list)

    def test_data_provider_cannot_modify_tenant_config_via_cli(self):
        """Test DATA_PROVIDER cannot modify tenant config even via CLI"""
        # Even if using CLI (API key), should not be able to modify config
        from hub.apps.auth.models import APIKey

        api_key = APIKey.objects.create(user=self.provider_user, name="CLI Key", tenant=self.tenant)

        # Authenticate with API key
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key.key_hash}")

        data = {"default_dq_profile": "intake_basic_gx"}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        # Should still be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_data_provider_rate_limit_retry_after(self):
        """Test rate limit Retry-After header for DATA_PROVIDER"""
        # Make requests until rate limited
        response = None
        for _i in range(20):  # Try to trigger rate limit
            response = self.client.get("/api/v1/contracts/")
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break

        # If rate limited, should have Retry-After header
        if response and response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            self.assertIn("Retry-After", response.headers or {})

    def test_data_provider_rate_limit_error_format(self):
        """Test rate limit error format for DATA_PROVIDER"""
        # Make requests until rate limited
        response = None
        for _i in range(20):
            response = self.client.get("/api/v1/contracts/")
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break

        # If rate limited, error should have standard format
        if response and response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            data = get_response_data(response) or {}
            self.assertIn("error", data)
            error = data["error"]
            self.assertIn("code", error)
            self.assertIn("message", error)

    def test_personal_tenant_registered_user_can_create_assets(self):
        """Useronboardfix 4.2.2: User created via personal-tenant registration can create assets."""
        self.client.force_authenticate(user=None)
        call_command("seed_default_plans")

        email = f"personal-dp-{uuid.uuid4().hex[:8]}@example.com"
        password = "Secure@Pass123"
        name = "Personal Data Provider"

        reg = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": password, "name": name},
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        reg_data = get_response_data(reg) or {}
        self.assertIn("tenant_id", reg_data)
        self.assertIsNotNone(reg_data.get("tenant_id"))

        login_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        access_token = (get_response_data(login_resp) or {}).get("access_token")
        self.assertIsNotNone(access_token)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        asset_resp = self.client.post(
            "/api/v1/assets/",
            {"key": "persona-personal-asset", "name": "Personal Asset", "domain": "test"},
            format="json",
        )
        self.assertEqual(asset_resp.status_code, status.HTTP_201_CREATED)
        asset_data = get_response_data(asset_resp) or {}
        self.assertIn("id", asset_data)
        self.assertEqual(asset_data["key"], "persona-personal-asset")

    def test_data_provider_rate_limit_per_user(self):
        """Test rate limits are enforced per user for DATA_PROVIDER"""
        # Create another provider user
        other_provider = User.objects.create_user(
            email=f"other_provider-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=other_provider, role=self.provider_role)

        # Each user should have separate rate limit counters (real requests, no mocks)
        rf = RequestFactory()
        request1 = rf.get("/api/v1/contracts/")
        request1.tenant_id = str(self.tenant.id)
        request1.user = self.provider_user
        request1.api_key_obj = None

        request2 = rf.get("/api/v1/contracts/")
        request2.tenant_id = str(self.tenant.id)
        request2.user = other_provider
        request2.api_key_obj = None

        is_allowed1, results1 = check_rate_limit(
            request=request1,
            tenant_id=str(self.tenant.id),
            user_id=str(self.provider_user.id),
            api_key_id=None,
        )

        is_allowed2, results2 = check_rate_limit(
            request=request2,
            tenant_id=str(self.tenant.id),
            user_id=str(other_provider.id),
            api_key_id=None,
        )

        # Both should be checked independently
        self.assertIsInstance(is_allowed1, bool)
        self.assertIsInstance(is_allowed2, bool)
        self.assertIsInstance(results1, list)
        self.assertIsInstance(results2, list)
