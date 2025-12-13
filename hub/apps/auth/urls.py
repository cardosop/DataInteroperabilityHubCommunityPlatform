"""
Authentication URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    login,
    refresh_token,
    logout,
    password_reset_request,
    password_reset_confirm,
    accept_invitation,
    APIKeyViewSet
)
from .sso_views import SSOViewSet

router = DefaultRouter()
router.register(r"api-keys", APIKeyViewSet, basename="api-key")
router.register(r"sso", SSOViewSet, basename="sso")

urlpatterns = [
    path("login/", login, name="login"),
    path("refresh/", refresh_token, name="refresh-token"),
    path("logout/", logout, name="logout"),
    path("password-reset/", password_reset_request, name="password-reset-request"),
    path("password-reset/confirm/", password_reset_confirm, name="password-reset-confirm"),
    path("accept-invitation/", accept_invitation, name="accept-invitation"),
    path("", include(router.urls)),
]

