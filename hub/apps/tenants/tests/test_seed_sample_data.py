"""
Phase 313.H.3 — sample-data seeding endpoint boundary.

Full mode: the marketplace provider (registered in the paid app's
``AppConfig.ready()``) seeds the sample listing via the commercial
hook. Core-only mode: no provider → asset seeded without a listing,
``listing_id: null``, and no paid import ever executes.

NO MOCKS at contract boundaries: real Postgres, real ORM, real
endpoint — core-only mode is simulated by unregistering the paid
providers (the exact runtime shape of a core-only process).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.core import commercial_hooks
from hub.apps.marketplace.models import Listing
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.tests.factories import SubscriptionFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

SEED_URL = "/api/v1/tenants/me/seed-sample/"


class SeedSampleEndpointTests(TestCase):
    """Seed-sample endpoint — full-mode and core-only contracts."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T-{uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
        )
        self.user = User.objects.create_user(
            email=f"u-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
        )
        # The tenant middleware blocks writes without an active
        # subscription (real platform behaviour).
        SubscriptionFactory.create_subscription(tenant=self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _post(self):
        return self.client.post(SEED_URL, format="json")

    def test_full_mode_seeds_asset_and_listing(self):
        resp = self._post()
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["asset_id"]
        assert data["listing_id"]
        assert Listing.objects.filter(asset_id=data["asset_id"]).exists()

    def test_full_mode_is_idempotent(self):
        first = self._post()
        second = self._post()
        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_200_OK
        assert Listing.objects.filter(tenant=self.tenant).count() == 1

    def test_full_mode_emits_seed_audit_event(self):
        self._post()
        assert AuditEvent.objects.filter(
            action="TENANT_SAMPLE_DATA_SEEDED",
            tenant=self.tenant,
        ).exists()

    def test_core_only_seeds_asset_without_listing(self):
        """Core-only: no provider → asset only, listing_id null, no crash."""
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            resp = self._post()
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["asset_id"]
        assert data["listing_id"] is None
        assert Listing.objects.filter(tenant=self.tenant).count() == 0
