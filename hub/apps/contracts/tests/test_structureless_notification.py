"""
Phase 227 Wave 0 (227.0.3) — tests for the
``asset.contract_structureless_pending`` T-14 notification.

These tests use real ``Tenant`` / ``User`` / ``Role`` rows (no mocks) and
exercise the helper that:

* finds every TENANT_ADMIN user in the affected tenant,
* builds the email context (contract list + Wave-5 deadline),
* enqueues an email per admin via the existing
  :func:`hub.apps.notifications.tasks.send_email_async` pipeline.

The async send itself is delivered via the existing email service
(SES/SendGrid/SMTP); these tests verify that the *enqueue path* runs
cleanly, the email-type registration is correct, and the rendered
template carries the operator-required fields. We do not mock the
template renderer — we let Django render the real HTML and assert key
substrings appear so future edits to copy don't silently drift.
"""

from __future__ import annotations

from datetime import UTC, timedelta

import pytest
from django.test import TestCase
from django.utils import timezone


def _create_tenant(name: str = "Wave 0 Notify Co"):
    from hub.apps.tenants.models import Tenant

    return Tenant.objects.create(name=name, slug=name.lower().replace(" ", "-"))


def _create_user(email: str, tenant):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create(email=email, tenant=tenant)


def _grant_tenant_admin_role(user, tenant):
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


def _create_contract(tenant, *, name: str | None = None):
    from hub.apps.contracts.models import Contract

    return Contract.objects.create(
        tenant=tenant,
        original_spec_type="ODCS",
        original_spec_version="3.1.0",
        original_format="YAML",
        original_raw=f"apiVersion: 3.0.0\nkind: DataContract\nname: {name or 'orders'}\n",
        hub_contract_json={"models": []},
        normalization_status="NORMALIZED_OK",
    )


# ---------------------------------------------------------------------------
# EmailType registration
# ---------------------------------------------------------------------------


def test_email_type_enum_includes_asset_contract_structureless_pending():
    from hub.apps.notifications.models import EmailType

    assert hasattr(EmailType, "ASSET_CONTRACT_STRUCTURELESS_PENDING"), (
        "EmailType enum must include ASSET_CONTRACT_STRUCTURELESS_PENDING"
    )
    # The value (DB-stored choice) is the stable identifier.
    assert EmailType.ASSET_CONTRACT_STRUCTURELESS_PENDING.value == (
        "ASSET_CONTRACT_STRUCTURELESS_PENDING"
    )


# ---------------------------------------------------------------------------
# Tenant-admin lookup
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TenantAdminLookupTests(TestCase):
    def test_get_tenant_admin_users_returns_only_admins(self):
        from hub.apps.users.services import get_tenant_admin_users

        tenant = _create_tenant()
        admin = _create_user("admin@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        plain = _create_user("plain@example.com", tenant)  # no role

        admins = list(get_tenant_admin_users(tenant))
        assert admin in admins
        assert plain not in admins

    def test_get_tenant_admin_users_isolates_per_tenant(self):
        from hub.apps.users.services import get_tenant_admin_users

        t1 = _create_tenant("Co A")
        t2 = _create_tenant("Co B")
        admin_a = _create_user("a@example.com", t1)
        admin_b = _create_user("b@example.com", t2)
        _grant_tenant_admin_role(admin_a, t1)
        _grant_tenant_admin_role(admin_b, t2)

        admins_a = list(get_tenant_admin_users(t1))
        admins_b = list(get_tenant_admin_users(t2))
        assert admin_a in admins_a and admin_b not in admins_a
        assert admin_b in admins_b and admin_a not in admins_b

    def test_get_tenant_admin_users_dedupes_multiple_user_role_rows(self):
        """A user with two UserRole rows (e.g. legacy duplicate) should
        appear once in the result.
        """
        from hub.apps.users.models import Role, UserRole
        from hub.apps.users.services import get_tenant_admin_users

        tenant = _create_tenant()
        admin = _create_user("admin@example.com", tenant)
        role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
        UserRole.objects.get_or_create(user=admin, tenant=tenant, role=role)
        # Force a second user_role row to simulate historical duplicate.
        second_role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN_SCOPED")
        UserRole.objects.get_or_create(user=admin, tenant=tenant, role=second_role)
        admins = list(get_tenant_admin_users(tenant))
        assert admins.count(admin) == 1


# ---------------------------------------------------------------------------
# Notification helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class NotifyTenantAdminsTests(TestCase):
    def test_helper_dispatches_one_email_per_admin(self):
        """Every tenant admin gets exactly one email — no admin gets two,
        and no non-admin user receives an email.
        """
        from hub.apps.contracts.notifications.structureless import (
            send_structureless_contract_pending_notification,
        )

        tenant = _create_tenant()
        admin1 = _create_user("admin1@example.com", tenant)
        admin2 = _create_user("admin2@example.com", tenant)
        plain = _create_user("plain@example.com", tenant)
        _grant_tenant_admin_role(admin1, tenant)
        _grant_tenant_admin_role(admin2, tenant)

        contract = _create_contract(tenant)
        deadline = timezone.now() + timedelta(days=14)

        # Helper SHALL return per-admin dispatch records and SHALL NOT
        # raise even if the underlying email service is unconfigured —
        # it queues; delivery is async.
        results = send_structureless_contract_pending_notification(
            tenant=tenant,
            structureless_contracts=[contract],
            deadline=deadline,
        )

        recipients = sorted(r["to_email"] for r in results)
        assert recipients == ["admin1@example.com", "admin2@example.com"]
        assert plain.email not in recipients

    def test_helper_raises_when_no_admins_exist(self):
        """The helper must surface a clear error if a tenant has no
        TENANT_ADMIN — silently dropping the notification would mask the
        Wave 0 deadline."""
        from hub.apps.contracts.notifications.structureless import (
            NoTenantAdminsError,
            send_structureless_contract_pending_notification,
        )

        tenant = _create_tenant()
        contract = _create_contract(tenant)
        deadline = timezone.now() + timedelta(days=14)

        with pytest.raises(NoTenantAdminsError):
            send_structureless_contract_pending_notification(
                tenant=tenant,
                structureless_contracts=[contract],
                deadline=deadline,
            )

    def test_helper_emits_email_type_constant(self):
        """Each enqueued email must use the canonical EmailType so
        delivery records are queryable by purpose."""
        from hub.apps.contracts.notifications.structureless import (
            send_structureless_contract_pending_notification,
        )
        from hub.apps.notifications.models import EmailType

        tenant = _create_tenant()
        admin = _create_user("admin@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        contract = _create_contract(tenant)
        deadline = timezone.now() + timedelta(days=14)

        results = send_structureless_contract_pending_notification(
            tenant=tenant,
            structureless_contracts=[contract],
            deadline=deadline,
        )
        assert results
        for r in results:
            assert r["email_type"] == (EmailType.ASSET_CONTRACT_STRUCTURELESS_PENDING.value)


# ---------------------------------------------------------------------------
# Email template rendering
# ---------------------------------------------------------------------------


def test_template_renders_with_required_substrings():
    """Rendering against a real Django template — no mocks. Asserts the
    operator-required substrings (deadline, contract list header,
    schema-editor link) appear so future copy edits don't silently drop
    critical instruction.

    The Schema-editor URL is now pre-rendered per-contract (see
    `_summarise_contract`) instead of substituted in the template,
    because Django has no built-in string-substitution filter.
    """
    from datetime import datetime

    from hub.apps.notifications.templates import render_email_template

    deadline = datetime(2026, 5, 14, 23, 59, tzinfo=UTC)
    rendered = render_email_template(
        "notifications/emails/asset_contract_structureless_pending.html",
        {
            "tenant_name": "Wave 0 Co",
            "contracts": [
                {
                    "id": "c-1",
                    "name": "orders",
                    "spec_type": "ODCS",
                    "schema_editor_url": (
                        "https://stagingmeshant-internal.example.com/contracts/c-1/edit?tab=schema"
                    ),
                },
                {
                    "id": "c-2",
                    "name": "users",
                    "spec_type": "ODPS",
                    "schema_editor_url": (
                        "https://stagingmeshant-internal.example.com/contracts/c-2/edit?tab=schema"
                    ),
                },
            ],
            "deadline_iso": deadline.strftime("%Y-%m-%d"),
        },
    )

    html = rendered["html"]
    assert "Wave 0 Co" in html
    assert "orders" in html
    assert "users" in html
    assert "2026-05-14" in html, "deadline must appear in human-readable form"
    # Anchor instruction must reference the schema editor explicitly.
    assert "schema" in html.lower()


def test_template_renders_per_contract_schema_editor_url_correctly():
    """Regression — the prior implementation used a Django template
    `cut|add` filter chain that produced malformed URLs (contract id
    appended at the END of the URL instead of substituted in place).

    This test ensures every contract's `schema_editor_url` appears
    intact in the rendered HTML, with the contract ID in the correct
    URL path position.
    """

    from hub.apps.notifications.templates import render_email_template

    rendered = render_email_template(
        "notifications/emails/asset_contract_structureless_pending.html",
        {
            "tenant_name": "Acme",
            "contracts": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "name": "orders",
                    "spec_type": "ODCS",
                    "schema_editor_url": (
                        "https://stagingmeshant-internal.example.com/contracts/"
                        "11111111-1111-1111-1111-111111111111/edit?tab=schema"
                    ),
                },
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "name": "users",
                    "spec_type": "ODPS",
                    "schema_editor_url": (
                        "https://stagingmeshant-internal.example.com/contracts/"
                        "22222222-2222-2222-2222-222222222222/edit?tab=schema"
                    ),
                },
            ],
            "deadline_iso": "2026-05-14",
        },
    )
    html = rendered["html"]

    # Each contract's URL appears verbatim — UUID in path, NOT appended
    # at the end of "{contract_id}" placeholder.
    assert (
        "https://stagingmeshant-internal.example.com/contracts/"
        "11111111-1111-1111-1111-111111111111/edit?tab=schema"
    ) in html
    assert (
        "https://stagingmeshant-internal.example.com/contracts/"
        "22222222-2222-2222-2222-222222222222/edit?tab=schema"
    ) in html
    # Hard regression: the literal placeholder must NOT appear.
    assert "{contract_id}" not in html


def test_dispatcher_pre_renders_schema_editor_url_per_contract():
    """End-to-end check that `_summarise_contract` (called by the
    dispatcher) substitutes `{contract_id}` correctly, not via filter chain.
    """
    from hub.apps.contracts.notifications.structureless import (
        _summarise_contract,
    )

    class _FakeContract:
        def __init__(self, cid, raw):
            self.id = cid
            self.original_spec_type = "ODCS"
            self.hub_contract_json = raw

    summary = _summarise_contract(
        _FakeContract("abc-123", {"info": {"name": "orders"}}),
        schema_editor_url_template=("https://example.com/contracts/{contract_id}/edit?tab=schema"),
    )
    assert summary["id"] == "abc-123"
    assert summary["schema_editor_url"] == ("https://example.com/contracts/abc-123/edit?tab=schema")
    # Hard regression: placeholder must be substituted, not appended.
    assert "{contract_id}" not in summary["schema_editor_url"]
