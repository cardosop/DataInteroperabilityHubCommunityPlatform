"""Integration gates for Phase 232.1 (signup, marketplace orders, webhooks)."""

from __future__ import annotations
from hub.apps.consent.models import ConsentPurpose, ConsentRecord, ConsentRecordStatus
from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User

SIGNUP_PURPOSE_KEY = "signup.privacy"
MARKETPLACE_PURPOSE_KEY = "marketplace.access"
WEBHOOK_PURPOSE_KEY = "webhooks.subscription"


def _active_consent_qs(*, tenant_id, user_id, purpose_key: str):
    return ConsentRecord.objects.filter(
        tenant_id=tenant_id,
        user_id=user_id,
        purpose__key=purpose_key,
        purpose__is_active=True,
        status=ConsentRecordStatus.GRANTED,
    )


def user_has_active_consent(*, user: User, tenant: Tenant, purpose_key: str) -> bool:
    if not tenant.compliance_consent_enabled:
        return True
    return _active_consent_qs(
        tenant_id=tenant.id, user_id=user.id, purpose_key=purpose_key
    ).exists()


def enforce_signup_consent(*, tenant: Tenant, signup_consent: bool) -> None:
    if not tenant or not tenant.compliance_consent_enabled:
        return
    if not signup_consent:
        raise ValidationError(
            "signup_consent is required when compliance consent is enabled for this tenant.",
            code="SIGNUP_CONSENT_REQUIRED",
            details={"signup_consent": True},
        )
    if not ConsentPurpose.objects.filter(
        tenant=tenant, key=SIGNUP_PURPOSE_KEY, is_active=True
    ).exists():
        raise ValidationError(
            f"Consent purpose {SIGNUP_PURPOSE_KEY!r} is not configured for this tenant.",
            code="CONSENT_PURPOSE_NOT_CONFIGURED",
            details={"missing_key": SIGNUP_PURPOSE_KEY},
        )
    from hub.apps.consent.signing import get_signing_key_ring_for_tenant

    if not get_signing_key_ring_for_tenant(str(tenant.id)):
        raise ValidationError(
            "Consent signing keys are not configured for this tenant.",
            code="SIGNING_KEYS_MISSING",
        )


def enforce_marketplace_order_consent(*, user: User, tenant: Tenant) -> None:
    if not tenant.compliance_consent_enabled:
        return
    if not ConsentPurpose.objects.filter(
        tenant=tenant, key=MARKETPLACE_PURPOSE_KEY, is_active=True
    ).exists():
        raise ValidationError(
            f"Marketplace consent purpose {MARKETPLACE_PURPOSE_KEY!r} is not configured.",
            code="CONSENT_PURPOSE_NOT_CONFIGURED",
        )
    if not user_has_active_consent(user=user, tenant=tenant, purpose_key=MARKETPLACE_PURPOSE_KEY):
        raise ValidationError(
            "Active marketplace access consent is required.",
            code="CONSENT_REQUIRED",
            http_status=403,
        )


def enforce_webhook_subscription_consent(*, user: User, tenant: Tenant) -> None:
    if not tenant.compliance_consent_enabled:
        return
    if not ConsentPurpose.objects.filter(
        tenant=tenant, key=WEBHOOK_PURPOSE_KEY, is_active=True
    ).exists():
        raise ValidationError(
            f"Webhook subscription consent purpose {WEBHOOK_PURPOSE_KEY!r} is not configured.",
            code="CONSENT_PURPOSE_NOT_CONFIGURED",
        )
    if not user_has_active_consent(user=user, tenant=tenant, purpose_key=WEBHOOK_PURPOSE_KEY):
        raise ValidationError(
            "Active webhook subscription consent is required.",
            code="CONSENT_REQUIRED",
            http_status=403,
        )


def grant_signup_consent_after_registration(*, user: User, tenant: Tenant):
    """Create signup consent record after successful registration (internal helper)."""
    from hub.apps.consent.services import ConsentService

    if not tenant or not tenant.compliance_consent_enabled:
        return None
    purpose = ConsentPurpose.objects.filter(
        tenant=tenant, key=SIGNUP_PURPOSE_KEY, is_active=True
    ).first()
    if purpose is None:
        return None
    return ConsentService().grant(
        tenant=tenant,
        user=user,
        purpose=purpose,
        payload={"source": "signup", "channel": "registration"},
        actor_user=user,
    )
