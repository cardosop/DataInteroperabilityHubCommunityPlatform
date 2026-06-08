"""
Phase 270.D.3 — ``submit_tax_id_to_stripe`` service test.

Stripe SDK is the documented external boundary; we patch
``stripe.Customer.create_tax_id`` (the standard pattern this
codebase uses elsewhere — see ``test_seller_refund_endpoint.py``
for the precedent). The function under test is pure-Python
business logic ABOVE the Stripe boundary; we test it against
real Tenant + Subscription rows.
"""
from __future__ import annotations
import pytest

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from hub.apps.billing.models import Subscription
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan
from hub.apps.tenants.tax_id_service import (
    submit_tax_id_to_stripe,
    TaxIdSubmissionError,
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant_with_customer(
    *, stripe_customer_id: str = "cus_test_default",
) -> Tenant:
    sfx = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"T {sfx}",
        slug=f"taxid-{sfx}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    plan, _plan_created = TenantPlan.objects.get_or_create(
        slug=f"test-plan-{sfx}",
        defaults={
            "name": f"Test Plan {sfx}", "tier": PlanTier.FREE,
            "limits_json": {"max_assets": 100}, "is_active": True,
        },
    )
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=f"sub_{sfx}",
        status="active",
        current_period_start=datetime.now(tz=timezone.utc),
        current_period_end=datetime.now(tz=timezone.utc),
    )
    return tenant


@override_settings(STRIPE_SECRET_KEY="sk_test_seed")
@pytest.mark.integration
class TestSubmitTaxIdToStripe(TestCase):
    @pytest.mark.integration
    def test_happy_path_persists_locally_and_calls_stripe(self):
        tenant = _seed_tenant_with_customer(
            stripe_customer_id="cus_happy",
        )

        class _FakeTaxId:
            id = "txi_test_happy"

        with patch(
            "stripe.Customer.create_tax_id",
            return_value=_FakeTaxId(),
        ) as stripe_call:
            result = submit_tax_id_to_stripe(
                tenant=tenant,
                tax_id_value="GB123456789",
                tax_id_type="gb_vat",
                tax_address={"country": "GB", "postal_code": "SW1A 1AA"},
            )

        # Stripe call signature.
        stripe_call.assert_called_once_with(
            "cus_happy",
            type="gb_vat",
            value="GB123456789",
            api_key="sk_test_seed",
        )
        # Result carries the Stripe TaxID id.
        assert result["stripe_tax_id_id"] == "txi_test_happy"  # Local state persisted; tax_id_verified resets to False)
        # pending the verification webhook.
        tenant.refresh_from_db()
        assert tenant.tax_id == "GB123456789"
        assert tenant.tax_id_type == "gb_vat"
        assert not tenant.tax_id_verified
        # tax_address encrypted on save — decrypt via accessor.
        assert tenant.get_tax_address() == {
            "country": "GB", "postal_code": "SW1A 1AA",
        }

    @pytest.mark.integration
    def test_resubmission_resets_verified_to_false(self):
        """Submitting a NEW tax_id resets ``tax_id_verified``
        to False — the new value goes through Stripe's
        verification path before re-flipping to True."""
        tenant = _seed_tenant_with_customer(
            stripe_customer_id="cus_re",
        )
        # Pre-state: previously-verified ID on file.
        tenant.tax_id = "GB111111111"
        tenant.tax_id_type = "gb_vat"
        tenant.tax_id_verified = True
        tenant.save()

        class _FakeTaxId:
            id = "txi_re"

        with patch("stripe.Customer.create_tax_id", return_value=_FakeTaxId()):
            submit_tax_id_to_stripe(
                tenant=tenant,
                tax_id_value="GB222222222",  # new value
                tax_id_type="gb_vat",
                tax_address=None,
            )

        tenant.refresh_from_db()
        assert tenant.tax_id == "GB222222222"
        assert tenant.tax_id_verified is False  # reset!

    @pytest.mark.integration
    def test_raises_when_no_stripe_customer(self):
        """A tenant without a Stripe customer (subscription
        bootstrap not complete) gets a STRUCTURED error rather
        than a 500 from the Stripe SDK."""
        sfx = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T {sfx}",
            slug=f"noc-{sfx}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        with pytest.raises(TaxIdSubmissionError) as exc_info:
            submit_tax_id_to_stripe(
                tenant=tenant,
                tax_id_value="GB123456789",
                tax_id_type="gb_vat",
                tax_address=None,
            )
        assert exc_info.value.stripe_error_code == "customer_not_provisioned"

    @pytest.mark.integration
    def test_raises_when_stripe_rejects(self):
        """Stripe-side error → ``TaxIdSubmissionError`` with the
        underlying error code preserved on the wrapper class so
        callers can branch on the cause."""
        tenant = _seed_tenant_with_customer(
            stripe_customer_id="cus_reject",
        )

        class _StripeError(Exception):
            code = "tax_id_invalid"

        with patch(
            "stripe.Customer.create_tax_id",
            side_effect=_StripeError("Invalid VAT format"),
        ):
            with pytest.raises(TaxIdSubmissionError) as exc_info:
                submit_tax_id_to_stripe(
                    tenant=tenant,
                    tax_id_value="GBBADBAD",
                    tax_id_type="gb_vat",
                    tax_address=None,
                )
        assert exc_info.value.stripe_error_code == "tax_id_invalid"

    @override_settings(STRIPE_SECRET_KEY=None)
    @pytest.mark.integration
    def test_raises_when_stripe_not_configured(self):
        """No STRIPE_SECRET_KEY → fail fast with a structured
        error rather than calling Stripe with a None key."""
        tenant = _seed_tenant_with_customer(
            stripe_customer_id="cus_nokey",
        )
        with pytest.raises(TaxIdSubmissionError) as exc_info:
            submit_tax_id_to_stripe(
                tenant=tenant,
                tax_id_value="GB123456789",
                tax_id_type="gb_vat",
                tax_address=None,
            )
        assert exc_info.value.stripe_error_code == "stripe_not_configured"
