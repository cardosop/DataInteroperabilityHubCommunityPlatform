"""
Webhook URLs

URL configuration for webhook endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WebhookDeliveryViewSet, WebhookViewSet

router = DefaultRouter()
router.register(r"webhooks", WebhookViewSet, basename="webhook")
router.register(r"webhook-deliveries", WebhookDeliveryViewSet, basename="webhook-delivery")

urlpatterns = [
    path("", include(router.urls)),
]
