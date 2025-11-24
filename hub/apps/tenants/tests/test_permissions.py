"""
Unit tests for tenant permissions.
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant, KYCStatus, TenantStatus
from hub.apps.tenants.permissions import IsPlatformAdmin, CanPublishToMarketplace

try:
    User = get_user_model()
    HAS_USER_MODEL = True
except:
    # Mock user for testing
    class MockUser:
        def __init__(self, email, is_platform_admin=False):
            self.email = email
            self.is_platform_admin = is_platform_admin
            self.is_authenticated = True
    
    User = MockUser
    HAS_USER_MODEL = False


class TenantPermissionsTest(TestCase):
    """Test tenant permission classes"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
    
    def test_is_platform_admin_permission(self):
        """Test IsPlatformAdmin permission"""
        permission = IsPlatformAdmin()
        
        # Platform admin user
        if HAS_USER_MODEL:
            admin_user = User.objects.create_user(
                email="admin@example.com",
                password="test",
                is_platform_admin=True
            )
            regular_user = User.objects.create_user(
                email="user@example.com",
                password="test",
                is_platform_admin=False
            )
        else:
            admin_user = User(email="admin@example.com", is_platform_admin=True)
            regular_user = User(email="user@example.com", is_platform_admin=False)
        
        request = self.factory.get("/api/v1/tenants/")
        request.user = admin_user
        
        self.assertTrue(permission.has_permission(request, None))
        
        request.user = regular_user
        
        self.assertFalse(permission.has_permission(request, None))
    
    def test_can_publish_to_marketplace_permission(self):
        """Test CanPublishToMarketplace permission"""
        permission = CanPublishToMarketplace()
        
        # Unverified tenant
        request = self.factory.get("/api/v1/marketplace/listings/")
        request.tenant = self.tenant
        
        self.assertFalse(permission.has_permission(request, None))
        
        # Verified tenant
        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save()
        request.tenant = self.tenant
        
        self.assertTrue(permission.has_permission(request, None))
        
        # Suspended verified tenant
        self.tenant.status = TenantStatus.SUSPENDED
        self.tenant.save()
        request.tenant = self.tenant
        
        self.assertFalse(permission.has_permission(request, None))
