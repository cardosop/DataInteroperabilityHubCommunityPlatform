"""Periodic DPIA review sweep — approved assessments past ``next_review_due_at``."""

from __future__ import annotations
from datetime import timedelta

from django.db import connection, transaction
from django.utils import timezone

from hub.apps.audit import event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.dpia.models import Dpia, DpiaStatus
from hub.apps.tenants.models import Tenant


def run_dpia_review_due_scan(*, reopen: bool = True) -> dict[str, int]:
    """
    For each tenant with DPIA enabled, reopen approved DPIAs whose review deadline passed.

    Transitions APPROVED → IN_REVIEW when ``now >= next_review_due_at`` (typically annual).

    Runs inside ``transaction.atomic()`` with ``SET LOCAL app.rls_dpia_enabled = 'off'``
    so the sweep can see rows across tenants when RLS is enabled on the connection.

    Returns:
        Counts: tenants_scanned, rows_reopened, audit_events_created
    """
    now = timezone.now()
    tenants_scanned = 0
    rows_reopened = 0
    audits = 0

    tenant_ids = list(
        Tenant.objects.filter(compliance_dpia_enabled=True).values_list("id", flat=True)
    )

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.rls_dpia_enabled = 'off'")

        for tid in tenant_ids:
            tenants_scanned += 1
            qs = Dpia.objects.filter(
                tenant_id=tid,
                status=DpiaStatus.APPROVED,
                next_review_due_at__isnull=False,
                next_review_due_at__lte=now,
            ).select_related("tenant")
            for dpia in qs:
                if not reopen:
                    continue
                dpia.status = DpiaStatus.IN_REVIEW
                dpia.dpo_summary = (
                    (dpia.dpo_summary or "").strip()
                    + "\n\n[System] Periodic review window opened — please re-assess."
                ).strip()
                dpia.save(update_fields=["status", "dpo_summary", "updated_at"])
                rows_reopened += 1
                create_audit_event(
                    resource_type="DPIA",
                    action=event_types.DPIA_PERIODIC_REVIEW_OPENED,
                    tenant=dpia.tenant,
                    resource_id=dpia.id,
                    details={
                        "due_at": dpia.next_review_due_at.isoformat()
                        if dpia.next_review_due_at
                        else None,
                        "regime": dpia.regime,
                    },
                )
                audits += 1

    return {
        "tenants_scanned": tenants_scanned,
        "rows_reopened": rows_reopened,
        "audit_events_created": audits,
    }


def default_next_review_due(from_dt=None):
    """Default 12-month review horizon."""
    base = from_dt or timezone.now()
    return base + timedelta(days=365)
