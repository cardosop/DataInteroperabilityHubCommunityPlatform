"""
Phase 227 Wave 4 (227.W4.1) — tenant-residue classification command.

The post-Wave-3 classification step partitions every tenant into one
of two cohorts:

* ``clean`` — zero remaining structureless contracts.  These tenants
  are safe to roll forward in W4.5 (the enforcement was already
  global from L3.3, but the classification still drives the rollout
  comms / dashboard).
* ``residue`` — at least one remaining structureless contract.
  These tenants drive the W4.2 T+7 reminder + W4.3 30-day
  escalation pipeline.

The original spec (W4.1) talked about flipping a feature flag for
clean tenants first; the 2026-04-30 ungate directive removed that
flag.  The classification artefact remains the canonical W4.1
deliverable: an operations-grade JSONL listing tenants and their
residue (or lack thereof) so W4.2 / W4.3 / dashboards can consume it.

These tests exercise real ``Contract`` rows + the canonical
``is_structureless`` predicate (no mocks of internal code).
"""

from __future__ import annotations

import io
import json
import tempfile
import uuid
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import TestCase


def _create_tenant(slug_prefix: str = "w41"):
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
    )


def _create_contract(tenant, *, hub_contract_json, status=None):
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
        status=status or ContractStatus.DRAFT,
    )


_HC_OK = {
    "models": [{"name": "m", "fields": [{"name": "id", "data_type": "string"}]}],
    "schema": {"fields": [{"name": "id", "data_type": "string"}]},
}
_HC_STRUCTURELESS = {"models": [], "schema": {"fields": []}}


# ---------------------------------------------------------------------------
# Pure-function classifier
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class ClassifyResidueFunctionTests(TestCase):
    """``classify_tenants_by_residue`` partitions tenants in one pass."""

    def test_tenant_with_only_clean_contracts_is_clean(self):
        from hub.apps.contracts.management.commands.wave4_classify_residue import (
            classify_tenants_by_residue,
        )

        tenant = _create_tenant("clean")
        _create_contract(tenant, hub_contract_json=_HC_OK)

        result = classify_tenants_by_residue()
        clean_ids = {row["tenant_id"] for row in result if row["cohort"] == "clean"}
        self.assertIn(str(tenant.id), clean_ids)

    def test_tenant_with_residue_is_classified_with_residue_count(self):
        from hub.apps.contracts.management.commands.wave4_classify_residue import (
            classify_tenants_by_residue,
        )

        tenant = _create_tenant("residue")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _create_contract(tenant, hub_contract_json=_HC_OK)

        result = classify_tenants_by_residue()
        rows = [r for r in result if r["tenant_id"] == str(tenant.id)]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cohort"], "residue")
        self.assertEqual(rows[0]["residue_count"], 2)
        # Residue contract ids surface so the W4.2 reminder driver can
        # render them without re-querying.
        self.assertEqual(len(rows[0]["residue_contract_ids"]), 2)

    def test_tenant_with_no_contracts_is_excluded(self):
        """A tenant with no contracts is vacuously satisfied — no
        residue, but no clean evidence either.  Excluding them keeps
        the W4.2 reminder noise-free and the W4.5 rollout tracker
        accurate (it counts tenants we've actually shipped at)."""
        from hub.apps.contracts.management.commands.wave4_classify_residue import (
            classify_tenants_by_residue,
        )

        empty = _create_tenant("empty")  # no contracts
        result = classify_tenants_by_residue()
        ids = {row["tenant_id"] for row in result}
        self.assertNotIn(str(empty.id), ids)

    def test_active_only_scope_excludes_draft_and_retired_residue(self):
        """``--include-active-only`` semantics mirror the renormalize
        command: DRAFT/RETIRED structureless contracts don't drive a
        reminder (data engineer's edit buffer / tombstone)."""
        from hub.apps.contracts.management.commands.wave4_classify_residue import (
            classify_tenants_by_residue,
        )
        from hub.apps.contracts.models import ContractStatus

        tenant = _create_tenant("active-scope")
        # DRAFT residue — shouldn't count under active-only.
        _create_contract(
            tenant,
            hub_contract_json=_HC_STRUCTURELESS,
            status=ContractStatus.DRAFT,
        )
        # ACTIVE clean — keeps the tenant in the population.
        _create_contract(
            tenant,
            hub_contract_json=_HC_OK,
            status=ContractStatus.ACTIVE,
        )

        result = classify_tenants_by_residue(active_only=True)
        rows = [r for r in result if r["tenant_id"] == str(tenant.id)]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cohort"], "clean")

    def test_active_only_excludes_tenant_with_zero_active_contracts(self):
        """W4.1-AUDIT-1 regression — under ``active_only=True`` a tenant
        whose only contracts are DRAFT/RETIRED has no rollout work to
        do.  Surfacing them as ``cohort=clean`` would inflate the W4
        rollout-tracker dashboard's numerator (clean-tenants count) and
        misrepresent the population.

        The pre-fix loop created the slot via ``setdefault`` BEFORE
        the active-only filter check, so a DRAFT-only tenant ended up
        in ``by_tenant`` as ``cohort=clean`` regardless.  The fix
        moves the filter ahead of the slot creation so a tenant only
        enters the dict if it owns at least one row in scope.
        """
        from hub.apps.contracts.management.commands.wave4_classify_residue import (
            classify_tenants_by_residue,
        )
        from hub.apps.contracts.models import ContractStatus

        tenant = _create_tenant("draft-only")
        _create_contract(
            tenant,
            hub_contract_json=_HC_STRUCTURELESS,
            status=ContractStatus.DRAFT,
        )

        result = classify_tenants_by_residue(active_only=True)
        ids = {row["tenant_id"] for row in result}
        self.assertNotIn(
            str(tenant.id),
            ids,
            "Tenants with zero ACTIVE contracts must be excluded under "
            "active_only=True — they have no rollout work, so surfacing "
            "them as 'clean' inflates the W4 dashboard population.",
        )

    def test_active_only_excludes_tenant_with_only_retired(self):
        """Companion to the previous test: RETIRED-only tenants follow
        the same exclusion rule under active_only."""
        from hub.apps.contracts.management.commands.wave4_classify_residue import (
            classify_tenants_by_residue,
        )
        from hub.apps.contracts.models import ContractStatus

        tenant = _create_tenant("retired-only")
        _create_contract(
            tenant,
            hub_contract_json=_HC_OK,  # status, not structureless, is the test
            status=ContractStatus.RETIRED,
        )

        result = classify_tenants_by_residue(active_only=True)
        ids = {row["tenant_id"] for row in result}
        self.assertNotIn(str(tenant.id), ids)


# ---------------------------------------------------------------------------
# Management-command CLI
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class ClassifyResidueCommandTests(TestCase):
    def test_emits_jsonl_with_per_tenant_rows(self):
        clean = _create_tenant("clean-cli")
        _create_contract(clean, hub_contract_json=_HC_OK)
        residue = _create_tenant("residue-cli")
        _create_contract(residue, hub_contract_json=_HC_STRUCTURELESS)

        out = io.StringIO()
        call_command(
            "wave4_classify_residue",
            "--output=json",
            stdout=out,
        )
        json_lines = [
            line
            for line in out.getvalue().splitlines()
            if line.startswith("{") and line.rstrip().endswith("}")
        ]
        records = [json.loads(line) for line in json_lines]
        by_tenant = {r["tenant_id"]: r for r in records}

        self.assertIn(str(clean.id), by_tenant)
        self.assertEqual(by_tenant[str(clean.id)]["cohort"], "clean")

        self.assertIn(str(residue.id), by_tenant)
        self.assertEqual(by_tenant[str(residue.id)]["cohort"], "residue")
        self.assertEqual(
            by_tenant[str(residue.id)]["residue_count"],
            1,
        )

    def test_human_summary_shows_cohort_counts(self):
        for i in range(2):
            t = _create_tenant(f"clean-h-{i}")
            _create_contract(t, hub_contract_json=_HC_OK)
        t = _create_tenant("residue-h")
        _create_contract(t, hub_contract_json=_HC_STRUCTURELESS)

        out = io.StringIO()
        call_command(
            "wave4_classify_residue",
            "--output=human",
            stdout=out,
        )
        text = out.getvalue()
        # Cohort counts grow with accumulated ``--keepdb`` state from prior
        # batch runs.  Verify the format (clean=N, residue=M) without exact values.

        self.assertRegex(text, r"clean=\d+", "Human-readable output must include clean=<count>")
        self.assertRegex(text, r"residue=\d+", "Human-readable output must include residue=<count>")

    def test_audit_output_writes_jsonl_artefact(self):
        clean = _create_tenant("clean-art")
        _create_contract(clean, hub_contract_json=_HC_OK)
        residue = _create_tenant("residue-art")
        _create_contract(residue, hub_contract_json=_HC_STRUCTURELESS)

        tmpdir = Path(tempfile.mkdtemp())
        path = tmpdir / "classification.jsonl"

        call_command(
            "wave4_classify_residue",
            "--output=json",
            f"--audit-output={path}",
            stdout=io.StringIO(),
        )

        self.assertTrue(path.exists())
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        ids = {r["tenant_id"] for r in rows}
        self.assertIn(str(clean.id), ids)
        self.assertIn(str(residue.id), ids)

    def test_only_residue_flag_filters_output(self):
        """``--only-residue`` is the W4.2 driver's input shape — only
        the rows that need a reminder.  Pre-filtering at the
        classifier saves the driver from re-loading the whole
        tenant table."""
        clean = _create_tenant("only-clean")
        _create_contract(clean, hub_contract_json=_HC_OK)
        residue = _create_tenant("only-residue")
        _create_contract(residue, hub_contract_json=_HC_STRUCTURELESS)

        out = io.StringIO()
        call_command(
            "wave4_classify_residue",
            "--output=json",
            "--only-residue",
            stdout=out,
        )
        json_lines = [
            line
            for line in out.getvalue().splitlines()
            if line.startswith("{") and line.rstrip().endswith("}")
        ]
        records = [json.loads(line) for line in json_lines]
        ids = {r["tenant_id"] for r in records}
        self.assertNotIn(str(clean.id), ids)
        self.assertIn(str(residue.id), ids)
        for r in records:
            self.assertEqual(r["cohort"], "residue")
