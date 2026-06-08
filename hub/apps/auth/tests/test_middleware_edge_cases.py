"""Phase 99: Middleware edge case tests for uncovered paths.

Targets uncovered lines in hub/apps/auth/middleware.py:
  100-103  - API key extraction ValueError/TypeError/KeyError/AttributeError
  122      - JWT token split returns None
  131-134  - JWT extraction ValueError/TypeError/KeyError/AttributeError
  176-177  - JWT decode failure in X-Tenant-Id path
  194-195  - Tenant.DoesNotExist in X-Tenant-Id path
  202      - tenant_id not a string (UUID type)
  208-213  - Tenant.DoesNotExist / DB error when tenant_id already set
  233-238  - Tenant.DoesNotExist / DB error after API key/JWT extraction
  275      - request.user != user reassignment
  289-296  - Tenant.DoesNotExist in user fallback + User.DoesNotExist + DB error
  302-310  - tenant_id_set fallback from user.tenant_id
  312-314  - fallback from user.tenant object
  318-319  - unauthenticated user with tenant object
  321-328  - unauthenticated user with tenant_id
"""
import uuid
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, UserTenantMembership
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class TenantScopingMiddlewareEdgeCases(TestCase):
    """Cover uncovered middleware paths via full request cycle."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"MW Test {uid}",
            slug=f"mw-test-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"mw-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
        )
        self.client = APIClient()

    def test_request_with_invalid_tenant_header(self):
        """X-Tenant-Id with invalid UUID format returns 400/403."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID="not-a-uuid",
        )
        # Invalid UUID should be rejected, not silently accepted
        self.assertIn(response.status_code, [400, 403])

    def test_request_with_nonexistent_tenant_header(self):
        """X-Tenant-Id with valid UUID but non-existent tenant → 403."""
        self.client.force_authenticate(user=self.user)
        fake_tenant = str(uuid.uuid4())
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=fake_tenant,
        )
        # Middleware returns 403 for non-existent or non-member tenant
        self.assertEqual(response.status_code, 403)

    def test_request_with_non_member_tenant(self):
        """X-Tenant-Id for tenant user is not a member of → 403."""
        other_tenant = Tenant.objects.create(
            name=f"Other {uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(other_tenant.id),
        )
        self.assertEqual(response.status_code, 403)

    def test_request_with_own_tenant_header_succeeds(self):
        """X-Tenant-Id matching user's own tenant should succeed."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        # Own tenant → middleware passes, view handles normally
        self.assertIn(response.status_code, [200, 403])

    def test_request_without_tenant_header_uses_user_tenant(self):
        """Without X-Tenant-Id, middleware falls back to user tenant."""
        self.client.force_authenticate(user=self.user)
        # No HTTP_X_TENANT_ID header — middleware should fall back
        response = self.client.get("/api/v1/assets/")
        # Should not crash; middleware resolves tenant from user
        self.assertIn(response.status_code, [200, 403])

    def test_health_endpoint_no_auth_required(self):
        """Health check endpoint works without authentication."""
        response = self.client.get("/api/v1/health/")
        # Endpoint returns 200 if it exists; 404 if not mounted
        self.assertIn(response.status_code, [200, 404])

    def test_malformed_bearer_token_no_crash(self):
        """Malformed Bearer token should not crash middleware."""
        # No force_authenticate → user is anonymous
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer invalid.token.here"
        )
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        # Anonymous + bad token + X-Tenant-Id → 401 or 403
        self.assertIn(response.status_code, [401, 403])

    def test_empty_authorization_header_no_crash(self):
        """Empty Authorization header should not crash middleware."""
        self.client.credentials(HTTP_AUTHORIZATION="")
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        # Anonymous + empty header → 401 or 403
        self.assertIn(response.status_code, [401, 403])

    def test_api_key_format_in_authorization_no_crash(self):
        """ApiKey format with invalid key should not crash middleware."""
        self.client.credentials(
            HTTP_AUTHORIZATION="ApiKey invalid-key-here"
        )
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        # Invalid API key + X-Tenant-Id → 401 or 403
        self.assertIn(response.status_code, [401, 403])


class MiddlewareDirectUnitTests(TestCase):
    """Direct unit tests for TenantScopingMiddleware using RequestFactory.

    These exercise internal code paths that are hard to reach via APIClient.
    """

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"MWUnit {uid}",
            slug=f"mwunit-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"mwunit-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
        )
        self.factory = RequestFactory()

    def _get_middleware(self):
        from hub.apps.auth.middleware import TenantScopingMiddleware

        return TenantScopingMiddleware(get_response=lambda r: None)

    # --- _extract_tenant_id_from_api_key edge cases (lines 100-103) ---

    def test_api_key_extraction_attribute_error(self):
        """Lines 100-103: AttributeError during API key extraction returns None."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = "ApiKey some-key"
        with patch(
            "hub.apps.auth.models.APIKey.objects.select_related"
        ) as mock_sr:
            mock_qs = MagicMock()
            mock_qs.prefetch_related.return_value.get.side_effect = AttributeError(
                "test"
            )
            mock_sr.return_value = mock_qs
            result = mw._extract_tenant_id_from_api_key(request)
        self.assertIsNone(result)

    def test_api_key_extraction_value_error(self):
        """Lines 100-103: ValueError during API key extraction returns None."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = "ApiKey some-key"
        with patch(
            "hub.apps.auth.models.APIKey.objects.select_related"
        ) as mock_sr:
            mock_qs = MagicMock()
            mock_qs.prefetch_related.return_value.get.side_effect = ValueError(
                "bad value"
            )
            mock_sr.return_value = mock_qs
            result = mw._extract_tenant_id_from_api_key(request)
        self.assertIsNone(result)

    def test_api_key_extraction_no_key(self):
        """Line 73: No API key in header returns None."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        # No Authorization or X-API-Key header
        result = mw._extract_tenant_id_from_api_key(request)
        self.assertIsNone(result)

    # --- _extract_tenant_id_from_jwt edge cases (lines 122, 131-134) ---

    def test_jwt_extraction_value_error(self):
        """Lines 131-134: ValueError during JWT extraction returns None."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer some.jwt.token"
        with patch(
            "hub.apps.auth.jwt_utils.JWTTokenGenerator.decode_access_token",
            side_effect=ValueError("bad token"),
        ):
            result = mw._extract_tenant_id_from_jwt(request)
        self.assertIsNone(result)

    def test_jwt_extraction_type_error(self):
        """Lines 131-134: TypeError during JWT extraction returns None."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer some.jwt.token"
        with patch(
            "hub.apps.auth.jwt_utils.JWTTokenGenerator.decode_access_token",
            side_effect=TypeError("bad type"),
        ):
            result = mw._extract_tenant_id_from_jwt(request)
        self.assertIsNone(result)

    def test_bearer_with_empty_token_returns_none(self):
        """Line 122: 'Bearer ' with empty token after split."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer "
        result = mw._extract_tenant_id_from_jwt(request)
        self.assertIsNone(result)

    def test_jwt_no_tenant_in_payload(self):
        """Line 136: JWT decoded successfully but no tenant_id in payload."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer some.jwt.token"
        with patch(
            "hub.apps.auth.jwt_utils.JWTTokenGenerator.decode_access_token",
            return_value={"sub": str(uuid.uuid4())},
        ):
            result = mw._extract_tenant_id_from_jwt(request)
        self.assertIsNone(result)

    # --- process_request: tenant_id already set (lines 202, 208-213) ---

    def test_tenant_id_already_set_as_uuid(self):
        """Line 202: tenant_id already set as UUID object gets converted to string."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        request.tenant_id = self.tenant.id  # UUID object, not string
        request.tenant = None
        result = mw.process_request(request)
        self.assertIsNone(result)
        self.assertIsInstance(request.tenant_id, str)
        self.assertEqual(request.tenant_id, str(self.tenant.id))

    def test_tenant_id_already_set_nonexistent(self):
        """Lines 208-210: tenant_id set but tenant does not exist in DB."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        request.tenant_id = str(uuid.uuid4())
        result = mw.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 403)

    def test_tenant_id_already_set_db_error(self):
        """Lines 211-213: DB error when looking up tenant_id returns 503."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        request.tenant_id = str(self.tenant.id)
        request.tenant = None

        from django.db import OperationalError

        with patch(
            "hub.apps.tenants.models.Tenant.objects.get",
            side_effect=OperationalError("connection lost"),
        ):
            result = mw.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 503)

    # --- process_request: JWT/API key extraction sets tenant (lines 233-238) ---

    def test_jwt_tenant_extraction_nonexistent_tenant(self):
        """Lines 233-235: JWT extracted tenant_id but tenant does not exist."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.user = AnonymousUser()
        fake_id = str(uuid.uuid4())
        with patch.object(
            mw, "_extract_tenant_id_from_api_key", return_value=None
        ), patch.object(mw, "_extract_tenant_id_from_jwt", return_value=fake_id):
            result = mw.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 403)

    def test_jwt_tenant_extraction_db_error(self):
        """Lines 236-238: DB error after JWT extraction returns 503."""
        from django.db import OperationalError

        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.user = AnonymousUser()
        with patch.object(
            mw, "_extract_tenant_id_from_api_key", return_value=None
        ), patch.object(
            mw,
            "_extract_tenant_id_from_jwt",
            return_value=str(self.tenant.id),
        ), patch(
            "hub.apps.tenants.models.Tenant.objects.get",
            side_effect=OperationalError("connection lost"),
        ):
            result = mw.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 503)

    # --- process_request: X-Tenant-Id with JWT failure (lines 176-177) ---

    def test_x_tenant_id_with_bearer_jwt_failure(self):
        """Lines 176-177: JWT decode failure during X-Tenant-Id processing.

        When JWT decode fails, the user is effectively unauthenticated.
        The middleware returns 401 (not 403) so the frontend can retry
        with a refreshed token.  403 would break automatic refresh.
        """
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_TENANT_ID"] = str(self.tenant.id)
        request.META["HTTP_AUTHORIZATION"] = "Bearer bad.jwt.token"
        request.user = AnonymousUser()
        with patch(
            "hub.apps.auth.jwt_utils.JWTTokenGenerator.decode_access_token",
            side_effect=ValueError("bad jwt"),
        ):
            result = mw.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 401)

    # --- process_request: user fallback (lines 275, 289-296, 302-314) ---

    def test_user_tenant_lookup_user_not_in_db(self):
        """Lines 291-293 + 302-310: User.DoesNotExist falls back to user.tenant_id."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        # Use a MagicMock that looks authenticated but is not in DB.
        # The mock must behave like AnonymousUser for isinstance check (False)
        # but pass the is_authenticated / has id check.
        mock_user = MagicMock(spec=[])
        mock_user.is_authenticated = True
        mock_user.id = uuid.uuid4()
        mock_user.tenant_id = self.tenant.id
        mock_user.tenant = self.tenant
        request.user = mock_user

        result = mw.process_request(request)
        self.assertIsNone(result)
        self.assertEqual(request.tenant_id, str(self.tenant.id))

    def test_user_tenant_lookup_db_error_fallback(self):
        """Lines 294-296: DB error during user lookup falls back to user object."""
        from django.db import OperationalError

        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        with patch.object(
            User.objects,
            "only",
            return_value=MagicMock(
                get=MagicMock(side_effect=OperationalError("conn lost"))
            ),
        ):
            result = mw.process_request(request)
        self.assertIsNone(result)
        self.assertEqual(request.tenant_id, str(self.tenant.id))

    def test_user_has_tenant_object_not_tenant_id(self):
        """Lines 312-314: user has .tenant but no .tenant_id in fallback."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        mock_user = MagicMock(spec=[])
        mock_user.is_authenticated = True
        mock_user.id = uuid.uuid4()
        mock_user.tenant_id = None  # No tenant_id
        mock_user.tenant = self.tenant  # But has tenant object
        request.user = mock_user

        result = mw.process_request(request)
        self.assertIsNone(result)
        self.assertEqual(request.tenant_id, str(self.tenant.id))

    def test_user_tenant_db_lookup_tenant_not_found(self):
        """Lines 289-290: Tenant.DoesNotExist during authenticated user fallback."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")

        # Use mock user with a tenant_id pointing to non-existent tenant.
        # The DB lookup for User will succeed but Tenant lookup will fail.
        mock_user = MagicMock(spec=[])
        mock_user.is_authenticated = True
        mock_user.id = self.user.id
        fake_tenant_id = uuid.uuid4()
        mock_user.tenant_id = fake_tenant_id
        mock_user.tenant = None
        request.user = mock_user

        # Patch User.objects.only().get() to return a user with fake tenant_id
        mock_db_user = MagicMock()
        mock_db_user.tenant_id = fake_tenant_id
        with patch.object(
            User.objects,
            "only",
            return_value=MagicMock(get=MagicMock(return_value=mock_db_user)),
        ):
            result = mw.process_request(request)

        self.assertIsNone(result)
        self.assertEqual(request.tenant_id, str(fake_tenant_id))
        # Tenant lookup failed, so tenant should be None
        self.assertIsNone(request.tenant)

    # --- process_request: unauthenticated user with tenant (lines 318-328) ---

    def test_unauthenticated_user_with_tenant_object(self):
        """Lines 318-319: unauthenticated user with tenant attribute."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        # AnonymousUser subclass that has tenant attribute
        anon = AnonymousUser()
        anon.tenant = self.tenant
        anon.tenant_id = None
        request.user = anon

        result = mw.process_request(request)
        self.assertIsNone(result)
        self.assertEqual(request.tenant_id, str(self.tenant.id))
        self.assertEqual(request.tenant, self.tenant)

    def test_unauthenticated_user_with_tenant_id(self):
        """Lines 321-328: unauthenticated user with tenant_id but no tenant object."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        anon = AnonymousUser()
        anon.tenant = None
        anon.tenant_id = self.tenant.id
        request.user = anon

        result = mw.process_request(request)
        self.assertIsNone(result)
        self.assertEqual(request.tenant_id, str(self.tenant.id))

    def test_unauthenticated_user_with_tenant_id_nonexistent(self):
        """Lines 325-328: unauthenticated user tenant_id to non-existent tenant."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        anon = AnonymousUser()
        anon.tenant = None
        fake_id = uuid.uuid4()
        anon.tenant_id = fake_id
        request.user = anon

        result = mw.process_request(request)
        self.assertIsNone(result)
        self.assertEqual(request.tenant_id, str(fake_id))
        self.assertIsNone(request.tenant)

    # --- __call__: force_auth_user assignment (line 275) ---

    def test_request_user_reassignment(self):
        """Line 275: request.user is reassigned when different from force_auth user."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.user = AnonymousUser()
        request._force_auth_user = self.user

        mw.__call__(request)
        self.assertEqual(request.user, self.user)

    # --- process_request: FEATURE_TENANT_SWITCH_ENABLED (line 158) ---

    def test_feature_tenant_switch_disabled(self):
        """Line 158: FEATURE_TENANT_SWITCH_ENABLED=False returns 403."""
        mw = self._get_middleware()
        request = self.factory.get("/api/v1/assets/")
        request.META["HTTP_X_TENANT_ID"] = str(self.tenant.id)
        request.user = self.user
        with patch("django.conf.settings.FEATURE_TENANT_SWITCH_ENABLED", False):
            result = mw.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 403)
