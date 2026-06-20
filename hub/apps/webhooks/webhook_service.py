"""
Webhook Service

Service layer for webhook management operations.
All create/update paths handle validation, persistence, and audit event emission.
"""

from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.services.base import BaseService, ValidationError
from hub.apps.webhooks.models import Webhook, WebhookStatus


class WebhookService(BaseService):
    """
    Service for webhook management operations.

    Provides business logic for:
    - Webhook creation
    - Webhook updates
    - Webhook validation
    """

    service_name = "webhook_service"

    def __init__(self, tenant_id: str | None = None, user_id: str | None = None):
        """
        Initialize WebhookService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def create_webhook(
        self,
        tenant_id: str,
        user_id: str,
        name: str,
        url: str,
        secret: str,
        event_types: list[str],
        status: str = WebhookStatus.ACTIVE,
        max_retries: int = 5,
        retry_intervals: list[int] | None = None,
    ) -> Webhook:
        """
        Create a webhook.

        Validates input, persists Webhook, and emits exactly one audit event.

        Args:
            tenant_id: Tenant UUID
            user_id: User UUID creating the webhook
            name: Webhook name/description
            url: Webhook delivery URL
            secret: Webhook secret for HMAC signature
            event_types: List of event types to subscribe to
            status: Webhook status (default: ACTIVE)
            max_retries: Maximum number of delivery retries
            retry_intervals: Retry intervals in seconds (default: [1, 5, 30, 300, 1800])

        Returns:
            Created Webhook instance

        Raises:
            ValidationError: If validation fails
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.tenants.services import PlanLimitService
        from hub.apps.users.models import User

        # Plan limit enforcement
        plan_limit_service = PlanLimitService(tenant_id=tenant_id)
        plan_limit_service.check_limit(
            tenant_id=tenant_id,
            limit_key="max_webhooks",
            delta=1,
        )

        # Resolve tenant and user
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)

        # Validate required fields
        if not name:
            raise ValidationError(
                "Webhook name is required", code="VALIDATION_ERROR", details={"name": name}
            )

        if not url:
            raise ValidationError(
                "Webhook URL is required", code="VALIDATION_ERROR", details={"url": url}
            )

        if not secret:
            raise ValidationError(
                "Webhook secret is required", code="VALIDATION_ERROR", details={"secret": secret}
            )

        if not event_types or not isinstance(event_types, list) or len(event_types) == 0:
            raise ValidationError(
                "At least one event type is required",
                code="VALIDATION_ERROR",
                details={"event_types": event_types},
            )

        # Validate URL format
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.core.validators import URLValidator

        url_validator = URLValidator()
        try:
            url_validator(url)
        except DjangoValidationError:
            raise ValidationError(
                f"Invalid URL format: {url}", code="VALIDATION_ERROR", details={"url": url}
            )

        # Use default retry intervals if not provided
        if retry_intervals is None:
            retry_intervals = [1, 5, 30, 300, 1800]

        # Create webhook
        webhook = Webhook.objects.create(
            tenant_id=tenant_id,
            name=name,
            url=url,
            secret=secret,
            event_types=event_types,
            status=status,
            max_retries=max_retries,
            retry_intervals=retry_intervals,
            created_by=user,
        )

        # Emit exactly one audit event (Phase 12.4.1)
        create_audit_event(
            resource_type="WEBHOOK",
            action="WEBHOOK_CREATED",
            actor_user=user,
            tenant=tenant,
            resource_id=str(webhook.id),
            details={
                "name": webhook.name,
                "url": webhook.url,
                "event_types": webhook.event_types,
                "status": webhook.status,
            },
        )

        return webhook

    @transaction.atomic
    def update_webhook(
        self, webhook_id: str, tenant_id: str, user_id: str, **update_data
    ) -> Webhook:
        """
        Update a webhook.

        Validates input, persists changes, and emits exactly one audit event.

        Args:
            webhook_id: Webhook UUID
            tenant_id: Tenant UUID
            user_id: User UUID updating the webhook
            **update_data: Fields to update

        Returns:
            Updated Webhook instance

        Raises:
            NotFoundError: If webhook not found
            ValidationError: If validation fails
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        # Get webhook
        webhook = self.get_resource_or_raise(Webhook, webhook_id, tenant_id=tenant_id)

        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)

        # Store original values for audit
        original_data = {
            "name": webhook.name,
            "url": webhook.url,
            "status": webhook.status,
            "event_types": webhook.event_types,
        }

        # Validate URL if being updated
        if "url" in update_data:
            from django.core.exceptions import ValidationError as DjangoValidationError
            from django.core.validators import URLValidator

            url_validator = URLValidator()
            try:
                url_validator(update_data["url"])
            except DjangoValidationError:
                raise ValidationError(
                    f"Invalid URL format: {update_data['url']}",
                    code="VALIDATION_ERROR",
                    details={"url": update_data["url"]},
                )

        # Update fields
        for field, value in update_data.items():
            if hasattr(webhook, field) and field not in [
                "id",
                "tenant",
                "created_by",
                "created_at",
                "updated_at",
            ]:
                setattr(webhook, field, value)

        # Validate updated webhook
        try:
            webhook.full_clean()
        except DjangoValidationError as e:
            raise ValidationError(
                str(e), code="VALIDATION_ERROR", details={"validation_errors": str(e)}
            )

        # Save webhook
        webhook.save()

        # Emit exactly one audit event (Phase 12.4.1)
        create_audit_event(
            resource_type="WEBHOOK",
            action="WEBHOOK_UPDATED",
            actor_user=user,
            tenant=tenant,
            resource_id=str(webhook.id),
            details={
                "changes": update_data,
                "original": original_data,
            },
        )

        return webhook
