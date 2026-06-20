"""
Phase 260.2.E — ``POST /api/v1/files/init/`` per-user and per-tenant throttles.

Contract (S-9): 60 req/min per authenticated user, 600 req/min per tenant,
using DRF ``SimpleRateThrottle`` + Django default cache (Redis in deployed
environments). Integration-style tests: real cache backend, no mocks on the
HTTP boundary.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.throttles import FileInitTenantThrottle, FileInitUserThrottle
from hub.apps.files.views import FileViewSet
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _init_payload() -> dict[str, Any]:
    return {
        "name": f"rl-init-{uuid.uuid4().hex[:10]}.csv",
        "content_type": "text/csv",
        "size": 1024,
        "upload_method": "browser",
    }


def _seed_tenant_with_user(*, tenant: Tenant | None = None):
    uid = uuid.uuid4().hex[:8]
    if tenant is None:
        tenant = Tenant.objects.create(
            name=f"file-init-rl-{uid}",
            slug=f"file-init-rl-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
    ensure_tenant_has_active_subscription(tenant)

    user_manager = cast("Any", User.objects)
    user = user_manager.create_user(
        email=f"file-init-rl-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return tenant, user, client


class FileInitRateLimitWiringTest(TestCase):
    @pytest.mark.integration
    def test_default_file_init_rate_values_match_s9_contract(self):
        user_throttle = FileInitUserThrottle()
        tenant_throttle = FileInitTenantThrottle()
        self.assertEqual(user_throttle.get_rate(), "60/minute")
        self.assertEqual(tenant_throttle.get_rate(), "600/minute")

    @pytest.mark.integration
    def test_init_upload_action_uses_file_init_throttles(self):
        view = FileViewSet()
        view.action = "init_upload"
        throttles = view.get_throttles()
        self.assertTrue(any(isinstance(t, FileInitUserThrottle) for t in throttles))
        self.assertTrue(any(isinstance(t, FileInitTenantThrottle) for t in throttles))

    @pytest.mark.integration
    def test_list_action_does_not_use_file_init_throttles(self):
        view = FileViewSet()
        view.action = "list"
        throttles = view.get_throttles()
        self.assertFalse(any(isinstance(t, FileInitUserThrottle) for t in throttles))
        self.assertFalse(any(isinstance(t, FileInitTenantThrottle) for t in throttles))


class FileInitRateLimitQuotaTest(TestCase):
    def setUp(self):
        super().setUp()
        self._orig_user_rates = dict(
            cast("dict[str, str]", FileInitUserThrottle.THROTTLE_RATES or {})
        )
        self._orig_tenant_rates = dict(
            cast("dict[str, str]", FileInitTenantThrottle.THROTTLE_RATES or {})
        )
        cache.clear()

    def tearDown(self):
        FileInitUserThrottle.THROTTLE_RATES = self._orig_user_rates
        FileInitTenantThrottle.THROTTLE_RATES = self._orig_tenant_rates
        cache.clear()

    @pytest.mark.integration
    def test_user_throttle_second_init_within_window_returns_429_with_retry_after(
        self,
    ):
        _tenant, _user, client = _seed_tenant_with_user()
        FileInitUserThrottle.THROTTLE_RATES = {
            **self._orig_user_rates,
            "file_init_user": "1/minute",
        }
        FileInitTenantThrottle.THROTTLE_RATES = {
            **self._orig_tenant_rates,
            "file_init_tenant": "1000/minute",
        }

        first = cast(
            "Any",
            client.post(
                "/api/v1/files/init/",
                _init_payload(),
                format="json",
            ),
        )
        self.assertNotEqual(first.status_code, status.HTTP_429_TOO_MANY_REQUESTS, first.content)

        blocked = cast(
            "Any",
            client.post(
                "/api/v1/files/init/",
                _init_payload(),
                format="json",
            ),
        )
        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(blocked.data["error"]["code"], "RATE_LIMIT_EXCEEDED")
        details = blocked.data["error"].get("details") or {}
        self.assertIn("retry_after", details)
        self.assertGreaterEqual(int(details["retry_after"]), 1)
        self.assertIn("Retry-After", blocked)
        self.assertGreaterEqual(int(blocked["Retry-After"]), 1)

    @pytest.mark.integration
    def test_tenant_throttle_applies_across_users_in_same_tenant(self):
        tenant, _user1, client1 = _seed_tenant_with_user()
        _tenant, _user2, client2 = _seed_tenant_with_user(tenant=tenant)
        FileInitUserThrottle.THROTTLE_RATES = {
            **self._orig_user_rates,
            "file_init_user": "1000/minute",
        }
        FileInitTenantThrottle.THROTTLE_RATES = {
            **self._orig_tenant_rates,
            "file_init_tenant": "1/minute",
        }

        first = cast(
            "Any",
            client1.post(
                "/api/v1/files/init/",
                _init_payload(),
                format="json",
            ),
        )
        self.assertNotEqual(first.status_code, status.HTTP_429_TOO_MANY_REQUESTS, first.content)

        blocked = cast(
            "Any",
            client2.post(
                "/api/v1/files/init/",
                _init_payload(),
                format="json",
            ),
        )
        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(blocked.data["error"]["code"], "RATE_LIMIT_EXCEEDED")
        details = blocked.data["error"].get("details") or {}
        self.assertIn("retry_after", details)
        self.assertGreaterEqual(int(details["retry_after"]), 1)
        self.assertIn("Retry-After", blocked)
        self.assertGreaterEqual(int(blocked["Retry-After"]), 1)
