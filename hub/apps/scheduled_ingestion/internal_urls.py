"""
Internal Worker API URL routes.

Mounted at: /api/v1/scheduled-ingestions/internal/
"""

from django.urls import path

from .internal_views import (
    InternalConfigView,
    InternalCreateJobView,
    InternalProcessFileView,
    InternalRunViewSet,
    InternalTestDataView,
)

urlpatterns = [
    path("runs/", InternalRunViewSet.as_view({"post": "create"}), name="internal-runs-create"),
    path(
        "runs/<uuid:pk>/",
        InternalRunViewSet.as_view({"patch": "partial_update"}),
        name="internal-runs-update",
    ),
    path(
        "config/<uuid:scheduled_ingestion_id>/",
        InternalConfigView.as_view(),
        name="internal-config",
    ),
    path("process-file/", InternalProcessFileView.as_view(), name="internal-process-file"),
    path("jobs/", InternalCreateJobView.as_view(), name="internal-jobs-create"),
    path(
        "test-data/<str:filename>",
        InternalTestDataView.as_view(),
        name="internal-test-data",
    ),
]
