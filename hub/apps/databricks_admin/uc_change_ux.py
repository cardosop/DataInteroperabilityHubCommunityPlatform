"""U4 approval UX (openspec add-databricks-uc-write task 2.8).

The approval surface around the 2.2 lifecycle:

- ``preview_change`` — the truthful DDL preview (exactly what will
  execute: the 2.3 executor's REST pin or the SQL statement; derived
  locally, ZERO network).
- ``timeline_for`` — merged status events + comments.
- ``add_comment`` — append-only comments (the ``UCChangeRequestComment``
  model, request-scoped).
- ``approval_inbox`` — requests whose CURRENT step authorizes the user
  (the workflow's own step logic — never a separate authorization copy).
- ``emit_change_transition`` — the transition side effects, best-effort:
  in-app ``UserNotification`` rows for the right recipients, webhook
  deliveries for the lifecycle event, and the observability metrics. A
  failure in ANY side effect never blocks the transition itself (the
  lifecycle functions call this AFTER the state persisted).

No secrets: webhook event data carries ids + statuses + names only.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.utils import timezone

from hub.apps.databricks_admin.models import (
    UCChangeRequest,
    UCChangeRequestComment,
    UCChangeRequestStatus,
)
from hub.apps.webhooks.models import WebhookEventType

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

# Lifecycle event → webhook event-type (the "databricks.uc_change.*"
# webhook namespace — distinct from the 2.9 AUDIT event vocabulary).
_TRANSITION_EVENTS = {
    "submitted": WebhookEventType.DATABRICKS_UC_CHANGE_SUBMITTED.value,
    "approved": WebhookEventType.DATABRICKS_UC_CHANGE_APPROVED.value,
    "rejected": WebhookEventType.DATABRICKS_UC_CHANGE_REJECTED.value,
    "executed": WebhookEventType.DATABRICKS_UC_CHANGE_EXECUTED.value,
    "failed": WebhookEventType.DATABRICKS_UC_CHANGE_FAILED.value,
    "rolled_back": WebhookEventType.DATABRICKS_UC_CHANGE_ROLLED_BACK.value,
}

_RESOURCE_TYPE = "DATABRICKS_UC_CHANGE_REQUEST"


# ── preview ──────────────────────────────────────────────────────────────────


def preview_change(change_request: UCChangeRequest) -> dict:
    """Exactly what the change will execute — derived locally, zero
    network. The 2.3 executor's dispatch table is the single source:
    REST-backed pins render method/path/body; SQL-only types render the
    identifier-quoted statement; unsupported combinations say so."""
    from hub.apps.databricks_admin.uc_change_executor import (
        _REST_PINS,
        UCChangeAction,
        UCDdlPayload,
        UCObjectType,
        _sql_statement,
    )

    # 2.8 review hardening — a deploy-rollback row carries a securable
    # the CURRENT vocabulary does not know: the preview marks it
    # unsupported instead of crashing the detail endpoint (fail-closed).
    try:
        object_type = UCObjectType(change_request.securable_type)
        action = UCChangeAction(change_request.change_type)
    except ValueError:
        return {
            "kind": "unsupported",
            "detail": f"unknown vocabulary {change_request.securable_type!r}",
        }
    payload = UCDdlPayload(
        object_type=object_type,
        action=action,
        identifiers=tuple((change_request.definition or {}).get("identifiers") or ()),
        options=(change_request.definition or {}).get("options") or {},
    )
    pin = _REST_PINS.get((payload.object_type, payload.action))
    if pin is not None:
        operation, method, body_builder, path_params_fn = pin
        from hub.apps.databricks_admin.api_paths import API_PATHS

        return {
            "kind": "rest",
            "method": method,
            "path": API_PATHS[operation].format(**path_params_fn(payload)),
            "body": body_builder(payload),
        }
    try:
        statement = _sql_statement(payload)
    except Exception:
        statement = None
    if statement is not None:
        return {"kind": "sql", "statement": statement}
    return {
        "kind": "unsupported",
        "detail": f"{payload.action.value} {payload.object_type.value}",
    }


# ── timeline + comments ──────────────────────────────────────────────────────


def add_comment(change_request: UCChangeRequest, author, body: str) -> UCChangeRequestComment:
    """Append a comment (request-scoped; blank bodies are rejected)."""
    comment = UCChangeRequestComment(request=change_request, author=author, body=body)
    comment.save()  # full_clean rejects blank bodies
    return comment


def timeline_for(change_request: UCChangeRequest) -> list[dict]:
    """Status events + comments merged in chronological order."""
    entries: list[dict] = []
    status_markers = [
        ("created", change_request.created_at, change_request.requested_by),
        (
            "submitted",
            change_request.updated_at
            if change_request.status != UCChangeRequestStatus.DRAFT
            else None,
            change_request.requested_by,
        ),
        ("approved", change_request.approved_at, change_request.approved_by),
        ("executing", change_request.executing_at, change_request.executed_by),
        ("executed", change_request.executed_at, change_request.executed_by),
        ("rejected", change_request.rejected_at, change_request.rejected_by),
        ("rolled_back", change_request.rolled_back_at, change_request.rolled_back_by),
    ]
    for kind, at, actor in status_markers:
        if at is None:
            continue
        entries.append(
            {
                "kind": kind,
                "at": at.isoformat(),
                "actor": getattr(actor, "email", None),
            }
        )
    for comment in change_request.comments.select_related("author").all():
        entries.append(
            {
                "kind": "comment",
                "at": comment.created_at.isoformat(),
                "author": getattr(comment.author, "email", None),
                "body": comment.body,
            }
        )
    entries.sort(key=lambda entry: entry["at"])
    return entries


# ── approver inbox ───────────────────────────────────────────────────────────


def approval_inbox(user) -> list[UCChangeRequest]:
    """Requests whose CURRENT approval step authorizes *user* — the
    workflow's own step logic (uc_changes), never a copied check."""
    from hub.apps.databricks_admin.uc_changes import _effective_step, _step_authorizes

    pending = UCChangeRequest.objects.filter(
        tenant=user.tenant,
        status__in=(
            UCChangeRequestStatus.PENDING_APPROVAL,
            UCChangeRequestStatus.PENDING_NEXT_APPROVER,
        ),
    ).select_related("workspace")
    inbox: list[UCChangeRequest] = []
    for request in pending:
        authorized, _reason = _step_authorizes(_effective_step(request), user)
        if authorized:
            inbox.append(request)
    return inbox


# ── transition side effects ──────────────────────────────────────────────────


def _recipients(change_request: UCChangeRequest, event: str) -> Iterable:
    """Who gets the in-app notification: approvers for submit, the
    requester for approve/reject/executed/failed/rolled_back."""
    from hub.apps.databricks_admin.uc_changes import _effective_step, _step_authorizes

    if event == "submitted":
        from hub.apps.users.models import User

        # The STEP AUTHORIZATION is the gate (has_role / approver-list
        # membership); the account status is a delivery concern, not a
        # security boundary — the workflow's own approver validation
        # checks activeness at approval time.
        step = _effective_step(change_request)
        for user in User.objects.filter(tenant=change_request.tenant):
            authorized, _reason = _step_authorizes(step, user)
            if authorized:
                yield user
        return
    if change_request.requested_by is not None:
        yield change_request.requested_by


def emit_change_transition(change_request: UCChangeRequest, event: str) -> None:
    """Best-effort side effects AFTER the transition persisted: in-app
    notifications + webhook deliveries + metrics. A failure here never
    blocks the transition (the lifecycle functions call it after save)."""
    from hub.apps.notifications.models import (
        NotificationCategory,
        NotificationType,
        UserNotification,
    )
    from hub.apps.webhooks.service import WebhookDeliveryService

    titles = {
        "submitted": "UC change request submitted",
        "approved": "UC change request approved",
        "rejected": "UC change request rejected",
        "executed": "UC change request executed",
        "failed": "UC change request failed",
        "rolled_back": "UC change request rolled back",
    }
    try:
        for user in _recipients(change_request, event):
            UserNotification.objects.create(
                tenant=change_request.tenant,
                user=user,
                title=titles.get(event, event),
                message=f"{change_request.change_type} {change_request.full_name} — {event}",
                notification_type=NotificationType.INFO,
                category=NotificationCategory.SYSTEM,
                resource_type=_RESOURCE_TYPE,
                resource_id=change_request.id,
            )
    except Exception:
        logger.warning(
            "databricks_uc_change_notification_failed",
            extra={"request": str(change_request.id), "event": event},
        )

    try:
        WebhookDeliveryService.trigger_webhook(
            tenant_id=str(change_request.tenant_id),
            event_type=_TRANSITION_EVENTS[event],
            resource_type=_RESOURCE_TYPE,
            resource_id=str(change_request.id),
            event_data={
                "request_id": str(change_request.id),
                "status": change_request.status,
                "change_type": change_request.change_type,
                "full_name": change_request.full_name,
                "workspace_id": str(change_request.workspace_id),
            },
        )
    except Exception:
        logger.warning(
            "databricks_uc_change_webhook_failed",
            extra={"request": str(change_request.id), "event": event},
        )

    try:
        from hub.apps.databricks_admin import metrics

        metrics.record_uc_change_request(event, tenant_id=str(change_request.tenant_id))
        if event in ("approved", "rejected"):
            metrics.record_uc_approval_duration(
                seconds=max(0.0, (timezone.now() - change_request.created_at).total_seconds())
            )
        metrics.refresh_uc_approval_gauges(str(change_request.tenant_id))
    except Exception:
        logger.warning(
            "databricks_uc_change_metrics_failed",
            extra={"request": str(change_request.id), "event": event},
        )
