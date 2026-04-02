"""
Webhook Views

REST API views for webhook management.
"""

import requests
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.tenants.request_tenant import get_request_tenant_id

from .models import DeliveryStatus, Webhook, WebhookDelivery, WebhookEventType, WebhookStatus
from .serializers import WebhookDeliverySerializer, WebhookSerializer
from .service import WebhookDeliveryService
from .webhook_service import WebhookService


def _resolve_tenant_id(request):
    """Get tenant ID from request; if user has none, assign default tenant so list/create work."""
    tenant_id = get_request_tenant_id(request)
    if tenant_id:
        return tenant_id
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None
    from django.contrib.auth import get_user_model

    from hub.apps.tenants.models import Tenant, TenantStatus

    User = get_user_model()
    default_tenant, _ = Tenant.objects.get_or_create(
        slug="default",
        defaults={"name": "Default Tenant", "status": TenantStatus.ACTIVE},
    )
    if not default_tenant.is_active():
        return None
    User.objects.filter(id=user.id).update(tenant_id=default_tenant.id)
    return str(default_tenant.id)


class WebhookViewSet(viewsets.ModelViewSet):
    """
    ViewSet for webhook management.
    """

    queryset = Webhook.objects.all()
    serializer_class = WebhookSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all webhooks
        qs = Webhook.objects.select_related("tenant", "created_by")
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return qs

        # Get tenant from request
        tenant_id = _resolve_tenant_id(self.request)
        if not tenant_id:
            return Webhook.objects.none()

        return qs.filter(tenant_id=tenant_id)

    def _get_tenant_id(self):
        return _resolve_tenant_id(self.request)

    def perform_create(self, serializer):
        """
        Create webhook via service layer (Phase 12.2.1).

        Service handles validation, persistence, and audit event emission.
        """
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            raise ValidationError("Tenant is required")

        # Validate request data via serializer (request validation only)
        serializer.is_valid(raise_exception=True)

        # Create webhook via service layer (Phase 12.2.1)
        # Service handles validation, persistence, and audit event emission
        try:
            service = WebhookService(tenant_id=tenant_id, user_id=str(self.request.user.id))
            webhook = service.create_webhook(
                tenant_id=tenant_id,
                user_id=str(self.request.user.id),
                name=serializer.validated_data["name"],
                url=serializer.validated_data["url"],
                secret=serializer.validated_data["secret"],
                event_types=serializer.validated_data["event_types"],
                status=serializer.validated_data.get("status", WebhookStatus.ACTIVE),
                max_retries=serializer.validated_data.get("max_retries", 5),
                retry_intervals=serializer.validated_data.get("retry_intervals"),
            )
        except ServiceValidationError as e:
            raise ValidationError(str(e))
        except NotFoundError as e:
            raise ValidationError(str(e))

        # Update serializer instance for response
        serializer.instance = webhook

    @transaction.atomic
    def perform_update(self, serializer):
        """
        Update webhook via service layer (Phase 12.2.1).

        Service handles validation, persistence, and audit event emission.
        """
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            raise ValidationError("Tenant is required")

        # Validate request data via serializer (request validation only)
        serializer.is_valid(raise_exception=True)

        # Get the webhook instance
        webhook = self.get_object()

        # Prepare update data from validated serializer data
        update_data = {}
        for field in serializer.validated_data:
            update_data[field] = serializer.validated_data[field]

        # Update webhook via service layer (Phase 12.2.1)
        # Service handles validation, persistence, and audit event emission
        try:
            service = WebhookService(tenant_id=tenant_id, user_id=str(self.request.user.id))
            updated_webhook = service.update_webhook(
                webhook_id=str(webhook.id),
                tenant_id=tenant_id,
                user_id=str(self.request.user.id),
                **update_data,
            )
        except ServiceValidationError as e:
            raise ValidationError(str(e))
        except NotFoundError as e:
            raise ValidationError(str(e))

        # Update serializer instance for response
        serializer.instance = updated_webhook

    @action(detail=True, methods=["post"], url_path="test")
    def test_webhook(self, request, id=None):
        """
        Test webhook delivery.

        POST /api/v1/webhooks/{id}/test/
        """
        webhook = self.get_object()

        # Create test event
        test_event_data = {
            "test": True,
            "message": "Test webhook delivery",
            "timestamp": timezone.now().isoformat(),
        }

        # Trigger test delivery
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(webhook.tenant.id),
            event_type="asset.created",  # Use a generic event type for testing
            resource_type="WEBHOOK",
            resource_id=str(webhook.id),
            event_data=test_event_data,
        )

        return Response({"status": "test webhook triggered"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="deliveries")
    def deliveries(self, request, id=None):
        """
        Get webhook delivery history.

        GET /api/v1/webhooks/{id}/deliveries/
        """
        webhook = self.get_object()

        queryset = WebhookDelivery.objects.filter(webhook=webhook).order_by("-created_at")

        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is not None:
            serializer = WebhookDeliverySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = WebhookDeliverySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="event-types")
    def event_types(self, request):
        """
        Get available webhook event types.

        GET /api/v1/webhooks/event-types/

        Query parameters:
        - odps_only: If true, return only ODPS event types
        """
        odps_only = request.query_params.get("odps_only", "false").lower() == "true"

        if odps_only:
            event_types = [
                {"value": event_type, "label": label}
                for event_type, label in WebhookEventType.choices
                if WebhookEventType.is_odps_event_type(event_type)
            ]
        else:
            event_types = [
                {"value": event_type, "label": label}
                for event_type, label in WebhookEventType.choices
            ]

        return Response(
            {
                "event_types": event_types,
                "odps_event_types": WebhookEventType.get_odps_event_types(),
            },
            status=status.HTTP_200_OK,
        )


class WebhookDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for webhook delivery history (read-only).
    """

    queryset = WebhookDelivery.objects.all()
    serializer_class = WebhookDeliverySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all deliveries
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return WebhookDelivery.objects.all()

        # Get tenant from request
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            return WebhookDelivery.objects.none()

        return WebhookDelivery.objects.filter(webhook__tenant_id=tenant_id)

    def _get_tenant_id(self):
        return _resolve_tenant_id(self.request)

    @action(detail=True, methods=["post"], url_path="retry")
    def retry_delivery(self, request, id=None):
        """
        Retry a failed webhook delivery.

        POST /api/v1/webhook-deliveries/{id}/retry/
        """
        delivery = self.get_object()

        success = WebhookDeliveryService.retry_delivery(str(delivery.id))

        if success:
            return Response({"status": "retry scheduled"}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Cannot retry this delivery"}, status=status.HTTP_400_BAD_REQUEST
            )
