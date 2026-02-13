"""
Worker Run Lifecycle Side Effects

Applies run completion side effects when PATCH updates run to COMPLETED or FAILED:
next_run_at, cost tracking, notifications, domain events.
"""

import logging
from types import SimpleNamespace

from django.utils import timezone

from .models import ScheduledExport, ScheduledExportRun, ScheduledExportStatus

logger = logging.getLogger(__name__)


def apply_run_completion_side_effects(run: ScheduledExportRun, new_status: str) -> None:
    """
    Apply side effects when run is PATCHed to COMPLETED or FAILED.
    Uses real CostTrackingManager, notifications; no mocks.
    """
    scheduled_export = run.scheduled_export
    scheduled_export_id = str(scheduled_export.id)
    tenant_id = str(scheduled_export.tenant_id)

    # 1. Update ScheduledExport: next_run_at, last_run_at, last_run_status; clear ERROR on success
    scheduled_export.last_run_at = run.completed_at or timezone.now()
    scheduled_export.last_run_status = new_status

    # Recalculate next_run_at for next scheduled run
    scheduled_export.next_run_at = scheduled_export._calculate_next_run_at()

    # Clear ERROR status if COMPLETED
    if new_status == "COMPLETED" and scheduled_export.status == ScheduledExportStatus.ERROR:
        scheduled_export.status = ScheduledExportStatus.ACTIVE

    # Set ERROR status if FAILED
    if new_status == "FAILED":
        scheduled_export.status = ScheduledExportStatus.ERROR

    update_fields = ["next_run_at", "last_run_at", "last_run_status", "updated_at"]
    # Always include status in update_fields if it was changed
    if new_status == "COMPLETED" or new_status == "FAILED":
        update_fields.append("status")
    scheduled_export.save(update_fields=update_fields)

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

    # 3. Completion or failure notification (if configured)
    _send_completion_or_failure_notification(run, new_status)

    # 4. Domain events (if needed)
    # Note: Export domain events can be added here if needed
    # For now, we rely on audit events which are emitted in views


def _send_completion_or_failure_notification(run: ScheduledExportRun, status: str) -> None:
    """Send completion or failure notification if configured."""
    scheduled_export = run.scheduled_export
    destination_config = scheduled_export.destination_config or {}

    # Check if notifications are enabled (default: True)
    if not destination_config.get("send_notifications", True):
        return

    # Get notification recipients
    recipients = destination_config.get("notification_recipients", [])
    # Note: ScheduledExport doesn't have created_by field, so we skip fallback to creator email

    if not recipients:
        return

    try:
        from hub.apps.notifications.models import EmailType
        from hub.apps.notifications.tasks import send_email_async

        # Template expects user with display_name; use a safe dummy (ScheduledExport doesn't have created_by)
        user_for_template = SimpleNamespace(display_name="")

        if status == "COMPLETED":
            subject = f"Scheduled Export Completed: {scheduled_export.name}"
            result_summary = (
                f"Scheduled export '{scheduled_export.name}' has completed.\n"
                f"Items exported: {run.items_exported}, Items failed: {run.items_failed}\n"
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
            }
        else:
            subject = f"Scheduled Export Failed: {scheduled_export.name}"
            error_message = (
                run.result_json.get("error_message", "Unknown") if run.result_json else "Unknown"
            )
            email_type = EmailType.JOB_FAILURE
            template_name = "notifications/emails/job_failure.html"
            context = {
                "user": user_for_template,
                "job_type": "Scheduled Export",
                "resource_type": "Run",
                "resource_id": str(run.id),
                "error_message": error_message,
            }

        for recipient in recipients:
            send_email_async(
                email_type=email_type,
                to_email=recipient,
                subject=subject,
                template_name=template_name,
                context=context,
                tenant_id=str(scheduled_export.tenant_id) if scheduled_export.tenant_id else None,
                user_id=None,  # ScheduledExport doesn't have created_by field
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
