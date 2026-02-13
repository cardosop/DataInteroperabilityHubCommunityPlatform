"""
Unit tests for authorization enforcement (roles, scopes).
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from hub.apps.auth.permissions import HasAnyRole, HasAnyScope, HasRole, HasScope
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class RequestUserAuth:
    """
    Auth class for tests: use the user set on the raw request (APIRequestFactory).
    DRF's Request wrapper runs authenticators; without this, request.user is overwritten.
    """

    def authenticate(self, request):
        user = getattr(request._request, "user", None)
        if user is not None and getattr(user, "is_authenticated", True):
            return (user, None)
        return None


class TestView(APIView):
    """Test view for authorization testing (uses get_permissions for param-based permissions)."""

    authentication_classes = [RequestUserAuth]

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        return [IsAuthenticated(), HasRole("TENANT_ADMIN")]

    def get(self, request):
        return Response({"message": "success"})


class AuthorizationTest(TestCase):
    """Test authorization enforcement"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Get or create roles (default roles are created by tenant signal)
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )

        # Create users
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.admin_user, role=self.admin_role)

        self.provider_user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.provider_user, role=self.provider_role)

        self.regular_user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_has_role_permission_admin_allowed(self):
        """Test HasRole permission class - admin user has access"""
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.test import APIRequestFactory
        from rest_framework.views import APIView

        class TestView(APIView):
            authentication_classes = [RequestUserAuth]

            def get_permissions(self):
                return [IsAuthenticated(), HasRole("TENANT_ADMIN")]

            def get(self, request):
                return Response({"message": "success"})

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.admin_user

        view = TestView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "success")

    def test_has_role_permission_provider_denied(self):
        """Test HasRole permission class - provider user denied access"""
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.test import APIRequestFactory
        from rest_framework.views import APIView

        class TestView(APIView):
            authentication_classes = [RequestUserAuth]

            def get_permissions(self):
                return [IsAuthenticated(), HasRole("TENANT_ADMIN")]

            def get(self, request):
                return Response({"message": "success"})

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.provider_user

        view = TestView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_has_role_permission_regular_user_denied(self):
        """Test HasRole permission class - regular user denied access"""
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.test import APIRequestFactory
        from rest_framework.views import APIView

        class TestView(APIView):
            authentication_classes = [RequestUserAuth]

            def get_permissions(self):
                return [IsAuthenticated(), HasRole("TENANT_ADMIN")]

            def get(self, request):
                return Response({"message": "success"})

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.regular_user

        view = TestView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_has_any_role_permission_admin_allowed(self):
        """Test HasAnyRole permission class - admin user has access"""
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.test import APIRequestFactory
        from rest_framework.views import APIView

        class TestView(APIView):
            authentication_classes = [RequestUserAuth]

            def get_permissions(self):
                return [
                    IsAuthenticated(),
                    HasAnyRole(["TENANT_ADMIN", "DATA_PROVIDER"]),
                ]

            def get(self, request):
                return Response({"message": "success"})

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.admin_user

        view = TestView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "success")

    def test_has_any_role_permission_provider_allowed(self):
        """Test HasAnyRole permission class - provider user has access"""
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.test import APIRequestFactory
        from rest_framework.views import APIView

        class TestView(APIView):
            authentication_classes = [RequestUserAuth]

            def get_permissions(self):
                return [
                    IsAuthenticated(),
                    HasAnyRole(["TENANT_ADMIN", "DATA_PROVIDER"]),
                ]

            def get(self, request):
                return Response({"message": "success"})

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.provider_user

        view = TestView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "success")

    def test_has_any_role_permission_regular_user_denied(self):
        """Test HasAnyRole permission class - regular user denied access"""
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.test import APIRequestFactory
        from rest_framework.views import APIView

        class TestView(APIView):
            authentication_classes = [RequestUserAuth]

            def get_permissions(self):
                return [
                    IsAuthenticated(),
                    HasAnyRole(["TENANT_ADMIN", "DATA_PROVIDER"]),
                ]

            def get(self, request):
                return Response({"message": "success"})

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.regular_user

        view = TestView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_has_all_permissions(self):
        """Test that platform admins have all permissions"""
        platform_admin = User.objects.create_user(
            email="platform@example.com",
            password="testpass123",
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )

        from rest_framework.permissions import IsAuthenticated
        from rest_framework.test import APIRequestFactory
        from rest_framework.views import APIView

        class TestView(APIView):
            authentication_classes = [RequestUserAuth]

            def get_permissions(self):
                return [IsAuthenticated(), HasRole("TENANT_ADMIN")]

            def get(self, request):
                return Response({"message": "success"})

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = platform_admin

        view = TestView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "success")

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
        from django.test import RequestFactory

        from hub.apps.auth.authentication import JWTAuthentication

        auth = JWTAuthentication()

        # Use real RequestFactory instead of Mock to test with real request object
        factory = RequestFactory()
        request = factory.get("/api/v1/test/", HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Should raise AuthenticationFailed due to token version mismatch
        from rest_framework.exceptions import AuthenticationFailed

        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(request)
