"""
DB-backed account lockout regression tests (260.B.4).
"""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import LoginAttempt
from hub.apps.auth.views import (
    _account_lockout_cache_key,
    _check_account_lockout,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DBBackedLockoutTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Lockout Tenant {uid}",
            slug=f"lockout-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(  # type: ignore[attr-defined]  # test: edge-case type exercise
            email=f"lockout-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.login_url = "/api/v1/auth/login/"

    def _post_login(self, password: str):
        return self.client.post(
            self.login_url,
            {"email": self.user.email, "password": password},
            format="json",
        )

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_LOCKOUT_WINDOW_MINUTES=15)
    def test_cache_eviction_mid_window_still_enforces_lockout_from_db(self):
        for _ in range(3):
            response = self._post_login("wrong-password")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        cache.delete(_account_lockout_cache_key(self.user.email))

        locked_response = self._post_login("testpass123")
        self.assertEqual(
            locked_response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
        self.assertIn(
            "Account temporarily locked",
            str(getattr(locked_response, "data", {}).get("detail", "")),
        )

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_LOCKOUT_WINDOW_MINUTES=1)
    def test_successful_login_after_window_expiry_clears_lockout(self):
        for _ in range(3):
            response = self._post_login("wrong-password")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        locked_response = self._post_login("testpass123")
        self.assertEqual(
            locked_response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

        stale_timestamp = timezone.now() - timedelta(minutes=2)
        LoginAttempt.objects.filter(email=self.user.email, success=False).update(
            created_at=stale_timestamp
        )
        lockout_cache_key = _account_lockout_cache_key(self.user.email)
        cache.delete(lockout_cache_key)

        # Progressive backoff sets locked_until on the User model independently
        # of the LoginAttempt window — clear it so the next login isn't blocked.
        self.user.refresh_from_db()
        self.user.locked_until = None
        self.user.lockout_level = 0
        self.user.failed_login_count = 0
        self.user.save(update_fields=["locked_until", "lockout_level", "failed_login_count"])

        success_response = self._post_login("testpass123")
        self.assertEqual(success_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(cache.get(lockout_cache_key))

        post_success_failure = self._post_login("wrong-password")
        self.assertEqual(
            post_success_failure.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_LOCKOUT_WINDOW_MINUTES=15)
    def test_db_query_executes_only_on_cache_miss(self):
        LoginAttempt.objects.create(
            email=self.user.email,
            ip_address="127.0.0.1",
            success=False,
        )
        cache_key = _account_lockout_cache_key(self.user.email)
        cache.delete(cache_key)

        with CaptureQueriesContext(connection) as cold_queries:
            self.assertTrue(_check_account_lockout(self.user.email))
        cold_lockout_queries = [
            q["sql"]
            for q in cold_queries.captured_queries
            if "login_attempts" in q["sql"]
        ]
        self.assertGreaterEqual(len(cold_lockout_queries), 1)

        with CaptureQueriesContext(connection) as warm_queries:
            self.assertTrue(_check_account_lockout(self.user.email))
        warm_lockout_queries = [
            q["sql"]
            for q in warm_queries.captured_queries
            if "login_attempts" in q["sql"]
        ]
        self.assertEqual(len(warm_lockout_queries), 0)
