"""
API Views

Views for API documentation and OpenAPI schema generation.
"""

import functools
import hmac
import logging
from collections.abc import Callable
from typing import Any

import drf_spectacular.renderers
from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from hub.apps.api.throttles import VersionDiscoveryRateThrottle
from hub.apps.users.management.commands.ensure_e2e_user_roles import (
    PROFILE_ISOLATION_WORKER_COUNT,
)

_e2e_logger = logging.getLogger(__name__)


def require_e2e_token(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Shared-secret gate for the four ``/api/v1/test/ensure-e2e-*`` endpoints.

    Returns 404 unconditionally when:
      - ``settings.E2E_TEST_SECRET`` is unset / empty, OR
      - request header ``X-E2E-Token`` is missing, OR
      - ``X-E2E-Token`` does not match the configured secret.

    Uses ``hmac.compare_digest`` so byte-by-byte timing leaks don't reveal
    the secret under probe traffic. Token mismatches are logged at WARNING
    (without the provided or expected values) so staging probes are
    visible via structured logs.

    Wraps the inner function and marks it with ``_require_e2e_token = True``
    so the post-condition test in ``test_require_e2e_token.py`` can
    verify the decorator stays applied on all four E2E views.
    """

    @functools.wraps(view_func)
    def wrapper(request: Any, *args: Any, **kwargs: Any) -> Any:
        secret = getattr(settings, "E2E_TEST_SECRET", "")
        provided = request.headers.get("X-E2E-Token", "") or ""
        if not secret:
            raise NotFound("Resource not found")
        if not hmac.compare_digest(provided.encode("utf-8"), secret.encode("utf-8")):
            _e2e_logger.warning(
                "e2e_token_mismatch",
                extra={
                    "path": request.path,
                    "remote_addr": request.META.get("REMOTE_ADDR"),
                    "has_header": bool(provided),
                },
            )
            raise NotFound("Resource not found")
        return view_func(request, *args, **kwargs)

    wrapper._require_e2e_token = True  # type: ignore[attr-defined]  # monkey-patch on function wrapper; mypy can't see dynamic attrs
    return wrapper


class OpenAPISchemaView(SpectacularAPIView):
    """
    OpenAPI 3.0 schema generation endpoint.

    GET /api-docs/openapi.json
    GET /api/v1/openapi.json
    GET /api/v1/openapi.yaml

    Uses OpenApiJsonRenderer2 so Accept: application/json (e.g. from browser/axios)
    is satisfied; OpenApiJsonRenderer uses application/vnd.oai.openapi+json and
    causes 406 when clients send application/json.
    """

    # Prefer renderer that declares application/json so browser/axios Accept works
    _json_renderer = getattr(
        drf_spectacular.renderers,
        "OpenApiJsonRenderer2",
        drf_spectacular.renderers.OpenApiJsonRenderer,
    )
    renderer_classes = [_json_renderer]
    urlconf = "hub.urls"

    def perform_content_negotiation(self, request, force=False):
        """Accept application/json so browser/axios requests get 200, not 406."""
        accept = request.META.get("HTTP_ACCEPT", "") or ""
        if "application/json" in accept and self.renderer_classes:
            renderer = self.renderer_classes[0]()
            return (renderer, renderer.media_type)
        return super().perform_content_negotiation(request, force=force)

    def get(self, request, *args, **kwargs):
        """Return JSON format schema with validation and enhancement"""
        import structlog
        from drf_spectacular.generators import SchemaGenerator

        from .openapi_enhancement import OpenAPISpecEnhancer
        from .openapi_validation import OpenAPISpecValidator

        logger = structlog.get_logger(__name__)

        # Generate schema using the generator
        try:
            generator = SchemaGenerator(urlconf=self.urlconf)
            schema = generator.get_schema(request=request, public=True)
        except Exception as e:
            logger.warning("openapi_schema_generation_failed", error=str(e), exc_info=True)
            # Return minimal schema so capabilities/register/password-reset can load
            schema = {
                "openapi": "3.0.0",
                "info": {"title": getattr(settings, "APP_NAME", "Meshant"), "version": "1.0"},
                "paths": {
                    "/api/v1/auth/register/": {"post": {"operationId": "auth_register_create"}},
                    "/api/v1/auth/password-reset/": {
                        "post": {"operationId": "auth_password_reset_create"}
                    },
                    "/api/v1/auth/password-reset/confirm/": {
                        "post": {"operationId": "auth_password_reset_confirm_create"}
                    },
                    "/api/v1/auth/verify-email/": {
                        "post": {"operationId": "auth_verify_email_create"}
                    },
                    "/api/v1/auth/resend-verification/": {
                        "post": {"operationId": "auth_resend_verification_create"}
                    },
                },
            }

        # Validate schema
        is_valid, errors = OpenAPISpecValidator.validate_spec(schema)
        if not is_valid:
            logger.warning("openapi_spec_validation_errors", errors=errors)

        # Enhance schema with validation and additional documentation
        schema = OpenAPISpecValidator.enhance_spec(schema)
        try:
            schema = OpenAPISpecEnhancer.enhance_spec(schema)
        except Exception as enh_err:
            logger.warning(
                "openapi_enhancement_failed",
                error=str(enh_err),
                exc_info=True,
            )
            # Return schema without enhancement so capabilities can load

        # Check if YAML format requested
        format_type = request.query_params.get("format", "json")
        if format_type.lower() == "yaml":
            yaml_content = OpenAPISpecValidator.export_spec(schema, format="yaml")
            return Response(yaml_content, content_type="application/x-yaml")

        # Return JSON schema
        return Response(schema, content_type="application/json")


class OpenAPIYAMLView(SpectacularAPIView):
    """
    OpenAPI 3.0 schema generation endpoint (YAML format).

    GET /api/v1/openapi.yaml
    """

    renderer_classes = [drf_spectacular.renderers.OpenApiYamlRenderer]
    urlconf = "hub.urls"

    def get(self, request, *args, **kwargs):
        """Return YAML format schema with validation and enhancement"""
        import structlog
        from drf_spectacular.generators import SchemaGenerator

        from .openapi_enhancement import OpenAPISpecEnhancer
        from .openapi_validation import OpenAPISpecValidator

        logger = structlog.get_logger(__name__)

        # Generate schema using the generator
        try:
            generator = SchemaGenerator(urlconf=self.urlconf)
            schema = generator.get_schema(request=request, public=True)
        except Exception as e:
            logger.warning("openapi_schema_generation_failed", error=str(e), exc_info=True)
            schema = {
                "openapi": "3.0.0",
                "info": {"title": getattr(settings, "APP_NAME", "Meshant"), "version": "1.0"},
                "paths": {
                    "/api/v1/auth/register/": {"post": {"operationId": "auth_register_create"}},
                    "/api/v1/auth/password-reset/": {
                        "post": {"operationId": "auth_password_reset_create"}
                    },
                    "/api/v1/auth/password-reset/confirm/": {
                        "post": {"operationId": "auth_password_reset_confirm_create"}
                    },
                    "/api/v1/auth/verify-email/": {
                        "post": {"operationId": "auth_verify_email_create"}
                    },
                    "/api/v1/auth/resend-verification/": {
                        "post": {"operationId": "auth_resend_verification_create"}
                    },
                },
            }

        # Validate schema
        is_valid, errors = OpenAPISpecValidator.validate_spec(schema)
        if not is_valid:
            logger.warning("openapi_spec_validation_errors", errors=errors)

        # Enhance schema with validation and additional documentation
        schema = OpenAPISpecValidator.enhance_spec(schema)
        try:
            schema = OpenAPISpecEnhancer.enhance_spec(schema)
        except Exception as enh_err:
            logger.warning(
                "openapi_enhancement_failed",
                error=str(enh_err),
                exc_info=True,
            )

        # Export as YAML
        yaml_content = OpenAPISpecValidator.export_spec(schema, format="yaml")
        return Response(yaml_content, content_type="application/x-yaml")


class SwaggerUIView(SpectacularSwaggerView):
    """
    Enhanced Swagger UI documentation endpoint with comprehensive examples.

    GET /api-docs/

    Provides interactive API documentation using Swagger UI.

    Phase 221.4.2 — Requires authentication as defense-in-depth for
    staging/dev environments where the URL is registered.  In production,
    the URL is not registered at all (221.4.1).
    """

    permission_classes = [IsAuthenticated]
    urlconf = "hub.urls"

    def get(self, request, *args, **kwargs):
        """
        Return Swagger UI with enhanced configuration.

        The Swagger UI automatically loads the OpenAPI schema from the
        openapi-schema endpoint and provides interactive API exploration.
        """
        response = super().get(request, *args, **kwargs)
        return response


class ReDocView(SpectacularRedocView):
    """
    ReDoc documentation endpoint.

    GET /api-docs/redoc/

    Provides alternative API documentation using ReDoc.
    ReDoc offers a clean, three-panel documentation layout.

    Phase 221.4.2 — Requires authentication (same rationale as SwaggerUIView).
    """

    permission_classes = [IsAuthenticated]
    urlconf = "hub.urls"

    def get(self, request, *args, **kwargs):
        """
        Return ReDoc documentation.

        ReDoc automatically loads the OpenAPI schema and provides
        a clean, readable documentation interface.
        """
        response = super().get(request, *args, **kwargs)
        return response


class APIInfoSerializer(serializers.Serializer):
    """Serializer for API info endpoint"""

    name = serializers.CharField()
    version = serializers.CharField()
    base_url = serializers.CharField()
    documentation = serializers.DictField()
    endpoints = serializers.DictField()


# Phase 228 (REQ-LIN-006, 228.0.18) — capability discovery endpoint.


@extend_schema(
    responses={
        200: inline_serializer(
            name="CapabilitiesResponse",
            fields={
                "capabilities": serializers.DictField(
                    child=serializers.BooleanField(),
                    help_text=(
                        "Flat map of capability flag name → enabled. "
                        "Phase 228 ships five lineage flags; future "
                        "phases extend this map."
                    ),
                ),
            },
        ),
    },
    tags=["API"],
    description=(
        "Backend-driven feature-discovery surface. Frontends call this "
        "to branch UI on what the deployed backend supports. The flat "
        "shape lets the frontend's ``useCapability('lineage.<flag>')`` "
        "hook read by name without traversing nested objects."
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def capabilities_view(request):
    """``GET /api/v1/capabilities/`` — return the capability flag map.

    REQ-LIN-006: registered + queryable. Default policy:
    production/staging → all flags ``False``;
    test → all flags ``True``;
    Django settings ``CAPABILITY_FLAGS`` map overrides per flag.

    Phase 240.4.B.4 — uses ``get_capabilities_for_request`` so the
    response also carries the per-tenant Data Quality flags
    (``data_quality``, ``data_quality_advanced``) resolved from the
    authenticated user's tenant.  The SPA reads these to render menus
    without a separate "tenant features" round-trip.
    """
    from hub.apps.api.capabilities import get_capabilities_for_request

    return Response({"capabilities": get_capabilities_for_request(request)})


@extend_schema(responses={200: APIInfoSerializer}, tags=["API"])
@api_view(["GET"])
@permission_classes([AllowAny])
def api_info(request):
    """
    API information endpoint.

    GET /api/v1/
    Returns basic API information and available endpoints.
    """
    from .versioning import APIVersionManager

    # Get API version from request
    api_version = APIVersionManager.get_request_version(request)

    # Phase 221.4 — Only advertise api-docs URLs when they're registered
    # (non-production).  In production the /api-docs/* URLs return 404, so
    # listing them would create dead links and leak URL structure.
    docs = {"openapi_yaml": "/api/v1/openapi.yaml"}
    if settings.ENVIRONMENT != "production":
        docs.update(
            {
                "openapi": "/api-docs/openapi.json",
                "swagger": "/api-docs/",
                "redoc": "/api-docs/redoc/",
            }
        )

    # Collect deprecated endpoints for the version discovery response.
    deprecated = []
    for _key, dep in sorted(APIVersionManager.DEPRECATED_ENDPOINTS.items()):
        deprecated.append(
            {
                "path": dep.path,
                "method": dep.method,
                "deprecated_since": dep.deprecated_since,
                "sunset_date": dep.sunset_date,
                "replacement": dep.replacement,
                "migration_guide": dep.migration_guide,
            }
        )

    return Response(
        {
            "name": "Interoperable Data Hub API",
            "version": str(api_version),
            "current_version": str(APIVersionManager.CURRENT_VERSION),
            "supported_versions": [str(v) for v in APIVersionManager.SUPPORTED_VERSIONS],
            "base_url": "/api/v1",
            "documentation": docs,
            "links": {
                "openapi_schema": "/api/v1/openapi.yaml",
                "openapi_json": "/api-docs/openapi.json",
                "changelog": "/docs/api/changelog.md",
                "versioning_policy": "/docs/api/versioning.md",
            },
            "deprecated_endpoints": deprecated,
            "endpoints": {
                "auth": "/api/v1/auth/",
                "tenants": "/api/v1/tenants/",
                "users": "/api/v1/users/",
                "files": "/api/v1/files/",
                "datasets": "/api/v1/datasets/",
                "assets": "/api/v1/assets/",
                "contracts": "/api/v1/contracts/",
                "jobs": "/api/v1/jobs/",
                "dq": "/api/v1/dq/",
                "compliance": "/api/v1/compliance/",
                "semantic": "/api/v1/semantic/",
                "marketplace": "/api/v1/marketplace/",
                "audit": "/api/v1/audit/",
                "webhooks": "/api/v1/webhooks/",
                "analytics": "/api/v1/analytics/",
                "scheduled-ingestions": "/api/v1/scheduled-ingestions/",
                "scheduled-exports": "/api/v1/scheduled-exports/",
                "governance": "/api/v1/governance/",
                "billing": "/api/v1/billing/",
                "notifications": "/api/v1/notifications/",
                "capabilities": "/api/v1/capabilities/",
            },
        }
    )


# Apply throttle class via the view_class so DRF's WrappedAPIView picks it up.
# Setting throttle_classes on the handler directly does NOT propagate to the
# WrappedAPIView class that @api_view creates internally — view_class is the
# canonical attribute for this.
api_info.view_class.throttle_classes = [VersionDiscoveryRateThrottle]


@extend_schema(exclude=True, tags=["API"])  # Exclude from OpenAPI schema
@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def api_not_found(request):
    """
    Catch-all handler for non-existent API endpoints.

    This ensures all 404s within /api/v1/ return standardized error format.
    """
    raise NotFound("Resource not found")


# Must match ensure_e2e_user_roles.E2E_USERS and ensure_e2e_subscription.E2E_EMAILS
_PROFILE_E2E_EMAILS = tuple(
    f"e2e_profile_w{i}@example.com" for i in range(PROFILE_ISOLATION_WORKER_COUNT)
)
E2E_EMAILS = (
    "e2e_test@example.com",
    "e2e_consumer@example.com",
    "e2e_admin@example.com",
    "e2e_platform@example.com",
    "e2e_auditor@example.com",
    "e2e_cpo@example.com",
    "e2e_developer@example.com",
    "e2e_dmo@example.com",
) + _PROFILE_E2E_EMAILS


@extend_schema(exclude=True, tags=["API"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@require_e2e_token
def ensure_e2e_invitation_token(request):
    """
    E2E-only: Create an invited user and return invitation token for accept-invitation E2E.

    POST /api/v1/test/ensure-e2e-invitation-token/
    Only when ENVIRONMENT=test or DEBUG. For E2E test users. Returns {"token": "uuid"}.
    No mocks; real DB writes.
    """
    import uuid
    from datetime import timedelta

    from django.utils import timezone

    from hub.apps.users.models import User, UserStatus

    # Allow on test/debug AND staging — staging is gated by the E2E_EMAILS
    # allow-list (the real security boundary). Production is the only env where
    # this endpoint must remain a 404. Without staging, E2E tests against
    # https://stagingmeshant-internal.example.com cannot prime tenant subscriptions and any
    # write call (asset/dataset/contract POST) gets a 403 from billing middleware.
    if not (getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG):
        raise NotFound("Resource not found")
    if request.user.email not in E2E_EMAILS:
        raise NotFound("Resource not found")
    tenant = getattr(request.user, "tenant", None)
    if not tenant:
        return Response({"error": "no tenant"}, status=400)

    # ── Self-cleanup: delete stale INVITED users matching this endpoint's ──
    # ── email pattern to prevent unbounded orphan accumulation across     ──
    # ── test runs.  Users older than 1 h that were never accepted are    ──
    # ── safe to remove.                                                  ──
    _stale_cutoff = timezone.now() - timedelta(hours=1)
    User.objects.filter(
        email__startswith="e2e-invited-",
        email__endswith="@example.com",
        status=UserStatus.INVITED,
        created_at__lt=_stale_cutoff,
    ).delete()

    from hub.apps.auth.utils import sha256_hex

    email = f"e2e-invited-{uuid.uuid4().hex[:8]}@example.com"
    plaintext_token = str(uuid.uuid4())
    # Store the SHA-256 hash — accept_invitation looks up by hash (11.3)
    token_hash = sha256_hex(plaintext_token)
    User.objects.create_user(
        email=email,
        tenant=tenant,
        status=UserStatus.INVITED,
        invitation_token=token_hash,
        invitation_token_expires_at=timezone.now() + timedelta(days=7),
    )
    # Return the plaintext token — the frontend sends it, backend hashes it to look up
    return Response({"token": plaintext_token}, status=200)


@extend_schema(exclude=True, tags=["API"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@require_e2e_token
def ensure_e2e_subscription(request):
    """
    Ensure E2E test user's tenant has active subscription and VERIFIED KYC.

    Subscription enables writes; KYC enables marketplace publish. Only available
    when ENVIRONMENT=test or DEBUG=True. Only for E2E test user emails.
    """
    from django.conf import settings

    # Allow on test/debug AND staging — staging is gated by the E2E_EMAILS
    # allow-list (the real security boundary). Production is the only env where
    # this endpoint must remain a 404. Without staging, E2E tests against
    # https://stagingmeshant-internal.example.com cannot prime tenant subscriptions and any
    # write call (asset/dataset/contract POST) gets a 403 from billing middleware.
    if not (getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG):
        raise NotFound("Resource not found")
    if request.user.email not in E2E_EMAILS:
        raise NotFound("Resource not found")
    if not request.user.tenant_id:
        return Response({"ok": False, "error": "no tenant"}, status=400)
    from hub.apps.testing.billing_support import ensure_e2e_tenant_ready

    ensure_e2e_tenant_ready(request.user.tenant)
    return Response({"ok": True})


@extend_schema(exclude=True, tags=["API"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@require_e2e_token
def ensure_e2e_tenant_switch_setup(request):
    """
    E2E-only: Add current user to a second tenant for tenant-switch E2E.

    POST /api/v1/test/ensure-e2e-tenant-switch-setup/
    Creates a second tenant and UserTenantMembership. Returns {tenant_ids, secondary_tenant_id}.
    Only when ENVIRONMENT=test or DEBUG. For E2E test users.

    Runs inside ``transaction.atomic()`` so concurrent calls cannot create
    duplicate tenants or violate the membership unique constraint.
    """
    import uuid

    from django.db import IntegrityError, transaction

    from hub.apps.tenants.models import Tenant
    from hub.apps.users.models import UserTenantMembership
    from hub.apps.users.services import UserTenantMembershipService

    # Allow on test/debug AND staging — staging is gated by the E2E_EMAILS
    # allow-list (the real security boundary). Production is the only env where
    # this endpoint must remain a 404. Without staging, E2E tests against
    # https://stagingmeshant-internal.example.com cannot prime tenant subscriptions and any
    # write call (asset/dataset/contract POST) gets a 403 from billing middleware.
    if not (getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG):
        raise NotFound("Resource not found")
    if request.user.email not in E2E_EMAILS:
        raise NotFound("Resource not found")
    if not request.user.tenant_id:
        return Response({"error": "no tenant"}, status=400)

    # ── Resolve primary tenant ───────────────────────────────────────
    # request.user.tenant uses the FK manager which may filter soft-deleted
    # rows.  Fall back to the raw tenant_id + unfiltered queryset so a
    # soft-deleted primary tenant does not crash the endpoint with 500.
    try:
        primary = request.user.tenant
    except Tenant.DoesNotExist:
        primary = Tenant.all_objects.filter(id=request.user.tenant_id).first()
        if primary is None:
            return Response({"error": "primary tenant not found"}, status=400)

    with transaction.atomic():
        # Ensure primary tenant membership exists (E2E users may have
        # tenant_id but no UserTenantMembership).
        UserTenantMembershipService().add_membership(request.user, primary)

        # ── Look for an existing secondary tenant ────────────────────
        # Only consider memberships whose tenants are NOT soft-deleted.
        memberships = list(
            UserTenantMembership.objects.filter(user=request.user)
            .select_related("tenant")
            .order_by("created_at")
        )
        active_memberships = [
            m for m in memberships if m.tenant_id is not None and m.tenant.deleted_at is None
        ]

        # Find a secondary tenant that differs from the primary.
        for m in active_memberships:
            if str(m.tenant_id) != str(primary.id):
                return Response(
                    {
                        "tenant_ids": [str(primary.id), str(m.tenant_id)],
                        "primary_tenant_id": str(primary.id),
                        "primary_tenant_name": primary.name,
                        "secondary_tenant_id": str(m.tenant_id),
                        "secondary_tenant_name": m.tenant.name,
                    },
                    status=200,
                )

        # ── Create a new secondary tenant ───────────────────────────
        # Retry on slug collision (extremely rare with uuid4, but safe).
        for _retry in range(3):
            uid = uuid.uuid4().hex[:8]
            try:
                secondary = Tenant.objects.create(
                    name=f"E2E Switch Tenant {uid}",
                    slug=f"e2e-switch-{uid}",
                )
                break
            except IntegrityError:
                if _retry == 2:
                    raise
                continue

        UserTenantMembershipService().add_membership(request.user, secondary)
        return Response(
            {
                "tenant_ids": [str(primary.id), str(secondary.id)],
                "primary_tenant_id": str(primary.id),
                "primary_tenant_name": primary.name,
                "secondary_tenant_id": str(secondary.id),
                "secondary_tenant_name": secondary.name,
            },
            status=200,
        )


@extend_schema(exclude=True, tags=["API"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@require_e2e_token
def ensure_e2e_free_plan_tenant(request):
    """
    E2E-only: Create or return a tenant with the standard Free plan
    (max_assets=10) for quota-enforcement testing.

    POST /api/v1/test/ensure-e2e-free-plan-tenant/

    Returns ``{"tenant_id": "<uuid>", "tenant_name": "..."}``.  The
    caller uses ``X-Tenant-Id`` to scope asset creation to this tenant
    and verify that ``plan_limit_exceeded`` fires when the limit is hit.

    The endpoint is idempotent: subsequent calls return the same tenant.
    Old free-plan tenants (> 24 h) are cleaned up before creation.
    """
    import uuid
    from datetime import timedelta

    from django.utils import timezone as _tz

    from hub.apps.tenants.models import Tenant, TenantPlan
    from hub.apps.users.services import UserTenantMembershipService

    # ── Safety gates ─────────────────────────────────────────────────
    if not (getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG):
        raise NotFound("Resource not found")
    if request.user.email not in E2E_EMAILS:
        raise NotFound("Resource not found")

    # ── Clean up old free-plan tenants (> 24 h) ─────────────────────
    _old_cutoff = _tz.now() - timedelta(hours=24)
    Tenant.objects.filter(
        slug__startswith="e2e-free-plan-",
        created_at__lt=_old_cutoff,
    ).delete()

    # ── Return existing free-plan tenant if user already has one ─────
    from hub.apps.users.models import UserTenantMembership

    existing = (
        UserTenantMembership.objects.filter(
            user=request.user, tenant__slug__startswith="e2e-free-plan-"
        )
        .select_related("tenant")
        .order_by("created_at")
        .first()
    )
    if existing is not None:
        return Response(
            {"tenant_id": str(existing.tenant_id), "tenant_name": existing.tenant.name},
            status=200,
        )

    # ── Create a new tenant + assign Free plan ──────────────────────
    # Look up the standard Free plan (slug="free") from seed data.
    free_plan = TenantPlan.objects.filter(slug="free").first()
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"E2E Free Plan Tenant {uid}",
        slug=f"e2e-free-plan-{uid}",
    )
    if free_plan is not None:
        tenant.plan = free_plan
        tenant.save(update_fields=["plan"])

    UserTenantMembershipService().add_membership(request.user, tenant)

    # Use the existing E2E helper to create an active subscription
    # (handles Stripe IDs, period dates, and all required fields),
    # then override the plan to the standard Free plan so quota
    # enforcement is testable.
    from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

    ensure_tenant_has_active_subscription(tenant)

    # Override: the helper assigns e2e-unlimited; we need the Free plan
    # for quota testing (max_assets=10).
    if free_plan is not None:
        tenant.plan = free_plan
        tenant.save(update_fields=["plan"])

    return Response(
        {"tenant_id": str(tenant.id), "tenant_name": tenant.name},
        status=200,
    )


@extend_schema(exclude=True, tags=["API"])
@api_view(["POST"])
@permission_classes([AllowAny])
@require_e2e_token
def ensure_e2e_users(request):
    """
    E2E-only: Ensure E2E test users exist with correct passwords and roles.

    POST /api/v1/test/ensure-e2e-users/
    Calls the same logic as ``manage.py ensure_e2e_user_roles`` to create
    or reset E2E accounts.  AllowAny because the whole problem this solves
    is that users cannot log in (chicken-and-egg).

    Safety guards:
    - Only available when ENVIRONMENT in (test, staging) or DEBUG=True
    - Only processes hardcoded @example.com E2E addresses
    - Idempotent — safe to call on every test run

    Optional body: {"email": "e2e_test@example.com"} to process a single user.
    If omitted, processes all E2E users.
    """
    from django.db import transaction as db_transaction

    from hub.apps.tenants.models import Tenant, TenantStatus
    from hub.apps.users.management.commands.ensure_e2e_user_roles import (
        E2E_USERS,
        ROLE_DESCRIPTIONS,
    )
    from hub.apps.users.models import Role, User, UserRole, UserStatus

    if not (getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG):
        raise NotFound("Resource not found")

    target_email = request.data.get("email") if request.data else None

    if target_email:
        users_to_ensure = [u for u in E2E_USERS if u["email"] == target_email]
        if not users_to_ensure:
            return Response(
                {"ok": False, "error": f"Unknown E2E email: {target_email}"},
                status=400,
            )
    else:
        users_to_ensure = E2E_USERS

    processed = []
    with db_transaction.atomic():
        # Ensure all required tenants exist
        tenant_cache = {}
        for slug, name in [
            ("default", "Default Tenant"),
            ("consumer", "Consumer Tenant"),
            ("tenant-iso", "Isolation Test Tenant"),
            ("tenant-b", "Tenant-B Test Tenant"),
        ]:
            t, _ = Tenant.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "status": TenantStatus.ACTIVE},
            )
            # Ensure ml_enabled is True on the default tenant (idempotent update for pre-existing tenants).
            if slug == "default" and not t.ml_enabled:
                t.ml_enabled = True
                t.save(update_fields=["ml_enabled"])
            tenant_cache[slug] = t

        for spec in users_to_ensure:
            email = spec["email"]
            password = spec["password"]
            display_name = spec["display_name"]
            roles = spec.get("roles", [])
            is_pa = spec.get("is_platform_admin", False)
            tenant_slug = spec.get("tenant_slug", "default")
            tenant = tenant_cache.get(tenant_slug, tenant_cache["default"])

            user, _created = User.objects.get_or_create(
                email=email,
                defaults={
                    "tenant": tenant,
                    "display_name": display_name,
                    "status": UserStatus.ACTIVE,
                    "is_platform_admin": is_pa,
                },
            )

            # Sync password (always — the user may exist with wrong password)
            if not user.check_password(password):
                user.set_password(password)
                user.save(update_fields=["password"])

            # Ensure email verified
            if not getattr(user, "email_verified", False):
                from django.utils import timezone as _tz

                user.email_verified = True
                user.email_verified_at = _tz.now()
                user.save(update_fields=["email_verified", "email_verified_at"])

            # Ensure correct tenant
            if (tenant_slug == "consumer" and user.tenant_id != tenant.id) or not user.tenant_id:
                user.tenant = tenant
                user.save(update_fields=["tenant"])

            # Ensure platform admin flag
            if user.is_platform_admin != is_pa:
                user.is_platform_admin = is_pa
                user.save(update_fields=["is_platform_admin"])

            # Ensure status is ACTIVE
            if user.status != UserStatus.ACTIVE:
                user.status = UserStatus.ACTIVE
                user.save(update_fields=["status"])

            # Ensure tenant membership
            user_tenant = user.tenant or tenant
            if user_tenant:
                from hub.apps.users.services import UserTenantMembershipService

                UserTenantMembershipService().add_membership(
                    user,
                    user_tenant,
                )

            # Ensure roles
            for role_name in roles:
                role, _ = Role.objects.get_or_create(
                    tenant=user_tenant,
                    name=role_name,
                    defaults={
                        "description": ROLE_DESCRIPTIONS.get(role_name, role_name),
                    },
                )
                UserRole.objects.get_or_create(
                    user=user,
                    tenant=role.tenant,
                    role=role,
                )

            # Ensure tenant has a plan
            if user_tenant and not user_tenant.plan:
                from hub.apps.tenants.models import TenantPlan

                free_plan = TenantPlan.objects.filter(
                    slug="free",
                    is_active=True,
                ).first()
                if free_plan:
                    user_tenant.plan = free_plan
                    user_tenant.save(update_fields=["plan"])

            processed.append(email)

    return Response(
        {"ok": True, "users_processed": len(processed), "emails": processed},
        status=200,
    )


@extend_schema(exclude=True, tags=["API"])
@api_view(["POST"])
@permission_classes([AllowAny])
@require_e2e_token
def reset_e2e_auth_rate_limits(request):
    """
    E2E-only: clear the auth-category Redis rate-limit keys.

    POST /api/v1/test/reset-e2e-auth-rate-limits/

    The MVP test suite (287 tests, 1 worker, ~3 h on staging) cumulatively
    fires hundreds of /auth/login/ requests via UI form login + API login
    fallbacks. Staging's per-tenant auth rate limiter eventually trips with
    increasingly long retry-after windows (observed up to 3 h on the
    cycle-7 staging run), and there is no recovery path inside the test
    runner itself — the limiter blocks the very calls needed to authenticate.

    This endpoint mirrors ``manage.py reset_e2e_auth_rate_limits`` (which
    only works for local docker via ``docker exec``) but exposes the reset
    to the test runner over HTTP so external runs against staging can
    self-heal between suites without requiring kubectl access.

    Safety guards (in this order):
      1. ``@require_e2e_token`` rejects anything without the
         ``X-E2E-Token: <E2E_TEST_SECRET>`` header — the same shared-secret
         gate the other ``ensure_e2e_*`` endpoints use, so production has no
         way to invoke this even if it somehow got mounted.
      2. ``[AllowAny]`` is intentional and necessary — the entire problem
         this solves is that the test runner CANNOT authenticate (rate
         limit blocks /auth/login/). Demanding ``IsAuthenticated`` would
         create a chicken-and-egg lockout. Same justification as
         ``ensure_e2e_users`` above.
      3. ENVIRONMENT must be ``test`` / ``staging`` / DEBUG — production
         deployments return 404 like every other ``test/`` endpoint.

    Returns ``{"ok": True, "cleared": <count>, "pattern": <str>}`` so the
    caller can log how many keys were cleared (a non-zero count confirms
    the limiter was active; zero means the suite started in a clean state).
    """
    from django.conf import settings

    if not (getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG):
        raise NotFound("Resource not found")

    try:
        import redis

        from hub.apps.core.redis_pools import get_redis_cache_pool
        from hub.apps.core.rate_limiting.utils import EndpointCategory

        pool = get_redis_cache_pool()
        client = redis.Redis(connection_pool=pool, decode_responses=True)
    except Exception as exc:
        # Redis unavailable is a real platform incident, not a test bug.
        # Surface explicitly so the runner can decide whether to abort the
        # suite or continue with degraded conditions.
        return Response(
            {
                "ok": False,
                "error": "redis_unavailable",
                "detail": str(exc)[:300],
            },
            status=503,
        )

    pattern = f"*:{EndpointCategory.AUTH}:*"
    # `scan_iter` is non-blocking; safe under load. The number of auth
    # rate-limit keys is bounded by the number of distinct tenants/users
    # that have logged in within the limiter's window, so the iteration is
    # O(active-tenants), not O(all-redis-keys).
    keys = list(client.scan_iter(match=pattern))
    if keys:
        client.delete(*keys)
    return Response(
        {"ok": True, "cleared": len(keys), "pattern": pattern},
        status=200,
    )


@permission_classes([AllowAny])
@require_e2e_token
def raise_500(request):
    """
    E2E-only: deliberately raise an unhandled exception to produce a 500.

    GET /api/v1/test/raise-500/

    Used by the ``test_500_errors_do_not_contain_stack_traces`` security
    test to verify that 500 responses do not leak Python stack traces,
    file paths, or Django internals to the client.

    Safety guards (mirroring the other test/* endpoints):
      1. ``@require_e2e_token`` — rejects requests without the correct
         ``X-E2E-Token`` header (404 when secret is unset or mismatched).
      2. ``[AllowAny]`` — auth is irrelevant; the whole point is to
         exercise the 500 handler.
      3. ENVIRONMENT must be ``test`` / ``staging`` / DEBUG — production
         deployments return 404.
    """
    from django.conf import settings

    if not (getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG):
        raise NotFound("Resource not found")

    # Deliberate unhandled exception — this is the whole point of the
    # endpoint.  The 500 handler must sanitise the response.
    raise RuntimeError("Deliberate 500 raised by /test/raise-500/ for E2E error-redaction tests")
