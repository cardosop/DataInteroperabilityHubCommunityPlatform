"""Aggregated breach response dashboard (Phase 232.3.14)."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from hub.apps.breach.models import (
    BreachIncident,
    BreachNotification,
    BreachNotificationStatus,
)
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context


def _hours_remaining(deadline) -> float | None:
    if deadline is None:
        return None
    return (deadline - timezone.now()).total_seconds() / 3600.0


def breach_dashboard_summary(*, tenant: Tenant) -> dict[str, Any]:
    with tenant_context(str(tenant.id)):
        qs = BreachIncident.objects.filter(tenant=tenant)
        open_count = qs.count()
        pending = BreachNotification.objects.filter(
            tenant=tenant, status=BreachNotificationStatus.PENDING
        ).count()
        inc = qs.order_by("statutory_authority_deadline_utc").values(
            "id",
            "title",
            "status",
            "statutory_authority_deadline_utc",
        )[:50]
        rows: list[dict[str, Any]] = []
        for r in inc:
            eol = r["statutory_authority_deadline_utc"]
            rows.append(
                {
                    "id": str(r["id"]),
                    "title": r["title"],
                    "status": r["status"],
                    "statutory_authority_deadline_utc": eol.isoformat() if eol else None,
                    "hours_remaining": _hours_remaining(eol),
                }
            )

    return {
        "tenant_id": str(tenant.id),
        "open_incidents_count": open_count,
        "pending_notifications_count": pending,
        "incidents": rows,
    }
