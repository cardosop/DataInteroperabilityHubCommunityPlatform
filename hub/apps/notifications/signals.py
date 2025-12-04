"""
Email Notification Signals

Signals for triggering email notifications on various events.
"""
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
    """
    from django.conf import settings
    
    # Only process status changes (not creation)
    if created:
        return
    
    # Check if job notifications are enabled
    if not getattr(settings, 'EMAIL_JOB_NOTIFICATIONS_ENABLED', False):
        return
    
    # Only send emails for terminal states
    if instance.status == JobStatus.COMPLETED:
        # Send completion email asynchronously
        if instance.created_by:
            send_job_completion_email.delay(str(instance.id))
    elif instance.status == JobStatus.FAILED:
        # Send failure email asynchronously
        if instance.created_by:
            send_job_failure_email.delay(str(instance.id))

