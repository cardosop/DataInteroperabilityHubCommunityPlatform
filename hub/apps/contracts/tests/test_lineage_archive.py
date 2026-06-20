"""
Phase 228 F5 (228.F5.5 + F5.6 + F5.11) — lineage-archive surface tests.

Pins:

* The ``archive_lineage_edges`` management command moves closed-and-old
  ``LineageEdge`` rows into ``LineageEdgeArchive`` (default target).
* ``--target=s3`` exports a parquet/jsonl bundle to the configured
  bucket and marks the archive rows ``exported_to_s3_at``.
* ``--before=<date>`` selects only rows whose ``valid_to`` predates
  the cutoff. Rows still open (``valid_to IS NULL``) are NEVER
  archived — they are the load-bearing current state.
* Idempotent: re-running the command with the same ``--before`` cutoff
  produces zero new archive rows (no double-archival).
* The original ``LineageEdge`` row is DELETED after a successful move
  (the spec semantics of "moved", not "copied"). The
  ``original_edge_id`` field on the archive row preserves the old PK
  for restore-to-hot operations.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone


def _create_tenant():
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"LA Co {suffix}",
        slug=f"la-co-{suffix}",
    )


def _create_contract(tenant):
    from hub.apps.contracts.models import Contract

    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=(
            "kind: DataContract\napiVersion: v3.0.2\nid: c\nname: c\n"
            "version: 1.0.0\nstatus: active\n"
        ),
        hub_contract_json={
            "models": [{"name": "m", "fields": [{"name": "id", "type": "string"}]}],
            "schema": {"fields": []},
        },
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


def _create_closed_edge(tenant, src, tgt, *, valid_from, valid_to):
    """Closed historical edge: valid_to is non-NULL."""
    from hub.apps.contracts.models import LineageEdge

    e = LineageEdge.objects.create(
        tenant=tenant,
        source_contract=src,
        target_contract=tgt,
        edge_type="derivation",
    )
    LineageEdge.objects.filter(pk=e.pk).update(
        valid_from=valid_from,
        valid_to=valid_to,
    )
    e.refresh_from_db()
    return e


def _create_open_edge(tenant, src, tgt):
    """Open current edge: valid_to is NULL."""
    from hub.apps.contracts.models import LineageEdge

    return LineageEdge.objects.create(
        tenant=tenant,
        source_contract=src,
        target_contract=tgt,
        edge_type="reference",
    )


@pytest.mark.django_db(transaction=True)
class TestArchiveLineageEdgesDefaultTarget(TransactionTestCase):
    """``--target=archive`` (default) moves closed-and-old rows from
    ``LineageEdge`` to ``LineageEdgeArchive``."""

    def test_moves_closed_old_rows_to_archive(self):
        from hub.apps.contracts.models import LineageEdge, LineageEdgeArchive

        tenant = _create_tenant()
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)

        # Two-year-old closed edge — eligible for archival.
        old_close = timezone.now() - timedelta(days=730)
        old_edge = _create_closed_edge(
            tenant,
            src,
            tgt,
            valid_from=old_close - timedelta(days=10),
            valid_to=old_close,
        )

        cutoff = (timezone.now() - timedelta(days=365)).date().isoformat()
        out = StringIO()
        call_command(
            "archive_lineage_edges",
            f"--before={cutoff}",
            stdout=out,
        )

        # The hot row is gone; an archive row exists carrying the
        # original UUID.
        assert not LineageEdge.objects.filter(pk=old_edge.pk).exists()
        archived = LineageEdgeArchive.objects.filter(
            original_edge_id=old_edge.pk,
        )
        assert archived.count() == 1
        a = archived.get()
        assert a.tenant_id == tenant.id
        assert a.edge_type == "derivation"
        assert a.exported_to_s3_at is None  # default target = archive only

    def test_open_edges_never_archived(self):
        """``valid_to IS NULL`` rows are the current state — they
        MUST survive any archival run."""
        from hub.apps.contracts.models import LineageEdge, LineageEdgeArchive

        tenant = _create_tenant()
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        open_edge = _create_open_edge(tenant, src, tgt)

        cutoff = (timezone.now() + timedelta(days=1)).date().isoformat()
        # Even with a cutoff in the future, an open edge is NOT eligible.
        call_command(
            "archive_lineage_edges",
            f"--before={cutoff}",
            stdout=StringIO(),
        )

        assert LineageEdge.objects.filter(pk=open_edge.pk).exists()
        assert (
            LineageEdgeArchive.objects.filter(
                original_edge_id=open_edge.pk,
            ).count()
            == 0
        )

    def test_idempotent_rerun(self):
        from hub.apps.contracts.models import LineageEdgeArchive

        tenant = _create_tenant()
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        old_close = timezone.now() - timedelta(days=730)
        edge = _create_closed_edge(
            tenant,
            src,
            tgt,
            valid_from=old_close - timedelta(days=10),
            valid_to=old_close,
        )

        cutoff = (timezone.now() - timedelta(days=365)).date().isoformat()
        for _ in range(2):
            call_command(
                "archive_lineage_edges",
                f"--before={cutoff}",
                stdout=StringIO(),
            )

        # Exactly one archive row, even after two runs.
        assert (
            LineageEdgeArchive.objects.filter(
                original_edge_id=edge.pk,
            ).count()
            == 1
        )

    def test_recently_closed_rows_NOT_archived(self):
        """A row closed inside the hot window (e.g. 30 days ago) MUST
        survive — it's still in the SLA-defined hot retention."""
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        recent_close = timezone.now() - timedelta(days=30)
        edge = _create_closed_edge(
            tenant,
            src,
            tgt,
            valid_from=recent_close - timedelta(days=1),
            valid_to=recent_close,
        )

        cutoff = (timezone.now() - timedelta(days=365)).date().isoformat()
        call_command(
            "archive_lineage_edges",
            f"--before={cutoff}",
            stdout=StringIO(),
        )

        assert LineageEdge.objects.filter(pk=edge.pk).exists(), (
            "row closed AFTER cutoff must survive archival"
        )

    def test_dry_run_lists_without_mutation(self):
        from hub.apps.contracts.models import LineageEdge, LineageEdgeArchive

        tenant = _create_tenant()
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        old_close = timezone.now() - timedelta(days=730)
        edge = _create_closed_edge(
            tenant,
            src,
            tgt,
            valid_from=old_close - timedelta(days=10),
            valid_to=old_close,
        )

        cutoff = (timezone.now() - timedelta(days=365)).date().isoformat()
        out = StringIO()
        call_command(
            "archive_lineage_edges",
            f"--before={cutoff}",
            "--dry-run",
            stdout=out,
        )
        envelope = json.loads(out.getvalue().strip())
        assert envelope["dry_run"] is True
        assert envelope["candidates"] == 1

        # No mutation.
        assert LineageEdge.objects.filter(pk=edge.pk).exists()
        assert (
            LineageEdgeArchive.objects.filter(
                original_edge_id=edge.pk,
            ).count()
            == 0
        )


@pytest.mark.django_db(transaction=True)
class TestArchiveLineageEdgesS3Target(TransactionTestCase):
    """``--target=s3`` exports archive rows to S3 and DELETES the
    archive row per spec REQ-LIN-F5-004 (the S3 object becomes the
    canonical record). The S3 client is patched at the boundary
    (``_s3_put_object``); the rest of the pipeline is real."""

    def setUp(self):
        """Purge any archive rows left by a previous --reuse-db run."""
        from hub.apps.contracts.models import LineageEdgeArchive
        LineageEdgeArchive.objects.all().delete()

    def test_target_s3_exports_then_deletes_archive_row(self):
        """Spec REQ-LIN-F5-004 / DoD-G4 — successful S3 PUT removes
        the row from LineageEdgeArchive."""
        from hub.apps.contracts.models import LineageEdgeArchive

        tenant = _create_tenant()
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        old_close = timezone.now() - timedelta(days=900)
        edge = _create_closed_edge(
            tenant,
            src,
            tgt,
            valid_from=old_close - timedelta(days=30),
            valid_to=old_close,
        )

        cutoff = (timezone.now() - timedelta(days=365)).date().isoformat()
        call_command(
            "archive_lineage_edges",
            f"--before={cutoff}",
            stdout=StringIO(),
        )
        archived = LineageEdgeArchive.objects.get(
            original_edge_id=edge.pk,
        )
        archived_id = archived.pk

        with mock.patch(
            "hub.apps.contracts.management.commands.archive_lineage_edges._s3_put_object"
        ) as put_obj:
            put_obj.return_value = "s3://meshant-test-lineage-archive/2026/05/abc.jsonl.gz"
            call_command(
                "archive_lineage_edges",
                f"--before={cutoff}",
                "--target=s3",
                "--bucket=meshant-test-lineage-archive",
                stdout=StringIO(),
            )
            put_obj.assert_called_once()

        # Spec REQ-LIN-F5-004 scenario "Archive to S3" requires the
        # row be REMOVED from LineageEdgeArchive after a successful
        # S3 export.
        assert not LineageEdgeArchive.objects.filter(pk=archived_id).exists(), (
            "row must be deleted from LineageEdgeArchive after successful "
            "S3 export per spec REQ-LIN-F5-004"
        )

    def test_s3_target_idempotent_rerun_after_delete(self):
        """Re-running with the same cutoff after all eligible rows
        were exported finds zero candidates → zero S3 PUTs.

        Replaces the legacy ``test_s3_target_skips_already_exported``
        which was meaningful only when rows were preserved with
        ``exported_to_s3_at`` set."""
        from hub.apps.contracts.models import LineageEdgeArchive

        tenant = _create_tenant()
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        old_close = timezone.now() - timedelta(days=900)
        _create_closed_edge(
            tenant,
            src,
            tgt,
            valid_from=old_close - timedelta(days=30),
            valid_to=old_close,
        )
        cutoff = (timezone.now() - timedelta(days=365)).date().isoformat()
        call_command(
            "archive_lineage_edges",
            f"--before={cutoff}",
            stdout=StringIO(),
        )
        # Drive first S3 export — deletes the archive row per spec.
        with mock.patch(
            "hub.apps.contracts.management.commands.archive_lineage_edges._s3_put_object"
        ) as put_obj:
            put_obj.return_value = "s3://meshant-test-lineage-archive/old/key.jsonl.gz"
            call_command(
                "archive_lineage_edges",
                f"--before={cutoff}",
                "--target=s3",
                "--bucket=meshant-test-lineage-archive",
                stdout=StringIO(),
            )
            assert put_obj.call_count == 1
        assert LineageEdgeArchive.objects.count() == 0

        # Second run — nothing left to export; zero PUTs.
        with mock.patch(
            "hub.apps.contracts.management.commands.archive_lineage_edges._s3_put_object"
        ) as put_obj:
            call_command(
                "archive_lineage_edges",
                f"--before={cutoff}",
                "--target=s3",
                "--bucket=meshant-test-lineage-archive",
                stdout=StringIO(),
            )
            put_obj.assert_not_called()
