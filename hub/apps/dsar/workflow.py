"""DSAR lifecycle and statutory deadline assignment (Phase 232.2)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.dsar.models import (
    DSARRequest,
    DSARStatus,
    DSARVerificationMethod,
)
from hub.apps.dsar.webhook_emission import publish_dsar_event
from hub.apps.regulation_policies.registry import (
    compute_dsar_ack_deadline_utc,
    compute_dsar_fulfilment_deadline_utc,
)
from hub.apps.webhooks.models import WebhookEventType

User = get_user_model()


def _regime_tuple(regimes: list[str]) -> tuple[str, ...]:
    cleaned = tuple(sorted({str(r).strip().upper() for r in regimes if str(r).strip()}))
    return cleaned if cleaned else ("GDPR",)


@transaction.atomic
def create_dsar_public(
    *,
    tenant_id,
    request_type: str,
    subject_email: str,
    regimes: list[str],
    verification_method: str = DSARVerificationMethod.EMAIL_OTP,
    subject_name: str = "",
    subject_timezone: str = "UTC",
    regulator_timezone: str = "UTC",
    idempotency_key: str = "",
    extension_path_selected: bool = False,
) -> DSARRequest:
    """Create a DSAR opened by a data subject (public ingress)."""
    from hub.apps.tenants.models import Tenant

    tenant = Tenant.objects.get(id=tenant_id)
    if not tenant.compliance_dsar_enabled:
        raise ValidationError("DSAR subsystem disabled for this tenant")

    rtuple = _regime_tuple(regimes)
    submitted = timezone.now()
    dsar = DSARRequest.objects.create(
        tenant=tenant,
        request_type=request_type,
        status=DSARStatus.SUBMITTED,
        regimes=list(rtuple),
        subject_email=subject_email.strip().lower(),
        subject_name=subject_name or "",
        subject_timezone=subject_timezone or "UTC",
        regulator_timezone=regulator_timezone or "UTC",
        verification_method=verification_method,
        idempotency_key=(idempotency_key or "").strip()[:128],
        extension_path_selected=extension_path_selected,
        statutory_ack_deadline_utc=compute_dsar_ack_deadline_utc(submitted, rtuple),
        statutory_fulfil_deadline_utc=compute_dsar_fulfilment_deadline_utc(
            submitted,
            rtuple,
            use_extension_path=extension_path_selected,
        ),
    )

    create_audit_event(
        resource_type="DSAR_REQUEST",
        action="DSAR_SUBMITTED",
        tenant=tenant,
        resource_id=str(dsar.id),
        details={
            "request_type": request_type,
            "regimes": list(rtuple),
            "verification_method": verification_method,
        },
    )
    publish_dsar_event(dsar, WebhookEventType.DSAR_SUBMITTED)
    if verification_method == DSARVerificationMethod.INTERNAL_API_TOKEN:
        dsar.refresh_from_db()
        transition_status(
            dsar,
            DSARStatus.UNDER_REVIEW,
            notes="Pre-authenticated subject (INTERNAL_API_TOKEN ingress)",
        )
    return dsar


@transaction.atomic
def transition_status(
    dsar: DSARRequest,
    new_status: str,
    *,
    actor_user: User | None = None,
    notes: str = "",
) -> DSARRequest:
    prev = dsar.status
    if prev == new_status:
        return dsar
    dsar.status = new_status
    if notes:
        dsar.handler_notes = (dsar.handler_notes + "\n" + notes).strip()
    dsar.save(update_fields=["status", "handler_notes", "updated_at"])

    create_audit_event(
        resource_type="DSAR_REQUEST",
        action="DSAR_STATUS_CHANGED",
        actor_user=actor_user,
        tenant=dsar.tenant,
        resource_id=str(dsar.id),
        details={"previous": prev, "current": new_status},
    )
    publish_dsar_event(dsar, WebhookEventType.DSAR_STATUS_CHANGED)
    if new_status == DSARStatus.CLOSED_FULFILLED:
        publish_dsar_event(dsar, WebhookEventType.DSAR_FULFILLED)
    elif new_status == DSARStatus.CLOSED_REJECTED:
        publish_dsar_event(dsar, WebhookEventType.DSAR_REJECTED)

    return dsar


def begin_identity_email_otp(dsar: DSARRequest) -> str:
    if dsar.verification_method != DSARVerificationMethod.EMAIL_OTP:
        raise ValueError("EMAIL_OTP not selected for this DSAR")
    plaintext = dsar.issue_email_otp()
    if dsar.status == DSARStatus.SUBMITTED:
        transition_status(dsar, DSARStatus.IDV_PENDING, notes="OTP issued")
    return plaintext


def submit_email_otp(dsar: DSARRequest, code: str) -> bool:
    if not dsar.verify_email_otp(code):
        create_audit_event(
            resource_type="DSAR_REQUEST",
            action="DSAR_IDV_FAILED",
            tenant=dsar.tenant,
            resource_id=str(dsar.id),
            result="FAILURE",
            details={"attempts": dsar.email_otp_attempts},
        )
        return False
    transition_status(dsar, DSARStatus.UNDER_REVIEW, notes="Email OTP verified")
    return True


@transaction.atomic
def set_legal_hold(
    dsar: DSARRequest,
    *,
    active: bool,
    reason: str,
    actor_user: User | None,
) -> DSARRequest:
    prior_logged = dsar.sla_suspended_event_logged
    first_suspend = active and not prior_logged

    dsar.legal_hold = active
    dsar.legal_hold_reason = reason[:4000]
    update_fields = ["legal_hold", "legal_hold_reason", "updated_at"]
    if first_suspend:
        dsar.sla_suspended_event_logged = True
        update_fields.append("sla_suspended_event_logged")
    dsar.save(update_fields=update_fields)
    create_audit_event(
        resource_type="DSAR_REQUEST",
        action="DSAR_LEGAL_HOLD_TOGGLED",
        actor_user=actor_user,
        tenant=dsar.tenant,
        resource_id=str(dsar.id),
        details={"active": active},
    )
    if first_suspend:
        create_audit_event(
            resource_type="DSAR_REQUEST",
            action="DSAR_SLA_SUSPENDED",
            actor_user=actor_user,
            tenant=dsar.tenant,
            resource_id=str(dsar.id),
            details={"reason": dsar.legal_hold_reason[:2000]},
        )
        publish_dsar_event(dsar, WebhookEventType.DSAR_SLA_SUSPENDED)
    return dsar
