"""
Governance URLs

URL configuration for governance endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccessAnalyticsViewSet, AccessCertificationViewSet
from .access_request_views import AccessRequestViewSet
from .retention_views import RetentionPolicyViewSet

router = DefaultRouter()
router.register(r'analytics', AccessAnalyticsViewSet, basename='access-analytics')
router.register(r'certifications', AccessCertificationViewSet, basename='access-certification')
router.register(r'access-requests', AccessRequestViewSet, basename='access-request')
router.register(r'retention-policies', RetentionPolicyViewSet, basename='retention-policy')

urlpatterns = [
    path('access/', include(router.urls)),
    # Also register at governance/ level for direct access
    path('', include(router.urls)),
]

