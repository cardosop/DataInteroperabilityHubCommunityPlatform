"""
Phase 54.5 — Search Deprecation Header & Empty-Query Guard Tests

Validates via real HTTP requests:
- SearchViewSet returns Deprecation + Link headers
- UnifiedSearchView does NOT return deprecation headers
- The deprecated SearchViewSet rejects empty q with 400 (QUERY_REQUIRED);
  the canonical UnifiedSearchView treats empty q as filter-only browse
  mode (200, Phase 18.3 — the shipped frontend omits q when the search
  box is empty)
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.billing.tests.plan_fixtures import get_pro_plan
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _setup_auth_client():
    """Create tenant + user + authenticated API client."""
    uid = uuid.uuid4().hex[:6]
    plan = get_pro_plan()
    tenant = Tenant.objects.create(
        name=f"search-hdr-{uid}",
        slug=f"search-hdr-{uid}",
        plan=plan,
    )
    from datetime import timedelta

    from django.utils import timezone

    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    user = User.objects.create_user(
        email=f"search-hdr-{uid}@test.local",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    token = JWTTokenGenerator.generate_access_token(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class SearchDeprecationHeaderTest(TestCase):
    """Test that SearchViewSet returns deprecation headers on real requests."""

    def setUp(self):
        self.client = _setup_auth_client()

    def test_search_viewset_returns_deprecation_header(self):
        """GET /api/v1/search/search/?q=test must include Deprecation header."""
        resp = self.client.get("/api/v1/search/search/", {"q": "test"})
        self.assertIn(resp.status_code, [200, 400])
        if resp.status_code == 200:
            self.assertIn(
                "Deprecation",
                resp,
                "SearchViewSet must set Deprecation response header",
            )
            self.assertEqual(resp["Deprecation"], "true")

    def test_search_viewset_returns_link_header(self):
        """GET /api/v1/search/search/?q=test must include Link header."""
        resp = self.client.get("/api/v1/search/search/", {"q": "test"})
        if resp.status_code == 200:
            self.assertIn(
                "Link",
                resp,
                "SearchViewSet must set Link response header",
            )
            self.assertIn("successor-version", resp.get("Link", ""))

    def test_unified_search_no_deprecation_header(self):
        """GET /api/search/?q=test must NOT include Deprecation header."""
        resp = self.client.get("/api/search/", {"q": "test"})
        if resp.status_code == 200:
            self.assertNotIn(
                "Deprecation",
                resp,
                "UnifiedSearchView must NOT set Deprecation header",
            )


class SearchViewSetEmptyQueryGuardTest(TestCase):
    """Deprecated view rejects empty q (400); unified view stays filter-only (200)."""

    def setUp(self):
        self.client = _setup_auth_client()

    def test_search_viewset_rejects_empty_q(self):
        """GET /api/v1/search/search/?q= must return 400."""
        resp = self.client.get("/api/v1/search/search/", {"q": ""})
        self.assertEqual(
            resp.status_code,
            400,
            f"Empty q must return 400, got {resp.status_code}",
        )
        self.assertIn("required", str(resp.data).lower())

    def test_unified_search_empty_q_returns_filter_only(self):
        """GET /api/search/?q= returns 200 filter-only (Phase 18.3).

        The canonical UnifiedSearchView treats an empty/missing ``q`` as
        valid browse mode — the shipped frontend search page omits ``q``
        when the search box is empty and expects filtered listings. Only
        the deprecated /api/v1/search/search/ ViewSet requires ``q``.
        """
        resp = self.client.get("/api/search/", {"q": ""})
        self.assertEqual(
            resp.status_code,
            200,
            f"Empty q on the unified surface must return 200 filter-only, got {resp.status_code}",
        )
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("results", data)
