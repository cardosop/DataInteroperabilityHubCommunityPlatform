"""
Phase 227 Wave 2 (227.W2.3 audit follow-up) — wave2 driver-command tests.

Pins the idempotent-batch dispatcher that ships the T-0 SCHEMA_EDITOR_AVAILABLE
announcement.  The deliverable is incomplete without this test surface
because the original implementation only shipped the per-tenant helper
— the audit found that ops had no way to actually run the W2.3
broadcast without a one-off shell script.

What we pin here
----------------
* Default scope: only tenants with structureless contracts get
  notified. A clean tenant is never emailed.
* ``--tenant-id`` selects a single row regardless of structureless-ness.
* ``--all-tenants`` broadcasts to every ACTIVE tenant.
* Idempotency: a tenant with a recent
  ``SCHEMA_EDITOR_AVAILABLE_NOTIFIED`` audit row is skipped.
* ``--force`` bypasses the idempotency check.
* Idempotency audit row is written when at least one admin receives
  the email — and NOT written when every dispatch failed (so a
  retry can self-heal a transient SES outage).
* ``--dry-run`` writes neither emails nor audit rows.
* No-admin tenant is skipped, not crashed.
* ``--audit-output`` writes a JSONL artefact with one line per
  dispatched recipient.

No mocks of internal code paths.  The email pipeline is intercepted at
the module-level ``send_email_async`` symbol in the helper module —
the same canonical patch target used by the helper's own tests.
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _create_tenant(slug_prefix: str = "w23d", *, status: str = "ACTIVE"):
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
        status=status,
    )


def _create_contract(tenant, *, hub_contract_json):
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
        hub_contract_json=hub_contract_json,
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.DRAFT,
    )


def _create_admin_user(email: str, tenant):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create(email=email, tenant=tenant)


def _grant_tenant_admin(user, tenant):
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


def _record_notified(tenant, *, when=None):
    """Write a SCHEMA_EDITOR_AVAILABLE_NOTIFIED audit row.

    Mirrors the timestamp-backdating dance the W2.4 fixture uses —
    ``AuditEvent.timestamp`` is ``auto_now_add=True`` so any value
    passed to ``create()`` is overridden by Django; backdating must
    go through a queryset UPDATE.
    """
    from hub.apps.audit.models import AuditEvent

    event = AuditEvent.objects.create(
        tenant=tenant,
        action="SCHEMA_EDITOR_AVAILABLE_NOTIFIED",
        resource_type="TENANT",
        resource_id=tenant.id,
        result="SUCCESS",
        details_json={"phase": "227.W2.3"},
    )
    if when is not None:
        AuditEvent.all_objects.filter(pk=event.pk).update(timestamp=when)
        event.refresh_from_db()
    return event


_HC_OK = {
    "models": [{"name": "m", "fields": [{"name": "id", "data_type": "string"}]}],
    "schema": {"fields": [{"name": "id", "data_type": "string"}]},
}
_HC_STRUCTURELESS = {"models": [], "schema": {"fields": []}}


# ---------------------------------------------------------------------------
# Driver-command tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class Wave2DriverScopeTests(TestCase):
    """The default scope must be 'tenants with structureless contracts'."""

    def setUp(self):
        """Purge contracts and notification audit rows from previous
        --reuse-db runs.  Users and tenants are preserved — deleting
        them causes FK cascade timeouts through access_logs.
        """
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import Contract

        Contract.objects.all().delete()
        AuditEvent.objects.filter(
            action="SCHEMA_EDITOR_AVAILABLE_NOTIFIED"
        ).delete()

    def test_default_scope_only_emails_structureless_tenants(self):
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        clean = _create_tenant("clean")
        _create_contract(clean, hub_contract_json=_HC_OK)
        _grant_tenant_admin(
            _create_admin_user("clean-admin@example.com", clean),
            clean,
        )

        broken = _create_tenant("broken")
        _create_contract(broken, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("broken-admin@example.com", broken),
            broken,
        )

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        out = io.StringIO()
        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                stdout=out,
            )

        # Only the structureless-tenant admin must have received an email.
        self.assertEqual(sent, ["broken-admin@example.com"])

    def test_all_tenants_flag_broadcasts_even_to_clean_tenants(self):
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        clean = _create_tenant("clean-bcast")
        _create_contract(clean, hub_contract_json=_HC_OK)
        _grant_tenant_admin(
            _create_admin_user("clean-bcast@example.com", clean),
            clean,
        )
        broken = _create_tenant("broken-bcast")
        _create_contract(broken, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("broken-bcast@example.com", broken),
            broken,
        )

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                "--all-tenants",
                stdout=io.StringIO(),
            )

        # With --reuse-db, pre-existing tenants also receive emails.
        # The invariant is that BOTH our test tenants appear in the
        # recipient list — the "clean" tenant proves --all-tenants
        # broadcasts even when the tenant has no structureless contracts.
        self.assertIn("broken-bcast@example.com", sent)
        self.assertIn("clean-bcast@example.com", sent)

    def test_tenant_id_flag_selects_single_tenant(self):
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        a = _create_tenant("a")
        _create_contract(a, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("a@example.com", a),
            a,
        )
        b = _create_tenant("b")
        _create_contract(b, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("b@example.com", b),
            b,
        )

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                f"--tenant-id={a.id}",
                stdout=io.StringIO(),
            )

        self.assertEqual(sent, ["a@example.com"])


@pytest.mark.django_db(transaction=True)
class Wave2DriverIdempotencyTests(TestCase):
    """A tenant with a recent NOTIFIED audit row must not be re-emailed."""

    def test_recent_notified_audit_row_skips_re_send(self):
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        tenant = _create_tenant("idem")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("idem-admin@example.com", tenant),
            tenant,
        )
        _record_notified(tenant)  # ← already notified

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                stdout=io.StringIO(),
            )
        self.assertEqual(sent, [])

    def test_force_flag_bypasses_idempotency_check(self):
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        tenant = _create_tenant("force")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("force-admin@example.com", tenant),
            tenant,
        )
        _record_notified(tenant)

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                "--force",
                stdout=io.StringIO(),
            )
        self.assertEqual(sent, ["force-admin@example.com"])

    def test_old_notified_audit_row_outside_window_does_not_block(self):
        """A NOTIFIED row older than --idempotency-days does NOT block
        a re-run — the field is a sliding window, not a permanent
        marker, so a re-rollout (e.g. v2 of the editor) can re-notify
        without manual cleanup."""
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        tenant = _create_tenant("stale-idem")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("stale-idem@example.com", tenant),
            tenant,
        )
        # Backdate the NOTIFIED row 200 days — well past the default
        # 90-day idempotency window.
        _record_notified(tenant, when=timezone.now() - timedelta(days=200))

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                stdout=io.StringIO(),
            )
        self.assertEqual(sent, ["stale-idem@example.com"])

    def test_successful_send_records_notified_audit_row(self):
        """The driver writes the idempotency audit row exactly once
        per successful run — that row is what the next run reads."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        tenant = _create_tenant("audit-row")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("ar@example.com", tenant),
            tenant,
        )

        before = AuditEvent.objects.filter(
            tenant=tenant,
            action="SCHEMA_EDITOR_AVAILABLE_NOTIFIED",
        ).count()

        with patch.object(
            helper_mod,
            "send_email_async",
            return_value={"success": True, "delivery_id": "x"},
        ):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                stdout=io.StringIO(),
            )

        after = AuditEvent.objects.filter(
            tenant=tenant,
            action="SCHEMA_EDITOR_AVAILABLE_NOTIFIED",
        ).count()
        self.assertEqual(after, before + 1)

    def test_full_failure_batch_does_not_record_notified_audit_row(self):
        """If every dispatch in the batch failed (transient SES outage),
        the idempotency row MUST NOT be written — otherwise a re-run
        would skip the tenant and leave them un-notified forever."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        tenant = _create_tenant("all-fail")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("all-fail@example.com", tenant),
            tenant,
        )

        with patch.object(
            helper_mod,
            "send_email_async",
            side_effect=RuntimeError("simulated SES outage"),
        ):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                stdout=io.StringIO(),
            )

        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="SCHEMA_EDITOR_AVAILABLE_NOTIFIED",
            ).count(),
            0,
            "An idempotency row written after an all-failed batch would "
            "leave the tenant un-notified-for-real on the next retry.",
        )


@pytest.mark.django_db(transaction=True)
class Wave2DriverDryRunAndSafetyTests(TestCase):
    def test_dry_run_writes_neither_emails_nor_audit_rows(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        tenant = _create_tenant("dry")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("dry@example.com", tenant),
            tenant,
        )

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        out = io.StringIO()
        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                "--dry-run",
                stdout=out,
            )

        self.assertEqual(sent, [])
        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="SCHEMA_EDITOR_AVAILABLE_NOTIFIED",
            ).count(),
            0,
        )
        self.assertIn("[dry-run]", out.getvalue())

    def test_no_admin_tenant_is_skipped_not_crashed(self):
        """A tenant with zero TENANT_ADMINs surfaces as a warning and
        the loop continues — the Wave 0 convention.  Without this
        invariant a single mis-configured tenant would block the
        broadcast for every other tenant."""
        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        no_admin = _create_tenant("no-admin")
        _create_contract(no_admin, hub_contract_json=_HC_STRUCTURELESS)
        # No admin granted

        ok = _create_tenant("ok")
        _create_contract(ok, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("ok@example.com", ok),
            ok,
        )

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        out = io.StringIO()
        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                stdout=out,
            )

        self.assertEqual(sent, ["ok@example.com"])
        self.assertIn("[skipped-no-admin]", out.getvalue())

    def test_audit_output_writes_jsonl(self):
        """``--audit-output`` produces a JSONL artefact with one row
        per dispatch, matching the Wave 0 convention so cross-channel
        verification queries work for either rollout."""
        import tempfile

        from hub.apps.contracts.notifications import (
            schema_editor_available as helper_mod,
        )

        tenant = _create_tenant("audit-jsonl")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(
            _create_admin_user("audit-jsonl@example.com", tenant),
            tenant,
        )

        tmpdir = Path(tempfile.mkdtemp())
        audit_path = tmpdir / "wave2-audit.jsonl"

        with patch.object(
            helper_mod,
            "send_email_async",
            return_value={"success": True, "delivery_id": "x"},
        ):
            call_command(
                "wave2_send_schema_editor_available_notifications",
                f"--audit-output={audit_path}",
                stdout=io.StringIO(),
            )

        self.assertTrue(audit_path.exists())
        rows = [json.loads(line) for line in audit_path.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["to_email"], "audit-jsonl@example.com")
        self.assertEqual(rows[0]["tenant_id"], str(tenant.id))
        self.assertTrue(rows[0]["success"])
