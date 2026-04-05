"""
Event API URLs
"""
from django.urls import path
from .views import replay_events, DLQListView, DLQRetryView, DLQResolveView

app_name = 'events'

urlpatterns = [
    path('replay/', replay_events, name='replay-events'),
    path('dlq/', DLQListView.as_view(), name='dlq-list'),
    path('dlq/<uuid:dlq_id>/retry/', DLQRetryView.as_view(), name='dlq-retry'),
    path('dlq/<uuid:dlq_id>/resolve/', DLQResolveView.as_view(), name='dlq-resolve'),
]

