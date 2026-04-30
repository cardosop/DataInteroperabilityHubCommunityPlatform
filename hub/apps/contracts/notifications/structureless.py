"""
Phase 227 Wave 0 (227.0.3) — T-14 heads-up notification helper.

Public API
----------
* :func:`send_structureless_contract_pending_notification` — for a tenant
  + a list of structureless contracts + a deadline, dispatches one
  email per TENANT_ADMIN through the existing
  ``hub.apps.notifications.tasks.send_email_async`` pipeline.

* :class:`NoTenantAdminsError` — raised when a tenant has zero
  TENANT_ADMIN users. The Wave 0 deadline matters; silently dropping the
  notification would mask non-compliance until Wave 5 demoted assets.

Design notes
------------
* The helper does NOT mock the email service. It calls the real async
  send path, which is responsible for retries, delivery records, and
  channel routing (SES / SendGrid / SMTP).

* Each enqueued email carries the canonical
  ``EmailType.ASSET_CONTRACT_STRUCTURELESS_PENDING`` so DB queries on
  ``EmailDelivery.email_type`` can produce a Wave 0 audit trail.

* The deadline is rendered in YYYY-MM-DD form. Customers are spread
  across timezones; a date-only deadline avoids ambiguity.

* The Schema-editor URL template is read from settings
  (``STRUCTURELESS_CONTRACT_SCHEMA_EDITOR_URL_TEMPLATE``) with a sensible
  staging default, so ops can override per-environment without code
  edits.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Iterable, Sequence

from django.conf import settings


class NoTenantAdminsError(RuntimeError):
    """A tenant requires TENANT_ADMINs but has none.

    Surfacing this loudly is intentional — Wave 0's purpose is to give
    customers 14 days of notice. If no admin exists, ops must escalate
    via the runbook (re-invite, re-grant role) rather than continue.
    """


_DEFAULT_SCHEMA_EDITOR_URL = (
    "https://stagingmeshant-internal.example.com/contracts/{contract_id}/edit?tab=schema"
)


def _format_deadline(deadline: _dt.datetime | _dt.date) -> str:
    """Return the deadline in YYYY-MM-DD form."""
    if isinstance(deadline, _dt.datetime):
        return deadline.date().isoformat()
    if isinstance(deadline, _dt.date):
        return deadline.isoformat()
    raise TypeError(
        "deadline must be a datetime or date instance; "
        f"got {type(deadline).__name__}"
    )


def _summarise_contract(contract: Any) -> dict[str, str]:
    """Build the per-contract row used in the email template context.

    The summary intentionally avoids exposing customer-data values
    (only contract identity + spec metadata).
    """
    payload = getattr(contract, "hub_contract_json", None) or {}
    info = payload.get("info") if isinstance(payload, dict) else None
    name = (info.get("name") if isinstance(info, dict) else None) or ""
    return {
        "id": str(contract.id),
        "name": str(name),
        "spec_type": str(getattr(contract, "original_spec_type", "")),
    }


def send_structureless_contract_pending_notification(
    *,
    tenant: Any,
    structureless_contracts: Sequence[Any],
    deadline: _dt.datetime | _dt.date,
) -> list[dict[str, str]]:
    """Dispatch the T-14 heads-up email to every TENANT_ADMIN of *tenant*.

    Args:
        tenant: ``Tenant`` instance whose admins should be notified.
        structureless_contracts: Iterable of ``Contract`` rows already
            classified as structureless by
            :func:`hub.apps.contracts.structureless.is_structureless`.
            The list appears verbatim in the email body.
        deadline: The customer-facing remediation cutoff (Wave 5 hard
            cutover). Rendered as ``YYYY-MM-DD`` in the body.

    Returns:
        List of dicts, one per dispatched email, each containing
        ``to_email`` and ``email_type``. Useful for tests, audit logs,
        and the runbook's "I sent N notifications" verification step.

    Raises:
        NoTenantAdminsError: when the tenant has no TENANT_ADMIN users.
    """
    from hub.apps.notifications.models import EmailType
    from hub.apps.notifications.tasks import send_email_async
    from hub.apps.users.services import get_tenant_admin_users

    admins: Iterable[Any] = list(get_tenant_admin_users(tenant))
    if not admins:
        raise NoTenantAdminsError(
            f"Tenant {tenant.id} ({getattr(tenant, 'name', '?')}) has no "
            "TENANT_ADMIN users; cannot dispatch the structureless-"
            "contract heads-up notification. Re-grant the role or "
            "re-invite the admin per the runbook before retrying."
        )

    deadline_iso = _format_deadline(deadline)
    contract_summaries = [
        _summarise_contract(c) for c in structureless_contracts
    ]
    schema_editor_url_template = getattr(
        settings,
        "STRUCTURELESS_CONTRACT_SCHEMA_EDITOR_URL_TEMPLATE",
        _DEFAULT_SCHEMA_EDITOR_URL,
    )

    subject = (
        f"Action required: data contract structure missing in "
        f"{getattr(tenant, 'name', 'your tenant')}"
    )

    template_name = (
        "notifications/emails/asset_contract_structureless_pending.html"
    )

    email_type_value = EmailType.ASSET_CONTRACT_STRUCTURELESS_PENDING.value
    tenant_id = str(getattr(tenant, "id", "")) or None
    tenant_name = str(getattr(tenant, "name", "")) or "your tenant"

    dispatched: list[dict[str, str]] = []
    for admin in admins:
        admin_email = getattr(admin, "email", None)
        if not admin_email:
            # Skip admins without an email — they cannot be reached via
            # this channel. The runbook's verification step counts the
            # returned dispatched-count and will surface the discrepancy.
            continue

        context = {
            "tenant_name": tenant_name,
            "contracts": contract_summaries,
            "deadline_iso": deadline_iso,
            "schema_editor_url_template": schema_editor_url_template,
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
        except Exception:
            # Fail-soft per recipient: a single misconfigured email
            # address must not stop the others from being notified.
            # The underlying pipeline already logs the failure; the
            # runbook covers the audit-trail review.
            continue

        dispatched.append(
            {"to_email": admin_email, "email_type": email_type_value}
        )

    return dispatched
