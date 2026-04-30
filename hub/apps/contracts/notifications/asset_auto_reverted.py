"""
Phase 227 Wave 5 (227.W5.3) — per-asset auto-revert notification helper.

When the apply-asset-revert path demotes an asset to DRAFT
(``Command._maybe_revert_asset``), this helper notifies every
TENANT_ADMIN of the affected tenant — once via in-app
``UserNotification``, once via the email pipeline.

The notification is the customer's first visible signal that their
asset has changed status. The body lists the asset, the
structureless contract id, the previous status (so they know what
to restore to), and the deep-link to the Schema editor where they
can fix the contract.

Public API
----------
* :func:`send_asset_auto_reverted_notification` — for one demoted
  asset + the contract that caused it, dispatches one email +
  one in-app notification per TENANT_ADMIN.

Design notes
------------
* Best-effort: this helper is invoked from a management command
  whose load-bearing operation (the asset demotion) has already
  committed. A notification failure (SES outage, bad email, DB
  hiccup) MUST NOT roll back the demotion. The caller wraps
  the helper in try/except for that reason.
* Per-recipient fail-soft: a single broken email address must not
  block the rest of the batch (W2.3-AUDIT-3 contract carried over).
* Module-level imports — same pattern as the W0/W2/W4 helpers.
  Tests patch ``send_email_async`` and ``create_user_notification``
  at this module's path.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from hub.apps.contracts.notifications.structureless import (
    NoTenantAdminsError,
)
from hub.apps.notifications.models import (
    EmailType,
    NotificationCategory,
    NotificationType,
)
from hub.apps.notifications.tasks import send_email_async
from hub.apps.notifications.utils import create_user_notification
from hub.apps.users.services import get_tenant_admin_users

logger = logging.getLogger(__name__)


_DEFAULT_SCHEMA_EDITOR_URL = (
    "https://stagingmeshant-internal.example.com/contracts/{contract_id}/edit?tab=schema"
)
_DEFAULT_ASSET_URL = "https://stagingmeshant-internal.example.com/assets/{asset_id}"


def _schema_editor_url(contract_id: str) -> str:
    template = getattr(
        settings,
        "STRUCTURELESS_CONTRACT_SCHEMA_EDITOR_URL_TEMPLATE",
        _DEFAULT_SCHEMA_EDITOR_URL,
    )
    return template.replace("{contract_id}", str(contract_id))


def _asset_url(asset_id: str) -> str:
    template = getattr(settings, "ASSET_DETAIL_URL_TEMPLATE", _DEFAULT_ASSET_URL)
    return template.replace("{asset_id}", str(asset_id))


def send_asset_auto_reverted_notification(
    *,
    asset: Any,
    contract: Any,
    previous_status: str,
    run_id: str,
) -> list[dict[str, Any]]:
    """Dispatch the per-asset W5.3 notification to every TENANT_ADMIN
    of ``asset.tenant``.

    Args:
        asset: The freshly-demoted ``Asset`` row. ``asset.tenant`` is
            the recipient scope.
        contract: The structureless ``Contract`` row that caused the
            demotion. Its UUID + spec_type appear in the email body
            and the deep-link target.
        previous_status: The asset's status before demotion (e.g.
            ``"ACTIVE"``). Customers need this to know what to
            restore to once they've fixed the contract.
        run_id: The migration run identifier from the apply path.
            Embedded in the audit trail / payload so ops can correlate
            individual notifications back to the batch run.

    Returns:
        One dict per **attempted** dispatch:
        ``{"to_email", "email_type", "success", "error"}``.

    Raises:
        NoTenantAdminsError: when the asset's tenant has no
            TENANT_ADMIN users. Caller (the management command) is
            expected to catch and surface this — an asset-less
            tenant or a misconfigured tenant is an ops concern,
            not a hard failure for the migration as a whole.
    """
    tenant = getattr(asset, "tenant", None)
    if tenant is None:
        raise NoTenantAdminsError(
            f"Asset {asset.id} has no tenant; cannot dispatch W5.3 "
            "post-revert notification. Investigate orphaned asset row."
        )

    admins = list(get_tenant_admin_users(tenant))
    if not admins:
        raise NoTenantAdminsError(
            f"Tenant {tenant.id} ({getattr(tenant, 'name', '?')}) has no "
            "TENANT_ADMIN users; cannot dispatch the W5.3 post-revert "
            "notification. Re-grant the role or re-invite the admin per "
            "the runbook before retrying."
        )

    asset_id = str(asset.id)
    contract_id = str(contract.id)
    tenant_name = str(getattr(tenant, "name", "")) or "your tenant"
    tenant_id = str(getattr(tenant, "id", ""))
    asset_name = str(getattr(asset, "name", "") or asset_id)
    asset_key = str(getattr(asset, "key", "") or "")
    spec_type = str(getattr(contract, "original_spec_type", ""))

    schema_editor_url = _schema_editor_url(contract_id)
    asset_url_value = _asset_url(asset_id)

    subject = (
        f"[{tenant_name}] Asset \"{asset_name}\" auto-reverted to DRAFT — "
        f"action required"
    )
    template_name = "notifications/emails/asset_auto_reverted.html"
    email_type_value = EmailType.ASSET_AUTO_REVERTED_NOTIFICATION.value

    in_app_message = (
        f"Asset \"{asset_name}\" was auto-reverted from "
        f"{previous_status} to DRAFT because its active contract is "
        "structureless. Open the Schema editor on the contract to "
        "remediate, then restore the asset."
    )

    dispatched: list[dict[str, Any]] = []
    for admin in admins:
        admin_email = getattr(admin, "email", None)
        if not admin_email:
            continue

        # In-app notification — fail-soft via create_user_notification's
        # built-in exception swallow (returns None on failure). We log a
        # warning so ops can spot a broken inbox path.
        try:
            row = create_user_notification(
                user=admin,
                tenant=tenant,
                title=f"Asset auto-reverted: {asset_name}",
                message=in_app_message,
                notification_type=NotificationType.WARNING,
                category=NotificationCategory.GOVERNANCE,
                resource_type="ASSET",
                resource_id=asset_id,
            )
            if row is None:
                logger.warning(
                    "asset_auto_reverted_in_app_dropped",
                    extra={
                        "tenant_id": tenant_id,
                        "user_id": str(getattr(admin, "id", "")),
                        "asset_id": asset_id,
                    },
                )
        except Exception:  # noqa: BLE001 — best-effort
            logger.exception(
                "asset_auto_reverted_in_app_failed",
                extra={
                    "tenant_id": tenant_id,
                    "user_id": str(getattr(admin, "id", "")),
                    "asset_id": asset_id,
                },
            )

        # Email — same per-recipient fail-soft contract as the W0/W2/W4
        # helpers; one bad address must not block the rest of the batch.
        context = {
            "tenant_name": tenant_name,
            "asset_name": asset_name,
            "asset_id": asset_id,
            "asset_key": asset_key,
            "asset_url": asset_url_value,
            "contract_id": contract_id,
            "spec_type": spec_type,
            "previous_status": previous_status,
            "schema_editor_url": schema_editor_url,
            "run_id": run_id,
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
                tenant_id=tenant_id or None,
                user_id=str(getattr(admin, "id", "")) or None,
            )
            attempt["success"] = True
        except Exception as exc:
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "asset_auto_reverted_email_send_failed",
                extra={
                    "tenant_id": tenant_id,
                    "to_email": admin_email,
                    "asset_id": asset_id,
                    "error": attempt["error"],
                },
            )
        dispatched.append(attempt)

    return dispatched


__all__ = [
    "NoTenantAdminsError",
    "send_asset_auto_reverted_notification",
]
