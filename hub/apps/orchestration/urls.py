"""
URL configuration for Workflows API (list, get by name, trigger).
"""

from django.urls import path

from . import views

app_name = "orchestration"

urlpatterns = [
    path("", views.WorkflowListView.as_view(), name="workflow-list"),
    path(
        "<str:name>/",
        views.WorkflowDetailView.as_view(),
        name="workflow-detail",
    ),
    path(
        "<str:name>/trigger/",
        views.WorkflowTriggerView.as_view(),
        name="workflow-trigger",
    ),
]
