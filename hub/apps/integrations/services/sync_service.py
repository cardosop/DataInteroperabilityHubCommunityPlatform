"""Sync workflow methods for MarketplaceIntegrationService."""
import structlog
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from hub.apps.core.services.base import (
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncDirection,
    SyncStatus,
)
from hub.apps.integrations.event_publishers import MarketplaceEventPublisher
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceSyncJob,
    ScheduledMarketplaceSync,
    ScheduledMarketplaceSyncStatus,
    ScheduleType,
)

logger = structlog.get_logger(__name__)


class SyncServiceMixin:
    """Mixin providing sync workflow and job operations."""

    def sync_assets_to_marketplace(
        self,
        connection_id: str,
        tenant_id: str,
        user_id: str,
        asset_ids: List[str],
        options: Optional[Dict[str, Any]] = None,
        request: Optional[Any] = None,
    ) -> MarketplaceSyncJob:
        """
        Synchronize Hub assets to marketplace (PUSH operation).

        Creates a sync job and enqueues it for asynchronous processing.
        The actual sync operation will be performed by a background worker.

        Args:
            connection_id: The ID of the marketplace connection to use.
            tenant_id: The ID of the tenant.
            user_id: The ID of the user initiating the sync.
            asset_ids: List of Hub asset IDs to synchronize.
            options: Optional dictionary of sync options (e.g., dry_run, force_update).
            request: Optional request object for audit logging and tracing context.

        Returns:
            The created MarketplaceSyncJob instance.

        Raises:
            NotFoundError: If connection not found.
            ValidationError: If input data is invalid.
            ServiceError: For other unexpected errors.
        """
        from django.contrib.auth import get_user_model
        from opentelemetry.trace import StatusCode

        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job, get_job_timeout
        from hub.apps.observability.span_instrumentation import (
            add_span_attributes,
            create_span,
            record_span_exception,
            set_span_status,
        )
        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.sync_assets_to_marketplace"
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            try:
                # Get connection
                try:
                    connection = self.get_resource_or_raise(
                        MarketplaceConnection, connection_id, tenant_id=effective_tenant_id
                    )
                except (DjangoValidationError, ValidationError) as e:
                    # Django ValidationError (invalid UUID) or service-level
                    # ValidationError (converted by get_resource_or_raise) should
                    # be treated as NotFoundError for a cleaner API response.
                    raise NotFoundError(
                        f"Connection {connection_id} not found",
                        details={"connection_id": connection_id, "error": str(e)},
                    ) from e

                # Validate connection is active
                if not connection.is_active:
                    raise ValidationError(
                        f"Connection {connection_id} is not active",
                        details={"connection_id": connection_id, "is_active": False},
                    )

                # Validate asset_ids
                if not asset_ids or not isinstance(asset_ids, list):
                    raise ValidationError(
                        "asset_ids must be a non-empty list",
                        details={"asset_ids_type": type(asset_ids).__name__},
                    )

                # Validate marketplace type supports PUSH
                marketplace_type = MarketplaceType(connection.marketplace_type)
                factory = MarketplaceConnectorFactory()
                if not factory.is_supported(marketplace_type):
                    raise ValidationError(
                        f"Marketplace type {marketplace_type.value} is not supported",
                        details={"marketplace_type": marketplace_type.value},
                    )

                # Get tenant and user
                tenant_obj = self.get_resource_or_raise(Tenant, effective_tenant_id)
                user_obj = self.get_resource_or_raise(User, effective_user_id)

                # Create sync job
                sync_job = MarketplaceSyncJob.objects.create(
                    tenant=tenant_obj,
                    connection=connection,
                    direction=SyncDirection.PUSH.value,
                    status=SyncStatus.PENDING.value,
                    metadata={
                        "asset_ids": asset_ids,
                        "options": options or {},
                        "request_id": self.request_id,
                    },
                )

                # Create and start workflow instance
                try:
                    from hub.apps.orchestration.registry import WorkflowRegistry
                    from hub.apps.orchestration.workflow_engine import WorkflowEngine
                    from hub.apps.orchestration.workflows.marketplace_sync import (
                        MarketplaceSyncWorkflow,
                    )

                    # Initialize workflow engine and registry
                    engine = WorkflowEngine()
                    registry = WorkflowRegistry()

                    # Register workflow and tasks
                    MarketplaceSyncWorkflow.register_workflow(registry)
                    MarketplaceSyncWorkflow.register_tasks(engine)

                    # Create workflow instance
                    workflow_instance = engine.create_instance(
                        workflow_name="marketplace_sync_push",
                        input_data={
                            "connection_id": connection_id,
                            "asset_ids": asset_ids,
                            "tenant_id": effective_tenant_id,
                            "user_id": effective_user_id,
                            "sync_job_id": str(sync_job.id),
                            "options": options or {},
                        },
                        tenant_id=effective_tenant_id,
                        created_by_id=effective_user_id,
                    )

                    # Initialize state_data with sync job context
                    workflow_instance.state_data = {
                        "connection_id": connection_id,
                        "sync_job_id": str(sync_job.id),
                    }
                    workflow_instance.save(update_fields=["state_data"])

                    # Start workflow execution
                    workflow_instance = engine.start_instance(str(workflow_instance.id))

                    # Execute workflow synchronously to create assets immediately
                    # This ensures assets are created without waiting for background worker
                    try:
                        workflow_instance = engine.execute_instance(str(workflow_instance.id))
                        logger.info(
                            f"Workflow instance {workflow_instance.id} executed synchronously for sync job {sync_job.id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to execute workflow synchronously, will run in background: {e}",
                            exc_info=True,
                        )
                        # Workflow will be picked up by background worker if available

                    # Track workflow instance ID in sync job metadata
                    sync_job.metadata["workflow_instance_id"] = str(workflow_instance.id)
                    sync_job.save(update_fields=["metadata", "updated_at"])

                    logger.info(
                        f"Created workflow instance {workflow_instance.id} for sync job {sync_job.id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to create workflow instance for sync {sync_job.id}: {e}",
                        exc_info=True,
                    )
                    # Workflow creation failure doesn't fail the sync job creation
                    # The sync job can be manually processed later
                    sync_job.metadata["workflow_error"] = str(e)
                    sync_job.save(update_fields=["metadata", "updated_at"])

                # Add span attributes
                if span:
                    add_span_attributes(
                        {
                            "sync_job.id": str(sync_job.id),
                            "sync_job.direction": SyncDirection.PUSH.value,
                            "sync_job.connection_id": connection_id,
                            "sync_job.asset_count": len(asset_ids),
                        }
                    )
                    set_span_status(StatusCode.OK)

                # Audit log
                try:
                    from hub.apps.audit.utils import create_audit_event

                    create_audit_event(
                        resource_type="MARKETPLACE_SYNC_JOB",
                        action="SYNC_JOB_CREATED",
                        actor_user=user_obj,
                        tenant=tenant_obj,
                        resource_id=str(sync_job.id),
                        result="SUCCESS",
                        details={
                            "sync_job_id": str(sync_job.id),
                            "connection_id": connection_id,
                            "direction": SyncDirection.PUSH.value,
                            "asset_count": len(asset_ids),
                            "request_id": self.request_id,
                        },
                        request=request,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to create audit log for sync job creation {sync_job.id}: {e}",
                        exc_info=True,
                    )

                # Publish events
                try:
                    # Publish integration.sync_job.created event (existing)
                    self.publish_sync_job_created(
                        sync_job_id=str(sync_job.id),
                        connection_id=connection_id,
                        direction=SyncDirection.PUSH.value,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                        request_id=self.request_id,
                    )
                    # Publish marketplace.sync.started event (new)
                    MarketplaceEventPublisher.publish_sync_started(
                        self,
                        sync_job_id=str(sync_job.id),
                        connection_id=connection_id,
                        direction=SyncDirection.PUSH.value,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                        correlation_id=self.request_id,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to publish sync events for {sync_job.id}: {e}",
                        exc_info=True,
                    )

                logger.info(
                    f"Created marketplace sync job {sync_job.id} (PUSH) for connection {connection_id}"
                )

                return sync_job

            except (ValidationError, NotFoundError) as e:
                if span:
                    record_span_exception(e)
                    set_span_status(StatusCode.ERROR)
                raise
            except Exception as e:
                if span:
                    record_span_exception(e)
                    set_span_status(StatusCode.ERROR)
                logger.error(
                    f"Unexpected error creating sync job: {e}",
                    exc_info=True,
                    extra={
                        "connection_id": connection_id,
                        "tenant_id": effective_tenant_id,
                        "user_id": effective_user_id,
                    },
                )
                raise ServiceError(f"Failed to create sync job: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )

    @transaction.atomic
    def sync_from_marketplace(
        self,
        connection_id: str,
        tenant_id: str,
        user_id: str,
        listing_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
        request: Optional[Any] = None,
    ) -> MarketplaceSyncJob:
        """
        Synchronize marketplace listings to Hub (PULL operation).

        Creates a sync job and enqueues it for asynchronous processing.
        The actual sync operation will be performed by a background worker.

        Args:
            connection_id: The ID of the marketplace connection to use.
            tenant_id: The ID of the tenant.
            user_id: The ID of the user initiating the sync.
            listing_ids: Optional list of specific listing IDs to sync.
            filters: Optional dictionary of filters to apply.
            options: Optional dictionary of sync options (e.g., dry_run, create_assets).
            request: Optional request object for audit logging and tracing context.

        Returns:
            The created MarketplaceSyncJob instance.

        Raises:
            NotFoundError: If connection not found.
            ValidationError: If input data is invalid.
            ServiceError: For other unexpected errors.
        """
        if tenant_id is not None and (
            tenant_id == "" or (isinstance(tenant_id, str) and not tenant_id.strip())
        ):
            raise ValueError("tenant_id cannot be empty")
        if user_id is None:
            raise ValueError("user_id is required")
        if user_id is not None and (
            user_id == "" or (isinstance(user_id, str) and not user_id.strip())
        ):
            raise ValueError("user_id cannot be empty")
        from django.contrib.auth import get_user_model
        from opentelemetry.trace import StatusCode

        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job, get_job_timeout
        from hub.apps.observability.span_instrumentation import (
            add_span_attributes,
            create_span,
            record_span_exception,
            set_span_status,
        )
        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.sync_from_marketplace"
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            try:
                # Get connection
                try:
                    connection = self.get_resource_or_raise(
                        MarketplaceConnection, connection_id, tenant_id=effective_tenant_id
                    )
                except (DjangoValidationError, ValidationError) as e:
                    # Django ValidationError (invalid UUID) or service-level
                    # ValidationError (converted by get_resource_or_raise) should
                    # be treated as NotFoundError for a cleaner API response.
                    raise NotFoundError(
                        f"Connection {connection_id} not found",
                        details={"connection_id": connection_id, "error": str(e)},
                    ) from e

                # Validate connection is active
                if not connection.is_active:
                    raise ValidationError(
                        f"Connection {connection_id} is not active",
                        details={"connection_id": connection_id, "is_active": False},
                    )

                # Validate marketplace type supports PULL
                marketplace_type = MarketplaceType(connection.marketplace_type)
                factory = MarketplaceConnectorFactory()
                if not factory.is_supported(marketplace_type):
                    raise ValidationError(
                        f"Marketplace type {marketplace_type.value} is not supported",
                        details={"marketplace_type": marketplace_type.value},
                    )

                # Get tenant and user
                tenant_obj = self.get_resource_or_raise(Tenant, effective_tenant_id)
                user_obj = self.get_resource_or_raise(User, effective_user_id)

                # Create sync job
                sync_job = MarketplaceSyncJob.objects.create(
                    tenant=tenant_obj,
                    connection=connection,
                    direction=SyncDirection.PULL.value,
                    status=SyncStatus.PENDING.value,
                    metadata={
                        "listing_ids": listing_ids or [],
                        "filters": filters or {},
                        "options": options or {},
                        "request_id": self.request_id,
                    },
                )

                # Create and start workflow instance
                try:
                    from hub.apps.orchestration.registry import WorkflowRegistry
                    from hub.apps.orchestration.workflow_engine import WorkflowEngine
                    from hub.apps.orchestration.workflows.marketplace_sync import (
                        MarketplaceSyncWorkflow,
                    )

                    # Initialize workflow engine and registry
                    engine = WorkflowEngine()
                    registry = WorkflowRegistry()

                    # Register workflow and tasks
                    MarketplaceSyncWorkflow.register_workflow(registry)
                    MarketplaceSyncWorkflow.register_tasks(engine)

                    # Create workflow instance
                    workflow_instance = engine.create_instance(
                        workflow_name="marketplace_sync_pull",
                        input_data={
                            "connection_id": connection_id,
                            "listing_ids": listing_ids,
                            "filters": filters or {},
                            "tenant_id": effective_tenant_id,
                            "user_id": effective_user_id,
                            "sync_job_id": str(sync_job.id),
                            "options": options or {},
                        },
                        tenant_id=effective_tenant_id,
                        created_by_id=effective_user_id,
                    )

                    # Initialize state_data with sync job context
                    workflow_instance.state_data = {
                        "connection_id": connection_id,
                        "sync_job_id": str(sync_job.id),
                    }
                    workflow_instance.save(update_fields=["state_data"])

                    # Start workflow execution
                    workflow_instance = engine.start_instance(str(workflow_instance.id))

                    # Execute workflow synchronously to create assets immediately
                    # This ensures assets are created without waiting for background worker
                    try:
                        workflow_instance = engine.execute_instance(str(workflow_instance.id))
                        logger.info(
                            f"Workflow instance {workflow_instance.id} executed synchronously for sync job {sync_job.id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to execute workflow synchronously, will run in background: {e}",
                            exc_info=True,
                        )
                        # Workflow will be picked up by background worker if available

                    # Track workflow instance ID in sync job metadata
                    sync_job.metadata["workflow_instance_id"] = str(workflow_instance.id)
                    sync_job.save(update_fields=["metadata", "updated_at"])

                    logger.info(
                        f"Created workflow instance {workflow_instance.id} for sync job {sync_job.id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to create workflow instance for sync {sync_job.id}: {e}",
                        exc_info=True,
                    )
                    # Workflow creation failure doesn't fail the sync job creation
                    # The sync job can be manually processed later
                    sync_job.metadata["workflow_error"] = str(e)
                    sync_job.save(update_fields=["metadata", "updated_at"])

                # Add span attributes
                if span:
                    add_span_attributes(
                        {
                            "sync_job.id": str(sync_job.id),
                            "sync_job.direction": SyncDirection.PULL.value,
                            "sync_job.connection_id": connection_id,
                            "sync_job.listing_count": len(listing_ids) if listing_ids else 0,
                        }
                    )
                    set_span_status(StatusCode.OK)

                # Audit log
                try:
                    from hub.apps.audit.utils import create_audit_event

                    create_audit_event(
                        resource_type="MARKETPLACE_SYNC_JOB",
                        action="SYNC_JOB_CREATED",
                        actor_user=user_obj,
                        tenant=tenant_obj,
                        resource_id=str(sync_job.id),
                        result="SUCCESS",
                        details={
                            "sync_job_id": str(sync_job.id),
                            "connection_id": connection_id,
                            "direction": SyncDirection.PULL.value,
                            "listing_count": len(listing_ids) if listing_ids else 0,
                            "has_filters": bool(filters),
                            "request_id": self.request_id,
                        },
                        request=request,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to create audit log for sync job creation {sync_job.id}: {e}",
                        exc_info=True,
                    )

                # Publish events
                try:
                    # Publish integration.sync_job.created event (existing)
                    self.publish_sync_job_created(
                        sync_job_id=str(sync_job.id),
                        connection_id=connection_id,
                        direction=SyncDirection.PULL.value,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                        request_id=self.request_id,
                    )
                    # Publish marketplace.sync.started event (new)
                    MarketplaceEventPublisher.publish_sync_started(
                        self,
                        sync_job_id=str(sync_job.id),
                        connection_id=connection_id,
                        direction=SyncDirection.PULL.value,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                        correlation_id=self.request_id,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to publish sync events for {sync_job.id}: {e}",
                        exc_info=True,
                    )

                logger.info(
                    f"Created marketplace sync job {sync_job.id} (PULL) for connection {connection_id}"
                )

                return sync_job

            except (ValidationError, NotFoundError) as e:
                if span:
                    record_span_exception(e)
                    set_span_status(StatusCode.ERROR)
                raise
            except Exception as e:
                if span:
                    record_span_exception(e)
                    set_span_status(StatusCode.ERROR)
                logger.error(
                    f"Unexpected error creating sync job: {e}",
                    exc_info=True,
                    extra={
                        "connection_id": connection_id,
                        "tenant_id": effective_tenant_id,
                        "user_id": effective_user_id,
                    },
                )
                raise ServiceError(f"Failed to create sync job: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )

    def get_sync_job(
        self,
        tenant_id: str,
        sync_job_id: str,
        request: Optional[Any] = None,
    ) -> MarketplaceSyncJob:
        """
        Retrieve a marketplace sync job by its ID.

        Args:
            tenant_id: The ID of the tenant.
            sync_job_id: The ID of the sync job to retrieve.
            request: Optional request object for tracing context.

        Returns:
            The MarketplaceSyncJob instance.

        Raises:
            NotFoundError: If the sync job is not found for the given tenant.
        """
        from opentelemetry.trace import StatusCode

        from hub.apps.observability.span_instrumentation import (
            add_span_attributes,
            create_span,
            record_span_exception,
            set_span_status,
        )

        span_name = "MarketplaceIntegrationService.get_sync_job"
        effective_tenant_id = tenant_id or self.tenant_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            try:
                sync_job = self.get_resource_or_raise(
                    MarketplaceSyncJob, sync_job_id, tenant_id=effective_tenant_id
                )
            except DjangoValidationError as e:
                # Django ValidationError for invalid UUID format should be treated as NotFoundError
                raise NotFoundError(
                    f"Sync job {sync_job_id} not found",
                    details={"sync_job_id": sync_job_id, "error": str(e)},
                ) from e

            if span:
                add_span_attributes(
                    {
                        "sync_job.id": str(sync_job.id),
                        "sync_job.direction": sync_job.direction,
                        "sync_job.status": sync_job.status,
                        "sync_job.connection_id": str(sync_job.connection.id),
                    }
                )
                set_span_status(StatusCode.OK)

            return sync_job

        except NotFoundError as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            logger.error(
                f"Unexpected error getting sync job: {e}",
                exc_info=True,
                extra={
                    "sync_job_id": sync_job_id,
                    "tenant_id": effective_tenant_id,
                },
            )
            raise ServiceError(f"Failed to retrieve sync job: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )

    def list_sync_jobs(
        self,
        tenant_id: str,
        connection_id: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        request: Optional[Any] = None,
    ) -> List[MarketplaceSyncJob]:
        """
        List marketplace sync jobs for a tenant.

        Args:
            tenant_id: The ID of the tenant.
            connection_id: Optional filter by connection ID.
            direction: Optional filter by sync direction (PUSH, PULL, BIDIRECTIONAL).
            status: Optional filter by sync status (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL).
            limit: Maximum number of sync jobs to return.
            offset: Offset for pagination.
            request: Optional request object for tracing context.

        Returns:
            A list of MarketplaceSyncJob instances.
        """
        from opentelemetry.trace import StatusCode

        from hub.apps.observability.span_instrumentation import (
            add_span_attributes,
            create_span,
            record_span_exception,
            set_span_status,
        )

        span_name = "MarketplaceIntegrationService.list_sync_jobs"
        effective_tenant_id = tenant_id or self.tenant_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            filters = {"tenant_id": effective_tenant_id}
            if connection_id:
                filters["connection_id"] = connection_id
            if direction:
                # Validate direction
                valid_directions = [sd.value for sd in SyncDirection]
                if direction not in valid_directions:
                    raise ValidationError(
                        f"Invalid sync direction: {direction}",
                        details={"valid_directions": valid_directions},
                    )
                filters["direction"] = direction
            if status:
                # Validate status
                valid_statuses = [ss.value for ss in SyncStatus]
                if status not in valid_statuses:
                    raise ValidationError(
                        f"Invalid sync status: {status}", details={"valid_statuses": valid_statuses}
                    )
                filters["status"] = status

            sync_jobs = MarketplaceSyncJob.objects.filter(**filters)[offset : offset + limit]

            if span:
                add_span_attributes(
                    {
                        "tenant_id": effective_tenant_id,
                        "filter.connection_id": connection_id,
                        "filter.direction": direction,
                        "filter.status": status,
                        "pagination.limit": limit,
                        "pagination.offset": offset,
                        "results.count": len(sync_jobs),
                    }
                )
                set_span_status(StatusCode.OK)

            return list(sync_jobs)

        except ValidationError as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            logger.error(
                f"Unexpected error listing sync jobs: {e}",
                exc_info=True,
                extra={
                    "tenant_id": effective_tenant_id,
                    "connection_id": connection_id,
                    "direction": direction,
                    "status": status,
                },
            )
            raise ServiceError(f"Failed to list sync jobs: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )

    @transaction.atomic
    def cancel_sync_job(
        self,
        sync_job_id: str,
        tenant_id: str,
        user_id: str,
        reason: Optional[str] = None,
        request: Optional[Any] = None,
    ) -> MarketplaceSyncJob:
        """
        Cancel a running marketplace sync job.

        Only jobs in PENDING or RUNNING status can be cancelled.
        Terminal status jobs (COMPLETED, FAILED, PARTIAL) cannot be cancelled.

        Args:
            sync_job_id: The ID of the sync job to cancel.
            tenant_id: The ID of the tenant.
            user_id: The ID of the user cancelling the job.
            reason: Optional reason for cancellation.
            request: Optional request object for audit logging and tracing context.

        Returns:
            The updated MarketplaceSyncJob instance.

        Raises:
            NotFoundError: If the sync job is not found.
            ValidationError: If the sync job cannot be cancelled (already in terminal state).
            ServiceError: For other unexpected errors.
        """
        from django.contrib.auth import get_user_model
        from opentelemetry.trace import StatusCode

        from hub.apps.observability.span_instrumentation import (
            add_span_attributes,
            create_span,
            record_span_exception,
            set_span_status,
        )
        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.cancel_sync_job"
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            # Get sync job
            try:
                sync_job = self.get_resource_or_raise(
                    MarketplaceSyncJob, sync_job_id, tenant_id=effective_tenant_id
                )
            except DjangoValidationError as e:
                # Django ValidationError for invalid UUID format should be treated as NotFoundError
                raise NotFoundError(
                    f"Sync job {sync_job_id} not found",
                    details={"sync_job_id": sync_job_id, "error": str(e)},
                ) from e

            # Check if job can be cancelled
            if sync_job.is_terminal():
                raise ValidationError(
                    f"Sync job {sync_job_id} is in terminal state ({sync_job.status}) and cannot be cancelled",
                    details={
                        "sync_job_id": sync_job_id,
                        "status": sync_job.status,
                        "terminal_statuses": [
                            SyncStatus.COMPLETED.value,
                            SyncStatus.FAILED.value,
                            SyncStatus.PARTIAL.value,
                        ],
                    },
                )

            # Get tenant and user
            tenant_obj = self.get_resource_or_raise(Tenant, effective_tenant_id)
            user_obj = self.get_resource_or_raise(User, effective_user_id)

            # Update sync job status
            sync_job.status = SyncStatus.FAILED.value  # Mark as failed with cancellation
            sync_job.completed_at = timezone.now()
            if reason:
                sync_job.add_error(f"Job cancelled: {reason}", save=False)
            else:
                sync_job.add_error("Job cancelled by user", save=False)
            sync_job.save()

            # Cancel background job if exists
            if "job_id" in sync_job.metadata:
                try:
                    from hub.apps.jobs.models import Job, JobStatus

                    job_id = sync_job.metadata["job_id"]
                    job = Job.objects.get(id=job_id)
                    if (
                        job.status == JobStatus.PENDING.value
                        or job.status == JobStatus.RUNNING.value
                    ):
                        job.status = JobStatus.CANCELLED.value
                        job.save(update_fields=["status", "updated_at"])
                except Exception as e:
                    logger.warning(
                        f"Failed to cancel background job {job_id} for sync {sync_job.id}: {e}",
                        exc_info=True,
                    )

            # Add span attributes
            if span:
                add_span_attributes(
                    {
                        "sync_job.id": str(sync_job.id),
                        "sync_job.direction": sync_job.direction,
                        "sync_job.status": sync_job.status,
                        "sync_job.reason": reason,
                    }
                )
                set_span_status(StatusCode.OK)

            # Audit log
            try:
                from hub.apps.audit.utils import create_audit_event

                create_audit_event(
                    resource_type="MARKETPLACE_SYNC_JOB",
                    action="SYNC_JOB_CANCELLED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(sync_job.id),
                    result="SUCCESS",
                    details={
                        "sync_job_id": str(sync_job.id),
                        "connection_id": str(sync_job.connection.id),
                        "direction": sync_job.direction,
                        "previous_status": sync_job.status,
                        "reason": reason,
                        "request_id": self.request_id,
                    },
                    request=request,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit log for sync job cancellation {sync_job.id}: {e}",
                    exc_info=True,
                )

            # Publish event
            try:
                self.publish_sync_job_cancelled(
                    sync_job_id=str(sync_job.id),
                    connection_id=str(sync_job.connection.id),
                    direction=sync_job.direction,
                    reason=reason,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    request_id=self.request_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to publish sync_job.cancelled event for {sync_job.id}: {e}",
                    exc_info=True,
                )

            logger.info(
                f"Cancelled marketplace sync job {sync_job.id} for tenant {effective_tenant_id}"
            )

            return sync_job

        except (ValidationError, NotFoundError) as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            logger.error(
                f"Unexpected error cancelling sync job: {e}",
                exc_info=True,
                extra={
                    "sync_job_id": sync_job_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )
            raise ServiceError(f"Failed to cancel sync job: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )

    def sync_workflow_status_to_sync_job(
        self,
        sync_job_id: str,
        tenant_id: Optional[str] = None,
    ) -> MarketplaceSyncJob:
        """
        Sync workflow status to sync job status.

        Updates sync job status based on the associated workflow instance status.
        This should be called when workflow status changes (via event handlers or polling).

        Args:
            sync_job_id: Sync job ID
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)

        Returns:
            Updated MarketplaceSyncJob instance

        Raises:
            NotFoundError: If sync job not found
        """
        from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus

        effective_tenant_id = tenant_id or self.tenant_id

        # Get sync job (get_sync_job handles invalid UUID -> NotFoundError)
        sync_job = self.get_sync_job(
            tenant_id=effective_tenant_id,
            sync_job_id=sync_job_id,
        )

        # Get workflow instance ID from metadata
        workflow_instance_id = sync_job.metadata.get("workflow_instance_id")
        if not workflow_instance_id:
            logger.debug(f"No workflow instance ID found for sync job {sync_job_id}")
            return sync_job

        try:
            # Validate workflow_instance_id is a valid UUID before ORM query
            import uuid as _uuid
            try:
                _uuid.UUID(str(workflow_instance_id))
            except (ValueError, AttributeError):
                logger.warning(
                    f"Invalid workflow_instance_id {workflow_instance_id!r} for sync job {sync_job_id}"
                )
                return sync_job

            # Get workflow instance
            workflow_instance = WorkflowInstance.objects.get(
                id=workflow_instance_id, tenant_id=effective_tenant_id
            )

            # Track previous status to avoid duplicate event publishing
            previous_status = sync_job.status

            # Map workflow status to sync job status
            workflow_status = WorkflowStatus(workflow_instance.status)

            if workflow_status == WorkflowStatus.COMPLETED:
                sync_job.status = SyncStatus.COMPLETED.value
                sync_job.completed_at = workflow_instance.completed_at or timezone.now()
            elif workflow_status == WorkflowStatus.FAILED:
                sync_job.status = SyncStatus.FAILED.value
                sync_job.completed_at = workflow_instance.completed_at or timezone.now()
                # Add workflow error to sync job errors
                if workflow_instance.error_message:
                    sync_job.add_error(workflow_instance.error_message, save=False)
            elif workflow_status == WorkflowStatus.RUNNING:
                sync_job.status = SyncStatus.RUNNING.value
            elif workflow_status == WorkflowStatus.CANCELLED:
                sync_job.status = SyncStatus.FAILED.value
                sync_job.completed_at = workflow_instance.completed_at or timezone.now()
                sync_job.add_error("Workflow was cancelled", save=False)
            elif workflow_status == WorkflowStatus.ROLLED_BACK:
                sync_job.status = SyncStatus.FAILED.value
                sync_job.completed_at = workflow_instance.completed_at or timezone.now()
                sync_job.add_error("Workflow was rolled back", save=False)

            # Update progress from workflow state_data
            if workflow_instance.state_data:
                progress_percentage = workflow_instance.state_data.get("progress_percentage")
                if progress_percentage is not None:
                    if sync_job.metadata is None:
                        sync_job.metadata = {}
                    sync_job.metadata["progress_percentage"] = progress_percentage
                    sync_job.metadata["current_step"] = workflow_instance.state_data.get(
                        "current_step_name"
                    )

            sync_job.save()

            # Publish marketplace events if status changed to completed or failed
            if previous_status != sync_job.status:
                try:
                    connection_id = str(sync_job.connection.id)
                    direction = sync_job.direction
                    items_synced = sync_job.items_synced or 0
                    items_failed = sync_job.items_failed or 0

                    if sync_job.status == SyncStatus.COMPLETED.value:
                        # Determine status string (COMPLETED or PARTIAL)
                        status_str = (
                            SyncStatus.PARTIAL.value
                            if items_failed > 0
                            else SyncStatus.COMPLETED.value
                        )
                        MarketplaceEventPublisher.publish_sync_completed(
                            self,
                            sync_job_id=str(sync_job.id),
                            connection_id=connection_id,
                            direction=direction,
                            status=status_str,
                            items_synced=items_synced,
                            items_failed=items_failed,
                            tenant_id=effective_tenant_id,
                            user_id=self.user_id,
                            correlation_id=self.request_id,
                        )
                    elif sync_job.status == SyncStatus.FAILED.value:
                        # Get error message from errors list or workflow error
                        error_message = "Sync job failed"
                        error_details = {}
                        if sync_job.errors:
                            first_error = (
                                sync_job.errors[0]
                                if isinstance(sync_job.errors, list)
                                else sync_job.errors
                            )
                            error_message = (
                                str(first_error)
                                if not isinstance(first_error, str)
                                else first_error
                            )
                            error_details = {"errors": sync_job.errors}
                        elif workflow_instance.error_message:
                            error_message = workflow_instance.error_message
                            error_details = {"workflow_error": workflow_instance.error_message}

                        MarketplaceEventPublisher.publish_sync_failed(
                            self,
                            sync_job_id=str(sync_job.id),
                            connection_id=connection_id,
                            direction=direction,
                            error_message=error_message,
                            error_details=error_details,
                            tenant_id=effective_tenant_id,
                            user_id=self.user_id,
                            correlation_id=self.request_id,
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to publish marketplace sync event for {sync_job_id}: {e}",
                        exc_info=True,
                    )

            logger.info(f"Synced workflow status to sync job {sync_job_id}: {sync_job.status}")

        except WorkflowInstance.DoesNotExist:
            logger.warning(
                f"Workflow instance {workflow_instance_id} not found for sync job {sync_job_id}"
            )
        except Exception as e:
            logger.error(
                f"Error syncing workflow status for sync job {sync_job_id}: {e}", exc_info=True
            )

        return sync_job

    def update_sync_job_progress(
        self,
        sync_job_id: str,
        progress_percentage: int,
        current_step: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> MarketplaceSyncJob:
        """
        Update sync job progress.

        Updates progress percentage and current step in sync job metadata.
        This can be called from workflow progress tracking.

        Args:
            sync_job_id: Sync job ID
            progress_percentage: Progress percentage (0-100)
            current_step: Optional current step name
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)

        Returns:
            Updated MarketplaceSyncJob instance

        Raises:
            NotFoundError: If sync job not found
        """
        effective_tenant_id = tenant_id or self.tenant_id

        # Get sync job (get_sync_job handles invalid UUID -> NotFoundError)
        sync_job = self.get_sync_job(
            tenant_id=effective_tenant_id,
            sync_job_id=sync_job_id,
        )

        # Update progress in metadata
        if sync_job.metadata is None:
            sync_job.metadata = {}

        sync_job.metadata["progress_percentage"] = max(0, min(100, progress_percentage))
        if current_step:
            sync_job.metadata["current_step"] = current_step

        sync_job.save(update_fields=["metadata", "updated_at"])

        logger.info(
            f"Updated progress for sync job {sync_job_id}: {sync_job.metadata['progress_percentage']}%"
        )

        return sync_job

    @transaction.atomic
    def schedule_sync(
        self,
        connection_id: str,
        tenant_id: str,
        user_id: str,
        name: str,
        direction: str,
        schedule_type: str,
        schedule_config: Dict[str, Any],
        sync_options: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        request: Optional[Any] = None,
    ) -> ScheduledMarketplaceSync:
        """
        Schedule a recurring marketplace sync operation.

        Creates a ScheduledMarketplaceSync record that will trigger sync operations
        automatically based on the specified schedule (daily, weekly, monthly, or custom cron).

        Args:
            connection_id: The ID of the marketplace connection to use
            tenant_id: The ID of the tenant
            user_id: The ID of the user creating the schedule
            name: Unique name for the scheduled sync (per tenant)
            direction: Sync direction (PUSH, PULL, or BIDIRECTIONAL)
            schedule_type: Schedule type (DAILY, WEEKLY, MONTHLY, CUSTOM_CRON)
            schedule_config: Schedule configuration dictionary:
                - For DAILY: {"time": "HH:MM"} (e.g., {"time": "02:00"})
                - For WEEKLY: {"days_of_week": [0,1,2], "time": "HH:MM"} (0=Monday)
                - For MONTHLY: {"day_of_month": 1, "time": "HH:MM"}
                - For CUSTOM_CRON: {"cron": "0 2 * * *", "timezone": "UTC"}
            sync_options: Optional sync options (asset_ids, listing_ids, filters, options)
            description: Optional description
            request: Optional HTTP request for audit logging

        Returns:
            Created ScheduledMarketplaceSync instance

        Raises:
            NotFoundError: If connection not found
            ValidationError: If validation fails
            ConflictError: If schedule name already exists for tenant
        """
        from django.contrib.auth import get_user_model
        from opentelemetry.trace import StatusCode

        from hub.apps.observability.span_instrumentation import (
            add_span_attributes,
            create_span,
            record_span_exception,
            set_span_status,
        )
        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.schedule_sync"
        span_context = None
        span = None

        try:
            # Create distributed tracing span
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            effective_tenant_id = tenant_id or self.tenant_id
            effective_user_id = user_id or self.user_id

            if span:
                add_span_attributes(
                    {
                        "connection_id": connection_id,
                        "tenant_id": effective_tenant_id,
                        "direction": direction,
                        "schedule_type": schedule_type,
                    }
                )

            # Get connection
            try:
                connection = self.get_resource_or_raise(
                    MarketplaceConnection, connection_id, tenant_id=effective_tenant_id
                )
            except DjangoValidationError as e:
                raise NotFoundError(
                    f"Connection {connection_id} not found",
                    details={"connection_id": connection_id, "error": str(e)},
                ) from e

            # Validate connection is active
            if not connection.is_active:
                raise ValidationError(
                    f"Connection {connection_id} is not active",
                    details={"connection_id": connection_id, "is_active": False},
                )

            # Validate direction
            valid_directions = [sd.value for sd in SyncDirection]
            if direction not in valid_directions:
                raise ValidationError(
                    f"Invalid sync direction. Must be one of: {', '.join(valid_directions)}",
                    details={"direction": direction},
                )

            # Validate schedule_type
            valid_schedule_types = [st.value for st in ScheduleType]
            if schedule_type not in valid_schedule_types:
                raise ValidationError(
                    f"Invalid schedule type. Must be one of: {', '.join(valid_schedule_types)}",
                    details={"schedule_type": schedule_type},
                )

            # Validate schedule_config based on schedule_type
            if schedule_type == ScheduleType.CUSTOM_CRON.value:
                if not schedule_config.get("cron"):
                    raise ValidationError(
                        "Cron expression is required for CUSTOM_CRON schedule type",
                        details={"schedule_config": schedule_config},
                    )
                # Validate cron expression
                try:
                    from croniter import croniter

                    croniter(schedule_config["cron"])
                except Exception as e:
                    raise ValidationError(
                        f"Invalid cron expression: {str(e)}",
                        details={"schedule_config": schedule_config, "error": str(e)},
                    ) from e

            # Get tenant and user
            tenant_obj = self.get_resource_or_raise(Tenant, effective_tenant_id)
            user_obj = self.get_resource_or_raise(User, effective_user_id)

            # Check if schedule name already exists for tenant
            if ScheduledMarketplaceSync.objects.filter(tenant=tenant_obj, name=name).exists():
                raise ConflictError(
                    f"Scheduled sync with name '{name}' already exists for tenant",
                    details={"name": name, "tenant_id": effective_tenant_id},
                )

            # Create scheduled sync
            scheduled_sync = ScheduledMarketplaceSync.objects.create(
                tenant=tenant_obj,
                connection=connection,
                name=name,
                description=description,
                direction=direction,
                schedule_type=schedule_type,
                schedule_config=schedule_config,
                sync_options=sync_options or {},
                status=ScheduledMarketplaceSyncStatus.ACTIVE,
                created_by=user_obj,
            )

            logger.info(
                f"Created scheduled marketplace sync {scheduled_sync.id} for connection {connection_id}"
            )

            if span:
                add_span_attributes(
                    {
                        "scheduled_sync.id": str(scheduled_sync.id),
                        "scheduled_sync.next_run_at": (
                            scheduled_sync.next_run_at.isoformat()
                            if scheduled_sync.next_run_at
                            else None
                        ),
                    }
                )
                set_span_status(StatusCode.OK)

            # Audit log
            try:
                from hub.apps.audit.utils import create_audit_event

                create_audit_event(
                    resource_type="SCHEDULED_MARKETPLACE_SYNC",
                    action="SCHEDULED_SYNC_CREATED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(scheduled_sync.id),
                    result="SUCCESS",
                    details={
                        "scheduled_sync_id": str(scheduled_sync.id),
                        "connection_id": connection_id,
                        "direction": direction,
                        "schedule_type": schedule_type,
                        "next_run_at": (
                            scheduled_sync.next_run_at.isoformat()
                            if scheduled_sync.next_run_at
                            else None
                        ),
                        "request_id": self.request_id,
                    },
                    request=request,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit log for scheduled sync creation {scheduled_sync.id}: {e}",
                    exc_info=True,
                )

            # Publish event
            try:
                self.publish_scheduled_sync_created(
                    scheduled_sync_id=str(scheduled_sync.id),
                    connection_id=connection_id,
                    direction=direction,
                    schedule_type=schedule_type,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    request_id=self.request_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to publish scheduled_sync.created event for {scheduled_sync.id}: {e}",
                    exc_info=True,
                )

            return scheduled_sync

        except (ValidationError, NotFoundError, ConflictError) as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            logger.error(
                f"Unexpected error creating scheduled sync: {e}",
                exc_info=True,
                extra={
                    "connection_id": connection_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )
            raise ServiceError(f"Failed to create scheduled sync: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )

    @transaction.atomic
    def unschedule_sync(
        self,
        scheduled_sync_id: str,
        tenant_id: Optional[str] = None,
        request: Optional[Any] = None,
    ) -> None:
        """
        Unschedule a recurring marketplace sync operation.

        Deletes the ScheduledMarketplaceSync record, stopping all future scheduled runs.

        Args:
            scheduled_sync_id: The ID of the scheduled sync to unschedule
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            request: Optional HTTP request for audit logging

        Raises:
            NotFoundError: If scheduled sync not found
        """
        from django.contrib.auth import get_user_model
        from opentelemetry.trace import StatusCode

        from hub.apps.observability.span_instrumentation import (
            add_span_attributes,
            create_span,
            record_span_exception,
            set_span_status,
        )

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.unschedule_sync"
        span_context = None
        span = None

        try:
            # Create distributed tracing span
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            effective_tenant_id = tenant_id or self.tenant_id

            if span:
                add_span_attributes(
                    {
                        "scheduled_sync_id": scheduled_sync_id,
                        "tenant_id": effective_tenant_id,
                    }
                )

            # Get scheduled sync
            try:
                scheduled_sync = self.get_resource_or_raise(
                    ScheduledMarketplaceSync, scheduled_sync_id, tenant_id=effective_tenant_id
                )
            except DjangoValidationError as e:
                raise NotFoundError(
                    f"Scheduled sync {scheduled_sync_id} not found",
                    details={"scheduled_sync_id": scheduled_sync_id, "error": str(e)},
                ) from e

            # Store details for audit log
            sync_name = scheduled_sync.name
            connection_id = str(scheduled_sync.connection.id)
            direction = scheduled_sync.direction
            schedule_type = scheduled_sync.schedule_type

            # Delete scheduled sync
            scheduled_sync.delete()

            logger.info(f"Deleted scheduled marketplace sync {scheduled_sync_id}")

            if span:
                set_span_status(StatusCode.OK)

            # Audit log
            try:
                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant

                tenant_obj = self.get_resource_or_raise(Tenant, effective_tenant_id)
                user_obj = None
                if self.user_id:
                    try:
                        user_obj = self.get_resource_or_raise(User, self.user_id)
                    except NotFoundError:
                        pass  # User might not exist

                create_audit_event(
                    resource_type="SCHEDULED_MARKETPLACE_SYNC",
                    action="SCHEDULED_SYNC_DELETED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=scheduled_sync_id,
                    result="SUCCESS",
                    details={
                        "scheduled_sync_id": scheduled_sync_id,
                        "scheduled_sync_name": sync_name,
                        "connection_id": connection_id,
                        "direction": direction,
                        "schedule_type": schedule_type,
                        "request_id": self.request_id,
                    },
                    request=request,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit log for scheduled sync deletion {scheduled_sync_id}: {e}",
                    exc_info=True,
                )

            # Publish event
            try:
                self.publish_scheduled_sync_deleted(
                    scheduled_sync_id=scheduled_sync_id,
                    connection_id=connection_id,
                    tenant_id=effective_tenant_id,
                    request_id=self.request_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to publish scheduled_sync.deleted event for {scheduled_sync_id}: {e}",
                    exc_info=True,
                )

        except NotFoundError as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            logger.error(
                f"Unexpected error deleting scheduled sync: {e}",
                exc_info=True,
                extra={
                    "scheduled_sync_id": scheduled_sync_id,
                    "tenant_id": effective_tenant_id,
                },
            )
            raise ServiceError(f"Failed to delete scheduled sync: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )
