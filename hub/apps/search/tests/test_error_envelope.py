"""
Phase 273.5.2 — error envelope shape tests for search/semantic views.

Every 4xx/5xx response from UnifiedSearchView must conform to the
canonical ``{error: {code, message, http_status, request_id}}`` shape.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"EE-{uid}",
        slug=f"ee-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"ee-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


class TestSearchErrorEnvelope(TestCase):
    """UnifiedSearchView error responses use canonical envelope."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.client.force_authenticate(user=self.user)

    def _assert_envelope(self, resp, expected_code, expected_status):
        assert resp.status_code == expected_status
        data = resp.json() if hasattr(resp, "json") else resp.data
        assert "error" in data, f"Missing 'error' key in {data}"
        err = data["error"]
        assert err.get("code") == expected_code
        assert "message" in err
        assert err.get("http_status") == expected_status
        assert "request_id" in err

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    def test_missing_q_returns_filter_only(self, mock_fts):
        """Empty/missing q returns 200 with filter-only results (Phase 18.3)."""
        mock_fts.return_value = []
        resp = self.client.get("/api/search/")  # no q param
        assert resp.status_code == 200
        data = resp.json() if hasattr(resp, "json") else resp.data
        assert "results" in data
        assert isinstance(data["results"], list)

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    def test_query_too_long_returns_envelope(self, mock_fts):
        mock_fts.return_value = []
        long_q = "x" * 600
        resp = self.client.get(f"/api/search/?q={long_q}")
        self._assert_envelope(resp, "QUERY_TOO_LONG", 400)


class TestSearchErrorEnvelopeUnauth(TestCase):
    """Unauthenticated request returns standard DRF error (not search-specific)."""

    def test_unauthenticated(self):
        client = APIClient()
        resp = client.get("/api/search/?q=test")
        assert resp.status_code in (401, 403)
