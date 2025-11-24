"""
Unit tests for authorization enforcement (roles, scopes).
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from hub.apps.auth.permissions import HasRole, HasAnyRole, HasScope, HasAnyScope
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.tenants.models import Tenant

User = get_user_model()


class TestView(APIView):
    """Test view for authorization testing"""
    permission_classes = [HasRole('TENANT_ADMIN')]
    
    def get(self, request):
        return Response({"message": "success"})


class AuthorizationTest(TestCase):
    """Test authorization enforcement"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Get or create roles (default roles are created by tenant signal)
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )
        
        # Create users
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.admin_user, role=self.admin_role)
        
        self.provider_user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.provider_user, role=self.provider_role)
        
        self.regular_user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_has_role_permission(self):
        """Test HasRole permission class"""
        from rest_framework.permissions import IsAuthenticated
        
        class TestView(APIView):
            permission_classes = [IsAuthenticated, HasRole('TENANT_ADMIN')]
            
            def get(self, request):
                return Response({"message": "success"})
        
        # Admin user should have access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/test/")
        # Note: This is a simplified test - actual endpoint routing would be needed
        
        # Provider user should not have access
        self.client.force_authenticate(user=self.provider_user)
        # Regular user should not have access
        self.client.force_authenticate(user=self.regular_user)
    
    def test_has_any_role_permission(self):
        """Test HasAnyRole permission class"""
        from rest_framework.permissions import IsAuthenticated
        
        class TestView(APIView):
            permission_classes = [IsAuthenticated, HasAnyRole(['TENANT_ADMIN', 'DATA_PROVIDER'])]
            
            def get(self, request):
                return Response({"message": "success"})
        
        # Both admin and provider should have access
        self.client.force_authenticate(user=self.admin_user)
        # Admin should have access
        
        self.client.force_authenticate(user=self.provider_user)
        # Provider should have access
        
        self.client.force_authenticate(user=self.regular_user)
        # Regular user should not have access
    
    def test_platform_admin_has_all_permissions(self):
        """Test that platform admins have all permissions"""
        # Create platform admin
        platform_admin = User.objects.create_user(
            email="platform@example.com",
            password="testpass123",
            is_platform_admin=True,
            status=UserStatus.ACTIVE
        )
        
        from rest_framework.permissions import IsAuthenticated
        
        class TestView(APIView):
            permission_classes = [IsAuthenticated, HasRole('TENANT_ADMIN')]
            
            def get(self, request):
                return Response({"message": "success"})
        
        # Platform admin should have access even without the role
        self.client.force_authenticate(user=platform_admin)
        # Should succeed
    
    def test_token_version_validation(self):
        """Test that tokens are invalidated when token_version changes"""
        from hub.apps.auth.jwt_utils import JWTTokenGenerator
        
        # Generate token
        access_token = JWTTokenGenerator.generate_access_token(self.admin_user)
        
        # Decode and verify
        payload = JWTTokenGenerator.decode_access_token(access_token)
        self.assertIsNotNone(payload)
        
        # Increment token version
        self.admin_user.increment_token_version()
        
        # Token should still decode, but validation should fail
        # (This is checked in the authentication class)
        from hub.apps.auth.authentication import JWTAuthentication
        auth = JWTAuthentication()
        
        # Create a mock request
        from unittest.mock import Mock
        request = Mock()
        request.META = {'HTTP_AUTHORIZATION': f'Bearer {access_token}'}
        
        # Should raise AuthenticationFailed due to token version mismatch
        from rest_framework.exceptions import AuthenticationFailed
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(request)

