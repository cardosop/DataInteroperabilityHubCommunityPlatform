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
import logging
from collections.abc import Iterable, Sequence
from typing import Any

from django.conf import settings

# Module-level imports (NOT lazy) so external callers / tests can patch
# `send_email_async` and `get_tenant_admin_users` at the dispatcher's
# module path — which is the canonical mock-target convention. Lazy
# in-function imports defeat that pattern (the attribute doesn't exist
# on the module dict).
from hub.apps.notifications.models import EmailType
from hub.apps.notifications.tasks import send_email_async
from hub.apps.users.services import get_tenant_admin_users

logger = logging.getLogger(__name__)


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
    raise TypeError(f"deadline must be a datetime or date instance; got {type(deadline).__name__}")


def _summarise_contract(
    contract: Any,
    *,
    schema_editor_url_template: str,
) -> dict[str, str]:
    """Build the per-contract row used in the email template context.

    The summary intentionally avoids exposing customer-data values
    (only contract identity + spec metadata). The Schema-editor URL
    is **pre-rendered here** rather than substituted in the Django
    template — Django has no built-in string-substitution filter, and
    the prior `cut|add` chain produced a malformed URL with the
    contract ID at the wrong position.
    """
    payload = getattr(contract, "hub_contract_json", None) or {}
    info = payload.get("info") if isinstance(payload, dict) else None
    name = (info.get("name") if isinstance(info, dict) else None) or ""
    contract_id = str(contract.id)
    return {
        "id": contract_id,
        "name": str(name),
        "spec_type": str(getattr(contract, "original_spec_type", "")),
        "schema_editor_url": schema_editor_url_template.replace("{contract_id}", contract_id),
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
        List of dicts, one per **attempted** dispatch. Each dict contains
        ``to_email`` (recipient address), ``email_type`` (canonical type
        constant), ``success`` (bool), and ``error`` (str or None when
        success). Recording attempts (not just successes) is important
        for the audit trail: ops needs to see "we tried, it failed
        because X" not silent dropping.

    Raises:
        NoTenantAdminsError: when the tenant has no TENANT_ADMIN users.
    """
    admins: Iterable[Any] = list(get_tenant_admin_users(tenant))
    if not admins:
        raise NoTenantAdminsError(
            f"Tenant {tenant.id} ({getattr(tenant, 'name', '?')}) has no "
            "TENANT_ADMIN users; cannot dispatch the structureless-"
            "contract heads-up notification. Re-grant the role or "
            "re-invite the admin per the runbook before retrying."
        )

    deadline_iso = _format_deadline(deadline)
    schema_editor_url_template = getattr(
        settings,
        "STRUCTURELESS_CONTRACT_SCHEMA_EDITOR_URL_TEMPLATE",
        _DEFAULT_SCHEMA_EDITOR_URL,
    )
    contract_summaries = [
        _summarise_contract(c, schema_editor_url_template=schema_editor_url_template)
        for c in structureless_contracts
    ]

    subject = (
        f"Action required: data contract structure missing in "
        f"{getattr(tenant, 'name', 'your tenant')}"
    )

    template_name = "notifications/emails/asset_contract_structureless_pending.html"

    email_type_value = EmailType.ASSET_CONTRACT_STRUCTURELESS_PENDING.value
    tenant_id = str(getattr(tenant, "id", "")) or None
    tenant_name = str(getattr(tenant, "name", "")) or "your tenant"

    dispatched: list[dict[str, Any]] = []
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
            # Fail-soft per recipient: a single misconfigured email
            # address must not stop the others from being notified.
            # The underlying pipeline already logs the failure; we
            # additionally record the error in the audit trail so ops
            # can see "we tried, it failed" rather than silent drops.
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "structureless_contract_notification_send_failed",
                extra={
                    "tenant_id": tenant_id,
                    "to_email": admin_email,
                    "error": attempt["error"],
                },
            )

        dispatched.append(attempt)

    return dispatched
