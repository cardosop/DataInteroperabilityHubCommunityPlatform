"""
Phase 235.5 — PLATFORM_ADMIN consolidated dashboard summary endpoint.

Mounts at ``GET /api/v1/admin/dashboard/summary/`` (registered in
``hub/apps/tenants/admin_urls.py``). Returns a single aggregate
payload that drives six widget cards on the SPA's
``AdminPage.tsx`` Overview tab:

* ``tenants``    — total / active / suspended / deleted / legal_hold /
                   scheduled_for_deletion counts.
* ``webhooks``   — total / active / paused + 24h delivery health.
* ``audit``      — events written in last 24h + integrity verifier
                   beacon (verified_at, mismatch_count).
* ``compliance`` — pending / running counts + 24h success/fail.
* ``billing``    — subscription counts by status.
* ``governance`` — open / approved access-requests counts.

Cache contract
==============

Server-side 5-minute cache via ``django.core.cache`` under the key
``"admin_dashboard_summary:v1"``. ``cache_hit`` in the response body
is the source-of-truth signal for whether the aggregate ran. The
``?refresh=true`` query parameter bypasses the cache (used by the
SPA's manual refresh button + ops mid-incident).

No model-level invalidation hooks are wired for 235.5 — operators
accept up to 5 minutes of dashboard staleness in exchange for the
cheaper aggregate query. A future 235.5.x can revisit when traffic
patterns demand sub-5-minute freshness.

Performance characteristics
===========================

The aggregator runs ~12 COUNT queries against indexed status
columns. Every query uses the ``admin`` BYPASSRLS connection alias
(cross-tenant by definition — this is a platform-admin surface and
the same pattern Phase 235.1 / 235.2 / 235.3 use). The cache key is
NOT tenant-scoped because the dashboard itself is global.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsPlatformAdmin

logger = logging.getLogger(__name__)

CACHE_KEY: str = "admin_dashboard_summary:v1"
CACHE_TTL_SECONDS: int = 300  # 5 minutes per spec 235.5.9

# Phase 235.5 audit-fix Gap 2 — sentinel returned when a single
# aggregator throws so the rest of the dashboard still renders. Audit
# emitters / log scrapers can grep for ``"widget_error"`` and a
# corresponding ``admin_dashboard_widget_failed`` log line.
_WIDGET_ERROR_SENTINEL: dict[str, Any] = {"widget_error": True}


# ---------------------------------------------------------------------------
# Aggregators (per-widget)
# ---------------------------------------------------------------------------


def _aggregate_tenants() -> dict[str, Any]:
    """Counts derived from ``Tenant.all_objects`` so soft-deleted rows
    are included (the deleted-tenant count is itself part of the
    dashboard signal).

    Phase 235.5 audit-fix Gap 3 — six per-status COUNT queries were
    consolidated into ONE ``aggregate()`` call using ``Count(filter=Q(...))``
    annotations. Each branch becomes a Postgres ``COUNT(*) FILTER (WHERE ...)``
    inside a single SELECT, which is both faster (one round-trip) and
    snapshot-consistent (all counters observe the SAME row visibility).
    """
    from .models import Tenant, TenantStatus

    qs = Tenant.all_objects.using("admin")
    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=TenantStatus.ACTIVE)),
        suspended=Count("id", filter=Q(status=TenantStatus.SUSPENDED)),
        deleted=Count("id", filter=Q(status=TenantStatus.DELETED)),
        legal_hold=Count("id", filter=Q(legal_hold=True)),
        scheduled_for_deletion=Count("id", filter=Q(scheduled_for_deletion_at__isnull=False)),
    )
    return {
        "total": counts["total"],
        "active": counts["active"],
        "suspended": counts["suspended"],
        "deleted": counts["deleted"],
        "legal_hold": counts["legal_hold"],
        "scheduled_for_deletion": counts["scheduled_for_deletion"],
    }


def _aggregate_webhooks(*, since_24h) -> dict[str, Any]:
    """Webhook subscription counts + 24h delivery-health breakdown.

    Two ``aggregate()`` calls — one for ``Webhook`` (subscription
    counts), one for ``WebhookDelivery`` (delivery health). Total: 2
    queries vs the prior 8. Phase 235.5 audit-fix Gap 3.
    """
    from hub.apps.webhooks.models import (
        DeliveryStatus,
        Webhook,
        WebhookDelivery,
        WebhookStatus,
    )

    sub_counts = Webhook.objects.using("admin").aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=WebhookStatus.ACTIVE)),
        paused=Count("id", filter=Q(status=WebhookStatus.PAUSED)),
        disabled=Count("id", filter=Q(status=WebhookStatus.DISABLED)),
    )
    dh = (
        WebhookDelivery.objects.using("admin")
        .filter(created_at__gte=since_24h)
        .aggregate(
            success=Count("id", filter=Q(status=DeliveryStatus.SUCCESS)),
            failed=Count("id", filter=Q(status=DeliveryStatus.FAILED)),
            dead_letter=Count("id", filter=Q(status=DeliveryStatus.DEAD_LETTER)),
            rate_limited=Count("id", filter=Q(status=DeliveryStatus.RATE_LIMITED)),
        )
    )
    return {
        "total": sub_counts["total"],
        "active": sub_counts["active"],
        "paused": sub_counts["paused"],
        "disabled": sub_counts["disabled"],
        "delivery_health_last_24h": dh,
    }


def _aggregate_audit(*, since_24h) -> dict[str, Any]:
    """Audit-event counts + tamper-integrity beacon.

    ``integrity_verified_at`` is the most recent ``AUDIT_INTEGRITY_VERIFIED``
    event globally — the operator's signal that the chain-integrity
    verifier ran and PASSED. ``integrity_mismatch_count`` is the
    number of mismatches in the last 24h — non-zero is a PagerDuty
    page (per ``event_types.AUDIT_INTEGRITY_MISMATCH`` docs).

    Phase 235.5 audit-fix Gap 3 — the two counts collapse into one
    ``aggregate()`` over the last-24h window; the ``latest_verified``
    lookup stays as a separate query because it scans the all-time
    window (a different filter shape) — joining them into the same
    aggregate would force the optimizer to scan the whole table.
    """
    from hub.apps.audit import event_types as _audit_et
    from hub.apps.audit.models import AuditEvent

    qs = AuditEvent.objects.using("admin")
    last_24h = qs.filter(timestamp__gte=since_24h).aggregate(
        events_last_24h=Count("id"),
        integrity_mismatch_count=Count("id", filter=Q(action=_audit_et.AUDIT_INTEGRITY_MISMATCH)),
    )
    latest_verified = (
        qs.filter(action=_audit_et.AUDIT_INTEGRITY_VERIFIED)
        .order_by("-timestamp")
        .values_list("timestamp", flat=True)
        .first()
    )
    return {
        "events_last_24h": last_24h["events_last_24h"],
        "integrity_mismatch_count": last_24h["integrity_mismatch_count"],
        "integrity_verified_at": (latest_verified.isoformat() if latest_verified else None),
    }


def _aggregate_compliance(*, since_24h) -> dict[str, Any]:
    """Compliance-run lifecycle counts. ``pending`` + ``running``
    are *in-flight*; the 24h windows are *terminal* counts.

    Phase 235.5 audit-fix Gap 3 — four COUNTs collapse to one
    ``aggregate()`` call.
    """
    from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus

    counts = ComplianceRun.objects.using("admin").aggregate(
        pending=Count("id", filter=Q(status=ComplianceRunStatus.PENDING)),
        running=Count("id", filter=Q(status=ComplianceRunStatus.RUNNING)),
        succeeded_last_24h=Count(
            "id",
            filter=Q(
                status=ComplianceRunStatus.SUCCEEDED,
                updated_at__gte=since_24h,
            ),
        ),
        failed_last_24h=Count(
            "id",
            filter=Q(
                status=ComplianceRunStatus.FAILED,
                updated_at__gte=since_24h,
            ),
        ),
    )
    return counts


def _aggregate_billing() -> dict[str, Any]:
    """Subscription counts by status + plan distribution by tier
    (285.13.12.8).

    Surfaces revenue-health drift (a spike in PAST_DUE or UNPAID) and
    plan-tier distribution so ops can see how many tenants are on FREE
    vs PRO vs ENTERPRISE.
    """
    from hub.apps.billing.models import Subscription, SubscriptionStatus

    status_counts = Subscription.objects.using("admin").aggregate(
        active=Count("id", filter=Q(status=SubscriptionStatus.ACTIVE)),
        past_due=Count("id", filter=Q(status=SubscriptionStatus.PAST_DUE)),
        canceled=Count("id", filter=Q(status=SubscriptionStatus.CANCELED)),
        trial=Count("id", filter=Q(status=SubscriptionStatus.TRIAL)),
        incomplete=Count("id", filter=Q(status=SubscriptionStatus.INCOMPLETE)),
        unpaid=Count("id", filter=Q(status=SubscriptionStatus.UNPAID)),
    )

    # 285.13.12.8 — Plan distribution by tier (FREE/PRO/ENTERPRISE)
    active_subs = Subscription.objects.using("admin").filter(
        status__in=[
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIAL,
        ],
    )
    plan_distribution = (
        active_subs.values("plan__tier")
        .annotate(
            count=Count("id"),
        )
        .order_by("plan__tier")
    )
    by_tier = {row["plan__tier"]: row["count"] for row in plan_distribution}

    return {
        **status_counts,
        "plan_distribution": {
            "by_tier": by_tier,
            "total_active": sum(by_tier.values()),
        },
    }


def _aggregate_governance() -> dict[str, Any]:
    """Open + approved access-requests across all tenants. DSAR counts
    intentionally omitted from 235.5 — the DSAR feature is per-tenant
    opt-in (``Tenant.compliance_dsar_enabled``) and the cross-tenant
    aggregate would mix tenants who opted out (always-zero) with
    tenants who opted in, leaving the operator unable to read the
    signal. Future 235.5.x can split per-tenant when an operator
    asks.

    Phase 235.5 audit-fix Gap 3 — three COUNTs collapse to one.
    """
    from hub.apps.governance.models import AccessRequest, AccessRequestStatus

    counts = AccessRequest.objects.using("admin").aggregate(
        open_access_requests=Count("id", filter=Q(status=AccessRequestStatus.PENDING)),
        approved_access_requests=Count("id", filter=Q(status=AccessRequestStatus.APPROVED)),
        rejected_access_requests=Count("id", filter=Q(status=AccessRequestStatus.REJECTED)),
    )
    return counts


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _run_widget(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Phase 235.5 audit-fix Gap 2 — run a single widget aggregator
    with per-widget error isolation.

    A single bad aggregator (model schema drift on one app, a missing
    index causing query timeout, a Postgres outage on one table) must
    NOT take down the entire dashboard — the whole point of the
    consolidated view is operator visibility, so partial visibility
    beats total blackout. On exception, we log a structured failure
    line and return a sentinel ``{"widget_error": true}`` payload so
    the SPA can render an inline error banner just for that widget.

    The timing is captured even on the failure path so a slow-failure
    aggregator (timeout) shows up in the telemetry alongside fast
    failures (NameError after a refactor).
    """
    started = time.monotonic()
    try:
        result = fn()
        duration_ms = (time.monotonic() - started) * 1000
        logger.debug(
            "admin_dashboard_widget_ok",
            extra={"widget": name, "duration_ms": round(duration_ms, 2)},
        )
        return result
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000
        logger.exception(
            "admin_dashboard_widget_failed",
            extra={
                "widget": name,
                "duration_ms": round(duration_ms, 2),
                "error": str(exc),
            },
        )
        return dict(_WIDGET_ERROR_SENTINEL)


def build_dashboard_summary() -> dict[str, Any]:
    """Aggregate the six widget blocks.

    Pure function — no caching, no request context. The caller (the
    DRF view) is responsible for the cache lookup + write.

    Each widget runs under per-widget error isolation (audit-fix
    Gap 2): if ``_aggregate_compliance`` throws, the other five
    widgets still render with real data and the compliance widget
    gets a sentinel ``{"widget_error": true}`` value. Total endpoint
    failure (5xx) only happens if the orchestrator itself crashes
    BEFORE delegating to a widget — which would be a Django setup
    issue, not a per-widget data-availability issue.
    """
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    return {
        "generated_at": now.isoformat(),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "tenants": _run_widget("tenants", _aggregate_tenants),
        "webhooks": _run_widget("webhooks", lambda: _aggregate_webhooks(since_24h=since_24h)),
        "audit": _run_widget("audit", lambda: _aggregate_audit(since_24h=since_24h)),
        "compliance": _run_widget("compliance", lambda: _aggregate_compliance(since_24h=since_24h)),
        "billing": _run_widget("billing", _aggregate_billing),
        "governance": _run_widget("governance", _aggregate_governance),
    }


# ---------------------------------------------------------------------------
# DRF view
# ---------------------------------------------------------------------------


class AdminDashboardSummaryView(APIView):
    """PLATFORM_ADMIN dashboard-summary endpoint.

    Cache contract
    --------------
    Aggregates are cached under ``CACHE_KEY`` for ``CACHE_TTL_SECONDS``.
    A request within the TTL receives the cached payload with
    ``cache_hit=true``. A request that bypasses the cache via
    ``?refresh=true`` re-runs the aggregator and replaces the cache
    entry.
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    @extend_schema(
        operation_id="admin_dashboard_summary",
        summary="Get the consolidated PLATFORM_ADMIN dashboard summary",
        description=(
            "Returns the aggregate payload that drives the six widget "
            "cards on the SPA Admin Overview tab (tenants / webhooks / "
            "audit / compliance / billing / governance). Cached server-"
            "side for 5 minutes; pass ``?refresh=true`` to force a "
            "re-aggregation. The ``cache_hit`` field discriminates "
            "between a fresh aggregator run and a cache replay. Per-"
            "widget error isolation: a single failing aggregator "
            'returns ``{"widget_error": true}`` for that widget while '
            "the other five render real data."
        ),
        parameters=[
            OpenApiParameter(
                name="refresh",
                type=bool,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "When true, bypasses the 5-minute server cache and "
                    "forces a fresh aggregator run. Used by the SPA's "
                    "manual refresh button and by ops mid-incident. "
                    "Subject to the platform's standard rate-limit "
                    "middleware."
                ),
            ),
        ],
        responses={
            200: OpenApiResponse(
                description=(
                    "Aggregate payload with six widget blocks. ``cache_hit`` "
                    "is true when the response was served from the 5-minute "
                    "server-side cache."
                ),
                examples=[
                    OpenApiExample(
                        "fresh aggregation",
                        value={
                            "generated_at": "2026-05-11T10:00:00Z",
                            "cache_ttl_seconds": 300,
                            "cache_hit": False,
                            "tenants": {
                                "total": 42,
                                "active": 38,
                                "suspended": 1,
                                "deleted": 3,
                                "legal_hold": 1,
                                "scheduled_for_deletion": 2,
                            },
                            "webhooks": {
                                "total": 18,
                                "active": 15,
                                "paused": 2,
                                "disabled": 1,
                                "delivery_health_last_24h": {
                                    "success": 1023,
                                    "failed": 4,
                                    "dead_letter": 1,
                                    "rate_limited": 0,
                                },
                            },
                            "audit": {
                                "events_last_24h": 12450,
                                "integrity_mismatch_count": 0,
                                "integrity_verified_at": "2026-05-11T09:30:00Z",
                            },
                            "compliance": {
                                "pending": 2,
                                "running": 1,
                                "succeeded_last_24h": 47,
                                "failed_last_24h": 0,
                            },
                            "billing": {
                                "active": 35,
                                "past_due": 1,
                                "canceled": 3,
                                "trial": 2,
                                "incomplete": 0,
                                "unpaid": 0,
                                "plan_distribution": {
                                    "by_tier": {"FREE": 10, "PRO": 20, "ENTERPRISE": 7},
                                    "total_active": 37,
                                },
                            },
                            "governance": {
                                "open_access_requests": 5,
                                "approved_access_requests": 120,
                                "rejected_access_requests": 8,
                            },
                        },
                    ),
                ],
            ),
            401: OpenApiResponse(
                description="Unauthorized — missing or invalid bearer token.",
            ),
            403: OpenApiResponse(
                description=(
                    "Forbidden — caller is not a PLATFORM_ADMIN. The "
                    "endpoint is platform-admin-only."
                ),
            ),
        },
        tags=["Admin"],
    )
    def get(self, request):
        force_refresh = str(request.query_params.get("refresh", "")).lower() == "true"
        actor_id = (
            str(request.user.id)
            if getattr(request, "user", None) and request.user.is_authenticated
            else None
        )

        cached_payload = cache.get(CACHE_KEY) if not force_refresh else None
        if cached_payload is not None:
            # Cache HIT — return the cached payload unmodified except for
            # the live ``cache_hit`` discriminator. The aggregator was
            # NOT re-run.
            logger.info(
                "admin_dashboard_summary_cache_hit",
                extra={"actor_user_id": actor_id},
            )
            self._record_cache_metric(outcome="hit")
            response = dict(cached_payload)
            response["cache_hit"] = True
            return self._with_cache_headers(Response(response, status=status.HTTP_200_OK))

        # Cache MISS or forced refresh — aggregate + cache the result.
        # Phase 235.5 audit-fix Gap 4 — telemetry: emit aggregator
        # duration so ops can graph dashboard-build latency over time
        # and alert on regressions.
        # Phase 235.6 — duration ALSO goes to the Prometheus histogram
        # ``admin_dashboard_summary_aggregate_duration_seconds`` so
        # Grafana panels can show P50/P95/P99 over time.
        aggregate_started = time.monotonic()
        try:
            payload = build_dashboard_summary()
        except Exception:
            logger.exception(
                "admin_dashboard_summary_aggregate_failed",
                extra={"actor_user_id": actor_id, "force_refresh": force_refresh},
            )
            raise
        aggregate_duration_seconds = time.monotonic() - aggregate_started
        cache.set(CACHE_KEY, payload, timeout=CACHE_TTL_SECONDS)
        logger.info(
            "admin_dashboard_summary_cache_miss",
            extra={
                "actor_user_id": actor_id,
                "force_refresh": force_refresh,
                "aggregate_duration_ms": round(aggregate_duration_seconds * 1000, 2),
            },
        )
        self._record_cache_metric(outcome="miss")
        self._record_duration_metric(aggregate_duration_seconds)
        response = dict(payload)
        response["cache_hit"] = False
        return self._with_cache_headers(Response(response, status=status.HTTP_200_OK))

    @staticmethod
    def _record_cache_metric(*, outcome: str) -> None:
        """Phase 235.6 — increment ``admin_dashboard_summary_cache_total``.

        Wrapped in try/except so a metric-backend outage (OTel exporter
        down, Prometheus scraping endpoint sick) MUST NOT block the
        admin dashboard response. The metric is ops-visibility; the
        response is the load-bearing artefact.
        """
        try:
            from hub.apps.observability.otel_metrics import (
                admin_dashboard_summary_cache_total,
            )

            admin_dashboard_summary_cache_total.labels(outcome=outcome).inc()
        except Exception:
            logger.debug(
                "admin_dashboard_summary_cache_metric_emit_failed",
                exc_info=True,
            )

    @staticmethod
    def _record_duration_metric(seconds: float) -> None:
        """Phase 235.6 — observe the aggregator duration histogram."""
        try:
            from hub.apps.observability.otel_metrics import (
                admin_dashboard_summary_aggregate_duration_seconds,
            )

            admin_dashboard_summary_aggregate_duration_seconds.observe(seconds)
        except Exception:
            logger.debug(
                "admin_dashboard_summary_duration_metric_emit_failed",
                exc_info=True,
            )

    @staticmethod
    def _with_cache_headers(response: Response) -> Response:
        """Phase 235.5 audit-fix Gap 5 — stamp a short browser cache
        on the response.

        The SPA polls every 60 s and the server cache is 5 min. A
        browser ``Cache-Control: private, max-age=60`` lets the
        browser de-dupe identical back-to-back polls within the
        60-second window (e.g. an operator switching tabs / a React
        Strict-Mode double-mount in dev) without paying the round-
        trip cost. ``private`` prevents any shared cache (CDN /
        corporate proxy) from caching the admin payload.
        """
        response["Cache-Control"] = "private, max-age=60"
        return response
