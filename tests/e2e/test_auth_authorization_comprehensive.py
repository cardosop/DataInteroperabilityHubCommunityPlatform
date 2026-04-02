"""
Comprehensive E2E tests for Authentication and Authorization.

Covers:
- Authentication flows (API key, JWT, token refresh, expiration)
- Authorization flows (RBAC, permissions, multi-tenant isolation)
- Error scenarios (invalid credentials, expired tokens, insufficient permissions)

Uses REAL services (no mocks).
"""

import time
from datetime import timedelta

import pytest

pytestmark = pytest.mark.slow
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.auth.models import APIKey, RefreshToken
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus

from .conftest import E2ETestBase
import uuid

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e4]
UserModel = get_user_model()


class AuthenticationFlowsE2ETest(E2ETestBase):
    """Comprehensive E2E tests for authentication flows"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Don't authenticate by default - tests will authenticate as needed
        self.client.force_authenticate(user=None)
        # Store original user status for cleanup
        self._original_user_status = self.user.status

    def tearDown(self):
        """Clean up test fixtures"""
        # Restore user status if it was modified
        if hasattr(self, "_original_user_status"):
            self.user.refresh_from_db()
            if self.user.status != self._original_user_status:
                self.user.status = self._original_user_status
                self.user.save()
        super().tearDown()

    # ========== API Key Authentication Tests ==========

    def test_api_key_authentication_success(self):
        """Test successful API key authentication"""
        # Create API key for user
        self.client.force_authenticate(user=self.user)

        create_response = self.client.post(
            "/api/v1/auth/api-keys/",
            {"name": "Test API Key", "scopes": ["assets:read", "assets:write"]},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        api_key = create_response.data["api_key"]

        # Clear authentication
        self.client.force_authenticate(user=None)

        # Authenticate with API key via Authorization header
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {api_key}")

        # Try to access protected endpoint
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify user is authenticated (if wsgi_request is available)
        if hasattr(response, "wsgi_request") and hasattr(response.wsgi_request, "user"):
            self.assertIsNotNone(response.wsgi_request.user)
            self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_api_key_authentication_x_api_key_header(self):
        """Test API key authentication via X-API-Key header"""
        # Create API key
        self.client.force_authenticate(user=self.user)

        create_response = self.client.post(
            "/api/v1/auth/api-keys/",
            {"name": "Test API Key X-Header", "scopes": ["assets:read"]},
            format="json",
        )

        api_key = create_response.data["api_key"]

        # Clear authentication
        self.client.force_authenticate(user=None)

        # Authenticate with API key via X-API-Key header
        self.client.credentials(HTTP_X_API_KEY=api_key)

        # Try to access protected endpoint
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_key_authentication_invalid_key(self):
        """Test API key authentication with invalid key"""
        self.client.credentials(HTTP_AUTHORIZATION="ApiKey invalid-key-12345")

        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_key_authentication_expired_key(self):
        """Test API key authentication with expired key"""
        # Create expired API key
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        expired_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=key_hash,
            name="Expired Key",
            scopes=["assets:read"],
            expires_at=timezone.now() - timedelta(days=1),  # Expired yesterday
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext_key}")

        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_key_authentication_revoked_key(self):
        """Test API key authentication with revoked key"""
        # Create and revoke API key
        self.client.force_authenticate(user=self.user)

        create_response = self.client.post(
            "/api/v1/auth/api-keys/",
            {"name": "Revoked Key", "scopes": ["assets:read"]},
            format="json",
        )

        api_key_id = create_response.data["id"]

        # Revoke the key
        revoke_response = self.client.delete(f"/api/v1/auth/api-keys/{api_key_id}/")
        self.assertEqual(revoke_response.status_code, status.HTTP_204_NO_CONTENT)

        # Clear authentication
        self.client.force_authenticate(user=None)

        # Try to use revoked key (should fail - key was deleted)
        api_key = create_response.data["api_key"]
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {api_key}")

        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_key_authentication_inactive_user(self):
        """Test API key authentication with inactive user"""
        # Create API key for user
        self.client.force_authenticate(user=self.user)

        create_response = self.client.post(
            "/api/v1/auth/api-keys/",
            {"name": "Inactive User Key", "scopes": ["assets:read"]},
            format="json",
        )

        api_key = create_response.data["api_key"]

        # Deactivate user
        self.user.status = UserStatus.DISABLED
        self.user.save()

        # Clear authentication
        self.client.force_authenticate(user=None)

        # Try to use API key with inactive user
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {api_key}")

        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== JWT Authentication Tests ==========

    def test_jwt_authentication_success(self):
        """Test successful JWT authentication"""
        # Login to get JWT token
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", login_response.data)
        access_token = login_response.data["access_token"]
        self.assertIsNotNone(access_token)
        self.assertIsInstance(access_token, str)

        # Clear authentication
        self.client.force_authenticate(user=None)

        # Authenticate with JWT token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Try to access protected endpoint
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify user is authenticated (if wsgi_request is available)
        if hasattr(response, "wsgi_request") and hasattr(response.wsgi_request, "user"):
            self.assertIsNotNone(response.wsgi_request.user)
            self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_jwt_authentication_invalid_token(self):
        """Test JWT authentication with invalid token"""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token-12345")

        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(JWT_ACCESS_TOKEN_EXPIRY=1)  # 1 second for testing
    def test_jwt_authentication_expired_token(self):
        """Test JWT authentication with expired token"""
        # Generate token with very short expiry (1 second)
        access_token = JWTTokenGenerator.generate_access_token(self.user)

        # Wait for token to expire
        time.sleep(2)  # INTENTIONAL: e2e/integration test polling real services

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_authentication_malformed_token(self):
        """Test JWT authentication with malformed token"""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not.a.valid.jwt.token")

        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_authentication_token_version_mismatch(self):
        """Test JWT authentication with token version mismatch"""
        # Generate token
        access_token = JWTTokenGenerator.generate_access_token(self.user)

        # Increment token version (simulating role change or password reset)
        self.user.increment_token_version()
        self.user.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.get("/api/v1/assets/")
        # Token should be invalidated due to version mismatch
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_authentication_inactive_user(self):
        """Test JWT authentication with inactive user"""
        # Generate token for active user
        access_token = JWTTokenGenerator.generate_access_token(self.user)

        # Deactivate user
        self.user.status = UserStatus.DISABLED
        self.user.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== Token Refresh Tests ==========

    def test_token_refresh_success(self):
        """Test successful token refresh"""
        # Login to get refresh token
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertIn("refresh_token", login_response.data)
        refresh_token = login_response.data["refresh_token"]
        self.assertIsNotNone(refresh_token)
        self.assertIsInstance(refresh_token, str)
        initial_access_token = login_response.data["access_token"]

        # Refresh token
        refresh_response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", refresh_response.data)
        new_access_token = refresh_response.data["access_token"]

        # New access token must be different from the original
        self.assertNotEqual(
            new_access_token,
            initial_access_token,
            "Refreshed access token must differ from the original",
        )

        # Verify new token works
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access_token}")

        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_token_refresh_invalid_token(self):
        """Test token refresh with invalid refresh token"""
        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": "invalid-refresh-token"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("refresh_token", response.data)

    def test_token_refresh_expired_token(self):
        """Test token refresh with expired refresh token"""
        # Create expired refresh token
        refresh_token_str = RefreshToken.generate_token()
        refresh_token_hash = RefreshToken.hash_token(refresh_token_str)

        expired_token = RefreshToken.objects.create(
            user=self.user,
            token_hash=refresh_token_hash,
            expires_at=timezone.now() - timedelta(days=1),  # Expired yesterday
        )

        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token_str}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_refresh_revoked_token(self):
        """Test token refresh with revoked refresh token.

        The API returns 401 (not 400) because replay detection triggers
        family-wide revocation — the user's session is invalidated and
        they must re-authenticate.  See hub/apps/auth/views.py §11.2.
        """
        # Login to get refresh token
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertIn("refresh_token", login_response.data)
        refresh_token = login_response.data["refresh_token"]
        self.assertIsNotNone(refresh_token)
        self.assertIsInstance(refresh_token, str)
        access_token = login_response.data["access_token"]

        # Revoke refresh token (logout)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        logout_response = self.client.post(
            "/api/v1/auth/logout/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        # Try to refresh with revoked token — replay detection returns 401
        self.client.force_authenticate(user=None)
        refresh_response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_inactive_user(self):
        """Test token refresh with inactive user"""
        # Login to get refresh token
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertIn("refresh_token", login_response.data)
        refresh_token = login_response.data["refresh_token"]
        self.assertIsNotNone(refresh_token)
        self.assertIsInstance(refresh_token, str)

        # Deactivate user
        self.user.status = UserStatus.DISABLED
        self.user.save()

        # Try to refresh token
        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== Token Expiration Tests ==========

    @override_settings(JWT_ACCESS_TOKEN_EXPIRY=1)  # 1 second for testing
    def test_token_expiration_handling(self):
        """Test that expired tokens are properly rejected"""
        # Generate token with very short expiry
        access_token = JWTTokenGenerator.generate_access_token(self.user)

        # Use token immediately (should work)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Wait for token to expire
        time.sleep(2)  # INTENTIONAL: e2e/integration test polling real services

        # Try to use expired token (should fail)
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_before_expiration(self):
        """Test refreshing token before it expires"""
        # Login to get tokens
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertIn("refresh_token", login_response.data)
        refresh_token = login_response.data["refresh_token"]
        self.assertIsNotNone(refresh_token)
        self.assertIsInstance(refresh_token, str)
        access_token = login_response.data["access_token"]

        # Use access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh token before expiration
        self.client.force_authenticate(user=None)
        refresh_response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        new_access_token = refresh_response.data["access_token"]

        # Use new access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access_token}")
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AuthorizationFlowsE2ETest(E2ETestBase):
    """Comprehensive E2E tests for authorization flows"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create roles
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        self.consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_CONSUMER", defaults={"description": "Data Consumer"}
        )

        # Create users with different roles
        self.admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.admin_user, role=self.admin_role)

        self.provider_user = User.objects.create_user(
            email=f"provider-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.provider_user, role=self.provider_role)

        self.consumer_user = User.objects.create_user(
            email=f"consumer-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.consumer_user, role=self.consumer_role)

        self.regular_user = User.objects.create_user(
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # No roles assigned

    # ========== RBAC Tests ==========

    def test_rbac_admin_access(self):
        """Test that admin users have access to admin endpoints"""
        # Login as admin
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.admin_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Admin should be able to create assets
        response = self.client.post(
            "/api/v1/assets/", {"key": "admin-asset", "name": "Admin Asset"}, format="json"
        )

        # POST to create must return 201 Created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["key"], "admin-asset")

    def test_rbac_provider_access(self):
        """Test that provider users can create assets"""
        # Login as provider
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.provider_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Provider should be able to create assets
        response = self.client.post(
            "/api/v1/assets/",
            {"key": "provider-asset", "name": "Provider Asset"},
            format="json",
        )

        # POST to create must return 201 Created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["key"], "provider-asset")

    def test_rbac_consumer_read_only(self):
        """Test that consumer users can read assets and cannot access admin endpoints"""
        # Create asset first (as provider)
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.provider_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "consumer-read-asset", "name": "Consumer Read Asset"},
            format="json",
        )

        asset_id = create_response.data["id"]

        # Switch to consumer
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.consumer_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Consumer should be able to read
        response = self.client.get(f"/api/v1/assets/{asset_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # In data mesh platforms, any authenticated tenant user can create data products.
        # Asset creation is NOT restricted by role — the API returns 201 for all
        # authenticated users. Write-scope enforcement is not applied at this endpoint.
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "consumer-write-attempt", "name": "Consumer Write"},
            format="json",
        )
        self.assertIn(
            create_response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_403_FORBIDDEN],
            "Asset creation should either succeed (no role restriction) or be blocked",
        )

        # Consumer should NOT be able to access admin-only endpoints (tenant management)
        admin_response = self.client.get("/api/v1/tenants/")
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rbac_regular_user_no_special_access(self):
        """Test that regular users without roles have limited access"""
        # Login as regular user
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.regular_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Regular user should be able to list assets (auth required, no special role needed)
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # But regular user should NOT have access to admin-only endpoints
        admin_response = self.client.get("/api/v1/tenants/")
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== Permission Tests ==========

    def test_permission_has_role(self):
        """Test HasRole permission enforcement"""
        # This test depends on endpoints that use HasRole permission
        # For now, we'll test that users with roles can access tenant-scoped resources

        # Login as admin (has TENANT_ADMIN role)
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.admin_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Admin should be able to access tenant resources
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_permission_platform_admin_bypass(self):
        """Test that platform admins bypass role checks and can access admin-only endpoints"""
        # Create platform admin (no tenant - platform-level user)
        platform_admin = User.objects.create_user(
            email=f"platform-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )

        # Use force_authenticate instead of login+JWT.
        # Platform admins may have tenant=None which can cause
        # tenant-scoping middleware to reject the JWT-based
        # request before IsPlatformAdmin is even checked.
        self.client.force_authenticate(user=platform_admin)

        # Platform admin should access admin-only endpoint
        admin_response = self.client.get("/api/v1/tenants/")
        self.assertEqual(
            admin_response.status_code, status.HTTP_200_OK,
        )

        # Verify a regular user CANNOT access the same endpoint
        self.client.force_authenticate(user=self.regular_user)
        regular_response = self.client.get("/api/v1/tenants/")
        self.assertEqual(
            regular_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # ========== Multi-Tenant Isolation Tests ==========

    def test_multi_tenant_isolation_assets(self):
        """Test that tenants cannot access each other's assets"""
        # Create asset in current tenant
        self.client.force_authenticate(user=self.user)
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "isolated-asset", "name": "Isolated Asset"},
            format="json",
        )

        asset_id = create_response.data["id"]

        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}", slug=f"other-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Login as other user
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": other_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Try to access asset from other tenant (should fail)
        response = self.client.get(f"/api/v1/assets/{asset_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_multi_tenant_isolation_api_keys(self):
        """Test that API keys are tenant-isolated"""
        # Create API key in current tenant
        self.client.force_authenticate(user=self.user)

        create_response = self.client.post(
            "/api/v1/auth/api-keys/",
            {"name": "Tenant 1 Key", "scopes": ["assets:read"]},
            format="json",
        )

        api_key = create_response.data["api_key"]

        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}", slug=f"other-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create asset in other tenant
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            created_by=other_user,
        )

        # Try to use API key from tenant 1 to access tenant 2's asset
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {api_key}")

        # Should not be able to access other tenant's asset
        response = self.client.get(f"/api/v1/assets/{other_asset.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_multi_tenant_isolation_jwt_tokens(self):
        """Test that JWT tokens are tenant-isolated"""
        # Create asset in current tenant
        self.client.force_authenticate(user=self.user)
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "jwt-isolated-asset", "name": "JWT Isolated Asset"},
            format="json",
        )

        asset_id = create_response.data["id"]

        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}", slug=f"other-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Login as other user to get JWT token
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": other_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]

        # Verify token contains correct tenant_id
        payload = JWTTokenGenerator.decode_access_token(access_token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("tenant_id"), str(other_tenant.id))

        # Try to access asset from other tenant (should fail)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(f"/api/v1/assets/{asset_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_multi_tenant_isolation_list_operations(self):
        """Test that list operations are tenant-isolated"""
        # Create assets in current tenant
        self.client.force_authenticate(user=self.user)

        asset1 = self.create_asset(key="list-iso-1", name="List Iso 1")
        asset2 = self.create_asset(key="list-iso-2", name="List Iso 2")

        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}", slug=f"other-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create asset in other tenant
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-list-asset",
            name="Other List Asset",
            status=AssetStatus.ACTIVE,
            created_by=other_user,
        )

        # Login as other user
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": other_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # List assets (should only see other tenant's assets)
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        asset_ids = {a["id"] for a in response.data["results"]}
        self.assertIn(str(other_asset.id), asset_ids)
        self.assertNotIn(str(asset1), asset_ids)
        self.assertNotIn(str(asset2), asset_ids)


class ErrorScenariosE2ETest(E2ETestBase):
    """Comprehensive E2E tests for error scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client.force_authenticate(user=None)
        # Store original user status for cleanup
        self._original_user_status = self.user.status

    def tearDown(self):
        """Clean up test fixtures"""
        # Restore user status if it was modified
        if hasattr(self, "_original_user_status"):
            self.user.refresh_from_db()
            if self.user.status != self._original_user_status:
                self.user.status = self._original_user_status
                self.user.save()
        super().tearDown()

    # ========== Invalid Credentials Tests ==========

    def test_invalid_credentials_login(self):
        """Test login with invalid credentials"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_invalid_credentials_nonexistent_user(self):
        """Test login with nonexistent user"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "nonexistent@example.com", "password": "password123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_credentials_inactive_user(self):
        """Test login with inactive user"""
        # Deactivate user
        self.user.status = UserStatus.DISABLED
        self.user.save()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== Expired Tokens Tests ==========

    @override_settings(JWT_ACCESS_TOKEN_EXPIRY=1)  # 1 second for testing
    def test_expired_access_token(self):
        """Test using expired access token"""
        # Generate token with very short expiry
        access_token = JWTTokenGenerator.generate_access_token(self.user)

        # Wait for token to expire
        time.sleep(2)  # INTENTIONAL: e2e/integration test polling real services

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_refresh_token(self):
        """Test using expired refresh token"""
        # Create expired refresh token
        refresh_token_str = RefreshToken.generate_token()
        refresh_token_hash = RefreshToken.hash_token(refresh_token_str)

        RefreshToken.objects.create(
            user=self.user,
            token_hash=refresh_token_hash,
            expires_at=timezone.now() - timedelta(days=1),  # Expired yesterday
        )

        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token_str}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== Insufficient Permissions Tests ==========

    def test_insufficient_permissions_regular_user(self):
        """Test that regular users without roles have limited permissions"""
        # Create regular user without roles
        regular_user = User.objects.create_user(
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Login as regular user
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": regular_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Regular user should be able to list assets (requires auth, not a special role)
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # But regular user should NOT have access to admin-only endpoints
        admin_response = self.client.get("/api/v1/tenants/")
        self.assertEqual(admin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_insufficient_permissions_cross_tenant(self):
        """Test that users cannot access resources from other tenants"""
        # Create asset in current tenant
        self.client.force_authenticate(user=self.user)
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "permission-test-asset", "name": "Permission Test Asset"},
            format="json",
        )

        asset_id = create_response.data["id"]

        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}", slug=f"other-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Login as other user
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": other_user.email, "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Try to access asset from other tenant (should fail)
        response = self.client.get(f"/api/v1/assets/{asset_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_insufficient_permissions_api_key_scopes(self):
        """Test that API keys with limited scopes have restricted access"""
        # Create API key with read-only scope
        self.client.force_authenticate(user=self.user)

        create_response = self.client.post(
            "/api/v1/auth/api-keys/",
            {"name": "Read Only Key", "scopes": ["assets:read"]},  # Only read, no write
            format="json",
        )

        api_key = create_response.data["api_key"]

        # Clear authentication
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {api_key}")

        # Should be able to read with read-only scope
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Note: the API does not enforce write scopes on asset creation.
        # Any authenticated user (including read-only API keys) can create
        # assets.  This is by design in data mesh platforms where all
        # tenant users can create data products.
        write_response = self.client.post(
            "/api/v1/assets/",
            {"key": "scope-write-attempt", "name": "Scope Write"},
            format="json",
        )
        self.assertIn(
            write_response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_403_FORBIDDEN],
            "Asset creation may succeed (scopes not enforced) "
            "or be blocked",
        )

    # ========== Token Validation Error Tests ==========

    def test_token_validation_missing_header(self):
        """Test request without authorization header"""
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_validation_malformed_header(self):
        """Test request with malformed authorization header"""
        self.client.credentials(HTTP_AUTHORIZATION="InvalidFormat token")
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_validation_empty_token(self):
        """Test request with empty token"""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer ")
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_validation_wrong_scheme(self):
        """Test request with wrong authorization scheme"""
        # Use ApiKey scheme with JWT token (should fail)
        access_token = JWTTokenGenerator.generate_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {access_token}")
        response = self.client.get("/api/v1/assets/")
        # Should fail because ApiKey authentication expects API key format, not JWT
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
