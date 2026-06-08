"""
Phase 235.2 — PLATFORM_ADMIN tenant-create endpoint + orchestrator.

Mounts at ``POST /api/v1/admin/tenants/`` (registered in
``hub/apps/tenants/admin_urls.py``). Distinct from the self-service
``TenantOnboardingService.create_tenant_with_first_user`` orchestrator
on two axes:

1.  **Authorization** — PLATFORM_ADMIN-only (``IsPlatformAdmin``).
    The self-service surface authenticates the FUTURE admin user;
    this surface authenticates the OPERATOR who is provisioning the
    tenant FOR another organisation.
2.  **Initial-user provisioning** — instead of taking
    ``first_user_password`` and creating an ACTIVE user, this
    orchestrator creates an INVITED user with a 7-day-expiring
    ``invitation_token`` and schedules a welcome email via the
    existing ``send_invitation_email`` task. The invited admin sets
    their own password during invitation redemption.

Spec contract (REQ-ADMIN-TENANT-CREATE-001 in
``openspec/changes/preprod01/specs/admin-tenant-lifecycle/spec.md``):

> Accepts ``{slug, display_name, jurisdiction, admin_email}``.
> Validates slug uniqueness, jurisdiction validity (a key in the
> regulation_policies registry), and admin email format. On success,
> atomically creates Tenant + initial TenantConfig + TENANT_ADMIN
> invitation (sent via SES with 7-day expiry). Emits ``TENANT_CREATED``
> audit.
"""
from __future__ import annotations
import logging
import uuid
from datetime import timedelta
from typing import Any

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.utils import create_audit_event
from hub.apps.auth.utils import sha256_hex

from .models import KYCStatus, Tenant, TenantConfig, TenantStatus
from .permissions import IsPlatformAdmin
from .validators import VALID_COMPLIANCE_REGIMES, get_platform_defaults

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------


class AdminTenantCreateSerializer(serializers.Serializer):
    """Wire-shape for ``POST /api/v1/admin/tenants/``.

    All four fields are required; the wire contract is strict by
    design — operators provisioning a tenant for an external
    customer MUST commit to a jurisdiction up front so downstream
    compliance gates have an explicit regime to evaluate against.
    """

    slug = serializers.SlugField(
        max_length=255,
        help_text=(
            "URL-safe tenant identifier (lowercase letters, digits, hyphens, "
            "underscores). Must be unique across the platform — duplicates "
            "return HTTP 422 with code TENANT_SLUG_DUPLICATE."
        ),
    )
    display_name = serializers.CharField(
        max_length=255,
        min_length=1,
        help_text="Tenant's human-readable name (the ``Tenant.name`` column).",
    )
    jurisdiction = serializers.CharField(
        max_length=64,
        help_text=(
            "A regime key from "
            "``hub.apps.tenants.validators.VALID_COMPLIANCE_REGIMES`` (e.g. "
            "``GDPR``, ``LGPD``, ``CCPA``). Lands in "
            "``TenantConfig.default_compliance_regimes`` so downstream "
            "compliance gates evaluate this regime by default."
        ),
    )
    admin_email = serializers.EmailField(
        help_text=(
            "Email of the human who will be invited as the initial "
            "TENANT_ADMIN. The platform creates an INVITED user with a "
            "7-day-expiring invitation token; the invitee sets their own "
            "password on redemption."
        ),
    )
    # 285.13.12.7 — Plan selector: plan_name + tier + price surfaced
    # in the admin UI for the platform admin to pick at tenant creation.
    plan_slug = serializers.SlugField(
        max_length=255,
        required=False,
        default="free",
        help_text=(
            "Slug of the TenantPlan to assign to the new tenant. "
            "Defaults to 'free' (FREE tier, order=0). Available plans "
            "are returned by GET /api/v1/admin/available-plans/ with "
            "name, tier, and price_amount_cents."
        ),
    )

    def validate_slug(self, value: str) -> str:
        normalized = value.lower()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise serializers.ValidationError(
                "Slug must contain only lowercase letters, digits, hyphens, "
                "and underscores."
            )
        return normalized

    def validate_jurisdiction(self, value: str) -> str:
        normalized = value.upper().strip()
        if normalized not in VALID_COMPLIANCE_REGIMES:
            raise serializers.ValidationError(
                f"Unknown jurisdiction {value!r}. Valid keys: "
                f"{', '.join(sorted(VALID_COMPLIANCE_REGIMES))}"
            )
        return normalized

    def validate_admin_email(self, value: str) -> str:
        # EmailField already validates RFC 5322; this is a thin
        # belt-and-braces check so a malformed email never reaches
        # the User row (where uniqueness + NOT NULL would otherwise
        # 500).
        try:
            validate_email(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _generate_invitation_token() -> tuple[str, str]:
    """Generate a (plaintext, sha256_hex) invitation token pair.

    The plaintext token goes into the invitation email URL; the
    hashed form is stored in ``User.invitation_token`` (so a
    database breach doesn't expose live invitation links). Same
    construction as
    :func:`hub.apps.users.views.UserViewSet.create`'s invitation flow.
    """
    plaintext = str(uuid.uuid4())
    return plaintext, sha256_hex(plaintext)


@transaction.atomic
def create_tenant_with_admin_invitation(
    *,
    slug: str,
    display_name: str,
    jurisdiction: str,
    admin_email: str,
    created_by,
    request=None,
    plan_slug: str = "free",
) -> dict[str, Any]:
    """Atomically create Tenant + TenantConfig + invited TENANT_ADMIN.

    Side effects (all within a single ``transaction.atomic`` block —
    a failure on ANY step rolls back the whole creation):

    1.  ``Tenant.objects.create`` with ``status=ACTIVE``,
        ``kyc_status=UNVERIFIED``, ``name=display_name``, ``slug=slug``,
        ``plan=resolved_plan`` (285.13.12.7).
    2.  ``TenantConfig.objects.create`` with platform defaults
        (:func:`get_platform_defaults`) AND the operator-chosen
        ``jurisdiction`` recorded in ``default_compliance_regimes`` so
        downstream compliance gates see it on the first request.
    3.  ``Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")``
        — the ``post_save`` signal on Tenant creates the four default
        roles, so this is usually a no-op fetch; ``get_or_create``
        defends against a future signal-handler change.
    4.  ``User.objects.create_user(email=admin_email, ...)`` with
        ``status=INVITED``, ``invitation_token = sha256_hex(plaintext_uuid)``,
        ``invitation_token_expires_at = now + 7 days``.
    5.  ``UserRole.objects.create(user=invited, role=tenant_admin_role)``.
    6.  ``TENANT_CREATED`` audit event (action constant from
        ``hub.apps.audit.event_types``).
    7.  Welcome-email task scheduled via ``transaction.on_commit`` so
        the task fires AFTER the DB commit — if anything above
        raises, the task is never enqueued (the on_commit callbacks
        only fire on a successful atomic-block exit).

    Raises
    ------
    ``django.db.IntegrityError`` if the slug collides — the caller
    translates this into HTTP 422 with code TENANT_SLUG_DUPLICATE.
    ``serializers.ValidationError`` if ``plan_slug`` doesn't resolve.

    Returns
    -------
    A dict ``{tenant, admin_user, plaintext_invitation_token}`` —
    the caller serialises ``tenant`` + ``admin_user`` for the
    response body; the plaintext token is NEVER returned to the
    client (it's only used to enqueue the email task).
    """
    from hub.apps.tenants.models import TenantPlan
    from hub.apps.users.models import Role, User, UserRole, UserStatus

    # 0. Resolve plan (285.13.12.7) — default to "free" if unspecified.
    plan = TenantPlan.objects.filter(slug=plan_slug, is_active=True).first()
    if plan is None and plan_slug != "free":
        raise serializers.ValidationError(
            f"Plan '{plan_slug}' not found or inactive."
        )
    if plan is None:
        plan = TenantPlan.objects.filter(
            tier="FREE", is_active=True, order=0,
        ).first()

    # 1. Tenant.
    tenant = Tenant.objects.create(
        name=display_name,
        slug=slug,
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        plan=plan,
    )

    # 2. TenantConfig with platform defaults + operator jurisdiction.
    platform_defaults = get_platform_defaults()
    # If the platform default list is empty, we use [jurisdiction] alone.
    # If it already lists multiple regimes, ensure ours is included
    # (deduped) so the operator's intent isn't dropped.
    default_regimes = list(
        platform_defaults.get("default_compliance_regimes") or []
    )
    if jurisdiction not in default_regimes:
        default_regimes.append(jurisdiction)
    # ``allowed_compliance_regimes`` MUST be a SUPERSET of
    # ``default_compliance_regimes`` — this is the TenantConfig
    # invariant pinned in TenantConfigSerializer's validate hook.
    #
    # Phase 235.2 audit-fix Gap 2 — defend against a misconfigured
    # platform default that ships ``default`` containing regimes
    # NOT present in ``allowed``. We:
    #   1. Start from the platform's allowed list.
    #   2. Add the operator-chosen jurisdiction.
    #   3. UNION every regime from ``default`` so the superset
    #      invariant holds regardless of the platform-default state.
    # ``dict.fromkeys(...)`` is the order-preserving dedupe (cheaper
    # than ``set(...)`` followed by ``sorted(...)`` and keeps the
    # platform-curated ordering for the lead regimes).
    allowed_regimes = list(platform_defaults.get("allowed_compliance_regimes") or [])
    if jurisdiction not in allowed_regimes:
        allowed_regimes.append(jurisdiction)
    allowed_regimes = list(dict.fromkeys(allowed_regimes + default_regimes))
    TenantConfig.objects.create(
        tenant=tenant,
        default_dq_profile=platform_defaults.get("default_dq_profile"),
        allowed_compliance_regimes=allowed_regimes,
        default_compliance_regimes=default_regimes,
        data_retention_days=platform_defaults.get("data_retention_days"),
        rate_limits=platform_defaults.get("rate_limits", {}),
        max_file_size_bytes=platform_defaults.get("max_file_size_bytes"),
        max_job_concurrency=platform_defaults.get("max_job_concurrency"),
        max_queued_jobs=platform_defaults.get("max_queued_jobs"),
    )

    # 3. TENANT_ADMIN role (the post_save signal usually has created
    # this already; get_or_create is defense in depth against future
    # signal refactors).
    tenant_admin_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="TENANT_ADMIN",
        defaults={"description": "Tenant administrator with full access"},
    )

    # 4. Invited user. The freshly-created user has NO password — the
    # invitee sets one during invitation redemption. We set the
    # invitation token here rather than relying on a downstream
    # signal so the email task can pass the plaintext token to the
    # URL builder.
    #
    # Phase 235.2 audit-fix Gap 3 — consolidate the User INSERT and
    # the invitation-token UPDATE into ONE INSERT via the
    # ``UserManager.create_user(**extra_fields)`` shape. The earlier
    # two-write pattern (INSERT then save(update_fields=...)) cost
    # an extra round-trip per provisioning request and meant a
    # mid-flight crash between the two writes would have left a
    # User row with a token-less ``invitation_token``. One write =
    # the half-baked state is no longer reachable.
    plaintext_token, hashed_token = _generate_invitation_token()
    invited = User.objects.create_user(
        email=admin_email,
        password=None,  # invitee sets their own on redemption
        tenant=tenant,
        display_name=admin_email.split("@")[0],
        status=UserStatus.INVITED,
        invitation_token=hashed_token,
        invitation_token_expires_at=timezone.now() + timedelta(days=7),
    )

    # 5. Bind invited user to TENANT_ADMIN role.
    UserRole.objects.create(user=invited, role=tenant_admin_role)

    # 6. Audit emission. The actor_user is the PLATFORM_ADMIN who
    # issued the request (the writer), NOT the invited user — they
    # haven't accepted yet. Both UUIDs are recorded in details_json.
    create_audit_event(
        resource_type="TENANT",
        action=_audit_et.TENANT_CREATED,
        actor_user=created_by,
        tenant=tenant,
        resource_id=str(tenant.id),
        result="SUCCESS",
        details={
            "slug": tenant.slug,
            "display_name": tenant.name,
            "jurisdiction": jurisdiction,
            "admin_email": admin_email,
            "admin_user_id": str(invited.id),
            "created_by": str(created_by.id) if created_by else None,
            "plan_slug": plan.slug if plan else None,
            "plan_tier": plan.tier if plan else None,
            "plan_price_cents": plan.price_amount_cents if plan else 0,
        },
        request=request,
        infer_tenant_from_actor=False,
    )

    # 7. Schedule welcome email AFTER commit (on_commit fires only
    # on a successful atomic-block exit; a rollback above means the
    # callback is never enqueued, so we don't email an invitee for
    # a tenant that doesn't exist).
    invited_user_id = str(invited.id)

    def _enqueue_invitation_email() -> None:
        from hub.apps.notifications.tasks import send_invitation_email

        try:
            send_invitation_email.delay(
                invited_user_id, plaintext_token=plaintext_token
            )
        except Exception as exc:  # pragma: no cover — Redis-outage path
            logger.warning(
                "admin_tenant_create_invitation_email_enqueue_failed",
                extra={
                    "user_id": invited_user_id,
                    "tenant_slug": tenant.slug,
                    "error": str(exc),
                },
            )

    transaction.on_commit(_enqueue_invitation_email)

    return {
        "tenant": tenant,
        "admin_user": invited,
        "plaintext_invitation_token": plaintext_token,
    }


# ---------------------------------------------------------------------------
# DRF view
# ---------------------------------------------------------------------------


class AdminTenantCreateView(APIView):
    """PLATFORM_ADMIN endpoint for provisioning a new tenant."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    @extend_schema(
        operation_id="admin_tenant_create",
        summary="Provision a new tenant + TENANT_ADMIN invitation",
        description=(
            "Atomically creates a ``Tenant`` (status=ACTIVE, "
            "kyc_status=UNVERIFIED), a paired ``TenantConfig`` with "
            "platform defaults + the operator-chosen ``jurisdiction`` "
            "in ``default_compliance_regimes``, a ``TENANT_ADMIN`` "
            "``Role`` (if not auto-created by signal), and an INVITED "
            "``User`` with a 7-day-expiring invitation token. Schedules "
            "the invitation email via ``send_invitation_email`` on "
            "transaction commit. Emits ``TENANT_CREATED`` audit."
        ),
        request=AdminTenantCreateSerializer,
        responses={
            201: OpenApiResponse(
                description=(
                    "Tenant + invited admin created. Response carries "
                    "``tenant`` (id, slug, name, status, kyc_status, "
                    "plan: {name, tier, price_amount_cents}, created_at) "
                    "and ``admin_user`` (id, email, status, "
                    "invitation_expires_at). 285.13.12.7 — plan selector."
                ),
            ),
            400: OpenApiResponse(
                description=(
                    "Validation error — slug format invalid, unknown "
                    "jurisdiction, malformed admin_email, etc."
                ),
            ),
            401: OpenApiResponse(
                description="Unauthorized — missing or invalid bearer token.",
            ),
            403: OpenApiResponse(
                description="Forbidden — caller is not a PLATFORM_ADMIN.",
            ),
            422: OpenApiResponse(
                description=(
                    "Unprocessable. ``code=TENANT_SLUG_DUPLICATE`` when "
                    "the slug already exists; ``code=ADMIN_EMAIL_DUPLICATE`` "
                    "when the admin email already maps to a user."
                ),
            ),
        },
        tags=["Admin"],
    )
    def post(self, request):
        serializer = AdminTenantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        try:
            result = create_tenant_with_admin_invitation(
                slug=validated["slug"],
                display_name=validated["display_name"],
                jurisdiction=validated["jurisdiction"],
                admin_email=validated["admin_email"],
                created_by=request.user,
                request=request,
                plan_slug=validated.get("plan_slug", "free"),
            )
        except IntegrityError:
            # Phase 235.2 audit-fix Gap 1 — disambiguate slug-vs-email
            # collisions by RE-QUERYING the live DB rather than
            # pattern-matching the Postgres error text. The earlier
            # ``"slug" in str(exc).lower()`` heuristic was fragile in
            # three ways:
            #   1.  psycopg2 / psycopg3 produce slightly different
            #       error message formats.
            #   2.  Localised Postgres builds (``lc_messages != "en"``)
            #       can omit column names from the readable text.
            #   3.  A non-collision IntegrityError (e.g. a FK violation
            #       on a yet-uncreated child) would also be silently
            #       translated into a misleading 422.
            #
            # The atomic block ALREADY rolled back by the time control
            # reaches this except clause, so ``Tenant.objects.filter(
            # slug=...).exists()`` only matches rows that PRE-EXIST
            # this request. Same for the email.
            from hub.apps.users.models import User as _User

            if Tenant.objects.filter(slug=validated["slug"]).exists():
                return Response(
                    {
                        "code": "TENANT_SLUG_DUPLICATE",
                        "detail": (
                            f"A tenant with slug {validated['slug']!r} "
                            "already exists."
                        ),
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            if _User.objects.filter(email=validated["admin_email"]).exists():
                return Response(
                    {
                        "code": "ADMIN_EMAIL_DUPLICATE",
                        "detail": (
                            f"A user with email {validated['admin_email']!r} "
                            "already exists."
                        ),
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            # Truly unexpected IntegrityError — re-raise so DRF's
            # default 500 handler surfaces it (and ops sees the
            # stack trace) rather than silently masking the bug
            # behind one of the two well-known 422 codes.
            raise

        tenant = result["tenant"]
        admin_user = result["admin_user"]
        assigned_plan = tenant.plan
        return Response(
            {
                "tenant": {
                    "id": str(tenant.id),
                    "slug": tenant.slug,
                    "name": tenant.name,
                    "status": tenant.status,
                    "kyc_status": tenant.kyc_status,
                    "plan": {
                        "name": assigned_plan.name if assigned_plan else None,
                        "tier": assigned_plan.tier if assigned_plan else None,
                        "price_amount_cents": assigned_plan.price_amount_cents if assigned_plan else 0,
                    },
                    "created_at": tenant.created_at.isoformat()
                    if tenant.created_at
                    else None,
                },
                "admin_user": {
                    "id": str(admin_user.id),
                    "email": admin_user.email,
                    "status": admin_user.status,
                    "invitation_expires_at": (
                        admin_user.invitation_token_expires_at.isoformat()
                        if admin_user.invitation_token_expires_at
                        else None
                    ),
                },
            },
            status=status.HTTP_201_CREATED,
        )
