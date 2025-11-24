"""
Job Processing Tasks

Worker tasks for processing jobs.
"""
import time
from django_rq import job
from django.utils import timezone
from django.db import transaction
from .models import Job, JobStatus, JobType
from .utils import WORKER_MAX_CONCURRENCY, WORKER_MAX_CONCURRENCY_PER_TENANT
from hub.apps.audit.utils import create_audit_event


@job('default', timeout=600)
def process_job(job_id: str, job_type: str, timeout: int = 600):
    """
    Process a job.
    
    This is a placeholder that will be extended by specific job handlers.
    For MVP, this demonstrates the job processing pattern.
    
    Args:
        job_id: UUID of the job
        job_type: Job type string
        timeout: Job timeout in seconds
    """
    try:
        # Get job
        job_obj = Job.objects.get(id=job_id)
        
        # Check if job was cancelled
        if job_obj.status == JobStatus.CANCELLED:
            return
        
        # Mark job as started
        job_obj.mark_started()
        
        # Log audit event
        if job_obj.tenant and job_obj.created_by:
            create_audit_event(
                resource_type="JOB",
                action=f"{job_type}_STARTED",
                actor_user=job_obj.created_by,
                tenant=job_obj.tenant,
                resource_id=str(job_obj.id),
                details={
                    'job_type': job_type,
                    'resource_type': job_obj.resource_type,
                    'resource_id': str(job_obj.resource_id)
                }
            )
        
        # Check timeout
        start_time = timezone.now()
        timeout_time = start_time + timezone.timedelta(seconds=timeout)
        
        # Placeholder: Execute job logic
        # In production, this would call specific handlers based on job_type
        result = _execute_job_logic(job_obj, job_type)
        
        # Check if timeout exceeded
        if timezone.now() > timeout_time:
            job_obj.mark_failed(
                error_message=f"Job exceeded timeout of {timeout} seconds",
                result_json=result
            )
            return
        
        # Mark job as completed
        job_obj.mark_completed(result_json=result)
        
        # Log audit event
        if job_obj.tenant and job_obj.created_by:
            create_audit_event(
                resource_type="JOB",
                action=f"{job_type}_COMPLETED",
                actor_user=job_obj.created_by,
                tenant=job_obj.tenant,
                resource_id=str(job_obj.id),
                details={
                    'job_type': job_type,
                    'resource_type': job_obj.resource_type,
                    'resource_id': str(job_obj.resource_id)
                }
            )
    
    except Exception as e:
        # Mark job as failed
        try:
            job_obj = Job.objects.get(id=job_id)
            job_obj.mark_failed(
                error_message=str(e),
                result_json={'error': str(e)}
            )
            
            # Log audit event
            if job_obj.tenant and job_obj.created_by:
                create_audit_event(
                    resource_type="JOB",
                    action=f"{job_type}_FAILED",
                    actor_user=job_obj.created_by,
                    tenant=job_obj.tenant,
                    resource_id=str(job_obj.id),
                    details={
                        'job_type': job_type,
                        'error': str(e)
                    }
                )
        except Exception:
            pass  # Job may not exist


def _execute_job_logic(job_obj: Job, job_type: str) -> dict:
    """
    Execute job logic based on job type.
    
    Args:
        job_obj: Job instance
        job_type: Job type string
    
    Returns:
        Result dictionary
    """
    if job_type == JobType.DQ_RUN:
        # Get dq_run_id from job details or resource_id
        dq_run_id = job_obj.details_json.get('dq_run_id') or job_obj.resource_id
        
        # Import here to avoid circular imports
        from hub.apps.dq.views import execute_dq_run
        
        # Execute DQ run
        execute_dq_run(dq_run_id)
        
        # Get updated DQ run
        from hub.apps.dq.models import DQRun
        dq_run = DQRun.objects.get(id=dq_run_id)
        
        return {
            'status': dq_run.status.lower(),
            'overall_status': dq_run.overall_status,
            'quality_score': dq_run.quality_score,
            'dq_run_id': str(dq_run.id)
        }
    
    elif job_type == JobType.COMPLIANCE_RUN:
        # Get compliance_run_id from job details or resource_id
        compliance_run_id = job_obj.details_json.get('compliance_run_id') or job_obj.resource_id
        
        # Import here to avoid circular imports
        from hub.apps.compliance.views import execute_compliance_run
        
        # Execute compliance run
        execute_compliance_run(compliance_run_id)
        
        # Get updated compliance run
        from hub.apps.compliance.models import ComplianceRun
        compliance_run = ComplianceRun.objects.get(id=compliance_run_id)
        
        return {
            'status': compliance_run.status.lower(),
            'overall_status': compliance_run.overall_status,
            'risk_level': compliance_run.risk_level,
            'allowed_to_store': compliance_run.allowed_to_store,
            'compliance_run_id': str(compliance_run.id)
        }
    
    elif job_type == JobType.SEMANTIC_MAPPING:
        # Get resource details from job
        resource_type = job_obj.details_json.get('resource_type')
        resource_id = job_obj.details_json.get('resource_id')
        
        # Import here to avoid circular imports
        from hub.apps.semantic.utils import map_contract_to_semantic, map_asset_to_semantic
        
        if resource_type == 'CONTRACT':
            from hub.apps.contracts.models import Contract
            contract = Contract.objects.get(id=resource_id)
            semantic_resource = map_contract_to_semantic(contract, tenant=contract.tenant)
            return {
                'status': 'completed',
                'resource_type': 'CONTRACT',
                'resource_id': str(resource_id),
                'semantic_resource_id': str(semantic_resource.id) if semantic_resource else None
            }
        elif resource_type == 'ASSET':
            from hub.apps.assets.models import Asset
            asset = Asset.objects.get(id=resource_id)
            semantic_resource = map_asset_to_semantic(asset, tenant=asset.tenant)
            return {
                'status': 'completed',
                'resource_type': 'ASSET',
                'resource_id': str(resource_id),
                'semantic_resource_id': str(semantic_resource.id) if semantic_resource else None
            }
        else:
            return {
                'status': 'failed',
                'error': f'Unknown resource type: {resource_type}'
            }
    
    elif job_type == JobType.CONTRACT_MIGRATION:
        # Get contract ID from resource_id
        contract_id = job_obj.resource_id
        
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.migration_manager import ContractMigrationManager
        
        contract = Contract.objects.get(id=contract_id)
        
        # Perform migration
        migrated, hub_contract, warnings = ContractMigrationManager.migrate_on_write(contract)
        
        if not migrated:
            return {
                'status': 'failed',
                'error': 'Migration failed or not needed',
                'warnings': warnings
            }
        
        return {
            'status': 'completed',
            'source_version': job_obj.details_json.get('source_version'),
            'target_version': job_obj.details_json.get('target_version'),
            'warnings': warnings,
            'contract_id': str(contract_id)
        }
    
    # Placeholder for other job types
    time.sleep(1)
    
    return {
        'status': 'completed',
        'message': f'Job {job_type} completed (placeholder)',
        'resource_type': job_obj.resource_type,
        'resource_id': str(job_obj.resource_id)
    }


@job('default', timeout=600)
def process_contract_migration_job(job_id: str):
    """
    Process contract migration job.
    
    Args:
        job_id: UUID of the job
    """
    process_job(job_id, JobType.CONTRACT_MIGRATION, timeout=600)


def check_job_timeouts():
    """
    Check for jobs that have exceeded their timeout.
    
    This should be called periodically (e.g., via cron or scheduled task).
    """
    running_jobs = Job.objects.filter(status=JobStatus.RUNNING)
    
    for job_obj in running_jobs:
        if not job_obj.timeout_seconds or not job_obj.started_at:
            continue
        
        # Calculate timeout time
        timeout_time = job_obj.started_at + timezone.timedelta(seconds=job_obj.timeout_seconds)
        
        # Check if timeout exceeded
        if timezone.now() > timeout_time:
            job_obj.mark_failed(
                error_message=f"Job exceeded timeout of {job_obj.timeout_seconds} seconds",
                result_json={'timeout': True, 'timeout_seconds': job_obj.timeout_seconds}
            )

