"""
Phase 227 Wave 0 (227.0.1) — tests for the `wave0_capture_structureless`
turn-key wrapper management command.

The wrapper auto-creates the `audit-reports/` directory, names the file
`structureless-pre-rollout-YYYY-MM-DD.jsonl`, and writes the JSONL there
instead of stdout. This makes the operator path one command (matching
the runbook one-liner) and ensures the directory + filename convention
is enforced by code, not by operator memory.

Tests use real Contract rows + a temporary directory (no mocks) and
verify the artefact file shape end-to-end.
"""
from __future__ import annotations

import json
import re
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings


def _create_tenant(name: str = "Wave 0 Capture Co"):
    from hub.apps.tenants.models import Tenant
    return Tenant.objects.create(name=name, slug=name.lower().replace(" ", "-"))


def _create_contract(tenant, *, hub_contract_json=None, original_raw: str = ""):
    from hub.apps.contracts.models import Contract
    return Contract.objects.create(
        tenant=tenant,
        original_spec_type="ODCS",
        original_spec_version="3.1.0",
        original_format="YAML",
        original_raw=original_raw or "apiVersion: 3.0.0\nkind: DataContract\n",
        hub_contract_json=hub_contract_json,
        normalization_status="NORMALIZED_OK",
    )


@pytest.mark.django_db(transaction=True)
class CaptureCommandTests(TestCase):

    def test_creates_audit_reports_directory_if_missing(self, tmp_path: Path | None = None):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        if tmp_path.exists():
            for p in tmp_path.iterdir():
                p.unlink()
            tmp_path.rmdir()
        try:
            tenant = _create_tenant()
            _create_contract(tenant, hub_contract_json={"models": []})

            out = StringIO()
            call_command(
                "wave0_capture_structureless",
                f"--audit-reports-dir={tmp_path}",
                stdout=out,
            )

            assert tmp_path.exists() and tmp_path.is_dir()
        finally:
            if tmp_path.exists():
                for p in tmp_path.iterdir():
                    p.unlink()
                tmp_path.rmdir()

    def test_writes_jsonl_with_today_date_in_filename(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant()
            _create_contract(tenant, hub_contract_json={"models": []})

            out = StringIO()
            call_command(
                "wave0_capture_structureless",
                f"--audit-reports-dir={tmp_path}",
                stdout=out,
            )

            today = date.today().isoformat()
            expected = tmp_path / f"structureless-pre-rollout-{today}.jsonl"
            assert expected.exists(), (
                f"Expected file {expected} not produced. "
                f"Found: {list(tmp_path.iterdir()) if tmp_path.exists() else []}"
            )
        finally:
            if tmp_path.exists():
                for p in tmp_path.iterdir():
                    p.unlink()
                tmp_path.rmdir()

    def test_jsonl_contains_one_row_per_structureless_contract(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant()
            _create_contract(tenant, hub_contract_json={"models": []})
            _create_contract(tenant, hub_contract_json={"models": []})
            # One non-structureless — must NOT appear.
            _create_contract(
                tenant,
                hub_contract_json={
                    "models": [{"name": "x", "fields": [{"name": "id"}]}]
                },
            )

            call_command(
                "wave0_capture_structureless",
                f"--audit-reports-dir={tmp_path}",
                stdout=StringIO(),
            )

            today = date.today().isoformat()
            artefact = tmp_path / f"structureless-pre-rollout-{today}.jsonl"
            content = artefact.read_text(encoding="utf-8")
            json_lines = [
                ln for ln in content.splitlines()
                if ln.startswith("{") and ln.rstrip().endswith("}")
            ]
            assert len(json_lines) == 2, (
                f"Expected 2 structureless rows; got {len(json_lines)}\n"
                f"content:\n{content}"
            )
            for ln in json_lines:
                # Each line must be valid JSON.
                json.loads(ln)
        finally:
            if tmp_path.exists():
                for p in tmp_path.iterdir():
                    p.unlink()
                tmp_path.rmdir()

    def test_stdout_summary_includes_path_and_count(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant()
            _create_contract(tenant, hub_contract_json={"models": []})

            out = StringIO()
            call_command(
                "wave0_capture_structureless",
                f"--audit-reports-dir={tmp_path}",
                stdout=out,
            )

            output = out.getvalue()
            today = date.today().isoformat()
            assert f"structureless-pre-rollout-{today}.jsonl" in output, output
            # The count must be visible to the operator without re-reading
            # the file.
            assert "1 structureless" in output or "structureless=1" in output, output
        finally:
            if tmp_path.exists():
                for p in tmp_path.iterdir():
                    p.unlink()
                tmp_path.rmdir()

    def test_idempotent_overwrite_warns_and_replaces(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            tenant = _create_tenant()
            _create_contract(tenant, hub_contract_json={"models": []})

            today = date.today().isoformat()
            artefact = tmp_path / f"structureless-pre-rollout-{today}.jsonl"
            tmp_path.mkdir(exist_ok=True)
            artefact.write_text("STALE\n", encoding="utf-8")

            out = StringIO()
            call_command(
                "wave0_capture_structureless",
                f"--audit-reports-dir={tmp_path}",
                stdout=out,
            )

            content = artefact.read_text(encoding="utf-8")
            assert "STALE" not in content, "Stale file must be overwritten"
            # The operator must be warned that an overwrite happened.
            assert (
                "overwrit" in out.getvalue().lower()
                or "exist" in out.getvalue().lower()
            )
        finally:
            if tmp_path.exists():
                for p in tmp_path.iterdir():
                    p.unlink()
                tmp_path.rmdir()

    def test_passes_tenant_id_through(self):
        tmp_path = Path(self.id().replace(".", "_") + "-tmp")
        try:
            t1 = _create_tenant("Tenant A")
            t2 = _create_tenant("Tenant B")
            _create_contract(t1, hub_contract_json={"models": []})
            _create_contract(t2, hub_contract_json={"models": []})

            call_command(
                "wave0_capture_structureless",
                f"--audit-reports-dir={tmp_path}",
                f"--tenant-id={t1.id}",
                stdout=StringIO(),
            )

            today = date.today().isoformat()
            artefact = tmp_path / f"structureless-pre-rollout-{today}.jsonl"
            json_lines = [
                ln for ln in artefact.read_text().splitlines()
                if ln.startswith("{")
            ]
            assert len(json_lines) == 1, (
                "Only Tenant A's contracts should be in the report"
            )
            assert json.loads(json_lines[0])["tenant_id"] == str(t1.id)
        finally:
            if tmp_path.exists():
                for p in tmp_path.iterdir():
                    p.unlink()
                tmp_path.rmdir()
