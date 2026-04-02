"""Phase 99: Authentication class edge case tests.

Targets uncovered lines in hub/apps/auth/authentication.py:
  47-59  - User not found from JWT token (logging + debug check)
  63     - User is not active
  67     - Token version invalidated
  71     - tenant_id not yet set in request
  120    - API key revoked
  134    - API key user not found
  136    - API key user not active
  143    - Tenant-scoped key without user
  162    - User tenant_id mismatch triggers refresh
  168    - authenticate_header returns 'ApiKey'
"""
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.exceptions import AuthenticationFailed

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, UserTenantMembership
from hub.apps.auth.models import APIKey
from hub.apps.auth.authentication import (
    JWTAuthentication,
    APIKeyAuthentication,
)
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class JWTAuthenticationEdgeCases(TestCase):
    """Cover uncovered JWT authentication paths."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"JWTAuth Test {uid}",
            slug=f"jwtauth-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"jwtauth-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
        )
        self.client = APIClient()
        self.factory = APIRequestFactory()

    def _generate_token(self, user=None):
        """Generate a valid access token for the given user."""
        user = user or self.user
        return JWTTokenGenerator.generate_access_token(user)

    def test_bearer_prefix_case_insensitive(self):
        """Bearer token with lowercase 'bearer' should not match (case-sensitive)."""
        self.client.credentials(HTTP_AUTHORIZATION="bearer some.token.here")
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertIn(response.status_code, [401, 403])

    def test_no_authorization_header(self):
        """Request without any Authorization header returns None (no auth)."""
        auth = JWTAuthentication()
        request = self.factory.get("/api/v1/assets/")
        result = auth.authenticate(request)
        self.assertIsNone(result)

    def test_token_for_nonexistent_user(self):
        """Lines 47-59: decode succeeds but user not found."""
        fake_user_id = str(uuid.uuid4())
        fake_payload = {
            "sub": fake_user_id,
            "tenant_id": str(self.tenant.id),
            "authz_version": 0,
        }
        auth = JWTAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer valid.token"

        with patch.object(
            JWTTokenGenerator,
            "decode_access_token",
            return_value=fake_payload,
        ), patch.object(
            JWTTokenGenerator,
            "get_user_from_token",
            return_value=None,
        ):
            with self.assertRaises(AuthenticationFailed) as ctx:
                auth.authenticate(request)
        self.assertIn(
            "User not found", str(ctx.exception)
        )

    def test_token_for_inactive_user(self):
        """Line 63: Token for inactive user is rejected."""
        token = self._generate_token()
        self.user.status = UserStatus.SUSPENDED
        self.user.save(update_fields=["status"])

        auth = JWTAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        with self.assertRaises(AuthenticationFailed) as ctx:
            auth.authenticate(request)
        self.assertIn("not active", str(ctx.exception))

    def test_token_version_invalidated(self):
        """Line 67: decode succeeds, user found, active, but
        validate_token_version returns False (version bumped
        between decode and second check)."""
        payload = {
            "sub": str(self.user.id),
            "tenant_id": str(self.tenant.id),
            "authz_version": -1,  # stale version
        }
        auth = JWTAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer valid.tok"

        with patch.object(
            JWTTokenGenerator,
            "decode_access_token",
            return_value=payload,
        ), patch.object(
            JWTTokenGenerator,
            "get_user_from_token",
            return_value=self.user,
        ):
            with self.assertRaises(AuthenticationFailed) as ctx:
                auth.authenticate(request)
        self.assertIn(
            "invalidated", str(ctx.exception)
        )

    def test_jwt_sets_tenant_id_when_not_set(self):
        """Line 71: JWT authentication sets request.tenant_id when not already set."""
        auth = JWTAuthentication()
        token = self._generate_token()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        result = auth.authenticate(request)
        self.assertIsNotNone(result)
        user, _ = result
        self.assertEqual(user.id, self.user.id)
        self.assertTrue(hasattr(request, "tenant_id"))

    def test_jwt_does_not_overwrite_existing_tenant_id(self):
        """Line 70: JWT auth does not overwrite tenant_id if already set."""
        auth = JWTAuthentication()
        token = self._generate_token()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        request.tenant_id = str(self.tenant.id)

        result = auth.authenticate(request)
        self.assertIsNotNone(result)
        self.assertEqual(request.tenant_id, str(self.tenant.id))

    def test_authenticate_header_returns_bearer(self):
        """JWT authenticate_header returns 'Bearer'."""
        auth = JWTAuthentication()
        request = self.factory.get("/")
        self.assertEqual(auth.authenticate_header(request), "Bearer")

    def test_invalid_token_payload(self):
        """Line 39: decode returns None for invalid token."""
        auth = JWTAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer totally.invalid.token"

        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(request)


class APIKeyAuthenticationEdgeCases(TestCase):
    """Cover uncovered API key authentication paths."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"APIKey Test {uid}",
            slug=f"apikey-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"apikey-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
        )
        self.client = APIClient()
        self.factory = APIRequestFactory()

    def _create_api_key(self, **kwargs):
        """Create an API key and return (key_str, api_key_obj)."""
        key_str = APIKey.generate_key()
        key_hash = APIKey.hash_key(key_str)
        defaults = {
            "tenant": self.tenant,
            "user": self.user,
            "key_hash": key_hash,
            "name": f"test-key-{uuid.uuid4().hex[:6]}",
        }
        defaults.update(kwargs)
        api_key = APIKey.objects.create(**defaults)
        return key_str, api_key

    def test_x_api_key_header_with_valid_key(self):
        """X-API-Key header with valid key authenticates via DRF auth class."""
        key_str, _ = self._create_api_key()
        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_API_KEY"] = key_str

        result = auth.authenticate(request)
        self.assertIsNotNone(result)
        user, key = result
        self.assertEqual(user.id, self.user.id)
        self.assertEqual(request.tenant_id, str(self.tenant.id))

    def test_x_api_key_header_with_invalid_key(self):
        """X-API-Key header with invalid key rejected."""
        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_API_KEY"] = "invalid-key-here"

        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(request)

    def test_api_key_updates_last_used(self):
        """Line 123: Successful API key auth updates last_used_at."""
        key_str, api_key = self._create_api_key()
        self.assertIsNone(api_key.last_used_at)

        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_API_KEY"] = key_str
        auth.authenticate(request)

        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.last_used_at)

    def test_revoked_api_key_rejected(self):
        """Line 120: Revoked API key should be rejected."""
        key_str, api_key = self._create_api_key()
        api_key.revoke()

        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_API_KEY"] = key_str

        with self.assertRaises(AuthenticationFailed) as ctx:
            auth.authenticate(request)
        self.assertIn("revoked", str(ctx.exception))

    def test_expired_api_key_rejected(self):
        """Line 118: Expired API key should be rejected."""
        from django.utils import timezone
        from datetime import timedelta

        key_str, _ = self._create_api_key(
            expires_at=timezone.now() - timedelta(hours=1),
        )

        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_API_KEY"] = key_str

        with self.assertRaises(AuthenticationFailed) as ctx:
            auth.authenticate(request)
        self.assertIn("expired", str(ctx.exception))

    def test_api_key_user_not_found(self):
        """Line 134: API key references user that cannot be loaded."""
        key_str, _ = self._create_api_key()

        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_API_KEY"] = key_str

        with patch(
            "hub.apps.auth.authentication.User.objects.filter"
        ) as mock_filter:
            mock_qs = MagicMock()
            mock_qs.prefetch_related.return_value.first.return_value = None
            mock_filter.return_value = mock_qs
            with self.assertRaises(AuthenticationFailed) as ctx:
                auth.authenticate(request)
            self.assertIn("User not found", str(ctx.exception))

    def test_api_key_user_inactive(self):
        """Line 136: API key user is inactive."""
        key_str, _ = self._create_api_key()
        self.user.status = UserStatus.SUSPENDED
        self.user.save(update_fields=["status"])

        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_API_KEY"] = key_str

        with self.assertRaises(AuthenticationFailed) as ctx:
            auth.authenticate(request)
        self.assertIn("not active", str(ctx.exception))

    def test_api_key_without_user_rejected(self):
        """Line 143: Tenant-scoped API key without user is rejected."""
        key_str, _ = self._create_api_key(user=None)

        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_API_KEY"] = key_str

        with self.assertRaises(AuthenticationFailed) as ctx:
            auth.authenticate(request)
        self.assertIn("User-scoped", str(ctx.exception))

    def test_api_key_tenant_mismatch_triggers_refresh(self):
        """Line 162: user.tenant_id != api_key.tenant_id triggers refresh_from_db."""
        other_tenant = Tenant.objects.create(
            name=f"Other {uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
        )
        key_str, _ = self._create_api_key(tenant=other_tenant)

        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_API_KEY"] = key_str

        result = auth.authenticate(request)
        self.assertIsNotNone(result)
        self.assertEqual(request.tenant_id, str(other_tenant.id))

    def test_authenticate_header_returns_apikey(self):
        """Line 168: authenticate_header returns 'ApiKey'."""
        auth = APIKeyAuthentication()
        request = self.factory.get("/")
        self.assertEqual(auth.authenticate_header(request), "ApiKey")

    def test_authorization_header_apikey_format(self):
        """Line 99: ApiKey in Authorization header (not X-API-Key)."""
        key_str, _ = self._create_api_key()
        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = f"ApiKey {key_str}"

        result = auth.authenticate(request)
        self.assertIsNotNone(result)
        user, key = result
        self.assertEqual(user.id, self.user.id)

    def test_no_api_key_returns_none(self):
        """Lines 104-105: No API key in any header returns None."""
        auth = APIKeyAuthentication()
        request = self.factory.get("/api/v1/assets/")
        result = auth.authenticate(request)
        self.assertIsNone(result)
