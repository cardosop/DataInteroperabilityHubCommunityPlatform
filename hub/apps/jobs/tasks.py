"""
Job Processing Tasks

Worker tasks for processing jobs.
"""
import time
from datetime import timedelta
from django_rq import job
from django.utils import timezone
from django.db import transaction
from .models import Job, JobStatus, JobType, JobPriority
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

        # Track priority metrics: decrement queue length, increment processing rate
        try:
            from hub.apps.observability.otel_metrics import (
                job_queue_length_by_priority,
                job_processing_rate_by_priority
            )
            job_priority = job_obj.priority
            job_queue_length_by_priority.labels(
                priority=job_priority,
                job_type=job_type
            ).dec()
            job_processing_rate_by_priority.labels(
                priority=job_priority,
                job_type=job_type
            ).inc()
        except Exception:
            pass  # Metrics may not be available

        # Update tenant job counters: decrement queued, increment running
        if job_obj.tenant:
            decrement_tenant_job_counter(str(job_obj.tenant.id), "queued")
            increment_tenant_job_counter(str(job_obj.tenant.id), "running")
            logger.info(
                "job_started",
                job_id=str(job_obj.id),
                tenant_id=str(job_obj.tenant.id),
                job_type=job_type,
                priority=job_obj.priority,
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

    elif job_type == JobType.ODPS_NORMALIZATION:
        return _execute_odps_normalization_job(job_obj)

    elif job_type == JobType.ODPS_REF_RESOLUTION:
        return _execute_odps_ref_resolution_job(job_obj)

    elif job_type == JobType.ODPS_EXPORT:
        return _execute_odps_export_job(job_obj)

    elif job_type == JobType.ODPS_SEMANTIC_MAPPING:
        return _execute_odps_semantic_mapping_job(job_obj)

    elif job_type == JobType.ODPS_LINKING:
        return _execute_odps_linking_job(job_obj)

    elif job_type == JobType.TRANSFORMATION_PIPELINE_EXECUTION:
        return _execute_transformation_pipeline_job(job_obj)

    elif job_type == JobType.VIRTUAL_QUERY_EXECUTION:
        return _execute_virtual_query_job(job_obj)

    elif job_type == JobType.MARKETPLACE_SYNC:
        return _execute_marketplace_sync_job(job_obj)

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
        elif resource_type == "VIRTUAL_DATASET":
            from hub.apps.virtualization.models import VirtualDataset
            virtual_dataset = VirtualDataset.objects.get(id=resource_id)
            search_index = SearchIndexer.index_virtual_dataset(virtual_dataset)
            indexed_type = "virtual_dataset"
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
        # Check if it's a VirtualDataset.DoesNotExist
        from hub.apps.virtualization.models import VirtualDataset
        if isinstance(e, VirtualDataset.DoesNotExist):
            raise ValueError(f"VirtualDataset {resource_id} not found")
        # Log and re-raise other exceptions
        logger.error(
            "Search index update job failed",
            exc_info=True,
            job_id=str(job_obj.id),
            resource_type=resource_type,
            resource_id=str(resource_id),
            error=str(e)
        )
        raise


def _execute_odps_normalization_job(job_obj: Job) -> dict:
    """
    Execute ODPS_NORMALIZATION job.

    Normalizes an ODPS contract to HubContract format with progress tracking
    and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with normalization results

    Raises:
        ValueError: If contract_id is missing, contract not found, or contract is not ODPS
        ConnectionError: If normalization service is unavailable
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)

    if not contract_id:
        raise ValueError("Contract ID is required for ODPS_NORMALIZATION job")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract, NormalizationStatus, OriginalSpecType
        from hub.apps.contracts.normalization_service import NormalizationService
        from hub.apps.core.events.service_publishers import ODPSEventPublisher
        from hub.apps.core.events.publisher import EventPublisher

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        # Validate contract is ODPS
        if contract.original_spec_type != OriginalSpecType.ODPS:
            raise ValueError(
                f"Contract {contract_id} is not an ODPS contract "
                f"(spec_type: {contract.original_spec_type})"
            )

        if not contract.original_raw or contract.original_raw.strip() == '':
            raise ValueError(f"Contract {contract_id} has no original_raw content")

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None,
        )

        tenant_id = str(contract.tenant.id) if contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Update progress: Starting normalization (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json['progress_percentage'] = 0.0
        job_obj.details_json['current_phase'] = 'initialization'
        job_obj.details_json['status_message'] = 'Starting ODPS normalization'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Publish normalization started event
        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=0.0,
                current_phase='initialization',
                phase_index=0,
                total_phases=5,
                status_message='Starting ODPS normalization',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_normalization_progress_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS normalization progress event"
            )

        # Update progress: Parsing contract (20%)
        job_obj.details_json['progress_percentage'] = 20.0
        job_obj.details_json['current_phase'] = 'parsing'
        job_obj.details_json['status_message'] = 'Parsing ODPS contract'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=20.0,
                current_phase='parsing',
                phase_index=1,
                total_phases=5,
                status_message='Parsing ODPS contract',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Update progress: Normalizing to HubContract (40%)
        job_obj.details_json['progress_percentage'] = 40.0
        job_obj.details_json['current_phase'] = 'normalization'
        job_obj.details_json['status_message'] = 'Normalizing ODPS to HubContract'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=40.0,
                current_phase='normalization',
                phase_index=2,
                total_phases=5,
                status_message='Normalizing ODPS to HubContract',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Normalize contract using NormalizationService (event publishing integrated)
        # This will publish normalization.started, normalization.completed/failed events
        normalization_service = NormalizationService(
            tenant_id=tenant_id,
            user_id=user_id
        )
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalization_service.normalize_contract(
            raw_contract=contract.original_raw,
            format=contract.original_format,
            spec_type="ODPS",
            tenant_id=tenant_id,
            user_id=user_id,
            contract_id=str(contract_id)  # Contract exists, so events will be published
        )

        # Update progress: Validation (60%)
        job_obj.details_json['progress_percentage'] = 60.0
        job_obj.details_json['current_phase'] = 'validation'
        job_obj.details_json['status_message'] = 'Validating normalized HubContract'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=60.0,
                current_phase='validation',
                phase_index=3,
                total_phases=5,
                status_message='Validating normalized HubContract',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Check normalization status
        if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
            error_message = norm_errors[0] if norm_errors else "ODPS normalization failed"

            # Update progress: Failed (100%)
            job_obj.details_json['progress_percentage'] = 100.0
            job_obj.details_json['current_phase'] = 'failed'
            job_obj.details_json['status_message'] = f'Normalization failed: {error_message}'
            job_obj.save(update_fields=['details_json', 'updated_at'])

            # Publish failure event
            try:
                odps_event_publisher.publish_odps_normalization_progress(
                    contract_id=str(contract_id),
                    progress_percentage=100.0,
                    current_phase='failed',
                    phase_index=5,
                    total_phases=5,
                    status_message=f'Normalization failed: {error_message}',
                    odps_version=contract.original_spec_version,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception:
                pass  # Event publishing failure should not affect job

            raise ValueError(f"ODPS normalization failed: {error_message}")

        # Update progress: Saving results (80%)
        job_obj.details_json['progress_percentage'] = 80.0
        job_obj.details_json['current_phase'] = 'saving'
        job_obj.details_json['status_message'] = 'Saving normalized HubContract'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=80.0,
                current_phase='saving',
                phase_index=4,
                total_phases=5,
                status_message='Saving normalized HubContract',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Update contract with normalized data
        with transaction.atomic():
            contract.hub_contract_json = hub_contract
            contract.normalization_status = norm_status
            contract.save(update_fields=['hub_contract_json', 'normalization_status', 'updated_at'])

        # Update progress: Completed (100%)
        job_obj.details_json['progress_percentage'] = 100.0
        job_obj.details_json['current_phase'] = 'completed'
        job_obj.details_json['status_message'] = 'ODPS normalization completed successfully'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_normalization_progress(
                contract_id=str(contract_id),
                progress_percentage=100.0,
                current_phase='completed',
                phase_index=5,
                total_phases=5,
                status_message='ODPS normalization completed successfully',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            # Publish normalized event
            odps_event_publisher.publish_odps_normalized(
                contract_id=str(contract_id),
                normalization_status=norm_status.value,
                normalization_errors=norm_errors,
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_normalization_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS normalization completion event"
            )

        logger.info(
            "odps_normalization_job_completed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id),
            tenant_id=tenant_id,
            normalization_status=norm_status.value,
            detected_spec_type=detected_spec_type,
            detected_spec_version=detected_spec_version,
            warnings_count=len(norm_warnings),
            message=f"ODPS normalization job completed for contract {contract_id}"
        )

        return {
            'status': 'completed',
            'normalization_status': norm_status.value,
            'detected_spec_type': detected_spec_type,
            'detected_spec_version': detected_spec_version,
            'normalization_errors': norm_errors,
            'normalization_warnings': norm_warnings,
            'contract_id': str(contract_id),
            'warnings_count': len(norm_warnings),
            'errors_count': len(norm_errors)
        }

    except (ValueError, ConnectionError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_normalization_job_failed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id) if 'contract_id' in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS normalization job failed: {str(e)}"
        )
        raise Exception(f"ODPS normalization failed: {str(e)}") from e


def _execute_odps_ref_resolution_job(job_obj: Job) -> dict:
    """
    Execute ODPS_REF_RESOLUTION job.

    Resolves all $ref references in an ODPS contract with progress tracking
    and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with ref resolution results

    Raises:
        ValueError: If contract_id is missing, contract not found, or contract is not ODPS
        ConnectionError: If ref resolution service is unavailable
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)

    if not contract_id:
        raise ValueError("Contract ID is required for ODPS_REF_RESOLUTION job")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract, OriginalSpecType
        from hub.apps.contracts.ref_resolver import RefResolver, ExternalRefHandling
        from hub.apps.contracts.odps_parser import ODPSParser
        from hub.apps.contracts.odps_errors import ODPSRefResolutionError
        from hub.apps.core.events.service_publishers import ODPSEventPublisher
        from hub.apps.core.events.publisher import EventPublisher
        import json

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        # Validate contract is ODPS
        if contract.original_spec_type != OriginalSpecType.ODPS:
            raise ValueError(
                f"Contract {contract_id} is not an ODPS contract "
                f"(spec_type: {contract.original_spec_type})"
            )

        if not contract.original_raw or contract.original_raw.strip() == '':
            raise ValueError(f"Contract {contract_id} has no original_raw content")

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None,
        )

        tenant_id = str(contract.tenant.id) if contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Update progress: Starting ref resolution (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json['progress_percentage'] = 0.0
        job_obj.details_json['current_phase'] = 'initialization'
        job_obj.details_json['status_message'] = 'Starting ODPS $ref resolution'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Publish ref resolution started event
        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=0.0,
                refs_processed=0,
                refs_total=None,
                status_message='Starting ODPS $ref resolution',
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_ref_progress_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS ref progress event"
            )

        # Update progress: Parsing document (10%)
        job_obj.details_json['progress_percentage'] = 10.0
        job_obj.details_json['current_phase'] = 'parsing'
        job_obj.details_json['status_message'] = 'Parsing ODPS document'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=10.0,
                refs_processed=0,
                refs_total=None,
                status_message='Parsing ODPS document',
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Parse ODPS document
        format_str = contract.original_format.lower() if contract.original_format else 'json'
        odps_doc = ODPSParser.parse(
            content=contract.original_raw,
            format=format_str
        )

        # Update progress: Analyzing refs (20%)
        job_obj.details_json['progress_percentage'] = 20.0
        job_obj.details_json['current_phase'] = 'analyzing'
        job_obj.details_json['status_message'] = 'Analyzing $ref references'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=20.0,
                refs_processed=0,
                refs_total=None,
                status_message='Analyzing $ref references',
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Count refs for progress tracking (approximate)
        def count_refs(obj, count=0):
            """Recursively count $ref references in document"""
            if isinstance(obj, dict):
                if "$ref" in obj:
                    count += 1
                for value in obj.values():
                    count = count_refs(value, count)
            elif isinstance(obj, list):
                for item in obj:
                    count = count_refs(item, count)
            return count

        total_refs = count_refs(odps_doc)
        job_obj.details_json['refs_total'] = total_refs
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Update progress: Resolving refs (30%)
        job_obj.details_json['progress_percentage'] = 30.0
        job_obj.details_json['current_phase'] = 'resolving'
        job_obj.details_json['status_message'] = f'Resolving {total_refs} $ref references'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=30.0,
                refs_processed=0,
                refs_total=total_refs,
                status_message=f'Resolving {total_refs} $ref references',
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Get external ref handling mode from job details (default: RESOLVE)
        external_ref_handling_str = job_obj.details_json.get('external_ref_handling', 'resolve')
        try:
            external_ref_handling = ExternalRefHandling(external_ref_handling_str.lower())
        except ValueError:
            external_ref_handling = ExternalRefHandling.RESOLVE

        # Create resolver
        resolver = RefResolver(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Resolve all refs
        try:
            original_doc, resolved_doc = resolver.resolve_all_refs(
                document=odps_doc,
                preserve_original=True,
                external_ref_handling=external_ref_handling
            )
        except ODPSRefResolutionError as e:
            # Update progress: Failed (100%)
            job_obj.details_json['progress_percentage'] = 100.0
            job_obj.details_json['current_phase'] = 'failed'
            job_obj.details_json['status_message'] = f'$ref resolution failed: {str(e)}'
            job_obj.save(update_fields=['details_json', 'updated_at'])

            # Publish failure event
            try:
                odps_event_publisher.publish_odps_ref_failed(
                    contract_id=str(contract_id),
                    ref_path=getattr(e, 'ref_path', 'unknown'),
                    ref_type=getattr(e, 'ref_type', 'unknown'),
                    error_message=str(e),
                    error_code=getattr(e, 'error_code', None),
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception:
                pass  # Event publishing failure should not affect job

            raise ValueError(f"ODPS $ref resolution failed: {str(e)}")

        # Update progress: Saving results (90%)
        job_obj.details_json['progress_percentage'] = 90.0
        job_obj.details_json['current_phase'] = 'saving'
        job_obj.details_json['status_message'] = 'Saving resolved document'
        job_obj.details_json['refs_processed'] = total_refs
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=90.0,
                refs_processed=total_refs,
                refs_total=total_refs,
                status_message='Saving resolved document',
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Serialize resolved document
        if format_str == 'yaml':
            import yaml
            resolved_raw = yaml.dump(resolved_doc, default_flow_style=False, sort_keys=False)
        else:
            resolved_raw = json.dumps(resolved_doc, indent=2)

        # Update contract with resolved document
        with transaction.atomic():
            # Store resolved document in original_raw_resolved if field exists, otherwise update original_raw
            if hasattr(contract, 'original_raw_resolved'):
                contract.original_raw_resolved = resolved_raw
                contract.save(update_fields=['original_raw_resolved', 'updated_at'])
            else:
                # Fallback: update original_raw (this replaces the original, which may not be desired)
                # In production, original_raw_resolved should be available
                contract.original_raw = resolved_raw
                contract.save(update_fields=['original_raw', 'updated_at'])

        # Update progress: Completed (100%)
        job_obj.details_json['progress_percentage'] = 100.0
        job_obj.details_json['current_phase'] = 'completed'
        job_obj.details_json['status_message'] = f'Successfully resolved {total_refs} $ref references'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Calculate duration (use started_at if available, otherwise use job creation time)
        if job_obj.started_at:
            duration = (timezone.now() - job_obj.started_at).total_seconds()
        elif job_obj.created_at:
            duration = (timezone.now() - job_obj.created_at).total_seconds()
        else:
            duration = 0.0  # Fallback to 0 if neither is available
        duration_ms = int(duration * 1000)

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_ref_progress(
                contract_id=str(contract_id),
                progress_percentage=100.0,
                refs_processed=total_refs,
                refs_total=total_refs,
                status_message=f'Successfully resolved {total_refs} $ref references',
                tenant_id=tenant_id,
                user_id=user_id,
            )

            # Publish resolved event
            odps_event_publisher.publish_odps_ref_resolved(
                contract_id=str(contract_id),
                ref_path="all",
                ref_type="all",
                resolution_status="completed",
                ref_count=total_refs,
                duration_ms=duration_ms,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_ref_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS ref resolution completion event"
            )

        logger.info(
            "odps_ref_resolution_job_completed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id),
            tenant_id=tenant_id,
            refs_resolved=total_refs,
            external_ref_handling=external_ref_handling.value,
            message=f"ODPS $ref resolution job completed for contract {contract_id}"
        )

        return {
            'status': 'completed',
            'refs_resolved': total_refs,
            'external_ref_handling': external_ref_handling.value,
            'contract_id': str(contract_id),
            'format': format_str
        }

    except (ValueError, ODPSRefResolutionError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_ref_resolution_job_failed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id) if 'contract_id' in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS $ref resolution job failed: {str(e)}"
        )
        raise Exception(f"ODPS $ref resolution failed: {str(e)}") from e


def _execute_odps_export_job(job_obj: Job) -> dict:
    """
    Execute ODPS_EXPORT job.

    Generates ODPS document from HubContract format with progress tracking
    and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with export results

    Raises:
        ValueError: If contract_id is missing, contract not found, or contract has no hub_contract_json
        Exception: For other errors
    """
    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)

    if not contract_id:
        raise ValueError("Contract ID is required for ODPS_EXPORT job")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract, OriginalSpecType, OriginalFormat
        from hub.apps.contracts.odps_generator import (
            generate_odps_from_hubcontract,
            format_odps_as_json,
            format_odps_as_yaml,
        )
        from hub.apps.contracts.normalization import parse_contract
        from hub.apps.core.events.service_publishers import ODPSEventPublisher
        from hub.apps.core.events.publisher import EventPublisher
        import json

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        # Validate contract has hub_contract_json
        if not contract.hub_contract_json:
            raise ValueError(
                f"Contract {contract_id} has no hub_contract_json. "
                "Cannot export as ODPS format."
            )

        # Get export options from job details
        export_format = job_obj.details_json.get('export_format', 'json').lower()
        if export_format not in ['json', 'yaml']:
            export_format = 'json'  # Default to JSON

        odps_version = job_obj.details_json.get('odps_version', '4.1')

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None,
        )

        tenant_id = str(contract.tenant.id) if contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Update progress: Starting export (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json['progress_percentage'] = 0.0
        job_obj.details_json['current_phase'] = 'initialization'
        job_obj.details_json['status_message'] = 'Starting ODPS export'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Publish export started event
        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=0.0,
                current_phase='initialization',
                status_message='Starting ODPS export',
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_export_progress_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS export progress event"
            )

        # Update progress: Preparing data (10%)
        job_obj.details_json['progress_percentage'] = 10.0
        job_obj.details_json['current_phase'] = 'preparation'
        job_obj.details_json['status_message'] = 'Preparing HubContract data'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=10.0,
                current_phase='preparation',
                status_message='Preparing HubContract data',
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Get original ODCS contract if available (for embedding in ODPS)
        original_odcs_contract = None
        if contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
            try:
                original_odcs_contract = parse_contract(
                    contract.original_raw, contract.original_format
                )
            except Exception:
                # If parsing fails, continue without original ODCS
                pass

        # Update progress: Generating ODPS (30%)
        job_obj.details_json['progress_percentage'] = 30.0
        job_obj.details_json['current_phase'] = 'generation'
        job_obj.details_json['status_message'] = 'Generating ODPS document'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=30.0,
                current_phase='generation',
                status_message='Generating ODPS document',
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Generate ODPS document
        odps_doc = generate_odps_from_hubcontract(
            hub_contract=contract.hub_contract_json,
            target_version=odps_version,
            original_odcs_contract=original_odcs_contract,
            original_odcs_url=None,
        )

        # Update progress: Formatting output (70%)
        job_obj.details_json['progress_percentage'] = 70.0
        job_obj.details_json['current_phase'] = 'formatting'
        job_obj.details_json['status_message'] = f'Formatting ODPS as {export_format.upper()}'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=70.0,
                current_phase='formatting',
                status_message=f'Formatting ODPS as {export_format.upper()}',
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Format output
        if export_format == 'yaml':
            odps_raw = format_odps_as_yaml(odps_doc)
        else:
            odps_raw = format_odps_as_json(odps_doc)

        # Calculate bytes for progress tracking
        bytes_processed = len(odps_raw.encode('utf-8'))
        bytes_total = bytes_processed  # Total is same as processed for export

        # Update progress: Saving results (90%)
        job_obj.details_json['progress_percentage'] = 90.0
        job_obj.details_json['current_phase'] = 'saving'
        job_obj.details_json['status_message'] = 'Saving exported ODPS document'
        job_obj.details_json['bytes_processed'] = bytes_processed
        job_obj.details_json['bytes_total'] = bytes_total
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=90.0,
                current_phase='saving',
                bytes_processed=bytes_processed,
                bytes_total=bytes_total,
                status_message='Saving exported ODPS document',
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Update contract with exported ODPS (store in original_raw for now)
        # Note: This preserves the original_raw if it exists, but stores the exported ODPS
        # In a production system, you might want to store this separately or in a versioned format
        with transaction.atomic():
            # Store exported ODPS in original_raw (or create a new field for exported content)
            contract.original_raw = odps_raw
            # Convert export_format string to OriginalFormat enum
            if export_format == 'yaml':
                contract.original_format = OriginalFormat.YAML
            else:
                contract.original_format = OriginalFormat.JSON
            contract.original_spec_type = OriginalSpecType.ODPS
            contract.original_spec_version = odps_version
            contract.save(update_fields=[
                'original_raw',
                'original_format',
                'original_spec_type',
                'original_spec_version',
                'updated_at'
            ])

        # Update progress: Completed (100%)
        job_obj.details_json['progress_percentage'] = 100.0
        job_obj.details_json['current_phase'] = 'completed'
        job_obj.details_json['status_message'] = 'ODPS export completed successfully'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_export_progress(
                contract_id=str(contract_id),
                export_format=export_format,
                progress_percentage=100.0,
                current_phase='completed',
                bytes_processed=bytes_processed,
                bytes_total=bytes_total,
                status_message='ODPS export completed successfully',
                odps_version=odps_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_export_event_publish_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS export completion event"
            )

        logger.info(
            "odps_export_job_completed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id),
            tenant_id=tenant_id,
            export_format=export_format,
            odps_version=odps_version,
            bytes_processed=bytes_processed,
            message=f"ODPS export job completed for contract {contract_id}"
        )

        # Record export success metric (Task 6.6.4)
        try:
            from hub.apps.observability.otel_metrics import odps_export_total
            odps_export_total.labels(
                status="success",
                format=export_format,
                tenant_id=tenant_id or "unknown"
            ).inc()
        except Exception:
            pass  # Don't fail on metrics recording

        return {
            'status': 'completed',
            'export_format': export_format,
            'odps_version': odps_version,
            'contract_id': str(contract_id),
            'bytes_processed': bytes_processed,
            'bytes_total': bytes_total,
        }

    except (ValueError, ConnectionError):
        # Record export failure metric (Task 6.6.4)
        try:
            from hub.apps.observability.otel_metrics import odps_export_total
            tenant_id = str(contract.tenant.id) if 'contract' in locals() and contract.tenant else "unknown"
            export_format = job_obj.details_json.get('export_format', 'unknown') if 'job_obj' in locals() else "unknown"
            odps_export_total.labels(
                status="failure",
                format=export_format,
                tenant_id=tenant_id
            ).inc()
        except Exception:
            pass  # Don't fail on metrics recording
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_export_job_failed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id) if 'contract_id' in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS export job failed: {str(e)}"
        )

        # Record export failure metric (Task 6.6.4)
        try:
            from hub.apps.observability.otel_metrics import odps_export_total
            tenant_id = str(contract.tenant.id) if 'contract' in locals() and contract.tenant else "unknown"
            export_format = job_obj.details_json.get('export_format', 'unknown') if 'job_obj' in locals() else "unknown"
            odps_export_total.labels(
                status="failure",
                format=export_format,
                tenant_id=tenant_id
            ).inc()
        except Exception:
            pass  # Don't fail on metrics recording

        raise Exception(f"ODPS export failed: {str(e)}") from e


def _execute_odps_semantic_mapping_job(job_obj: Job) -> dict:
    """
    Execute ODPS_SEMANTIC_MAPPING job.

    Maps an ODPS contract to RDF (semantic representation) with progress tracking
    and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with semantic mapping results

    Raises:
        ValueError: If contract_id is missing, contract not found, or contract is not ODPS
        ConnectionError: If semantic service is unavailable
        Exception: For other errors
    """
    import time
    start_time = time.time()

    # Get contract ID from resource_id
    contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if contract_id is not None:
        contract_id = str(contract_id)

    if not contract_id:
        raise ValueError("Contract ID is required for ODPS_SEMANTIC_MAPPING job")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract, OriginalSpecType
        from hub.apps.semantic.utils import map_odps_to_semantic
        from hub.apps.core.events.service_publishers import ODPSEventPublisher
        from hub.apps.core.events.publisher import EventPublisher

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"Contract {contract_id} not found")

        # Validate contract is ODPS
        if contract.original_spec_type != OriginalSpecType.ODPS:
            raise ValueError(
                f"Contract {contract_id} is not an ODPS contract "
                f"(spec_type: {contract.original_spec_type})"
            )

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=str(contract.tenant.id) if contract.tenant else None,
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None,
        )

        tenant_id = str(contract.tenant.id) if contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Update progress: Starting semantic mapping (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json['progress_percentage'] = 0.0
        job_obj.details_json['current_phase'] = 'initialization'
        job_obj.details_json['status_message'] = 'Starting ODPS semantic mapping'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Publish semantic mapping started event
        try:
            odps_event_publisher.publish_odps_semantic_mapping_progress(
                contract_id=str(contract_id),
                progress_percentage=0.0,
                current_phase='initialization',
                phase_index=0,
                total_phases=4,
                status_message='Starting ODPS semantic mapping',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_semantic_mapping_progress_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS semantic mapping progress event"
            )

        # Update progress: Extracting ODPS product (25%)
        job_obj.details_json['progress_percentage'] = 25.0
        job_obj.details_json['current_phase'] = 'extraction'
        job_obj.details_json['status_message'] = 'Extracting ODPS product structure'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_semantic_mapping_progress(
                contract_id=str(contract_id),
                progress_percentage=25.0,
                current_phase='extraction',
                phase_index=1,
                total_phases=4,
                status_message='Extracting ODPS product structure',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Update progress: Mapping to RDF (50%)
        job_obj.details_json['progress_percentage'] = 50.0
        job_obj.details_json['current_phase'] = 'mapping'
        job_obj.details_json['status_message'] = 'Mapping ODPS to RDF'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_semantic_mapping_progress(
                contract_id=str(contract_id),
                progress_percentage=50.0,
                current_phase='mapping',
                phase_index=2,
                total_phases=4,
                status_message='Mapping ODPS to RDF',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Map ODPS to semantic (RDF)
        semantic_resource = map_odps_to_semantic(
            contract=contract,
            tenant=contract.tenant,
            use_cache=False
        )

        # Update progress: Saving semantic resource (75%)
        job_obj.details_json['progress_percentage'] = 75.0
        job_obj.details_json['current_phase'] = 'saving'
        job_obj.details_json['status_message'] = 'Saving semantic resource'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_semantic_mapping_progress(
                contract_id=str(contract_id),
                progress_percentage=75.0,
                current_phase='saving',
                phase_index=3,
                total_phases=4,
                status_message='Saving semantic resource',
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Check if mapping was successful
        if not semantic_resource:
            # Mapping was skipped (e.g., no ODPS product data)
            raise ValueError(
                f"ODPS semantic mapping was skipped for contract {contract_id}. "
                "Contract may not have valid ODPS product data."
            )

        # Update progress: Completed (100%)
        job_obj.details_json['progress_percentage'] = 100.0
        job_obj.details_json['current_phase'] = 'completed'
        job_obj.details_json['status_message'] = 'ODPS semantic mapping completed'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Get semantic resource metadata
        triples_count = 0
        semantic_status = 'UNKNOWN'
        if semantic_resource.metadata_json:
            triples_count = semantic_resource.metadata_json.get('triples_count', 0)
        if semantic_resource.status:
            semantic_status = semantic_resource.status

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_semantic_mapped(
                contract_id=str(contract_id),
                semantic_resource_id=str(semantic_resource.id),
                semantic_uri=semantic_resource.uri,
                triples_count=triples_count,
                semantic_status=semantic_status,
                duration_ms=duration_ms,
                odps_version=contract.original_spec_version,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_semantic_mapped_event_failed",
                job_id=str(job_obj.id),
                contract_id=str(contract_id),
                error=str(e),
                message="Failed to publish ODPS semantic mapped event"
            )

        logger.info(
            "odps_semantic_mapping_job_completed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id),
            tenant_id=tenant_id,
            semantic_resource_id=str(semantic_resource.id),
            triples_count=triples_count,
            message=f"ODPS semantic mapping job completed for contract {contract_id}"
        )

        return {
            'status': 'completed',
            'contract_id': str(contract_id),
            'semantic_resource_id': str(semantic_resource.id),
            'semantic_uri': semantic_resource.uri,
            'triples_count': triples_count,
            'semantic_status': semantic_status,
            'duration_ms': duration_ms,
        }

    except (ValueError, ConnectionError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_semantic_mapping_job_failed",
            job_id=str(job_obj.id),
            contract_id=str(contract_id) if 'contract_id' in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS semantic mapping job failed: {str(e)}"
        )
        raise Exception(f"ODPS semantic mapping failed: {str(e)}") from e


def _execute_odps_linking_job(job_obj: Job) -> dict:
    """
    Execute ODPS_LINKING job.

    Validates and establishes bidirectional links between ODPS and ODCS contracts
    with progress tracking and event publishing.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with linking results

    Raises:
        ValueError: If contract IDs are missing, contracts not found, or validation fails
        Exception: For other errors
    """
    import time
    start_time = time.time()

    # Get contract IDs from job details
    odps_contract_id = job_obj.details_json.get('odps_contract_id')
    odcs_contract_id = job_obj.details_json.get('odcs_contract_id')

    # If not in details, try resource_id (for backward compatibility)
    if not odps_contract_id:
        odps_contract_id = job_obj.resource_id

    # Convert to string if it's a UUID object, handle None case
    if odps_contract_id is not None:
        odps_contract_id = str(odps_contract_id)
    if odcs_contract_id is not None:
        odcs_contract_id = str(odcs_contract_id)

    if not odps_contract_id:
        raise ValueError("ODPS contract ID is required for ODPS_LINKING job")
    if not odcs_contract_id:
        raise ValueError("ODCS contract ID is required for ODPS_LINKING job")

    try:
        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract, OriginalSpecType, NormalizationStatus
        from hub.apps.contracts.linking_validation import validate_linking, LinkingValidationError
        from hub.apps.contracts.services import ContractService
        from hub.apps.core.events.service_publishers import ODPSEventPublisher
        from hub.apps.core.events.publisher import EventPublisher

        # Get contracts
        try:
            odps_contract = Contract.objects.get(id=odps_contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"ODPS contract {odps_contract_id} not found")

        try:
            odcs_contract = Contract.objects.get(id=odcs_contract_id)
        except Contract.DoesNotExist:
            raise ValueError(f"ODCS contract {odcs_contract_id} not found")

        # Get tenant and user IDs
        tenant_id = str(odps_contract.tenant.id) if odps_contract.tenant else None
        user_id = str(job_obj.created_by.id) if job_obj.created_by else None

        # Initialize event publisher
        odps_event_publisher = ODPSEventPublisher()
        odps_event_publisher._event_publisher = EventPublisher(
            service_name="job_service",
            tenant_id=tenant_id,
            user_id=user_id,
        )

        # Update progress: Starting linking (0%)
        job_obj.details_json = job_obj.details_json or {}
        job_obj.details_json['progress_percentage'] = 0.0
        job_obj.details_json['current_phase'] = 'initialization'
        job_obj.details_json['status_message'] = 'Starting ODPS linking'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Publish linking started event
        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="starting",
                progress_percentage=0.0,
                current_phase="initialization",
                status_message="Starting ODPS linking",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_linking_status_event_failed",
                job_id=str(job_obj.id),
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                error=str(e),
                message="Failed to publish ODPS linking status event"
            )

        # Update progress: Validating contracts (20%)
        job_obj.details_json['progress_percentage'] = 20.0
        job_obj.details_json['current_phase'] = 'validation'
        job_obj.details_json['status_message'] = 'Validating contracts for linking'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="validating",
                progress_percentage=20.0,
                current_phase="validation",
                status_message="Validating contracts for linking",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Validate contracts for linking
        try:
            validated_odps_contract, validated_odcs_contract = validate_linking(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                tenant_id=tenant_id
            )
        except LinkingValidationError as e:
            # Update progress: Validation failed (100%)
            job_obj.details_json['progress_percentage'] = 100.0
            job_obj.details_json['current_phase'] = 'failed'
            job_obj.details_json['status_message'] = f'Linking validation failed: {str(e)}'
            job_obj.save(update_fields=['details_json', 'updated_at'])

            # Publish failure event
            try:
                odps_event_publisher.publish_odps_linking_status(
                    odps_contract_id=odps_contract_id,
                    odcs_contract_id=odcs_contract_id,
                    status="failed",
                    progress_percentage=100.0,
                    current_phase="validation",
                    validation_passed=False,
                    validation_errors=[str(e)],
                    status_message=f"Linking validation failed: {str(e)}",
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception:
                pass  # Event publishing failure should not affect job

            raise ValueError(f"ODPS linking validation failed: {str(e)}")

        # Update progress: Validation passed (40%)
        job_obj.details_json['progress_percentage'] = 40.0
        job_obj.details_json['current_phase'] = 'validation'
        job_obj.details_json['status_message'] = 'Linking validation passed'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="validating",
                progress_percentage=40.0,
                current_phase="validation",
                validation_passed=True,
                status_message="Linking validation passed",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Update progress: Establishing links (60%)
        job_obj.details_json['progress_percentage'] = 60.0
        job_obj.details_json['current_phase'] = 'linking'
        job_obj.details_json['status_message'] = 'Establishing bidirectional links'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="linking",
                progress_percentage=60.0,
                current_phase="linking",
                status_message="Establishing bidirectional links",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Establish bidirectional links using ContractService
        contract_service = ContractService(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Use the service method to link contracts (this handles the actual linking logic)
        linked_odps_contract = contract_service.link_odps_to_odcs(
            odcs_contract_id=odcs_contract_id,
            odps_contract_id=odps_contract_id,
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Refresh contracts from DB to get updated links
        validated_odps_contract.refresh_from_db()
        validated_odcs_contract.refresh_from_db()

        # Verify links were established
        odps_hub_contract = validated_odps_contract.hub_contract_json or {}
        odcs_hub_contract = validated_odcs_contract.hub_contract_json or {}
        odps_extensions = odps_hub_contract.get("extensions", {})
        odcs_extensions = odcs_hub_contract.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        odcs_x_odps = odcs_extensions.get("x_odps", {})

        odps_to_odcs_link = odps_x_odps.get("odcs_link")
        odcs_to_odps_link = odcs_x_odps.get("odps_link")

        if not odps_to_odcs_link or str(odps_to_odcs_link) != odcs_contract_id:
            raise ValueError(
                f"ODPS → ODCS link not established correctly. "
                f"Expected {odcs_contract_id}, got {odps_to_odcs_link}"
            )

        if not odcs_to_odps_link or str(odcs_to_odps_link) != odps_contract_id:
            raise ValueError(
                f"ODCS → ODPS link not established correctly. "
                f"Expected {odps_contract_id}, got {odcs_to_odps_link}"
            )

        # Update progress: Saving results (80%)
        job_obj.details_json['progress_percentage'] = 80.0
        job_obj.details_json['current_phase'] = 'saving'
        job_obj.details_json['status_message'] = 'Links established successfully'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="linking",
                progress_percentage=80.0,
                current_phase="saving",
                status_message="Links established successfully",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass  # Event publishing failure should not affect job

        # Update progress: Completed (100%)
        job_obj.details_json['progress_percentage'] = 100.0
        job_obj.details_json['current_phase'] = 'completed'
        job_obj.details_json['status_message'] = 'ODPS linking completed successfully'
        job_obj.save(update_fields=['details_json', 'updated_at'])

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Publish completion event
        try:
            odps_event_publisher.publish_odps_linking_status(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                status="completed",
                progress_percentage=100.0,
                current_phase="completed",
                validation_passed=True,
                link_type="bidirectional",
                status_message="ODPS linking completed successfully",
                tenant_id=tenant_id,
                user_id=user_id,
            )

            # Publish linked event
            odps_event_publisher.publish_odps_linked(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                link_type="bidirectional",
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "odps_linking_event_publish_failed",
                job_id=str(job_obj.id),
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                error=str(e),
                message="Failed to publish ODPS linking completion event"
            )

        # Send notification email for ODPS linking status (Task 8.4.4)
        try:
            from hub.apps.notifications.tasks import send_odps_linking_status_email
            send_odps_linking_status_email.delay(
                odps_contract_id=odps_contract_id,
                status="completed",
                status_message="ODPS linking completed successfully",
                odcs_contract_id=odcs_contract_id,
                progress_percentage=100.0,
                current_phase="completed",
                validation_passed=True,
                user_id=user_id,
                tenant_id=tenant_id
            )
        except Exception as e:
            # Log but don't fail job if notification fails
            logger.warning(
                "odps_linking_notification_failed",
                job_id=str(job_obj.id),
                odps_contract_id=odps_contract_id,
                error=str(e),
                message="Failed to send ODPS linking status notification (non-critical)"
            )

        logger.info(
            "odps_linking_job_completed",
            job_id=str(job_obj.id),
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            tenant_id=tenant_id,
            duration_ms=duration_ms,
            message=f"ODPS linking job completed for contracts {odps_contract_id} ↔ {odcs_contract_id}"
        )

        return {
            'status': 'completed',
            'odps_contract_id': odps_contract_id,
            'odcs_contract_id': odcs_contract_id,
            'link_type': 'bidirectional',
            'duration_ms': duration_ms,
        }

    except (ValueError, LinkingValidationError):
        raise  # Re-raise specific errors
    except Exception as e:
        # Wrap other exceptions
        logger.error(
            "odps_linking_job_failed",
            job_id=str(job_obj.id),
            odps_contract_id=odps_contract_id if 'odps_contract_id' in locals() else None,
            odcs_contract_id=odcs_contract_id if 'odcs_contract_id' in locals() else None,
            error=str(e),
            exc_info=True,
            message=f"ODPS linking job failed: {str(e)}"
        )
        raise Exception(f"ODPS linking failed: {str(e)}") from e


@transaction.atomic
def _execute_transformation_pipeline_job(job_obj: Job) -> dict:
    """
    Execute transformation pipeline execution job.

    Uses transaction.atomic for database operations and implements
    idempotency checking using execution_id as idempotency key.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with execution results

    Raises:
        ValueError: For validation errors
        Exception: For execution errors
    """
    from hub.apps.transformation.models import PipelineExecution, ExecutionStatus
    from hub.apps.transformation.services import TransformationService
    from hub.apps.transformation.exceptions import (
        TransformationExecutionError,
        TransformationValidationError
    )

    execution_id = job_obj.resource_id
    if not execution_id:
        raise ValueError("execution_id is required in resource_id")

    try:
        # Use select_for_update to prevent concurrent execution
        execution = PipelineExecution.objects.select_for_update().get(id=execution_id)
    except PipelineExecution.DoesNotExist:
        raise ValueError(f"PipelineExecution {execution_id} not found")

    # Idempotency check: if execution is already in terminal state, return existing result
    # This uses execution_id as the idempotency key (as per requirements)
    if execution.is_terminal():
        logger.warning(
            "transformation_pipeline_execution_already_terminal",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            status=execution.status,
            message=f"Execution {execution_id} is already in terminal state: {execution.status} (idempotency check)"
        )
        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "skipped": True,
            "reason": "Already in terminal state (idempotent retry)",
            "idempotency_key": execution.idempotency_key or str(execution.id)
        }

    # Sync execution status from job before starting
    execution.sync_status_from_job()

    # Check if execution was cancelled
    if execution.status == ExecutionStatus.CANCELLED:
        logger.info(
            "transformation_pipeline_execution_cancelled",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            message=f"Execution {execution_id} was cancelled, skipping job execution"
        )
        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "skipped": True,
            "reason": "Execution was cancelled"
        }

    # Mark execution as started
    execution.mark_started()
    execution.add_log_entry(f"Job {job_obj.id} started processing", "INFO")

    try:
        # Get execution details from job
        details = job_obj.details_json or {}
        pipeline_id = details.get("pipeline_id")
        asset_id = details.get("asset_id")
        execution_mode = details.get("execution_mode", "ASYNC")

        if not pipeline_id or not asset_id:
            raise ValueError("pipeline_id and asset_id are required in job details")

        # Initialize service
        service = TransformationService(
            tenant_id=str(execution.pipeline.tenant_id),
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None
        )

        # Execute pipeline synchronously (job worker handles async execution)
        # The actual transformation logic would be called here
        execution.add_log_entry("Executing pipeline transformation steps", "INFO")

        # Run quality check on input asset
        input_quality_metrics = service._run_quality_check(
            asset_id,
            str(execution.pipeline.tenant_id),
            execution
        )

        # Run compliance check on input asset
        input_compliance_status = service._run_compliance_check(
            asset_id,
            str(execution.pipeline.tenant_id),
            execution
        )

        # Execute pipeline (sync execution within async job)
        result_data = service._execute_pipeline_sync(
            execution.pipeline,
            asset_id,
            execution,
            str(execution.pipeline.tenant_id),
            str(job_obj.created_by.id) if job_obj.created_by else None
        )

        # Store metrics and result asset
        from hub.apps.assets.models import Asset
        source_asset = Asset.objects.get(id=asset_id, tenant_id=str(execution.pipeline.tenant_id))

        execution.mark_completed(
            result_asset=source_asset,  # Placeholder: use source asset as result for now
            metrics={
                "execution_mode": execution_mode,
                "input_quality_metrics": input_quality_metrics,
                "input_compliance_status": input_compliance_status,
                **result_data
            }
        )

        # Sync execution status from job to ensure consistency
        execution.sync_status_from_job()

        # Publish completion event
        duration_ms = int(execution.get_duration_seconds() * 1000) if execution.get_duration_seconds() else None
        try:
            service.publish_pipeline_execution_completed(
                pipeline_id=str(execution.pipeline.id),
                execution_id=str(execution.id),
                duration_ms=duration_ms,
                records_processed=result_data.get("rows_processed"),
                quality_metrics=input_quality_metrics,
                tenant_id=str(execution.pipeline.tenant_id),
                user_id=str(job_obj.created_by.id) if job_obj.created_by else None
            )
        except Exception as e:
            logger.warning(
                f"Failed to publish pipeline execution completed event: {e}",
                extra={
                    "execution_id": str(execution.id),
                    "error": str(e)
                },
                exc_info=True
            )

        # Create audit log for completion
        try:
            from hub.apps.audit.utils import create_audit_event
            duration_seconds = execution.get_duration_seconds()
            duration_ms = int(duration_seconds * 1000) if duration_seconds else None

            completion_details = {
                "execution_id": str(execution.id),
                "pipeline_id": str(execution.pipeline.id),
                "asset_id": asset_id,
                "execution_mode": execution.execution_mode.value if hasattr(execution.execution_mode, 'value') else str(execution.execution_mode),
                "duration_seconds": duration_seconds,
                "duration_ms": duration_ms,
                "quality_metrics": input_quality_metrics
            }

            # Add result_asset_id if available
            if execution.result_asset:
                completion_details["result_asset_id"] = str(execution.result_asset.id)

            # Add records_processed if available
            if result_data and "rows_processed" in result_data:
                completion_details["records_processed"] = result_data["rows_processed"]

            create_audit_event(
                resource_type="TRANSFORMATION_PIPELINE",
                action="EXECUTION_COMPLETED",
                actor_user=job_obj.created_by,
                tenant=execution.pipeline.tenant,
                resource_id=str(execution.pipeline.id),
                result="SUCCESS",
                details=completion_details
            )
        except Exception as e:
            logger.warning(
                f"Failed to create audit log for execution completion: {e}",
                extra={
                    "execution_id": str(execution.id),
                    "error": str(e)
                },
                exc_info=True
            )

        # Send notification email for completion
        try:
            from hub.apps.notifications.tasks import send_pipeline_execution_completion_email
            send_pipeline_execution_completion_email.delay(str(execution.id))
        except Exception as e:
            logger.warning(
                f"Failed to send pipeline execution completion notification: {e}",
                extra={
                    "execution_id": str(execution.id),
                    "error": str(e)
                },
                exc_info=True
            )

        logger.info(
            "transformation_pipeline_execution_completed",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            pipeline_id=str(execution.pipeline.id),
            message=f"Transformation pipeline execution {execution_id} completed successfully"
        )

        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "duration_seconds": execution.get_duration_seconds(),
            "rows_processed": result_data.get("rows_processed", 0)
        }

    except (TransformationValidationError, TransformationExecutionError) as e:
        error_msg = str(e)
        duration_ms = int(execution.get_duration_seconds() * 1000) if execution.get_duration_seconds() else None

        # Execute compensation logic for multi-service operations
        try:
            from hub.apps.transformation.compensation import TransformationPipelineCompensation
            compensation = TransformationPipelineCompensation(execution)
            compensation_result = compensation.compensate(
                rollback_execution=True,
                cleanup_job=True,  # Cleanup job on failure
                cleanup_result_asset=True,
                publish_compensation_events=True
            )
            logger.info(
                f"Compensation completed for job execution {execution.id}",
                extra={
                    "execution_id": str(execution.id),
                    "job_id": str(job_obj.id),
                    "compensation_result": compensation_result
                }
            )
        except Exception as comp_error:
            logger.exception(
                f"Compensation failed for job execution {execution.id}: {comp_error}",
                extra={
                    "execution_id": str(execution.id),
                    "job_id": str(job_obj.id),
                    "compensation_error": str(comp_error)
                }
            )
            # Still mark execution as failed even if compensation fails
            execution.mark_failed(error_message=error_msg)

        # Sync execution status from job to ensure consistency
        execution.sync_status_from_job()

        # Publish failure event
        try:
            service = TransformationService(
                tenant_id=str(execution.pipeline.tenant_id),
                user_id=str(job_obj.created_by.id) if job_obj.created_by else None
            )
            service.publish_pipeline_execution_failed(
                pipeline_id=str(execution.pipeline.id),
                execution_id=str(execution.id),
                error_message=error_msg,
                error_code=getattr(e, 'error_code', None),
                error_details=getattr(e, 'details', None),
                duration_ms=duration_ms,
                tenant_id=str(execution.pipeline.tenant_id),
                user_id=str(job_obj.created_by.id) if job_obj.created_by else None
            )
        except Exception as e2:
            logger.warning(
                f"Failed to publish pipeline execution failed event: {e2}",
                extra={
                    "execution_id": str(execution.id),
                    "error": str(e2)
                },
                exc_info=True
            )

        # Create audit log for failure
        try:
            from hub.apps.audit.utils import create_audit_event
            duration_seconds = execution.get_duration_seconds()
            duration_ms = int(duration_seconds * 1000) if duration_seconds else None

            failure_details = {
                "execution_id": str(execution.id),
                "pipeline_id": str(execution.pipeline.id),
                "asset_id": asset_id,
                "execution_mode": execution.execution_mode.value if hasattr(execution.execution_mode, 'value') else str(execution.execution_mode),
                "error_message": error_msg,
                "error_code": getattr(e, 'error_code', None),
                "duration_seconds": duration_seconds,
                "duration_ms": duration_ms
            }

            # Add error details if available
            error_details = getattr(e, 'details', None)
            if error_details:
                failure_details["error_details"] = error_details

            create_audit_event(
                resource_type="TRANSFORMATION_PIPELINE",
                action="EXECUTION_FAILED",
                actor_user=job_obj.created_by,
                tenant=execution.pipeline.tenant,
                resource_id=str(execution.pipeline.id),
                result="FAILURE",
                details=failure_details
            )
        except Exception as e2:
            logger.warning(
                f"Failed to create audit log for execution failure: {e2}",
                extra={
                    "execution_id": str(execution.id),
                    "error": str(e2)
                },
                exc_info=True
            )

        # Send notification email for failure
        try:
            from hub.apps.notifications.tasks import send_pipeline_execution_failure_email
            send_pipeline_execution_failure_email.delay(str(execution.id))
        except Exception as e2:
            logger.warning(
                f"Failed to send pipeline execution failure notification: {e2}",
                extra={
                    "execution_id": str(execution.id),
                    "error": str(e2)
                },
                exc_info=True
            )

        logger.error(
            "transformation_pipeline_execution_failed",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            pipeline_id=str(execution.pipeline.id),
            error=error_msg,
            error_code=getattr(e, 'error_code', None),
            exc_info=True,
            message=f"Transformation pipeline execution {execution_id} failed: {error_msg}"
        )
        raise Exception(f"Transformation pipeline execution failed: {error_msg}") from e

    except Exception as e:
        error_msg = f"Unexpected error during transformation pipeline execution: {str(e)}"

        # Execute compensation logic for unexpected errors
        try:
            from hub.apps.transformation.compensation import TransformationPipelineCompensation
            compensation = TransformationPipelineCompensation(execution)
            compensation_result = compensation.compensate(
                rollback_execution=True,
                cleanup_job=True,
                cleanup_result_asset=True,
                publish_compensation_events=True
            )
            logger.info(
                f"Compensation completed for unexpected error in execution {execution.id}",
                extra={
                    "execution_id": str(execution.id),
                    "job_id": str(job_obj.id),
                    "compensation_result": compensation_result
                }
            )
        except Exception as comp_error:
            logger.exception(
                f"Compensation failed for unexpected error in execution {execution.id}: {comp_error}",
                extra={
                    "execution_id": str(execution.id),
                    "job_id": str(job_obj.id),
                    "compensation_error": str(comp_error)
                }
            )
            # Still mark execution as failed even if compensation fails
            execution.mark_failed(error_message=error_msg)

        # Sync execution status from job to ensure consistency
        execution.sync_status_from_job()

        logger.error(
            "transformation_pipeline_execution_error",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            error=str(e),
            exc_info=True,
            message=f"Unexpected error during transformation pipeline execution: {str(e)}"
        )
        raise Exception(f"Transformation pipeline execution error: {str(e)}") from e


@transaction.atomic
def _execute_virtual_query_job(job_obj: Job) -> dict:
    """
    Execute virtual query execution job.

    Executes a virtual dataset query asynchronously.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with execution results

    Raises:
        ValueError: For validation errors
        Exception: For execution errors
    """
    from hub.apps.virtualization.models import QueryExecution, QueryExecutionStatus
    from hub.apps.virtualization.services import VirtualizationService

    execution_id = job_obj.resource_id
    if not execution_id:
        raise ValueError("execution_id is required in resource_id")

    try:
        # Use select_for_update to prevent concurrent execution
        execution = QueryExecution.objects.select_for_update().get(id=execution_id)
    except QueryExecution.DoesNotExist:
        raise ValueError(f"QueryExecution {execution_id} not found")

    # Idempotency check: if execution is already in terminal state, return existing result
    if execution.is_completed():
        logger.warning(
            "virtual_query_execution_already_terminal",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            status=execution.status,
            message=f"Execution {execution_id} is already in terminal state: {execution.status} (idempotency check)"
        )
        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "skipped": True,
            "reason": "Already in terminal state (idempotent retry)"
        }

    # Check if execution was cancelled
    if execution.status == QueryExecutionStatus.CANCELLED:
        logger.info(
            "virtual_query_execution_cancelled",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            message=f"Execution {execution_id} was cancelled, skipping job execution"
        )
        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "skipped": True,
            "reason": "Execution was cancelled"
        }

    # Mark execution as started
    execution.mark_started()
    execution.add_log_entry("INFO", f"Job {job_obj.id} started processing")

    try:
        # Get execution details from job
        details = job_obj.details_json or {}
        virtual_dataset_id = str(execution.virtual_dataset_id)
        timeout_seconds = details.get("timeout_seconds", 3600)

        # Initialize service
        service = VirtualizationService(
            tenant_id=str(execution.virtual_dataset.tenant_id),
            user_id=str(job_obj.created_by.id) if job_obj.created_by else None
        )

        # Execute query synchronously (job worker handles async execution)
        execution.add_log_entry("INFO", "Executing virtual dataset query")

        # Execute the query using the sync method (job worker provides async execution)
        execution = service._execute_query_sync(
            execution,
            execution.virtual_dataset,
            execution.parameters or {},
            timeout_seconds
        )

        execution.add_log_entry("INFO", f"Query execution completed successfully")

        # Sync execution status from job to ensure consistency
        execution.sync_status_from_job()

        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "row_count": execution.get_metric("rows_processed", 0),
            "duration_ms": execution.get_metric("duration_ms", 0)
        }

    except Exception as e:
        error_msg = str(e)
        execution.mark_failed(error_message=error_msg)

        # Sync execution status from job to ensure consistency
        execution.sync_status_from_job()

        logger.error(
            "virtual_query_execution_error",
            job_id=str(job_obj.id),
            execution_id=str(execution.id),
            error=error_msg,
            exc_info=True,
            message=f"Error during virtual query execution: {error_msg}"
        )
        raise Exception(f"Virtual query execution error: {error_msg}") from e


def _execute_marketplace_sync_job(job_obj: Job) -> dict:
    """
    Execute MARKETPLACE_SYNC job.

    Processes a marketplace synchronization job by calling the execute_marketplace_sync task.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with sync job execution results

    Raises:
        ValueError: If sync_job_id is missing or sync job not found
        ConnectionError: If connector cannot connect to marketplace
        Exception: For other errors
    """
    # Get sync_job_id from job details or resource_id
    sync_job_id = job_obj.details_json.get('sync_job_id')
    if not sync_job_id:
        sync_job_id = job_obj.resource_id

    # Convert to string if it's a UUID object
    if sync_job_id is not None:
        sync_job_id = str(sync_job_id)

    if not sync_job_id:
        raise ValueError("Sync job ID is required")

    # Get retry count from job details
    retry_count = job_obj.details_json.get('retry_count', 0) if job_obj.details_json else 0

    # Import here to avoid circular imports
    from hub.apps.integrations.tasks import execute_marketplace_sync

    # Execute the sync task
    # Note: execute_marketplace_sync is a django-rq job, but we can call it directly
    # from within another job handler. The @job decorator makes it callable as a function.
    result = execute_marketplace_sync(sync_job_id, retry_count=retry_count)

    # Ensure result is a dict
    if result is None:
        return {
            "status": "completed",
            "sync_job_id": sync_job_id
        }
    return result


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

