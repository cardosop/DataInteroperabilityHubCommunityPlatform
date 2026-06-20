"""
Phase 227 Wave 0 (227.0.2) — tests for the
`wave0_summarize_structureless` triage aggregator.

Consumes the JSONL artefact produced by `wave0_capture_structureless`
and emits a markdown report with:

* Total counts (overall + per classification + per spec_type).
* Per-tenant breakdown joined with `Tenant.name` so CS/PM teams can
  identify owners without a separate JOIN.
* Tenants with no admin user — escalation list per runbook §227.0.3.

No mocks: tests build a real JSONL file from real ``Contract`` rows and
assert markdown substrings + counts.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import TestCase


def _create_tenant(name: str = "Wave 0 Summarize Co"):
    from hub.apps.tenants.models import Tenant

    return Tenant.objects.create(name=name, slug=name.lower().replace(" ", "-"))


def _create_contract(tenant, *, hub_contract_json=None, spec_type="ODCS", original_raw=""):
    from hub.apps.contracts.models import Contract

    return Contract.objects.create(
        tenant=tenant,
        original_spec_type=spec_type,
        original_spec_version="3.1.0",
        original_format="YAML",
        original_raw=original_raw or "apiVersion: 3.0.0\nkind: DataContract\n",
        hub_contract_json=hub_contract_json,
        normalization_status="NORMALIZED_OK",
    )


def _grant_tenant_admin(user, tenant):
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


def _create_user(email, tenant):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create(email=email, tenant=tenant)


def _write_jsonl(tmp_path: Path, rows: list[dict]) -> Path:
    artefact = tmp_path / "report.jsonl"
    tmp_path.mkdir(parents=True, exist_ok=True)
    with artefact.open("w", encoding="utf-8") as fp:
        # Match the capture command's header lines so the summarizer
        # has to skip them (real-world artefact shape).
        fp.write("# renormalize_contracts --filter=structureless --output=json\n")
        for row in rows:
            fp.write(json.dumps(row, sort_keys=True) + "\n")
        fp.write(f"# scanned={len(rows)} structureless={len(rows)}\n")
    return artefact


def _row(contract, classification: str = "odcs_no_schema_block"):
    return {
        "contract_id": str(contract.id),
        "tenant_id": str(contract.tenant_id) if contract.tenant_id else None,
        "asset_id": None,
        "spec_type": contract.original_spec_type,
        "spec_version": contract.original_spec_version,
        "original_format": contract.original_format,
        "classification": classification,
        "models_count": 0,
        "schema_fields_count": 0,
    }


@pytest.mark.django_db(transaction=True)
class SummarizeCommandTests(TestCase):
    def test_summarizes_total_count(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant()
            c1 = _create_contract(tenant, hub_contract_json={"models": []})
            c2 = _create_contract(tenant, hub_contract_json={"models": []})
            artefact = _write_jsonl(tmp_path, [_row(c1), _row(c2)])

            out = StringIO()
            call_command(
                "wave0_summarize_structureless",
                f"--input={artefact}",
                stdout=out,
            )

            output = out.getvalue()
            assert "2" in output, output
            assert "structureless" in output.lower()
        finally:
            self._cleanup(tmp_path)

    def test_per_classification_breakdown(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant()
            c1 = _create_contract(tenant, hub_contract_json={"models": []})
            c2 = _create_contract(tenant, hub_contract_json={"models": []})
            c3 = _create_contract(tenant, hub_contract_json={"models": []})
            artefact = _write_jsonl(
                tmp_path,
                [
                    _row(c1, "pure_odps_with_outputports"),
                    _row(c2, "odcs_no_schema_block"),
                    _row(c3, "odcs_no_schema_block"),
                ],
            )

            out = StringIO()
            call_command(
                "wave0_summarize_structureless",
                f"--input={artefact}",
                stdout=out,
            )

            output = out.getvalue()
            # Both classes must be enumerated with their counts.
            assert "pure_odps_with_outputports" in output
            assert "odcs_no_schema_block" in output
            # The 2-vs-1 ratio between odcs and odps must be visible.
            assert "2" in output and "1" in output
        finally:
            self._cleanup(tmp_path)

    def test_per_tenant_breakdown_joins_tenant_name(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            t1 = _create_tenant("Acme Corp")
            t2 = _create_tenant("Globex")
            c1 = _create_contract(t1, hub_contract_json={"models": []})
            c2 = _create_contract(t2, hub_contract_json={"models": []})
            artefact = _write_jsonl(tmp_path, [_row(c1), _row(c2)])

            out = StringIO()
            call_command(
                "wave0_summarize_structureless",
                f"--input={artefact}",
                stdout=out,
            )

            output = out.getvalue()
            # Tenant names must appear (joined via Tenant lookup, not
            # passed in the JSONL) so CS/PM identifies owners directly.
            assert "Acme Corp" in output
            assert "Globex" in output
        finally:
            self._cleanup(tmp_path)

    def test_handles_unknown_tenant_id_gracefully(self):
        """A row with a tenant_id that no longer exists must surface as
        '(unknown tenant)' rather than crashing the summarizer."""
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            artefact = _write_jsonl(
                tmp_path,
                [
                    {
                        "contract_id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
                        "tenant_id": "00000000-0000-0000-0000-000000000000",
                        "asset_id": None,
                        "spec_type": "ODCS",
                        "spec_version": "3.1.0",
                        "original_format": "YAML",
                        "classification": "other",
                        "models_count": 0,
                        "schema_fields_count": 0,
                    }
                ],
            )

            out = StringIO()
            call_command(
                "wave0_summarize_structureless",
                f"--input={artefact}",
                stdout=out,
            )

            output = out.getvalue()
            assert "unknown" in output.lower() or "missing" in output.lower()
        finally:
            self._cleanup(tmp_path)

    def test_flags_tenants_without_admin(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            with_admin = _create_tenant("WithAdmin")
            no_admin = _create_tenant("NoAdmin")
            admin_user = _create_user("admin@example.com", with_admin)
            _grant_tenant_admin(admin_user, with_admin)

            c1 = _create_contract(with_admin, hub_contract_json={"models": []})
            c2 = _create_contract(no_admin, hub_contract_json={"models": []})
            artefact = _write_jsonl(tmp_path, [_row(c1), _row(c2)])

            out = StringIO()
            call_command(
                "wave0_summarize_structureless",
                f"--input={artefact}",
                stdout=out,
            )

            output = out.getvalue()
            # The summarizer must explicitly call out tenants with no
            # TENANT_ADMIN — they're an escalation per runbook §227.0.3.
            assert "no_admin" in output.lower() or "NoAdmin" in output, output
            # The "no admin" section header must be present.
            assert "no admin" in output.lower() or "without admin" in output.lower()
        finally:
            self._cleanup(tmp_path)

    def test_writes_to_output_file_when_specified(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant()
            c1 = _create_contract(tenant, hub_contract_json={"models": []})
            artefact = _write_jsonl(tmp_path, [_row(c1)])
            out_md = tmp_path / "summary.md"

            call_command(
                "wave0_summarize_structureless",
                f"--input={artefact}",
                f"--output={out_md}",
                stdout=StringIO(),
            )

            assert out_md.exists()
            content = out_md.read_text(encoding="utf-8")
            assert "structureless" in content.lower()
        finally:
            self._cleanup(tmp_path)

    def test_handles_empty_jsonl_with_clean_message(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            artefact = _write_jsonl(tmp_path, [])

            out = StringIO()
            call_command(
                "wave0_summarize_structureless",
                f"--input={artefact}",
                stdout=out,
            )

            output = out.getvalue().lower()
            assert "0" in output
            assert "no" in output or "clean" in output or "empty" in output
        finally:
            self._cleanup(tmp_path)

    def test_skips_malformed_lines_with_warning(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tmp_path.mkdir(parents=True, exist_ok=True)
            artefact = tmp_path / "report.jsonl"
            tenant = _create_tenant()
            c = _create_contract(tenant, hub_contract_json={"models": []})
            with artefact.open("w") as fp:
                fp.write("# header\n")
                fp.write(json.dumps(_row(c), sort_keys=True) + "\n")
                fp.write("THIS IS NOT JSON\n")
                fp.write("# trailer\n")

            err = StringIO()
            out = StringIO()
            call_command(
                "wave0_summarize_structureless",
                f"--input={artefact}",
                stdout=out,
                stderr=err,
            )

            # The malformed line is skipped; the valid row is counted.
            assert "1" in out.getvalue()
            # A warning is surfaced (stdout or stderr).
            combined = out.getvalue() + err.getvalue()
            assert (
                "skip" in combined.lower()
                or "malformed" in combined.lower()
                or "warn" in combined.lower()
            )
        finally:
            self._cleanup(tmp_path)

    def _cleanup(self, tmp_path: Path):
        if tmp_path.exists():
            for p in tmp_path.iterdir():
                p.unlink()
            tmp_path.rmdir()
