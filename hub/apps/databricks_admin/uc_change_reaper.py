"""Stuck-EXECUTING reaper (openspec add-databricks-uc-write task 2.5) — D4.

The rollback policy for ``UCChangeRequest`` rows that died in EXECUTING:

- LEASE — a request is stuck when its ``executing_at`` anchor is older
  than ``REAPER_LEASE_SECONDS`` (an EXECUTING row with NO anchor is
  treated as abandoned — it can never prove freshness).
- CREATE-type — BEST-EFFORT rollback: the compensating DROP deletes
  exactly what the request created (the same identifier chain, the 2.3
  executor's DROP pin) and the request lands in ROLLED_BACK even when
  the delete fails (the object may never have existed — the worker may
  have died before the DDL). The compensating DROP runs with the 2.4
  denylist BYPASSED: this is the sanctioned policy carve-out — the
  reaper is the rollback policy itself, and it only ever deletes the
  object a stuck CREATE request created, never a user-requested DROP.
- Destructive (DROP-type) — the request lands in FAILED with ZERO
  compensating DDL. Destructive DDL is NEVER auto-rolled-back (rolling
  back a DROP would recreate data the Hub did not own).
- Identity failures (no workspace M2M credential / no approver-chain
  linkage) fail the request too — a stuck request never lingers.

The identity is the D12 BACKGROUND purpose ``uc_change_reaper`` (the
workspace M2M credential WITH approver-chain linkage); the client
factory seam is ``_build_uc_client`` (uc_views — the 1.5 convention;
tests redirect it to a real local transport).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils import timezone

from hub.apps.databricks_admin.models import (
    UCChangeAction,
    UCChangeRequest,
    UCChangeRequestStatus,
    UCObjectType,
)
from hub.apps.databricks_admin.uc_views import _build_uc_client

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# The lease: how long a request may sit in EXECUTING before the reaper
# considers the worker dead. Bounds the async window (D4).
REAPER_LEASE_SECONDS = 3600


def find_stuck_requests(tenant, *, lease_seconds: int | None = None) -> list[UCChangeRequest]:
    """The tenant's EXECUTING requests whose lease expired. Caller runs
    under ``tenant_context`` (the worker contract — RLS-scoped)."""
    lease = lease_seconds if lease_seconds is not None else REAPER_LEASE_SECONDS
    cutoff = timezone.now() - timedelta(seconds=lease)
    return list(
        UCChangeRequest.objects.filter(
            tenant=tenant, status=UCChangeRequestStatus.EXECUTING
        ).filter(Q(executing_at__isnull=True) | Q(executing_at__lt=cutoff))
    )


def _compensating_payload(request: UCChangeRequest):
    """The DROP payload for what the request created (the identifier
    chain the request itself stored)."""
    identifiers = (request.definition or {}).get("identifiers")
    if (
        not isinstance(identifiers, list)
        or not identifiers
        or not all(isinstance(part, str) and part for part in identifiers)
    ):
        return None
    from hub.apps.databricks_admin.uc_change_executor import UCDdlPayload

    return UCDdlPayload(
        object_type=UCObjectType(request.securable_type),
        action=UCChangeAction.DROP,
        identifiers=tuple(identifiers),
        options={},
    )


def _resolve_terminal(request: UCChangeRequest, status: str, *, error: str | None = None) -> dict:
    """Persist the reaper's terminal resolution through the state
    machine (the single source of truth) — never a raw status write."""
    request.transition_to(status)
    if status == UCChangeRequestStatus.FAILED:
        request.execution_error = error
    request.save()
    # 2.9 — the reaper's terminal resolutions are audited like every
    # other transition (system actor — the reaper has no user).
    from hub.apps.databricks_admin.uc_changes import emit_uc_change_audit

    emit_uc_change_audit(
        "FAILED" if status == UCChangeRequestStatus.FAILED else "ROLLED_BACK",
        request,
        details={"reason": error or ""},
    )
    return {"terminal": status, "reason": error or ""}


def _force_fail_terminal(request: UCChangeRequest, error: str) -> dict:
    """Terminal FAILED for a row the MODEL cannot validate — the
    documented exception to ``transition_to``.

    A deploy-rollback enum value makes ``save()`` run ``full_clean()``
    and reject the very column the reaper cannot rewrite, so the normal
    path can never persist the terminal state. The conditional update
    (``status=EXECUTING`` in the WHERE) keeps the re-entrancy semantics:
    only an EXECUTING row resolves, and the hop (EXECUTING → FAILED) is
    the state machine's own legal edge.
    """
    updated = UCChangeRequest.objects.filter(
        pk=request.pk, status=UCChangeRequestStatus.EXECUTING
    ).update(
        status=UCChangeRequestStatus.FAILED,
        execution_error=error,
        updated_at=timezone.now(),
    )
    if updated == 1:
        # 2.9 — audited like every terminal resolution; only when THIS
        # worker won the conditional update (a 0-row update means another
        # worker already resolved the row — no second audit row).
        from hub.apps.databricks_admin.uc_changes import emit_uc_change_audit

        emit_uc_change_audit(
            "FAILED",
            request,
            details={"reason": error, "forced": True},
        )
    return {
        "terminal": UCChangeRequestStatus.FAILED,
        "reason": error,
        "forced": updated == 1,
    }


def resolve_stuck_request(
    request: UCChangeRequest,
    *,
    client_factory: Callable | None = None,
    lease_seconds: int | None = None,
) -> dict:
    """Resolve ONE request. Re-entrant: re-checks the lease first (a
    request another worker claimed is left alone — ``{"skipped": True}``).

    Returns ``{"terminal": "ROLLED_BACK"|"FAILED", "reason": ...}`` or
    ``{"skipped": True}``.
    """
    from hub.apps.databricks_admin.client import DatabricksOBOError
    from hub.apps.databricks_admin.identity import HybridIdentityError, resolve_execution_identity
    from hub.apps.databricks_admin.uc_change_executor import UCChangeExecutor
    from hub.apps.databricks_admin.uc_sync import _select_service_credential

    lease = lease_seconds if lease_seconds is not None else REAPER_LEASE_SECONDS
    if request.status != UCChangeRequestStatus.EXECUTING:
        return {"skipped": True}
    if (
        request.executing_at is not None
        and (timezone.now() - request.executing_at).total_seconds() <= lease
    ):
        return {"skipped": True}

    # Destructive DDL is NEVER auto-rolled-back (D4) — fail it with ZERO
    # compensating DDL, before any identity resolution or network call.
    if request.change_type == UCChangeAction.DROP:
        return _resolve_terminal(
            request,
            UCChangeRequestStatus.FAILED,
            error=(
                "stuck destructive DDL is never auto-rolled-back "
                "(the reaper does not recreate dropped objects)"
            ),
        )

    # 2.5 review hardening — fail-closed on the VOCABULARY. The enums are
    # persisted as CHARFIELDS: a deploy rollback (or a future phase —
    # 2.6 adds securables, a later phase may add ALTER) leaves rows whose
    # values today's code does not know. An unknown action must NEVER
    # fall through into the CREATE rollback path (compensating for an
    # operation we do not understand is forbidden), and an unknown
    # securable must fail the REQUEST — not crash the sweep.
    if request.change_type != UCChangeAction.CREATE:
        return _force_fail_terminal(
            request,
            f"unknown change_type {request.change_type!r} — the reaper "
            "cannot roll back an operation it does not understand",
        )
    try:
        UCObjectType(request.securable_type)
    except ValueError:
        return _force_fail_terminal(
            request,
            f"unknown securable_type {request.securable_type!r} — the reaper "
            "cannot determine what the request created",
        )

    # CREATE-type: resolve the D12 BACKGROUND identity (M2M credential +
    # approver-chain linkage). An identity failure fails the request —
    # a stuck request never lingers.
    credential = _select_service_credential(request.workspace)
    if credential is None or credential.approval_request is None:
        return _resolve_terminal(
            request,
            UCChangeRequestStatus.FAILED,
            error=(
                "the workspace M2M credential carries no approver-chain "
                "linkage (D12 background execution) — the reaper cannot "
                "issue the compensating DDL"
            ),
        )
    try:
        identity = resolve_execution_identity(
            purpose="uc_change_reaper",
            workspace=request.workspace,
            credential=credential,
            approval_request=credential.approval_request,
        )
    except (HybridIdentityError, DatabricksOBOError) as exc:
        return _resolve_terminal(
            request,
            UCChangeRequestStatus.FAILED,
            error=f"D12 identity resolution failed: {exc}",
        )

    payload = _compensating_payload(request)
    if payload is None:
        return _resolve_terminal(
            request,
            UCChangeRequestStatus.FAILED,
            error="the request definition is not payload-shaped — the reaper "
            "cannot determine what the request created",
        )

    factory = client_factory or _build_uc_client
    with factory(request.workspace, identity) as client:
        # The sanctioned denylist carve-out (2.5): the compensating DROP
        # is the rollback POLICY itself, not a user request — it deletes
        # exactly what the stuck CREATE created. Best-effort: a failed
        # delete (the object may never have existed) still resolves.
        executor = UCChangeExecutor(client=client, denylist_bypass=True)
        try:
            result = executor.execute(payload)
        except Exception as exc:
            logger.warning(
                "databricks_uc_change_reaper_rollback_failed",
                extra={
                    "request": str(request.id),
                    "workspace": str(request.workspace_id),
                    "error": str(exc),
                },
            )
        else:
            logger.info(
                "databricks_uc_change_reaper_rollback",
                extra={"request": str(request.id), "terminal": result.terminal},
            )

    request.rolled_back_at = timezone.now()
    return _resolve_terminal(request, UCChangeRequestStatus.ROLLED_BACK)
