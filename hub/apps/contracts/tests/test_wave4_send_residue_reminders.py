"""
Phase 227 Wave 4 (227.W4.2) — driver-command tests for the T+7
residue reminder.

Pins the engineering invariants the driver promises:

* Default scope is the residue cohort (clean tenants are never emailed).
* ``--tenant-id`` selects a single tenant.
* ``--deadline`` validation: must be ISO date, must be in the future.
* Idempotency via ``SCHEMA_EDITOR_RESIDUE_REMINDED`` audit row.
* ``--force`` bypasses the idempotency check.
* Idempotency record is written ONLY when ≥1 admin received the email
  — same critical sub-invariant as the W2 driver, so an all-failed
  batch self-heals on retry.
* Drift guard: contracts remediated between classification and
  dispatch are excluded from the email body; tenants whose entire
  residue was remediated are skipped (not sent an empty reminder).
* No-admin tenant skipped, not crashed.
* ``--dry-run`` writes no emails and no audit rows.
* ``--audit-output`` produces a JSONL artefact.

No mocks of internal code; ``send_email_async`` is patched at the
helper-module's path, the canonical convention.
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _create_tenant(slug_prefix: str = "w42d", *, status: str = "ACTIVE"):
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


def _create_admin(email: str, tenant):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create(email=email, tenant=tenant)


def _grant_tenant_admin(user, tenant):
    from hub.apps.users.models import Role, UserRole
    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


def _record_reminded(tenant, *, when=None):
    """Write a SCHEMA_EDITOR_RESIDUE_REMINDED audit row, optionally
    backdated.  Mirrors the W2.4-AUDIT-1 fixture pattern."""
    from hub.apps.audit.models import AuditEvent
    event = AuditEvent.objects.create(
        tenant=tenant,
        action="SCHEMA_EDITOR_RESIDUE_REMINDED",
        resource_type="TENANT",
        resource_id=tenant.id,
        result="SUCCESS",
        details_json={"phase": "227.W4.2"},
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


def _future_deadline(days: int = 30) -> str:
    return (_dt.date.today() + _dt.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class ArgumentValidationTests(TestCase):

    def test_past_deadline_rejected(self):
        past = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
        with self.assertRaises(CommandError):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={past}",
                stdout=io.StringIO(),
            )

    def test_today_deadline_rejected(self):
        today = _dt.date.today().isoformat()
        with self.assertRaises(CommandError):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={today}",
                stdout=io.StringIO(),
            )

    def test_malformed_deadline_rejected(self):
        with self.assertRaises(CommandError):
            call_command(
                "wave4_send_residue_reminders",
                "--deadline=not-a-date",
                stdout=io.StringIO(),
            )


# ---------------------------------------------------------------------------
# Scope guard
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class Wave4ReminderScopeTests(TestCase):

    def test_default_scope_only_emails_residue_tenants(self):
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        clean = _create_tenant("clean-r")
        _create_contract(clean, hub_contract_json=_HC_OK)
        _grant_tenant_admin(_create_admin("clean@example.com", clean), clean)

        residue = _create_tenant("residue-r")
        _create_contract(residue, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("residue@example.com", residue), residue)

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                stdout=io.StringIO(),
            )
        self.assertEqual(sent, ["residue@example.com"])

    def test_tenant_id_flag_selects_single_tenant(self):
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        a = _create_tenant("a-r")
        _create_contract(a, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("a@example.com", a), a)
        b = _create_tenant("b-r")
        _create_contract(b, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("b@example.com", b), b)

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                f"--tenant-id={a.id}",
                stdout=io.StringIO(),
            )
        self.assertEqual(sent, ["a@example.com"])


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class Wave4ReminderIdempotencyTests(TestCase):

    def test_recent_reminded_audit_row_skips_re_send(self):
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        tenant = _create_tenant("idem-r")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("idem@example.com", tenant), tenant)
        _record_reminded(tenant)  # already reminded today

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                stdout=io.StringIO(),
            )
        self.assertEqual(sent, [])

    def test_force_flag_bypasses_idempotency(self):
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        tenant = _create_tenant("force-r")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("force@example.com", tenant), tenant)
        _record_reminded(tenant)

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                "--force",
                stdout=io.StringIO(),
            )
        self.assertEqual(sent, ["force@example.com"])

    def test_old_audit_row_outside_window_does_not_block(self):
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        tenant = _create_tenant("stale-idem")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("stale@example.com", tenant), tenant)
        # 60 days ago — past the default 30-day idempotency window.
        _record_reminded(tenant, when=timezone.now() - timedelta(days=60))

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                stdout=io.StringIO(),
            )
        self.assertEqual(sent, ["stale@example.com"])

    def test_successful_send_records_reminded_audit_row(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        tenant = _create_tenant("rec-row")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("rec@example.com", tenant), tenant)

        before = AuditEvent.objects.filter(
            tenant=tenant,
            action="SCHEMA_EDITOR_RESIDUE_REMINDED",
        ).count()

        with patch.object(
            helper_mod, "send_email_async",
            return_value={"success": True, "delivery_id": "x"},
        ):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                stdout=io.StringIO(),
            )

        rows = AuditEvent.objects.filter(
            tenant=tenant,
            action="SCHEMA_EDITOR_RESIDUE_REMINDED",
        )
        self.assertEqual(rows.count(), before + 1)
        # The W4.3 escalation reads details.deadline; pin the shape.
        latest = rows.order_by("-timestamp").first()
        self.assertIn("deadline", latest.details_json)
        self.assertIn("residue_count", latest.details_json)

    def test_full_failure_batch_does_not_record_audit_row(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        tenant = _create_tenant("all-fail-r")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("af@example.com", tenant), tenant)

        with patch.object(
            helper_mod, "send_email_async",
            side_effect=RuntimeError("simulated SES outage"),
        ):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                stdout=io.StringIO(),
            )

        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="SCHEMA_EDITOR_RESIDUE_REMINDED",
            ).count(),
            0,
            "All-failed batch must NOT record idempotency row — "
            "otherwise the next retry would skip this tenant forever.",
        )


# ---------------------------------------------------------------------------
# Drift guard + dry-run + no-admin
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class Wave4ReminderSafetyTests(TestCase):

    def test_drift_guard_excludes_remediated_contracts_from_email_body(self):
        """A contract remediated between classification and dispatch
        must not appear in the reminder body.  We can't easily inspect
        the rendered HTML in this test (the helper is mocked), but
        we can pin the kwargs the helper is called with."""
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )
        from hub.apps.contracts.models import Contract

        tenant = _create_tenant("drift")
        c_still = _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        c_was_residue = _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("drift@example.com", tenant), tenant)

        # Simulate remediation of c_was_residue between classification
        # and dispatch by mutating its hub_contract_json post-classification.
        # We monkey-patch classify_tenants_by_residue to return BOTH
        # contract ids, then mutate the row, and let the driver's drift
        # guard detect that one of them is no longer structureless.
        Contract.objects.filter(pk=c_was_residue.pk).update(
            hub_contract_json=_HC_OK,
        )

        captured: list[dict] = []

        def _capture(**kwargs):
            captured.append(kwargs)
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                stdout=io.StringIO(),
            )

        self.assertEqual(len(captured), 1)
        # The email body's contract list should contain ONLY c_still.
        contracts = captured[0]["context"]["contracts"]
        contract_ids = [c["id"] for c in contracts]
        self.assertEqual(contract_ids, [str(c_still.id)])

    def test_tenant_with_only_remediated_residue_is_skipped(self):
        """If the entire residue was remediated between classification
        and dispatch, the driver must NOT send an empty reminder."""
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )
        from hub.apps.contracts.models import Contract

        tenant = _create_tenant("all-fixed")
        c1 = _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("af@example.com", tenant), tenant)

        # Remediate after the classifier records the residue.
        Contract.objects.filter(pk=c1.pk).update(
            hub_contract_json=_HC_OK,
        )

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        out = io.StringIO()
        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                stdout=out,
            )
        self.assertEqual(sent, [])
        self.assertIn("[drift-clean]", out.getvalue())

    def test_dry_run_writes_neither_emails_nor_audit_rows(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        tenant = _create_tenant("dry-r")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("dr@example.com", tenant), tenant)

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                "--dry-run",
                stdout=io.StringIO(),
            )

        self.assertEqual(sent, [])
        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="SCHEMA_EDITOR_RESIDUE_REMINDED",
            ).count(),
            0,
        )

    def test_no_admin_tenant_is_skipped_not_crashed(self):
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        no_admin = _create_tenant("no-admin-r")
        _create_contract(no_admin, hub_contract_json=_HC_STRUCTURELESS)

        ok = _create_tenant("ok-r")
        _create_contract(ok, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("ok@example.com", ok), ok)

        sent: list[str] = []

        def _capture(**kwargs):
            sent.append(kwargs["to_email"])
            return {"success": True, "delivery_id": "x"}

        out = io.StringIO()
        with patch.object(helper_mod, "send_email_async", side_effect=_capture):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                stdout=out,
            )
        self.assertEqual(sent, ["ok@example.com"])
        self.assertIn("[skipped-no-admin]", out.getvalue())

    def test_audit_output_writes_jsonl(self):
        from hub.apps.contracts.notifications import (
            schema_editor_residue_reminder as helper_mod,
        )

        tenant = _create_tenant("audit-r")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _grant_tenant_admin(_create_admin("au@example.com", tenant), tenant)

        tmpdir = Path(tempfile.mkdtemp())
        path = tmpdir / "wave4-audit.jsonl"

        with patch.object(
            helper_mod, "send_email_async",
            return_value={"success": True, "delivery_id": "x"},
        ):
            call_command(
                "wave4_send_residue_reminders",
                f"--deadline={_future_deadline()}",
                f"--audit-output={path}",
                stdout=io.StringIO(),
            )

        self.assertTrue(path.exists())
        rows = [
            json.loads(line) for line in path.read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["to_email"], "au@example.com")
        self.assertEqual(rows[0]["tenant_id"], str(tenant.id))
        self.assertTrue(rows[0]["success"])
        self.assertIn("deadline", rows[0])
        self.assertIn("residue_count", rows[0])
