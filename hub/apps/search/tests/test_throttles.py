"""
Phase 273.2.6 — throttle tests for search endpoints.

Covers:
- 60+1 requests → 429 with Retry-After
- Per-tenant isolation (tenant A exhaustion does not affect tenant B)
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _mk_tenant(name="TL"):
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{name}-{uid}", slug=f"tl-{uid}",
        status="ACTIVE", kyc_status="UNVERIFIED",
    )


def _mk_user(tenant, email_pfx="user"):
    return User.objects.create_user(
        email=f"{email_pfx}-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass", tenant=tenant, status=UserStatus.ACTIVE,
    )


@override_settings(SEARCH_RATE_LIMIT_PER_MIN="5/min")
class TestSearchThrottle429(TestCase):
    """60+1 pattern: exhaust 5/min rate, 6th returns 429."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _mk_tenant("TH")
        self.user = _mk_user(self.tenant)
        self.client.force_authenticate(user=self.user)

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    def test_429_on_sixth_request(self, mock_fts):
        mock_fts.return_value = []
        for i in range(5):
            resp = self.client.get("/api/search/?q=test")
            assert resp.status_code == 200, f"req {i}: {resp.status_code}"

        resp = self.client.get("/api/search/?q=test")
        assert resp.status_code == 429, resp.status_code
        assert "Retry-After" in resp

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    def test_tenant_isolation(self, mock_fts):
        mock_fts.return_value = []

        tenant_b = _mk_tenant("TB")
        user_b = _mk_user(tenant_b)
        client_b = APIClient()
        client_b.force_authenticate(user=user_b)

        # Exhaust tenant A's quota.
        for _ in range(5):
            self.client.get("/api/search/?q=test")
        assert self.client.get("/api/search/?q=test").status_code == 429

        # Tenant B should still succeed.
        resp = client_b.get("/api/search/?q=test")
        assert resp.status_code == 200, f"tenant B blocked: {resp.status_code}"
