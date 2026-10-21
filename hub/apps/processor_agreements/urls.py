from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hub.apps.processor_agreements import views

router = DefaultRouter()
router.register(r"processors", views.ProcessorViewSet, basename="processor")
router.register(
    r"processor-agreements", views.ProcessorAgreementViewSet, basename="processor-agreement"
)
router.register(
    r"asset-processor-links",
    views.AssetProcessorLinkViewSet,
    basename="asset-processor-link",
)

urlpatterns = [
    path("", include(router.urls)),
]
