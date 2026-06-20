"""
Event API URLs
"""

from django.urls import path

from .views import DLQListView, DLQResolveView, DLQRetryView, replay_events

app_name = "events"

urlpatterns = [
    path("replay/", replay_events, name="replay-events"),
    path("dlq/", DLQListView.as_view(), name="dlq-list"),
    path("dlq/<uuid:dlq_id>/retry/", DLQRetryView.as_view(), name="dlq-retry"),
    path("dlq/<uuid:dlq_id>/resolve/", DLQResolveView.as_view(), name="dlq-resolve"),
]
