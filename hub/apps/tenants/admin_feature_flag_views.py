"""
Phase 235.1 — PLATFORM_ADMIN per-tenant feature-flag API surface.

Two endpoints land here (mounted at ``/api/v1/admin/...`` via
``hub/apps/tenants/urls.py``):

* ``GET /api/v1/admin/tenants/{id}/feature-flags/``  — read every
  registry-tracked flag's current value + metadata. Drives the
  ``FeatureFlagPage.tsx`` tabular UI (rows = tenants, columns =
  flags) — adding a flag to the registry auto-renders.
* ``PUT /api/v1/admin/tenants/{id}/feature-flags/`` — partial
  update of one or more flags + a min-10-char ``reason``. Sensitive
  flags (``sensitive=True`` in the registry) DO NOT flip; they
  open a ``FeatureFlagFlipApproval`` row in ``PENDING`` status
  and a SECOND PLATFORM_ADMIN must approve via
  ``POST /api/v1/admin/feature-flag-approvals/{id}/approve/``.

The approval endpoint is the second view in this module
(``FeatureFlagFlipApprovalApproveView``); it enforces the
two-person rule by rejecting self-approval with HTTP 403
``SELF_APPROVAL_FORBIDDEN``.

Audit emission:

* Non-sensitive flip                  → ``TENANT_FEATURE_FLAG_CHANGED``
* Sensitive flip (request phase)      → ``FEATURE_FLAG_FLIP_APPROVAL_REQUESTED``
* Sensitive flip (approve phase)      → ``FEATURE_FLAG_FLIP_APPROVED``
                                        + ``TENANT_FEATURE_FLAG_CHANGED``

Rate limit: 60 flips per PLATFORM_ADMIN per hour
(:func:`hub.apps.tenants.admin_flag_flip_rate_limit.check_flag_flip_rate_limit`).
The rate-limit check runs BEFORE any flag-state mutation so a 429
returns without leaving partial state.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.utils import create_audit_event

from .admin_flag_flip_rate_limit import (
    FLAG_FLIP_LIMIT_PER_HOUR,
    check_flag_flip_rate_limit,
)
from .feature_flag_registry import REGISTRY, get_flag, is_sensitive
from .models import (
    FeatureFlagFlipApproval,
    FeatureFlagFlipApprovalStatus,
    Tenant,
)
from .permissions import IsPlatformAdmin

logger = logging.getLogger(__name__)

#: The shared minimum-length constraint on the ``reason`` field —
#: pinned by the test suite and the spec (REQ-ADMIN-FLAGS-001).
_REASON_MIN_LENGTH: int = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_flag_row(flag, *, current_value: bool) -> dict[str, Any]:
    """Serialize one registry entry + the tenant's current value.

    The shape is consumed verbatim by ``FeatureFlagPage.tsx`` — any
    field change here needs a matching frontend update.
    """
    return {
        "name": flag.name,
        "description": flag.description,
        "stage": flag.stage,
        "sensitive": flag.sensitive,
        "owner_team": flag.owner_team,
        "related_phase": flag.related_phase,
        "default_existing_tenants": flag.default_existing_tenants,
        "default_new_tenants": flag.default_new_tenants,
        "current_value": current_value,
    }


def _validate_reason(reason: Any) -> str | None:
    """Return None if valid, else the validation error message."""
    if not isinstance(reason, str):
        return "reason is required"
    stripped = reason.strip()
    if len(stripped) < _REASON_MIN_LENGTH:
        return f"reason must be at least {_REASON_MIN_LENGTH} characters (got {len(stripped)})"
    return None


def _emit_changed_event(
    *,
    tenant: Tenant,
    flag: str,
    old_value: bool,
    new_value: bool,
    reason: str,
    requested_by,
    approver,
    approval_id: str | None,
    request,
    actor=None,
) -> None:
    """Emit the canonical ``TENANT_FEATURE_FLAG_CHANGED`` audit row.

    The ``approver`` is the same as ``requested_by`` on non-sensitive
    flips; on sensitive flips it's the second admin who approved.
    ``approval_id`` is only populated for sensitive flips and links
    the row to the matching ``FEATURE_FLAG_FLIP_APPROVED`` event.

    ``actor`` (Phase 235.1 audit-fix Gap 3) is the user whose action
    physically persisted the flip (the DB-write actor). Defaults to
    ``requested_by`` for backwards compatibility with the
    immediate-flip path where the requester IS the writer. The
    approve-path passes ``actor=request.user`` (the second admin)
    so the audit event's top-level ``actor_user_id`` column reflects
    the standard "who did this DB write" semantic. Both UUIDs are
    duplicated into ``details_json.{requested_by, approver}`` so
    audit-replay can reconstruct the full two-person-rule transition
    regardless of which field it indexes on.
    """
    if actor is None:
        actor = requested_by
    create_audit_event(
        resource_type="TENANT",
        action=_audit_et.TENANT_FEATURE_FLAG_CHANGED,
        actor_user=actor,
        tenant=tenant,
        resource_id=str(tenant.id),
        result="SUCCESS",
        details={
            "flag": flag,
            "old_value": bool(old_value),
            "new_value": bool(new_value),
            "reason": reason,
            "requested_by": str(requested_by.id) if requested_by else None,
            "approver": str(approver.id) if approver else None,
            "approval_id": approval_id,
            "tenant_id": str(tenant.id),
        },
        request=request,
        infer_tenant_from_actor=False,
    )


# ---------------------------------------------------------------------------
# GET / PUT /api/v1/admin/tenants/{tenant_id}/feature-flags/
# ---------------------------------------------------------------------------


class AdminTenantFeatureFlagView(APIView):
    """PLATFORM_ADMIN endpoint for reading + flipping one tenant's flags."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    # GET ----------------------------------------------------------------

    @extend_schema(
        operation_id="admin_tenant_feature_flags_list",
        summary="List every registry-tracked feature flag for a tenant",
        description=(
            "Returns every flag in the platform's feature-flag registry "
            "with the tenant's current value + the flag's metadata "
            "(stage, sensitivity, owner team, related phase, rollout "
            "defaults). Drives the SPA's ``FeatureFlagPage.tsx`` tabular "
            "view. Also lists any PENDING ``FeatureFlagFlipApproval`` "
            "rows so the SPA can render the two-person-rule queue."
        ),
        responses={
            200: OpenApiResponse(
                description=("Returns ``{tenant_id, flags[], pending_approvals[]}``."),
            ),
            401: OpenApiResponse(description="Unauthorized."),
            403: OpenApiResponse(description="Forbidden — not a PLATFORM_ADMIN."),
            404: OpenApiResponse(description="Tenant not found."),
        },
        tags=["Admin"],
    )
    def get(self, request, tenant_id):
        tenant = get_object_or_404(Tenant.all_objects.using("admin"), pk=tenant_id)
        flags = [
            _serialize_flag_row(f, current_value=bool(getattr(tenant, f.name, False)))
            for f in REGISTRY
        ]
        # Surface pending approvals so the SPA can render "Awaiting
        # second admin" state next to the toggle row.
        pending = list(
            FeatureFlagFlipApproval.objects.using("admin")
            .filter(
                tenant_id=tenant.id,
                status=FeatureFlagFlipApprovalStatus.PENDING,
            )
            .values("id", "flag", "requested_value", "requested_by_id", "requested_at")
        )
        return Response(
            {
                "tenant_id": str(tenant.id),
                "flags": flags,
                "pending_approvals": [
                    {
                        "id": str(p["id"]),
                        "flag": p["flag"],
                        "requested_value": p["requested_value"],
                        "requested_by_id": str(p["requested_by_id"]),
                        "requested_at": p["requested_at"].isoformat()
                        if p["requested_at"]
                        else None,
                    }
                    for p in pending
                ],
            },
            status=status.HTTP_200_OK,
        )

    # PUT ----------------------------------------------------------------

    @extend_schema(
        operation_id="admin_tenant_feature_flags_update",
        summary="Flip one or more feature flags on a tenant",
        description=(
            "Partial-update of one or more flag values + a min-10-char "
            "``reason``. The backend decides per flag (via the "
            "``sensitive`` field on the registry entry) whether the flip "
            "lands directly OR opens a ``FeatureFlagFlipApproval`` row "
            "that a SECOND PLATFORM_ADMIN must approve via "
            "``POST /api/v1/admin/feature-flag-approvals/{id}/approve/``. "
            "Per-admin rate-limit: 60 flips/hour."
        ),
        request={
            "application/json": {
                "type": "object",
                "required": ["reason"],
                "properties": {
                    "reason": {
                        "type": "string",
                        "minLength": 10,
                        "description": (
                            "Operator justification (min 10 chars). "
                            "Pinned in the audit row's ``details_json.reason``."
                        ),
                    },
                },
                "additionalProperties": {
                    "type": "boolean",
                    "description": (
                        "Any registry-tracked flag name as key, boolean "
                        "value as the desired new state."
                    ),
                },
            },
        },
        responses={
            200: OpenApiResponse(
                description=(
                    "All requested flips were non-sensitive AND landed "
                    "directly. Response: ``{applied[], pending_approvals: "
                    "[], rate_limit_observed, rate_limit_bucket}``."
                ),
            ),
            202: OpenApiResponse(
                description=(
                    "At least one sensitive flip awaits a second-admin "
                    "approval. Response shape same as 200; "
                    "``pending_approvals[]`` carries the new approval "
                    "row UUIDs."
                ),
            ),
            400: OpenApiResponse(
                description=(
                    "Validation error — missing/short ``reason``, unknown flag name, etc."
                ),
            ),
            401: OpenApiResponse(description="Unauthorized."),
            403: OpenApiResponse(description="Forbidden — not a PLATFORM_ADMIN."),
            404: OpenApiResponse(description="Tenant not found."),
            429: OpenApiResponse(
                description=(
                    "Rate-limit exceeded — caller has already issued "
                    "60 flip requests in the current hour bucket. "
                    "Response carries ``rate_limit_observed`` reflecting "
                    "the current bucket count."
                ),
            ),
        },
        tags=["Admin"],
    )
    def put(self, request, tenant_id):
        payload = request.data or {}
        reason_error = _validate_reason(payload.get("reason"))
        if reason_error is not None:
            return Response(
                {"reason": [reason_error]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = payload["reason"].strip()

        # Identify the flags the request wants to flip.
        #
        # Phase 235.1 audit-fix Gap 1 — DO NOT coerce via ``bool(v)``.
        # The previous version did ``{k: bool(v) for k, v in ...}`` which
        # silently converted the string ``"false"`` (truthy in Python)
        # to ``True``, flipping the flag in the OPPOSITE direction the
        # operator clearly intended. The JSON contract requires the
        # value be a real JSON boolean (``true``/``false`` → Python
        # ``bool``); any other type — strings, ints, None, lists — is
        # an operator error worth surfacing as 400 rather than
        # rewriting at the server.
        flag_updates: dict[str, bool] = {}
        non_bool_keys: list[str] = []
        for k, v in payload.items():
            if k == "reason":
                continue
            if isinstance(v, bool):
                flag_updates[k] = v
            else:
                non_bool_keys.append(k)
        if non_bool_keys:
            return Response(
                {
                    "detail": (
                        "Flag values MUST be JSON booleans "
                        "(true / false). Got non-boolean values for: "
                        f"{', '.join(sorted(non_bool_keys))}."
                    ),
                    "non_boolean_flags": sorted(non_bool_keys),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not flag_updates:
            return Response(
                {"detail": "At least one flag update is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Reject unknown flag names BEFORE any rate-limit / state mutation.
        unknown = [name for name in flag_updates if get_flag(name) is None]
        if unknown:
            return Response(
                {
                    "detail": (
                        f"Unknown feature flag(s): {', '.join(sorted(unknown))}. "
                        "Add the flag to hub/apps/tenants/feature_flag_registry.py first."
                    ),
                    "unknown_flags": sorted(unknown),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rate-limit check BEFORE any side effect.
        allowed, observed, retry_after, bucket = check_flag_flip_rate_limit(actor=request.user)
        if not allowed:
            resp = Response(
                {
                    "detail": (
                        f"Rate limit exceeded ({FLAG_FLIP_LIMIT_PER_HOUR} flips "
                        "per PLATFORM_ADMIN per hour)."
                    ),
                    "observed": observed,
                    "limit": FLAG_FLIP_LIMIT_PER_HOUR,
                    "retry_after_seconds": retry_after,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            resp.headers["Retry-After"] = str(retry_after)
            return resp

        tenant = get_object_or_404(Tenant.all_objects.using("admin"), pk=tenant_id)

        # Split the requested flips into sensitive (two-person rule)
        # vs. non-sensitive (immediate). Process both classes inside
        # ONE atomic transaction so a partial failure rolls back the
        # entire request.
        immediate_flips: list[tuple[str, bool, bool]] = []
        sensitive_flips: list[tuple[str, bool, bool]] = []
        for name, new_value in flag_updates.items():
            old_value = bool(getattr(tenant, name, False))
            if old_value == new_value:
                # No-op flips are accepted (audit-empty) so the
                # SPA's optimistic-toggle UX doesn't 400 on a
                # debounce-reposted same-value.
                continue
            if is_sensitive(name):
                sensitive_flips.append((name, old_value, new_value))
            else:
                immediate_flips.append((name, old_value, new_value))

        with transaction.atomic(using="admin"):
            # Non-sensitive: flip + audit in one shot.
            for name, old, new in immediate_flips:
                setattr(tenant, name, new)
            if immediate_flips:
                # ``updated_at`` is part of the Tenant model schema
                # (line 208 of models.py, ``auto_now=True``). Passing
                # it explicitly in ``update_fields`` is required for
                # auto_now to fire on partial saves.
                tenant.save(update_fields=[name for name, _, _ in immediate_flips] + ["updated_at"])
                for name, old, new in immediate_flips:
                    _emit_changed_event(
                        tenant=tenant,
                        flag=name,
                        old_value=old,
                        new_value=new,
                        reason=reason,
                        requested_by=request.user,
                        approver=request.user,  # non-sensitive: self-approver
                        approval_id=None,
                        request=request,
                    )

            # Sensitive: open approval rows + emit REQUESTED audit.
            pending_rows: list[FeatureFlagFlipApproval] = []
            for name, old, new in sensitive_flips:
                approval = FeatureFlagFlipApproval.objects.create(
                    tenant=tenant,
                    flag=name,
                    requested_value=new,
                    requested_by=request.user,
                    reason=reason,
                )
                pending_rows.append(approval)
                create_audit_event(
                    resource_type="FEATURE_FLAG_FLIP_APPROVAL",
                    action=_audit_et.FEATURE_FLAG_FLIP_APPROVAL_REQUESTED,
                    actor_user=request.user,
                    tenant=tenant,
                    resource_id=str(approval.id),
                    result="SUCCESS",
                    details={
                        "flag": name,
                        "requested_value": new,
                        "reason": reason,
                        "requested_by": str(request.user.id),
                        "approval_id": str(approval.id),
                        "tenant_id": str(tenant.id),
                    },
                    request=request,
                    infer_tenant_from_actor=False,
                )

        # Response shape:
        # * 202 when at least one sensitive flag awaits approval —
        #   the SPA shows the "Requires 2nd approval" pending state.
        # * 200 when only non-sensitive flips happened.
        if pending_rows:
            resp_status = status.HTTP_202_ACCEPTED
        else:
            resp_status = status.HTTP_200_OK
        return Response(
            {
                "applied": [
                    {"flag": name, "old_value": old, "new_value": new}
                    for name, old, new in immediate_flips
                ],
                "pending_approvals": [
                    {
                        "id": str(p.id),
                        "flag": p.flag,
                        "requested_value": p.requested_value,
                    }
                    for p in pending_rows
                ],
                "rate_limit_observed": observed,
                "rate_limit_bucket": bucket,
            },
            status=resp_status,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/admin/feature-flag-approvals/{id}/approve/
# ---------------------------------------------------------------------------


class FeatureFlagFlipApprovalApproveView(APIView):
    """PLATFORM_ADMIN endpoint for completing a sensitive flag flip.

    The two-person rule (REQ-ADMIN-FLAGS-002) is enforced here: the
    approving admin MUST be different from the requesting admin.
    Self-approval returns HTTP 403 with the error code
    ``SELF_APPROVAL_FORBIDDEN``.

    On successful approval:

    1. The approval row transitions to ``APPROVED`` with
       ``approved_by`` + ``approved_at`` set (via
       :meth:`FeatureFlagFlipApproval.mark_approved`).
    2. The matching ``Tenant.<flag>`` value flips to
       ``requested_value`` — same atomic transaction as step 1.
    3. ``FEATURE_FLAG_FLIP_APPROVED`` audit event is emitted.
    4. ``TENANT_FEATURE_FLAG_CHANGED`` audit event is emitted with
       ``approver`` set to the second admin's UUID (this is the
       single canonical "the flag changed" event — non-sensitive
       and sensitive flips both produce one).
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    @extend_schema(
        operation_id="admin_feature_flag_flip_approval_approve",
        summary="Approve a pending sensitive feature-flag flip (two-person rule)",
        description=(
            "Marks a ``FeatureFlagFlipApproval`` row as APPROVED + "
            "atomically flips the target tenant's flag inside one "
            "``transaction.atomic(using='admin')``. Emits both "
            "``FEATURE_FLAG_FLIP_APPROVED`` AND "
            "``TENANT_FEATURE_FLAG_CHANGED`` linked by ``approval_id``. "
            "Self-approval is rejected at two layers (model guard + API "
            "permission) — the same PLATFORM_ADMIN who opened the "
            "request CANNOT approve it."
        ),
        request=None,
        responses={
            200: OpenApiResponse(
                description=(
                    "Approval succeeded + flag flipped. Response carries "
                    "the approval row's new state and the flipped flag."
                ),
            ),
            401: OpenApiResponse(description="Unauthorized."),
            403: OpenApiResponse(
                description=(
                    "Forbidden. ``code=SELF_APPROVAL_FORBIDDEN`` when "
                    "the caller is the same PLATFORM_ADMIN who opened "
                    "the request — the two-person-rule's load-bearing "
                    "invariant."
                ),
            ),
            404: OpenApiResponse(description="Approval row not found."),
            409: OpenApiResponse(
                description=(
                    "Conflict. The approval row is no longer in PENDING "
                    "status (already APPROVED, REJECTED, or EXPIRED)."
                ),
            ),
        },
        tags=["Admin"],
    )
    def post(self, request, approval_id):
        # Phase 235.1 audit-fix Gap 2 — wrap the lookup + state-check +
        # transition in ONE ``transaction.atomic(using="admin")`` block
        # with ``select_for_update()`` so two PLATFORM_ADMINs clicking
        # Approve simultaneously can't both flip the flag and emit
        # duplicate audit rows. The lock is per-row (Postgres
        # ``SELECT ... FOR UPDATE`` on the approval row); the loser
        # waits for the winner to COMMIT, re-reads the row, sees
        # status=APPROVED, and 409s out.
        with transaction.atomic(using="admin"):
            try:
                approval = (
                    FeatureFlagFlipApproval.objects.using("admin")
                    .select_for_update()
                    .get(pk=approval_id)
                )
            except FeatureFlagFlipApproval.DoesNotExist:
                return Response(
                    {"detail": "Approval not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if approval.status != FeatureFlagFlipApprovalStatus.PENDING:
                return Response(
                    {
                        "detail": (
                            f"Approval is {approval.status}; only PENDING approvals "
                            "can be transitioned."
                        ),
                        "status": approval.status,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            if str(approval.requested_by_id) == str(request.user.id):
                return Response(
                    {
                        "detail": (
                            "SELF_APPROVAL_FORBIDDEN: the approver must be a "
                            "different PLATFORM_ADMIN than the requester "
                            "(two-person rule)."
                        ),
                        "code": "SELF_APPROVAL_FORBIDDEN",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            tenant = Tenant.all_objects.using("admin").get(pk=approval.tenant_id)
            old_value = bool(getattr(tenant, approval.flag, False))
            new_value = bool(approval.requested_value)

            # Transition the approval row.
            approval.mark_approved(by=request.user)
            # Flip the actual flag column.
            setattr(tenant, approval.flag, new_value)
            tenant.save(update_fields=[approval.flag, "updated_at"])

            # Audit emission — both events linked by approval_id.
            create_audit_event(
                resource_type="FEATURE_FLAG_FLIP_APPROVAL",
                action=_audit_et.FEATURE_FLAG_FLIP_APPROVED,
                actor_user=request.user,
                tenant=tenant,
                resource_id=str(approval.id),
                result="SUCCESS",
                details={
                    "flag": approval.flag,
                    "requested_value": new_value,
                    "reason": approval.reason,
                    "requested_by": str(approval.requested_by_id),
                    "approver": str(request.user.id),
                    "approval_id": str(approval.id),
                    "tenant_id": str(tenant.id),
                },
                request=request,
                infer_tenant_from_actor=False,
            )
            # Phase 235.1 audit-fix Gap 3 — the actor_user on the
            # canonical CHANGED event is the APPROVER (the user whose
            # action persisted the SQL UPDATE), not the requester.
            # ``requested_by`` and ``approver`` BOTH live in
            # ``details_json`` so audit-replay can reconstruct the
            # two-person-rule transition either way; the top-level
            # ``actor_user_id`` column reflects "who did this DB
            # write" which is the standard audit semantic.
            _emit_changed_event(
                tenant=tenant,
                flag=approval.flag,
                old_value=old_value,
                new_value=new_value,
                reason=approval.reason,
                requested_by=approval.requested_by,
                approver=request.user,
                approval_id=str(approval.id),
                request=request,
                actor=request.user,
            )

        return Response(
            {
                "id": str(approval.id),
                "flag": approval.flag,
                "old_value": old_value,
                "new_value": new_value,
                "approver": str(request.user.id),
                "status": approval.status,
            },
            status=status.HTTP_200_OK,
        )
