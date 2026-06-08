"""
Phase 235.3 — PLATFORM_ADMIN tenant soft-delete endpoint.

Mounts at ``DELETE /api/v1/admin/tenants/{id}/`` (registered in
``hub/apps/tenants/admin_urls.py``). Two-phase deletion contract:

1.  **Soft-delete (this endpoint)** — stamps
    ``Tenant.scheduled_for_deletion_at = now()`` (alongside the
    existing Phase 226 ``deleted_at`` field) and flips the tenant's
    ``status`` to ``DELETED``. The Tenant row stays in the DB for a
    90-day grace window; the audit event ``TENANT_SOFT_DELETED``
    captures the operator's intent + the grace deadline.
2.  **Hard-delete (separate cron — see
    ``hub/apps/tenants/tenant_hard_delete_sweep.py``)** — the daily
    sweep walks tenants whose ``scheduled_for_deletion_at`` is older
    than 90 days, re-checks ``legal_hold`` AND DSAR-restriction at
    sweep time, emits ``TENANT_HARD_DELETED`` BEFORE the cascade,
    and hard-deletes the Tenant row (cascading through every FK
    that has ``on_delete=CASCADE`` — see the runbook for the affected
    resource map).

Rejection contract (REQ-ADMIN-TENANT-DELETE-001):

* HTTP 422 ``LEGAL_HOLD_ACTIVE`` if ``tenant.legal_hold=True``.
* HTTP 422 ``DSAR_RESTRICTION_ACTIVE`` if any open RESTRICTION-class
  DSAR exists for the tenant.
* HTTP 409 ``ALREADY_DELETED`` if the tenant is already soft-deleted
  (idempotency contract — the operator's second click on the
  "Deactivate" button shouldn't error opaquely).
"""
from __future__ import annotations
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.utils import create_audit_event
from hub.apps.governance.dsar_retention_block import (
    tenant_blocked_by_open_dsar_restriction,
)

from .models import Tenant, TenantStatus
from .permissions import IsPlatformAdmin

logger = logging.getLogger(__name__)


class AdminTenantDeleteView(APIView):
    """PLATFORM_ADMIN endpoint for soft-deleting a tenant with 90-day grace."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    @extend_schema(
        operation_id="admin_tenant_soft_delete",
        summary="Soft-delete a tenant (90-day grace window)",
        description=(
            "Stamps ``Tenant.scheduled_for_deletion_at = now()`` + "
            "``Tenant.deleted_at = now()`` and flips ``status`` to "
            "``DELETED``. The row stays in the database; the daily "
            "``tenant_hard_delete_sweep`` cron hard-deletes 90 days "
            "later. Emits ``TENANT_SOFT_DELETED`` audit. See "
            "``docs/runbooks/admin-tenant-deactivation.md`` for the "
            "restore flow + blocker contracts."
        ),
        request=None,
        responses={
            200: OpenApiResponse(
                description=(
                    "Soft-delete succeeded. Response carries ``tenant`` "
                    "(id, slug, status, deleted_at, "
                    "scheduled_for_deletion_at, hard_delete_after) + "
                    "``grace_window_days``."
                ),
            ),
            401: OpenApiResponse(
                description="Unauthorized — missing or invalid bearer token.",
            ),
            403: OpenApiResponse(
                description="Forbidden — caller is not a PLATFORM_ADMIN.",
            ),
            404: OpenApiResponse(description="Tenant not found."),
            409: OpenApiResponse(
                description=(
                    "Conflict. ``code=ALREADY_DELETED`` — tenant is "
                    "already in DELETED status (idempotent re-click "
                    "from the SPA)."
                ),
            ),
            422: OpenApiResponse(
                description=(
                    "Unprocessable. ``code=LEGAL_HOLD_ACTIVE`` when "
                    "``Tenant.legal_hold=True``; ``code=DSAR_RESTRICTION_ACTIVE`` "
                    "when an open RESTRICTION DSAR targets the tenant. "
                    "Both blockers re-evaluated at hard-delete sweep "
                    "time too."
                ),
            ),
        },
        tags=["Admin"],
    )
    def delete(self, request, tenant_id):
        # Phase 235.3 audit-fix Gap 1 — wrap the entire flow (lookup +
        # guard checks + state mutation + audit emission) in ONE
        # ``transaction.atomic()`` block with ``select_for_update()``
        # on the tenant row. Without the row-level lock, two
        # PLATFORM_ADMINs clicking Deactivate concurrently would BOTH
        # pass the ``deleted_at is None`` check (each reads the row
        # under its own READ COMMITTED snapshot before the other
        # commits), BOTH stamp ``deleted_at``, and BOTH emit
        # ``TENANT_SOFT_DELETED`` — two audit events for one
        # soft-delete is a forensic mess. The Postgres row lock
        # serialises the two requests: the loser blocks on the
        # lock, re-reads the row after the winner commits, sees
        # ``status=DELETED``, and 409s out via the idempotency check
        # below.
        with transaction.atomic():
            try:
                tenant = (
                    Tenant.all_objects.select_for_update().get(pk=tenant_id)
                )
            except Tenant.DoesNotExist:
                return Response(
                    {"detail": "Tenant not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # 409 — already soft-deleted. Idempotency contract: the SPA's
            # double-click on the "Deactivate" button should NOT surface a
            # confusing 400 or 500. We return 409 with an explicit code so
            # the SPA can render "Tenant is already scheduled for deletion".
            if tenant.deleted_at is not None or tenant.status == TenantStatus.DELETED:
                return Response(
                    {
                        "code": "ALREADY_DELETED",
                        "detail": (
                            f"Tenant {tenant.slug!r} is already soft-deleted "
                            f"(deleted_at={tenant.deleted_at.isoformat() if tenant.deleted_at else None})."
                        ),
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # 422 — legal hold blocks any deletion attempt.
            if tenant.legal_hold:
                return Response(
                    {
                        "code": "LEGAL_HOLD_ACTIVE",
                        "detail": (
                            f"Tenant {tenant.slug!r} has an active legal hold. "
                            "Lift the hold before attempting deletion."
                        ),
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            # 422 — open RESTRICTION-class DSAR blocks deletion. Re-checked
            # at hard-delete sweep time too (an admin who soft-deletes a
            # tenant before the subject opens a DSAR-restriction within the
            # grace window MUST NOT have the hard-delete proceed).
            if tenant_blocked_by_open_dsar_restriction(tenant_id=str(tenant.id)):
                return Response(
                    {
                        "code": "DSAR_RESTRICTION_ACTIVE",
                        "detail": (
                            f"Tenant {tenant.slug!r} has an open RESTRICTION-class "
                            "DSAR. Resolve the DSAR (CLOSED_FULFILLED or "
                            "CLOSED_REJECTED) before attempting deletion."
                        ),
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            # Happy path — state mutation + audit emission under the
            # row lock so the next concurrent caller sees the new state.
            now = timezone.now()
            Tenant.all_objects.filter(pk=tenant.pk).update(
                scheduled_for_deletion_at=now,
                deleted_at=now,
                status=TenantStatus.DELETED,
                updated_at=now,
            )
            tenant.refresh_from_db()
            create_audit_event(
                resource_type="TENANT",
                action=_audit_et.TENANT_SOFT_DELETED,
                actor_user=request.user,
                tenant=tenant,
                resource_id=str(tenant.id),
                result="SUCCESS",
                details={
                    "slug": tenant.slug,
                    "display_name": tenant.name,
                    "scheduled_for_deletion_at": now.isoformat(),
                    "deleted_by": str(request.user.id),
                    "tenant_id": str(tenant.id),
                },
                request=request,
                infer_tenant_from_actor=False,
            )

        # ``deleted_at`` and ``scheduled_for_deletion_at`` were just
        # stamped in the atomic block above; both are guaranteed non-NULL
        # at this point, so the isoformat() calls are safe.
        assert tenant.deleted_at is not None
        assert tenant.scheduled_for_deletion_at is not None
        hard_delete_after = tenant.scheduled_for_deletion_at + timedelta(days=90)
        return Response(
            {
                "tenant": {
                    "id": str(tenant.id),
                    "slug": tenant.slug,
                    "status": tenant.status,
                    "deleted_at": tenant.deleted_at.isoformat(),
                    "scheduled_for_deletion_at": tenant.scheduled_for_deletion_at.isoformat(),
                    "hard_delete_after": hard_delete_after.isoformat(),
                },
                "grace_window_days": 90,
            },
            status=status.HTTP_200_OK,
        )
