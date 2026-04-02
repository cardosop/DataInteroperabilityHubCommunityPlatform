"""
Transformation pipelines URLs — delegates to the transformation app.

Phase 115A: Replaced placeholder views with full transformation app.
"""
from django.urls import include, path

# Delegate entirely to the transformation app's own URL configuration.
urlpatterns = [
    path("", include("hub.apps.transformation.urls")),
]
