"""
Phase 235.5 — Single consolidated PLATFORM_ADMIN dashboard summary endpoint.

Engineering contract this suite pins (REQ-ADMIN-DASHBOARD-001 in
``openspec/changes/preprod01/specs/admin-tenant-lifecycle/spec.md`` —
the dashboard is part of the broader admin-lifecycle surface):

1.  ``GET /api/v1/admin/dashboard/summary/`` is PLATFORM_ADMIN-only via
    ``IsPlatformAdmin``; TENANT_ADMIN → 403; unauthenticated → 401/403.

2.  Response shape carries six widget blocks (matches the 235.5 spec's
    six widget cards plus a top-level ``generated_at`` ISO-8601
    timestamp + ``cache_ttl_seconds`` so the SPA can decide whether
    to refresh).

3.  Each widget summarises a distinct subsystem:

    * ``tenants``       — total / active / suspended / deleted /
                          legal_hold / scheduled_for_deletion counts.
    * ``webhooks``      — total / active / paused + delivery health
                          (last-24h success, failed, dead-letter,
                          rate-limited).
    * ``audit``         — events written in the last 24h, integrity
                          verified-at timestamp (when present), and
                          a tamper-mismatch count.
    * ``compliance``    — pending / running / succeeded-last-24h /
                          failed-last-24h.
    * ``billing``       — active subscription count + counts by
                          status (PAST_DUE, CANCELED, TRIAL, …).
    * ``governance``    — open access-requests by status + open
                          DSARs (when feature enabled).

4.  **5-minute server-side cache** — repeat calls within 5 minutes
    return the SAME cached payload. The endpoint reports
    ``cache_hit: true`` on the second call (the source-of-truth ground
    test for the cache contract).

5.  Cache invalidation: cache TTL alone is the source of refresh.
    No model-level invalidation hook is required for 235.5 — operators
    accept up to 5-minutes of dashboard staleness in exchange for a
    cheaper aggregate query.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "admin"])
User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant(*, slug_suffix: str | None = None, status_value=TenantStatus.ACTIVE) -> Tenant:
    uid = slug_suffix or uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status=status_value,
    )


def _make_platform_admin(*, tenant: Tenant | None = None) -> User:
    uid = uuid.uuid4().hex[:8]
    home_tenant = tenant or _make_tenant(slug_suffix=f"pa-home-{uid}")
    user = User.objects.create_user(
        email=f"pa-{uid}@example.com", password="testpass123", tenant=home_tenant
    )
    user.is_platform_admin = True
    user.save(update_fields=["is_platform_admin"])
    return user


def _make_regular_user(tenant: Tenant) -> User:
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"u-{uid}@example.com", password="testpass123", tenant=tenant
    )


def _url() -> str:
    return "/api/v1/admin/dashboard/summary/"


@pytest.fixture(autouse=True)
def _clear_dashboard_cache():
    """Clear Django's cache between tests so cache_hit contracts are deterministic."""
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Tier 1 — permission gating
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDashboardSummaryPermissions:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.client = APIClient()

    @pytest.mark.integration
    def test_unauthenticated_blocked(self):
        resp = self.client.get(_url())
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.integration
    def test_tenant_admin_blocked(self):
        tenant = _make_tenant()
        regular = _make_regular_user(tenant)
        self.client.force_authenticate(regular)
        resp = self.client.get(_url())
        assert (
            resp.status_code == status.HTTP_403_FORBIDDEN
        )  # ---------------------------------------------------------------------------)


# Tier 2 — Response shape (PLATFORM_ADMIN happy path, empty state)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDashboardSummaryShape:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.admin = _make_platform_admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @pytest.mark.integration
    def test_response_carries_six_widget_blocks(self):
        resp = self.client.get(_url())
        assert resp.status_code == status.HTTP_200_OK, resp.content
        body = resp.json()
        assert "generated_at" in body
        assert "cache_ttl_seconds" in body
        assert body["cache_ttl_seconds"] == 300  # 5 minutes)
        assert "cache_hit" in body
        for widget_key in (
            "tenants",
            "webhooks",
            "audit",
            "compliance",
            "billing",
            "governance",
        ):
            assert widget_key in body, f"missing widget: {widget_key}"

    @pytest.mark.integration
    def test_tenants_widget_has_required_keys(self):
        resp = self.client.get(_url())
        widget = resp.json()["tenants"]
        for k in (
            "total",
            "active",
            "suspended",
            "deleted",
            "legal_hold",
            "scheduled_for_deletion",
        ):
            assert k in widget, f"tenants widget missing: {k}"

    @pytest.mark.integration
    def test_webhooks_widget_has_required_keys(self):
        resp = self.client.get(_url())
        widget = resp.json()["webhooks"]
        for k in ("total", "active", "paused"):
            assert k in widget
        delivery_health = widget.get("delivery_health_last_24h", {})
        for k in ("success", "failed", "dead_letter", "rate_limited"):
            assert k in delivery_health

    @pytest.mark.integration
    def test_audit_widget_has_required_keys(self):
        resp = self.client.get(_url())
        widget = resp.json()["audit"]
        for k in ("events_last_24h", "integrity_mismatch_count", "integrity_verified_at"):
            assert k in widget

    @pytest.mark.integration
    def test_compliance_widget_has_required_keys(self):
        resp = self.client.get(_url())
        widget = resp.json()["compliance"]
        for k in ("pending", "running", "succeeded_last_24h", "failed_last_24h"):
            assert k in widget

    @pytest.mark.integration
    def test_billing_widget_has_required_keys(self):
        resp = self.client.get(_url())
        widget = resp.json()["billing"]
        for k in ("active", "past_due", "canceled", "trial"):
            assert k in widget

    @pytest.mark.integration
    def test_governance_widget_has_required_keys(self):
        resp = self.client.get(_url())
        widget = resp.json()["governance"]
        for k in ("open_access_requests", "approved_access_requests"):
            assert k in widget


# ---------------------------------------------------------------------------
# Tier 3 — Widgets reflect seeded data (happy path)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDashboardSummaryReflectsSeededData:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.admin = _make_platform_admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @pytest.mark.integration
    def test_tenants_widget_counts_active_vs_suspended(self):
        _make_tenant(status_value=TenantStatus.ACTIVE)
        _make_tenant(status_value=TenantStatus.ACTIVE)
        _make_tenant(status_value=TenantStatus.SUSPENDED)
        resp = self.client.get(_url())
        widget = resp.json()["tenants"]
        # The PLATFORM_ADMIN's home tenant + the three above + setup
        # extras count toward `total`, so we assert on monotonic
        # invariants rather than exact totals.
        assert widget["active"] >= 2
        assert widget["suspended"] >= 1

    @pytest.mark.integration
    def test_tenants_widget_counts_legal_hold(self):
        t = _make_tenant()
        t.legal_hold = True
        t.save(update_fields=["legal_hold"])
        resp = self.client.get(_url())
        assert resp.json()["tenants"]["legal_hold"] >= 1

    @pytest.mark.integration
    def test_tenants_widget_counts_scheduled_for_deletion(self):
        t = _make_tenant()
        t.scheduled_for_deletion_at = timezone.now()
        t.save(update_fields=["scheduled_for_deletion_at"])
        resp = self.client.get(_url())
        assert resp.json()["tenants"]["scheduled_for_deletion"] >= 1

    @pytest.mark.integration
    def test_webhooks_widget_counts_active_and_paused(self):
        from hub.apps.webhooks.models import Webhook, WebhookStatus

        tenant = _make_tenant()
        Webhook.objects.create(
            tenant=tenant,
            name="wh-1",
            url="https://example.com/wh-1",
            secret="x" * 32,
            event_types=["asset.created"],
            status=WebhookStatus.ACTIVE,
        )
        Webhook.objects.create(
            tenant=tenant,
            name="wh-2",
            url="https://example.com/wh-2",
            secret="x" * 32,
            event_types=["asset.created"],
            status=WebhookStatus.PAUSED,
        )
        resp = self.client.get(_url())
        widget = resp.json()["webhooks"]
        assert widget["total"] >= 2
        assert widget["active"] >= 1
        assert widget["paused"] >= 1

    @pytest.mark.integration
    def test_audit_widget_counts_recent_events(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _make_tenant()
        AuditEvent.objects.create(
            tenant=tenant,
            resource_type="ASSET",
            action="ASSET_CREATED",
            result="SUCCESS",
        )
        resp = self.client.get(_url())
        assert resp.json()["audit"]["events_last_24h"] >= 1

    @pytest.mark.integration
    def test_compliance_widget_counts_runs(self):
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        from hub.apps.jobs.models import Job, JobType

        tenant = _make_tenant()
        # ComplianceRun.clean() requires at least one of asset/dataset/file
        asset = Asset.objects.create(
            tenant=tenant,
            name="dashboard-cr-asset",
            key=f"dash-cr-{uuid.uuid4().hex[:8]}",
            status=AssetStatus.ACTIVE,
        )
        job = Job.objects.create(
            tenant=tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET",
            resource_id=asset.id,
        )
        ComplianceRun.objects.create(
            tenant=tenant,
            job=job,
            asset=asset,
            status=ComplianceRunStatus.PENDING,
            regulations=["GDPR"],
        )
        job2 = Job.objects.create(
            tenant=tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET",
            resource_id=asset.id,
        )
        ComplianceRun.objects.create(
            tenant=tenant,
            job=job2,
            asset=asset,
            status=ComplianceRunStatus.RUNNING,
            regulations=["GDPR"],
        )
        resp = self.client.get(_url())
        widget = resp.json()["compliance"]
        assert widget["pending"] >= 1
        assert widget["running"] >= 1

    @pytest.mark.integration
    def test_billing_widget_counts_active_subscriptions(self):
        from hub.apps.billing.models import Subscription, SubscriptionStatus
        from hub.apps.tenants.models import TenantPlan

        tenant = _make_tenant()
        _plan_uid = uuid.uuid4().hex[:8]
        plan, _ = TenantPlan.objects.get_or_create(
            slug=f"dashboard-plan-{_plan_uid}",
            defaults={
                "name": f"Dashboard Test Plan {_plan_uid}",
                "tier": "FREE",
                "limits_json": {"max_assets": 100},
                "is_active": True,
            },
        )
        Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:12]}",
            status=SubscriptionStatus.ACTIVE,
        )
        Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:12]}",
            status=SubscriptionStatus.PAST_DUE,
        )
        resp = self.client.get(_url())
        widget = resp.json()["billing"]
        assert widget["active"] >= 1
        assert widget["past_due"] >= 1

    @pytest.mark.integration
    def test_governance_widget_counts_access_requests(self):
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.governance.models import AccessRequest, AccessRequestStatus

        tenant = _make_tenant()
        # AccessRequest.clean() requires at least one of asset/dataset/file
        asset = Asset.objects.create(
            tenant=tenant,
            name="dashboard-gov-asset",
            key=f"dash-gov-{uuid.uuid4().hex[:8]}",
            status=AssetStatus.ACTIVE,
        )
        requester = _make_regular_user(tenant)
        AccessRequest.objects.create(
            tenant=tenant,
            requested_by=requester,
            asset=asset,
            reason="testing",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )
        AccessRequest.objects.create(
            tenant=tenant,
            requested_by=requester,
            asset=asset,
            reason="testing",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
        )
        resp = self.client.get(_url())
        widget = resp.json()["governance"]
        assert widget["open_access_requests"] >= 1
        assert widget["approved_access_requests"] >= 1


# ---------------------------------------------------------------------------
# Tier 4 — Cache contract (5-minute TTL, source-of-truth test)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDashboardSummaryCache:
    """Spec 235.5.9 + 235.5.10 — the second call within the TTL window
    MUST return the cached payload (``cache_hit=true``). A counter-
    increment between the two calls MUST NOT show up in the cached
    response (proves the aggregator did NOT re-run)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.admin = _make_platform_admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @pytest.mark.integration
    def test_second_call_within_ttl_returns_cache_hit(self):
        resp1 = self.client.get(_url())
        assert resp1.status_code == status.HTTP_200_OK
        assert not resp1.json().get("cache_hit")

        resp2 = self.client.get(_url())
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.json().get("cache_hit")

    @pytest.mark.integration
    def test_cache_hit_avoids_regeneration(self):
        """If the cache hit is real, mutations between the two calls
        do NOT show up in the cached payload — proves the aggregator
        was skipped on the second call."""
        resp1 = self.client.get(_url())
        baseline_total = resp1.json()["tenants"]["total"]
        # Mutation: create a fresh tenant AFTER the first call.
        _make_tenant()
        resp2 = self.client.get(_url())
        # Cache hit means the second response equals the first,
        # NOT reflecting the newly created tenant.
        assert resp2.json().get("cache_hit")
        assert resp2.json()["tenants"]["total"] == baseline_total

    @pytest.mark.integration
    def test_cache_clear_forces_regeneration(self):
        """Operators can force a refresh by clearing the cache key."""
        resp1 = self.client.get(_url())
        baseline_total = resp1.json()["tenants"]["total"]
        _make_tenant()
        cache.clear()
        resp3 = self.client.get(_url())
        # Fresh aggregator run picks up the new tenant.
        assert not resp3.json().get("cache_hit")
        assert resp3.json()["tenants"]["total"] == baseline_total + 1

    @pytest.mark.integration
    def test_force_refresh_query_param_bypasses_cache(self):
        """``?refresh=true`` re-runs the aggregator even within the TTL
        window. Useful for the SPA's manual refresh button + for
        operators investigating mid-incident."""
        resp1 = self.client.get(_url())
        assert not resp1.json().get("cache_hit")
        resp2 = self.client.get(_url())
        assert resp2.json().get("cache_hit")
        resp3 = self.client.get(f"{_url()}?refresh=true")
        # The refresh bypassed the cache and re-aggregated.
        assert not resp3.json().get("cache_hit")


# ---------------------------------------------------------------------------
# Tier 5 — Phase 235.5 audit-fix Gap 2: widget-level error isolation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDashboardWidgetErrorIsolation:
    """Phase 235.5 audit-fix Gap 2 — when ONE aggregator raises, the
    other five widgets MUST still render real data and the failing
    widget gets a ``{"widget_error": true}`` sentinel payload.

    The whole point of the consolidated dashboard is operator
    visibility, so a single-table outage (schema drift, slow query
    timeout, Postgres replica lag) must NOT take down the entire
    surface.
    """

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.admin = _make_platform_admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @pytest.mark.integration
    def test_single_widget_failure_returns_sentinel_others_intact(self, monkeypatch):
        """Force ``_aggregate_compliance`` to raise; the response must
        still 200 OK with five real widgets + one sentinel block."""
        from hub.apps.tenants import admin_dashboard_summary as mod

        def _boom(**_kwargs):
            raise RuntimeError("simulated compliance-table outage")

        monkeypatch.setattr(mod, "_aggregate_compliance", _boom)

        resp = self.client.get(_url())
        assert resp.status_code == status.HTTP_200_OK, resp.content
        body = resp.json()
        # Other five widgets returned real data (a top-level required
        # key surfaces in the dict).
        assert "total" in body["tenants"]
        assert "total" in body["webhooks"]
        assert "events_last_24h" in body["audit"]
        assert "active" in body["billing"]
        assert "open_access_requests" in body["governance"]
        # The compliance widget returned the sentinel — the SPA renders
        # an inline error banner just for that widget.
        assert body["compliance"] == {"widget_error": True}

    @pytest.mark.integration
    def test_response_carries_cache_control_header(self):
        """Phase 235.5 audit-fix Gap 5 — browser-side dedup."""
        resp = self.client.get(_url())
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers.get("Cache-Control") == "private, max-age=60"
