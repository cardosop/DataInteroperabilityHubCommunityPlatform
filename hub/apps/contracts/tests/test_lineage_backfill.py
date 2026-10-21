"""
Phase 228 (228.0.12, REQ-LIN-003) — backfill command tests.

Pins idempotency, resume-from-checkpoint, dry-run, and the post-run
verification tolerance check. Real DB rows; no mocks of internal
code paths.
"""

from __future__ import annotations

import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TransactionTestCase


def _create_tenant(prefix: str = "BLF"):
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{prefix} Co {suffix}",
        slug=f"{prefix.lower()}-co-{suffix}",
    )


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


def _run(*flags) -> str:
    out = StringIO()
    call_command("backfill_lineage_edges", *flags, stdout=out)
    return out.getvalue()


@pytest.mark.django_db(transaction=True)
class TestBackfillIdempotent(TransactionTestCase):
    """REQ-LIN-003 idempotency invariant: a same-state rerun produces
    no duplicate edges."""

    def test_first_run_creates_edges(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(
            tenant,
            lineage_entries=[
                {
                    "source_contract": str(upstream.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                },
            ],
        )
        # Wipe edges that the live signal handler may have created so
        # we're testing the backfill in isolation.
        LineageEdge.objects.all().delete()

        _run(f"--tenant={tenant.id}")

        edges = LineageEdge.objects.filter(
            target_contract=target,
            valid_to__isnull=True,
        )
        assert edges.count() == 1

    def test_second_run_does_not_duplicate(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(
            tenant,
            lineage_entries=[
                {
                    "source_contract": str(upstream.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                },
            ],
        )
        LineageEdge.objects.all().delete()

        _run(f"--tenant={tenant.id}")
        before = LineageEdge.objects.filter(
            target_contract=target,
            valid_to__isnull=True,
        ).count()
        _run(f"--tenant={tenant.id}")
        after = LineageEdge.objects.filter(
            target_contract=target,
            valid_to__isnull=True,
        ).count()
        assert before == after == 1, (
            f"idempotent rerun must not duplicate edges; before={before} after={after}"
        )


@pytest.mark.django_db(transaction=True)
class TestBackfillDryRun(TransactionTestCase):
    """REQ-LIN-003 scenario: ``--dry-run`` reports without writing."""

    def test_dry_run_does_not_create_edges(self):
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
        LineageEdge.objects.all().delete()

        out = _run(f"--tenant={tenant.id}", "--dry-run")

        assert LineageEdge.objects.count() == 0, "dry-run must not write edges"
        assert "[dry-run]" in out


@pytest.mark.django_db(transaction=True)
class TestBackfillResumeCheckpoint(TransactionTestCase):
    """REQ-LIN-003 scenario: ``--resume-key`` checkpoints survive
    crashes and resume from the next batch.

    The test simulates the crash by saving a checkpoint manually,
    then invoking the command — the command should skip contracts
    whose id is ``<= checkpoint``."""

    def test_resume_skips_contracts_before_checkpoint(self):
        from django.core.cache import cache

        from hub.apps.contracts.models import Contract, LineageEdge

        tenant = _create_tenant()
        # Three contracts with ascending UUIDs.
        c1 = _create_contract(tenant)
        _create_contract(tenant)
        _create_contract(
            tenant,
            lineage_entries=[
                {
                    "source_contract": str(c1.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                },
            ],
        )
        # Wipe edges so the test sees the backfill's writes.
        LineageEdge.objects.all().delete()
        # Plant a resume checkpoint pointing at the LARGEST contract id
        # (sorted by uuid). This means the backfill should skip all
        # three and write zero edges.
        sorted_ids = sorted(Contract.objects.filter(tenant=tenant).values_list("id", flat=True))
        last_uuid = sorted_ids[-1]
        cache.set("backfill_lineage:test-resume", str(last_uuid), timeout=3600)
        try:
            _run(f"--tenant={tenant.id}", "--resume-key=test-resume")
        finally:
            cache.delete("backfill_lineage:test-resume")
        # No edges written because every candidate was past the checkpoint.
        assert LineageEdge.objects.count() == 0


@pytest.mark.django_db(transaction=True)
class TestBackfillVerification(TransactionTestCase):
    """REQ-LIN-003: post-run verification compares open-edge count
    against JSON-lineage-entry count and reports the delta."""

    def test_verification_reports_ok_when_counts_match(self):
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

        out = _run(f"--tenant={tenant.id}")
        assert "verification=ok" in out, (
            f"verification line should report 'ok' when counts match; got: {out!r}"
        )
