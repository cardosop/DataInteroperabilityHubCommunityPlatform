"""Breach incident workflow + statutory notification fan-out (Phase 232.3.5)."""

from __future__ import annotations
from datetime import timedelta
from typing import Any, Iterable, Optional, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.breach.models import (
    BreachIncident,
    BreachIncidentStatus,
    BreachNotification,
    BreachNotificationChannel,
    BreachNotificationStatus,
)
from hub.apps.breach.proof_storage import archive_breach_notification_proof
from hub.apps.breach.template_service import render_for_authority_id
from hub.apps.regulation_policies.registry import (
    breach_statutory_clock_matrix,
    compute_breach_supervisory_deadline_utc,
    resolve_breach_supervisory_authority_ids,
)
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context

User = get_user_model()


def _regime_tuple(regimes: Iterable[str]) -> tuple[str, ...]:
    cleaned = tuple(sorted({str(r).strip().upper() for r in regimes if str(r).strip()}))
    return cleaned if cleaned else ("GDPR",)


def _audit_event_ids_for(
    *,
    tenant_id,
    incident_id: str,
    notification_id: Optional[str] = None,
) -> list[str]:
    id_list: list[str] = [incident_id]
    if notification_id:
        id_list.append(notification_id)
    rows = (
        AuditEvent.objects.filter(
            tenant_id=tenant_id,
            resource_type__in=("BREACH_INCIDENT", "BREACH_NOTIFICATION"),
            resource_id__in=id_list,
        )
        # ``AuditEvent`` exposes the canonical event time as
        # ``timestamp`` (``auto_now_add=True``); there is no
        # ``created_at`` column. The pre-fix ``order_by("created_at")``
        # raised ``FieldError`` and 500'd every breach
        # ``mark_notification_sent`` call that hit the audit-ordering
        # path.
        .order_by("timestamp")
        .values_list("id", flat=True)[:2000]
    )
    return [str(x) for x in rows]


@transaction.atomic
def create_breach_incident(
    *,
    tenant: Tenant,
    actor: User,
    title: str,
    summary: str,
    regimes: list[str],
    discovered_at,
) -> BreachIncident:
    if not tenant.compliance_breach_enabled:
        raise ValidationError("Breach workflow is disabled for this tenant.")

    rt = _regime_tuple(regimes)
    deadline = compute_breach_supervisory_deadline_utc(discovered_at, rt)

    with tenant_context(str(tenant.id)):
        inc = BreachIncident.objects.create(
            tenant=tenant,
            title=title.strip()[:512],
            summary=(summary or "").strip(),
            regimes=list(rt),
            discovered_at=discovered_at,
            status=BreachIncidentStatus.OPEN,
            statutory_authority_deadline_utc=deadline,
            created_by=actor,
        )

        create_audit_event(
            resource_type="BREACH_INCIDENT",
            action=audit_event_types.BREACH_INCIDENT_OPENED,
            actor_user=actor,
            tenant=tenant,
            resource_id=str(inc.id),
            details={
                "regimes": list(rt),
                "statutory_authority_deadline_utc": deadline.isoformat(),
            },
        )

        for regime in rt:
            reg_mx = breach_statutory_clock_matrix(regime)
            regime_deadline = discovered_at + timedelta(
                hours=int(reg_mx["supervisory_notification_hours"])
            )
            auth_ids = resolve_breach_supervisory_authority_ids(regime)
            if not auth_ids:
                BreachNotification.objects.create(
                    tenant=tenant,
                    incident=inc,
                    regime=regime,
                    supervisory_authority_id="",
                    status=BreachNotificationStatus.PENDING,
                    channel=BreachNotificationChannel.MANUAL,
                    statutory_due_at_utc=regime_deadline,
                )
                continue
            for aid in auth_ids:
                BreachNotification.objects.create(
                    tenant=tenant,
                    incident=inc,
                    regime=regime,
                    supervisory_authority_id=aid,
                    status=BreachNotificationStatus.PENDING,
                    channel=BreachNotificationChannel.MANUAL,
                    statutory_due_at_utc=regime_deadline,
                )

    return inc


@transaction.atomic
def transition_incident_status(
    incident: BreachIncident,
    new_status: str,
    *,
    actor: User,
    notes: str = "",
) -> BreachIncident:
    prev = incident.status
    if prev == new_status:
        return incident
    incident.status = new_status
    if notes:
        d = cast(dict[str, Any], dict(incident.details_json or {}))
        d["status_notes"] = (d.get("status_notes", "") + "\n" + notes).strip()
        incident.details_json = d
    incident.save(update_fields=["status", "details_json", "updated_at"])

    create_audit_event(
        resource_type="BREACH_INCIDENT",
        action=audit_event_types.BREACH_INCIDENT_STATUS_CHANGED,
        actor_user=actor,
        tenant=incident.tenant,
        resource_id=str(incident.id),
        details={"previous": prev, "current": new_status},
    )
    return incident


@transaction.atomic
def mark_notification_sent(
    notification: BreachNotification,
    *,
    actor: User,
    outbound_reference: str,
) -> BreachNotification:
    if notification.status == BreachNotificationStatus.SENT:
        raise ValidationError("Notification already marked sent.")
    incident = notification.incident
    ver, subject, body = render_for_authority_id(notification, incident)
    notification.rendered_subject = subject
    notification.rendered_body = body
    notification.template_version = ver
    notification.outbound_reference = outbound_reference.strip()[:512]
    notification.sent_at = timezone.now()
    notification.status = BreachNotificationStatus.SENT

    from django.conf import settings as dj_settings

    retention_days = int(getattr(dj_settings, "BREACH_PROOF_OBJECT_LOCK_RETENTION_DAYS", 0) or 0)
    notification.object_lock_retention_days = retention_days

    audit_refs = _audit_event_ids_for(
        tenant_id=incident.tenant_id,
        incident_id=str(incident.id),
        notification_id=str(notification.id),
    )
    payload = {
        "notification_id": str(notification.id),
        "incident_id": str(incident.id),
        "tenant_id": str(incident.tenant_id),
        "regime": notification.regime,
        "supervisory_authority_id": notification.supervisory_authority_id,
        "rendered_subject": subject,
        "rendered_body": body,
        "outbound_reference": notification.outbound_reference,
        "template_version": ver,
        "audit_event_ids": audit_refs,
        "archived_at_utc": notification.sent_at.isoformat(),
    }

    with tenant_context(str(incident.tenant_id)):
        proof = archive_breach_notification_proof(
            tenant_id=str(incident.tenant_id),
            notification_id=str(notification.id),
            payload=payload,
        )
        notification.delivery_proof_sha256 = proof.sha256_hex
        notification.proof_storage_path = proof.storage_path
        notification.proof_s3_version_id = proof.s3_version_id

        notification.save(
            update_fields=[
                "rendered_subject",
                "rendered_body",
                "template_version",
                "outbound_reference",
                "sent_at",
                "status",
                "delivery_proof_sha256",
                "proof_storage_path",
                "proof_s3_version_id",
                "object_lock_retention_days",
                "updated_at",
            ]
        )

        create_audit_event(
            resource_type="BREACH_NOTIFICATION",
            action=audit_event_types.BREACH_NOTIFICATION_SENT,
            actor_user=actor,
            tenant=incident.tenant,
            resource_id=str(notification.id),
            details={
                "incident_id": str(incident.id),
                "proof_sha256": proof.sha256_hex,
                "storage_path": proof.storage_path,
                "s3_version_id": proof.s3_version_id or None,
            },
        )
    return notification
