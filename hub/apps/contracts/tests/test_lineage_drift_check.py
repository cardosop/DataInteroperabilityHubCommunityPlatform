"""
Phase 228 (228.0.DoD.3) — lineage_drift_check management command tests.

The drift-check command is the verification gate that closes DoD.3 —
"Backfill executed against staging; row count reconciles to JSON
within ±0.1%". It is the **operator's one-shot post-backfill check**:
emit a structured JSON status (ok / DRIFT / EMPTY) the staging
workflow can archive and ops can grep for ``"status": "ok"``.

The command must be:

* **Idempotent + read-only** — never modifies LineageEdge rows; only
  reads + computes.
* **Tenant-scoped** — ``--tenant=<uuid>`` constrains scope so per-
  tenant drift can be diagnosed independently.
* **Tolerance-configurable** — ``--tolerance=0.001`` (default 0.1%)
  matches REQ-LIN-003.
* **Exit-code-meaningful** — exit 0 on ok / EMPTY, non-zero on DRIFT
  so CI / cron can branch on the return code.
* **Structured output** — JSON to stdout so the operator's wrapper
  script can archive it as an artefact.
"""

from __future__ import annotations

import json
import uuid
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import TransactionTestCase


def _create_tenant():
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"Drift Co {suffix}", slug=f"drift-{suffix}")


def _create_contract(tenant, *, lineage_entries=None):
    from hub.apps.contracts.models import Contract

    hub_contract = {
        "models": [{"name": "m", "fields": [{"name": "id", "type": "string"}]}],
        "schema": {"fields": []},
    }
    if lineage_entries is not None:
        hub_contract["lineage"] = {"contracts": lineage_entries}
    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw="kind: DataContract\napiVersion: v3.0.2\nid: c\nname: c\nversion: 1.0.0\nstatus: active\n",
        hub_contract_json=hub_contract,
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


def _run(*flags) -> tuple[str, int]:
    """Run the command, return (stdout, exit-code-equivalent).

    The command uses ``raise CommandError`` for the DRIFT exit-code-
    meaningful path; tests catch that and translate to a non-zero
    code so the assertion stays clean.
    """
    out = StringIO()
    try:
        call_command("lineage_drift_check", *flags, stdout=out)
        return out.getvalue(), 0
    except CommandError:
        return out.getvalue(), 1


@pytest.mark.django_db(transaction=True)
class TestEmptyScope(TransactionTestCase):
    """A tenant with zero contracts → status=EMPTY; exit 0."""

    def test_empty_tenant_returns_empty_status(self):
        # Use a freshly-created empty tenant so the result is
        # deterministic regardless of other tests' data in the shared DB.
        empty_tenant = _create_tenant()
        out, code = _run(f"--tenant={empty_tenant.id}")
        assert code == 0
        report = self._parse_report(out)
        assert report["status"] == "EMPTY"
        assert report["json_entries"] == 0
        assert report["edges_open"] == 0

    @staticmethod
    def _parse_report(out: str) -> dict:
        """Parse the trailing JSON object from the command output."""
        # The command emits one JSON object per line of stdout — the
        # trailing line is the canonical report.
        lines = [ln for ln in out.strip().splitlines() if ln.startswith("{")]
        assert lines, f"no JSON line in output: {out!r}"
        return json.loads(lines[-1])


@pytest.mark.django_db(transaction=True)
class TestNoDrift(TransactionTestCase):
    """Backfill ran cleanly → counts match → status=ok."""

    def test_no_drift_after_backfill(self):
        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        _create_contract(
            tenant,
            lineage_entries=[
                {
                    "source_contract": str(upstream.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                },
            ],
        )
        # Signal handler ran on save, so edges should match JSON entries.
        out, code = _run(f"--tenant={tenant.id}")
        assert code == 0, f"expected exit 0; got code={code}, out={out!r}"
        report = TestEmptyScope._parse_report(out)
        assert report["status"] == "ok"
        assert report["json_entries"] == report["edges_open"] >= 1
        assert report["delta_pct"] == 0.0


@pytest.mark.django_db(transaction=True)
class TestDriftDetected(TransactionTestCase):
    """JSON entry exists but no LineageEdge row → DRIFT, exit non-zero."""

    def test_drift_above_tolerance_returns_nonzero(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        _create_contract(
            tenant,
            lineage_entries=[
                {
                    "source_contract": str(upstream.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                },
            ],
        )
        # Simulate drift: delete the edge row but leave the JSON entry.
        LineageEdge.objects.filter(tenant=tenant).delete()

        out, code = _run(f"--tenant={tenant.id}", "--tolerance=0.001")
        assert code != 0, (
            f"DRIFT must produce non-zero exit so CI / cron can branch; got code={code}"
        )
        report = TestEmptyScope._parse_report(out)
        assert report["status"] == "DRIFT"
        assert report["json_entries"] == 1
        assert report["edges_open"] == 0


@pytest.mark.django_db(transaction=True)
class TestTenantScope(TransactionTestCase):
    """``--tenant`` constrains scope — drift in tenant A is invisible
    to a check scoped to tenant B."""

    def test_tenant_scope_isolates_drift(self):
        from hub.apps.contracts.models import LineageEdge

        tenant_a = _create_tenant()
        tenant_b = _create_tenant()
        upstream_a = _create_contract(tenant_a)
        _create_contract(
            tenant_a,
            lineage_entries=[
                {
                    "source_contract": str(upstream_a.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                },
            ],
        )
        # Create drift in tenant A only.
        LineageEdge.objects.filter(tenant=tenant_a).delete()

        # Tenant B is clean (no contracts at all).
        _, code_b = _run(f"--tenant={tenant_b.id}")
        assert code_b == 0, "tenant B is clean; should exit 0"

        # Tenant A has drift.
        _, code_a = _run(f"--tenant={tenant_a.id}")
        assert code_a != 0, "tenant A has drift; should exit non-zero"


@pytest.mark.django_db(transaction=True)
class TestToleranceFlag(TransactionTestCase):
    """``--tolerance`` configures the threshold; loose tolerance can
    accept what tight tolerance rejects."""

    def test_tolerance_relaxes_drift_classification(self):
        # Build a scenario with exactly 1% drift (10 JSON entries, 9 edges).
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstreams = [_create_contract(tenant) for _ in range(10)]
        _create_contract(
            tenant,
            lineage_entries=[
                {
                    "source_contract": str(u.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                }
                for u in upstreams
            ],
        )
        # Delete exactly one edge → 1/10 = 10% drift.
        first_edge = LineageEdge.objects.filter(tenant=tenant).first()
        first_edge.delete()

        # Tight tolerance (0.001 = 0.1%) → DRIFT.
        _, code_tight = _run(f"--tenant={tenant.id}", "--tolerance=0.001")
        assert code_tight != 0

        # Loose tolerance (0.5 = 50%) → ok.
        _, code_loose = _run(f"--tenant={tenant.id}", "--tolerance=0.5")
        assert code_loose == 0
