"""
Marketplace Integration URLs

URL routing for marketplace connection management endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MarketplaceConnectionViewSet,
    MarketplaceSyncJobViewSet,
    MarketplaceMappingViewSet,
    list_connectors,
    get_connector_info,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(
    r'marketplace/connections',
    MarketplaceConnectionViewSet,
    basename='marketplace-connection'
)
router.register(
    r'marketplace/sync',
    MarketplaceSyncJobViewSet,
    basename='marketplace-sync-job'
)
router.register(
    r'marketplace/mappings',
    MarketplaceMappingViewSet,
    basename='marketplace-mapping'
)

urlpatterns = [
    path('', include(router.urls)),
    # Connector endpoints
    path('marketplace/connectors/', list_connectors, name='marketplace-connectors-list'),
    path('marketplace/connectors/<str:connector_type>/', get_connector_info, name='marketplace-connectors-info'),
]

