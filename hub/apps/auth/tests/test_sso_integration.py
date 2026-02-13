"""
Integration tests for SSO

Tests for SSO authentication flows.
"""

import pytest
from django.test import TestCase

from hub.apps.auth.sso import SSOService
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class SSOIntegrationTest(TestCase):
    """Integration tests for SSO"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
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
        """Test SSO login URL generation for SAML returns URL."""
        saml_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="SAML",
            redirect_uri="https://example.com/callback",
        )
        self.assertIsNotNone(saml_url)

    def test_sso_login_url_generation_oidc_returns_url(self):
        """Test SSO login URL generation for OIDC returns URL."""
        oidc_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback",
        )
        self.assertIsNotNone(oidc_url)

    def test_sso_login_url_generation_oidc_includes_client_id(self):
        """Test SSO login URL generation for OIDC includes client_id."""
        oidc_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback",
        )
        self.assertIn("client_id", oidc_url)

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
