"""
Phase 313.H.3 — plan downgrade + ML add-on endpoint boundary.

Full mode: billing's ``PlanLimitService.validate_downgrade`` blocks a
downgrade that would violate the target plan's limits; the ML add-on
endpoint resolves qualification through billing subscriptions.

Core-only mode (simulated by unregistering the paid providers, the
exact runtime shape of a core-only process): the downgrade validator
hook is absent → the downgrade is always valid; the ML add-on
endpoint is paid-by-design → an empty addons list.

NO MOCKS at contract boundaries: real Postgres, real ORM, real
endpoint, real billing service in full mode.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.core import commercial_hooks
from hub.apps.tenants.models import Tenant, TenantPlan
from hub.apps.tenants.tests.factories import SubscriptionFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

DOWNGRADE_URL = "/api/v1/tenants/me/plan/downgrade/"
ML_ADDONS_URL = "/api/v1/tenants/me/plan/available-ml-addons/"


class PlanDowngradeBoundaryTests(TestCase):
    """Downgrade validation — full-mode billing vs core-only hook-absent."""

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
        self.current_plan = TenantPlan.objects.create(
            name=f"current-{uid}",
            slug=f"current-{uid}",
            tier="PRO",
            is_active=True,
            limits_json={"max_assets": 100},
        )
        self.target_plan = TenantPlan.objects.create(
            name=f"target-{uid}",
            slug=f"target-{uid}",
            tier="FREE",
            is_active=True,
            limits_json={"max_assets": 1},
        )
        self.tenant.plan = self.current_plan
        self.tenant.save(update_fields=["plan"])
        # The tenant middleware blocks writes without an active
        # subscription (real platform behaviour).
        SubscriptionFactory.create_subscription(tenant=self.tenant, plan=self.current_plan)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _add_assets(self, count):
        for i in range(count):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}-{uuid.uuid4().hex[:8]}",
                name=f"Asset {i}",
                created_by=self.user,
            )

    def _downgrade(self):
        return self.client.post(
            DOWNGRADE_URL,
            {"plan_slug": self.target_plan.slug},
            format="json",
        )

    def test_full_mode_blocks_downgrade_when_usage_exceeds_target_limit(self):
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest("full-mode contract — billing absent in core-only")

        self._add_assets(2)
        resp = self._downgrade()
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        self.tenant.refresh_from_db()
        assert self.tenant.plan == self.current_plan

    def test_full_mode_allows_downgrade_within_limits(self):
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest("full-mode contract — billing absent in core-only")

        self._add_assets(1)
        resp = self._downgrade()
        assert resp.status_code == status.HTTP_200_OK
        self.tenant.refresh_from_db()
        assert self.tenant.plan == self.target_plan

    def test_core_only_downgrade_always_valid(self):
        """Core-only: no billing validator → even a violating downgrade passes."""
        self._add_assets(2)
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            resp = self._downgrade()
        assert resp.status_code == status.HTTP_200_OK
        self.tenant.refresh_from_db()
        assert self.tenant.plan == self.target_plan


class MlAddonsBoundaryTests(TestCase):
    """ML add-on endpoint — paid-by-design; empty list in core-only."""

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
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_core_only_returns_empty_addons(self):
        import os

        # Restore the AMBIENT value (not "absent"): in a real core-only
        # run HUB_CORE_ONLY=1 is set by the harness, and deleting it here
        # breaks the is_core_only() skips in the sibling full-mode tests.
        original = os.environ.get("HUB_CORE_ONLY")
        os.environ["HUB_CORE_ONLY"] = "1"
        try:
            resp = self.client.get(ML_ADDONS_URL)
        finally:
            if original is None:
                del os.environ["HUB_CORE_ONLY"]
            else:
                os.environ["HUB_CORE_ONLY"] = original
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {"addons": []}

    def test_full_mode_fresh_tenant_lacks_base_plan(self):
        """Full mode: no billing base subscription → qualification fails."""
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest("full-mode contract — billing absent in core-only")

        resp = self.client.get(ML_ADDONS_URL)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Starter" in resp.json()["error"]
