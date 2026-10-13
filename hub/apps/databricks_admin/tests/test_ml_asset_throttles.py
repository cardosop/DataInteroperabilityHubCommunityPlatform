"""TDD pins for the ML-assets throttle (openspec
add-databricks-ml-assets task 12.6 / the Shared DoD throttle gate) —
the Phase 273 contract on the 12.x browse surface:

- the throttle's cache key carries the TENANT ID
  (``throttle_databricks_ml_assets_<tenant_id>`` — tenant A's
  exhaustion never affects tenant B's quota),
- a 429 emits ``DATABRICKS_ML_RATE_LIMIT_EXCEEDED`` from the
  ``allow_request`` failure branch (the DRF 3.16 discipline — the
  ``throttled()`` override is dead code) with ``result="THROTTLED"``
  and identifiers-only details,
- the VIEWS mount the throttle (the coverage check's own contract).

No mocks: a REAL AuditEvent row asserted, the REAL production throttle
class against a locmem cache (the pin overrides CACHES so the bucket
state is deterministic without a Redis dependency), and the REAL view
path for the 429 leg.
"""

import uuid

import pytest
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _api_client, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

_LOCMEM_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


class TestMlAssetThrottleKey(TestCase):
    """The cache key carries the tenant id (the Phase 273 letter)."""

    def test_the_cache_key_carries_the_tenant_id(self):
        from hub.apps.databricks_admin.throttles import MlAssetsRateThrottle

        tenant = TenantFactory.create_tenant()
        user = _make_user(tenant, f"throttle-{uuid.uuid4().hex[:8]}@test.com")
        request = APIRequestFactory().get("/irrelevant")
        request.user = user
        request.tenant = tenant
        throttle = MlAssetsRateThrottle()
        key = throttle.get_cache_key(request, view=None)
        assert key == f"throttle_databricks_ml_assets_{tenant.id}", key


class TestMlAssetThrottleEmission(TestCase):
    """The exhausted bucket emits the classified rate-limit audit row."""

    @override_settings(CACHES=_LOCMEM_CACHES)
    def test_the_failure_branch_emits_the_rate_limit_row(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.throttles import MlAssetsRateThrottle

        tenant = TenantFactory.create_tenant()
        user = _make_user(tenant, f"throttle-emit-{uuid.uuid4().hex[:8]}@test.com")
        request = APIRequestFactory().get("/irrelevant")
        request.user = user
        request.tenant = tenant

        class _StubView:
            throttle_scope = "databricks_ml_assets"

        throttle = MlAssetsRateThrottle()
        throttle.THROTTLE_RATES = {"databricks_ml_assets": "1/min"}

        assert throttle.allow_request(request, _StubView) is True, "the first call is allowed"
        assert throttle.allow_request(request, _StubView) is False, "the second exhausts the bucket"
        rows = list(
            AuditEvent.objects.filter(
                tenant=tenant, action="DATABRICKS_ML_RATE_LIMIT_EXCEEDED"
            ).order_by("timestamp")
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.resource_type == "DATABRICKS_ML_ASSET"
        assert row.result == "THROTTLED"
        assert set(row.details_json) == {"wait_seconds"}, "identifiers only"


class TestMlAssetViewThrottle(TestCase):
    """The views mount the throttle — a 429 through the REAL view path
    carries the classified emission."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.tenant.databricks_ml_assets_enabled = True
        self.tenant.save(update_fields=["databricks_ml_assets_enabled"])
        self.workspace = _make_workspace(self.tenant, name=f"ws-throt-{uuid.uuid4().hex[:8]}")
        self.actor = _make_user(
            self.tenant, f"throttle-view-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.client = _api_client(self.actor)

    @override_settings(CACHES=_LOCMEM_CACHES)
    def test_the_second_call_answers_429_with_the_audit_row(self):
        from unittest import mock

        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.throttles import MlAssetsRateThrottle

        patched_rates = mock.patch.object(
            MlAssetsRateThrottle,
            "THROTTLE_RATES",
            {"databricks_ml_assets": "1/min"},
        )
        patched_rates.start()
        self.addCleanup(patched_rates.stop)

        url = reverse("ml-asset-models", kwargs={"workspace_id": self.workspace.id})
        first = self.client.get(url)
        assert first.status_code == 200, first.json()
        second = self.client.get(url)
        assert second.status_code == 429, second.json()
        rows = list(
            AuditEvent.objects.filter(
                tenant=self.tenant, action="DATABRICKS_ML_RATE_LIMIT_EXCEEDED"
            )
        )
        assert len(rows) == 1, "the 429 path emits exactly one rate-limit row"
