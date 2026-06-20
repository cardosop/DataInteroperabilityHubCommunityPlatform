"""
Integration tests for SSO

Tests for SSO authentication flows.
"""

import urllib.parse
import uuid

import pytest
from django.test import TestCase

from hub.apps.auth.sso import SSOService
from hub.apps.tenants.models import Tenant, TenantConfig

pytestmark = pytest.mark.django_db(transaction=True)


class SSOIntegrationTest(TestCase):
    """Integration tests for SSO"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create tenant config with SSO
        self.config = TenantConfig.objects.create(
            tenant=self.tenant,
            sso_config={
                "saml": {"sso_url": "https://saml.example.com/sso", "role_mapping": {}},
                "oidc": {
                    "authorization_endpoint": "https://oidc.example.com/auth",
                    "client_id": "test-client-id",
                    "role_mapping": {},
                },
            },
        )

    def test_saml_provider_retrieval_returns_provider(self):
        """Test SAML provider retrieval returns provider."""
        provider = SSOService.get_provider(str(self.tenant.id), "SAML")
        self.assertIsNotNone(provider)

    def test_saml_provider_retrieval_has_correct_tenant_id(self):
        """Test SAML provider retrieval has correct tenant_id."""
        provider = SSOService.get_provider(str(self.tenant.id), "SAML")
        self.assertEqual(provider.tenant_id, str(self.tenant.id))

    def test_oidc_provider_retrieval_returns_provider(self):
        """Test OIDC provider retrieval returns provider."""
        provider = SSOService.get_provider(str(self.tenant.id), "OIDC")
        self.assertIsNotNone(provider)

    def test_oidc_provider_retrieval_has_correct_tenant_id(self):
        """Test OIDC provider retrieval has correct tenant_id."""
        provider = SSOService.get_provider(str(self.tenant.id), "OIDC")
        self.assertEqual(provider.tenant_id, str(self.tenant.id))

    def test_sso_login_url_generation_saml_returns_url(self):
        """SAML login URL targets the configured sso_url with expected params."""
        saml_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="SAML",
            redirect_uri="https://example.com/callback",
        )
        self.assertIsNotNone(saml_url)
        self.assertIsInstance(saml_url, str)
        parsed = urllib.parse.urlparse(saml_url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.hostname, "saml.example.com")
        self.assertEqual(parsed.path, "/sso")
        self.assertIn("SAMLRequest", parsed.query)

    def test_sso_login_url_generation_oidc_returns_url(self):
        """OIDC login URL targets the configured authorization_endpoint with
        client_id, redirect_uri, response_type, scope, and state."""
        oidc_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback",
        )
        self.assertIsNotNone(oidc_url)
        self.assertIsInstance(oidc_url, str)
        parsed = urllib.parse.urlparse(oidc_url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.hostname, "oidc.example.com")
        self.assertEqual(parsed.path, "/auth")
        qs = urllib.parse.parse_qs(parsed.query)
        self.assertIn("client_id", qs)
        self.assertEqual(qs["client_id"][0], "test-client-id")
        self.assertEqual(qs["redirect_uri"][0], "https://example.com/callback")
        self.assertEqual(qs["response_type"][0], "code")
        self.assertIn("openid", qs["scope"][0])
        self.assertIn("state", qs)

    def test_sso_login_url_generation_oidc_includes_client_id(self):
        """OIDC URL client_id matches the tenant config."""
        oidc_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback",
        )
        self.assertIsNotNone(oidc_url)
        parsed = urllib.parse.urlparse(oidc_url)
        qs = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(qs["client_id"][0], "test-client-id")

    # ========== FAILURE SCENARIOS ==========

    def test_provider_retrieval_invalid_tenant_returns_none(self):
        """Test provider retrieval with invalid tenant returns None."""
        import uuid

        invalid_tenant_id = str(uuid.uuid4())
        provider = SSOService.get_provider(invalid_tenant_id, "SAML")
        self.assertIsNone(provider)

    # ========== EDGE CASES ==========

    def test_sso_login_url_generation_with_special_characters_in_redirect_uri(self):
        """Test SSO login URL generation with special characters in redirect_uri (edge case)."""
        oidc_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback?param=value&other=test",
        )
        # Should handle special characters properly
        self.assertIsNotNone(oidc_url)

    # ========== ERROR HANDLING ==========

    def test_provider_retrieval_handles_missing_config(self):
        """Test provider retrieval handles missing config gracefully."""
        tenant_no_config = Tenant.objects.create(
            name="No Config Tenant",
            slug="no-config-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        provider = SSOService.get_provider(str(tenant_no_config.id), "SAML")
        self.assertIsNone(provider)
