    @transaction.atomic
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
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model
        from hub.apps.jobs.utils import create_job, get_job_timeout
        from hub.apps.jobs.models import JobType

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.sync_assets_to_marketplace"
        with create_span(span_name, kind=1) as span:
            effective_tenant_id = tenant_id or self.tenant_id
            effective_user_id = user_id or self.user_id

            try:
                # Get connection
                connection = self.get_resource_or_raise(
                    MarketplaceConnection,
                    connection_id,
                    tenant_id=effective_tenant_id
                )

                # Validate connection is active
                if not connection.is_active:
                    raise ValidationError(
                        f"Connection {connection_id} is not active",
                        details={'connection_id': connection_id, 'is_active': False}
                    )

                # Validate asset_ids
                if not asset_ids or not isinstance(asset_ids, list):
                    raise ValidationError(
                        "asset_ids must be a non-empty list",
                        details={'asset_ids_type': type(asset_ids).__name__}
                    )

                # Validate marketplace type supports PUSH
                marketplace_type = MarketplaceType(connection.marketplace_type)
                factory = MarketplaceConnectorFactory()
                if not factory.is_supported(marketplace_type):
                    raise ValidationError(
                        f"Marketplace type {marketplace_type.value} is not supported",
                        details={'marketplace_type': marketplace_type.value}
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
                        'asset_ids': asset_ids,
                        'options': options or {},
                        'request_id': self.request_id,
                    }
                )

                # Create background job for async processing
                try:
                    job = create_job(
                        tenant=tenant_obj,
                        user=user_obj,
                        job_type=JobType.MARKETPLACE_SYNC,
                        resource_type="MARKETPLACE_SYNC_JOB",
                        resource_id=str(sync_job.id),
                        details_json={
                            'sync_job_id': str(sync_job.id),
                            'connection_id': connection_id,
                            'direction': SyncDirection.PUSH.value,
                            'asset_ids': asset_ids,
                            'options': options or {},
                        },
                        timeout_seconds=get_job_timeout(JobType.MARKETPLACE_SYNC),
                    )
                    sync_job.metadata['job_id'] = str(job.id)
                    sync_job.save(update_fields=['metadata', 'updated_at'])
                except Exception as e:
                    logger.warning(
                        f"Failed to create background job for sync {sync_job.id}: {e}",
                        exc_info=True,
                    )
                    # Job creation failure doesn't fail the sync job creation
                    # The sync job can be manually processed later

                # Add span attributes
                if span:
                    add_span_attributes({
                        "sync_job.id": str(sync_job.id),
                        "sync_job.direction": SyncDirection.PUSH.value,
                        "sync_job.connection_id": connection_id,
                        "sync_job.asset_count": len(asset_ids),
                    })
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

                # Publish event
                try:
                    self.publish_sync_job_created(
                        sync_job_id=str(sync_job.id),
                        connection_id=connection_id,
                        direction=SyncDirection.PUSH.value,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                        request_id=self.request_id,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to publish sync_job.created event for {sync_job.id}: {e}",
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
                    }
                )
                raise ServiceError(f"Failed to create sync job: {e}") from e

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
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model
        from hub.apps.jobs.utils import create_job, get_job_timeout
        from hub.apps.jobs.models import JobType

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.sync_from_marketplace"
        with create_span(span_name, kind=1) as span:
            effective_tenant_id = tenant_id or self.tenant_id
            effective_user_id = user_id or self.user_id

            try:
                # Get connection
                connection = self.get_resource_or_raise(
                    MarketplaceConnection,
                    connection_id,
                    tenant_id=effective_tenant_id
                )

                # Validate connection is active
                if not connection.is_active:
                    raise ValidationError(
                        f"Connection {connection_id} is not active",
                        details={'connection_id': connection_id, 'is_active': False}
                    )

                # Validate marketplace type supports PULL
                marketplace_type = MarketplaceType(connection.marketplace_type)
                factory = MarketplaceConnectorFactory()
                if not factory.is_supported(marketplace_type):
                    raise ValidationError(
                        f"Marketplace type {marketplace_type.value} is not supported",
                        details={'marketplace_type': marketplace_type.value}
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
                        'listing_ids': listing_ids or [],
                        'filters': filters or {},
                        'options': options or {},
                        'request_id': self.request_id,
                    }
                )

                # Create background job for async processing
                try:
                    job = create_job(
                        tenant=tenant_obj,
                        user=user_obj,
                        job_type=JobType.MARKETPLACE_SYNC,
                        resource_type="MARKETPLACE_SYNC_JOB",
                        resource_id=str(sync_job.id),
                        details_json={
                            'sync_job_id': str(sync_job.id),
                            'connection_id': connection_id,
                            'direction': SyncDirection.PULL.value,
                            'listing_ids': listing_ids,
                            'filters': filters or {},
                            'options': options or {},
                        },
                        timeout_seconds=get_job_timeout(JobType.MARKETPLACE_SYNC),
                    )
                    sync_job.metadata['job_id'] = str(job.id)
                    sync_job.save(update_fields=['metadata', 'updated_at'])
                except Exception as e:
                    logger.warning(
                        f"Failed to create background job for sync {sync_job.id}: {e}",
                        exc_info=True,
                    )

                # Add span attributes
                if span:
                    add_span_attributes({
                        "sync_job.id": str(sync_job.id),
                        "sync_job.direction": SyncDirection.PULL.value,
                        "sync_job.connection_id": connection_id,
                        "sync_job.listing_count": len(listing_ids) if listing_ids else 0,
                    })
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

                # Publish event
                try:
                    self.publish_sync_job_created(
                        sync_job_id=str(sync_job.id),
                        connection_id=connection_id,
                        direction=SyncDirection.PULL.value,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                        request_id=self.request_id,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to publish sync_job.created event for {sync_job.id}: {e}",
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
                    }
                )
                raise ServiceError(f"Failed to create sync job: {e}") from e

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
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode

        span_name = "MarketplaceIntegrationService.get_sync_job"
        with create_span(span_name, kind=1) as span:
            effective_tenant_id = tenant_id or self.tenant_id

            try:
                sync_job = self.get_resource_or_raise(
                    MarketplaceSyncJob,
                    sync_job_id,
                    tenant_id=effective_tenant_id
                )

                if span:
                    add_span_attributes({
                        "sync_job.id": str(sync_job.id),
                        "sync_job.direction": sync_job.direction,
                        "sync_job.status": sync_job.status,
                        "sync_job.connection_id": str(sync_job.connection.id),
                    })
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
                    }
                )
                raise ServiceError(f"Failed to retrieve sync job: {e}") from e

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
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode

        span_name = "MarketplaceIntegrationService.list_sync_jobs"
        with create_span(span_name, kind=1) as span:
            effective_tenant_id = tenant_id or self.tenant_id

            try:
                filters = {'tenant_id': effective_tenant_id}
                if connection_id:
                    filters['connection_id'] = connection_id
                if direction:
                    # Validate direction
                    valid_directions = [sd.value for sd in SyncDirection]
                    if direction not in valid_directions:
                        raise ValidationError(
                            f"Invalid sync direction: {direction}",
                            details={'valid_directions': valid_directions}
                        )
                    filters['direction'] = direction
                if status:
                    # Validate status
                    valid_statuses = [ss.value for ss in SyncStatus]
                    if status not in valid_statuses:
                        raise ValidationError(
                            f"Invalid sync status: {status}",
                            details={'valid_statuses': valid_statuses}
                        )
                    filters['status'] = status

                sync_jobs = MarketplaceSyncJob.objects.filter(**filters)[offset:offset + limit]

                if span:
                    add_span_attributes({
                        "tenant_id": effective_tenant_id,
                        "filter.connection_id": connection_id,
                        "filter.direction": direction,
                        "filter.status": status,
                        "pagination.limit": limit,
                        "pagination.offset": offset,
                        "results.count": len(sync_jobs),
                    })
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
                    }
                )
                raise ServiceError(f"Failed to list sync jobs: {e}") from e

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
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.cancel_sync_job"
        with create_span(span_name, kind=1) as span:
            effective_tenant_id = tenant_id or self.tenant_id
            effective_user_id = user_id or self.user_id

            try:
                # Get sync job
                sync_job = self.get_resource_or_raise(
                    MarketplaceSyncJob,
                    sync_job_id,
                    tenant_id=effective_tenant_id
                )

                # Check if job can be cancelled
                if sync_job.is_terminal():
                    raise ValidationError(
                        f"Sync job {sync_job_id} is in terminal state ({sync_job.status}) and cannot be cancelled",
                        details={
                            'sync_job_id': sync_job_id,
                            'status': sync_job.status,
                            'terminal_statuses': [SyncStatus.COMPLETED.value, SyncStatus.FAILED.value, SyncStatus.PARTIAL.value]
                        }
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
                if 'job_id' in sync_job.metadata:
                    try:
                        from hub.apps.jobs.models import Job, JobStatus
                        job_id = sync_job.metadata['job_id']
                        job = Job.objects.get(id=job_id)
                        if job.status == JobStatus.PENDING.value or job.status == JobStatus.RUNNING.value:
                            job.status = JobStatus.CANCELLED.value
                            job.save(update_fields=['status', 'updated_at'])
                    except Exception as e:
                        logger.warning(
                            f"Failed to cancel background job {job_id} for sync {sync_job.id}: {e}",
                            exc_info=True,
                        )

                # Add span attributes
                if span:
                    add_span_attributes({
                        "sync_job.id": str(sync_job.id),
                        "sync_job.direction": sync_job.direction,
                        "sync_job.status": sync_job.status,
                        "sync_job.reason": reason,
                    })
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
                    }
                )
                raise ServiceError(f"Failed to cancel sync job: {e}") from e

