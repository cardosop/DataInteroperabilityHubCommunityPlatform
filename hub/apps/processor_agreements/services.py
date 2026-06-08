"""Notifications and helpers for processor agreements (Phase 232.6.8)."""

from __future__ import annotations
import json
from typing import Any, Iterable

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.notifications.models import NotificationCategory, NotificationType
from hub.apps.notifications.utils import create_user_notification
from hub.apps.processor_agreements.models import ProcessorAgreement
from hub.apps.users.models import UserRole


def subprocessor_fingerprint(rows: Iterable[dict[str, Any]]) -> str:
    """Stable fingerprint for equality checks (order-independent)."""
    norm = sorted((dict(r) for r in rows), key=lambda x: str(x.get("name", "")).lower())
    return json.dumps(norm, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def notify_subprocessor_change(
    *,
    agreement: ProcessorAgreement,
    previous: list[dict[str, Any]] | None,
    actor,
) -> None:
    """Emit audit + in-app notifications to TENANT_ADMIN when sub-processor list changes."""
    prev = previous if previous is not None else []
    cur = list(agreement.sub_processors_declared or [])
    if subprocessor_fingerprint(prev) == subprocessor_fingerprint(cur):
        return

    create_audit_event(
        resource_type="PROCESSOR_AGREEMENT",
        action=audit_event_types.PROCESSOR_AGREEMENT_SUBPROCESSOR_CHANGED,
        actor_user=actor,
        tenant=agreement.tenant,
        resource_id=str(agreement.id),
        details={
            "processor_id": str(agreement.processor_id),
            "previous": prev,
            "current": cur,
        },
    )

    qs = UserRole.objects.filter(
        tenant=agreement.tenant,
        role__name="TENANT_ADMIN",
    ).select_related("user")
    title = "Sub-processor list updated"
    msg = (
        f"Agreement {agreement.agreement_type} for processor "
        f"{agreement.processor.name}: sub-processor disclosure changed — review inbox / audit."
    )
    for ur in qs:
        create_user_notification(
            user=ur.user,
            tenant=agreement.tenant,
            title=title,
            message=msg,
            notification_type=NotificationType.WARNING,
            category=NotificationCategory.GOVERNANCE,
            resource_type="PROCESSOR_AGREEMENT",
            resource_id=agreement.id,
        )
