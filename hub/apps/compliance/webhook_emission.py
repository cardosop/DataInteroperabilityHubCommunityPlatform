"""
Phase 231.4 — Tenant HTTP webhooks for terminal compliance runs (``compliance.completed``).

Distinct from :meth:`ComplianceEventPublisher.publish_compliance_check_completed`, which posts
internal bus events (``compliance.check.completed``). This module fans out scrubbed payloads through
:class:`~hub.apps.webhooks.service.WebhookDeliveryService`.
"""

from __future__ import annotations
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import quote

import structlog
from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.tenants.request_tenant import tenant_context
from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.service import WebhookDeliveryService

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant

logger = structlog.get_logger(__name__)

_REPORT_SIGNER_SALT = "compliance.webhook.report.v1"
_REPORT_SIGNER_MAX_AGE = int(timedelta(days=7).total_seconds())


def build_report_presigned_token(run: ComplianceRun) -> str:
    signer = TimestampSigner(salt=_REPORT_SIGNER_SALT)
    return signer.sign(f"{run.pk}|{run.tenant_id}")


def decode_report_presigned_token(raw_token: str) -> tuple[str, str]:
    signer = TimestampSigner(salt=_REPORT_SIGNER_SALT)
    try:
        value = signer.unsign(raw_token, max_age=_REPORT_SIGNER_MAX_AGE)
    except SignatureExpired as exc:
        raise BadSignature("expired") from exc
    parts = value.split("|", 1)
    if len(parts) != 2:
        raise BadSignature("malformed payload")
    return parts[0], parts[1]


def build_report_presigned_url_for_run(run: ComplianceRun) -> Optional[str]:
    base = (getattr(settings, "COMPLIANCE_WEBHOOK_REPORT_BASE_URL", "") or "").strip()
    if not base:
        return None
    token = build_report_presigned_token(run)
    return f"{base.rstrip('/')}/webhooks/completed/report/?token={quote(token, safe='')}"


def build_compliance_completed_webhook_data(
    run: ComplianceRun,
    *,
    report_presigned_url: Optional[str],
) -> Dict[str, Any]:
    """D231.8 — whitelist-only payload nested under webhook ``data``."""
    asset_id = str(run.asset_id) if run.asset_id else None
    completed = run.completed_at.isoformat() if run.completed_at else None
    return {
        "risk_level": run.risk_level,
        "asset_id": asset_id,
        "run_id": str(run.id),
        "completed_at": completed,
        "report_presigned_url": report_presigned_url,
        "terminal_status": run.status,
        # Idempotency for WebhookDelivery id dedupe (promoted to payload ``event_id``).
        "event_id": str(run.id),
    }


def publish_compliance_check_completed(run: ComplianceRun) -> None:
    """
    Deliver ``WebhookEventType.COMPLIANCE_COMPLETED`` (``compliance.completed``) subscriptions.

    Eligibility:
        * status is ``SUCCEEDED`` or ``FAILED``
        * ``webhook_fired_at`` is ``NULL``

    ``on_commit`` callbacks run after the saving transaction's GUC scope ends; this
    function re-enters :func:`~hub.apps.tenants.request_tenant.tenant_context` so
    RLS on ``compliance_runs`` does not hide the row / block the stamp.

    Raises:
        Does not raise — callers use ``transaction.on_commit``; failures leave
        ``webhook_fired_at`` unset so a later terminal transition retry can retry.
    """
    tenant_key = getattr(run, "tenant_id", None)
    if tenant_key is None:
        logger.error(
            "compliance_completed_webhook_missing_tenant_id",
            run_id=str(getattr(run, "pk", None) or getattr(run, "id", "")),
        )
        return

    with tenant_context(str(tenant_key)):
        row = (
            ComplianceRun.objects.select_related("tenant")
            .filter(
                pk=run.pk,
                webhook_fired_at__isnull=True,
                status__in=[
                    ComplianceRunStatus.SUCCEEDED,
                    ComplianceRunStatus.FAILED,
                ],
            )
            .first()
        )
        if not row:
            return

        report_url = build_report_presigned_url_for_run(row)
        event_data = build_compliance_completed_webhook_data(
            row, report_presigned_url=report_url
        )

        try:
            delivery_targets = WebhookDeliveryService.trigger_webhook(
                tenant_id=str(row.tenant_id),
                event_type=str(WebhookEventType.COMPLIANCE_COMPLETED),
                resource_type="COMPLIANCE_RUN",
                resource_id=str(row.id),
                event_data=event_data,
            )
        except Exception as exc:
            logger.exception(
                "compliance_completed_webhook_trigger_failed",
                run_id=str(row.id),
                tenant_id=str(row.tenant_id),
                error=str(exc),
            )
            return

        now = timezone.now()
        updated = ComplianceRun.objects.filter(
            pk=row.pk,
            webhook_fired_at__isnull=True,
        ).update(webhook_fired_at=now)
        if updated == 0:
            return

        from hub.apps.compliance.metrics_phase231 import (
            EVENT_WEBHOOK_FIRED,
            record_compliance_intake_gate_event,
        )

        record_compliance_intake_gate_event(EVENT_WEBHOOK_FIRED, row.tenant_id)

        tenant_row: Optional[Tenant] = getattr(row, "tenant", None)

        try:
            create_audit_event(
                resource_type="COMPLIANCE_RUN",
                action=audit_event_types.COMPLIANCE_WEBHOOK_FIRED,
                actor_user=None,
                tenant=tenant_row,
                resource_id=str(row.id),
                details={
                    "compliance_run_id": str(row.id),
                    "tenant_id": str(row.tenant_id),
                    "terminal_status": row.status,
                    "subscription_match_count": delivery_targets,
                },
            )
        except Exception as exc:
            logger.warning(
                "compliance_webhook_fired_audit_failed",
                run_id=str(row.id),
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )
