"""
Email Notification Signals

Signals for triggering email notifications on various events.
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from hub.apps.jobs.models import Job, JobStatus
from .tasks import send_job_completion_email, send_job_failure_email


@receiver(post_save, sender=Job)
def job_status_changed(sender, instance, created, **kwargs):
    """
    Send email notifications when job status changes to COMPLETED or FAILED.

    Only sends emails if:
    - Job is in terminal state (COMPLETED or FAILED)
    - Job has a created_by user
    - Job notifications are enabled (configurable)

    Uses transaction.on_commit to ensure emails are only queued after
    the enclosing transaction commits — preventing orphaned task
    execution on rollback.
    """
    from django.conf import settings

    # Only process status changes (not creation)
    if created:
        return

    # Check if job notifications are enabled
    if not getattr(settings, 'EMAIL_JOB_NOTIFICATIONS_ENABLED', False):
        return

    # Only send emails for terminal states — defer to on_commit so the
    # task is never enqueued when the surrounding transaction rolls back.
    job_id = str(instance.id)
    if instance.status == JobStatus.COMPLETED:
        if instance.created_by:
            transaction.on_commit(lambda: send_job_completion_email.delay(job_id))
    elif instance.status == JobStatus.FAILED:
        if instance.created_by:
            transaction.on_commit(lambda: send_job_failure_email.delay(job_id))
