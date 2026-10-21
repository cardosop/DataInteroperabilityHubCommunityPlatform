"""
Compliance URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ComplianceRunViewSet
from .webhook_report_views import ComplianceWebhookReportSummaryView

router = DefaultRouter()
router.register(r"runs", ComplianceRunViewSet, basename="compliance-run")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "webhooks/completed/report/",
        ComplianceWebhookReportSummaryView.as_view(),
        name="compliance-webhook-report-summary",
    ),
]
