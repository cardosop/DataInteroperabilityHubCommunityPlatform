from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hub.apps.dsar import views

router = DefaultRouter()
router.register(r"requests", views.DSARRequestViewSet, basename="dsar-request")

urlpatterns = [
    path("", include(router.urls)),
]
