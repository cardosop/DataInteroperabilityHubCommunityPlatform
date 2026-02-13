"""
Unit tests for SSO Integration

Tests for SAML and OIDC authentication.
"""

import pytest
from django.test import TestCase

from hub.apps.auth.sso import OIDCProvider, SAMLProvider, SSOService
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class SSOServiceTest(TestCase):
    """Test SSOService"""

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

    def test_get_saml_provider_returns_provider(self):
        """Test getting SAML provider returns provider."""
        provider = SSOService.get_provider(str(self.tenant.id), "SAML")
        self.assertIsNotNone(provider)

    def test_get_saml_provider_returns_saml_provider_instance(self):
        """Test getting SAML provider returns SAMLProvider instance."""
        provider = SSOService.get_provider(str(self.tenant.id), "SAML")
        self.assertIsInstance(provider, SAMLProvider)

    def test_get_oidc_provider_returns_provider(self):
        """Test getting OIDC provider returns provider."""
        provider = SSOService.get_provider(str(self.tenant.id), "OIDC")
        self.assertIsNotNone(provider)

    def test_get_oidc_provider_returns_oidc_provider_instance(self):
        """Test getting OIDC provider returns OIDCProvider instance."""
        provider = SSOService.get_provider(str(self.tenant.id), "OIDC")
        self.assertIsInstance(provider, OIDCProvider)

    def test_get_sso_login_url_saml_returns_url(self):
        """Test getting SAML login URL returns URL."""
        login_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="SAML",
            redirect_uri="https://example.com/callback",
        )

        self.assertIsNotNone(login_url)

    def test_get_sso_login_url_oidc_returns_url(self):
        """Test getting OIDC login URL returns URL."""
        login_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback",
        )

        self.assertIsNotNone(login_url)

    def test_get_sso_login_url_oidc_includes_client_id(self):
        """Test getting OIDC login URL includes client_id."""
        login_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback",
        )

        self.assertIn("client_id", login_url)

    def test_get_sso_login_url_oidc_includes_redirect_uri(self):
        """Test getting OIDC login URL includes redirect_uri."""
        login_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback",
        )

        self.assertIn("redirect_uri", login_url)

    # ========== FAILURE SCENARIOS ==========

    def test_get_provider_invalid_tenant_id_returns_none(self):
        """Test getting provider with invalid tenant_id returns None."""
        import uuid

        invalid_tenant_id = str(uuid.uuid4())
        provider = SSOService.get_provider(invalid_tenant_id, "SAML")
        self.assertIsNone(provider)

    def test_get_provider_invalid_provider_type_returns_none(self):
        """Test getting provider with invalid provider_type returns None."""
        provider = SSOService.get_provider(str(self.tenant.id), "INVALID")
        self.assertIsNone(provider)

    # ========== EDGE CASES ==========

    def test_get_sso_login_url_empty_redirect_uri(self):
        """Test getting SSO login URL with empty redirect_uri (edge case)."""
        login_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id), provider_type="SAML", redirect_uri=""
        )

        # Should handle gracefully (may return None or empty string)
        self.assertIsNotNone(login_url)

    def test_get_sso_login_url_none_redirect_uri(self):
        """Test getting SSO login URL with None redirect_uri (edge case)."""
        login_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id), provider_type="SAML", redirect_uri=None
        )

        # Should handle gracefully
        self.assertIsNotNone(login_url)

    # ========== ERROR HANDLING ==========

    def test_get_provider_handles_missing_config_gracefully(self):
        """Test getting provider handles missing tenant config gracefully."""
        # Create tenant without config
        tenant_no_config = Tenant.objects.create(
            name="No Config Tenant",
            slug="no-config-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        provider = SSOService.get_provider(str(tenant_no_config.id), "SAML")
        # Should return None or handle gracefully
        self.assertIsNone(provider)
