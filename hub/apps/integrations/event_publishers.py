"""
Marketplace Event Publisher

Event publisher for marketplace integration events.
Extends EventPublisher to provide typed methods for marketplace-specific events.
"""

from typing import Any

from django.utils import timezone

from hub.apps.core.events.publisher import EventPublisher


class MarketplaceEventPublisher(EventPublisher):
    """
    Event publisher for marketplace integration events.

    Extends EventPublisher to provide typed methods for publishing
    marketplace-specific events including:
    - Connection lifecycle events (created, updated, deleted)
    - Sync operation events (started, completed, failed)
    - Mapping lifecycle events (created, updated, deleted)

    Usage:
        publisher = MarketplaceEventPublisher(
            tenant_id="tenant-uuid",
            user_id="user-uuid"
        )
        event_id = publisher.publish_connection_created(
            connection_id="conn-uuid",
            marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
            name="My Connection"
        )
    """

    def __init__(self, tenant_id: str | None = None, user_id: str | None = None):
        """
        Initialize MarketplaceEventPublisher.

        Args:
            tenant_id: Optional tenant ID (can be overridden per event)
            user_id: Optional user ID (can be overridden per event)
        """
        super().__init__(
            service_name="marketplace_integration_service", tenant_id=tenant_id, user_id=user_id
        )

    def publish_connection_created(
        self,
        connection_id: str,
        marketplace_type: str,
        name: str,
        **kwargs,
    ) -> str:
        """
        Publish marketplace.connection.created event.

        Args:
            connection_id: Unique identifier for the connection (required, non-empty string)
            marketplace_type: Type of marketplace (e.g., SNOWFLAKE_DATA_MARKETPLACE)
            name: Connection name
            **kwargs: Additional event parameters (tenant_id, user_id, correlation_id, etc.)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)

        Raises:
            ValueError: If connection_id is None or not a non-empty string.
        """
        if connection_id is None or not isinstance(connection_id, str) or not connection_id.strip():
            raise ValueError(
                "connection_id is required and must be a non-empty string "
                "for marketplace.connection.created"
            )
        if marketplace_type is None:
            raise ValueError("marketplace_type is required for marketplace.connection.created")
        # name may be empty string per schema; allow None -> treat as ""
        safe_name = name if name is not None else ""
        return self.publish(
            event_type="marketplace.connection.created",
            data={
                "connection_id": connection_id.strip(),
                "marketplace_type": marketplace_type,
                "name": safe_name,
                "created_at": timezone.now().isoformat(),
            },
            tags=["marketplace", "connection", "created"],
            **kwargs,
        )

    def publish_connection_updated(
        self,
        connection_id: str,
        changes: dict[str, Any],
        **kwargs,
    ) -> str:
        """
        Publish marketplace.connection.updated event.

        Args:
            connection_id: Unique identifier for the connection
            changes: Dictionary describing what changed (e.g., {"name": {"old": "...", "new": "..."}})
            **kwargs: Additional event parameters (tenant_id, user_id, correlation_id, etc.)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)
        """
        return self.publish(
            event_type="marketplace.connection.updated",
            data={
                "connection_id": connection_id,
                "changes": changes,
                "updated_at": timezone.now().isoformat(),
            },
            tags=["marketplace", "connection", "updated"],
            **kwargs,
        )

    def publish_connection_deleted(
        self,
        connection_id: str,
        marketplace_type: str,
        name: str,
        reason: str | None = None,
        **kwargs,
    ) -> str:
        """
        Publish marketplace.connection.deleted event.

        Args:
            connection_id: Unique identifier for the connection
            marketplace_type: Type of marketplace
            name: Connection name
            reason: Optional reason for deletion
            **kwargs: Additional event parameters (tenant_id, user_id, correlation_id, etc.)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)
        """
        return self.publish(
            event_type="marketplace.connection.deleted",
            data={
                "connection_id": connection_id,
                "marketplace_type": marketplace_type,
                "name": name,
                "reason": reason,
                "deleted_at": timezone.now().isoformat(),
            },
            tags=["marketplace", "connection", "deleted"],
            **kwargs,
        )

    def publish_sync_started(
        self,
        sync_job_id: str,
        connection_id: str,
        direction: str,
        **kwargs,
    ) -> str:
        """
        Publish marketplace.sync.started event.

        Args:
            sync_job_id: Unique identifier for the sync job
            connection_id: Unique identifier for the connection
            direction: Sync direction (PUSH, PULL, or BIDIRECTIONAL)
            **kwargs: Additional event parameters (tenant_id, user_id, correlation_id, etc.)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)
        """
        return self.publish(
            event_type="marketplace.sync.started",
            data={
                "sync_job_id": sync_job_id,
                "connection_id": connection_id,
                "direction": direction,
                "started_at": timezone.now().isoformat(),
            },
            tags=["marketplace", "sync", "started"],
            **kwargs,
        )

    def publish_sync_completed(
        self,
        sync_job_id: str,
        connection_id: str,
        direction: str,
        status: str,
        items_synced: int,
        items_failed: int,
        **kwargs,
    ) -> str:
        """
        Publish marketplace.sync.completed event.

        Args:
            sync_job_id: Unique identifier for the sync job
            connection_id: Unique identifier for the connection
            direction: Sync direction (PUSH, PULL, or BIDIRECTIONAL)
            status: Sync status (COMPLETED, PARTIAL, etc.)
            items_synced: Number of items successfully synced
            items_failed: Number of items that failed to sync
            **kwargs: Additional event parameters (tenant_id, user_id, correlation_id, etc.)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)
        """
        return self.publish(
            event_type="marketplace.sync.completed",
            data={
                "sync_job_id": sync_job_id,
                "connection_id": connection_id,
                "direction": direction,
                "status": status,
                "items_synced": items_synced,
                "items_failed": items_failed,
                "completed_at": timezone.now().isoformat(),
            },
            tags=["marketplace", "sync", "completed"],
            **kwargs,
        )

    def publish_sync_failed(
        self,
        sync_job_id: str,
        connection_id: str,
        direction: str,
        error_message: str,
        error_details: dict[str, Any] | None = None,
        **kwargs,
    ) -> str:
        """
        Publish marketplace.sync.failed event.

        Args:
            sync_job_id: Unique identifier for the sync job
            connection_id: Unique identifier for the connection
            direction: Sync direction (PUSH, PULL, or BIDIRECTIONAL)
            error_message: Human-readable error message
            error_details: Optional dictionary with additional error details
            **kwargs: Additional event parameters (tenant_id, user_id, correlation_id, etc.)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)
        """
        return self.publish(
            event_type="marketplace.sync.failed",
            data={
                "sync_job_id": sync_job_id,
                "connection_id": connection_id,
                "direction": direction,
                "error_message": error_message,
                "error_details": error_details or {},
                "failed_at": timezone.now().isoformat(),
            },
            tags=["marketplace", "sync", "failed"],
            **kwargs,
        )

    def publish_mapping_created(
        self,
        mapping_id: str,
        connection_id: str,
        hub_asset_id: str,
        external_listing_id: str,
        **kwargs,
    ) -> str:
        """
        Publish marketplace.mapping.created event.

        Args:
            mapping_id: Unique identifier for the mapping
            connection_id: Unique identifier for the connection
            hub_asset_id: Unique identifier for the Hub asset
            external_listing_id: External marketplace listing identifier
            **kwargs: Additional event parameters (tenant_id, user_id, correlation_id, etc.)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)
        """
        return self.publish(
            event_type="marketplace.mapping.created",
            data={
                "mapping_id": mapping_id,
                "connection_id": connection_id,
                "hub_asset_id": hub_asset_id,
                "external_listing_id": external_listing_id,
                "created_at": timezone.now().isoformat(),
            },
            tags=["marketplace", "mapping", "created"],
            **kwargs,
        )

    def publish_mapping_updated(
        self,
        mapping_id: str,
        connection_id: str,
        changes: dict[str, Any],
        **kwargs,
    ) -> str:
        """
        Publish marketplace.mapping.updated event.

        Args:
            mapping_id: Unique identifier for the mapping
            connection_id: Unique identifier for the connection
            changes: Dictionary describing what changed
            **kwargs: Additional event parameters (tenant_id, user_id, correlation_id, etc.)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)
        """
        return self.publish(
            event_type="marketplace.mapping.updated",
            data={
                "mapping_id": mapping_id,
                "connection_id": connection_id,
                "changes": changes,
                "updated_at": timezone.now().isoformat(),
            },
            tags=["marketplace", "mapping", "updated"],
            **kwargs,
        )

    def publish_mapping_deleted(
        self,
        mapping_id: str,
        connection_id: str,
        hub_asset_id: str,
        external_listing_id: str,
        reason: str | None = None,
        **kwargs,
    ) -> str:
        """
        Publish marketplace.mapping.deleted event.

        Args:
            mapping_id: Unique identifier for the mapping
            connection_id: Unique identifier for the connection
            hub_asset_id: Unique identifier for the Hub asset
            external_listing_id: External marketplace listing identifier
            reason: Optional reason for deletion
            **kwargs: Additional event parameters (tenant_id, user_id, correlation_id, etc.)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)
        """
        return self.publish(
            event_type="marketplace.mapping.deleted",
            data={
                "mapping_id": mapping_id,
                "connection_id": connection_id,
                "hub_asset_id": hub_asset_id,
                "external_listing_id": external_listing_id,
                "reason": reason,
                "deleted_at": timezone.now().isoformat(),
            },
            tags=["marketplace", "mapping", "deleted"],
            **kwargs,
        )
