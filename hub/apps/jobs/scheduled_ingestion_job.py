"""
Scheduled Ingestion Job Execution

Handles execution of SCHEDULED_INGESTION job type.
"""
from typing import Dict, Any
from django.db import transaction
from django.utils import timezone
import structlog

from hub.apps.jobs.models import Job, JobStatus
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus
)
from hub.apps.scheduled_ingestion.ingestion import ScheduledIngestionProcessor
from hub.apps.scheduled_ingestion.cost_tracking import CostTrackingManager
from hub.apps.scheduled_ingestion.dead_letter_queue import DeadLetterQueueManager

logger = structlog.get_logger(__name__)


def _execute_scheduled_ingestion_job(job_obj: Job) -> Dict[str, Any]:
    """
    Execute SCHEDULED_INGESTION job.
    
    Args:
        job_obj: Job instance
        
    Returns:
        Result dictionary with ingestion results
        
    Raises:
        ValueError: If scheduled_ingestion_id is missing or ingestion not found
        Exception: For other errors
    """
    # Get scheduled_ingestion_id from resource_id or details_json
    scheduled_ingestion_id = job_obj.resource_id
    if not scheduled_ingestion_id:
        scheduled_ingestion_id = job_obj.details_json.get('scheduled_ingestion_id')
    
    # Convert to string if it's a UUID object
    if scheduled_ingestion_id:
        scheduled_ingestion_id = str(scheduled_ingestion_id)
    
    if not scheduled_ingestion_id:
        raise ValueError("Scheduled ingestion ID is required")
    
    # Get scheduled ingestion
    try:
        scheduled_ingestion = ScheduledIngestion.objects.get(id=scheduled_ingestion_id)
    except ScheduledIngestion.DoesNotExist:
        raise ValueError(f"Scheduled ingestion {scheduled_ingestion_id} not found")
    
    # Get or create run record
    run = None
    if job_obj.details_json and job_obj.details_json.get('scheduled_ingestion_run_id'):
        try:
            run = ScheduledIngestionRun.objects.get(
                id=job_obj.details_json['scheduled_ingestion_run_id']
            )
        except ScheduledIngestionRun.DoesNotExist:
            pass
    
    if not run:
        # Create new run record
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=scheduled_ingestion,
            job=job_obj,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=timezone.now(),
            prefect_flow_run_id=job_obj.details_json.get('prefect_flow_run_id') if job_obj.details_json else None
        )
    else:
        # Update existing run
        run.status = ScheduledIngestionRunStatus.RUNNING
        run.started_at = timezone.now()
        run.job = job_obj
        run.save(update_fields=['status', 'started_at', 'job', 'updated_at'])
    
    try:
        # Initialize processor
        processor = ScheduledIngestionProcessor(scheduled_ingestion)
        
        # Process ingestion
        result = processor.process()
        
        # Update run with results
        run.status = ScheduledIngestionRunStatus.COMPLETED
        run.completed_at = timezone.now()
        run.files_found = result.get('files_found', 0)
        run.files_processed = result.get('files_processed', 0)
        run.files_failed = result.get('files_failed', 0)
        run.datasets_created = result.get('datasets_created', 0)
        run.result_json = result
        run.save(update_fields=[
            'status', 'completed_at', 'files_found', 'files_processed',
            'files_failed', 'datasets_created', 'result_json', 'updated_at'
        ])
        
        # Calculate and store costs
        try:
            CostTrackingManager.calculate_run_costs(str(run.id))
        except Exception as e:
            logger.warning(
                "Failed to calculate ingestion costs",
                run_id=str(run.id),
                error=str(e)
            )
        
        # Sync DLQ items from ingestion state
        try:
            DeadLetterQueueManager.sync_from_ingestion_state(str(scheduled_ingestion.id))
        except Exception as e:
            logger.warning(
                "Failed to sync DLQ items",
                scheduled_ingestion_id=str(scheduled_ingestion.id),
                error=str(e)
            )
        
        # Update scheduled ingestion status
        if scheduled_ingestion.status == ScheduledIngestionStatus.ERROR:
            scheduled_ingestion.status = ScheduledIngestionStatus.ACTIVE
            scheduled_ingestion.error_message = None
            scheduled_ingestion.save(update_fields=['status', 'error_message', 'updated_at'])
        
        logger.info(
            "Scheduled ingestion job completed",
            job_id=str(job_obj.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            run_id=str(run.id),
            files_processed=result.get('files_processed', 0),
            datasets_created=result.get('datasets_created', 0)
        )
        
        return {
            'status': 'completed',
            'run_id': str(run.id),
            'files_found': result.get('files_found', 0),
            'files_processed': result.get('files_processed', 0),
            'files_failed': result.get('files_failed', 0),
            'datasets_created': result.get('datasets_created', 0)
        }
    
    except Exception as e:
        # Update run with failure
        run.status = ScheduledIngestionRunStatus.FAILED
        run.completed_at = timezone.now()
        run.error_message = str(e)
        run.result_json = {
            'error': str(e),
            'error_type': type(e).__name__
        }
        run.save(update_fields=['status', 'completed_at', 'error_message', 'result_json', 'updated_at'])
        
        # Update scheduled ingestion status
        scheduled_ingestion.status = ScheduledIngestionStatus.ERROR
        scheduled_ingestion.error_message = str(e)
        scheduled_ingestion.save(update_fields=['status', 'error_message', 'updated_at'])
        
        logger.error(
            "Scheduled ingestion job failed",
            job_id=str(job_obj.id),
            scheduled_ingestion_id=scheduled_ingestion_id,
            run_id=str(run.id),
            error=str(e),
            exc_info=True
        )
        
        raise

