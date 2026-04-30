"""
Phase 227 Wave 0 — tests for the `--filter=structureless` and
`--output=json` extensions to the `renormalize_contracts` management
command.

Per Wave 0 (227.0.1) the dry-run JSONL is the diagnosis artefact: each
line documents one structureless contract with enough context (tenant,
asset, classification) to feed the customer-coordination playbook.

These tests use real ``Contract`` rows (no mocks) and verify the JSONL
shape end-to-end. They share a fixture pattern with the existing tests
under ``hub/apps/contracts/tests/`` so the new flags compose with the
existing ``--dry-run`` / ``--tenant-id`` flags.
"""
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase


def _create_tenant(name: str = "Wave 0 Co"):
    from hub.apps.tenants.models import Tenant
    return Tenant.objects.create(name=name, slug=name.lower().replace(" ", "-"))


def _create_contract(
    tenant,
    *,
    spec_type: str = "ODCS",
    spec_version: str = "3.1.0",
    hub_contract_json=None,
    original_raw: str = "",
    name: str | None = None,
):
    """Create a real Contract row with minimal valid metadata.

    The hub_contract_json is written *as-is* (no normalization triggered)
    so each test can express the exact structure it needs.
    """
    from hub.apps.contracts.models import Contract
    return Contract.objects.create(
        tenant=tenant,
        original_spec_type=spec_type,
        original_spec_version=spec_version,
        original_format="YAML",
        original_raw=original_raw or "apiVersion: 3.0.0\nkind: DataContract\n",
        hub_contract_json=hub_contract_json,
        normalization_status="NORMALIZED_OK",
    )


@pytest.mark.django_db(transaction=True)
class FilterStructurelessTests(TestCase):
    """Cover the predicate composition with the existing dry-run flag."""

    def test_filter_structureless_dry_run_emits_jsonl_to_stdout(self):
        tenant = _create_tenant()
        # 1 structureless ODCS contract (no schema:)
        structureless = _create_contract(
            tenant,
            hub_contract_json={"models": [], "schema": {}},
            original_raw="apiVersion: 3.0.0\nkind: DataContract\nname: orders\n",
        )
        # 1 normal contract — must NOT appear in output
        _create_contract(
            tenant,
            hub_contract_json={
                "models": [{"name": "orders", "fields": [{"name": "id"}]}],
            },
        )

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=json",
            stdout=out,
        )

        # Find lines that look like JSON objects (header / footer lines
        # are plain prose for human readability).
        json_lines = [
            ln for ln in out.getvalue().splitlines()
            if ln.startswith("{") and ln.rstrip().endswith("}")
        ]

        assert len(json_lines) == 1, (
            "Expected exactly one JSONL row for the one structureless "
            "contract; got: " + repr(json_lines)
        )

        record = json.loads(json_lines[0])
        assert record["contract_id"] == str(structureless.id)
        assert record["tenant_id"] == str(tenant.id)
        assert record["classification"] == "odcs_no_schema_block"
        assert record["spec_type"] == "ODCS"
        # Implementation may include an asset_id field (null when absent)
        # — assert it's present rather than asserting the exact value.
        assert "asset_id" in record

    def test_filter_structureless_skips_normal_contracts(self):
        tenant = _create_tenant()
        _create_contract(
            tenant,
            hub_contract_json={
                "models": [{"name": "orders", "fields": [{"name": "id"}]}],
            },
        )

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=json",
            stdout=out,
        )

        json_lines = [
            ln for ln in out.getvalue().splitlines()
            if ln.startswith("{")
        ]
        assert json_lines == [], (
            "Normal contracts must not appear in the structureless report"
        )

    def test_filter_structureless_classifies_odps_outputports(self):
        tenant = _create_tenant("Wave 0 ODPS")
        odps = _create_contract(
            tenant,
            spec_type="ODPS",
            original_raw=(
                "apiVersion: dataproduct.open-data-product-initiative.org/v1\n"
                "kind: DataProduct\n"
                "spec:\n"
                "  outputPorts:\n"
                "    - name: orders\n"
            ),
            hub_contract_json={"models": []},
        )

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=json",
            stdout=out,
        )

        json_lines = [
            ln for ln in out.getvalue().splitlines()
            if ln.startswith("{")
        ]
        assert len(json_lines) == 1
        record = json.loads(json_lines[0])
        assert record["contract_id"] == str(odps.id)
        assert record["classification"] == "pure_odps_with_outputports"

    def test_filter_structureless_respects_tenant_id_scope(self):
        tenant_a = _create_tenant("Tenant A")
        tenant_b = _create_tenant("Tenant B")
        in_scope = _create_contract(
            tenant_a, hub_contract_json={"models": []}
        )
        _create_contract(tenant_b, hub_contract_json={"models": []})

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=json",
            f"--tenant-id={tenant_a.id}",
            stdout=out,
        )

        json_lines = [
            ln for ln in out.getvalue().splitlines()
            if ln.startswith("{")
        ]
        assert len(json_lines) == 1, (
            "Only Tenant A's contracts should appear when --tenant-id=A"
        )
        record = json.loads(json_lines[0])
        assert record["contract_id"] == str(in_scope.id)


@pytest.mark.django_db(transaction=True)
class OutputJsonContractTests(TestCase):
    """Validate the JSONL row contract — every operator-required field
    must be present and JSON-parseable.
    """

    REQUIRED_FIELDS = {
        "contract_id",
        "tenant_id",
        "asset_id",
        "spec_type",
        "spec_version",
        "classification",
        "models_count",
        "schema_fields_count",
    }

    def test_jsonl_row_has_required_fields(self):
        tenant = _create_tenant()
        _create_contract(tenant, hub_contract_json={"models": []})

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=json",
            stdout=out,
        )

        json_lines = [
            ln for ln in out.getvalue().splitlines()
            if ln.startswith("{")
        ]
        assert json_lines, "Expected at least one JSONL row"
        record = json.loads(json_lines[0])
        missing = self.REQUIRED_FIELDS - set(record)
        assert not missing, f"JSONL row missing fields: {missing}"

    def test_jsonl_row_models_count_reflects_payload(self):
        tenant = _create_tenant()
        # One model with empty fields — still structureless (per predicate)
        _create_contract(
            tenant,
            hub_contract_json={"models": [{"name": "orders", "fields": []}]},
        )

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=json",
            stdout=out,
        )

        json_lines = [
            ln for ln in out.getvalue().splitlines()
            if ln.startswith("{")
        ]
        record = json.loads(json_lines[0])
        # The contract has 1 model entry but 0 fields — both are
        # surfaced so the operator can understand "why structureless".
        assert record["models_count"] == 1
        assert record["schema_fields_count"] == 0

    def test_output_json_default_path_emits_to_stdout(self):
        """When --output=json is given without a path, JSONL goes to
        stdout so the operator can pipe it through jq."""
        tenant = _create_tenant()
        _create_contract(tenant, hub_contract_json={"models": []})

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=json",
            stdout=out,
        )

        # At least one valid JSON object must appear on its own line.
        for ln in out.getvalue().splitlines():
            if ln.startswith("{"):
                json.loads(ln)  # raises if malformed
                return
        raise AssertionError("No JSONL row emitted to stdout")
