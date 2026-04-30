"""
Phase 227 Wave 2 (227.W2.3) — T-0 announcement helper.

Sends a one-shot ``SCHEMA_EDITOR_AVAILABLE`` email to every TENANT_ADMIN
announcing that the Schema editor is now generally available and that
they should triage their structureless contracts via the new Contract
Health page (``/admin/contract-health``).

Public API
----------
* :func:`send_schema_editor_available_notification` — dispatches one
  email per TENANT_ADMIN of the given ``tenant`` through the existing
  ``hub.apps.notifications.tasks.send_email_async`` pipeline.
* :class:`NoTenantAdminsError` — raised when a tenant has no
  TENANT_ADMINs to notify (re-uses the same error type the Wave 0
  helper raises for consistency).

Design notes
------------
* Single tenant per call. The CLI / cron driver iterates tenants.
* Idempotency lives in the caller: a per-tenant audit-event check
  (``SCHEMA_EDITOR_AVAILABLE_NOTIFIED``) prevents the second send.
* Module-level imports — same pattern as
  :mod:`hub.apps.contracts.notifications.structureless` — so tests can
  patch ``send_email_async`` / ``get_tenant_admin_users`` at this
  module's path. Lazy in-function imports defeat that pattern.
* Fail-soft per recipient: a single misconfigured admin email must not
  block the rest of the notification batch.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

from django.conf import settings

from hub.apps.contracts.notifications.structureless import NoTenantAdminsError
from hub.apps.notifications.models import EmailType
from hub.apps.notifications.tasks import send_email_async
from hub.apps.users.services import get_tenant_admin_users

logger = logging.getLogger(__name__)


_DEFAULT_CONTRACT_HEALTH_URL = (
    "https://stagingmeshant-internal.example.com/admin/contract-health"
)


def send_schema_editor_available_notification(
    *,
    tenant: Any,
) -> list[dict[str, Any]]:
    """Dispatch the W2 T-0 email to every TENANT_ADMIN of *tenant*.

    Args:
        tenant: ``Tenant`` instance whose admins should be notified.

    Returns:
        One dict per **attempted** dispatch. Same shape as the Wave 0
        helper: ``to_email``, ``email_type``, ``success``, ``error``.

    Raises:
        NoTenantAdminsError: when the tenant has no TENANT_ADMIN users.
    """
    admins: Iterable[Any] = list(get_tenant_admin_users(tenant))
    if not admins:
        raise NoTenantAdminsError(
            f"Tenant {tenant.id} ({getattr(tenant, 'name', '?')}) has no "
            "TENANT_ADMIN users; cannot dispatch the W2 schema-editor "
            "announcement. Re-grant the role or re-invite the admin per "
            "the runbook before retrying."
        )

    contract_health_url = getattr(
        settings,
        "CONTRACT_HEALTH_PAGE_URL",
        _DEFAULT_CONTRACT_HEALTH_URL,
    )

    tenant_name = str(getattr(tenant, "name", "")) or "your tenant"
    tenant_id = str(getattr(tenant, "id", "")) or None
    subject = (
        f"Schema editor is now available in {tenant_name} — triage "
        "your contracts"
    )
    template_name = (
        "notifications/emails/schema_editor_available.html"
    )
    email_type_value = EmailType.SCHEMA_EDITOR_AVAILABLE.value

    dispatched: list[dict[str, Any]] = []
    for admin in admins:
        admin_email = getattr(admin, "email", None)
        if not admin_email:
            # Skip admins without an email — same fail-soft pattern as
            # the Wave 0 helper.
            continue

        context = {
            "tenant_name": tenant_name,
            "contract_health_url": contract_health_url,
            # ``admin_first_name`` is rendered in the greeting when
            # populated, otherwise the template falls back to "there".
            "admin_first_name": (
                getattr(admin, "first_name", None)
                or getattr(admin, "name", None)
                or ""
            ),
        }

        attempt: dict[str, Any] = {
            "to_email": admin_email,
            "email_type": email_type_value,
            "success": False,
            "error": None,
        }
        try:
            send_email_async(
                email_type=email_type_value,
                to_email=admin_email,
                subject=subject,
                template_name=template_name,
                context=context,
                tenant_id=tenant_id,
                user_id=str(getattr(admin, "id", "")) or None,
            )
            attempt["success"] = True
        except Exception as exc:
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "schema_editor_available_notification_send_failed",
                extra={
                    "tenant_id": tenant_id,
                    "to_email": admin_email,
                    "error": attempt["error"],
                },
            )
        dispatched.append(attempt)

    return dispatched
