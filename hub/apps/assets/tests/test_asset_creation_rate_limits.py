"""
Phase 250.7.G — asset-creation rate limits on all creation endpoints.

Pins the contract from S-8:

* Per-user throttle: 60/minute.
* Per-tenant throttle: 600/minute.
* Applies to BOTH asset-creation endpoints:
  - ``POST /api/v1/assets/``
  - ``POST /api/v1/assets/data-first/``
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

from hub.apps.assets.throttles import (
    AssetDataFirstTenantThrottle,
    AssetDataFirstUserThrottle,
)
from hub.apps.assets.views import AssetViewSet
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant_user_client(*, tenant: Tenant | None = None):
    uid = uuid.uuid4().hex[:8]
    if tenant is None:
        tenant = Tenant.objects.create(
            name=f"rate-limit-{uid}",
            slug=f"rate-limit-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(tenant)

    user_manager = cast("Any", User.objects)
    user = user_manager.create_user(
        email=f"rl-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(user)

    file_obj = File.objects.create(
        tenant=tenant,
        name=f"rate-limit-{uid}.csv",
        content_type="text/csv",
        size=42,
        status=FileStatus.ACTIVE,
        storage_path=f"{tenant.id}/{uuid.uuid4()}/rate-limit-{uid}.csv",
        created_by=user,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return tenant, user, client, file_obj


class AssetCreationRateLimitWiringTest(TestCase):
    def test_default_asset_creation_rate_values_match_s8_contract(self):
        user_throttle = AssetDataFirstUserThrottle()
        tenant_throttle = AssetDataFirstTenantThrottle()
        assert user_throttle.get_rate() == "60/minute"
        assert tenant_throttle.get_rate() == "600/minute"

    def test_create_action_uses_asset_creation_throttles(self):
        view = AssetViewSet()
        view.action = "create"
        throttles = view.get_throttles()
        assert any(isinstance(t, AssetDataFirstUserThrottle) for t in throttles)
        assert any(isinstance(t, AssetDataFirstTenantThrottle) for t in throttles)

    def test_data_first_action_uses_asset_creation_throttles(self):
        view = AssetViewSet()
        view.action = "data_first"
        throttles = view.get_throttles()
        assert any(isinstance(t, AssetDataFirstUserThrottle) for t in throttles)
        assert any(isinstance(t, AssetDataFirstTenantThrottle) for t in throttles)


class AssetCreationRateLimitQuotaTest(TestCase):
    def setUp(self):
        self._orig_user_rates = dict(
            cast("dict[str, str]", AssetDataFirstUserThrottle.THROTTLE_RATES or {})
        )
        self._orig_tenant_rates = dict(
            cast("dict[str, str]", AssetDataFirstTenantThrottle.THROTTLE_RATES or {})
        )
        cache.clear()

    def tearDown(self):
        AssetDataFirstUserThrottle.THROTTLE_RATES = self._orig_user_rates
        AssetDataFirstTenantThrottle.THROTTLE_RATES = self._orig_tenant_rates
        cache.clear()

    def test_user_throttle_budget_is_shared_across_create_and_data_first(self):
        _tenant, _user, client, _file_obj = _seed_tenant_user_client()
        AssetDataFirstUserThrottle.THROTTLE_RATES = {
            **self._orig_user_rates,
            "asset_data_first_user": "1/minute",
        }
        AssetDataFirstTenantThrottle.THROTTLE_RATES = {
            **self._orig_tenant_rates,
            "asset_data_first_tenant": "1000/minute",
        }

        # First call: POST /api/v1/assets/ with a VALID body so the
        # throttle is actually evaluated (an empty body would return
        # 400 from validation, not prove the throttle consumed the
        # budget).
        uid = uuid.uuid4().hex[:8]
        create_resp = cast(
            "Any",
            client.post(
                "/api/v1/assets/",
                {"key": f"rl-{uid}", "name": "Rate Limit Test"},
                format="json",
            ),
        )
        # With a valid body the throttle is consumed; the response
        # may be 201 (success) or 429 (already throttled from other
        # tests). Both prove the throttle was evaluated.
        self.assertIn(
            create_resp.status_code,
            (status.HTTP_201_CREATED, status.HTTP_429_TOO_MANY_REQUESTS),
        )

        # Second call: POST /api/v1/assets/data-first/ — the per-user
        # budget (1/min) was consumed by the first call, so this must
        # return 429.
        second_resp = cast(
            "Any",
            client.post(
                "/api/v1/assets/data-first/",
                {"key": f"rl-df-{uuid.uuid4().hex[:8]}", "name": "N"},
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            ),
        )
        self.assertEqual(
            second_resp.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Per-user throttle budget (1/min) shared across create "
            "and data-first endpoints must be exhausted by the first "
            "call and return 429 on the second.",
        )

    def test_tenant_throttle_applies_across_users_in_same_tenant(self):
        tenant, _user1, client1, _file1 = _seed_tenant_user_client()
        _tenant, _user2, client2, _file2 = _seed_tenant_user_client(tenant=tenant)
        AssetDataFirstUserThrottle.THROTTLE_RATES = {
            **self._orig_user_rates,
            "asset_data_first_user": "1000/minute",
        }
        AssetDataFirstTenantThrottle.THROTTLE_RATES = {
            **self._orig_tenant_rates,
            "asset_data_first_tenant": "1/minute",
        }

        # First call: user1 POSTs with a VALID body so the tenant
        # throttle is actually evaluated.
        uid1 = uuid.uuid4().hex[:8]
        first_resp = cast(
            "Any",
            client1.post(
                "/api/v1/assets/",
                {"key": f"rl-t1-{uid1}", "name": "Tenant Rate Limit"},
                format="json",
            ),
        )
        self.assertIn(
            first_resp.status_code,
            (status.HTTP_201_CREATED, status.HTTP_429_TOO_MANY_REQUESTS),
        )

        # Second call: user2 in the SAME tenant. The per-tenant
        # budget (1/min) was consumed by user1, so user2 gets 429.
        uid2 = uuid.uuid4().hex[:8]
        second_resp = cast(
            "Any",
            client2.post(
                "/api/v1/assets/",
                {"key": f"rl-t2-{uid2}", "name": "Tenant Rate Limit 2"},
                format="json",
            ),
        )
        self.assertEqual(
            second_resp.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Per-tenant throttle budget (1/min) shared across users "
            "in the same tenant must return 429 for user2 after "
            "user1 consumed the budget.",
        )
