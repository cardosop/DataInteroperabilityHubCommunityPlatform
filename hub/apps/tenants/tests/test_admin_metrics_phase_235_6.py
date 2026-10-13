"""
Phase 235.6 — Prometheus metrics for the PLATFORM_ADMIN surface.

Engineering contract this suite pins (REQ-ADMIN-METRICS-001):

1.  The pre-existing ``audit_events_total{action, resource_type, result}``
    counter (Phase 227 Wave 1) already covers every Phase 235 audit
    emission because the ``action`` label captures TENANT_CREATED /
    TENANT_SOFT_DELETED / TENANT_HARD_DELETED / IMPERSONATION_STARTED /
    IMPERSONATION_ENDED / IMPERSONATION_REJECTED / TENANT_FEATURE_FLAG_CHANGED /
    FEATURE_FLAG_FLIP_APPROVAL_REQUESTED / FEATURE_FLAG_FLIP_APPROVED.
    No new counter is needed for these — this test confirms the
    instrumentation is observable from the audit-utils path.

2.  NEW ``admin_dashboard_summary_cache_total{outcome}`` counter —
    incremented on every dashboard summary request with
    ``outcome="hit"`` or ``"miss"``. Drives the cache-hit-ratio
    Grafana panel and lets ops alert when the cache effectiveness
    drops below an SLO threshold (e.g. < 0.8 sustained over 1h).

3.  NEW ``admin_dashboard_summary_aggregate_duration_seconds``
    histogram — recorded on every cache-MISS aggregator run. Drives
    the dashboard build-latency Grafana panel and lets ops alert on
    P95 regressions (target P95 < 2s for the consolidated aggregate).

The metric primitives are the existing
``hub.apps.observability.otel_metrics`` wrappers — same pattern as
``audit_events_total`` (line 711 of otel_metrics.py).

Emission pins are REAL end-to-end (no test doubles): the counter
assertions read the wrapper's in-process prometheus-compat ``_value``
state (the repo's own convention — ``test_otel_metrics.py``), and the
histogram assertion points the wrappers' global meter at a REAL
in-memory OTel ``MeterProvider`` whose ``InMemoryMetricReader``
captures the actual data points the view records.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers (mirror the Phase 235.5 test file shape)
# ---------------------------------------------------------------------------


def _ensure_tenant_has_subscription(tenant: Tenant) -> None:
    from datetime import timedelta

    from django.utils import timezone

    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.tenants.models import PlanTier, TenantPlan

    if Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE).exists():
        return
    plan, _ = TenantPlan.objects.get_or_create(
        slug=f"test-plan-{tenant.slug}",
        defaults={
            "name": f"Test Plan {tenant.slug}",
            "tier": PlanTier.FREE,
            "limits_json": {"max_assets": 100},
            "is_active": True,
        },
    )
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=365),
    )


def _make_tenant(*, slug_suffix: str | None = None) -> Tenant:
    uid = slug_suffix or uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"Tenant {uid}", slug=f"tenant-{uid}")
    _ensure_tenant_has_subscription(tenant)
    return tenant


def _make_platform_admin() -> User:
    uid = uuid.uuid4().hex[:8]
    home_tenant = _make_tenant(slug_suffix=f"pa-home-{uid}")
    user = User.objects.create_user(
        email=f"pa-{uid}@example.com", password="testpass123", tenant=home_tenant
    )
    user.is_platform_admin = True
    user.save(update_fields=["is_platform_admin"])
    return user


def _dashboard_url() -> str:
    return "/api/v1/admin/dashboard/summary/"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Real-metric observation helpers
# ---------------------------------------------------------------------------


def _labeled_count(metric, **labels) -> float:
    """Read the wrapper's REAL in-process prometheus-compat value.

    The ``otel_metrics`` wrappers track each labeled inc() in-process
    (``_LabeledMetric._value._count``) regardless of the OTel backend —
    this is the same read ``hub.apps.observability.tests.test_otel_metrics``
    pins. Delta-assert against it for deterministic cross-test isolation.
    """
    return metric.labels(**labels)._value.get()


def _install_in_memory_otel_meter():
    """Point the wrappers' global meter at a REAL in-memory OTel SDK.

    This is not a test double — it is a real ``MeterProvider`` whose
    exporter is ``InMemoryMetricReader`` instead of the production
    Prometheus reader, so the actual data points the view records are
    observable. Returns ``(reader, old_meter, old_histogram)`` — pass
    the latter two to :func:`_restore_meter` after the assertions.
    """
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.resources import Resource

    from hub.apps.observability import otel_metrics

    reader = InMemoryMetricReader()
    provider = MeterProvider(
        resource=Resource.create({"service.name": "hub-test"}),
        metric_readers=[reader],
    )
    meter = provider.get_meter("hub-test")

    old_meter = otel_metrics._meter
    old_histogram = otel_metrics.admin_dashboard_summary_aggregate_duration_seconds._histogram
    otel_metrics._meter = meter
    # Force the wrapper to recreate its backend histogram against the
    # in-memory meter (it caches the backend on first observe()).
    otel_metrics.admin_dashboard_summary_aggregate_duration_seconds._histogram = None
    return reader, old_meter, old_histogram


def _restore_meter(old_meter, old_histogram) -> None:
    """Restore the wrappers' global meter state saved by ``_install_...``."""
    from hub.apps.observability import otel_metrics

    otel_metrics._meter = old_meter
    otel_metrics.admin_dashboard_summary_aggregate_duration_seconds._histogram = old_histogram


def _reader_metric_points(reader, metric_name: str):
    """Return the data points recorded for ``metric_name`` by the reader."""
    points = []
    for resource_metric in reader.get_metrics_data().resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            for metric in scope_metric.metrics:
                if metric.name == metric_name:
                    points.extend(metric.data.data_points)
    return points


# ---------------------------------------------------------------------------
# Tier 1 — Metric module exports the expected names
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMetricsModuleExports:
    """Pin the names + types of the new metric exports so a typo in a
    refactor breaks the import contract at test time rather than at
    Grafana-panel-load time."""

    @pytest.mark.integration
    def test_dashboard_cache_counter_exists(self):
        from hub.apps.observability.otel_metrics import (
            admin_dashboard_summary_cache_total,
        )

        # The wrapper exposes the prometheus-client-compatible name +
        # description + labels. Check the names + the outcome label.
        assert admin_dashboard_summary_cache_total.name == "admin_dashboard_summary_cache_total"
        assert "outcome" in admin_dashboard_summary_cache_total._expected_labels

    @pytest.mark.integration
    def test_dashboard_aggregate_duration_histogram_exists(self):
        from hub.apps.observability.otel_metrics import (
            admin_dashboard_summary_aggregate_duration_seconds,
        )

        assert (
            admin_dashboard_summary_aggregate_duration_seconds.name
            == "admin_dashboard_summary_aggregate_duration_seconds"
        )
        # No labels — global aggregator timing, not per-tenant.
        assert admin_dashboard_summary_aggregate_duration_seconds._expected_labels == ()
        # The buckets the 235.6 spec chose for the 12-COUNT aggregator.
        assert admin_dashboard_summary_aggregate_duration_seconds.buckets == (
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.0,
            5.0,
            10.0,
        )

    @pytest.mark.integration
    def test_audit_events_total_exists_with_expected_labels(self):
        """Spec 235.6.1 — the pre-existing audit counter covers every
        Phase 235 emission because its label set is (action,
        resource_type, result)."""
        from hub.apps.observability.otel_metrics import audit_events_total

        assert audit_events_total.name == "audit_events_total"
        for label in ("action", "resource_type", "result"):
            assert label in audit_events_total._expected_labels


# ---------------------------------------------------------------------------
# Tier 2 — Dashboard endpoint emits the new metrics
# ---------------------------------------------------------------------------


class TestDashboardMetricsEmission:
    """Confirms the dashboard endpoint actually calls the metric wrappers.

    REAL end-to-end: the counter assertions delta-read the wrapper's
    in-process prometheus-compat ``_value`` before/after the request;
    the histogram assertion reads the data points from a real
    in-memory OTel reader installed via ``_in_memory_otel_meter``.
    """

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.admin = _make_platform_admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @pytest.mark.integration
    def test_cache_miss_increments_cache_counter_with_miss_label(self):
        """First request after a cache.clear() — cache miss path."""
        from hub.apps.observability.otel_metrics import (
            admin_dashboard_summary_cache_total,
        )

        before = _labeled_count(admin_dashboard_summary_cache_total, outcome="miss")

        resp = self.client.get(_dashboard_url())
        assert resp.status_code == status.HTTP_200_OK, resp.content
        assert not resp.json().get("cache_hit")

        assert _labeled_count(admin_dashboard_summary_cache_total, outcome="miss") == before + 1

    @pytest.mark.integration
    def test_cache_hit_increments_cache_counter_with_hit_label(self):
        """Second request within the TTL — cache hit path."""
        from hub.apps.observability.otel_metrics import (
            admin_dashboard_summary_cache_total,
        )

        # Prime the cache (cache miss).
        resp1 = self.client.get(_dashboard_url())
        assert not resp1.json().get("cache_hit")

        before = _labeled_count(admin_dashboard_summary_cache_total, outcome="hit")

        resp2 = self.client.get(_dashboard_url())
        assert resp2.status_code == status.HTTP_200_OK, resp2.content
        assert resp2.json().get("cache_hit")

        assert _labeled_count(admin_dashboard_summary_cache_total, outcome="hit") == before + 1

    @pytest.mark.integration
    def test_cache_miss_records_aggregate_duration(self):
        """Cache miss path records a duration sample on the histogram.

        Cache hit path MUST NOT record (the aggregator did not run)."""
        reader, old_meter, old_histogram = _install_in_memory_otel_meter()
        try:
            # First request — cache miss, expect exactly 1 observation.
            resp1 = self.client.get(_dashboard_url())
            assert resp1.status_code == status.HTTP_200_OK, resp1.content
            miss_points = _reader_metric_points(
                reader, "admin_dashboard_summary_aggregate_duration_seconds"
            )
            assert len(miss_points) == 1, f"expected 1 histogram point, got {len(miss_points)}"
            assert miss_points[0].count == 1
            assert miss_points[0].sum > 0  # some positive duration in seconds

            # Second request — cache hit, MUST NOT observe.
            resp2 = self.client.get(_dashboard_url())
            assert resp2.status_code == status.HTTP_200_OK, resp2.content
            assert resp2.json().get("cache_hit")
            after_points = _reader_metric_points(
                reader, "admin_dashboard_summary_aggregate_duration_seconds"
            )
            assert len(after_points) == 1, (
                "cache-hit path must NOT record on the aggregator histogram"
            )
            assert after_points[0].count == 1
        finally:
            _restore_meter(old_meter, old_histogram)


# ---------------------------------------------------------------------------
# Tier 3 — audit_events_total covers Phase 235 audit-event types
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuditEventsTotalCoversPhase235:
    """Every Phase 235 audit-emit goes through ``create_audit_event``
    (hub/apps/audit/utils.py:258+), which emits the existing
    ``audit_events_total{action, resource_type, result}`` counter
    AS A SIDE EFFECT of the row creation (otel_metrics.py:711).

    This test pins that every action constant listed in spec 235.6.1
    is queryable via the existing counter (i.e., the action label is
    exactly the action constant). A future refactor that decoupled
    the audit row from the metric emit would break this test.
    """

    PHASE_235_ACTIONS: tuple[str, ...] = (
        "TENANT_CREATED",
        "TENANT_SOFT_DELETED",
        "TENANT_HARD_DELETED",
        "TENANT_FEATURE_FLAG_CHANGED",
        "IMPERSONATION_STARTED",
        "IMPERSONATION_ENDED",
        "IMPERSONATION_REJECTED",
        "FEATURE_FLAG_FLIP_APPROVAL_REQUESTED",
        "FEATURE_FLAG_FLIP_APPROVED",
    )

    @pytest.mark.integration
    def test_every_phase_235_constant_is_a_string(self):
        """The action constants land in the metric's ``action`` label
        as-is; a None / int / enum value would break the Prometheus
        ingester. Pin all 9 constants are str."""
        from hub.apps.audit import event_types as _audit_et

        for action in self.PHASE_235_ACTIONS:
            value = getattr(_audit_et, action)
            assert isinstance(value, str), f"{action} must be str, got {type(value)}"
            assert value == action, (
                f"{action} constant value drifted from its name "
                f"(value={value!r}). Audit-replay queries break when "
                f"name != value."
            )

    @pytest.mark.integration
    def test_create_audit_event_increments_audit_events_total(self):
        """The audit-emit path increments ``audit_events_total`` with the
        action constant in the label — exercised end-to-end via a real
        ``create_audit_event`` call, delta-read from the wrapper's real
        in-process value."""
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.observability.otel_metrics import audit_events_total

        labels = {
            "action": "TENANT_CREATED",
            "resource_type": "TENANT",
            "result": "SUCCESS",
        }
        before = _labeled_count(audit_events_total, **labels)

        tenant = _make_tenant()
        create_audit_event(
            resource_type="TENANT",
            action="TENANT_CREATED",
            tenant=tenant,
            resource_id=str(tenant.id),
            result="SUCCESS",
            details={"slug": tenant.slug},
            infer_tenant_from_actor=False,
        )

        assert _labeled_count(audit_events_total, **labels) == before + 1
