"""
Phase 227 Wave 0 (227.0.3) — tests for the
`wave0_send_structureless_notifications` batch dispatcher.

Reads a JSONL artefact, groups contracts by tenant, calls the canonical
``send_structureless_contract_pending_notification`` helper per tenant,
and writes an audit JSONL trail of dispatched emails.

Tests use real ``Tenant`` / ``User`` / ``Role`` / ``Contract`` rows and
the real Django template renderer (no mocks). The underlying
``send_email_async`` is patched at one tightly-scoped point because the
tests must NOT actually hit AWS SES — the patch is the thinnest possible
boundary around the network call, not around our own code paths.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase


def _create_tenant(name: str = "Wave 0 Notify Co"):
    from hub.apps.tenants.models import Tenant

    return Tenant.objects.create(name=name, slug=name.lower().replace(" ", "-"))


def _create_user(email, tenant):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create(email=email, tenant=tenant)


def _grant_admin(user, tenant):
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


def _create_contract(tenant, *, hub_contract_json=None, name: str | None = None):
    from hub.apps.contracts.models import Contract

    return Contract.objects.create(
        tenant=tenant,
        original_spec_type="ODCS",
        original_spec_version="3.1.0",
        original_format="YAML",
        original_raw=f"apiVersion: 3.0.0\nkind: DataContract\nname: {name or 'orders'}\n",
        hub_contract_json=hub_contract_json or {"models": []},
        normalization_status="NORMALIZED_OK",
    )


def _row_for(contract, classification: str = "odcs_no_schema_block") -> dict:
    return {
        "contract_id": str(contract.id),
        "tenant_id": str(contract.tenant_id),
        "asset_id": None,
        "spec_type": contract.original_spec_type,
        "spec_version": contract.original_spec_version,
        "original_format": contract.original_format,
        "classification": classification,
        "models_count": 0,
        "schema_fields_count": 0,
    }


def _write_jsonl(tmp_path: Path, rows: list[dict]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    artefact = tmp_path / "report.jsonl"
    with artefact.open("w", encoding="utf-8") as fp:
        fp.write("# header\n")
        for r in rows:
            fp.write(json.dumps(r, sort_keys=True) + "\n")
    return artefact


@pytest.mark.django_db(transaction=True)
class NotifyCommandTests(TestCase):
    def _cleanup(self, tmp_path: Path):
        if tmp_path.exists():
            for p in tmp_path.iterdir():
                p.unlink()
            tmp_path.rmdir()

    # --------------------------------------------------------------
    # Dry-run path (no email sent)
    # --------------------------------------------------------------

    def test_dry_run_reports_per_tenant_dispatch_plan_without_sending(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            t1 = _create_tenant("Acme")
            t2 = _create_tenant("Globex")
            for tenant, email in [(t1, "a1@example.com"), (t2, "b1@example.com")]:
                user = _create_user(email, tenant)
                _grant_admin(user, tenant)
            c_a1 = _create_contract(t1, name="orders")
            c_a2 = _create_contract(t1, name="users")
            c_b1 = _create_contract(t2, name="catalog")
            artefact = _write_jsonl(tmp_path, [_row_for(c_a1), _row_for(c_a2), _row_for(c_b1)])

            deadline = (date.today() + timedelta(days=14)).isoformat()
            out = StringIO()

            with patch(
                "hub.apps.contracts.notifications.structureless.send_email_async"
            ) as mock_send:
                call_command(
                    "wave0_send_structureless_notifications",
                    f"--input={artefact}",
                    f"--deadline={deadline}",
                    "--dry-run",
                    stdout=out,
                )

            output = out.getvalue()
            assert "Acme" in output and "Globex" in output, output
            # Dry-run reports the planned per-tenant counts.
            assert "2" in output and "1" in output
            # Dry-run never invokes the email pipeline.
            assert mock_send.call_count == 0
        finally:
            self._cleanup(tmp_path)

    # --------------------------------------------------------------
    # Real dispatch path
    # --------------------------------------------------------------

    def test_dispatch_calls_send_email_async_for_each_admin(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant("Acme")
            admin1 = _create_user("admin1@example.com", tenant)
            admin2 = _create_user("admin2@example.com", tenant)
            _grant_admin(admin1, tenant)
            _grant_admin(admin2, tenant)
            contract = _create_contract(tenant)
            artefact = _write_jsonl(tmp_path, [_row_for(contract)])

            deadline = (date.today() + timedelta(days=14)).isoformat()

            with patch(
                "hub.apps.contracts.notifications.structureless.send_email_async"
            ) as mock_send:
                call_command(
                    "wave0_send_structureless_notifications",
                    f"--input={artefact}",
                    f"--deadline={deadline}",
                    stdout=StringIO(),
                )

            recipients = sorted(call.kwargs["to_email"] for call in mock_send.call_args_list)
            assert recipients == ["admin1@example.com", "admin2@example.com"]

            # Each call carries the canonical EmailType value.
            for call in mock_send.call_args_list:
                assert call.kwargs["email_type"] == "ASSET_CONTRACT_STRUCTURELESS_PENDING"
        finally:
            self._cleanup(tmp_path)

    def test_skips_tenant_with_no_admin_with_warning(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant_with_admin = _create_tenant("WithAdmin")
            tenant_no_admin = _create_tenant("NoAdmin")
            admin = _create_user("admin@example.com", tenant_with_admin)
            _grant_admin(admin, tenant_with_admin)
            c1 = _create_contract(tenant_with_admin)
            c2 = _create_contract(tenant_no_admin)
            artefact = _write_jsonl(tmp_path, [_row_for(c1), _row_for(c2)])

            deadline = (date.today() + timedelta(days=14)).isoformat()
            out = StringIO()
            err = StringIO()

            with patch(
                "hub.apps.contracts.notifications.structureless.send_email_async"
            ) as mock_send:
                call_command(
                    "wave0_send_structureless_notifications",
                    f"--input={artefact}",
                    f"--deadline={deadline}",
                    stdout=out,
                    stderr=err,
                )

            # The admin tenant got an email; the no-admin tenant was
            # skipped (not crashed) with a warning surfaced.
            recipients = [c.kwargs["to_email"] for c in mock_send.call_args_list]
            assert recipients == ["admin@example.com"]
            combined = (out.getvalue() + err.getvalue()).lower()
            assert "noadmin" in combined or "no admin" in combined or "skipp" in combined
        finally:
            self._cleanup(tmp_path)

    # --------------------------------------------------------------
    # Drift guard
    # --------------------------------------------------------------

    def test_skips_contracts_no_longer_structureless(self):
        """If a contract was structureless when the JSONL was captured
        but has since been remediated, the dispatcher must NOT include
        it in the per-tenant body — drift would mislead customers."""
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant("Acme")
            admin = _create_user("admin@example.com", tenant)
            _grant_admin(admin, tenant)

            still_structureless = _create_contract(tenant)
            already_fixed = _create_contract(
                tenant,
                hub_contract_json={"models": [{"name": "orders", "fields": [{"name": "id"}]}]},
            )
            artefact = _write_jsonl(
                tmp_path,
                [_row_for(still_structureless), _row_for(already_fixed)],
            )

            deadline = (date.today() + timedelta(days=14)).isoformat()
            out = StringIO()

            with patch(
                "hub.apps.contracts.notifications.structureless.send_email_async"
            ) as mock_send:
                call_command(
                    "wave0_send_structureless_notifications",
                    f"--input={artefact}",
                    f"--deadline={deadline}",
                    stdout=out,
                )

            assert mock_send.call_count == 1
            ctx = mock_send.call_args.kwargs["context"]
            ids_in_body = {c["id"] for c in ctx["contracts"]}
            assert str(still_structureless.id) in ids_in_body
            assert str(already_fixed.id) not in ids_in_body
            # The skip is surfaced for audit.
            assert (
                "remediated" in out.getvalue().lower()
                or "skipped" in out.getvalue().lower()
                or "no longer" in out.getvalue().lower()
            )
        finally:
            self._cleanup(tmp_path)

    # --------------------------------------------------------------
    # Audit trail
    # --------------------------------------------------------------

    def test_writes_audit_trail_jsonl(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant("Acme")
            admin = _create_user("admin@example.com", tenant)
            _grant_admin(admin, tenant)
            contract = _create_contract(tenant)
            artefact = _write_jsonl(tmp_path, [_row_for(contract)])

            deadline = (date.today() + timedelta(days=14)).isoformat()
            audit_path = tmp_path / "audit.jsonl"

            with patch("hub.apps.contracts.notifications.structureless.send_email_async"):
                call_command(
                    "wave0_send_structureless_notifications",
                    f"--input={artefact}",
                    f"--deadline={deadline}",
                    f"--audit-output={audit_path}",
                    stdout=StringIO(),
                )

            assert audit_path.exists()
            lines = [
                json.loads(ln) for ln in audit_path.read_text().splitlines() if ln.startswith("{")
            ]
            assert lines, "audit JSONL must contain at least one record"
            r = lines[0]
            assert r["tenant_id"] == str(tenant.id)
            assert r["to_email"] == "admin@example.com"
            assert r["email_type"] == "ASSET_CONTRACT_STRUCTURELESS_PENDING"
            assert r["deadline"] == deadline
            assert r["contract_count"] == 1
        finally:
            self._cleanup(tmp_path)

    # --------------------------------------------------------------
    # Tenant filter
    # --------------------------------------------------------------

    def test_tenant_id_flag_scopes_dispatch(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            t1 = _create_tenant("Acme")
            t2 = _create_tenant("Globex")
            for tenant, email in [(t1, "a@example.com"), (t2, "b@example.com")]:
                user = _create_user(email, tenant)
                _grant_admin(user, tenant)
            c1 = _create_contract(t1)
            c2 = _create_contract(t2)
            artefact = _write_jsonl(tmp_path, [_row_for(c1), _row_for(c2)])

            deadline = (date.today() + timedelta(days=14)).isoformat()

            with patch(
                "hub.apps.contracts.notifications.structureless.send_email_async"
            ) as mock_send:
                call_command(
                    "wave0_send_structureless_notifications",
                    f"--input={artefact}",
                    f"--deadline={deadline}",
                    f"--tenant-id={t1.id}",
                    stdout=StringIO(),
                )

            recipients = [c.kwargs["to_email"] for c in mock_send.call_args_list]
            assert recipients == ["a@example.com"]
        finally:
            self._cleanup(tmp_path)

    # --------------------------------------------------------------
    # Date validation
    # --------------------------------------------------------------

    def test_rejects_invalid_deadline_format(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            artefact = _write_jsonl(tmp_path, [])

            err = StringIO()
            from django.core.management.base import CommandError

            with pytest.raises((CommandError, ValueError, SystemExit)):
                call_command(
                    "wave0_send_structureless_notifications",
                    f"--input={artefact}",
                    "--deadline=not-a-date",
                    stdout=StringIO(),
                    stderr=err,
                )
        finally:
            self._cleanup(tmp_path)

    def test_rejects_past_deadline(self):
        """A T-14 notification with a deadline in the past is a runbook
        violation — the operator must use a future date."""
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant()
            admin = _create_user("a@example.com", tenant)
            _grant_admin(admin, tenant)
            c = _create_contract(tenant)
            artefact = _write_jsonl(tmp_path, [_row_for(c)])

            past = (date.today() - timedelta(days=1)).isoformat()

            from django.core.management.base import CommandError

            with pytest.raises((CommandError, SystemExit)):
                call_command(
                    "wave0_send_structureless_notifications",
                    f"--input={artefact}",
                    f"--deadline={past}",
                    stdout=StringIO(),
                )
        finally:
            self._cleanup(tmp_path)
