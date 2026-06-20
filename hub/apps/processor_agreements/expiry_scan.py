"""Daily processor-agreement expiry sweep (Phase 232.6.7)."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.processor_agreements.models import ProcessorAgreement, ProcessorAgreementStatus


def run_processor_agreement_expiry_scan(
    *,
    today: date | None = None,
) -> dict[str, int]:
    """
    Fire audits at 60 / 30 / 7 days before ``expires_on``; mark EXPIRED when past due.

    Idempotent per agreement via ``expiry_warn_windows_sent`` (stores fired day-counts).
    """
    day = today or timezone.now().date()
    counters = {"expired": 0, "warn_60": 0, "warn_30": 0, "warn_7": 0}
    thresholds = (60, 30, 7)

    qs = (
        ProcessorAgreement.objects.filter(
            tenant__compliance_processor_agreements_enabled=True,
        )
        .exclude(status=ProcessorAgreementStatus.SUPERSEDED)
        .select_related("tenant", "processor")
    )

    for row in qs.iterator(chunk_size=100):
        if row.expires_on is None:
            continue
        expires: date = row.expires_on
        delta = (expires - day).days
        sent = [int(x) for x in (row.expiry_warn_windows_sent or []) if str(x).isdigit()]

        if delta < 0:
            if row.status != ProcessorAgreementStatus.EXPIRED:
                row.status = ProcessorAgreementStatus.EXPIRED
                row.save(update_fields=["status", "updated_at"])
                create_audit_event(
                    resource_type="PROCESSOR_AGREEMENT",
                    action=audit_event_types.PROCESSOR_AGREEMENT_EXPIRED,
                    tenant=row.tenant,
                    resource_id=str(row.id),
                    details={
                        "processor_id": str(row.processor.pk),
                        "expires_on": expires.isoformat(),
                    },
                )
                counters["expired"] += 1
            continue

        if row.status == ProcessorAgreementStatus.EXPIRED:
            continue

        for th in thresholds:
            if delta == th and th not in sent:
                action = {
                    60: audit_event_types.PROCESSOR_AGREEMENT_EXPIRY_WARN_60,
                    30: audit_event_types.PROCESSOR_AGREEMENT_EXPIRY_WARN_30,
                    7: audit_event_types.PROCESSOR_AGREEMENT_EXPIRY_WARN_7,
                }[th]
                create_audit_event(
                    resource_type="PROCESSOR_AGREEMENT",
                    action=action,
                    tenant=row.tenant,
                    resource_id=str(row.id),
                    details={
                        "processor_id": str(row.processor.pk),
                        "expires_on": expires.isoformat(),
                        "days_remaining": delta,
                    },
                )
                sent.append(th)
                row.expiry_warn_windows_sent = sent
                row.save(update_fields=["expiry_warn_windows_sent", "updated_at"])
                counters[f"warn_{th}"] += 1

    return counters
