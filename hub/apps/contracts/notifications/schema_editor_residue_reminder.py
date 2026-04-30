"""
Phase 227 Wave 4 (227.W4.2) — T+7 residue reminder helper.

Sends a follow-up email to TENANT_ADMINs whose contracts are still
structureless one week after the Wave 2 GA announcement.  The body
lists every residue contract by name with a one-click deep-link into
the Schema editor and a 30-day deadline that matches the W4.3
escalation cron.

Public API
----------
* :func:`send_schema_editor_residue_reminder` — for a tenant + a
  list of residue contracts + a deadline, dispatches one email per
  TENANT_ADMIN through the existing ``send_email_async`` pipeline.
* :class:`NoTenantAdminsError` — re-exported from the Wave 0 helper
  so callers don't need to know the original module path.

Design notes
------------
* Module-level imports — same pattern as the Wave 0 helper.  Tests
  patch ``send_email_async`` at this module's path.
* Fail-soft per recipient: a single broken email address must not
  block the rest of the batch (W2.3-AUDIT-3 regression already pinned
  in our other helpers; this one carries the same contract).
* Contract summaries pre-render their Schema-editor URL so the
  Django template doesn't have to do string substitution (which it
  doesn't natively support).
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Iterable, Sequence

from django.conf import settings

from hub.apps.contracts.notifications.structureless import (
    NoTenantAdminsError,
)
from hub.apps.notifications.models import EmailType
from hub.apps.notifications.tasks import send_email_async
from hub.apps.users.services import get_tenant_admin_users

logger = logging.getLogger(__name__)


_DEFAULT_SCHEMA_EDITOR_URL = (
    "https://stagingmeshant-internal.example.com/contracts/{contract_id}/edit?tab=schema"
)
_DEFAULT_CONTRACT_HEALTH_URL = (
    "https://stagingmeshant-internal.example.com/admin/contract-health"
)


def _format_deadline(deadline: _dt.datetime | _dt.date) -> str:
    if isinstance(deadline, _dt.datetime):
        return deadline.date().isoformat()
    if isinstance(deadline, _dt.date):
        return deadline.isoformat()
    raise TypeError(
        "deadline must be a datetime or date instance; "
        f"got {type(deadline).__name__}"
    )


def _summarise_contract(
    contract: Any,
    *,
    schema_editor_url_template: str,
) -> dict[str, str]:
    payload = getattr(contract, "hub_contract_json", None) or {}
    info = payload.get("info") if isinstance(payload, dict) else None
    name = (info.get("name") if isinstance(info, dict) else None) or ""
    contract_id = str(contract.id)
    return {
        "id": contract_id,
        "name": str(name),
        "spec_type": str(getattr(contract, "original_spec_type", "")),
        "schema_editor_url": schema_editor_url_template.replace(
            "{contract_id}", contract_id
        ),
    }


def send_schema_editor_residue_reminder(
    *,
    tenant: Any,
    structureless_contracts: Sequence[Any],
    deadline: _dt.datetime | _dt.date,
) -> list[dict[str, Any]]:
    """Dispatch the W4 T+7 reminder email to every TENANT_ADMIN of *tenant*.

    Args:
        tenant: ``Tenant`` instance whose admins should be notified.
        structureless_contracts: Iterable of ``Contract`` rows still
            classified as structureless (caller drift-guards that
            list).  Embedded verbatim in the email body.
        deadline: Customer-facing remediation cutoff at which the
            W4.3 escalation runs.  Rendered as ``YYYY-MM-DD``.

    Returns:
        One dict per **attempted** dispatch:
        ``{"to_email", "email_type", "success", "error"}``.

    Raises:
        NoTenantAdminsError: when the tenant has no TENANT_ADMIN users.
    """
    admins: Iterable[Any] = list(get_tenant_admin_users(tenant))
    if not admins:
        raise NoTenantAdminsError(
            f"Tenant {tenant.id} ({getattr(tenant, 'name', '?')}) has no "
            "TENANT_ADMIN users; cannot dispatch the W4 residue "
            "reminder.  Re-grant the role or re-invite the admin per "
            "the runbook before retrying."
        )

    deadline_iso = _format_deadline(deadline)
    schema_editor_url_template = getattr(
        settings,
        "STRUCTURELESS_CONTRACT_SCHEMA_EDITOR_URL_TEMPLATE",
        _DEFAULT_SCHEMA_EDITOR_URL,
    )
    contract_health_url = getattr(
        settings,
        "CONTRACT_HEALTH_PAGE_URL",
        _DEFAULT_CONTRACT_HEALTH_URL,
    )
    contract_summaries = [
        _summarise_contract(
            c, schema_editor_url_template=schema_editor_url_template,
        )
        for c in structureless_contracts
    ]

    tenant_name = str(getattr(tenant, "name", "")) or "your tenant"
    tenant_id = str(getattr(tenant, "id", "")) or None
    subject = (
        f"Action required by {deadline_iso}: residue contracts in "
        f"{tenant_name}"
    )
    template_name = (
        "notifications/emails/schema_editor_residue_reminder.html"
    )
    email_type_value = EmailType.SCHEMA_EDITOR_RESIDUE_REMINDER.value

    dispatched: list[dict[str, Any]] = []
    for admin in admins:
        admin_email = getattr(admin, "email", None)
        if not admin_email:
            continue

        context = {
            "tenant_name": tenant_name,
            "deadline_iso": deadline_iso,
            "contracts": contract_summaries,
            "contract_health_url": contract_health_url,
            "admin_first_name": (
                getattr(admin, "first_name", None)
                or getattr(admin, "name", None)
                or ""
            ),
            "residue_count": len(contract_summaries),
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
                "schema_editor_residue_reminder_send_failed",
                extra={
                    "tenant_id": tenant_id,
                    "to_email": admin_email,
                    "error": attempt["error"],
                },
            )
        dispatched.append(attempt)

    return dispatched


__all__ = [
    "NoTenantAdminsError",
    "send_schema_editor_residue_reminder",
]
