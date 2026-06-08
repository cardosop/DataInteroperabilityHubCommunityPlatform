"""Public DSAR ingress (anonymous + capability-gated tenants)."""

from django.urls import path

from hub.apps.dsar.views import (
    PublicDsarStatusByTokenView,
    PublicDsarSubmitView,
    PublicDsarVerifyOtpView,
)

urlpatterns = [
    path("dsar-requests/", PublicDsarSubmitView.as_view(), name="public-dsar-submit"),
    path(
        "dsar-requests/<uuid:dsar_id>/verify-otp/",
        PublicDsarVerifyOtpView.as_view(),
        name="public-dsar-verify-otp",
    ),
    path(
        "dsar-requests/status/<uuid:reference_token>/",
        PublicDsarStatusByTokenView.as_view(),
        name="public-dsar-status",
    ),
]
