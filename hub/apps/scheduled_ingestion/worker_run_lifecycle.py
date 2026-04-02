"""
Worker Run Lifecycle Side Effects

Applies run completion side effects when PATCH updates run to COMPLETED or FAILED:
next_run_at, cost tracking, DLQ sync, notifications, audit events.

Phase 76 — Outbox pattern: side effects are persisted as SideEffect rows before
execution so that failures can be retried by the retry_failed_side_effects CronJob.
"""

import logging
from typing import List

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from hub.apps.jobs.models import SideEffect, SideEffectStatus, SideEffectType

from .models import ScheduledIngestion, ScheduledIngestionRun, ScheduledIngestionStatus

logger = logging.getLogger(__name__)


def apply_run_completion_side_effects(run: ScheduledIngestionRun, new_status: str) -> None:
    """
    Apply side effects when run is PATCHed to COMPLETED or FAILED.

    1. Synchronously update the parent ScheduledIngestion (next_run_at, failure
       tracking, auto-pause).  This is *not* a side effect — it is the core
       state transition and must succeed atomically with the run status change.
    2. Create SideEffect outbox rows for each downstream effect.
    3. Attempt to process each row immediately; failures are captured and
       retried later by the CronJob.
    """
    scheduled_ingestion = run.scheduled_ingestion
    scheduled_ingestion_id = str(scheduled_ingestion.id)

    # ── 1. Core state transition (not a side effect) ──────────────────
    _update_parent_ingestion(scheduled_ingestion, run, new_status)

    # ── 2. Create outbox rows ─────────────────────────────────────────
    run_ct = ContentType.objects.get_for_model(run)
    context = {
        "run_id": str(run.id),
        "scheduled_ingestion_id": scheduled_ingestion_id,
        "new_status": new_status,
    }

    effect_types: List[str] = [SideEffectType.DLQ_SYNC, SideEffectType.NOTIFICATION, SideEffectType.AUDIT_EVENT]
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
    Execute a single SideEffect row.  On success → COMPLETED; on failure → FAILED.
    """
    se.attempt_count += 1
    try:
        ctx = se.context_json or {}
        run_id = ctx.get("run_id")
        scheduled_ingestion_id = ctx.get("scheduled_ingestion_id")
        new_status = ctx.get("new_status")

        if se.effect_type == SideEffectType.COST_TRACKING:
            _execute_cost_tracking(run_id)
        elif se.effect_type == SideEffectType.DLQ_SYNC:
            _execute_dlq_sync(scheduled_ingestion_id, run_id)
        elif se.effect_type == SideEffectType.NOTIFICATION:
            _execute_notification(run_id, new_status)
        elif se.effect_type == SideEffectType.AUDIT_EVENT:
            _execute_audit_event(run_id, new_status, scheduled_ingestion_id)

        se.status = SideEffectStatus.COMPLETED
        se.completed_at = timezone.now()
        se.error_message = None
        se.save(update_fields=["status", "completed_at", "error_message", "attempt_count", "updated_at"])
    except Exception as exc:
        se.status = SideEffectStatus.FAILED
        se.error_message = str(exc)[:2000]
        se.save(update_fields=["status", "error_message", "attempt_count", "updated_at"])
        logger.warning(
            "Side effect %s failed: run_object_id=%s error=%s",
            se.effect_type,
            se.run_object_id,
            str(exc),
        )
        # Phase 78: Prometheus counter for side-effect failures
        try:
            from hub.apps.observability.otel_metrics import side_effect_failures_total
            side_effect_failures_total.labels(effect_type=se.effect_type).inc()
        except Exception:
            pass


# ── Concrete side-effect executors ────────────────────────────────────


def _execute_cost_tracking(run_id: str) -> None:
    from .cost_tracking import CostTrackingManager
    CostTrackingManager.calculate_run_costs(run_id)


def _execute_dlq_sync(scheduled_ingestion_id: str, run_id: str) -> None:
    from .dead_letter_queue import DeadLetterQueueManager
    from .models import ScheduledIngestionRun

    try:
        DeadLetterQueueManager.sync_from_ingestion_state(scheduled_ingestion_id)
        ScheduledIngestionRun.objects.filter(pk=run_id).update(
            dlq_sync_status="SYNCED", updated_at=timezone.now(),
        )
    except Exception:
        ScheduledIngestionRun.objects.filter(pk=run_id).update(
            dlq_sync_status="FAILED", updated_at=timezone.now(),
        )
        logger.error(
            "DLQ sync failed for run %s (ingestion %s)",
            run_id,
            scheduled_ingestion_id,
            exc_info=True,
        )
        raise


def _execute_notification(run_id: str, new_status: str) -> None:
    from .models import ScheduledIngestionRun
    run = ScheduledIngestionRun.objects.select_related(
        "scheduled_ingestion", "scheduled_ingestion__created_by",
    ).get(pk=run_id)
    _send_completion_or_failure_notification(run, new_status)


def _execute_audit_event(run_id: str, new_status: str, scheduled_ingestion_id: str) -> None:
    from hub.apps.audit.utils import create_audit_event
    from .models import ScheduledIngestionRun

    run = ScheduledIngestionRun.objects.select_related(
        "scheduled_ingestion__tenant",
    ).get(pk=run_id)

    create_audit_event(
        resource_type="SCHEDULED_INGESTION_RUN",
        action=f"RUN_{new_status}",
        actor_user=None,
        tenant=run.scheduled_ingestion.tenant,
        resource_id=run_id,
        details={
            "scheduled_ingestion_id": scheduled_ingestion_id,
            "status": new_status,
        },
    )


# ── Parent ingestion state machine (synchronous, non-side-effect) ────


def _update_parent_ingestion(
    scheduled_ingestion: ScheduledIngestion,
    run: ScheduledIngestionRun,
    new_status: str,
) -> None:
    from django.conf import settings as _s

    scheduled_ingestion.next_run_at = scheduled_ingestion._calculate_next_run_at()

    if new_status == "COMPLETED":
        scheduled_ingestion.consecutive_failure_count = 0
        scheduled_ingestion.last_error_at = None
        if scheduled_ingestion.status == ScheduledIngestionStatus.ERROR:
            scheduled_ingestion.status = ScheduledIngestionStatus.ACTIVE
            scheduled_ingestion.error_message = None
    elif new_status == "FAILED":
        scheduled_ingestion.consecutive_failure_count += 1
        scheduled_ingestion.last_error_at = timezone.now()
        scheduled_ingestion.error_message = run.error_message or "Run failed"
        max_failures = getattr(_s, "MAX_CONSECUTIVE_FAILURES", 5)
        if scheduled_ingestion.consecutive_failure_count >= max_failures:
            scheduled_ingestion.status = ScheduledIngestionStatus.PAUSED
            logger.warning(
                "Auto-paused after %d consecutive failures",
                scheduled_ingestion.consecutive_failure_count,
                extra={"id": str(scheduled_ingestion.id)},
            )
        else:
            scheduled_ingestion.status = ScheduledIngestionStatus.ERROR

    update_fields = [
        "next_run_at", "updated_at", "status", "error_message",
        "consecutive_failure_count", "last_error_at",
    ]
    scheduled_ingestion.save(update_fields=update_fields)


# ── Notification helper (preserved from original) ────────────────────


def _send_completion_or_failure_notification(run: ScheduledIngestionRun, status: str) -> None:
    """Send completion or failure notification if configured."""
    scheduled_ingestion = run.scheduled_ingestion
    source_config = scheduled_ingestion.get_source_config() or {}
    if not source_config.get("send_notifications", True):
        return
    recipients = source_config.get("notification_recipients", [])
    if not recipients and scheduled_ingestion.created_by_id:
        if scheduled_ingestion.created_by and getattr(
            scheduled_ingestion.created_by, "email", None
        ):
            recipients = [scheduled_ingestion.created_by.email]
    if not recipients:
        return

    from types import SimpleNamespace

    from hub.apps.notifications.models import EmailType
    from hub.apps.notifications.tasks import send_email_async

    user_for_template = scheduled_ingestion.created_by or SimpleNamespace(display_name="")

    if status == "COMPLETED":
        subject = f"Scheduled Ingestion Completed: {scheduled_ingestion.name}"
        result_summary = (
            f"Scheduled ingestion '{scheduled_ingestion.name}' has completed.\n"
            f"Files processed: {run.files_processed}, Files failed: {run.files_failed}\nRun ID: {run.id}"
        )
        email_type = EmailType.JOB_COMPLETION
        template_name = "notifications/emails/job_completion.html"
        context = {
            "user": user_for_template,
            "job_type": "Scheduled Ingestion",
            "resource_type": "Run",
            "resource_id": str(run.id),
            "result_summary": result_summary,
            "job_url": None,
        }
    else:
        subject = f"Scheduled Ingestion Failed: {scheduled_ingestion.name}"
        error_message = run.error_message or "Unknown"
        email_type = EmailType.JOB_FAILURE
        template_name = "notifications/emails/job_failure.html"
        context = {
            "user": user_for_template,
            "job_type": "Scheduled Ingestion",
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
                str(scheduled_ingestion.tenant_id) if scheduled_ingestion.tenant_id else None
            ),
            user_id=(
                str(scheduled_ingestion.created_by_id)
                if scheduled_ingestion.created_by_id
                else None
            ),
        )
    logger.info(
        "Run %s notification sent: run_id=%s recipients=%s",
        status.lower(),
        str(run.id),
        recipients,
    )
