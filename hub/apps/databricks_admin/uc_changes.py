"""UC change-request service (openspec add-databricks-control-plane task 2.2).

D7: DDL via approval workflow. This module owns the ``UCChangeRequest``
lifecycle service: creation, submission, approval (multi-step per Phase
272.4, delegation per Phase 272.6), rejection, and the guarded execution
hooks the task 2.3 executor consumes.

Layering (governance parity): the MODEL enforces the state machine
(``ALLOWED_TRANSITIONS`` / ``transition_to``, Django ``ValidationError``
code ``invalid_uc_change_status_transition``); THIS service enforces the
cross-cutting rules (tenant scoping, approver identity, workflow
advancement) and raises the core ``ValidationError`` family
(``hub.apps.core.services.base``) with the ``uc_change_*`` codes.

RLS contract: every mutation runs inside ``tenant_context(tenant_id)`` so
worker/signal callers (no request middleware) satisfy the
``app.current_tenant_id`` GUC the policy's WITH CHECK demands. Reads and
row-locks are tenant-scoped (``select_for_update`` by id+tenant — the
governance double-approve guard pattern).

Task 2.7 registers the ``databricks.uc.change.request/approve/execute``
business-rules chains AROUND these functions; task 2.9 owns the
``DATABRICKS_UC_CHANGE_*`` audit events — emitted here (one row per
lifecycle transition, best-effort, IDENTIFIERS-ONLY details).
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

from hub.apps.core.services.base import ValidationError
from hub.apps.databricks_admin.models import (
    UCChangeAction,
    UCChangeRequest,
    UCChangeRequestStatus,
    UCObjectType,
)
from hub.apps.tenants.request_tenant import tenant_context

_APPROVABLE_STATUSES = {
    UCChangeRequestStatus.PENDING_APPROVAL,
    UCChangeRequestStatus.PENDING_NEXT_APPROVER,
}


def create_change_request(
    *,
    tenant,
    workspace,
    requested_by,
    change_type: UCChangeAction,
    securable_type: UCObjectType,
    full_name: str,
    definition: dict,
    reason: str = "",
    required_approval_chain: list | None = None,
    requires_approval: bool = True,
) -> UCChangeRequest:
    """Create a DRAFT change request for a workspace of the SAME tenant.

    ``definition`` carries the executor's payload shape (task 2.3):
    ``{"identifiers": [catalog, schema?, name], "options": {...}}`` —
    consumed verbatim by :func:`build_ddl_payload`.

    Raises:
        ValidationError (uc_change_workspace_tenant_mismatch): the
            workspace belongs to another tenant.
    """
    if str(workspace.tenant_id) != str(tenant.id):
        raise ValidationError(
            f"Workspace {workspace.id} belongs to tenant {workspace.tenant_id}, "
            f"not tenant {tenant.id}",
            code="uc_change_workspace_tenant_mismatch",
        )
    with tenant_context(tenant.id):
        return UCChangeRequest.objects.create(
            tenant=tenant,
            workspace=workspace,
            requested_by=requested_by,
            change_type=change_type,
            securable_type=securable_type,
            full_name=full_name,
            definition=definition,
            reason=reason,
            required_approval_chain=list(required_approval_chain or []),
            requires_approval=requires_approval,
        )


def emit_uc_change_audit(
    action: str,
    change_request: UCChangeRequest,
    *,
    actor_user=None,
    details: dict | None = None,
) -> None:
    """2.9 — the change lifecycle's single audit chokepoint.

    One row per transition (resource_type=``DATABRICKS_UC_CHANGE``) with
    tenant/requester/approver attribution. IDENTIFIERS ONLY:
    ``definition.options`` can carry credential material (a
    storage-credential CREATE) — it is NEVER copied into the event
    details. Best-effort: an audit-DB outage never blocks the state
    transition (the Phase 273 contract).
    """
    try:
        from hub.apps.audit.utils import create_audit_event

        event_details = {
            "object_type": change_request.securable_type,
            "change_action": change_request.change_type,
            "full_name": change_request.full_name,
        }
        if details:
            event_details.update(details)
        create_audit_event(
            resource_type="DATABRICKS_UC_CHANGE",
            action=action,
            actor_user=actor_user,
            tenant=change_request.tenant,
            resource_id=change_request.id,
            details=event_details,
        )
    except Exception:
        logger.warning("databricks_uc_change_audit_failed", extra={"action": action})


def build_ddl_payload(change_request: UCChangeRequest):
    """The typed hand-off to the task 2.3 executor.

    Bridges the request row's persisted vocabulary (``UCObjectType`` /
    ``UCChangeAction`` + the payload-shaped ``definition``) into the
    executor's frozen ``UCDdlPayload`` — the contract between the request
    lifecycle and execution. Raises:
        ValidationError (uc_change_invalid_definition): the definition is
            not payload-shaped or its identifiers disagree with
            ``full_name``.
    """
    from hub.apps.databricks_admin.uc_change_executor import UCDdlPayload

    definition = change_request.definition or {}
    identifiers = definition.get("identifiers")
    if (
        not isinstance(identifiers, list)
        or not identifiers
        or not all(isinstance(part, str) and part for part in identifiers)
    ):
        raise ValidationError(
            f"UCChangeRequest {change_request.id} definition is not payload-shaped: "
            "identifiers must be a non-empty list of non-empty strings",
            code="uc_change_invalid_definition",
        )
    options = definition.get("options")
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ValidationError(
            f"UCChangeRequest {change_request.id} definition options must be an object",
            code="uc_change_invalid_definition",
        )
    payload = UCDdlPayload(
        object_type=UCObjectType(change_request.securable_type),
        action=UCChangeAction(change_request.change_type),
        identifiers=tuple(identifiers),
        options=dict(options),
    )
    if payload.full_name != change_request.full_name:
        raise ValidationError(
            f"UCChangeRequest {change_request.id} definition identifiers "
            f"({payload.full_name!r}) disagree with full_name "
            f"({change_request.full_name!r})",
            code="uc_change_invalid_definition",
        )
    return payload


def submit_change_request(*, change_request: UCChangeRequest) -> UCChangeRequest:
    """DRAFT → PENDING_APPROVAL (or APPROVED when requires_approval is
    False — the approval-skip shortcut the tenant config can choose).
    """
    with transaction.atomic(), tenant_context(change_request.tenant_id):
        request = _lock_for_update(change_request)
        if request.status != UCChangeRequestStatus.DRAFT:
            raise ValidationError(
                f"Cannot submit a UCChangeRequest in status {request.status} "
                "(only DRAFT can be submitted).",
                code="uc_change_invalid_submit_state",
            )
        target = (
            UCChangeRequestStatus.APPROVED
            if not request.requires_approval
            else UCChangeRequestStatus.PENDING_APPROVAL
        )
        request.transition_to(target)
        request.save()
        # 2.9 — one audit row per transition (REQUESTED = the DRAFT →
        # PENDING_APPROVAL hop; the approval-skip shortcut is flagged).
        emit_uc_change_audit(
            "REQUESTED",
            request,
            actor_user=request.requested_by,
            details={
                "target_status": str(target.value),
                **({"approval_skipped": True} if not request.requires_approval else {}),
            },
        )
        # 2.8 — U4 side effects (notifications + webhook + metrics),
        # best-effort AFTER the transition persisted.
        from hub.apps.databricks_admin.uc_change_ux import emit_change_transition

        emit_change_transition(request, "submitted")
        return request


def approve_change_request(*, change_request: UCChangeRequest, approver) -> UCChangeRequest:
    """Approve the CURRENT step of the workflow (272.4/272.6).

    Mirrors ``GovernanceService.approve_access_request``: row-locked
    double-approve guard, approver identity validation (active, same
    tenant, authorized for the step — directly or through an ACTIVE
    ``ApprovalDelegation`` whose delegator is authorized), chain
    SNAPSHOT on first approval, final step → APPROVED, intermediate →
    PENDING_NEXT_APPROVER.
    """
    with transaction.atomic():
        request = _lock_for_update(change_request)
        if request.status not in _APPROVABLE_STATUSES:
            raise ValidationError(
                f"UCChangeRequest {request.id} is not approvable (status: {request.status}).",
                code="uc_change_not_approvable",
            )

        _validate_approver(request, approver)
        _advance_workflow(request, approver)
        # 2.9 — one APPROVED row per approval action (intermediate
        # 272.4 steps included; the final step carries final=True).
        emit_uc_change_audit(
            "APPROVED",
            request,
            actor_user=approver,
            details={
                "step": request.current_approval_step,
                "final": request.status == UCChangeRequestStatus.APPROVED,
            },
        )
        from hub.apps.databricks_admin.uc_change_ux import emit_change_transition

        emit_change_transition(request, "approved")
        return request


def reject_change_request(
    *, change_request: UCChangeRequest, approver, reason: str
) -> UCChangeRequest:
    """Deny the request (terminal REJECTED with a recorded reason)."""
    if not (reason or "").strip():
        raise ValidationError(
            "A rejection reason is required.", code="uc_change_rejection_reason_required"
        )
    with transaction.atomic():
        request = _lock_for_update(change_request)
        if request.status not in _APPROVABLE_STATUSES:
            raise ValidationError(
                f"UCChangeRequest {request.id} is not rejectable (status: {request.status}).",
                code="uc_change_not_approvable",
            )
        _validate_approver(request, approver)
        request.rejection_reason = reason.strip()
        request.rejected_by = approver
        request.rejected_at = timezone.now()
        request.transition_to(UCChangeRequestStatus.REJECTED)
        request.save()
        emit_uc_change_audit(
            "REJECTED",
            request,
            actor_user=approver,
            details={"reason": request.rejection_reason},
        )
        from hub.apps.databricks_admin.uc_change_ux import emit_change_transition

        emit_change_transition(request, "rejected")
        return request


def mark_executing(*, change_request: UCChangeRequest) -> UCChangeRequest:
    """APPROVED → EXECUTING (the 2.3 executor's guarded entry point)."""
    with transaction.atomic(), tenant_context(change_request.tenant_id):
        request = _lock_for_update(change_request)
        request.transition_to(UCChangeRequestStatus.EXECUTING)
        request.save()
        emit_uc_change_audit("EXECUTING", request)
        return request


def mark_executed(*, change_request: UCChangeRequest, executor) -> UCChangeRequest:
    """EXECUTING → EXECUTED with execution bookkeeping."""
    with transaction.atomic(), tenant_context(change_request.tenant_id):
        request = _lock_for_update(change_request)
        request.transition_to(UCChangeRequestStatus.EXECUTED)
        request.executed_by = executor
        request.executed_at = timezone.now()
        request.save()
        emit_uc_change_audit("EXECUTED", request, actor_user=executor)
        from hub.apps.databricks_admin.uc_change_ux import emit_change_transition

        emit_change_transition(request, "executed")
        return request


def mark_failed(*, change_request: UCChangeRequest, error: str) -> UCChangeRequest:
    """EXECUTING → FAILED with the failure detail (2.5's reaper also
    drives stuck EXECUTING rows through this)."""
    with transaction.atomic(), tenant_context(change_request.tenant_id):
        request = _lock_for_update(change_request)
        request.transition_to(UCChangeRequestStatus.FAILED)
        request.execution_error = error or "execution failed"
        request.save()
        emit_uc_change_audit("FAILED", request, details={"error": request.execution_error})
        from hub.apps.databricks_admin.uc_change_ux import emit_change_transition

        emit_change_transition(request, "failed")
        return request


def mark_rolled_back(*, change_request: UCChangeRequest, actor) -> UCChangeRequest:
    """FAILED → ROLLED_BACK (best-effort recovery; D7 — destructive DDL is
    never auto-rolled-back, the executor decides)."""
    with transaction.atomic(), tenant_context(change_request.tenant_id):
        request = _lock_for_update(change_request)
        request.transition_to(UCChangeRequestStatus.ROLLED_BACK)
        request.rolled_back_by = actor
        request.rolled_back_at = timezone.now()
        request.save()
        emit_uc_change_audit("ROLLED_BACK", request, actor_user=actor)
        from hub.apps.databricks_admin.uc_change_ux import emit_change_transition

        emit_change_transition(request, "rolled_back")
        return request


# ── internals ──────────────────────────────────────────────────────────────


def _lock_for_update(change_request: UCChangeRequest) -> UCChangeRequest:
    """Re-fetch tenant-scoped under a row lock (the double-approve guard).

    RLS-contract-safe: the row is resolved by id AND tenant_id, so a
    caller can never drive another tenant's request.
    """
    return UCChangeRequest.objects.select_for_update().get(
        id=change_request.id, tenant_id=change_request.tenant_id
    )


def _effective_step(change_request: UCChangeRequest) -> Any | None:
    """The approval step the request is CURRENTLY on.

    Prefer the frozen workflow snapshot. When nothing is snapshotted yet
    (first approval), resolve step 0 from the PROPOSED chain — an
    improvement over governance's single-step fallback: the chain defines
    step 0, so the first approver is validated against it.
    """
    workflow = change_request.approval_workflow or []
    index = change_request.current_approval_step
    if workflow and 0 <= index < len(workflow):
        return workflow[index]
    chain = change_request.required_approval_chain or []
    if isinstance(chain, list) and len(chain) > 0:
        return chain[0]
    return None  # single-step semantics


def _step_authorizes(step_def: Any | None, user) -> tuple[bool, str | None]:
    """Whether *user* is directly authorized for *step_def*.

    Step forms: dict with ``approvers`` (user-id list) or ``role``;
    legacy string steps are role names; ``None`` is the single-step
    fallback (TENANT_ADMIN — the AccessRequest semantics). Returns
    (authorized, role) — the role when the step is role-gated.
    """
    if step_def is None:
        return user.has_role("TENANT_ADMIN"), "TENANT_ADMIN"
    if isinstance(step_def, dict):
        approvers = step_def.get("approvers") or []
        if isinstance(approvers, list) and str(user.id) in [str(a) for a in approvers]:
            return True, None
        role = step_def.get("role")
        if role:
            return user.has_role(role), role
        return False, None
    if isinstance(step_def, str):
        return user.has_role(step_def), step_def
    return False, None


def _authorize_via_delegation(
    change_request: UCChangeRequest, approver, step_def: Any | None
) -> bool:
    """272.6 — approval authority through an ACTIVE ApprovalDelegation.

    The delegation cannot MANUFACTURE authority: the delegator must
    themselves be authorized for the step. For role-gated steps the
    delegate must also HOLD the role (governance parity — a role is
    delegated as the ability to act with it, not to act without it).
    """
    from hub.apps.governance.models import ApprovalDelegation

    now = timezone.now()
    delegation = (
        ApprovalDelegation.objects.filter(
            tenant_id=change_request.tenant_id,
            delegate_id=approver.id,
            start_at__lte=now,
            end_at__gte=now,
        )
        .order_by("-created_at")
        .first()
    )
    if delegation is None:
        return False

    # The delegator must themselves be authorized for the step (None =
    # the single-step TENANT_ADMIN fallback).
    delegator_authorized, required_role = _step_authorizes(step_def, delegation.delegator)
    return delegator_authorized and (required_role is None or approver.has_role(required_role))


def _validate_approver(change_request: UCChangeRequest, approver) -> None:
    """Approver identity validation (the governance
    ``_validate_access_request_approval`` mirror).

    Raises:
        ValidationError (uc_change_approver_inactive /
            uc_change_approver_tenant_mismatch / uc_change_approver_unauthorized)
    """
    # The repo's User exposes ``is_active`` as a METHOD
    # (``User.is_active()`` → status == ACTIVE); legacy models may use an
    # attribute. Handle both forms — a bound method is truthy, so the
    # attribute-only check would silently never fire.
    is_active = getattr(approver, "is_active", False)
    if callable(is_active):
        is_active = is_active()
    if not is_active:
        raise ValidationError(
            f"Approver {approver.email} is not active",
            code="uc_change_approver_inactive",
        )
    if str(getattr(approver, "tenant_id", "") or "") != str(change_request.tenant_id):
        raise ValidationError(
            f"Approver {approver.email} belongs to tenant "
            f"{getattr(approver, 'tenant_id', None)} but the change request "
            f"is for tenant {change_request.tenant_id}",
            code="uc_change_approver_tenant_mismatch",
        )

    step_def = _effective_step(change_request)
    authorized, _ = _step_authorizes(step_def, approver)
    if not authorized and not _authorize_via_delegation(change_request, approver, step_def):
        raise ValidationError(
            f"Approver {approver.email} is not authorized for the current "
            f"approval step of UCChangeRequest {change_request.id}",
            code="uc_change_approver_unauthorized",
        )


def _advance_workflow(change_request: UCChangeRequest, approver) -> None:
    """272.4 — snapshot the chain on first approval, then advance.

    Mutates and SAVES the request: APPROVED on the final step (or when the
    chain is empty — single-step), PENDING_NEXT_APPROVER otherwise.
    """
    workflow = change_request.approval_workflow or []

    if not workflow:
        chain = change_request.required_approval_chain or []
        if isinstance(chain, list) and len(chain) > 0:
            # FIRST approval — freeze the proposed chain (272.4 snapshot).
            change_request.approval_workflow = list(chain)
            change_request.current_approval_step = 0
        else:
            # Single-step — complete immediately.
            change_request.approval_workflow = []
            change_request.current_approval_step = 0
            change_request.approved_by = approver
            change_request.approved_at = timezone.now()
            change_request.transition_to(UCChangeRequestStatus.APPROVED)
            change_request.save()
            return

    workflow = change_request.approval_workflow
    current_step = change_request.current_approval_step
    total_steps = len(workflow)

    change_request.approved_by = approver
    change_request.approved_at = timezone.now()
    if current_step >= total_steps - 1:
        # Final step — the workflow is complete.
        change_request.current_approval_step = total_steps
        change_request.transition_to(UCChangeRequestStatus.APPROVED)
    else:
        # Intermediate step — advance to the next approver.
        change_request.current_approval_step = current_step + 1
        change_request.transition_to(UCChangeRequestStatus.PENDING_NEXT_APPROVER)
    change_request.save()
