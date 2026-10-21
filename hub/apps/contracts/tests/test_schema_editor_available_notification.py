"""
Phase 227 Wave 2 (227.W2.3) — T-0 ``SCHEMA_EDITOR_AVAILABLE`` notification.

Pins the helper that announces the Schema editor's GA to every
TENANT_ADMIN of a given tenant. Mirrors the test pattern from the
Wave 0 ``ASSET_CONTRACT_STRUCTURELESS_PENDING`` helper:

* Email type registered in ``EmailType``.
* Tenant-admin lookup honoured.
* One email per admin, none for non-admin users.
* Per-recipient fail-soft: a single broken email address must not
  block the rest of the batch.
* Template renders with the operator-required substrings (tenant
  name, Contract Health link).

No mocks of internal code paths — the helper calls the real
``send_email_async`` pipeline; the test container's email backend is a
no-op so dispatches succeed without actually sending.
"""

from __future__ import annotations

import pytest
from django.test import TestCase


def _create_tenant(name: str = "Wave 2 Co"):
    from hub.apps.tenants.models import Tenant

    return Tenant.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
    )


def _create_user(email: str, tenant):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create(email=email, tenant=tenant)


def _grant_tenant_admin_role(user, tenant):
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


# ---------------------------------------------------------------------------
# EmailType registration
# ---------------------------------------------------------------------------


def test_email_type_enum_includes_schema_editor_available():
    from hub.apps.notifications.models import EmailType

    assert hasattr(EmailType, "SCHEMA_EDITOR_AVAILABLE"), (
        "EmailType enum must include SCHEMA_EDITOR_AVAILABLE"
    )
    assert EmailType.SCHEMA_EDITOR_AVAILABLE.value == "SCHEMA_EDITOR_AVAILABLE"


# ---------------------------------------------------------------------------
# Notification helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class SchemaEditorAvailableNotifyTests(TestCase):
    def test_dispatches_one_email_per_tenant_admin(self):
        from hub.apps.contracts.notifications.schema_editor_available import (
            send_schema_editor_available_notification,
        )

        tenant = _create_tenant()
        admin1 = _create_user("admin1@example.com", tenant)
        admin2 = _create_user("admin2@example.com", tenant)
        plain = _create_user("plain@example.com", tenant)
        _grant_tenant_admin_role(admin1, tenant)
        _grant_tenant_admin_role(admin2, tenant)

        results = send_schema_editor_available_notification(tenant=tenant)

        recipients = sorted(r["to_email"] for r in results)
        self.assertEqual(
            recipients,
            ["admin1@example.com", "admin2@example.com"],
        )
        self.assertNotIn(plain.email, recipients)

    def test_helper_raises_when_no_admins_exist(self):
        from hub.apps.contracts.notifications.schema_editor_available import (
            send_schema_editor_available_notification,
        )
        from hub.apps.contracts.notifications.structureless import (
            NoTenantAdminsError,
        )

        tenant = _create_tenant("No Admins Co")
        with pytest.raises(NoTenantAdminsError):
            send_schema_editor_available_notification(tenant=tenant)

    def test_emits_email_type_constant(self):
        from hub.apps.contracts.notifications.schema_editor_available import (
            send_schema_editor_available_notification,
        )
        from hub.apps.notifications.models import EmailType

        tenant = _create_tenant("Email Type Co")
        admin = _create_user("admin@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)

        results = send_schema_editor_available_notification(tenant=tenant)
        self.assertTrue(results)
        for r in results:
            self.assertEqual(
                r["email_type"],
                EmailType.SCHEMA_EDITOR_AVAILABLE.value,
            )

    def test_per_recipient_failure_does_not_block_remaining_admins(self):
        """W2.3-AUDIT-3 regression guard: a single failing email
        address must not stop the rest of the batch.

        Exercises the helper's documented fail-soft contract by patching
        ``send_email_async`` to raise on the first call and succeed on
        the second. Both attempts must appear in the result list (one
        marked failed, one marked success) — the historical regression
        was a try/except wrapping the *whole* loop, which silently
        dropped every admin after the first failure.
        """
        from unittest.mock import patch

        from hub.apps.contracts.notifications import (
            schema_editor_available as mod,
        )

        tenant = _create_tenant("FailSoft Co")
        bad = _create_user("bad@example.com", tenant)
        good = _create_user("good@example.com", tenant)
        _grant_tenant_admin_role(bad, tenant)
        _grant_tenant_admin_role(good, tenant)

        call_log: list[str] = []

        def _fake_send(**kwargs):
            recipient = kwargs["to_email"]
            call_log.append(recipient)
            if recipient == "bad@example.com":
                raise RuntimeError("simulated SES outage for this recipient")
            return {"success": True, "delivery_id": "fake"}

        with patch.object(mod, "send_email_async", side_effect=_fake_send):
            results = mod.send_schema_editor_available_notification(
                tenant=tenant,
            )

        # Both admins must have been *attempted* — the failure on `bad`
        # MUST NOT stop the batch from reaching `good`.
        self.assertEqual(sorted(call_log), ["bad@example.com", "good@example.com"])
        # And both attempts must surface in the return list with the
        # right success / error annotations.
        self.assertEqual(len(results), 2)
        by_email = {r["to_email"]: r for r in results}
        self.assertFalse(by_email["bad@example.com"]["success"])
        self.assertIn(
            "RuntimeError",
            by_email["bad@example.com"]["error"],
        )
        self.assertTrue(by_email["good@example.com"]["success"])
        self.assertIsNone(by_email["good@example.com"]["error"])


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def test_template_renders_with_required_substrings():
    from hub.apps.notifications.templates import render_email_template

    rendered = render_email_template(
        "notifications/emails/schema_editor_available.html",
        {
            "tenant_name": "Wave 2 Co",
            "contract_health_url": "https://stagingmeshant-internal.example.com/admin/contract-health",
            "admin_first_name": "Alex",
        },
    )
    html = rendered["html"]
    assert "Wave 2 Co" in html
    assert "Schema editor" in html
    assert "Contract Health" in html
    # The CTA link must appear verbatim.
    assert "https://stagingmeshant-internal.example.com/admin/contract-health" in html
    # First-name personalisation when supplied.
    assert "Alex" in html
