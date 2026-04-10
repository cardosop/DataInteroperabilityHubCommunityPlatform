"""
API Views

Views for API documentation and OpenAPI schema generation.
"""

import drf_spectacular.renderers
import yaml
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from django.conf import settings

from hub.apps.users.management.commands.ensure_e2e_user_roles import (
    PROFILE_ISOLATION_WORKER_COUNT,
)


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
                    "/api/v1/auth/password-reset/": {"post": {"operationId": "auth_password_reset_create"}},
                    "/api/v1/auth/password-reset/confirm/": {
                        "post": {"operationId": "auth_password_reset_confirm_create"}
                    },
                    "/api/v1/auth/verify-email/": {"post": {"operationId": "auth_verify_email_create"}},
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
                    "/api/v1/auth/password-reset/": {"post": {"operationId": "auth_password_reset_create"}},
                    "/api/v1/auth/password-reset/confirm/": {
                        "post": {"operationId": "auth_password_reset_confirm_create"}
                    },
                    "/api/v1/auth/verify-email/": {"post": {"operationId": "auth_verify_email_create"}},
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
    """

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
    """

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

    return Response(
        {
            "name": "Interoperable Data Hub API",
            "version": str(api_version),
            "base_url": "/api/v1",
            "documentation": {
                "openapi": "/api-docs/openapi.json",
                "openapi_yaml": "/api/v1/openapi.yaml",
                "swagger": "/api-docs/",
                "redoc": "/api-docs/redoc/",
            },
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
            },
        }
    )


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
    if not (
        getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG
    ):
        raise NotFound("Resource not found")
    if request.user.email not in E2E_EMAILS:
        raise NotFound("Resource not found")
    tenant = getattr(request.user, "tenant", None)
    if not tenant:
        return Response({"error": "no tenant"}, status=400)

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
    if not (
        getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG
    ):
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
def ensure_e2e_tenant_switch_setup(request):
    """
    E2E-only: Add current user to a second tenant for tenant-switch E2E.

    POST /api/v1/test/ensure-e2e-tenant-switch-setup/
    Creates a second tenant and UserTenantMembership. Returns {tenant_ids, secondary_tenant_id}.
    Only when ENVIRONMENT=test or DEBUG. For E2E test users.
    """
    import uuid

    from hub.apps.tenants.models import Tenant
    from hub.apps.users.models import UserTenantMembership
    from hub.apps.users.services import UserTenantMembershipService

    # Allow on test/debug AND staging — staging is gated by the E2E_EMAILS
    # allow-list (the real security boundary). Production is the only env where
    # this endpoint must remain a 404. Without staging, E2E tests against
    # https://stagingmeshant-internal.example.com cannot prime tenant subscriptions and any
    # write call (asset/dataset/contract POST) gets a 403 from billing middleware.
    if not (
        getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG
    ):
        raise NotFound("Resource not found")
    if request.user.email not in E2E_EMAILS:
        raise NotFound("Resource not found")
    if not request.user.tenant_id:
        return Response({"error": "no tenant"}, status=400)

    primary = request.user.tenant
    # Ensure primary tenant membership exists (E2E users may have tenant_id but no UserTenantMembership)
    UserTenantMembershipService().add_membership(request.user, primary)
    memberships = list(
        UserTenantMembership.objects.filter(user=request.user)
        .values_list("tenant_id", flat=True)
        .order_by("created_at")
    )
    if len(memberships) >= 2:
        secondary_id = next((t for t in memberships if str(t) != str(primary.id)), memberships[1])
        secondary_tenant = Tenant.objects.get(id=secondary_id)
        return Response(
            {
                "tenant_ids": [str(primary.id), str(secondary_id)],
                "primary_tenant_id": str(primary.id),
                "primary_tenant_name": primary.name,
                "secondary_tenant_id": str(secondary_id),
                "secondary_tenant_name": secondary_tenant.name,
            },
            status=200,
        )

    uid = uuid.uuid4().hex[:8]
    secondary = Tenant.objects.create(
        name=f"E2E Switch Tenant {uid}",
        slug=f"e2e-switch-{uid}",
    )
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
@permission_classes([AllowAny])
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

    if not (
        getattr(settings, "ENVIRONMENT", "") in ("test", "staging") or settings.DEBUG
    ):
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
            tenant_cache[slug] = t

        for spec in users_to_ensure:
            email = spec["email"]
            password = spec["password"]
            display_name = spec["display_name"]
            roles = spec.get("roles", [])
            is_pa = spec.get("is_platform_admin", False)
            tenant_slug = spec.get("tenant_slug", "default")
            tenant = tenant_cache.get(tenant_slug, tenant_cache["default"])

            user, created = User.objects.get_or_create(
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
            if tenant_slug == "consumer" and user.tenant_id != tenant.id:
                user.tenant = tenant
                user.save(update_fields=["tenant"])
            elif not user.tenant_id:
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
                UserTenantMembershipService().add_membership(user, user_tenant)

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
                    user=user, tenant=role.tenant, role=role,
                )

            # Ensure tenant has a plan
            if user_tenant and not user_tenant.plan:
                from hub.apps.tenants.models import TenantPlan
                free_plan = TenantPlan.objects.filter(
                    slug="free", is_active=True,
                ).first()
                if free_plan:
                    user_tenant.plan = free_plan
                    user_tenant.save(update_fields=["plan"])

            processed.append(email)

    return Response(
        {"ok": True, "users_processed": len(processed), "emails": processed},
        status=200,
    )
