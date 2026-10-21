"""
Authentication URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .sso_views import SSOViewSet
from .views import (
    APIKeyViewSet,
    accept_invitation,
    end_all_other_sessions,
    list_active_sessions,
    login,
    logout,
    me,
    me_tenants,
    password_reset_confirm,
    password_reset_request,
    refresh_token,
    register,
    resend_verification_email,
    revoke_session,
    switch_tenant,
    verify_email,
)

router = DefaultRouter()
router.register(r"api-keys", APIKeyViewSet, basename="api-key")
router.register(r"sso", SSOViewSet, basename="sso")

urlpatterns = [
    path("login/", login, name="login"),
    path("register/", register, name="register"),
    path("me/", me, name="me"),
    path("me/tenants/", me_tenants, name="me-tenants"),
    path("switch-tenant/", switch_tenant, name="switch-tenant"),
    path("refresh/", refresh_token, name="refresh-token"),
    path("logout/", logout, name="logout"),
    path("password-reset/", password_reset_request, name="password-reset-request"),
    path("password-reset/confirm/", password_reset_confirm, name="password-reset-confirm"),
    path("verify-email/", verify_email, name="verify-email"),
    path("resend-verification/", resend_verification_email, name="resend-verification"),
    path("accept-invitation/", accept_invitation, name="accept-invitation"),
    path("sessions/", list_active_sessions, name="list-active-sessions"),
    path("sessions/end-all-others/", end_all_other_sessions, name="end-all-other-sessions"),
    path("sessions/<uuid:session_id>/revoke/", revoke_session, name="revoke-session"),
    path("", include(router.urls)),
]
