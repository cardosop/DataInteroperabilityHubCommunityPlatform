"""
Phase 270.D.3 — Tenant tax-id submission service.

Single seam between the tenants HTTP view and the Stripe Customer
``create_tax_id`` API. Keeping this out of the view lets the test
suite + the CLI/SDK reach the same code path; keeping it out of
``billing/services.py`` keeps the tenant-identity concern next to
the Tenant model rather than the Stripe billing surface.

Contract
========
``submit_tax_id_to_stripe`` is idempotent over the
(tenant, tax_id_value) pair — submitting the same value twice is
safe (Stripe returns the existing TaxID without creating a
duplicate). The local ``Tenant.tax_id`` column is updated with
the new value AND ``Tenant.tax_id_verified`` is reset to False
pending Stripe's verification webhook. ``Tenant.tax_address`` is
written through the encrypted-on-save path on ``Tenant.save()``.

Failures
========
Wraps Stripe-side errors in ``TaxIdSubmissionError`` so the view
layer can render a structured 400 without leaking the underlying
Stripe error class. Network / 5xx failures from Stripe also raise
the same wrapper class — operators read the cause from the
``stripe_error_code`` attribute.
"""
from __future__ import annotations
import logging
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class TaxIdSubmissionError(Exception):
    """Raised when ``stripe.Customer.create_tax_id`` fails.

    Carries ``stripe_error_code`` (the underlying Stripe error
    code, e.g. ``tax_id_invalid``) so callers can branch on the
    cause without grepping the message string.
    """

    def __init__(
        self,
        message: str,
        *,
        stripe_error_code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.stripe_error_code = stripe_error_code


def _stripe_customer_id_for_tenant(tenant) -> Optional[str]:
    """Resolve the Stripe Customer ID for a tenant.

    Uses the existing Subscription→Tenant chain (same as the
    billing webhook handlers). Returns None when the tenant has
    no Stripe Customer yet — the caller treats that as a
    bootstrap-not-complete condition and surfaces a structured
    error rather than calling Stripe with a None customer.
    """
    from hub.apps.billing.models import Subscription

    sub = (
        Subscription.objects
        .filter(tenant=tenant)
        .exclude(stripe_customer_id__isnull=True)
        .exclude(stripe_customer_id="")
        .order_by("-created_at")
        .first()
    )
    return sub.stripe_customer_id if sub else None


def submit_tax_id_to_stripe(
    *,
    tenant,
    tax_id_value: str,
    tax_id_type: str,
    tax_address: Optional[dict],
) -> dict[str, Any]:
    """Phase 270.D.3 — submit a tax_id to Stripe + persist locally.

    Parameters
    ----------
    tenant:
        The ``Tenant`` instance whose tax identity is being set.
    tax_id_value:
        The tenant's tax registration number (e.g.
        ``GB123456789``).
    tax_id_type:
        Stripe-vocabulary type (e.g. ``gb_vat``, ``eu_vat``).
    tax_address:
        Optional registered address dict. Encrypted on save via
        the Tenant model's ``save()`` override (Phase 211 KMS
        pattern).

    Returns
    -------
    dict
        ``{"stripe_tax_id_id": <id>}`` on success — the Stripe
        TaxID resource ID for downstream observability.

    Raises
    ------
    TaxIdSubmissionError
        On any Stripe-side failure OR when the tenant has no
        Stripe Customer yet (bootstrap not complete).
    """
    try:
        import stripe
    except ImportError as exc:
        raise TaxIdSubmissionError(
            "Stripe SDK not available",
            stripe_error_code="sdk_missing",
        ) from exc

    api_key = getattr(settings, "STRIPE_SECRET_KEY", None)
    if not api_key:
        raise TaxIdSubmissionError(
            "Stripe is not configured on this deployment",
            stripe_error_code="stripe_not_configured",
        )

    stripe_customer_id = _stripe_customer_id_for_tenant(tenant)
    if not stripe_customer_id:
        raise TaxIdSubmissionError(
            "Tenant has no Stripe Customer yet — create a "
            "subscription first.",
            stripe_error_code="customer_not_provisioned",
        )

    # Persist the LOCAL state FIRST (in a way that's revertible)
    # so a Stripe-side failure leaves the row in a consistent
    # "unverified, value-staged" state rather than half-applied.
    # tax_id_verified resets to False — Stripe's verification
    # webhook flips it to True later. tax_address (if present)
    # is encrypted on save by the Tenant.save() override.
    tenant.tax_id = tax_id_value
    tenant.tax_id_type = tax_id_type
    tenant.tax_id_verified = False
    if tax_address is not None:
        tenant.tax_address = tax_address
    tenant.save(update_fields=[
        "tax_id", "tax_id_type", "tax_id_verified",
        "tax_address", "updated_at",
    ])

    # Stripe call. Wrap in try/except + map to
    # TaxIdSubmissionError so the view layer doesn't import
    # stripe directly.
    try:
        result = stripe.Customer.create_tax_id(
            stripe_customer_id,
            type=tax_id_type,
            value=tax_id_value,
            api_key=api_key,
        )
    except Exception as exc:
        # Stripe raises a hierarchy of error classes (StripeError,
        # InvalidRequestError, etc.); we narrow on the
        # ``code`` attribute for forensics + map to a flat
        # error type for the view.
        code = getattr(exc, "code", None) or getattr(exc, "error_code", None)
        logger.warning(
            "stripe_create_tax_id_failed",
            tenant_id=str(tenant.id),
            stripe_customer_id=stripe_customer_id,
            tax_id_type=tax_id_type,
            stripe_error_code=code,
            error=str(exc),
        )
        raise TaxIdSubmissionError(
            f"Stripe rejected the tax_id submission: {exc}",
            stripe_error_code=code,
        ) from exc

    stripe_tax_id_id = getattr(result, "id", None) or (
        result.get("id") if isinstance(result, dict) else None
    )
    logger.info(
        "stripe_create_tax_id_ok",
        extra={
            "tenant_id": str(tenant.id),
            "stripe_customer_id": stripe_customer_id,
            "stripe_tax_id_id": stripe_tax_id_id,
            "tax_id_type": tax_id_type,
        },
    )
    return {"stripe_tax_id_id": stripe_tax_id_id}
