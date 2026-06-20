"""
E2E test-only ephemeral-tenant endpoint (Phase 226 OQ4).

Provisions a fresh, prefix-marked tenant with a single TENANT_ADMIN user so
E2E specs can exercise tenant-isolation flows (226.G14 cross-tenant 404
matrix, tenant-suspend tests) without polluting a shared static tenant.

Mirrors the gating posture of ``webhook_sink_views.py``:

  - Production lockout: 404 when ``settings.ENVIRONMENT`` is not in
    {test, staging} and ``DEBUG`` is False.
  - Token gate: requires the ``X-E2E-Token`` (or ``x-e2e-token``) header to
    match ``settings.E2E_TEST_SECRET`` via ``hmac.compare_digest``. Without
    a configured secret the endpoint 404s — production stays closed by
    default.

Cleanup is handled out-of-band by the staging-prefix-purge cron (226.E2):
the tenant slug carries the canonical ``e2e-`` prefix so the cron sweeps
leaks even if a test crashes mid-flight.
"""

from __future__ import annotations

import logging
import secrets
import uuid

from django.db import transaction
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from hub.apps.api.e2e_gating import is_e2e_environment, verify_e2e_token

logger = logging.getLogger(__name__)

# Tenant slug prefix — staging-prefix-purge (226.E2) sweeps anything that
# starts with this. Keep in sync with `scripts/staging_prefix_purge.cjs`.
EPHEMERAL_TENANT_PREFIX = "e2e-ephemeral-"

# Length of the random suffix appended to slugs/emails. 8 hex chars is
# 32 bits of entropy — collision probability is negligible at the tens-
# of-thousands-of-tenants scale this fixture supports per env.
RANDOM_SUFFIX_BYTES = 4

# Admin password length. 24 bytes urlsafe-base64 ~ 32 chars. The password
# is returned ONCE to the caller and never logged or persisted in plain text.
ADMIN_PASSWORD_BYTES = 24


def _build_unique_slug(suggested_name: str) -> str:
    """Build a guaranteed-unique tenant slug carrying the cleanup prefix.

    Pure helper — exposed for unit tests.
    """
    base = slugify(suggested_name or "tenant")[:40] or "tenant"
    suffix = secrets.token_hex(RANDOM_SUFFIX_BYTES)
    return f"{EPHEMERAL_TENANT_PREFIX}{base}-{suffix}"


def _build_admin_email(slug: str) -> str:
    """Build the admin user's email. Pure helper — exposed for unit tests."""
    return f"admin+{slug}@e2e.meshant.test"


@extend_schema(exclude=True, tags=["Tenants"])
@api_view(["POST"])
@permission_classes([AllowAny])
def ephemeral_tenant(request):
    """Provision an ephemeral tenant + admin user. Test-only.

    Path: ``/api/v1/tenants/ephemeral/``

    Request body (optional):
        ``{ "name": "<suggested name>", "label": "<spec label>" }``

    Response (201)::

        {
            "id":   "<tenant uuid>",
            "name": "<final tenant name>",
            "slug": "<e2e-ephemeral-...>",
            "admin_user": {
                "id":       "<user uuid>",
                "email":    "admin+...@e2e.meshant.test",
                "password": "<one-time plaintext>"
            }
        }
    """
    # Production lockout. Mirrors webhook_sink: closed-by-default. Both
    # gates share `hub.apps.api.e2e_gating` as their single source of truth.
    if not is_e2e_environment():
        raise NotFound("ephemeral tenant endpoint is not enabled in this environment")
    if not verify_e2e_token(request):
        # Same 404 on bad-secret as on missing-env so a probe cannot
        # distinguish "endpoint is mounted but you're unauthorized"
        # from "endpoint does not exist".
        raise NotFound("ephemeral tenant endpoint is not enabled in this environment")

    body = request.data if isinstance(request.data, dict) else {}
    suggested_name = (body.get("name") or "").strip() or f"e2e-tenant-{uuid.uuid4().hex[:8]}"
    label = (body.get("label") or "").strip() or "e2e"

    # Imports are local to keep import-time cost low for non-test envs
    # where this view is never invoked.
    from hub.apps.tenants.services import TenantService
    from hub.apps.users.models import Role, User, UserRole

    slug = _build_unique_slug(suggested_name)
    admin_email = _build_admin_email(slug)
    admin_password = secrets.token_urlsafe(ADMIN_PASSWORD_BYTES)

    try:
        with transaction.atomic():
            tenant = TenantService().create_tenant(
                name=f"{suggested_name}-{slug[-8:]}"[:255],
                slug=slug,
            )
            admin = User.objects.create_user(
                email=admin_email,
                password=admin_password,
                tenant=tenant,
                display_name=f"E2E Admin ({label})",
                status="ACTIVE",
                email_verified=True,
            )
            role, _ = Role.objects.get_or_create(
                tenant=tenant,
                name="TENANT_ADMIN",
                defaults={"description": "Auto-created for ephemeral tenant"},
            )
            UserRole.objects.get_or_create(user=admin, tenant=tenant, role=role)
    except Exception as exc:
        # Don't echo internal exception detail to the client (it's a test
        # endpoint but still talks to the network). Log full context.
        logger.exception("ephemeral_tenant: provisioning failed", extra={"slug": slug})
        return Response(
            {
                "detail": "ephemeral tenant provisioning failed",
                "error_class": exc.__class__.__name__,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "admin_user": {
                "id": str(admin.id),
                "email": admin.email,
                "password": admin_password,
            },
        },
        status=status.HTTP_201_CREATED,
    )
