"""285.6.2 — Data Movement URL routing."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DataMovementConfigViewSet

router = DefaultRouter()
router.register(r"config", DataMovementConfigViewSet, basename="data-movement-config")

from .internal_views import internal_pipeline_config

urlpatterns = [
    path("", include(router.urls)),
    path(
        "internal/config/<str:direction>/<uuid:resource_id>/",
        internal_pipeline_config,
        name="data-movement-internal-config",
    ),
]
