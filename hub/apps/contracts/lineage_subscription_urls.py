"""
Phase 228.F3.6 — URL routing for the lineage subscription endpoints.

Mounted under ``/api/v1/lineage/subscriptions/`` in the top-level
``hub/apps/api/urls.py``.
"""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hub.apps.contracts.lineage_subscription_views import (
    LineageSubscriptionViewSet,
)

router = DefaultRouter()
# Empty prefix — the parent path already says ``lineage/subscriptions/``
# so we don't want to double-nest.
router.register(
    r"",
    LineageSubscriptionViewSet,
    basename="lineage-subscription",
)

urlpatterns = [
    path("", include(router.urls)),
]
