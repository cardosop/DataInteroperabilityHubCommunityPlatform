from django.urls import include, path, re_path

from .views import (
    OpenAPISchemaView,
    OpenAPIYAMLView,
    ReDocView,
    SwaggerUIView,
    api_info,
    api_not_found,
    ensure_e2e_invitation_token,
    ensure_e2e_subscription,
    ensure_e2e_tenant_switch_setup,
    ensure_e2e_users,
    reset_e2e_auth_rate_limits,
)
# Phase 226 G11 — E2E-only webhook sink endpoint.
from .webhook_sink_views import webhook_sink
# Phase 226 OQ-MailHog — E2E-only MailHog inbox proxy.
from .mailhog_proxy_views import mailhog_message_detail, mailhog_messages_list

# Non-MVP areas remain mounted so URLconf is stable across Django settings reloads
# (e.g. tests using @override_settings). When MVP_MODE is True, access is blocked
# by MvpModeApiGateMiddleware and omitted from OpenAPI via postprocess_drop_mvp_gated_paths.
urlpatterns = [
    path("", api_info, name="api-info"),
    path("openapi.json", OpenAPISchemaView.as_view(), name="openapi-schema-v1"),
    path("openapi.yaml", OpenAPIYAMLView.as_view(), name="openapi-schema-yaml"),
    path("auth/", include("hub.apps.auth.urls")),
    path("tenants/", include("hub.apps.tenants.urls")),
    path("users/", include("hub.apps.users.urls")),
    path("audit/", include("hub.apps.audit.urls")),
    path("files/", include("hub.apps.files.urls")),
    path("datasets/", include("hub.apps.datasets.urls")),
    path("jobs/", include("hub.apps.jobs.urls")),
    path("contracts/", include("hub.apps.contracts.urls")),
    path("security/", include("hub.apps.contracts.security_urls")),
    path("assets/", include("hub.apps.assets.urls")),
    path("dq/", include("hub.apps.dq.urls")),
    path("compliance/", include("hub.apps.compliance.urls")),
    path("semantic/", include("hub.apps.semantic.urls")),
    path("marketplace/", include("hub.apps.marketplace.urls")),
    path("scheduled-ingestions/", include("hub.apps.scheduled_ingestion.urls")),
    path("scheduled-exports/", include("hub.apps.scheduled_export.urls")),
    path("search/", include("hub.apps.search.urls")),
    path("developer/", include("hub.apps.developer.urls")),
    path("webhooks/", include("hub.apps.webhooks.urls")),
    path("events/", include("hub.apps.core.events.urls")),
    path("", include("hub.apps.api.analytics.urls")),
    path("governance/", include("hub.apps.governance.urls")),
    path("notifications/", include("hub.apps.notifications.urls")),
    path("", include("hub.apps.observability.urls_api_v1")),
    path("ai/", include("hub.apps.ai.urls")),
    path("", include("hub.apps.social.urls")),
    path("mesh/", include("hub.apps.mesh.urls")),
    path("virtualization/", include("hub.apps.virtualization.urls")),
    path("integrations/", include("hub.apps.integrations.urls")),
    path("baas/", include("hub.apps.baas.urls")),
    path("ml/", include("hub.apps.ml.urls")),
    path("billing/", include("hub.apps.billing.urls")),
    path("platform/", include("hub.apps.platform.urls")),
    path("versioning/", include("hub.apps.versioning.urls")),
    path("workflows/", include("hub.apps.orchestration.urls")),
    path("transformation/", include("hub.apps.api.transformation_urls")),
    path("test/ensure-e2e-subscription/", ensure_e2e_subscription, name="ensure-e2e-subscription"),
    path("test/ensure-e2e-invitation-token/", ensure_e2e_invitation_token, name="ensure-e2e-invitation-token"),
    path("test/ensure-e2e-tenant-switch-setup/", ensure_e2e_tenant_switch_setup, name="ensure-e2e-tenant-switch-setup"),
    path("test/ensure-e2e-users/", ensure_e2e_users, name="ensure-e2e-users"),
    # Cycle-7 (staging): pre-flight rate-limit reset for long E2E runs.
    # Remote runner equivalent of `manage.py reset_e2e_auth_rate_limits` —
    # required because the per-tenant auth limiter accumulates over the
    # 287-test MVP suite and only the local docker path had a reset hook.
    path("test/reset-e2e-auth-rate-limits/", reset_e2e_auth_rate_limits, name="reset-e2e-auth-rate-limits"),
    # Phase 226 G11 — E2E webhook sink. Receives inbound POSTs from the
    # WebhookDeliveryService so specs can assert delivery + payload shape.
    path("test/webhook-sink/<str:sink_id>/", webhook_sink, name="webhook-sink"),
    # Phase 226 OQ-MailHog — token-gated read-only proxy to the staging
    # MailHog inbox. Required for JOURNEY-AUTH-003 to extract the
    # password-reset token from the email body. Same E2E_TEST_SECRET
    # gate as the rest of the test/* family.
    path(
        "test/mailhog/messages/",
        mailhog_messages_list,
        name="mailhog-list",
    ),
    path(
        "test/mailhog/messages/<str:message_id>/",
        mailhog_message_detail,
        name="mailhog-detail",
    ),
    re_path(
        r"^(?!auth/|tenants/|users/|audit/|files/|datasets/|jobs/|contracts/|assets/|dq/|compliance/|semantic/|marketplace/|scheduled-ingestions/|scheduled-exports/|search/|developer/|webhooks/|events/|mesh/|virtualization/|integrations/|baas/|ml/|billing/|platform/|versioning/|workflows/|transformation/|notifications/|governance/|test/).*$",
        api_not_found,
        name="api-not-found",
    ),
]
