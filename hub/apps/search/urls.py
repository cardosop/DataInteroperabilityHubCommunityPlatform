"""
Search URLs
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SearchViewSet

router = DefaultRouter()
# Register with empty prefix since path prefix already includes 'search/'
# This prevents triple "search" in URL: /api/v1/search/search/search/
# Result: /api/v1/search/search/ (path prefix + action name)
router.register(r"", SearchViewSet, basename="search")

urlpatterns = [
    path("", include(router.urls)),
]
