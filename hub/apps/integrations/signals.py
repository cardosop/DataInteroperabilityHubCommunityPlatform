"""
Marketplace Integration Signals

Signal handlers for marketplace integration events, including workflow status sync.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import structlog

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.integrations.models import MarketplaceSyncJob

logger = structlog.get_logger(__name__)


@receiver(post_save, sender=WorkflowInstance)
def sync_workflow_status_to_sync_job(sender, instance, created, **kwargs):
    """
    Sync workflow status to sync job when workflow status changes.

    This signal handler ensures that marketplace sync jobs stay in sync
    with their associated workflow instances.

    Only processes marketplace sync workflows and non-creation updates.
    """
    # Only process updates (not creation)
    if created:
        return

    # Only process marketplace sync workflows
    if not instance.workflow_name.startswith("marketplace_sync"):
        return

    # Get sync job ID from workflow state_data
    sync_job_id = None
    if instance.state_data:
        sync_job_id = instance.state_data.get("sync_job_id")

    if not sync_job_id:
        return

    try:
        # Get sync job
        sync_job = MarketplaceSyncJob.objects.get(id=sync_job_id)

        # Sync workflow status to sync job via service layer
        from hub.apps.integrations.services import MarketplaceIntegrationService
        service = MarketplaceIntegrationService(tenant_id=str(instance.tenant_id))
        service.sync_workflow_status_to_sync_job(
            sync_job_id=sync_job_id,
            tenant_id=str(instance.tenant_id)
        )

        logger.debug(
            "Synced workflow status to sync job via signal",
            workflow_instance_id=str(instance.id),
            sync_job_id=sync_job_id,
            workflow_status=instance.status
        )
    except MarketplaceSyncJob.DoesNotExist:
        logger.debug(
            "Sync job not found for workflow status sync",
            workflow_instance_id=str(instance.id),
            sync_job_id=sync_job_id
        )
    except Exception as e:
        logger.warning(
            "Failed to sync workflow status to sync job via signal",
            workflow_instance_id=str(instance.id),
            sync_job_id=sync_job_id,
            error=str(e),
            exc_info=True
        )

