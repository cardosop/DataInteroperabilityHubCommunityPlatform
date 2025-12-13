"""
Job Processing Tasks

Worker tasks for processing jobs.
"""
import time
from datetime import timedelta
from django_rq import job
from django.utils import timezone
from django.db import transaction
from .models import Job, JobStatus, JobType
from .utils import (
    WORKER_MAX_CONCURRENCY,
    WORKER_MAX_CONCURRENCY_PER_TENANT,
    WORKER_RESERVED_SLOTS,
    WORKER_SHARED_SLOTS,
    decrement_tenant_job_counter,
    increment_tenant_job_counter,
    get_queue_for_job_type,
    should_elevate_job,
    increment_reserved_slots_usage,
    decrement_reserved_slots_usage,
    increment_shared_slots_usage,
    decrement_shared_slots_usage,
    get_job_wait_time,
    retry_job,
)
from hub.apps.audit.utils import create_audit_event
import structlog

logger = structlog.get_logger(__name__)


@job('default', timeout=600)
def process_job(job_id: str, job_type: str, timeout: int = 600):
    """
    Process a job.
    
    This is a placeholder that will be extended by specific job handlers.
    For MVP, this demonstrates the job processing pattern.
    
    Implements reserved slots and starvation prevention:
    - HIGH priority jobs (job_critical) can use reserved slots or shared slots
    - NORMAL priority jobs (job_default) can use shared slots, or reserved slots if elevated
    - LOW priority jobs (job_low) can only use shared slots
    - NORMAL priority jobs are elevated to HIGH if they've been waiting > threshold
    
    Args:
        job_id: UUID of the job
        job_type: Job type string
        timeout: Job timeout in seconds
    """
    # Determine queue name and check starvation prevention
    queue_name = get_queue_for_job_type(job_type)
    is_elevated = should_elevate_job(job_id, queue_name)
    wait_time = get_job_wait_time(job_id)
    
    # Track slot usage based on priority and elevation
    slot_type = None
    try:
        # Get job
        job_obj = Job.objects.get(id=job_id)
        
        # Check if job was cancelled before processing
        if job_obj.status == JobStatus.CANCELLED:
            logger.info(
                "job_cancelled_before_processing",
                job_id=job_id,
                message=f"Job {job_id} was cancelled before processing started"
            )
            return
        
        # Determine slot type based on queue and elevation
        if queue_name == 'job_critical' or (queue_name == 'job_default' and is_elevated):
            # HIGH priority or elevated: try reserved slot first, then shared
            from .utils import can_use_reserved_slot, can_use_shared_slot
            if can_use_reserved_slot():
                increment_reserved_slots_usage()
                slot_type = "reserved"
            elif can_use_shared_slot():
                increment_shared_slots_usage()
                slot_type = "shared"
            else:
                # No slots available - this shouldn't happen as django-rq already picked the job
                logger.warning(
                    "job_no_slots_available",
                    job_id=job_id,
                    queue_name=queue_name,
                    is_elevated=is_elevated,
                    message="Job picked but no slots available (should not happen)"
                )
                slot_type = "shared"  # Fallback to shared
                increment_shared_slots_usage()
        else:
            # NORMAL or LOW priority: use shared slot
            from .utils import can_use_shared_slot
            if can_use_shared_slot():
                increment_shared_slots_usage()
                slot_type = "shared"
            else:
                # No slots available - this shouldn't happen
                logger.warning(
                    "job_no_shared_slots_available",
                    job_id=job_id,
                    queue_name=queue_name,
                    message="Job picked but no shared slots available (should not happen)"
                )
                slot_type = "shared"  # Fallback
                increment_shared_slots_usage()
        
        # Mark job as started
        job_obj.mark_started()
        
        # Update tenant job counters: decrement queued, increment running
        if job_obj.tenant:
            decrement_tenant_job_counter(str(job_obj.tenant.id), "queued")
            increment_tenant_job_counter(str(job_obj.tenant.id), "running")
            logger.info(
                "job_started",
                job_id=str(job_obj.id),
                tenant_id=str(job_obj.tenant.id),
                job_type=job_type,
                queue_name=queue_name,
                slot_type=slot_type,
                is_elevated=is_elevated,
                wait_time_seconds=wait_time,
                status="RUNNING",
                message=f"Job started for tenant {job_obj.tenant.id} (slot: {slot_type}, elevated: {is_elevated})"
            )
        
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
        
        # Check if job was cancelled after starting (before executing logic)
        job_obj.refresh_from_db()
        if job_obj.status == JobStatus.CANCELLED:
            logger.info(
                "job_cancelled_during_processing",
                job_id=str(job_obj.id),
                tenant_id=str(job_obj.tenant.id) if job_obj.tenant else None,
                job_type=job_type,
                message=f"Job {job_obj.id} was cancelled after starting, before executing logic"
            )
            # Release tenant job counter
            if job_obj.tenant:
                decrement_tenant_job_counter(str(job_obj.tenant.id), "running")
            # Release slot
            if slot_type == "reserved":
                decrement_reserved_slots_usage()
            elif slot_type == "shared":
                decrement_shared_slots_usage()
            return
        
        # Execute job logic
        result = _execute_job_logic(job_obj, job_type)
        
        # Check if job was cancelled during execution
        job_obj.refresh_from_db()
        if job_obj.status == JobStatus.CANCELLED:
            logger.info(
                "job_cancelled_during_execution",
                job_id=str(job_obj.id),
                tenant_id=str(job_obj.tenant.id) if job_obj.tenant else None,
                job_type=job_type,
                message=f"Job {job_obj.id} was cancelled during execution"
            )
            # Release tenant job counter
            if job_obj.tenant:
                decrement_tenant_job_counter(str(job_obj.tenant.id), "running")
            # Release slot
            if slot_type == "reserved":
                decrement_reserved_slots_usage()
            elif slot_type == "shared":
                decrement_shared_slots_usage()
            return
        
        # Check if timeout exceeded
        if timezone.now() > timeout_time:
            job_obj.mark_failed(
                error_message=f"Job exceeded timeout of {timeout} seconds",
                result_json=result
            )
            return
        
        # Mark job as completed
        job_obj.mark_completed(result_json=result)
        
        # Update tenant job counter: decrement running
        if job_obj.tenant:
            decrement_tenant_job_counter(str(job_obj.tenant.id), "running")
            # Calculate duration for logging
            duration_seconds = None
            if job_obj.started_at and job_obj.completed_at:
                duration_seconds = (job_obj.completed_at - job_obj.started_at).total_seconds()
            logger.info(
                "job_completed",
                job_id=str(job_obj.id),
                tenant_id=str(job_obj.tenant.id),
                job_type=job_type,
                slot_type=slot_type,
                duration_seconds=duration_seconds,
                status="COMPLETED",
                message=f"Job completed for tenant {job_obj.tenant.id}"
            )
        
        # Release slot
        if slot_type == "reserved":
            decrement_reserved_slots_usage()
        elif slot_type == "shared":
            decrement_shared_slots_usage()
        
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
        # Handle job failure with retry logic
        try:
            job_obj = Job.objects.get(id=job_id)
            
            # Determine error type and code
            error_type = type(e).__name__
            error_code = 'UNKNOWN_ERROR'
            
            if isinstance(e, ValueError):
                error_code = 'VALIDATION_ERROR'
            elif isinstance(e, ConnectionError):
                error_code = 'SERVICE_UNAVAILABLE'
            elif isinstance(e, TimeoutError):
                error_code = 'TIMEOUT_ERROR'
            elif 'timeout' in str(e).lower() or 'timed out' in str(e).lower():
                error_code = 'TIMEOUT_ERROR'
            elif 'connection' in str(e).lower() or 'unavailable' in str(e).lower():
                error_code = 'SERVICE_UNAVAILABLE'
            
            # Try to retry job if error is transient
            if retry_job(job_obj, job_type, e):
                # Job was retried - release slot and return (job will be processed again)
                if job_obj.tenant and job_obj.status == JobStatus.RUNNING:
                    decrement_tenant_job_counter(str(job_obj.tenant.id), "running")
                
                # Release slot
                if slot_type == "reserved":
                    decrement_reserved_slots_usage()
                elif slot_type == "shared":
                    decrement_shared_slots_usage()
                
                # Log retry event
                if job_obj.tenant and job_obj.created_by:
                    create_audit_event(
                        resource_type="JOB",
                        action=f"{job_type}_RETRY",
                        actor_user=job_obj.created_by,
                        tenant=job_obj.tenant,
                        resource_id=str(job_obj.id),
                        details={
                            'job_type': job_type,
                            'retry_count': job_obj.details_json.get('retry_count', 0),
                            'error': str(e)
                        }
                    )
                return  # Job will be retried, exit here
            
            # No retries remaining or error is not transient - mark as failed
            job_obj.mark_failed(
                error_message=str(e),
                result_json={
                    'error': str(e),
                    'error_type': error_type,
                    'error_code': error_code,
                    'retry_count': job_obj.details_json.get('retry_count', 0) if job_obj.details_json else 0
                }
            )
            
            # Update tenant job counter: decrement running (if job was running)
            if job_obj.tenant and job_obj.status == JobStatus.RUNNING:
                decrement_tenant_job_counter(str(job_obj.tenant.id), "running")
            
            # Calculate duration for logging
            duration_seconds = None
            if job_obj.started_at and job_obj.completed_at:
                duration_seconds = (job_obj.completed_at - job_obj.started_at).total_seconds()
            
            # Log structured error
            logger.error(
                "job_failed",
                job_id=str(job_obj.id),
                tenant_id=str(job_obj.tenant.id) if job_obj.tenant else None,
                job_type=job_type,
                error_type=error_type,
                error_code=error_code,
                error_message=str(e),
                duration_seconds=duration_seconds,
                retry_count=job_obj.details_json.get('retry_count', 0) if job_obj.details_json else 0,
                status="FAILED",
                message=f"Job failed for tenant {job_obj.tenant.id if job_obj.tenant else 'system'}: {str(e)}"
            )
            
            # Release slot
            if slot_type == "reserved":
                decrement_reserved_slots_usage()
            elif slot_type == "shared":
                decrement_shared_slots_usage()
            
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
                        'error': str(e),
                        'retry_count': job_obj.details_json.get('retry_count', 0) if job_obj.details_json else 0
                    }
                )
        except Exception:
            pass  # Job may not exist


def _execute_job_logic(job_obj: Job, job_type: str) -> dict:
    """
    Execute job logic based on job type.
    
    Handles errors, timeouts, and service failures for each job type.
    Raises exceptions that will be caught by the outer process_job function.
    
    Args:
        job_obj: Job instance
        job_type: Job type string
    
    Returns:
        Result dictionary with job execution results
    
    Raises:
        ValueError: For validation errors (missing parameters, invalid resource types)
        TimeoutError: For timeout errors
        ConnectionError: For service connection errors
        Exception: For other errors (will be caught and logged)
    """
    if job_type == JobType.DQ_RUN:
        return _execute_dq_run_job(job_obj)
    
    elif job_type == JobType.COMPLIANCE_RUN:
        return _execute_compliance_run_job(job_obj)
    
    elif job_type == JobType.CONTRACT_VALIDATION:
        return _execute_contract_validation_job(job_obj)
    
    elif job_type == JobType.SEMANTIC_MAPPING:
        return _execute_semantic_mapping_job(job_obj)
    
    elif job_type == JobType.CONTRACT_MIGRATION:
        return _execute_contract_migration_job(job_obj)
    
    elif job_type == JobType.SCHEDULED_INGESTION:
        from hub.apps.jobs.scheduled_ingestion_job import _execute_scheduled_ingestion_job
        return _execute_scheduled_ingestion_job(job_obj)
    
    elif job_type == JobType.RETENTION_POLICY_ENFORCEMENT:
        return _execute_retention_policy_enforcement_job(job_obj)
    
    elif job_type == JobType.SEARCH_INDEX_UPDATE:
        return _execute_search_index_update_job(job_obj)
    
    else:
        raise ValueError(f"Unknown job type: {job_type}")


def _execute_dq_run_job(job_obj: Job) -> dict:
    """
    Execute DQ_RUN job.
    
    Args:
        job_obj: Job instance
    
    Returns:
        Result dictionary with DQ run results
    
    Raises:
        ValueError: If dq_run_id is missing or DQ run not found
        ConnectionError: If DQ service is unavailable
        Exception: For other errors
    """
    # Get dq_run_id from job details or resource_id
    # Handle None values explicitly (details_json can have None, resource_id can be None if model allows)
    dq_run_id = job_obj.details_json.get('dq_run_id')
    if not dq_run_id:  # None or empty string
        dq_run_id = job_obj.resource_id
    
    # Convert to string if it's a UUID object, handle None case
    if dq_run_id is not None:
        dq_run_id = str(dq_run_id)
    
    if not dq_run_id:
        raise ValueError("DQ run ID is required")
    
    # Check if DQ run exists before executing
    try:
        from hub.apps.dq.models import DQRun, DQRunStatus
        dq_run = DQRun.objects.get(id=dq_run_id)
    except DQRun.DoesNotExist:
        raise ValueError(f"DQ run {dq_run_id} not found")
    
    try:
        # Import here to avoid circular imports
        from hub.apps.dq.views import execute_dq_run
        from hub.apps.dq.service_client import DQServiceClient
        
        # Check if DQ service is available
        dq_client = DQServiceClient()
        is_healthy, _ = dq_client.health_check()
        if not is_healthy:
            raise ConnectionError("DQ service is unavailable")
        
        # Execute DQ run (this handles its own errors and updates DQRun status)
        execute_dq_run(str(dq_run_id))
        
        # Get updated DQ run (refresh from DB)
        dq_run.refresh_from_db()
        
        # Check if DQ run failed
        if dq_run.status == DQRunStatus.FAILED:
            error_msg = dq_run.details_json.get('error', 'DQ run failed') if dq_run.details_json else 'DQ run failed'
            raise Exception(f"DQ run failed: {error_msg}")
        
        return {
            'status': dq_run.status.lower(),
            'overall_status': dq_run.overall_status,
            'quality_score': dq_run.quality_score,
            'dq_run_id': str(dq_run.id),
            'engine': dq_run.engine if hasattr(dq_run, 'engine') else None
        }
    
    except ConnectionError:
        raise  # Re-raise connection errors
    except ValueError:
        raise  # Re-raise validation errors
    except Exception as e:
        # Wrap other exceptions
        raise Exception(f"DQ run execution failed: {str(e)}") from e


def _execute_compliance_run_job(job_obj: Job) -> dict:
    """
    Execute COMPLIANCE_RUN job.
    
    Args:
        job_obj: Job instance
    
    Returns:
        Result dictionary with compliance run results
    
    Raises:
        ValueError: If compliance_run_id is missing or compliance run not found
        ConnectionError: If compliance service is unavailable
        Exception: For other errors
    """
    # Get compliance_run_id from job details or resource_id
    compliance_run_id = job_obj.details_json.get('compliance_run_id') or job_obj.resource_id
    
    # Convert to string if it's a UUID object
    if compliance_run_id:
        compliance_run_id = str(compliance_run_id)
    
    if not compliance_run_id:
        raise ValueError("Compliance run ID is required")
    
    try:
        # Import here to avoid circular imports
        from hub.apps.compliance.views import execute_compliance_run
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        from hub.apps.compliance.service_client import ComplianceServiceClient
        
        # Check if compliance run exists before executing
        try:
            compliance_run = ComplianceRun.objects.get(id=compliance_run_id)
        except ComplianceRun.DoesNotExist:
            raise ValueError(f"Compliance run {compliance_run_id} not found")
        
        # Check if compliance service is available
        compliance_client = ComplianceServiceClient()
        is_healthy, _ = compliance_client.health_check()
        if not is_healthy:
            raise ConnectionError("Compliance service is unavailable")
        
        # Execute compliance run (this handles its own errors and updates ComplianceRun status)
        execute_compliance_run(str(compliance_run_id))
        
        # Get updated compliance run (refresh from DB)
        compliance_run.refresh_from_db()
        
        # Check if compliance run failed
        if compliance_run.status == ComplianceRunStatus.FAILED:
            error_msg = compliance_run.regulation_mapping_json.get('error', 'Compliance run failed') if compliance_run.regulation_mapping_json else 'Compliance run failed'
            raise Exception(f"Compliance run failed: {error_msg}")
        
        return {
            'status': compliance_run.status.lower(),
            'overall_status': compliance_run.overall_status,
            'risk_level': compliance_run.risk_level,
            'allowed_to_store': compliance_run.allowed_to_store,
            'compliance_run_id': str(compliance_run.id)
        }
    
    except ConnectionError:
        raise  # Re-raise connection errors
    except ValueError:
        raise  # Re-raise validation errors
    except Exception as e:
        # Wrap other exceptions
        raise Exception(f"Compliance run execution failed: {str(e)}") from e


def _execute_contract_validation_job(job_obj: Job) -> dict:
    """
    Execute CONTRACT_VALIDATION job.
    
    Args:
        job_obj: Job instance
    
    Returns:
        Result dictionary with validation results
    
    Raises:
        ValueError: If contract_id is missing or contract not found
        ConnectionError: If DataContract CLI service is unavailable
        TimeoutError: If validation times out
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id
    
    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)
    
    if not contract_id:
        raise ValueError("Contract ID is required")
    
    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract, ValidationStatus
        from hub.apps.contracts.cli_client import DataContractCLIClient, SYNC_TIMEOUT
        from hub.apps.contracts.cli_client import interpret_validation_status, group_errors_by_category
        
        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")
        
        if not contract.original_raw or contract.original_raw.strip() == '':
            raise ValueError(f"Contract {contract_id} has no original_raw content")
        
        # Check if DataContract CLI service is available
        cli_client = DataContractCLIClient()
        try:
            health = cli_client.health_check()
            # DataContractCLIClient returns Dict[str, Any] with 'status' key
            if isinstance(health, dict) and health.get('status') != 'healthy':
                raise ConnectionError("DataContract CLI service is unavailable")
        except ConnectionError:
            raise  # Re-raise connection errors
        except Exception as e:
            raise ConnectionError(f"DataContract CLI service health check failed: {str(e)}")
        
        # Validate contract
        try:
            validation_result = cli_client.validate(
                raw_contract=contract.original_raw,
                format=contract.original_format,
                tenant_id=str(contract.tenant.id) if contract.tenant else None,
                use_cache=True,
                timeout=SYNC_TIMEOUT
            )
        except Exception as e:
            if 'timeout' in str(e).lower() or 'timed out' in str(e).lower():
                raise TimeoutError(f"Contract validation timed out after {SYNC_TIMEOUT} seconds")
            raise ConnectionError(f"Contract validation service error: {str(e)}")
        
        # Interpret validation status
        validation_status, errors, warnings = interpret_validation_status(validation_result)
        
        # Group errors by category
        grouped_errors = group_errors_by_category(errors)
        
        return {
            'status': 'completed',
            'validation_status': validation_status,
            'errors': errors,
            'warnings': warnings,
            'grouped_errors': grouped_errors,
            'cli_version': validation_result.get('cli_version', 'unknown'),
            'contract_id': str(contract_id)
        }
    
    except (ConnectionError, TimeoutError, ValueError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        raise Exception(f"Contract validation failed: {str(e)}") from e


def _execute_semantic_mapping_job(job_obj: Job) -> dict:
    """
    Execute SEMANTIC_MAPPING job.
    
    Args:
        job_obj: Job instance
    
    Returns:
        Result dictionary with semantic mapping results
    
    Raises:
        ValueError: If resource_type or resource_id is missing, or resource not found
        ConnectionError: If semantic service is unavailable
        Exception: For other errors
    """
    # Get resource details from job
    resource_type = job_obj.details_json.get('resource_type')
    resource_id = job_obj.details_json.get('resource_id')
    
    if not resource_type:
        raise ValueError("Resource type is required for SEMANTIC_MAPPING job")
    
    if not resource_id:
        raise ValueError("Resource ID is required for SEMANTIC_MAPPING job")
    
    try:
        # Import here to avoid circular imports
        from hub.apps.semantic.utils import map_contract_to_semantic, map_asset_to_semantic
        from hub.apps.semantic.service_client import SemanticServiceClient
        
        # Validate resource type first (before service health check)
        if resource_type not in ['CONTRACT', 'ASSET']:
            raise ValueError(f"Unknown resource type: {resource_type}")
        
        # Validate resource exists before checking service health
        if resource_type == 'CONTRACT':
            from hub.apps.contracts.models import Contract
            try:
                # Convert resource_id to UUID if it's a string
                if isinstance(resource_id, str):
                    import uuid as uuid_module
                    resource_id = uuid_module.UUID(resource_id)
                contract = Contract.objects.get(id=resource_id)
            except Contract.DoesNotExist:
                raise ValueError(f"Contract {resource_id} not found")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid contract ID format: {resource_id}") from e
        
        elif resource_type == 'ASSET':
            from hub.apps.assets.models import Asset
            try:
                # Convert resource_id to UUID if it's a string
                if isinstance(resource_id, str):
                    import uuid as uuid_module
                    resource_id = uuid_module.UUID(resource_id)
                asset = Asset.objects.get(id=resource_id)
            except Asset.DoesNotExist:
                raise ValueError(f"Asset {resource_id} not found")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid asset ID format: {resource_id}") from e
        
        # Check if semantic service is available (after resource validation)
        semantic_client = SemanticServiceClient()
        try:
            # SemanticServiceClient.health_check() returns Tuple[bool, str]
            is_healthy, _ = semantic_client.health_check()
            if not is_healthy:
                raise ConnectionError("Semantic service is unavailable")
        except ConnectionError:
            raise  # Re-raise connection errors
        except Exception as e:
            raise ConnectionError(f"Semantic service health check failed: {str(e)}")
        
        # Execute mapping (resource already validated above)
        if resource_type == 'CONTRACT':
            semantic_resource = map_contract_to_semantic(contract, tenant=contract.tenant)
            
            return {
                'status': 'completed',
                'resource_type': 'CONTRACT',
                'resource_id': str(resource_id),
                'semantic_resource_id': str(semantic_resource.id) if semantic_resource else None
            }
        
        elif resource_type == 'ASSET':
            semantic_resource = map_asset_to_semantic(asset, tenant=asset.tenant)
            
            return {
                'status': 'completed',
                'resource_type': 'ASSET',
                'resource_id': str(resource_id),
                'semantic_resource_id': str(semantic_resource.id) if semantic_resource else None
            }
    
    except (ConnectionError, ValueError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        raise Exception(f"Semantic mapping failed: {str(e)}") from e


def _execute_contract_migration_job(job_obj: Job) -> dict:
    """
    Execute CONTRACT_MIGRATION job.
    
    Args:
        job_obj: Job instance
    
    Returns:
        Result dictionary with migration results
    
    Raises:
        ValueError: If contract_id is missing or contract not found
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id
    
    if not contract_id:
        raise ValueError("Contract ID is required for CONTRACT_MIGRATION job")
    
    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.migration_manager import ContractMigrationManager
        
        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")
        
        # Perform migration
        migrated, hub_contract, warnings = ContractMigrationManager.migrate_on_write(contract)
        
        if not migrated:
            return {
                'status': 'completed',
                'migrated': False,
                'message': 'Migration not needed or already completed',
                'warnings': warnings,
                'contract_id': str(contract_id)
            }
        
        return {
            'status': 'completed',
            'migrated': True,
            'source_version': job_obj.details_json.get('source_version'),
            'target_version': job_obj.details_json.get('target_version'),
            'warnings': warnings,
            'contract_id': str(contract_id)
        }
    
    except ValueError:
        raise  # Re-raise validation errors
    except Exception as e:
        # Wrap other exceptions
        raise Exception(f"Contract migration failed: {str(e)}") from e


@job('default', timeout=600)
def process_contract_migration_job(job_id: str):
    """
    Process contract migration job.
    
    Args:
        job_id: UUID of the job
    """
    process_job(job_id, JobType.CONTRACT_MIGRATION, timeout=600)


def _execute_retention_policy_enforcement_job(job_obj: Job) -> dict:
    """
    Execute RETENTION_POLICY_ENFORCEMENT job.
    
    Enforces retention policies for assets, datasets, and files.
    
    Args:
        job_obj: Job instance
    
    Returns:
        Result dictionary with enforcement summary
    
    Raises:
        ValueError: For validation errors
        Exception: For other errors
    """
    from hub.apps.governance.retention import RetentionPolicyEnforcer
    
    tenant_id = job_obj.tenant_id
    
    logger.info("Starting retention policy enforcement", job_id=str(job_obj.id), tenant_id=str(tenant_id))
    
    try:
        # Enforce all policies
        results = RetentionPolicyEnforcer.enforce_all_policies(tenant_id=str(tenant_id) if tenant_id else None)
        
        logger.info(
            "Retention policy enforcement completed",
            job_id=str(job_obj.id),
            total_policies=results['total_policies'],
            enforced=results['enforced'],
            failed=results['failed']
        )
        
        return {
            'success': True,
            'summary': {
                'total_policies': results['total_policies'],
                'enforced': results['enforced'],
                'failed': results['failed'],
                'no_action': results['no_action']
            },
            'details': results['details']
        }
    
    except Exception as e:
        logger.error("Retention policy enforcement job failed", exc_info=True, job_id=str(job_obj.id), error=str(e))
        raise


def _execute_search_index_update_job(job_obj: Job) -> dict:
    """
    Execute SEARCH_INDEX_UPDATE job.
    
    Updates search index for a specific resource (contract, asset, or dataset).
    
    Args:
        job_obj: Job instance
    
    Returns:
        Result dictionary with indexing summary
    
    Raises:
        ValueError: For validation errors
        Exception: For other errors
    """
    from hub.apps.search.indexing import SearchIndexer
    from hub.apps.contracts.models import Contract
    from hub.apps.assets.models import Asset
    from hub.apps.datasets.models import Dataset
    
    resource_type = job_obj.resource_type
    resource_id = job_obj.resource_id
    
    logger.info(
        "Starting search index update",
        job_id=str(job_obj.id),
        resource_type=resource_type,
        resource_id=str(resource_id)
    )
    
    try:
        # Index based on resource type
        if resource_type == "CONTRACT":
            contract = Contract.objects.get(id=resource_id)
            search_index = SearchIndexer.index_contract(contract)
            indexed_type = "contract"
        elif resource_type == "ASSET":
            asset = Asset.objects.get(id=resource_id)
            search_index = SearchIndexer.index_asset(asset)
            indexed_type = "asset"
        elif resource_type == "DATASET":
            dataset = Dataset.objects.get(id=resource_id)
            search_index = SearchIndexer.index_dataset(dataset)
            indexed_type = "dataset"
        else:
            raise ValueError(f"Unknown resource type for indexing: {resource_type}")
        
        logger.info(
            "Search index update completed",
            job_id=str(job_obj.id),
            resource_type=resource_type,
            resource_id=str(resource_id),
            search_index_id=str(search_index.id)
        )
        
        return {
            'success': True,
            'indexed_type': indexed_type,
            'search_index_id': str(search_index.id),
            'resource_type': resource_type,
            'resource_id': str(resource_id)
        }
    
    except Contract.DoesNotExist:
        raise ValueError(f"Contract {resource_id} not found")
    except Asset.DoesNotExist:
        raise ValueError(f"Asset {resource_id} not found")
    except Dataset.DoesNotExist:
        raise ValueError(f"Dataset {resource_id} not found")
    except Exception as e:
        logger.error(
            "Search index update job failed",
            exc_info=True,
            job_id=str(job_obj.id),
            resource_type=resource_type,
            resource_id=str(resource_id),
            error=str(e)
        )
        raise


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
        timeout_time = job_obj.started_at + timedelta(seconds=job_obj.timeout_seconds)
        
        # Check if timeout exceeded
        if timezone.now() > timeout_time:
            job_obj.mark_failed(
                error_message=f"Job exceeded timeout of {job_obj.timeout_seconds} seconds",
                result_json={'timeout': True, 'timeout_seconds': job_obj.timeout_seconds}
            )

