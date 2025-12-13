"""
Webhook URLs

URL configuration for webhook endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WebhookViewSet, WebhookDeliveryViewSet

router = DefaultRouter()
router.register(r'webhooks', WebhookViewSet, basename='webhook')
router.register(r'webhook-deliveries', WebhookDeliveryViewSet, basename='webhook-delivery')

urlpatterns = [
    path('', include(router.urls)),
]

