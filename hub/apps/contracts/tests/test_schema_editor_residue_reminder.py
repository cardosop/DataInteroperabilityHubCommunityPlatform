"""
Phase 227 Wave 4 (227.W4.2) — T+7 residue reminder helper tests.

Mirrors the W2.3 ``schema_editor_available`` test pattern:

* EmailType registered.
* Tenant-admin lookup honoured; one email per admin.
* No-admin tenant raises ``NoTenantAdminsError``.
* Per-recipient fail-soft (the W2.3-AUDIT-3 regression we already
  pinned for the W2 helper applies equally here).
* Template renders with the operator-required substrings (tenant
  name, deadline, residue contract names, schema-editor links).

No mocks of internal code paths; the email pipeline is intercepted
at the helper-module's ``send_email_async`` symbol — the canonical
patch target the other helpers' tests already use.
"""

from __future__ import annotations

import datetime as _dt
import uuid

import pytest
from django.test import TestCase


def _create_tenant(name: str = "Wave 4 Co"):
    from hub.apps.tenants.models import Tenant

    return Tenant.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6],
    )


def _create_user(email: str, tenant):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create(email=email, tenant=tenant)


def _grant_tenant_admin(user, tenant):
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


def _create_contract(tenant, *, name: str = "orders"):
    from hub.apps.contracts.models import (
        Contract,
        ContractStatus,
        OriginalFormat,
        OriginalSpecType,
    )

    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json={"info": {"name": name}, "models": [], "schema": {"fields": []}},
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.DRAFT,
    )


# ---------------------------------------------------------------------------
# EmailType registration
# ---------------------------------------------------------------------------


def test_email_type_enum_includes_schema_editor_residue_reminder():
    from hub.apps.notifications.models import EmailType

    assert hasattr(EmailType, "SCHEMA_EDITOR_RESIDUE_REMINDER")
    assert EmailType.SCHEMA_EDITOR_RESIDUE_REMINDER.value == ("SCHEMA_EDITOR_RESIDUE_REMINDER")


# ---------------------------------------------------------------------------
# Helper behaviour
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class SchemaEditorResidueReminderTests(TestCase):
    def test_dispatches_one_email_per_tenant_admin(self):
        from hub.apps.contracts.notifications.schema_editor_residue_reminder import (
            send_schema_editor_residue_reminder,
        )

        tenant = _create_tenant()
        admin1 = _create_user("admin1@example.com", tenant)
        admin2 = _create_user("admin2@example.com", tenant)
        plain = _create_user("plain@example.com", tenant)
        _grant_tenant_admin(admin1, tenant)
        _grant_tenant_admin(admin2, tenant)
        contract = _create_contract(tenant, name="orders")

        results = send_schema_editor_residue_reminder(
            tenant=tenant,
            structureless_contracts=[contract],
            deadline=_dt.date.today() + _dt.timedelta(days=30),
        )

        recipients = sorted(r["to_email"] for r in results)
        self.assertEqual(
            recipients,
            ["admin1@example.com", "admin2@example.com"],
        )
        self.assertNotIn(plain.email, recipients)

    def test_helper_raises_when_no_admins_exist(self):
        from hub.apps.contracts.notifications.schema_editor_residue_reminder import (
            NoTenantAdminsError,
            send_schema_editor_residue_reminder,
        )

        tenant = _create_tenant("No Admins Co")
        with pytest.raises(NoTenantAdminsError):
            send_schema_editor_residue_reminder(
                tenant=tenant,
                structureless_contracts=[],
                deadline=_dt.date.today() + _dt.timedelta(days=30),
            )

    def test_per_recipient_failure_does_not_block_remaining_admins(self):
        """W2.3-AUDIT-3 fail-soft regression — applies equally here."""
        from unittest.mock import patch

        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as mod,
        )

        tenant = _create_tenant("FailSoft 4 Co")
        bad = _create_user("bad@example.com", tenant)
        good = _create_user("good@example.com", tenant)
        _grant_tenant_admin(bad, tenant)
        _grant_tenant_admin(good, tenant)
        contract = _create_contract(tenant, name="orders")

        attempted: list[str] = []

        def _fake_send(**kwargs):
            attempted.append(kwargs["to_email"])
            if kwargs["to_email"] == "bad@example.com":
                raise RuntimeError("simulated SES outage")
            return {"success": True, "delivery_id": "x"}

        with patch.object(mod, "send_email_async", side_effect=_fake_send):
            results = mod.send_schema_editor_residue_reminder(
                tenant=tenant,
                structureless_contracts=[contract],
                deadline=_dt.date.today() + _dt.timedelta(days=30),
            )

        self.assertEqual(
            sorted(attempted),
            ["bad@example.com", "good@example.com"],
        )
        by_email = {r["to_email"]: r for r in results}
        self.assertFalse(by_email["bad@example.com"]["success"])
        self.assertTrue(by_email["good@example.com"]["success"])

    def test_emits_email_type_constant(self):
        from hub.apps.contracts.notifications.schema_editor_residue_reminder import (
            send_schema_editor_residue_reminder,
        )
        from hub.apps.notifications.models import EmailType

        tenant = _create_tenant("Email Type 4")
        admin = _create_user("admin@example.com", tenant)
        _grant_tenant_admin(admin, tenant)
        contract = _create_contract(tenant)

        results = send_schema_editor_residue_reminder(
            tenant=tenant,
            structureless_contracts=[contract],
            deadline=_dt.date.today() + _dt.timedelta(days=30),
        )
        self.assertTrue(results)
        for r in results:
            self.assertEqual(
                r["email_type"],
                EmailType.SCHEMA_EDITOR_RESIDUE_REMINDER.value,
            )


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def test_template_renders_with_required_substrings():
    from hub.apps.notifications.templates import render_email_template

    rendered = render_email_template(
        "notifications/emails/schema_editor_residue_reminder.html",
        {
            "tenant_name": "Wave 4 Co",
            "deadline_iso": "2026-05-30",
            "contracts": [
                {
                    "id": "c-1",
                    "name": "orders",
                    "spec_type": "ODCS",
                    "schema_editor_url": (
                        "https://stagingmeshant-internal.example.com/contracts/c-1/edit?tab=schema"
                    ),
                },
            ],
            "contract_health_url": ("https://stagingmeshant-internal.example.com/admin/contract-health"),
            "admin_first_name": "Alex",
            "residue_count": 1,
        },
    )
    html = rendered["html"]
    assert "Wave 4 Co" in html
    assert "2026-05-30" in html
    assert "orders" in html
    assert "Open Schema editor" in html
    assert "STRUCTURELESS_CONTRACT" in html
    assert "Alex" in html
    assert "https://stagingmeshant-internal.example.com/contracts/c-1/edit?tab=schema" in html
