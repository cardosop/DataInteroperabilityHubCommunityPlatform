"""
Worker Run Lifecycle Side Effects

Applies run completion side effects when PATCH updates run to COMPLETED or FAILED:
next_run_at, cost tracking, DLQ sync, notifications, domain events.
"""

import logging

from django.utils import timezone

from .models import ScheduledIngestion, ScheduledIngestionRun, ScheduledIngestionStatus

logger = logging.getLogger(__name__)


def apply_run_completion_side_effects(run: ScheduledIngestionRun, new_status: str) -> None:
    """
    Apply side effects when run is PATCHed to COMPLETED or FAILED.
    Uses real CostTrackingManager, DeadLetterQueueManager, notifications; no mocks.
    """
    scheduled_ingestion = run.scheduled_ingestion
    scheduled_ingestion_id = str(scheduled_ingestion.id)

    # 1. Update ScheduledIngestion: next_run_at (for UI); clear ERROR if COMPLETED, set ERROR if FAILED
    scheduled_ingestion.next_run_at = scheduled_ingestion._calculate_next_run_at()
    if new_status == "COMPLETED" and scheduled_ingestion.status == ScheduledIngestionStatus.ERROR:
        scheduled_ingestion.status = ScheduledIngestionStatus.ACTIVE
        scheduled_ingestion.error_message = None
    if new_status == "FAILED":
        scheduled_ingestion.status = ScheduledIngestionStatus.ERROR
        scheduled_ingestion.error_message = run.error_message or "Run failed"
    update_fields = ["next_run_at", "updated_at", "status", "error_message"]
    scheduled_ingestion.save(update_fields=update_fields)

    # 2. If COMPLETED: cost tracking
    if new_status == "COMPLETED":
        try:
            from .cost_tracking import CostTrackingManager

            CostTrackingManager.calculate_run_costs(str(run.id))
        except Exception as e:
            logger.warning(
                "Failed to calculate run costs: run_id=%s error=%s",
                str(run.id),
                str(e),
            )

    # 3. DLQ sync
    try:
        from .dead_letter_queue import DeadLetterQueueManager

        DeadLetterQueueManager.sync_from_ingestion_state(scheduled_ingestion_id)
    except Exception as e:
        logger.warning(
            "Failed to sync DLQ from ingestion state: scheduled_ingestion_id=%s error=%s",
            scheduled_ingestion_id,
            str(e),
        )

    # 4. Completion or failure notification (same semantics as workflow)
    _send_completion_or_failure_notification(run, new_status)


def _send_completion_or_failure_notification(run: ScheduledIngestionRun, status: str) -> None:
    """Send completion or failure notification if configured (source_config.send_notifications, notification_recipients)."""
    scheduled_ingestion = run.scheduled_ingestion
    source_config = scheduled_ingestion.source_config or {}
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
    try:
        from types import SimpleNamespace

        from hub.apps.notifications.models import EmailType
        from hub.apps.notifications.tasks import send_email_async

        # Template expects user with display_name; use created_by or a safe dummy
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
                "job_url": None,  # Run has no Job; template expects job_url for {% if job_url %}
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
                "job_url": None,  # Run has no Job; template expects job_url for {% if job_url %}
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
    except Exception as e:
        logger.warning(
            "Failed to send run notification: run_id=%s status=%s error=%s",
            str(run.id),
            status,
            str(e),
        )
