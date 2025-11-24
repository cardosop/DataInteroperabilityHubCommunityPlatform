"""
DQ URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DQRunViewSet

router = DefaultRouter()
router.register(r"dq-runs", DQRunViewSet, basename="dq-run")

urlpatterns = [
    path("", include(router.urls)),
]

