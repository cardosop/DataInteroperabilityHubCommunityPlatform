"""Notification authoring helpers (Phase 223.1).

Call ``create_user_notification`` from business-rule code to drop a row
into the recipient's inbox. Keep the function import-lite and defensive:
callers already own the happy path — they should not fail just because
the inbox write is flaky (disk full, DB rollback edge, etc.). Errors are
logged and swallowed so the primary business flow still succeeds.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from .models import (
    NotificationCategory,
    NotificationType,
    UserNotification,
)

if TYPE_CHECKING:
    from hub.apps.audit.models import AuditEvent
    from hub.apps.tenants.models import Tenant
    from hub.apps.users.models import User

logger = logging.getLogger(__name__)

# Normalise keys so callers can pass lowercase / enum / display labels —
# the serializer enforces the canonical uppercase constant in the DB.
_TYPE_ALIASES = {str(t).lower(): t for t in NotificationType.values}
_CATEGORY_ALIASES = {str(c).lower(): c for c in NotificationCategory.values}


def _coerce_type(value: str | NotificationType) -> str:
    key = str(value).lower()
    if key in _TYPE_ALIASES:
        return _TYPE_ALIASES[key]
    return NotificationType.INFO.value


def _coerce_category(value: str | NotificationCategory) -> str:
    key = str(value).lower()
    if key in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[key]
    return NotificationCategory.SYSTEM.value


def create_user_notification(
    *,
    user: User,
    tenant: Tenant,
    title: str,
    message: str,
    notification_type: str | NotificationType = NotificationType.INFO,
    category: str | NotificationCategory = NotificationCategory.SYSTEM,
    resource_type: str | None = None,
    resource_id: str | UUID | None = None,
    audit_event: AuditEvent | None = None,
    **_ignored: Any,
) -> UserNotification | None:
    """Persist a notification; returns the row, or ``None`` on failure.

    Required: ``user``, ``tenant``, ``title``, ``message``.

    Failure modes are *logged and swallowed* — the upstream business
    operation (e.g. approving an access request) must not fail because
    the inbox insert hit an integrity error; a retry or email fallback
    can be added later without changing call sites.
    """
    if user is None or tenant is None:
        logger.warning(
            "create_user_notification called without user/tenant; dropping",
            extra={"user_id": getattr(user, "id", None)},
        )
        return None

    try:
        if resource_id is not None and not isinstance(resource_id, UUID):
            try:
                resource_id = UUID(str(resource_id))
            except (ValueError, TypeError):
                logger.warning(
                    "create_user_notification got non-UUID resource_id; dropping field",
                    extra={"resource_id": resource_id},
                )
                resource_id = None

        notification = UserNotification.objects.create(
            user=user,
            tenant=tenant,
            audit_event=audit_event,
            title=str(title)[:200],
            message=str(message),
            notification_type=_coerce_type(notification_type),
            category=_coerce_category(category),
            resource_type=resource_type,
            resource_id=resource_id,
        )
    except Exception:
        logger.exception(
            "create_user_notification failed",
            extra={
                "user_id": getattr(user, "id", None),
                "tenant_id": getattr(tenant, "id", None),
                "category": category,
            },
        )
        return None

    # Phase 223.1.10 — publish a websocket event so subscribed clients
    # can refresh their inbox in real-time. Failures here are non-fatal:
    # the row is already persisted and the 60s polling fallback will
    # surface it eventually.
    try:
        from hub.apps.core.events.publisher import publish_event

        recipient_id = str(notification.user.id)
        recipient_tenant_id = str(notification.tenant.id)
        event_data = {
            "id": str(notification.id),
            "user_id": recipient_id,
            "category": notification.category,
            "notification_type": notification.notification_type,
            "title": notification.title,
            "resource_id": (str(notification.resource_id) if notification.resource_id else None),
        }
        # Only include resource_type when it has a string value to
        # satisfy the event schema (resource_type: string, not nullable).
        if notification.resource_type:
            event_data["resource_type"] = notification.resource_type
        publish_event(
            event_type="notification.created",
            data=event_data,
            tenant_id=recipient_tenant_id,
            user_id=recipient_id,
            skip_deduplication=True,
        )
    except Exception:
        logger.warning(
            "notification.created event publish failed",
            extra={"notification_id": str(notification.id)},
            exc_info=True,
        )

    return notification
