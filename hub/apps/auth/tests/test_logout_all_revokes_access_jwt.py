import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class LogoutAllRevokesAccessJWTTest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Tenant {uid}",
            slug=f"tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(  # type: ignore[attr-defined]  # test: edge-case type exercise
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @staticmethod
    def _extract_access_token(response) -> str:
        body = response.json()
        token = body.get("access_token")
        if token:
            return str(token)
        cookie_token = response.cookies.get("access_token")
        if cookie_token:
            return str(cookie_token.value)
        return ""

    def test_logout_all_invalidates_existing_access_token(self) -> None:
        access_v1 = JWTTokenGenerator.generate_access_token(self.user)

        logout_response = self.client.post(
            "/api/v1/auth/logout/",
            {},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access_v1}",
        )
        self.assertEqual(logout_response.status_code, 200)

        me_response = self.client.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {access_v1}",
        )
        self.assertEqual(me_response.status_code, 401)
        self.assertEqual(
            me_response.json().get("error", {}).get("code"),
            "TOKEN_INVALIDATED",
        )

    def test_relogin_issues_new_version_and_access_succeeds(self) -> None:
        access_v1 = JWTTokenGenerator.generate_access_token(self.user)
        payload_v1 = JWTTokenGenerator.decode_access_token(
            access_v1,
            verify_version=False,
        )
        assert payload_v1 is not None

        logout_response = self.client.post(
            "/api/v1/auth/logout/",
            {},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access_v1}",
        )
        self.assertEqual(logout_response.status_code, 200)

        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        access_v2 = self._extract_access_token(login_response)
        self.assertTrue(access_v2)

        payload_v2 = JWTTokenGenerator.decode_access_token(
            access_v2,
            verify_version=False,
        )
        assert payload_v2 is not None
        self.assertGreater(
            int(payload_v2.get("authz_version", 0)),
            int(payload_v1.get("authz_version", 0)),
        )

        me_response = self.client.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {access_v2}",
        )
        self.assertEqual(me_response.status_code, 200)
