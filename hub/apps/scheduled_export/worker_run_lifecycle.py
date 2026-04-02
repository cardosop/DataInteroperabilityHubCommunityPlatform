"""
Worker Run Lifecycle Side Effects

Applies run completion side effects when PATCH updates run to COMPLETED or FAILED:
next_run_at, cost tracking, notifications, audit events.

Phase 76 — Outbox pattern: side effects are persisted as SideEffect rows before
execution so that failures can be retried by the retry_failed_side_effects CronJob.
"""

import logging
from types import SimpleNamespace
from typing import List

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from hub.apps.jobs.models import SideEffect, SideEffectStatus, SideEffectType

from .models import ScheduledExport, ScheduledExportRun, ScheduledExportStatus

logger = logging.getLogger(__name__)


def apply_run_completion_side_effects(
    run: ScheduledExportRun, new_status: str,
) -> None:
    """
    Apply side effects when run is PATCHed to COMPLETED or FAILED.

    1. Synchronously update the parent ScheduledExport (next_run_at,
       last_run_at, last_run_status, status).
    2. Create SideEffect outbox rows for each downstream effect.
    3. Attempt to process each row immediately; failures are captured and
       retried later by the CronJob.
    """
    scheduled_export = run.scheduled_export

    # ── 1. Core state transition (not a side effect) ──────────────────
    _update_parent_export(scheduled_export, run, new_status)

    # ── 2. Create outbox rows ─────────────────────────────────────────
    run_ct = ContentType.objects.get_for_model(run)
    context = {
        "run_id": str(run.id),
        "scheduled_export_id": str(scheduled_export.id),
        "new_status": new_status,
    }

    effect_types: List[str] = [
        SideEffectType.NOTIFICATION,
        SideEffectType.AUDIT_EVENT,
    ]
    if new_status == "COMPLETED":
        effect_types.insert(0, SideEffectType.COST_TRACKING)

    side_effects = SideEffect.objects.bulk_create([
        SideEffect(
            run_content_type=run_ct,
            run_object_id=run.pk,
            effect_type=et,
            status=SideEffectStatus.PENDING,
            context_json=context,
        )
        for et in effect_types
    ])

    # ── 3. Process each immediately ───────────────────────────────────
    for se in side_effects:
        execute_side_effect(se)


def execute_side_effect(se: SideEffect) -> None:
    """
    Execute a single SideEffect row for a ScheduledExportRun.
    On success -> COMPLETED; on failure -> FAILED.
    """
    se.attempt_count += 1
    try:
        ctx = se.context_json or {}
        run_id = ctx.get("run_id")
        scheduled_export_id = ctx.get("scheduled_export_id")
        new_status = ctx.get("new_status")

        if se.effect_type == SideEffectType.COST_TRACKING:
            _execute_cost_tracking(run_id)
        elif se.effect_type == SideEffectType.NOTIFICATION:
            _execute_notification(run_id, new_status)
        elif se.effect_type == SideEffectType.AUDIT_EVENT:
            _execute_audit_event(
                run_id, new_status, scheduled_export_id,
            )

        se.status = SideEffectStatus.COMPLETED
        se.completed_at = timezone.now()
        se.error_message = None
        se.save(update_fields=[
            "status", "completed_at", "error_message",
            "attempt_count", "updated_at",
        ])
    except Exception as exc:
        se.status = SideEffectStatus.FAILED
        se.error_message = str(exc)[:2000]
        se.save(update_fields=[
            "status", "error_message",
            "attempt_count", "updated_at",
        ])
        logger.warning(
            "Side effect %s failed: run_object_id=%s error=%s",
            se.effect_type,
            se.run_object_id,
            str(exc),
        )
        # Phase 78: Prometheus counter for side-effect failures
        try:
            from hub.apps.observability.otel_metrics import (
                side_effect_failures_total,
            )
            side_effect_failures_total.labels(
                effect_type=se.effect_type,
            ).inc()
        except Exception:
            pass


# ── Concrete side-effect executors ────────────────────────────────────


def _execute_cost_tracking(run_id: str) -> None:
    from .cost_tracking import CostTrackingManager
    CostTrackingManager.calculate_run_costs(run_id)


def _execute_notification(run_id: str, new_status: str) -> None:
    from .models import ScheduledExportRun
    run = ScheduledExportRun.objects.select_related(
        "scheduled_export",
    ).get(pk=run_id)
    _send_completion_or_failure_notification(run, new_status)


def _execute_audit_event(
    run_id: str, new_status: str, scheduled_export_id: str,
) -> None:
    from hub.apps.audit.utils import create_audit_event
    from .models import ScheduledExportRun

    run = ScheduledExportRun.objects.select_related(
        "scheduled_export__tenant",
    ).get(pk=run_id)

    create_audit_event(
        resource_type="SCHEDULED_EXPORT_RUN",
        action=f"RUN_{new_status}",
        actor_user=None,
        tenant=run.scheduled_export.tenant,
        resource_id=run_id,
        details={
            "scheduled_export_id": scheduled_export_id,
            "status": new_status,
        },
    )


# ── Parent export state machine (synchronous, non-side-effect) ───────


def _update_parent_export(
    scheduled_export: ScheduledExport,
    run: ScheduledExportRun,
    new_status: str,
) -> None:
    scheduled_export.last_run_at = run.completed_at or timezone.now()
    scheduled_export.last_run_status = new_status
    scheduled_export.next_run_at = (
        scheduled_export._calculate_next_run_at()
    )

    if (
        new_status == "COMPLETED"
        and scheduled_export.status == ScheduledExportStatus.ERROR
    ):
        scheduled_export.status = ScheduledExportStatus.ACTIVE

    if new_status == "FAILED":
        scheduled_export.status = ScheduledExportStatus.ERROR

    update_fields = [
        "next_run_at", "last_run_at", "last_run_status", "updated_at",
    ]
    if new_status in ("COMPLETED", "FAILED"):
        update_fields.append("status")
    scheduled_export.save(update_fields=update_fields)


# ── Notification helper (preserved from original) ────────────────────


def _send_completion_or_failure_notification(
    run: ScheduledExportRun, status: str,
) -> None:
    """Send completion or failure notification if configured."""
    scheduled_export = run.scheduled_export
    destination_config = scheduled_export.get_destination_config()

    if not destination_config.get("send_notifications", True):
        return

    recipients = destination_config.get("notification_recipients", [])
    if not recipients:
        return

    from hub.apps.notifications.models import EmailType
    from hub.apps.notifications.tasks import send_email_async

    user_for_template = SimpleNamespace(display_name="")

    if status == "COMPLETED":
        subject = (
            f"Scheduled Export Completed: {scheduled_export.name}"
        )
        result_summary = (
            f"Scheduled export '{scheduled_export.name}' completed.\n"
            f"Items exported: {run.items_exported}, "
            f"Items failed: {run.items_failed}\n"
            f"Run ID: {run.id}"
        )
        email_type = EmailType.JOB_COMPLETION
        template_name = "notifications/emails/job_completion.html"
        context = {
            "user": user_for_template,
            "job_type": "Scheduled Export",
            "resource_type": "Run",
            "resource_id": str(run.id),
            "result_summary": result_summary,
            "job_url": None,
        }
    else:
        subject = (
            f"Scheduled Export Failed: {scheduled_export.name}"
        )
        error_message = (
            run.result_json.get("error_message", "Unknown")
            if run.result_json
            else "Unknown"
        )
        email_type = EmailType.JOB_FAILURE
        template_name = "notifications/emails/job_failure.html"
        context = {
            "user": user_for_template,
            "job_type": "Scheduled Export",
            "resource_type": "Run",
            "resource_id": str(run.id),
            "error_message": error_message,
            "job_url": None,
        }

    for recipient in recipients:
        send_email_async(
            email_type=email_type,
            to_email=recipient,
            subject=subject,
            template_name=template_name,
            context=context,
            tenant_id=(
                str(scheduled_export.tenant_id)
                if scheduled_export.tenant_id
                else None
            ),
            user_id=None,
        )
    logger.info(
        "Run %s notification sent: run_id=%s recipients=%s",
        status.lower(),
        str(run.id),
        recipients,
    )
