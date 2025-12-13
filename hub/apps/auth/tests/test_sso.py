"""
Unit tests for SSO Integration

Tests for SAML and OIDC authentication.
"""
import pytest
from django.test import TestCase

from hub.apps.auth.sso import SSOService, SAMLProvider, OIDCProvider
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class SSOServiceTest(TestCase):
    """Test SSOService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create tenant config with SSO
        self.config = TenantConfig.objects.create(
            tenant=self.tenant,
            sso_config={
                "saml": {
                    "sso_url": "https://saml.example.com/sso",
                    "role_mapping": {}
                },
                "oidc": {
                    "authorization_endpoint": "https://oidc.example.com/auth",
                    "client_id": "test-client-id",
                    "role_mapping": {}
                }
            }
        )
    
    def test_get_saml_provider(self):
        """Test getting SAML provider"""
        provider = SSOService.get_provider(str(self.tenant.id), "SAML")
        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, SAMLProvider)
    
    def test_get_oidc_provider(self):
        """Test getting OIDC provider"""
        provider = SSOService.get_provider(str(self.tenant.id), "OIDC")
        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, OIDCProvider)
    
    def test_get_sso_login_url_saml(self):
        """Test getting SAML login URL"""
        login_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="SAML",
            redirect_uri="https://example.com/callback"
        )
        
        # Should return URL (even if simplified)
        self.assertIsNotNone(login_url)
    
    def test_get_sso_login_url_oidc(self):
        """Test getting OIDC login URL"""
        login_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback"
        )
        
        # Should return URL with proper parameters
        self.assertIsNotNone(login_url)
        self.assertIn("client_id", login_url)
        self.assertIn("redirect_uri", login_url)

