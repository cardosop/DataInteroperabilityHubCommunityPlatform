    # --- Mapping CRUD methods ---

    @transaction.atomic
    def create_mapping(
        self,
        connection_id: str,
        hub_asset_id: str,
        external_listing_id: str,
        external_resource_ids: Optional[List[str]] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Any] = None,
    ) -> MarketplaceMapping:
        """
        Create a marketplace mapping between a Hub asset and an external marketplace listing.

        Args:
            connection_id: The ID of the marketplace connection.
            hub_asset_id: The ID of the Hub asset to map.
            external_listing_id: The external marketplace listing identifier.
            external_resource_ids: Optional list of external resource identifiers.
            sync_metadata: Optional dictionary of synchronization metadata.
            tenant_id: Optional tenant ID (uses service tenant_id if not provided).
            user_id: Optional user ID (uses service user_id if not provided).
            request: Optional request object for audit logging and tracing context.

        Returns:
            The created MarketplaceMapping instance.

        Raises:
            NotFoundError: If connection or asset not found.
            ValidationError: If input data is invalid or mapping already exists.
            ServiceError: For other unexpected errors.
        """
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model
        from hub.apps.assets.models import Asset

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.create_mapping"
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            # Get connection
            try:
                connection = self.get_resource_or_raise(
                    MarketplaceConnection,
                    connection_id,
                    tenant_id=effective_tenant_id
                )
            except DjangoValidationError as e:
                raise NotFoundError(
                    f"Connection {connection_id} not found",
                    details={'connection_id': connection_id, 'error': str(e)}
                ) from e

            # Validate connection is active
            if not connection.is_active:
                raise ValidationError(
                    f"Connection {connection_id} is not active",
                    details={'connection_id': connection_id, 'is_active': False}
                )

            # Get asset
            try:
                asset = self.get_resource_or_raise(
                    Asset,
                    hub_asset_id,
                    tenant_id=effective_tenant_id
                )
            except DjangoValidationError as e:
                raise NotFoundError(
                    f"Asset {hub_asset_id} not found",
                    details={'hub_asset_id': hub_asset_id, 'error': str(e)}
                ) from e

            # Validate external_listing_id
            if not external_listing_id or not external_listing_id.strip():
                raise ValidationError(
                    "external_listing_id cannot be empty",
                    details={'external_listing_id': external_listing_id}
                )

            # Check for existing mapping
            if MarketplaceMapping.objects.filter(
                connection=connection,
                hub_asset=asset
            ).exists():
                raise ConflictError(
                    f"Mapping already exists for connection {connection_id} and asset {hub_asset_id}",
                    details={
                        'connection_id': connection_id,
                        'hub_asset_id': hub_asset_id
                    }
                )

            # Get tenant and user
            tenant_obj = self.get_resource_or_raise(Tenant, effective_tenant_id)
            user_obj = self.get_resource_or_raise(User, effective_user_id)

            # Create mapping
            mapping = MarketplaceMapping.objects.create(
                tenant=tenant_obj,
                connection=connection,
                hub_asset=asset,
                external_listing_id=external_listing_id.strip(),
                external_resource_ids=external_resource_ids or [],
                sync_metadata=sync_metadata or {}
            )

            # Add span attributes
            if span:
                add_span_attributes({
                    "mapping.id": str(mapping.id),
                    "mapping.connection_id": connection_id,
                    "mapping.hub_asset_id": hub_asset_id,
                    "mapping.external_listing_id": external_listing_id,
                })
                set_span_status(StatusCode.OK)

            # Audit log
            try:
                from hub.apps.audit.utils import create_audit_event
                create_audit_event(
                    resource_type="MARKETPLACE_MAPPING",
                    action="MAPPING_CREATED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(mapping.id),
                    result="SUCCESS",
                    details={
                        "mapping_id": str(mapping.id),
                        "connection_id": connection_id,
                        "hub_asset_id": hub_asset_id,
                        "external_listing_id": external_listing_id,
                        "request_id": self.request_id,
                    },
                    request=request,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit log for mapping creation {mapping.id}: {e}",
                    exc_info=True,
                )

            # Publish event
            try:
                self.publish_mapping_created(
                    mapping_id=str(mapping.id),
                    connection_id=connection_id,
                    hub_asset_id=hub_asset_id,
                    external_listing_id=external_listing_id,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    request_id=self.request_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to publish mapping.created event for {mapping.id}: {e}",
                    exc_info=True,
                )

            logger.info(
                f"Created marketplace mapping {mapping.id} for connection {connection_id} and asset {hub_asset_id}"
            )

            return mapping

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
                f"Unexpected error creating mapping: {e}",
                exc_info=True,
                extra={
                    "connection_id": connection_id,
                    "hub_asset_id": hub_asset_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                }
            )
            raise ServiceError(f"Failed to create mapping: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass

    def get_mapping(
        self,
        mapping_id: str,
        tenant_id: Optional[str] = None,
        request: Optional[Any] = None,
    ) -> MarketplaceMapping:
        """
        Retrieve a marketplace mapping by its ID.

        Args:
            mapping_id: The ID of the mapping to retrieve.
            tenant_id: Optional tenant ID (uses service tenant_id if not provided).
            request: Optional request object for tracing context.

        Returns:
            The MarketplaceMapping instance.

        Raises:
            NotFoundError: If the mapping is not found for the given tenant.
        """
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode

        span_name = "MarketplaceIntegrationService.get_mapping"
        effective_tenant_id = tenant_id or self.tenant_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            try:
                mapping = self.get_resource_or_raise(
                    MarketplaceMapping,
                    mapping_id,
                    tenant_id=effective_tenant_id
                )
            except DjangoValidationError as e:
                raise NotFoundError(
                    f"Mapping {mapping_id} not found",
                    details={'mapping_id': mapping_id, 'error': str(e)}
                ) from e

            if span:
                add_span_attributes({
                    "mapping.id": str(mapping.id),
                    "mapping.connection_id": str(mapping.connection.id),
                    "mapping.hub_asset_id": str(mapping.hub_asset.id),
                    "mapping.external_listing_id": mapping.external_listing_id,
                })
                set_span_status(StatusCode.OK)

            return mapping

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
                f"Unexpected error getting mapping: {e}",
                exc_info=True,
                extra={
                    "mapping_id": mapping_id,
                    "tenant_id": effective_tenant_id,
                }
            )
            raise ServiceError(f"Failed to retrieve mapping: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass

    def list_mappings(
        self,
        tenant_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        hub_asset_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        request: Optional[Any] = None,
    ) -> List[MarketplaceMapping]:
        """
        List marketplace mappings for a tenant.

        Args:
            tenant_id: Optional tenant ID (uses service tenant_id if not provided).
            connection_id: Optional filter by connection ID.
            hub_asset_id: Optional filter by Hub asset ID.
            limit: Maximum number of mappings to return.
            offset: Offset for pagination.
            request: Optional request object for tracing context.

        Returns:
            A list of MarketplaceMapping instances.
        """
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode

        span_name = "MarketplaceIntegrationService.list_mappings"
        effective_tenant_id = tenant_id or self.tenant_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            filters = {'tenant_id': effective_tenant_id}
            if connection_id:
                try:
                    # Validate connection_id is valid UUID
                    import uuid
                    uuid.UUID(connection_id)
                    filters['connection_id'] = connection_id
                except (ValueError, TypeError):
                    raise ValidationError(
                        f"Invalid connection_id format: {connection_id}",
                        details={'connection_id': connection_id}
                    )
            if hub_asset_id:
                try:
                    # Validate hub_asset_id is valid UUID
                    import uuid
                    uuid.UUID(hub_asset_id)
                    filters['hub_asset_id'] = hub_asset_id
                except (ValueError, TypeError):
                    raise ValidationError(
                        f"Invalid hub_asset_id format: {hub_asset_id}",
                        details={'hub_asset_id': hub_asset_id}
                    )

            mappings = MarketplaceMapping.objects.filter(**filters)[offset:offset + limit]

            if span:
                add_span_attributes({
                    "tenant_id": effective_tenant_id,
                    "filter.connection_id": connection_id,
                    "filter.hub_asset_id": hub_asset_id,
                    "pagination.limit": limit,
                    "pagination.offset": offset,
                    "results.count": len(mappings),
                })
                set_span_status(StatusCode.OK)

            return list(mappings)

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
                f"Unexpected error listing mappings: {e}",
                exc_info=True,
                extra={
                    "tenant_id": effective_tenant_id,
                    "connection_id": connection_id,
                    "hub_asset_id": hub_asset_id,
                }
            )
            raise ServiceError(f"Failed to list mappings: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass

    @transaction.atomic
    def update_mapping(
        self,
        mapping_id: str,
        external_listing_id: Optional[str] = None,
        external_resource_ids: Optional[List[str]] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Any] = None,
    ) -> MarketplaceMapping:
        """
        Update a marketplace mapping.

        Args:
            mapping_id: The ID of the mapping to update.
            external_listing_id: Optional new external listing ID.
            external_resource_ids: Optional new list of external resource IDs.
            sync_metadata: Optional sync metadata to merge with existing metadata.
            tenant_id: Optional tenant ID (uses service tenant_id if not provided).
            user_id: Optional user ID (uses service user_id if not provided).
            request: Optional request object for audit logging and tracing context.

        Returns:
            The updated MarketplaceMapping instance.

        Raises:
            NotFoundError: If the mapping is not found.
            ValidationError: If input data is invalid.
            ServiceError: For other unexpected errors.
        """
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.update_mapping"
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            # Get mapping
            try:
                mapping = self.get_resource_or_raise(
                    MarketplaceMapping,
                    mapping_id,
                    tenant_id=effective_tenant_id
                )
            except DjangoValidationError as e:
                raise NotFoundError(
                    f"Mapping {mapping_id} not found",
                    details={'mapping_id': mapping_id, 'error': str(e)}
                ) from e

            # Track changes
            changes = {}
            update_fields = []

            # Update external_listing_id if provided
            if external_listing_id is not None:
                if not external_listing_id.strip():
                    raise ValidationError(
                        "external_listing_id cannot be empty",
                        details={'external_listing_id': external_listing_id}
                    )
                if mapping.external_listing_id != external_listing_id.strip():
                    changes['external_listing_id'] = {
                        'old': mapping.external_listing_id,
                        'new': external_listing_id.strip()
                    }
                    mapping.external_listing_id = external_listing_id.strip()
                    update_fields.append('external_listing_id')

            # Update external_resource_ids if provided
            if external_resource_ids is not None:
                if not isinstance(external_resource_ids, list):
                    raise ValidationError(
                        "external_resource_ids must be a list",
                        details={'external_resource_ids_type': type(external_resource_ids).__name__}
                    )
                if mapping.external_resource_ids != external_resource_ids:
                    changes['external_resource_ids'] = {
                        'old': mapping.external_resource_ids,
                        'new': external_resource_ids
                    }
                    mapping.external_resource_ids = external_resource_ids
                    update_fields.append('external_resource_ids')

            # Update sync_metadata if provided (merge with existing)
            if sync_metadata is not None:
                if not isinstance(sync_metadata, dict):
                    raise ValidationError(
                        "sync_metadata must be a dictionary",
                        details={'sync_metadata_type': type(sync_metadata).__name__}
                    )
                old_metadata = mapping.sync_metadata.copy()
                mapping.sync_metadata.update(sync_metadata)
                if mapping.sync_metadata != old_metadata:
                    changes['sync_metadata'] = {
                        'old': old_metadata,
                        'new': mapping.sync_metadata
                    }
                    update_fields.append('sync_metadata')

            # If no changes, return early
            if not changes:
                return mapping

            # Get tenant and user
            tenant_obj = self.get_resource_or_raise(Tenant, effective_tenant_id)
            user_obj = self.get_resource_or_raise(User, effective_user_id)

            # Save changes
            update_fields.append('updated_at')
            mapping.save(update_fields=update_fields)

            # Add span attributes
            if span:
                add_span_attributes({
                    "mapping.id": str(mapping.id),
                    "mapping.connection_id": str(mapping.connection.id),
                    "mapping.changes": list(changes.keys()),
                })
                set_span_status(StatusCode.OK)

            # Audit log
            try:
                from hub.apps.audit.utils import create_audit_event
                create_audit_event(
                    resource_type="MARKETPLACE_MAPPING",
                    action="MAPPING_UPDATED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(mapping.id),
                    result="SUCCESS",
                    details={
                        "mapping_id": str(mapping.id),
                        "connection_id": str(mapping.connection.id),
                        "hub_asset_id": str(mapping.hub_asset.id),
                        "changes": changes,
                        "request_id": self.request_id,
                    },
                    request=request,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit log for mapping update {mapping.id}: {e}",
                    exc_info=True,
                )

            # Publish event
            try:
                self.publish_mapping_updated(
                    mapping_id=str(mapping.id),
                    connection_id=str(mapping.connection.id),
                    changes=changes,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    request_id=self.request_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to publish mapping.updated event for {mapping.id}: {e}",
                    exc_info=True,
                )

            logger.info(
                f"Updated marketplace mapping {mapping.id} with changes: {list(changes.keys())}"
            )

            return mapping

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
                f"Unexpected error updating mapping: {e}",
                exc_info=True,
                extra={
                    "mapping_id": mapping_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                }
            )
            raise ServiceError(f"Failed to update mapping: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass

    @transaction.atomic
    def delete_mapping(
        self,
        mapping_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        reason: Optional[str] = None,
        request: Optional[Any] = None,
    ) -> None:
        """
        Delete a marketplace mapping.

        Args:
            mapping_id: The ID of the mapping to delete.
            tenant_id: Optional tenant ID (uses service tenant_id if not provided).
            user_id: Optional user ID (uses service user_id if not provided).
            reason: Optional reason for deletion.
            request: Optional request object for audit logging and tracing context.

        Raises:
            NotFoundError: If the mapping is not found.
            ServiceError: For other unexpected errors.
        """
        from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
        from opentelemetry.trace import StatusCode
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model

        User = get_user_model()
        span_name = "MarketplaceIntegrationService.delete_mapping"
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(span_name, kind=1)
            span = span_context.__enter__() if span_context else None

            # Get mapping
            try:
                mapping = self.get_resource_or_raise(
                    MarketplaceMapping,
                    mapping_id,
                    tenant_id=effective_tenant_id
                )
            except DjangoValidationError as e:
                raise NotFoundError(
                    f"Mapping {mapping_id} not found",
                    details={'mapping_id': mapping_id, 'error': str(e)}
                ) from e

            # Store values for event publishing
            connection_id = str(mapping.connection.id)
            hub_asset_id = str(mapping.hub_asset.id)
            external_listing_id = mapping.external_listing_id

            # Get tenant and user
            tenant_obj = self.get_resource_or_raise(Tenant, effective_tenant_id)
            user_obj = self.get_resource_or_raise(User, effective_user_id)

            # Delete mapping
            mapping.delete()

            # Add span attributes
            if span:
                add_span_attributes({
                    "mapping.id": mapping_id,
                    "mapping.connection_id": connection_id,
                    "mapping.hub_asset_id": hub_asset_id,
                })
                set_span_status(StatusCode.OK)

            # Audit log
            try:
                from hub.apps.audit.utils import create_audit_event
                create_audit_event(
                    resource_type="MARKETPLACE_MAPPING",
                    action="MAPPING_DELETED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=mapping_id,
                    result="SUCCESS",
                    details={
                        "mapping_id": mapping_id,
                        "connection_id": connection_id,
                        "hub_asset_id": hub_asset_id,
                        "external_listing_id": external_listing_id,
                        "reason": reason,
                        "request_id": self.request_id,
                    },
                    request=request,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit log for mapping deletion {mapping_id}: {e}",
                    exc_info=True,
                )

            # Publish event
            try:
                self.publish_mapping_deleted(
                    mapping_id=mapping_id,
                    connection_id=connection_id,
                    hub_asset_id=hub_asset_id,
                    external_listing_id=external_listing_id,
                    reason=reason,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    request_id=self.request_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to publish mapping.deleted event for {mapping_id}: {e}",
                    exc_info=True,
                )

            logger.info(
                f"Deleted marketplace mapping {mapping_id} for tenant {effective_tenant_id}"
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
                f"Unexpected error deleting mapping: {e}",
                exc_info=True,
                extra={
                    "mapping_id": mapping_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                }
            )
            raise ServiceError(f"Failed to delete mapping: {e}") from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass

