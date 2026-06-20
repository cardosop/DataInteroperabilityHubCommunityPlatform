"""
Phase 235.4 — PLATFORM_ADMIN impersonation endpoints (start + exit).

Mounts at:

* ``POST /api/v1/admin/impersonate/``      — open a new session.
* ``POST /api/v1/admin/impersonate/exit/`` — end an existing session.

Contract (REQ-ADMIN-IMPERSONATION-001 in
``openspec/changes/preprod01/specs/admin-impersonation/spec.md``):

1.  PLATFORM_ADMIN-only via ``IsPlatformAdmin``.
2.  Target tenant MUST have ``impersonation_allowed=True`` —
    rejection emits ``IMPERSONATION_REJECTED`` audit + HTTP 403
    ``IMPERSONATION_NOT_ENABLED``.
3.  Target user MUST NOT carry the PLATFORM_ADMIN role —
    rejection emits ``IMPERSONATION_REJECTED`` audit + HTTP 422
    ``TARGET_IS_PLATFORM_ADMIN``. Distinct from the
    ``impersonation_allowed`` rejection so dashboards can surface
    "operator-attempted-cross-PA" separately.
4.  Target user MUST be ACTIVE — DISABLED / INVITED → HTTP 422
    ``TARGET_INACTIVE``.
5.  ``max_minutes`` defaults to the tenant's
    ``impersonation_default_max_minutes`` (60); hard cap is 240
    (4 hours). Out-of-range values → HTTP 400
    ``MAX_MINUTES_OUT_OF_RANGE``.
6.  Happy path creates ``ImpersonationSession`` + emits
    ``IMPERSONATION_STARTED`` in BOTH tenants (target + impersonator
    home) + schedules an email to the impersonated user + returns
    a short-lived JWT carrying the ``impersonation_session_id``
    claim (TTL = ``max_minutes * 60`` seconds).

Race-protection contract
========================

The session-create + audit emit + JWT mint happen inside ONE
``transaction.atomic`` block. A subsequent ``POST /exit/`` calls
``session.end(reason="manual_exit")`` under a ``select_for_update``
row lock so a concurrent operator-driven exit + cron-driven
expiration cannot race; the second caller observes ``status=ENDED``
and 409s out via ``ALREADY_ENDED``.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.utils import create_audit_event
from hub.apps.auth.jwt_utils import JWTTokenGenerator

from .models import (
    ImpersonationSession,
    ImpersonationSessionStatus,
    Tenant,
)
from .permissions import IsPlatformAdmin


class IsPlatformAdminOrActiveImpersonator(permissions.BasePermission):
    """Phase 235.4 — exit-endpoint permission.

    A live impersonation session can be ended by EITHER:

    * a PLATFORM_ADMIN authenticated via their regular cookie/Bearer
      session (e.g. incident-response force-end on another operator's
      runaway session), OR
    * the operator who STARTED the session, authenticating with the
      impersonation JWT itself — the JWT's ``impersonation_session_id``
      claim is cryptographic proof the bearer is the holder of the
      session.

    The active-impersonator path is essential because the SPA's
    common-case flow swaps the operator's Bearer to the impersonation
    JWT immediately after start (so subsequent /api/* calls run AS the
    impersonated user). Without this permission, the operator could
    not call ``/exit/`` until they manually re-authenticated as
    themselves — the banner Exit button would 403 every time.

    The view body still validates that the claim matches the
    body's ``session_id`` (defence-in-depth: an attacker holding a
    DIFFERENT session's JWT cannot use it to end an unrelated
    session).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_platform_admin", False):
            return True
        # Tagged by ImpersonationMiddleware when the JWT carried a
        # valid ACTIVE-session claim.
        return bool(getattr(request, "impersonation_session_id", None))


logger = logging.getLogger(__name__)

#: Hard cap on impersonation session duration, regardless of the
#: tenant's ``impersonation_default_max_minutes`` value or the
#: operator's request override. 240 minutes (4 hours) is enough for a
#: long support call but short enough that an inadvertently-left-open
#: session expires before it can be picked up by a rotating shift.
IMPERSONATION_MAX_MINUTES_CAP: int = 240

#: Floor on max_minutes — a 0-minute session is meaningless and a
#: 1-minute session is virtually unusable. The floor doesn't try to
#: be clever about reasonable lower bounds; 5 just keeps the wire
#: input from being trivially abused.
IMPERSONATION_MIN_MINUTES: int = 5


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


class ImpersonationStartSerializer(serializers.Serializer):
    """Wire-shape for ``POST /api/v1/admin/impersonate/``."""

    user_id = serializers.UUIDField(
        help_text="The target user UUID to impersonate.",
    )
    reason = serializers.CharField(
        min_length=10,
        max_length=2000,
        help_text=(
            "Operator justification (min 10 chars). Pinned in the audit "
            "trail so an auditor can read WHY the session was opened."
        ),
    )
    max_minutes = serializers.IntegerField(
        required=False,
        help_text=(
            "Override the tenant's default duration cap. When omitted, the "
            "tenant's ``impersonation_default_max_minutes`` is used. Out-of-"
            "range values return HTTP 400 MAX_MINUTES_OUT_OF_RANGE."
        ),
    )


class ImpersonationExitSerializer(serializers.Serializer):
    """Wire-shape for ``POST /api/v1/admin/impersonate/exit/``."""

    session_id = serializers.UUIDField(
        help_text="UUID of the ImpersonationSession to end.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_has_platform_admin_role(user) -> bool:
    """Best-effort check for PLATFORM_ADMIN role on a user.

    Mirrors the role-detection logic used in
    ``JWTTokenGenerator.generate_access_token`` (the ``is_platform_admin``
    flag is the canonical source of truth; the role-name fallback
    catches an out-of-band PLATFORM_ADMIN UserRole binding that
    pre-dates the flag).
    """
    if getattr(user, "is_platform_admin", False):
        return True
    if not hasattr(user, "user_roles"):
        return False
    try:
        return user.user_roles.filter(role__name="PLATFORM_ADMIN").exists()
    except Exception:
        return False


def _user_is_active_for_impersonation(user) -> bool:
    """Return True iff the user is in a state that can be impersonated.

    A DISABLED / INVITED user cannot log in themselves, so impersonating
    them would let the operator perform actions the user could not
    legitimately perform. The capability surface is for SUPPORT, not
    for unilateral action on behalf of a never-onboarded subject.
    """
    from hub.apps.users.models import UserStatus

    status_value = getattr(user, "status", None)
    if status_value is None:
        return True  # Legacy users without status are treated as ACTIVE.
    return status_value == UserStatus.ACTIVE


# ---------------------------------------------------------------------------
# Start endpoint
# ---------------------------------------------------------------------------


class AdminImpersonateStartView(APIView):
    """PLATFORM_ADMIN endpoint to begin a new impersonation session."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    @extend_schema(
        operation_id="admin_impersonate_start",
        summary="Start a PLATFORM_ADMIN impersonation session",
        description=(
            "Opens a new impersonation session against ``user_id``. "
            "Returns a short-lived JWT (TTL = max_minutes × 60 seconds, "
            "hard cap 240 min) carrying the ``impersonation_session_id`` "
            "claim. Emits ``IMPERSONATION_STARTED`` audit rows in BOTH "
            "the impersonated user's tenant AND the impersonator's home "
            "tenant; schedules a courtesy email to the impersonated user."
        ),
        request=ImpersonationStartSerializer,
        responses={
            201: OpenApiResponse(
                description=(
                    "Session created. Response body carries ``session`` "
                    "metadata + ``access_token`` (the short-lived JWT)."
                ),
            ),
            400: OpenApiResponse(
                description=(
                    "Bad request. ``code=MAX_MINUTES_OUT_OF_RANGE`` when "
                    "max_minutes is outside [5, 240]."
                ),
            ),
            401: OpenApiResponse(
                description="Unauthorized — missing or invalid bearer token.",
            ),
            403: OpenApiResponse(
                description=(
                    "Forbidden. ``code=IMPERSONATION_NOT_ENABLED`` when the "
                    "target tenant has not opted in (``Tenant."
                    "impersonation_allowed=False``). Also returned when "
                    "the caller is not a PLATFORM_ADMIN."
                ),
            ),
            404: OpenApiResponse(description="Target user not found."),
            422: OpenApiResponse(
                description=(
                    "Unprocessable. Codes: ``TARGET_IS_PLATFORM_ADMIN`` "
                    "(cannot impersonate another platform admin), "
                    "``TARGET_INACTIVE`` (user is DISABLED / INVITED), "
                    "``TARGET_HAS_NO_TENANT`` (target user has no home "
                    "tenant to anchor the session against)."
                ),
            ),
        },
        tags=["Admin"],
    )
    def post(self, request):
        serializer = ImpersonationStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        from hub.apps.users.models import User

        try:
            target = User.objects.select_related("tenant").get(pk=validated["user_id"])
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        target_tenant = target.tenant
        if target_tenant is None:
            # PLATFORM-only users (no home tenant) — they live outside
            # the tenant-scoped surface, so impersonating them has no
            # tenant context to anchor the session row against.
            return Response(
                {
                    "code": "TARGET_HAS_NO_TENANT",
                    "detail": "User has no home tenant; cannot impersonate.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        reason = validated["reason"]

        # --- Rejection gate 1: tenant must have opted in. --------------
        if not target_tenant.impersonation_allowed:
            self._emit_rejection_audit(
                request=request,
                impersonator=request.user,
                target=target,
                target_tenant=target_tenant,
                code="IMPERSONATION_NOT_ENABLED",
                reason=reason,
            )
            return Response(
                {
                    "code": "IMPERSONATION_NOT_ENABLED",
                    "detail": (
                        f"Tenant {target_tenant.slug!r} has not opted in to "
                        "impersonation. Set ``impersonation_allowed=True`` "
                        "on the tenant before retrying."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # --- Rejection gate 2: cross-PA impersonation forbidden. -------
        if _user_has_platform_admin_role(target):
            self._emit_rejection_audit(
                request=request,
                impersonator=request.user,
                target=target,
                target_tenant=target_tenant,
                code="TARGET_IS_PLATFORM_ADMIN",
                reason=reason,
            )
            return Response(
                {
                    "code": "TARGET_IS_PLATFORM_ADMIN",
                    "detail": (
                        "Cannot impersonate a PLATFORM_ADMIN — the role "
                        "transcends tenant boundaries; impersonation would "
                        "blur the actor / effective_user audit trail."
                    ),
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # --- Rejection gate 3: target must be ACTIVE. ------------------
        if not _user_is_active_for_impersonation(target):
            self._emit_rejection_audit(
                request=request,
                impersonator=request.user,
                target=target,
                target_tenant=target_tenant,
                code="TARGET_INACTIVE",
                reason=reason,
            )
            return Response(
                {
                    "code": "TARGET_INACTIVE",
                    "detail": (
                        "Target user is not ACTIVE; cannot impersonate a "
                        "disabled or unaccepted-invite user."
                    ),
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # --- Validate max_minutes. ------------------------------------
        max_minutes = validated.get("max_minutes")
        if max_minutes is None:
            max_minutes = target_tenant.impersonation_default_max_minutes
        if max_minutes < IMPERSONATION_MIN_MINUTES or max_minutes > IMPERSONATION_MAX_MINUTES_CAP:
            return Response(
                {
                    "code": "MAX_MINUTES_OUT_OF_RANGE",
                    "detail": (
                        f"max_minutes must be between {IMPERSONATION_MIN_MINUTES} "
                        f"and {IMPERSONATION_MAX_MINUTES_CAP}; received "
                        f"{max_minutes}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Happy path. ----------------------------------------------
        now = timezone.now()
        expires_at = now + timedelta(minutes=max_minutes)
        impersonator = request.user
        impersonator_tenant = getattr(impersonator, "tenant", None)

        # Write the session through the DEFAULT connection so that FK
        # references to ``users`` (impersonator, impersonated_user) and
        # ``tenants`` resolve within the same transaction.  The RLS
        # policy on ``impersonation_sessions`` is satisfied because a
        # PLATFORM_ADMIN writing from their home tenant context is
        # explicitly allowed by the policy's USING clause.
        with transaction.atomic(using="default"):
            sess = ImpersonationSession.objects.create(
                impersonator=impersonator,
                impersonated_user=target,
                impersonator_tenant=impersonator_tenant,
                impersonated_tenant=target_tenant,
                started_at=now,
                expires_at=expires_at,
                max_minutes=max_minutes,
                reason=reason,
            )
            common_details = {
                "impersonation_session_id": str(sess.id),
                "impersonator_user_id": str(impersonator.id),
                "impersonated_user_id": str(target.id),
                "impersonator_tenant_id": (
                    str(impersonator_tenant.id) if impersonator_tenant else None
                ),
                "impersonated_tenant_id": str(target_tenant.id),
                "max_minutes": max_minutes,
                "expires_at": expires_at.isoformat(),
                "reason": reason,
            }
            # Audit row #1 — under the target tenant (auditor-facing).
            create_audit_event(
                resource_type="IMPERSONATION_SESSION",
                action=_audit_et.IMPERSONATION_STARTED,
                actor_user=impersonator,
                tenant=target_tenant,
                resource_id=str(sess.id),
                result="SUCCESS",
                details=common_details,
                request=request,
                infer_tenant_from_actor=False,
            )
            # Audit row #2 — under the impersonator's home tenant
            # (security-team-facing). Skip if the impersonator has no
            # home tenant — the row would be tenant=NULL which is the
            # platform-level surface; a duplicate of the target-tenant
            # row would only add noise.
            if impersonator_tenant is not None and impersonator_tenant.id != target_tenant.id:
                create_audit_event(
                    resource_type="IMPERSONATION_SESSION",
                    action=_audit_et.IMPERSONATION_STARTED,
                    actor_user=impersonator,
                    tenant=impersonator_tenant,
                    resource_id=str(sess.id),
                    result="SUCCESS",
                    details=common_details,
                    request=request,
                    infer_tenant_from_actor=False,
                )

            # Schedule the courtesy email AFTER commit so a rollback
            # above means no email goes out for a session that didn't
            # actually start.
            session_id = str(sess.id)

            def _enqueue_email() -> None:
                from hub.apps.notifications.tasks import (
                    send_impersonation_started_email,
                )

                try:
                    send_impersonation_started_email.delay(session_id=session_id)
                except Exception as exc:  # pragma: no cover — Redis-outage path
                    logger.warning(
                        "impersonation_email_enqueue_failed",
                        extra={
                            "session_id": session_id,
                            "error": str(exc),
                        },
                    )

            transaction.on_commit(_enqueue_email)

        # Mint the short-lived JWT AS the target user (so the SPA
        # carries the impersonated user's claims) but stamped with
        # the impersonation_session_id claim so middleware can
        # disambiguate actor vs effective_user on every request.
        ttl_seconds = max_minutes * 60
        access_token = JWTTokenGenerator.generate_access_token(
            target,
            tenant_id=str(target_tenant.id),
            impersonation_session_id=str(sess.id),
            ttl_seconds=ttl_seconds,
        )

        return Response(
            {
                "session": {
                    "id": str(sess.id),
                    "impersonator_user_id": str(impersonator.id),
                    "impersonated_user_id": str(target.id),
                    "impersonator_tenant_id": (
                        str(impersonator_tenant.id) if impersonator_tenant else None
                    ),
                    "impersonated_tenant_id": str(target_tenant.id),
                    "started_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "max_minutes": max_minutes,
                    "status": sess.status,
                },
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": ttl_seconds,
            },
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _emit_rejection_audit(
        *,
        request,
        impersonator,
        target,
        target_tenant: Tenant,
        code: str,
        reason: str,
    ) -> None:
        """Emit one ``IMPERSONATION_REJECTED`` row under the target tenant.

        The row carries enough context for an auditor to reconstruct
        what was attempted; we deliberately do NOT also write a row
        under the impersonator's home tenant for rejections — the
        rejection is a non-event from the target tenant's
        perspective, and one row per rejection keeps the audit feed
        from being flooded by a misconfigured operator's repeated
        attempts.
        """
        try:
            create_audit_event(
                resource_type="IMPERSONATION_SESSION",
                action=_audit_et.IMPERSONATION_REJECTED,
                actor_user=impersonator,
                tenant=target_tenant,
                resource_id=None,
                result="FAILURE",
                details={
                    "code": code,
                    "impersonator_user_id": str(impersonator.id),
                    "impersonated_user_id": str(target.id),
                    "impersonated_tenant_id": str(target_tenant.id),
                    "reason": reason,
                },
                request=request,
                infer_tenant_from_actor=False,
            )
        except Exception:  # pragma: no cover — audit-write is best-effort
            logger.exception(
                "impersonation_rejection_audit_emit_failed",
                extra={"code": code, "target_user_id": str(target.id)},
            )


# ---------------------------------------------------------------------------
# Exit endpoint
# ---------------------------------------------------------------------------


class AdminImpersonateExitView(APIView):
    """PLATFORM_ADMIN endpoint to end an active impersonation session.

    Permission contract (audit-fix Gap 2)
    =====================================
    Accepts EITHER a PLATFORM_ADMIN (regular cookie/Bearer session —
    force-end path for incident response) OR a request authenticated
    via the impersonation JWT itself (the common-case banner Exit
    flow, where ``request.user`` is the impersonated user but
    ``request.impersonation_session_id`` is set by
    ``ImpersonationMiddleware`` to the operator's session UUID).

    The view body validates that the claim matches the request
    body's ``session_id`` so an attacker holding a different
    impersonation JWT cannot use it to end an unrelated session.

    Idempotency contract
    ====================
    Re-calling exit on an already-ENDED session returns HTTP 409 +
    ``ALREADY_ENDED`` so a double-click on the SPA banner's Exit
    button surfaces a stable error instead of a misleading 200.

    Race protection
    ===============
    The session lookup uses ``select_for_update`` so a concurrent
    cron-driven expire sweep cannot race the exit and produce
    duplicate ``IMPERSONATION_ENDED`` audit events. The cron's
    ``skip_locked=True`` shape makes it back off cleanly when the
    exit endpoint holds the row.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsPlatformAdminOrActiveImpersonator,
    ]

    @extend_schema(
        operation_id="admin_impersonate_exit",
        summary="End an active impersonation session",
        description=(
            "Ends a live impersonation session. Accepts EITHER a "
            "PLATFORM_ADMIN's regular cookie/Bearer session (force-end "
            "path) OR an impersonation JWT whose claim matches the "
            "``session_id`` in the request body (banner Exit button "
            "path). Emits ``IMPERSONATION_ENDED`` with "
            "``end_reason=manual_exit`` + the actual clicker's UUID in "
            "``details_json.ended_by_user_id``. Idempotent: a second "
            "exit on an already-ENDED session returns HTTP 409."
        ),
        request=ImpersonationExitSerializer,
        responses={
            200: OpenApiResponse(
                description="Session ended successfully.",
            ),
            401: OpenApiResponse(
                description="Unauthorized — missing or invalid bearer token.",
            ),
            403: OpenApiResponse(
                description=(
                    "Forbidden. Caller is neither a PLATFORM_ADMIN nor "
                    "the holder of an active impersonation JWT matching "
                    "the body's ``session_id``. The defence-in-depth "
                    "``SESSION_ID_MISMATCH`` code triggers when the "
                    "impersonation JWT's claim references a different "
                    "session than the body asks to end."
                ),
            ),
            404: OpenApiResponse(description="Impersonation session not found."),
            409: OpenApiResponse(
                description=(
                    "Conflict. ``code=ALREADY_ENDED`` — the session "
                    "is already in ENDED status (idempotent contract)."
                ),
            ),
        },
        tags=["Admin"],
    )
    def post(self, request):
        serializer = ImpersonationExitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        session_id = validated["session_id"]

        # Defence-in-depth: if the caller is NOT a PLATFORM_ADMIN, the
        # impersonation JWT they presented MUST be for the same session
        # they are trying to end. The permission class already vetted
        # that SOME active session is in play; this check binds the
        # caller's session to the body's session.
        if not getattr(request.user, "is_platform_admin", False):
            jwt_session_id = getattr(request, "impersonation_session_id", None)
            if jwt_session_id is None or str(jwt_session_id) != str(session_id):
                return Response(
                    {
                        "code": "SESSION_ID_MISMATCH",
                        "detail": (
                            "The impersonation JWT used to authenticate "
                            "this request is bound to a different session. "
                            "Re-authenticate as PLATFORM_ADMIN to force-end "
                            "another operator's session."
                        ),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # PLATFORM_ADMIN write path — route through the ``admin``
        # BYPASSRLS connection so the SELECT FOR UPDATE + UPDATE on
        # ``impersonation_sessions`` does not trip the RLS policy
        # whose USING clause requires ``current_tenant_id`` to match
        # ``impersonated_tenant_id``. The operator (PLATFORM_ADMIN)
        # may have no tenant context or a different home tenant.
        with transaction.atomic(using="admin"):
            try:
                sess = (
                    ImpersonationSession.objects.using("admin")
                    .select_for_update()
                    .select_related("impersonated_tenant", "impersonator_tenant")
                    .get(pk=session_id)
                )
            except ImpersonationSession.DoesNotExist:
                return Response(
                    {"detail": "Impersonation session not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if sess.status == ImpersonationSessionStatus.ENDED:
                return Response(
                    {
                        "code": "ALREADY_ENDED",
                        "detail": (
                            f"Session is already ENDED "
                            f"(end_reason={sess.end_reason!r}, "
                            f"ended_at={sess.ended_at.isoformat() if sess.ended_at else None})."
                        ),
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # ``sess`` was loaded from ``admin``; ``sess.save`` will
            # reuse the same alias via ``_state.db`` so the UPDATE
            # also bypasses RLS. Same contract as the start endpoint.
            sess.end(reason="manual_exit")

            # The actor on the audit row is the IMPERSONATOR (the
            # operator who is exiting their own session), NOT the
            # impersonated user — even though request.user is the
            # impersonated user when the call arrives via the
            # impersonation JWT path. Resolve the impersonator from
            # the session row to keep the audit trail correct.
            audit_actor = sess.impersonator if sess.impersonator else request.user

            create_audit_event(
                resource_type="IMPERSONATION_SESSION",
                action=_audit_et.IMPERSONATION_ENDED,
                actor_user=audit_actor,
                tenant=sess.impersonated_tenant,
                resource_id=str(sess.id),
                result="SUCCESS",
                details={
                    "impersonation_session_id": str(sess.id),
                    "impersonator_user_id": str(sess.impersonator_id),
                    "impersonated_user_id": str(sess.impersonated_user_id),
                    "impersonator_tenant_id": (
                        str(sess.impersonator_tenant_id) if sess.impersonator_tenant_id else None
                    ),
                    "impersonated_tenant_id": str(sess.impersonated_tenant_id),
                    "end_reason": sess.end_reason,
                    "started_at": sess.started_at.isoformat(),
                    "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
                    # Capture WHO ended it — a PLATFORM_ADMIN
                    # force-end (different from the impersonator)
                    # shows up here as a distinct actor from the
                    # session's original impersonator.
                    "ended_by_user_id": str(request.user.id),
                },
                request=request,
                infer_tenant_from_actor=False,
            )

        return Response(
            {
                "session": {
                    "id": str(sess.id),
                    "status": sess.status,
                    "end_reason": sess.end_reason,
                    "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
                },
            },
            status=status.HTTP_200_OK,
        )
