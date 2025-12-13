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
    
    def test_saml_provider_retrieval(self):
        """Test SAML provider retrieval"""
        provider = SSOService.get_provider(str(self.tenant.id), "SAML")
        self.assertIsNotNone(provider)
        self.assertEqual(provider.tenant_id, str(self.tenant.id))
    
    def test_oidc_provider_retrieval(self):
        """Test OIDC provider retrieval"""
        provider = SSOService.get_provider(str(self.tenant.id), "OIDC")
        self.assertIsNotNone(provider)
        self.assertEqual(provider.tenant_id, str(self.tenant.id))
    
    def test_sso_login_url_generation(self):
        """Test SSO login URL generation"""
        # SAML
        saml_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="SAML",
            redirect_uri="https://example.com/callback"
        )
        self.assertIsNotNone(saml_url)
        
        # OIDC
        oidc_url = SSOService.get_sso_login_url(
            tenant_id=str(self.tenant.id),
            provider_type="OIDC",
            redirect_uri="https://example.com/callback"
        )
        self.assertIsNotNone(oidc_url)
        self.assertIn("client_id", oidc_url)

