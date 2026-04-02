"""
URL configuration for the unified /api/search/ endpoint (Phase 18.3).

Registered in hub/urls.py as:
    path("api/search/", include("hub.apps.search.search_urls"))

Resulting URL:  GET /api/search/?q=<term>&types=assets,contracts
"""
from django.urls import path

from .views import UnifiedSearchView

urlpatterns = [
    path("", UnifiedSearchView.as_view(), name="unified-search"),
]
