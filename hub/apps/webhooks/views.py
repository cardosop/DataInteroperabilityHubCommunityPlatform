"""
Webhook Views

REST API views for webhook management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
import requests

from .models import Webhook, WebhookDelivery, WebhookStatus, DeliveryStatus, WebhookEventType
from .serializers import WebhookSerializer, WebhookDeliverySerializer
from .service import WebhookDeliveryService
from hub.apps.audit.utils import create_audit_event


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
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return Webhook.objects.all()
        
        # Get tenant from request
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            return Webhook.objects.none()
        
        return Webhook.objects.filter(tenant_id=tenant_id)
    
    def _get_tenant_id(self):
        """Get tenant ID from request"""
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            return str(self.request.tenant_id)
        
        tenant = getattr(self.request, "tenant", None)
        if tenant and hasattr(tenant, "id"):
            return str(tenant.id)
        
        return None
    
    def perform_create(self, serializer):
        """Create webhook with audit logging"""
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            raise ValidationError("Tenant is required")
        
        webhook = serializer.save(
            tenant_id=tenant_id,
            created_by=self.request.user
        )
        
        # Log audit event
        create_audit_event(
            resource_type="WEBHOOK",
            action="WEBHOOK_CREATED",
            actor_user=self.request.user,
            tenant=webhook.tenant,
            resource_id=str(webhook.id),
            details={
                "name": webhook.name,
                "url": webhook.url,
                "event_types": webhook.event_types,
                "status": webhook.status
            },
            request=self.request
        )
    
    @action(detail=True, methods=['post'], url_path='test')
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
            "timestamp": timezone.now().isoformat()
        }
        
        # Trigger test delivery
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(webhook.tenant.id),
            event_type="asset.created",  # Use a generic event type for testing
            resource_type="WEBHOOK",
            resource_id=str(webhook.id),
            event_data=test_event_data
        )
        
        return Response(
            {"status": "test webhook triggered"},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'], url_path='deliveries')
    def deliveries(self, request, id=None):
        """
        Get webhook delivery history.
        
        GET /api/v1/webhooks/{id}/deliveries/
        """
        webhook = self.get_object()
        
        deliveries = WebhookDelivery.objects.filter(webhook=webhook).order_by('-created_at')[:100]
        
        serializer = WebhookDeliverySerializer(deliveries, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
        """Get tenant ID from request"""
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            return str(self.request.tenant_id)
        
        tenant = getattr(self.request, "tenant", None)
        if tenant and hasattr(tenant, "id"):
            return str(tenant.id)
        
        return None
    
    @action(detail=True, methods=['post'], url_path='retry')
    def retry_delivery(self, request, id=None):
        """
        Retry a failed webhook delivery.
        
        POST /api/v1/webhook-deliveries/{id}/retry/
        """
        delivery = self.get_object()
        
        success = WebhookDeliveryService.retry_delivery(str(delivery.id))
        
        if success:
            return Response(
                {"status": "retry scheduled"},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Cannot retry this delivery"},
                status=status.HTTP_400_BAD_REQUEST
            )

