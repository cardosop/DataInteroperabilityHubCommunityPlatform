from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hub.apps.ropa.views import RopaGenerationViewSet

router = DefaultRouter()
router.register(r"generations", RopaGenerationViewSet, basename="ropa-generation")

generate_post = RopaGenerationViewSet.as_view({"post": "generate"})
urlpatterns = [
    path("generate/", generate_post, name="ropa-generate"),
    path("", include(router.urls)),
]
