import uuid
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class CookieDomainTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Cookie Domain Tenant {uid}",
            slug=f"cookie-domain-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = cast(
            Any,
            User.objects.create(
            email=f"cookie-domain-{uid}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            ),
        )
        self.user.set_password("testpass123")
        self.user.save(update_fields=["password"])
        self.login_payload = {
            "email": self.user.email,
            "password": "testpass123",
        }

    @override_settings(
        USE_HTTPONLY_AUTH_COOKIES=True,
        SESSION_COOKIE_DOMAIN=".meshant.com",
        CSRF_COOKIE_DOMAIN=".meshant.com",
        REFRESH_COOKIE_NAME="__Secure-refresh_token",
    )
    def test_staging_override_applies_meshant_domain_to_auth_cookies(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("__Secure-refresh_token", response.cookies)
        self.assertIn("access_token", response.cookies)
        self.assertEqual(
            response.cookies["__Secure-refresh_token"]["domain"],
            ".meshant.com",
        )
        self.assertEqual(
            response.cookies["access_token"]["domain"],
            ".meshant.com",
        )

    @override_settings(
        USE_HTTPONLY_AUTH_COOKIES=True,
        SESSION_COOKIE_DOMAIN=None,
        CSRF_COOKIE_DOMAIN=None,
        REFRESH_COOKIE_NAME="__Secure-refresh_token",
    )
    def test_dev_override_none_emits_host_only_auth_cookies(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("__Secure-refresh_token", response.cookies)
        self.assertIn("access_token", response.cookies)
        self.assertEqual(response.cookies["__Secure-refresh_token"]["domain"], "")
        self.assertEqual(
            response.cookies["access_token"]["domain"],
            "",
        )
