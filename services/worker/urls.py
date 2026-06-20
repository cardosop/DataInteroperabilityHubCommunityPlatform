"""
URL configuration for worker service health check endpoints.
"""

from django.urls import path

from . import health

urlpatterns = [
    path("healthz", health.healthz, name="healthz"),
    path("ready", health.ready, name="ready"),
]
