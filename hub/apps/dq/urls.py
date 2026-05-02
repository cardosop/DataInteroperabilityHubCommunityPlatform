"""
DQ URL Configuration

Standardized to use 'runs' pattern for consistency with API naming standards.
This follows the plural resources rule and avoids duplication (no 'dq/dq-runs').

Phase 240.3.B (REQ-DQ-A2 / D240.10) — advanced quality endpoints under
``/dq/quality/{anomalies,trends,scorecards,root_cause_analysis}/`` are
exposed by ``DQQualityViewSet``. The ViewSet itself is also dual-mounted
under the deprecated ``/api/v1/quality/*`` prefix in ``hub/apps/api/urls.py``;
that wrapper emits ``Sunset``/``Deprecation``/``Link`` response headers.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DQAlertingRuleViewSet, DQQualityViewSet, DQRunViewSet

router = DefaultRouter()
router.register(r"runs", DQRunViewSet, basename="dq-run")
router.register(r"alerting-rules", DQAlertingRuleViewSet, basename="dq-alerting-rule")

# Phase 240.3.B.1+3 — canonical mount at /api/v1/dq/quality/.
quality_router = DefaultRouter()
quality_router.register(r"quality", DQQualityViewSet, basename="dq-quality")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(quality_router.urls)),
]
