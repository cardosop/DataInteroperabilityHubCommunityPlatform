"""Connection management methods for MarketplaceIntegrationService."""
import structlog
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from hub.apps.core.services.base import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from hub.apps.integrations.base import (
    MarketplaceType,
)
from hub.apps.integrations.business_rules import MarketplaceIntegrationBusinessRules
from hub.apps.integrations.event_publishers import MarketplaceEventPublisher
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.logging_utils import get_correlation_context
from hub.apps.integrations.models import (
    MarketplaceConnection,
)
from hub.apps.integrations.utils import (
    MarketplaceAuthenticationError,
    MarketplaceConnectionError,
    MarketplaceError,
    validate_marketplace_config,
)

logger = structlog.get_logger(__name__)


class ConnectionServiceMixin:
    """Mixin providing connection CRUD and test operations."""

    @transaction.atomic
    def create_connection(
        self,
        tenant_id: str,
        user_id: str,
        marketplace_type: str,
        name: str,
        config: Dict[str, Any],
        is_active: bool = True,
        request: Optional[Any] = None,
    ) -> MarketplaceConnection:
        """
        Create a new marketplace connection.

        Args:
            tenant_id: Tenant ID
            user_id: User ID creating the connection
            marketplace_type: Marketplace type (from MarketplaceType enum)
            name: Connection name (unique per tenant)
            config: Connection configuration dictionary (will be encrypted)
            is_active: Whether connection is active (default: True)
            request: Optional HTTP request for audit logging

        Returns:
            Created MarketplaceConnection instance

        Raises:
            ValidationError: If validation fails
            ConflictError: If connection name already exists for tenant
            NotFoundError: If tenant not found
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
        span = None

        # Plan limit enforcement
        from hub.apps.tenants.services import PlanLimitService
        plan_limit_service = PlanLimitService(tenant_id=tenant_id)
        plan_limit_service.check_limit(
            tenant_id=tenant_id,
            limit_key="max_marketplace_connections",
            delta=1,
        )

        try:
            # Create span for distributed tracing
            span_context = create_span(
                "marketplace_integration.create_connection",
                attributes={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "marketplace_type": marketplace_type,
                    "connection_name": name,
                },
            )
            span = span_context.__enter__() if span_context else None

            # Validate marketplace type
            valid_types = [mt.value for mt in MarketplaceType]
            if marketplace_type not in valid_types:
                raise ValidationError(
                    f"Invalid marketplace type: {marketplace_type}",
                    details={"valid_types": valid_types},
                )

            # Get tenant and user
            try:
                tenant_obj = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                raise NotFoundError(f"Tenant with id {tenant_id} not found")

            try:
                user_obj = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise NotFoundError(f"User with id {user_id} not found")

            # Validate via MarketplaceIntegrationBusinessRules before mutation
            payload_connection = MarketplaceConnection(
                tenant=tenant_obj,
                marketplace_type=marketplace_type,
                name=name,
                config=config,
                is_active=is_active,
            )
            rules = MarketplaceIntegrationBusinessRules(tenant_id=tenant_id, user_id=user_id)
            result = rules.validate(
                connection=payload_connection,
                validation_type="connection",
            )
            if not result.is_valid:
                raise ValidationError(
                    "; ".join(result.errors),
                    code="BUSINESS_RULES_VALIDATION",
                    details=result.details,
                )

            # Validate config (basic validation - encryption happens in model save)
            if not isinstance(config, dict):
                raise ValidationError(
                    "Configuration must be a dictionary",
                    details={"config_type": type(config).__name__},
                )

            # Validate marketplace-specific config if needed
            try:
                validate_marketplace_config(
                    config, marketplace_type=MarketplaceType(marketplace_type)
                )
            except MarketplaceError as e:
                raise ValidationError(
                    f"Invalid marketplace configuration: {e.message}", details=e.details
                ) from e

            # Phase 90.6: SSRF validation on URL-like config values
            # Gated on INTEGRATION_SSRF_ENABLED (same pattern as WEBHOOK_SSRF_ENABLED)
            from django.conf import settings as _django_settings
            if getattr(_django_settings, "INTEGRATION_SSRF_ENABLED", True):
                from hub.apps.webhooks.ssrf_guard import validate_webhook_url, SSRFViolationError
                _url_keys = {"url", "endpoint", "api_url", "base_url", "host_url", "callback_url"}
                for key, value in (config or {}).items():
                    if key.lower() in _url_keys and isinstance(value, str) and value.startswith(("http://", "https://")):
                        try:
                            validate_webhook_url(value, raise_as_validation_error=False)
                        except SSRFViolationError as ssrf_exc:
                            raise ValidationError(
                                f"Connection config '{key}' targets a private/reserved address: {ssrf_exc}",
                                code="SSRF_VIOLATION",
                            )

            # Create connection (nested atomic block acts as savepoint)
            try:
                with transaction.atomic():
                    connection = MarketplaceConnection.objects.create(
                        tenant=tenant_obj,
                        marketplace_type=marketplace_type,
                        name=name,
                        config=config,  # Will be encrypted in model save()
                        is_active=is_active,
                    )
            except IntegrityError:
                raise ConflictError(
                    f"Connection with name '{name}' already exists for tenant {tenant_id}",
                    details={"name": name, "tenant_id": tenant_id},
                )
            except DjangoValidationError as e:
                if "already exists" in str(e):
                    raise ConflictError(
                        f"Connection with name '{name}' already exists for tenant {tenant_id}",
                        details={"name": name, "tenant_id": tenant_id},
                    )
                raise

            # Record metrics
            try:
                from hub.apps.observability.otel_metrics import (
                    marketplace_connection_status,
                    marketplace_connections_total,
                )

                status = "active" if is_active else "inactive"
                marketplace_connections_total.labels(
                    marketplace_type=marketplace_type,
                    tenant_id=tenant_id,
                    status=status,
                ).inc()
                marketplace_connection_status.labels(
                    marketplace_type=marketplace_type,
                    tenant_id=tenant_id,
                    connection_id=str(connection.id),
                ).set(1 if is_active else 0)
            except Exception as e:
                # Log but don't fail connection creation if metrics fail
                correlation_context = get_correlation_context()
                logger.warning(
                    "metrics_recording_failed",
                    connection_id=str(connection.id),
                    error=str(e),
                    error_type=type(e).__name__,
                    **correlation_context,
                    exc_info=True,
                )

            # Add span attributes
            if span:
                add_span_attributes(
                    {
                        "connection.id": str(connection.id),
                        "connection.is_active": is_active,
                    }
                )
                set_span_status(StatusCode.OK)

            # Create audit log
            try:
                from hub.apps.audit.utils import create_audit_event

                create_audit_event(
                    resource_type="MARKETPLACE_CONNECTION",
                    action="CONNECTION_CREATED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(connection.id),
                    result="SUCCESS",
                    details={
                        "connection_id": str(connection.id),
                        "marketplace_type": marketplace_type,
                        "name": name,
                        "is_active": is_active,
                        "request_id": self.request_id,
                    },
                    request=request,
                )
            except Exception as e:
                # Log but don't fail connection creation if audit logging fails
                correlation_context = get_correlation_context()
                logger.warning(
                    "audit_logging_failed",
                    connection_id=str(connection.id),
                    error=str(e),
                    error_type=type(e).__name__,
                    **correlation_context,
                    exc_info=True,
                )

            # Publish events
            try:
                # Publish integration.connection.created event (existing)
                self.publish_connection_created(
                    connection_id=str(connection.id),
                    marketplace_type=marketplace_type,
                    name=name,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    request_id=self.request_id,
                )
                # Publish marketplace.connection.created event (new)
                MarketplaceEventPublisher.publish_connection_created(
                    self,
                    connection_id=str(connection.id),
                    marketplace_type=marketplace_type,
                    name=name,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    correlation_id=self.request_id,
                )
            except Exception as e:
                # Log but don't fail connection creation if event publishing fails
                correlation_context = get_correlation_context()
                logger.warning(
                    "event_publishing_failed",
                    connection_id=str(connection.id),
                    event_type="connection.created",
                    error=str(e),
                    error_type=type(e).__name__,
                    **correlation_context,
                    exc_info=True,
                )

            # Log connection creation with structured fields
            correlation_context = get_correlation_context()
            logger.info(
                "marketplace_connection_created",
                connection_id=str(connection.id),
                marketplace_type=marketplace_type,
                connection_name=name,
                tenant_id=tenant_id,
                user_id=user_id,
                is_active=is_active,
                **correlation_context,
            )

            return connection

        except (ValidationError, NotFoundError, ConflictError) as e:
            # Re-raise service errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            # Log unexpected errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            correlation_context = get_correlation_context()
            logger.error(
                "marketplace_connection_creation_failed",
                tenant_id=tenant_id,
                user_id=user_id,
                marketplace_type=marketplace_type,
                connection_name=name,
                error=str(e),
                error_type=type(e).__name__,
                **correlation_context,
                exc_info=True,
            )
            raise ValidationError(
                f"Failed to create marketplace connection: {str(e)}", details={"error": str(e)}
            ) from e
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
    def update_connection(
        self,
        connection_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
        request: Optional[Any] = None,
    ) -> MarketplaceConnection:
        """
        Update an existing marketplace connection.

        Args:
            connection_id: Connection ID to update
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            user_id: Optional user ID (uses service user_id if not provided)
            name: Optional new connection name
            config: Optional new configuration dictionary
            is_active: Optional new active status
            request: Optional HTTP request for audit logging

        Returns:
            Updated MarketplaceConnection instance

        Raises:
            NotFoundError: If connection not found
            ValidationError: If validation fails
            ConflictError: If new name conflicts with existing connection
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
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(
                "marketplace_integration.update_connection",
                attributes={
                    "connection_id": connection_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )
            span = span_context.__enter__() if span_context else None

            # Get connection
            connection = self.get_resource_or_raise(
                MarketplaceConnection, connection_id, tenant_id=effective_tenant_id
            )

            # Track changes for audit log
            changes = {}
            original_values = {}

            # Update name if provided
            if name is not None:
                if name != connection.name:
                    # Check for duplicate name
                    if (
                        MarketplaceConnection.objects.filter(
                            tenant_id=effective_tenant_id, name=name
                        )
                        .exclude(id=connection_id)
                        .exists()
                    ):
                        raise ConflictError(
                            f"Connection with name '{name}' already exists for tenant {effective_tenant_id}",
                            details={"name": name, "tenant_id": effective_tenant_id},
                        )
                    original_values["name"] = connection.name
                    connection.name = name
                    changes["name"] = name

            # Update config if provided
            if config is not None:
                if not isinstance(config, dict):
                    raise ValidationError(
                        "Configuration must be a dictionary",
                        details={"config_type": type(config).__name__},
                    )

                # Validate marketplace-specific config
                try:
                    validate_marketplace_config(
                        config, marketplace_type=MarketplaceType(connection.marketplace_type)
                    )
                except MarketplaceError as e:
                    raise ValidationError(
                        f"Invalid marketplace configuration: {e.message}", details=e.details
                    ) from e

                # Store original config (encrypted, so we can't show actual values)
                original_values["config"] = "[ENCRYPTED]"
                connection.set_config(config)
                changes["config"] = "[UPDATED]"

            # Update is_active if provided
            if is_active is not None:
                if is_active != connection.is_active:
                    original_values["is_active"] = connection.is_active
                    connection.is_active = is_active
                    changes["is_active"] = is_active

            # Save if there are changes
            if changes:
                connection.save()

                # Record metrics for status changes
                if "is_active" in changes:
                    try:
                        from hub.apps.observability.otel_metrics import (
                            marketplace_connection_status,
                        )

                        marketplace_connection_status.labels(
                            marketplace_type=connection.marketplace_type,
                            tenant_id=effective_tenant_id,
                            connection_id=str(connection.id),
                        ).set(1 if connection.is_active else 0)
                    except Exception as e:
                        # Log but don't fail update if metrics fail
                        correlation_context = get_correlation_context()
                        logger.warning(
                            "metrics_recording_failed",
                            connection_id=str(connection.id),
                            metric_type="connection_status",
                            error=str(e),
                            error_type=type(e).__name__,
                            **correlation_context,
                            exc_info=True,
                        )

                # Add span attributes
                if span:
                    add_span_attributes(
                        {
                            "connection.changes": list(changes.keys()),
                        }
                    )
                    set_span_status(StatusCode.OK)

                # Create audit log
                try:
                    from hub.apps.audit.utils import create_audit_event

                    tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                    user_obj = User.objects.get(id=effective_user_id) if effective_user_id else None

                    create_audit_event(
                        resource_type="MARKETPLACE_CONNECTION",
                        action="CONNECTION_UPDATED",
                        actor_user=user_obj,
                        tenant=tenant_obj,
                        resource_id=str(connection.id),
                        result="SUCCESS",
                        details={
                            "connection_id": str(connection.id),
                            "marketplace_type": connection.marketplace_type,
                            "changes": changes,
                            "original_values": original_values,
                            "request_id": self.request_id,
                        },
                        request=request,
                    )
                except Exception as e:
                    # Log but don't fail update if audit logging fails
                    correlation_context = get_correlation_context()
                    logger.warning(
                        "audit_logging_failed",
                        connection_id=str(connection.id),
                        action="CONNECTION_UPDATED",
                        error=str(e),
                        error_type=type(e).__name__,
                        **correlation_context,
                        exc_info=True,
                    )

                # Publish events
                try:
                    # Publish integration.connection.updated event (existing)
                    self.publish_connection_updated(
                        connection_id=str(connection.id),
                        changes=changes,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                        request_id=self.request_id,
                    )
                    # Publish marketplace.connection.updated event (new)
                    MarketplaceEventPublisher.publish_connection_updated(
                        self,
                        connection_id=str(connection.id),
                        changes=changes,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                        correlation_id=self.request_id,
                    )
                except Exception as e:
                    # Log but don't fail update if event publishing fails
                    logger.warning(
                        f"Failed to publish connection.updated event for {connection.id}: {e}",
                        exc_info=True,
                    )

                logger.info(
                    f"Updated marketplace connection {connection.id} with changes: {list(changes.keys())}"
                )
            else:
                correlation_context = get_correlation_context()
                logger.debug(
                    "marketplace_connection_no_changes",
                    connection_id=str(connection.id),
                    tenant_id=effective_tenant_id,
                    **correlation_context,
                )

            return connection

        except (ValidationError, NotFoundError, ConflictError) as e:
            # Re-raise service errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            # Log unexpected errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            correlation_context = get_correlation_context()
            logger.error(
                "marketplace_connection_update_failed",
                connection_id=connection_id,
                tenant_id=effective_tenant_id,
                user_id=effective_user_id,
                error=str(e),
                error_type=type(e).__name__,
                **correlation_context,
                exc_info=True,
            )
            raise ValidationError(
                f"Failed to update marketplace connection: {str(e)}", details={"error": str(e)}
            ) from e
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
    def delete_connection(
        self,
        connection_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        reason: Optional[str] = None,
        request: Optional[Any] = None,
    ) -> None:
        """
        Delete a marketplace connection.

        Args:
            connection_id: Connection ID to delete
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            user_id: Optional user ID (uses service user_id if not provided)
            reason: Optional reason for deletion
            request: Optional HTTP request for audit logging

        Raises:
            NotFoundError: If connection not found
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
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(
                "marketplace_integration.delete_connection",
                attributes={
                    "connection_id": connection_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )
            span = span_context.__enter__() if span_context else None

            # Get connection
            connection = self.get_resource_or_raise(
                MarketplaceConnection, connection_id, tenant_id=effective_tenant_id
            )

            # Store connection details before deletion
            connection_id_str = str(connection.id)
            marketplace_type = connection.marketplace_type
            name = connection.name
            was_active = connection.is_active

            # Record metrics before deletion
            try:
                from hub.apps.observability.otel_metrics import (
                    marketplace_connection_status,
                )

                marketplace_connection_status.labels(
                    marketplace_type=marketplace_type,
                    tenant_id=effective_tenant_id,
                    connection_id=connection_id_str,
                ).set(
                    0
                )  # Set to 0 (inactive) before deletion
            except Exception as e:
                # Log but don't fail deletion if metrics fail
                logger.warning(
                    f"Failed to record deletion metrics for connection {connection_id_str}: {e}",
                    exc_info=True,
                )

            # Delete connection
            connection.delete()

            # Add span attributes
            if span:
                add_span_attributes(
                    {
                        "connection.marketplace_type": marketplace_type,
                    }
                )
                set_span_status(StatusCode.OK)

            # Create audit log
            try:
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                user_obj = User.objects.get(id=effective_user_id) if effective_user_id else None

                from hub.apps.audit.utils import create_audit_event

                create_audit_event(
                    resource_type="MARKETPLACE_CONNECTION",
                    action="CONNECTION_DELETED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=connection_id_str,
                    result="SUCCESS",
                    details={
                        "connection_id": connection_id_str,
                        "marketplace_type": marketplace_type,
                        "name": name,
                        "reason": reason,
                        "request_id": self.request_id,
                    },
                    request=request,
                )
            except Exception as e:
                # Log but don't fail deletion if audit logging fails
                logger.warning(
                    f"Failed to create audit log for connection deletion {connection_id_str}: {e}",
                    exc_info=True,
                )

            # Publish events
            try:
                # Publish integration.connection.deleted event (existing)
                self.publish_connection_deleted(
                    connection_id=connection_id_str,
                    marketplace_type=marketplace_type,
                    name=name,  # Use stored name
                    reason=reason,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    request_id=self.request_id,
                )
                # Publish marketplace.connection.deleted event (new)
                MarketplaceEventPublisher.publish_connection_deleted(
                    self,
                    connection_id=connection_id_str,
                    marketplace_type=marketplace_type,
                    name=name,
                    reason=reason,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    correlation_id=self.request_id,
                )
            except Exception as e:
                # Log but don't fail deletion if event publishing fails
                logger.warning(
                    f"Failed to publish connection.deleted event for {connection_id_str}: {e}",
                    exc_info=True,
                )

            logger.info(
                f"Deleted marketplace connection {connection_id_str} ({name}) for tenant {effective_tenant_id}"
            )

        except NotFoundError as e:
            # Re-raise service errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            # Log unexpected errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            logger.error(
                f"Unexpected error deleting marketplace connection: {e}",
                exc_info=True,
                extra={
                    "connection_id": connection_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )
            raise
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )

    def list_connections(
        self,
        tenant_id: Optional[str] = None,
        marketplace_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[MarketplaceConnection]:
        """
        List marketplace connections.

        Args:
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            marketplace_type: Optional marketplace type filter
            is_active: Optional active status filter

        Returns:
            List of MarketplaceConnection instances

        Raises:
            NotFoundError: If tenant not found
        """
        from opentelemetry.trace import StatusCode

        from hub.apps.observability.span_instrumentation import (
            add_span_attributes,
            create_span,
            set_span_status,
        )
        from hub.apps.tenants.models import Tenant

        effective_tenant_id = tenant_id or self.tenant_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(
                "marketplace_integration.list_connections",
                attributes={
                    "tenant_id": effective_tenant_id,
                    "marketplace_type": marketplace_type or "all",
                    "is_active": str(is_active) if is_active is not None else "all",
                },
            )
            span = span_context.__enter__() if span_context else None

            # Validate tenant exists
            if effective_tenant_id:
                try:
                    Tenant.objects.get(id=effective_tenant_id)
                except Tenant.DoesNotExist:
                    raise NotFoundError(f"Tenant with id {effective_tenant_id} not found")

            # Build query
            query = MarketplaceConnection.objects.all()

            if effective_tenant_id:
                query = query.filter(tenant_id=effective_tenant_id)

            if marketplace_type:
                query = query.filter(marketplace_type=marketplace_type)

            if is_active is not None:
                query = query.filter(is_active=is_active)

            connections = list(query.order_by("-created_at"))

            # Add span attributes
            if span:
                add_span_attributes(
                    {
                        "connection.count": len(connections),
                    }
                )
                set_span_status(StatusCode.OK)

            logger.debug(
                f"Listed {len(connections)} marketplace connections for tenant {effective_tenant_id}"
            )

            return connections

        except NotFoundError:
            # Re-raise service errors
            if span:
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            # Log unexpected errors
            if span:
                set_span_status(StatusCode.ERROR)
            logger.error(
                f"Unexpected error listing marketplace connections: {e}",
                exc_info=True,
                extra={
                    "tenant_id": effective_tenant_id,
                    "marketplace_type": marketplace_type,
                    "is_active": is_active,
                },
            )
            raise
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )

    def get_connection(
        self,
        connection_id: str,
        tenant_id: Optional[str] = None,
    ) -> MarketplaceConnection:
        """
        Get a marketplace connection by ID.

        Args:
            connection_id: Connection ID
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)

        Returns:
            MarketplaceConnection instance

        Raises:
            NotFoundError: If connection not found
        """
        from opentelemetry.trace import StatusCode

        from hub.apps.observability.span_instrumentation import (
            add_span_attributes,
            create_span,
            record_span_exception,
            set_span_status,
        )

        effective_tenant_id = tenant_id or self.tenant_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(
                "marketplace_integration.get_connection",
                attributes={
                    "connection_id": connection_id,
                    "tenant_id": effective_tenant_id,
                },
            )
            span = span_context.__enter__() if span_context else None

            # Get connection
            connection = self.get_resource_or_raise(
                MarketplaceConnection, connection_id, tenant_id=effective_tenant_id
            )

            # Add span attributes
            if span:
                add_span_attributes(
                    {
                        "connection.marketplace_type": connection.marketplace_type,
                        "connection.is_active": connection.is_active,
                    }
                )
                set_span_status(StatusCode.OK)

            return connection

        except NotFoundError as e:
            # Re-raise service errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            # Log unexpected errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            logger.error(
                f"Unexpected error getting marketplace connection: {e}",
                exc_info=True,
                extra={
                    "connection_id": connection_id,
                    "tenant_id": effective_tenant_id,
                },
            )
            raise
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )

    def test_connection(
        self,
        connection_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Test a marketplace connection.

        Creates a connector instance and tests the connection to verify
        that credentials are valid and the marketplace is accessible.

        Args:
            connection_id: Connection ID to test
            tenant_id: Optional tenant ID (uses service tenant_id if not provided)
            user_id: Optional user ID (uses service user_id if not provided)
            request: Optional HTTP request for audit logging

        Returns:
            Dictionary with test results:
            - success: bool
            - message: str
            - error: Optional[str]
            - tested_at: str (ISO format)

        Raises:
            NotFoundError: If connection not found
            ValidationError: If connection configuration is invalid
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
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id
        span = None
        span_context = None

        try:
            # Create span for distributed tracing
            span_context = create_span(
                "marketplace_integration.test_connection",
                attributes={
                    "connection_id": connection_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )
            span = span_context.__enter__() if span_context else None

            # Get connection
            connection = self.get_resource_or_raise(
                MarketplaceConnection, connection_id, tenant_id=effective_tenant_id
            )

            # Get decrypted config
            try:
                config = connection.get_config()
            except Exception as e:
                raise ValidationError(
                    f"Failed to decrypt connection configuration: {str(e)}",
                    details={"error": str(e)},
                ) from e

            # Create connector instance
            try:
                factory = MarketplaceConnectorFactory()
                connector = factory.create_connector(
                    marketplace_type=MarketplaceType(connection.marketplace_type), config=config
                )
            except Exception as e:
                raise ValidationError(
                    f"Failed to create connector: {str(e)}",
                    details={"error": str(e), "marketplace_type": connection.marketplace_type},
                ) from e

            # Test connection
            tested_at = timezone.now()
            success = False
            error_message = None
            error_type = None

            try:
                success = connector.test_connection()
                if not success:
                    error_message = "Connection test failed (connector returned False)"
                    error_type = "CONNECTION_FAILED"
            except MarketplaceConnectionError as e:
                error_message = f"Connection error: {e.message}"
                error_type = "CONNECTION_ERROR"
            except MarketplaceAuthenticationError as e:
                error_message = f"Authentication error: {e.message}"
                error_type = "AUTHENTICATION_ERROR"
            except Exception as e:
                error_message = f"Unexpected error: {str(e)}"
                error_type = "UNEXPECTED_ERROR"

            # Record connection test metrics
            try:
                from hub.apps.observability.otel_metrics import (
                    marketplace_connection_tests_total,
                    marketplace_connection_test_failures_total,
                )
                status = "success" if success else "failure"
                marketplace_connection_tests_total.labels(
                    marketplace_type=connection.marketplace_type,
                    tenant_id=effective_tenant_id,
                    status=status,
                ).inc()
                if not success and error_type:
                    marketplace_connection_test_failures_total.labels(
                        marketplace_type=connection.marketplace_type,
                        tenant_id=effective_tenant_id,
                        connection_id=str(connection.id),
                        error_type=error_type,
                    ).inc()
            except Exception as e:
                logger.warning(
                    f"Failed to record connection test metrics: {e}",
                    exc_info=True,
                )

            # Add span attributes
            if span:
                add_span_attributes(
                    {
                        "connection.test.success": success,
                        "connection.marketplace_type": connection.marketplace_type,
                    }
                )
                if success:
                    set_span_status(StatusCode.OK)
                else:
                    set_span_status(StatusCode.ERROR)

            # Create audit log
            try:
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                user_obj = User.objects.get(id=effective_user_id) if effective_user_id else None

                from hub.apps.audit.utils import create_audit_event

                create_audit_event(
                    resource_type="MARKETPLACE_CONNECTION",
                    action="CONNECTION_TESTED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(connection.id),
                    result="SUCCESS" if success else "FAILURE",
                    details={
                        "connection_id": str(connection.id),
                        "marketplace_type": connection.marketplace_type,
                        "success": success,
                        "error_message": error_message,
                        "tested_at": tested_at.isoformat(),
                        "request_id": self.request_id,
                    },
                    request=request,
                )
            except Exception as e:
                # Log but don't fail test if audit logging fails
                logger.warning(
                    f"Failed to create audit log for connection test {connection.id}: {e}",
                    exc_info=True,
                )

            # Publish event
            try:
                self.publish_connection_tested(
                    connection_id=str(connection.id),
                    success=success,
                    error_message=error_message,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    request_id=self.request_id,
                )
            except Exception as e:
                # Log but don't fail test if event publishing fails
                logger.warning(
                    f"Failed to publish connection.tested event for {connection.id}: {e}",
                    exc_info=True,
                )

            # Send notification email if test failed (Task 9.10.6.3.2)
            if not success and error_message:
                try:
                    from hub.apps.notifications.tasks import send_marketplace_connection_test_failure_email
                    send_marketplace_connection_test_failure_email.delay(
                        connection_id=str(connection.id),
                        error_message=error_message,
                        tested_at=tested_at.isoformat(),
                        user_id=effective_user_id,
                        tenant_id=effective_tenant_id
                    )
                except Exception as e:
                    # Log but don't fail test if notification fails
                    logger.warning(
                        f"Failed to send connection test failure notification for {connection.id}: {e}",
                        exc_info=True,
                    )

            # Prepare result
            result = {
                "success": success,
                "message": (
                    "Connection test successful"
                    if success
                    else (error_message or "Connection test failed")
                ),
                "error": error_message if not success else None,
                "tested_at": tested_at.isoformat(),
            }

            logger.info(
                f"Tested marketplace connection {connection.id}: {'SUCCESS' if success else 'FAILED'}"
            )

            return result

        except (NotFoundError, ValidationError) as e:
            # Re-raise service errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            raise
        except Exception as e:
            # Log unexpected errors
            if span:
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            logger.error(
                f"Unexpected error testing marketplace connection: {e}",
                exc_info=True,
                extra={
                    "connection_id": connection_id,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )
            raise ValidationError(
                f"Failed to test marketplace connection: {str(e)}", details={"error": str(e)}
            ) from e
        finally:
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(
                        "integrations_non_critical_failed",
                        extra={"error_type": type(e).__name__, "error": str(e)},
                    )
