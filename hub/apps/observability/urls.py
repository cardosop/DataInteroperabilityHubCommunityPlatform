"""
Observability URLs
"""
from django.urls import path
from .metrics import metrics_view

urlpatterns = [
    path('', metrics_view, name='prometheus-metrics'),
]

