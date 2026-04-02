"""
Marketplace Integration Background Tasks

Background tasks for processing marketplace synchronization jobs.
Includes retry logic, error handling, progress tracking, and distributed tracing.
"""
import time
import uuid
from typing import Dict, Any, Optional
from django_rq import job
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
import structlog

from hub.apps.integrations.models import MarketplaceSyncJob, MarketplaceConnection
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncDirection,
    SyncStatus,
    SyncResult,
    DataMarketplaceConnector
)
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.logging_utils import log_sync_job, get_correlation_context
from hub.apps.observability.span_instrumentation import (
    create_span,
    add_span_attributes,
    set_span_status,
    record_span_exception
)
from opentelemetry.trace import StatusCode
from hub.apps.core.services.base import NotFoundError, ValidationError, ServiceError
from hub.apps.integrations.error_classification import (
    classify_connector_error,
    ConnectorErrorType,
)

logger = structlog.get_logger(__name__)


@job('job_default', timeout=3600)  # 1 hour timeout for sync operations
def execute_marketplace_sync(sync_job_id: str, retry_count: int = 0):
    """
    Execute a marketplace synchronization job.

    Processes a MarketplaceSyncJob by:
    1. Loading the sync job and connection
    2. Creating the appropriate connector
    3. Executing sync operation (PUSH or PULL)
    4. Tracking progress and updating sync job status
    5. Handling errors with retry logic
    6. Using distributed tracing for observability

    Args:
        sync_job_id: UUID of the MarketplaceSyncJob to execute
        retry_count: Current retry attempt number (for retry logic)

    Raises:
        ValueError: If sync job not found or invalid
        ConnectionError: If connector cannot connect to marketplace
        Exception: For other errors (will trigger retry if transient)
    """
    import time
    span_context = None
    span = None
    start_time = time.time()
    marketplace_type = None
    direction = None
    tenant_id = None
    final_status = None

    try:
        # Create distributed tracing span
        span_name = f"execute_marketplace_sync.{sync_job_id}"
        span_context = create_span(span_name, kind=1)
        span = span_context.__enter__() if span_context else None

        if span:
            add_span_attributes({
                "sync_job.id": sync_job_id,
                "sync_job.retry_count": retry_count,
            })

        # Load sync job
        try:
            sync_job = MarketplaceSyncJob.objects.select_related(
                'connection', 'tenant'
            ).get(id=sync_job_id)
        except (DjangoValidationError, ValueError) as e:
            error_msg = f"Invalid sync job ID format: {sync_job_id}"
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise ValueError(error_msg) from e
        except MarketplaceSyncJob.DoesNotExist:
            error_msg = f"Sync job {sync_job_id} not found"
            correlation_context = get_correlation_context()
            log_sync_job(
                "sync_job_not_found",
                level="error",
                sync_job_id=sync_job_id,
                error_message=error_msg,
                **correlation_context,
            )
            if span:
                record_span_exception(NotFoundError(error_msg))
                set_span_status(StatusCode.ERROR)
            raise ValueError(error_msg)

        # Check if job is already in terminal state (idempotency)
        if sync_job.is_terminal():
            correlation_context = get_correlation_context()
            log_sync_job(
                "sync_job_already_terminal",
                level="info",
                sync_job_id=str(sync_job.id),
                status=sync_job.status,
                **correlation_context,
            )
            if span:
                add_span_attributes({
                    "sync_job.status": sync_job.status,
                    "sync_job.idempotent": True
                })
                set_span_status(StatusCode.OK)
            return {
                "status": "skipped",
                "reason": f"Sync job already in terminal state: {sync_job.status}",
                "sync_job_id": str(sync_job.id)
            }

        # Add span attributes
        if span:
            add_span_attributes({
                "sync_job.connection_id": str(sync_job.connection.id),
                "sync_job.direction": sync_job.direction,
                "sync_job.tenant_id": str(sync_job.tenant.id),
            })

        # Store metadata for metrics
        connection = sync_job.connection
        marketplace_type = connection.marketplace_type
        direction = sync_job.direction
        tenant_id = str(sync_job.tenant.id)

        # Record sync job start metric
        try:
            from hub.apps.observability.otel_metrics import (
                marketplace_sync_jobs_total,
            )
            marketplace_sync_jobs_total.labels(
                marketplace_type=marketplace_type,
                direction=direction,
                tenant_id=tenant_id,
                status="started",
            ).inc()
        except Exception as e:
            correlation_context = get_correlation_context()
            logger.warning(
                "metrics_recording_failed",
                sync_job_id=str(sync_job.id),
                metric_type="sync_job_start",
                error=str(e),
                error_type=type(e).__name__,
                **correlation_context,
                exc_info=True,
            )

        # Mark job as running
        sync_job.mark_running()

        # Log sync job start with structured fields
        correlation_context = get_correlation_context()
        log_sync_job(
            "sync_job_started",
            level="info",
            sync_job_id=str(sync_job.id),
            connection_id=str(sync_job.connection.id),
            marketplace_type=marketplace_type,
            direction=direction,
            tenant_id=tenant_id,
            retry_count=retry_count,
            **correlation_context,
        )

        # Get connection and validate
        connection = sync_job.connection
        if not connection.is_active:
            error_msg = f"Connection {connection.id} is not active"
            correlation_context = get_correlation_context()
            log_sync_job(
                "connection_not_active",
                level="error",
                sync_job_id=str(sync_job.id),
                connection_id=str(connection.id),
                error_message=error_msg,
                **correlation_context,
            )
            sync_job.mark_failed(error_message=error_msg)
            if span:
                record_span_exception(ValidationError(error_msg))
                set_span_status(StatusCode.ERROR)
            raise ValueError(error_msg)

        # Get connection config
        try:
            config = connection.get_config()
        except Exception as e:
            error_msg = f"Failed to decrypt connection config: {str(e)}"
            correlation_context = get_correlation_context()
            log_sync_job(
                "config_decryption_failed",
                level="error",
                sync_job_id=str(sync_job.id),
                connection_id=str(connection.id),
                error_type=type(e).__name__,
                error_message=str(e),
                **correlation_context,
                exc_info=True,
            )
            sync_job.mark_failed(error_message=error_msg)
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise ValueError(error_msg) from e

        # Create connector
        try:
            marketplace_type = MarketplaceType(connection.marketplace_type)
            factory = MarketplaceConnectorFactory()

            if not factory.is_supported(marketplace_type):
                error_msg = f"Marketplace type {marketplace_type.value} is not supported"
                correlation_context = get_correlation_context()
                log_sync_job(
                    "marketplace_type_not_supported",
                    level="error",
                    sync_job_id=str(sync_job.id),
                    marketplace_type=marketplace_type.value,
                    error_message=error_msg,
                    **correlation_context,
                )
                sync_job.mark_failed(error_message=error_msg)
                if span:
                    record_span_exception(ValidationError(error_msg))
                    set_span_status(StatusCode.ERROR)
                raise ValueError(error_msg)

            connector = factory.create_connector(
                marketplace_type=marketplace_type,
                config=config,
                tenant_id=str(sync_job.tenant.id),
                user_id=None  # Background job doesn't have user context
            )
        except ValueError as e:
            # Re-raise validation errors
            sync_job.mark_failed(error_message=str(e))
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            error_msg = f"Failed to create connector: {str(e)}"
            correlation_context = get_correlation_context()
            log_sync_job(
                "connector_creation_failed",
                level="error",
                sync_job_id=str(sync_job.id),
                connection_id=str(connection.id),
                marketplace_type=connection.marketplace_type,
                error_type=type(e).__name__,
                error_message=str(e),
                **correlation_context,
                exc_info=True,
            )
            sync_job.mark_failed(error_message=error_msg)
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise ServiceError(error_msg) from e

        # Execute sync based on direction
        sync_direction = SyncDirection(sync_job.direction)
        sync_result: Optional[SyncResult] = None

        try:
            if sync_direction == SyncDirection.PUSH:
                # PUSH: Sync Hub assets to marketplace
                asset_ids = sync_job.metadata.get('asset_ids', [])
                options = sync_job.metadata.get('options', {})

                if not asset_ids:
                    error_msg = "No asset IDs provided for PUSH sync"
                    correlation_context = get_correlation_context()
                    log_sync_job(
                        "no_asset_ids_for_push",
                        level="error",
                        sync_job_id=str(sync_job.id),
                        error_message=error_msg,
                        **correlation_context,
                    )
                    sync_job.mark_failed(error_message=error_msg)
                    if span:
                        record_span_exception(ValidationError(error_msg))
                        set_span_status(StatusCode.ERROR)
                    raise ValueError(error_msg)

                if span:
                    add_span_attributes({
                        "sync.asset_count": len(asset_ids),
                        "sync.direction": "PUSH"
                    })

                correlation_context = get_correlation_context()
                log_sync_job(
                    "sync_push_starting",
                    level="info",
                    sync_job_id=str(sync_job.id),
                    direction="PUSH",
                    total_items=len(asset_ids),
                    **correlation_context,
                )

                # Execute PUSH sync with metrics
                import time
                sync_start_time = time.time()
                try:
                    from hub.apps.observability.otel_metrics import (
                        marketplace_connector_operations_total,
                        marketplace_connector_operation_duration_seconds,
                        marketplace_connector_operation_errors_total,
                    )
                    sync_result = connector.sync_push(
                        asset_ids=asset_ids,
                        options=options
                    )
                    if sync_result is None:
                        error_msg = "Sync operation returned no result"
                        sync_job.mark_failed(error_message=error_msg)
                        raise ServiceError(error_msg)
                    sync_duration = time.time() - sync_start_time
                    status = "success" if sync_result.status == SyncStatus.COMPLETED else "error"
                    marketplace_connector_operations_total.labels(
                        marketplace_type=marketplace_type.value,
                        operation_type="sync_push",
                        status=status,
                        tenant_id=str(sync_job.tenant.id),
                    ).inc()
                    marketplace_connector_operation_duration_seconds.labels(
                        marketplace_type=marketplace_type.value,
                        operation_type="sync_push",
                        status=status,
                    ).observe(sync_duration)
                    if status == "error":
                        marketplace_connector_operation_errors_total.labels(
                            marketplace_type=marketplace_type.value,
                            operation_type="sync_push",
                            error_type=sync_result.status.value,
                            tenant_id=str(sync_job.tenant.id),
                        ).inc()
                except ConnectionError as e:
                    sync_job.mark_failed(error_message=str(e))
                    raise
                except Exception as e:
                    sync_duration = time.time() - sync_start_time
                    try:
                        from hub.apps.observability.otel_metrics import (
                            marketplace_connector_operations_total,
                            marketplace_connector_operation_duration_seconds,
                            marketplace_connector_operation_errors_total,
                        )
                        marketplace_connector_operations_total.labels(
                            marketplace_type=marketplace_type.value,
                            operation_type="sync_push",
                            status="error",
                            tenant_id=str(sync_job.tenant.id),
                        ).inc()
                        marketplace_connector_operation_duration_seconds.labels(
                            marketplace_type=marketplace_type.value,
                            operation_type="sync_push",
                            status="error",
                        ).observe(sync_duration)
                        marketplace_connector_operation_errors_total.labels(
                            marketplace_type=marketplace_type.value,
                            operation_type="sync_push",
                            error_type=type(e).__name__,
                            tenant_id=str(sync_job.tenant.id),
                        ).inc()
                    except Exception:
                        pass
                    sync_job.mark_failed(error_message=str(e))
                    raise

            elif sync_direction == SyncDirection.PULL:
                # PULL: Sync marketplace listings to Hub
                listing_ids = sync_job.metadata.get('listing_ids')
                filters = sync_job.metadata.get('filters', {})
                options = sync_job.metadata.get('options', {})

                if span:
                    add_span_attributes({
                        "sync.listing_count": len(listing_ids) if listing_ids else 0,
                        "sync.has_filters": bool(filters),
                        "sync.direction": "PULL"
                    })

                correlation_context = get_correlation_context()
                log_sync_job(
                    "sync_pull_starting",
                    level="info",
                    sync_job_id=str(sync_job.id),
                    direction="PULL",
                    total_items=len(listing_ids) if listing_ids else 0,
                    **correlation_context,
                )

                # Execute PULL sync with metrics
                import time
                sync_start_time = time.time()
                try:
                    from hub.apps.observability.otel_metrics import (
                        marketplace_connector_operations_total,
                        marketplace_connector_operation_duration_seconds,
                        marketplace_connector_operation_errors_total,
                    )
                    sync_result = connector.sync_pull(
                        listing_ids=listing_ids,
                        filters=filters if filters else None,
                        options=options
                    )
                    if sync_result is None:
                        error_msg = "Sync operation returned no result"
                        sync_job.mark_failed(error_message=error_msg)
                        raise ServiceError(error_msg)
                    sync_duration = time.time() - sync_start_time
                    status = "success" if sync_result.status == SyncStatus.COMPLETED else "error"
                    marketplace_connector_operations_total.labels(
                        marketplace_type=marketplace_type.value,
                        operation_type="sync_pull",
                        status=status,
                        tenant_id=str(sync_job.tenant.id),
                    ).inc()
                    marketplace_connector_operation_duration_seconds.labels(
                        marketplace_type=marketplace_type.value,
                        operation_type="sync_pull",
                        status=status,
                    ).observe(sync_duration)
                    if status == "error":
                        marketplace_connector_operation_errors_total.labels(
                            marketplace_type=marketplace_type.value,
                            operation_type="sync_pull",
                            error_type=sync_result.status.value,
                            tenant_id=str(sync_job.tenant.id),
                        ).inc()
                except ConnectionError as e:
                    sync_job.mark_failed(error_message=str(e))
                    raise
                except Exception as e:
                    sync_duration = time.time() - sync_start_time
                    try:
                        from hub.apps.observability.otel_metrics import (
                            marketplace_connector_operations_total,
                            marketplace_connector_operation_duration_seconds,
                            marketplace_connector_operation_errors_total,
                        )
                        marketplace_connector_operations_total.labels(
                            marketplace_type=marketplace_type.value,
                            operation_type="sync_pull",
                            status="error",
                            tenant_id=str(sync_job.tenant.id),
                        ).inc()
                        marketplace_connector_operation_duration_seconds.labels(
                            marketplace_type=marketplace_type.value,
                            operation_type="sync_pull",
                            status="error",
                        ).observe(sync_duration)
                        marketplace_connector_operation_errors_total.labels(
                            marketplace_type=marketplace_type.value,
                            operation_type="sync_pull",
                            error_type=type(e).__name__,
                            tenant_id=str(sync_job.tenant.id),
                        ).inc()
                    except Exception:
                        pass
                    sync_job.mark_failed(error_message=str(e))
                    raise

            elif sync_direction == SyncDirection.BIDIRECTIONAL:
                # BIDIRECTIONAL: Sync both directions
                asset_ids = sync_job.metadata.get('asset_ids', [])
                listing_ids = sync_job.metadata.get('listing_ids')
                filters = sync_job.metadata.get('filters', {})
                options = sync_job.metadata.get('options', {})

                if span:
                    add_span_attributes({
                        "sync.asset_count": len(asset_ids),
                        "sync.listing_count": len(listing_ids) if listing_ids else 0,
                        "sync.direction": "BIDIRECTIONAL"
                    })

                logger.info(
                    "sync_bidirectional_starting",
                    sync_job_id=str(sync_job.id),
                    asset_count=len(asset_ids),
                    listing_count=len(listing_ids) if listing_ids else 0
                )

                # Execute PUSH first
                push_result = None
                if asset_ids:
                    push_result = connector.sync_push(
                        asset_ids=asset_ids,
                        options=options
                    )

                # Execute PULL second
                pull_result = None
                if listing_ids or filters:
                    pull_result = connector.sync_pull(
                        listing_ids=listing_ids,
                        filters=filters if filters else None,
                        options=options
                    )

                # Combine results
                if push_result and pull_result:
                    sync_result = SyncResult(
                        status=SyncStatus.PARTIAL if (
                            push_result.status == SyncStatus.FAILED or
                            pull_result.status == SyncStatus.FAILED
                        ) else SyncStatus.COMPLETED,
                        total_items=push_result.total_items + pull_result.total_items,
                        successful_items=push_result.successful_items + pull_result.successful_items,
                        failed_items=push_result.failed_items + pull_result.failed_items,
                        skipped_items=push_result.skipped_items + pull_result.skipped_items,
                        errors=push_result.errors + pull_result.errors,
                        metadata={
                            **push_result.metadata,
                            **pull_result.metadata,
                            'push_result': {
                                'status': push_result.status.value,
                                'items': push_result.successful_items
                            },
                            'pull_result': {
                                'status': pull_result.status.value,
                                'items': pull_result.successful_items
                            }
                        },
                        started_at=push_result.started_at or pull_result.started_at,
                        completed_at=push_result.completed_at or pull_result.completed_at
                    )
                elif push_result:
                    sync_result = push_result
                elif pull_result:
                    sync_result = pull_result
                else:
                    error_msg = "No sync operations specified for BIDIRECTIONAL sync"
                    sync_job.mark_failed(error_message=error_msg)
                    if span:
                        record_span_exception(ValidationError(error_msg))
                        set_span_status(StatusCode.ERROR)
                    raise ValueError(error_msg)

            else:
                error_msg = f"Unsupported sync direction: {sync_direction.value}"
                correlation_context = get_correlation_context()
                log_sync_job(
                    "unsupported_sync_direction",
                    level="error",
                    sync_job_id=str(sync_job.id),
                    direction=sync_direction.value,
                    error_message=error_msg,
                    **correlation_context,
                )
                sync_job.mark_failed(error_message=error_msg)
                if span:
                    record_span_exception(ValidationError(error_msg))
                    set_span_status(StatusCode.ERROR)
                raise ValueError(error_msg)

            # Update sync job with results
            if sync_result:
                # Update progress
                sync_job.items_synced = sync_result.successful_items
                sync_job.items_failed = sync_result.failed_items

                # Add errors
                for error_msg in sync_result.errors:
                    sync_job.add_error(error_msg, save=False)

                # Prepare metadata for JSON serialization
                # Ensure all values are JSON-serializable (convert datetime objects, etc.)
                import json
                from datetime import datetime

                def make_json_serializable(obj):
                    """Recursively convert objects to JSON-serializable format."""
                    if isinstance(obj, dict):
                        return {k: make_json_serializable(v) for k, v in obj.items()}
                    elif isinstance(obj, (list, tuple)):
                        return [make_json_serializable(item) for item in obj]
                    elif isinstance(obj, datetime):
                        return obj.isoformat()
                    elif hasattr(obj, '__dict__'):
                        # Handle dataclass or object instances
                        return make_json_serializable(obj.__dict__)
                    elif hasattr(obj, 'value'):
                        # Handle enum values
                        return obj.value
                    else:
                        # Try to serialize, if it fails return string representation
                        try:
                            json.dumps(obj)
                            return obj
                        except (TypeError, ValueError):
                            return str(obj)

                # Serialize sync_result.metadata
                serialized_metadata = make_json_serializable(sync_result.metadata) if sync_result.metadata else {}

                # Update metadata
                sync_job.metadata.update({
                    **serialized_metadata,
                    'sync_result': {
                        'status': sync_result.status.value,
                        'total_items': sync_result.total_items,
                        'successful_items': sync_result.successful_items,
                        'failed_items': sync_result.failed_items,
                        'skipped_items': sync_result.skipped_items,
                    },
                    'completed_at': sync_result.completed_at.isoformat() if sync_result.completed_at else None,
                    'started_at': sync_result.started_at.isoformat() if sync_result.started_at else None,
                })

                # Update status based on result
                if sync_result.status == SyncStatus.COMPLETED:
                    sync_job.mark_completed(
                        items_synced=sync_result.successful_items,
                        metadata=serialized_metadata
                    )
                    final_status = "completed"
                    # Send completion notification (Task 9.10.6.3.2)
                    try:
                        from hub.apps.notifications.tasks import send_marketplace_sync_completion_email
                        send_marketplace_sync_completion_email.delay(str(sync_job.id))
                    except Exception as e:
                        logger.warning(
                            f"Failed to send sync completion notification for {sync_job.id}: {e}",
                            exc_info=True,
                        )
                elif sync_result.status == SyncStatus.FAILED:
                    error_msg = sync_result.errors[0] if sync_result.errors else "Sync operation failed"
                    sync_job.mark_failed(
                        error_message=error_msg,
                        items_synced=sync_result.successful_items,
                        items_failed=sync_result.failed_items,
                        metadata=serialized_metadata
                    )
                    final_status = "failed"
                    # Send failure notification (Task 9.10.6.3.2)
                    try:
                        from hub.apps.notifications.tasks import send_marketplace_sync_failure_email
                        send_marketplace_sync_failure_email.delay(str(sync_job.id))
                    except Exception as e:
                        logger.warning(
                            f"Failed to send sync failure notification for {sync_job.id}: {e}",
                            exc_info=True,
                        )
                elif sync_result.status == SyncStatus.PARTIAL:
                    sync_job.mark_partial(
                        items_synced=sync_result.successful_items,
                        items_failed=sync_result.failed_items,
                        metadata=serialized_metadata
                    )
                    final_status = "partial"
                    # Send completion notification for partial success (Task 9.10.6.3.2)
                    try:
                        from hub.apps.notifications.tasks import send_marketplace_sync_completion_email
                        send_marketplace_sync_completion_email.delay(str(sync_job.id))
                    except Exception as e:
                        logger.warning(
                            f"Failed to send sync completion notification for {sync_job.id}: {e}",
                            exc_info=True,
                        )

                # Record metrics
                if marketplace_type and direction and tenant_id:
                    try:
                        from hub.apps.observability.otel_metrics import (
                            marketplace_sync_jobs_total,
                            marketplace_sync_job_duration_seconds,
                            marketplace_sync_job_success_rate,
                        )
                        duration = time.time() - start_time
                        status_label = final_status or sync_result.status.value

                        # Record completion metric
                        marketplace_sync_jobs_total.labels(
                            marketplace_type=marketplace_type,
                            direction=direction,
                            tenant_id=tenant_id,
                            status=status_label,
                        ).inc()

                        # Record duration
                        marketplace_sync_job_duration_seconds.labels(
                            marketplace_type=marketplace_type,
                            direction=direction,
                            status=status_label,
                        ).observe(duration)

                        # Record success rate (increment on success)
                        if final_status == "completed":
                            marketplace_sync_job_success_rate.labels(
                                marketplace_type=marketplace_type,
                                direction=direction,
                                tenant_id=tenant_id,
                            ).inc()
                    except Exception as e:
                        correlation_context = get_correlation_context()
                        logger.warning(
                            "metrics_recording_failed",
                            sync_job_id=str(sync_job.id),
                            metric_type="sync_job_completion",
                            error=str(e),
                            error_type=type(e).__name__,
                            **correlation_context,
                            exc_info=True,
                        )

                # Log sync job completion with structured fields
                correlation_context = get_correlation_context()
                duration = time.time() - start_time
                log_sync_job(
                    "sync_job_completed",
                    level="info",
                    sync_job_id=str(sync_job.id),
                    status=sync_result.status.value,
                    marketplace_type=marketplace_type,
                    direction=direction,
                    tenant_id=tenant_id,
                    duration=duration,
                    total_items=sync_result.total_items,
                    successful_items=sync_result.successful_items,
                    failed_items=sync_result.failed_items,
                    **correlation_context,
                )

                if span:
                    add_span_attributes({
                        "sync.result.status": sync_result.status.value,
                        "sync.result.successful_items": sync_result.successful_items,
                        "sync.result.failed_items": sync_result.failed_items,
                        "sync.result.total_items": sync_result.total_items,
                    })
                    set_span_status(StatusCode.OK)

                return {
                    "status": "completed",
                    "sync_job_id": str(sync_job.id),
                    "sync_status": sync_result.status.value,
                    "successful_items": sync_result.successful_items,
                    "failed_items": sync_result.failed_items,
                    "total_items": sync_result.total_items,
                }
            else:
                error_msg = "Sync operation returned no result"
                correlation_context = get_correlation_context()
                log_sync_job(
                    "sync_no_result",
                    level="error",
                    sync_job_id=str(sync_job.id),
                    error_message=error_msg,
                    **correlation_context,
                )
                sync_job.mark_failed(error_message=error_msg)
                if span:
                    record_span_exception(ServiceError(error_msg))
                    set_span_status(StatusCode.ERROR)
                raise ServiceError(error_msg)

        except ValueError as e:
            # Validation errors — always permanent, don't retry
            final_status = "failed"
            correlation_context = get_correlation_context()
            log_sync_job(
                "sync_validation_error",
                level="error",
                sync_job_id=str(sync_job.id),
                error_type=type(e).__name__,
                error_message=str(e),
                **correlation_context,
                exc_info=True,
            )
            sync_job.mark_failed(error_message=str(e))
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise

        except Exception as e:
            # ── Phase 77: classify error for retry decision ─────
            error_class = classify_connector_error(e)
            error_msg = f"{error_class.value.title()} error during sync: {str(e)}"
            final_status = "failed"
            correlation_context = get_correlation_context()
            log_sync_job(
                "sync_classified_error",
                level="error",
                sync_job_id=str(sync_job.id),
                error_type=type(e).__name__,
                error_class=error_class.value,
                error_message=str(e),
                retry_count=retry_count,
                **correlation_context,
                exc_info=True,
            )

            if error_class == ConnectorErrorType.PERMANENT:
                # Permanent — fail immediately, no retry.
                # add_error first (with error_type), then
                # mark_failed WITHOUT error_message to avoid
                # a duplicate entry (mark_failed calls add_error
                # internally when error_message is provided).
                sync_job.add_error(
                    error_msg, save=False,
                    error_type=error_class.value,
                )
                sync_job.mark_failed()
                if span:
                    record_span_exception(e)
                    add_span_attributes({
                        "error.retryable": False,
                        "error.class": error_class.value,
                    })
                    set_span_status(StatusCode.ERROR)
                raise ServiceError(error_msg) from e

            elif error_class == ConnectorErrorType.TRANSIENT:
                # Transient — record error and re-raise for retry
                sync_job.add_error(
                    error_msg, save=True,
                    error_type=error_class.value,
                )
                if span:
                    record_span_exception(e)
                    add_span_attributes({
                        "error.retryable": True,
                        "error.class": error_class.value,
                    })
                    set_span_status(StatusCode.ERROR)
                raise

            else:
                # Unknown — retry once then fail
                max_unknown_retries = 1
                sync_job.add_error(
                    error_msg, save=False,
                    error_type=error_class.value,
                )
                if retry_count < max_unknown_retries:
                    sync_job.save(
                        update_fields=["errors", "updated_at"],
                    )
                    if span:
                        record_span_exception(e)
                        add_span_attributes({
                            "error.retryable": True,
                            "error.class": error_class.value,
                            "error.retry_count": retry_count,
                        })
                        set_span_status(StatusCode.ERROR)
                    raise
                else:
                    # Exhausted unknown retries — fail.
                    # Don't pass error_message to mark_failed;
                    # it was already recorded by add_error above.
                    sync_job.mark_failed()
                    if span:
                        record_span_exception(e)
                        add_span_attributes({
                            "error.retryable": False,
                            "error.class": error_class.value,
                            "error.retry_count": retry_count,
                        })
                        set_span_status(StatusCode.ERROR)
                    raise ServiceError(error_msg) from e

    except Exception as e:
        # Catch-all for any unhandled errors
        final_status = "failed"
        correlation_context = get_correlation_context()
        log_sync_job(
            "sync_job_execution_failed",
            level="error",
            sync_job_id=sync_job_id,
            error_type=type(e).__name__,
            error_message=str(e),
            retry_count=retry_count,
            **correlation_context,
            exc_info=True,
        )
        if span:
            record_span_exception(e)
            set_span_status(StatusCode.ERROR)
        raise

    finally:
        # Record metrics for failed jobs
        if marketplace_type and direction and tenant_id and final_status == "failed":
            try:
                from hub.apps.observability.otel_metrics import (
                    marketplace_sync_jobs_total,
                    marketplace_sync_job_duration_seconds,
                )
                duration = time.time() - start_time

                # Record failure metric
                marketplace_sync_jobs_total.labels(
                    marketplace_type=marketplace_type,
                    direction=direction,
                    tenant_id=tenant_id,
                    status="failed",
                ).inc()

                # Record duration even for failures
                marketplace_sync_job_duration_seconds.labels(
                    marketplace_type=marketplace_type,
                    direction=direction,
                    status="failed",
                ).observe(duration)
            except Exception as e:
                correlation_context = get_correlation_context()
                logger.warning(
                    "metrics_recording_failed",
                    sync_job_id=sync_job_id,
                    metric_type="sync_job_failure",
                    error=str(e),
                    error_type=type(e).__name__,
                    **correlation_context,
                    exc_info=True,
                )

            # Send failure notification if not already sent (Task 9.10.6.3.2)
            try:
                from hub.apps.notifications.tasks import send_marketplace_sync_failure_email
                send_marketplace_sync_failure_email.delay(sync_job_id)
            except Exception as e:
                correlation_context = get_correlation_context()
                logger.warning(
                    "notification_send_failed",
                    sync_job_id=sync_job_id,
                    notification_type="sync_failure",
                    error=str(e),
                    error_type=type(e).__name__,
                    **correlation_context,
                    exc_info=True,
                )

        # Clean up span
        if span_context:
            try:
                span_context.__exit__(None, None, None)
            except Exception:
                pass


@job('job_default', timeout=300)  # 5 minute timeout for checking schedules
def process_scheduled_syncs():
    """
    Process scheduled marketplace syncs that are due to run.

    Checks all active scheduled syncs and triggers sync jobs for those that are due.
    This task should be called periodically (e.g., every minute via cron or scheduler).

    Returns:
        Dictionary with processing results
    """
    from hub.apps.integrations.models import ScheduledMarketplaceSync, ScheduledMarketplaceSyncStatus
    from hub.apps.integrations.services import MarketplaceIntegrationService
    from hub.apps.integrations.base import SyncDirection

    span_context = None
    span = None

    try:
        # Create distributed tracing span
        span_name = "process_scheduled_syncs"
        span_context = create_span(span_name, kind=1)
        span = span_context.__enter__() if span_context else None

        if span:
            add_span_attributes({
                "task": "process_scheduled_syncs"
            })

        # Get all active scheduled syncs that are due
        now = timezone.now()
        due_syncs = ScheduledMarketplaceSync.objects.filter(
            status=ScheduledMarketplaceSyncStatus.ACTIVE,
            next_run_at__lte=now
        ).select_related('connection', 'tenant', 'created_by')

        correlation_context = get_correlation_context()
        logger.info(
            "scheduled_syncs_check",
            due_count=due_syncs.count(),
            **correlation_context,
        )

        if span:
            add_span_attributes({
                "scheduled_syncs.due_count": due_syncs.count()
            })

        results = {
            "processed": 0,
            "failed": 0,
            "errors": []
        }

        # Process each due sync
        for scheduled_sync in due_syncs:
            try:
                # Create service instance
                user_id = str(scheduled_sync.created_by.id) if scheduled_sync.created_by else None
                if not user_id:
                    # Use a system user or tenant admin as fallback
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    try:
                        # Try to get a tenant admin user
                        admin_user = User.objects.filter(
                            tenant=scheduled_sync.tenant,
                            is_platform_admin=False
                        ).first()
                        if admin_user:
                            user_id = str(admin_user.id)
                        else:
                            # Use tenant ID as fallback (system user)
                            user_id = str(scheduled_sync.tenant.id)
                    except Exception:
                        user_id = str(scheduled_sync.tenant.id)

                service = MarketplaceIntegrationService(
                    tenant_id=str(scheduled_sync.tenant.id),
                    user_id=user_id
                )

                # Get sync options
                sync_options = scheduled_sync.sync_options or {}
                direction = SyncDirection(scheduled_sync.direction)

                # Trigger sync based on direction
                if direction == SyncDirection.PUSH:
                    asset_ids = sync_options.get('asset_ids', [])
                    if asset_ids:
                        sync_job = service.sync_assets_to_marketplace(
                            connection_id=str(scheduled_sync.connection.id),
                            tenant_id=str(scheduled_sync.tenant.id),
                            user_id=user_id,
                            asset_ids=asset_ids,
                            options=sync_options.get('options', {}),
                            request=None
                        )
                    else:
                        correlation_context = get_correlation_context()
                        logger.warning(
                            "scheduled_sync_no_asset_ids",
                            scheduled_sync_id=str(scheduled_sync.id),
                            direction="PUSH",
                            **correlation_context,
                        )
                        results["errors"].append({
                            "scheduled_sync_id": str(scheduled_sync.id),
                            "error": "No asset_ids configured for PUSH sync"
                        })
                        results["failed"] += 1
                        continue

                elif direction == SyncDirection.PULL:
                    listing_ids = sync_options.get('listing_ids')
                    filters = sync_options.get('filters', {})
                    sync_job = service.sync_from_marketplace(
                        connection_id=str(scheduled_sync.connection.id),
                        tenant_id=str(scheduled_sync.tenant.id),
                        user_id=user_id,
                        listing_ids=listing_ids,
                        filters=filters if filters else None,
                        options=sync_options.get('options', {}),
                        request=None
                    )

                elif direction == SyncDirection.BIDIRECTIONAL:
                    # For bidirectional, we need both asset_ids and listing_ids/filters
                    asset_ids = sync_options.get('asset_ids', [])
                    listing_ids = sync_options.get('listing_ids')
                    filters = sync_options.get('filters', {})

                    # Trigger PUSH if asset_ids provided
                    push_job = None
                    if asset_ids:
                        push_job = service.sync_assets_to_marketplace(
                            connection_id=str(scheduled_sync.connection.id),
                            tenant_id=str(scheduled_sync.tenant.id),
                            user_id=user_id,
                            asset_ids=asset_ids,
                            options=sync_options.get('options', {}),
                            request=None
                        )

                    # Trigger PULL if listing_ids or filters provided
                    pull_job = None
                    if listing_ids or filters:
                        pull_job = service.sync_from_marketplace(
                            connection_id=str(scheduled_sync.connection.id),
                            tenant_id=str(scheduled_sync.tenant.id),
                            user_id=user_id,
                            listing_ids=listing_ids,
                            filters=filters if filters else None,
                            options=sync_options.get('options', {}),
                            request=None
                        )

                    # Use the first job created as the reference
                    sync_job = push_job or pull_job

                    if not sync_job:
                        correlation_context = get_correlation_context()
                        logger.warning(
                            "scheduled_sync_no_config",
                            scheduled_sync_id=str(scheduled_sync.id),
                            direction="BIDIRECTIONAL",
                            **correlation_context,
                        )
                        results["errors"].append({
                            "scheduled_sync_id": str(scheduled_sync.id),
                            "error": "No asset_ids or listing_ids/filters configured for BIDIRECTIONAL sync"
                        })
                        results["failed"] += 1
                        continue

                else:
                    correlation_context = get_correlation_context()
                    logger.error(
                        "scheduled_sync_invalid_direction",
                        scheduled_sync_id=str(scheduled_sync.id),
                        direction=scheduled_sync.direction,
                        **correlation_context,
                    )
                    results["errors"].append({
                        "scheduled_sync_id": str(scheduled_sync.id),
                        "error": f"Invalid sync direction: {scheduled_sync.direction}"
                    })
                    results["failed"] += 1
                    continue

                # Mark scheduled sync as run
                scheduled_sync.mark_run(sync_job.id)

                correlation_context = get_correlation_context()
                logger.info(
                    "scheduled_sync_triggered",
                    scheduled_sync_id=str(scheduled_sync.id),
                    sync_job_id=str(sync_job.id),
                    direction=scheduled_sync.direction,
                    next_run_at=scheduled_sync.next_run_at.isoformat() if scheduled_sync.next_run_at else None,
                    **correlation_context,
                )

                results["processed"] += 1

            except Exception as e:
                correlation_context = get_correlation_context()
                logger.error(
                    "scheduled_sync_trigger_failed",
                    scheduled_sync_id=str(scheduled_sync.id),
                    error_type=type(e).__name__,
                    error_message=str(e),
                    **correlation_context,
                    exc_info=True,
                )
                results["errors"].append({
                    "scheduled_sync_id": str(scheduled_sync.id),
                    "error": str(e)
                })
                results["failed"] += 1

                # Mark scheduled sync as error if it fails multiple times
                # For now, just log the error - the sync will be retried on next run

        correlation_context = get_correlation_context()
        logger.info(
            "scheduled_syncs_processed",
            processed=results["processed"],
            failed=results["failed"],
            total=results["processed"] + results["failed"],
            **correlation_context,
        )

        if span:
            add_span_attributes({
                "scheduled_syncs.processed": results["processed"],
                "scheduled_syncs.failed": results["failed"]
            })
            set_span_status(StatusCode.OK)

        return results

    except Exception as e:
        logger.error(
            "process_scheduled_syncs_failed",
            error=str(e),
            exc_info=True
        )
        if span:
            record_span_exception(e)
            set_span_status(StatusCode.ERROR)
        raise

    finally:
        if span_context:
            try:
                span_context.__exit__(None, None, None)
            except Exception:
                pass

