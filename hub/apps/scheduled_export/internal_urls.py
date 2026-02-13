"""
Internal Worker API URL routes.

Mounted at: /api/v1/scheduled-exports/internal/
"""

from django.urls import path

from .internal_views import (
    InternalConfigView,
    InternalProcessExportView,
    InternalRunViewSet,
)

urlpatterns = [
    path("runs/", InternalRunViewSet.as_view({"post": "create"}), name="internal-runs-create"),
    path(
        "runs/<uuid:pk>/",
        InternalRunViewSet.as_view({"patch": "partial_update"}),
        name="internal-runs-update",
    ),
    path(
        "config/<uuid:scheduled_export_id>/",
        InternalConfigView.as_view(),
        name="internal-config",
    ),
    path("process-export/", InternalProcessExportView.as_view(), name="internal-process-export"),
]
