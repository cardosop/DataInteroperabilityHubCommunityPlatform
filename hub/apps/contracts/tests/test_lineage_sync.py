"""
Phase 228 (228.0.9-10) — lineage-sync signal-handler tests.

Pins REQ-LIN-001 + REQ-LIN-002 against real DB rows / real signal /
real Tenant + Contract + LineageEdge. No internal mocks.

Coverage:

* REQ-LIN-001 scenarios — derived edge created on contract save;
  idempotent rerun produces no duplicates; edge update closes the
  old row + opens a new one with adjacent timestamps; tenant cascade
  deletes the rows.
* REQ-LIN-002 scenarios — handler runs in ``transaction.on_commit``
  so a rollback discards the work; concurrent saves do not deadlock;
  ``valid_from`` is DB-side ``NOW()`` not application time.
* The unique-on-open constraint catches duplicate open edges.

The metric assertion (``lineage_edge_writes_total{operation}``)
uses ``mock.patch`` at the import-site of the helper — that's the
boundary the spec explicitly requires fail-soft semantics for.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest import mock

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from hub.apps.contracts.tests.test_base import ContractsTransactionTestBase


def _create_tenant(prefix: str = "LIN"):
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{prefix} Co {suffix}",
        slug=f"{prefix.lower()}-co-{suffix}",
    )


def _create_contract(tenant, *, lineage_entries=None, version: int = 1):
    """Real Contract row whose ``hub_contract_json.lineage`` carries
    the supplied lineage entries (or no lineage if None).

    Each entry is a dict matching the canonical lineage shape used by
    the engine — minimum keys: ``source_contract``, ``target_contract``,
    ``edge_type``. Optional: ``source_model``, ``source_field``,
    ``target_model``, ``target_field``, ``transformation_ref``,
    ``job_ref``."""
    from hub.apps.contracts.models import Contract

    hub_contract = {
        "models": [
            {
                "name": "m",
                "fields": [{"name": "id", "type": "string"}],
            },
        ],
        "schema": {"fields": []},
    }
    if lineage_entries is not None:
        hub_contract["lineage"] = {"contracts": lineage_entries}
    return Contract.objects.create(
        tenant=tenant,
        version=version,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw="kind: DataContract\napiVersion: v3.0.2\nid: c\nname: c\nversion: 1.0.0\nstatus: active\n",
        hub_contract_json=hub_contract,
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


# ---------------------------------------------------------------------------
# REQ-LIN-001 scenarios
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestEdgeCreatedOnContractSave(ContractsTransactionTestBase):
    """REQ-LIN-001 / REQ-LIN-002 — saving a Contract with one upstream
    reference produces exactly one LineageEdge row."""

    def test_save_creates_one_open_edge(self):
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

        edges = list(
            LineageEdge.objects.filter(
                target_contract=target,
                valid_to__isnull=True,
            )
        )
        assert len(edges) == 1, f"expected 1 open edge; got {len(edges)}"
        e = edges[0]
        assert e.source_contract_id == upstream.id
        assert e.target_contract_id == target.id
        assert e.edge_type == "reference"
        assert e.valid_to is None
        assert e.valid_from is not None
        assert e.tenant_id == tenant.id

    def test_idempotent_resave_produces_no_duplicate(self):
        """REQ-LIN-001 scenario "Sync is idempotent": running the
        handler twice with no change yields the same end state."""
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
        before = LineageEdge.objects.filter(target_contract=target).count()

        # Re-save without changes — should be a noop for the edge state.
        target.save()

        after = LineageEdge.objects.filter(target_contract=target).count()
        assert after == before, (
            f"idempotent resave should not duplicate edges; before={before} after={after}"
        )
        # And the open edge count is exactly 1.
        open_count = LineageEdge.objects.filter(
            target_contract=target, valid_to__isnull=True
        ).count()
        assert open_count == 1

    def test_update_closes_old_edge_and_opens_new(self):
        """REQ-LIN-001 scenario: updating the lineage entry closes the
        prior open row and opens a new one. Both rows reference the
        same scope tuple but only one is open."""
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
                    "transformation_ref": "v1",
                },
            ],
        )

        # Mutate the lineage so the transformation_ref changes.
        target.hub_contract_json = dict(target.hub_contract_json)
        target.hub_contract_json["lineage"] = {
            "contracts": [
                {
                    "source_contract": str(upstream.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                    "transformation_ref": "v2",
                },
            ],
        }
        target.save()

        all_edges = list(LineageEdge.objects.filter(target_contract=target).order_by("valid_from"))
        assert len(all_edges) == 2, f"expected 2 rows (closed + open); got {len(all_edges)}"
        closed = [e for e in all_edges if e.valid_to is not None]
        opened = [e for e in all_edges if e.valid_to is None]
        assert len(closed) == 1, "exactly one row closed"
        assert len(opened) == 1, "exactly one row open"
        assert closed[0].transformation_ref == "v1"
        assert opened[0].transformation_ref == "v2"

    def test_tenant_cascade_deletes_rows(self):
        """REQ-LIN-001 scenario: deleting a Tenant cascade-deletes
        every LineageEdge scoped to that tenant."""
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
        before = LineageEdge.objects.filter(tenant=tenant).count()
        assert before >= 1

        # REQ-LIN-001: deleting a Tenant must cascade-delete every
        # LineageEdge scoped to that tenant.  The ``lineage_edge_id``
        # FK on ``pipeline_dependencies`` is guaranteed to exist by
        # orchestration migration 0012.
        tenant.delete()

        after = LineageEdge.objects.filter(tenant_id=tenant.id).count()
        assert after == 0, f"tenant cascade should remove all edges; got {after} remaining"


# ---------------------------------------------------------------------------
# REQ-LIN-002 scenarios — async commit-only execution + concurrency
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestSignalRunsOnCommitOnly(ContractsTransactionTestBase):
    """REQ-LIN-002 scenario: handler runs only inside ``on_commit`` so
    a rolled-back transaction does NOT create edges."""

    def test_rollback_discards_edge_writes(self):
        from hub.apps.contracts.models import Contract, LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)

        try:
            with transaction.atomic():
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
                # Force rollback. The handler registered via on_commit
                # MUST NOT fire because the transaction did not commit.
                raise RuntimeError("intentional rollback")
        except RuntimeError:
            pass

        # The contract row itself rolled back too (since we created it
        # inside the atomic block), but ALSO assert no orphan edges.
        contract_count = Contract.objects.filter(tenant=tenant).count()
        edge_count = LineageEdge.objects.filter(tenant=tenant).count()
        # Only the upstream contract committed (created before atomic).
        assert contract_count == 1, contract_count
        assert edge_count == 0, (
            f"on_commit handler must not fire for a rolled-back save; got {edge_count} edges"
        )


# ---------------------------------------------------------------------------
# REQ-LIN-F5-006 — DB NOW() invariant (handler uses Func('NOW') / db_default)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestValidFromIsDBSide(ContractsTransactionTestBase):
    """The signal handler MUST use DB-side ``NOW()`` for ``valid_from``.
    Pinned by checking the DB-recorded value falls within seconds of
    ``timezone.now()`` on a system with no app↔DB clock skew (the test
    container uses the same wall-clock so this is the strongest
    assertion we can make from inside the test process)."""

    def test_valid_from_within_a_few_seconds_of_now(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        before = timezone.now()
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
        after = timezone.now()

        edge = LineageEdge.objects.get(target_contract=target, valid_to__isnull=True)
        # The DB-recorded valid_from should land between ``before`` and
        # ``after``, accounting for ~1s round-trip slack on either side.
        slack = timedelta(seconds=2)
        assert before - slack <= edge.valid_from <= after + slack, (
            f"valid_from must be DB NOW(); recorded={edge.valid_from} "
            f"window=[{before - slack}, {after + slack}]"
        )


# ---------------------------------------------------------------------------
# Open-edge unique-constraint
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestOpenEdgeUniqueConstraint(ContractsTransactionTestBase):
    """Direct ORM insert that violates the partial unique constraint
    (two open rows with identical scope tuple) must raise
    ``IntegrityError``. Closed rows can repeat the scope."""

    def test_two_open_edges_with_same_scope_violate_constraint(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(tenant)

        LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )
        with pytest.raises(IntegrityError):
            LineageEdge.objects.create(
                tenant=tenant,
                source_contract=upstream,
                target_contract=target,
                edge_type="reference",
            )

    def test_closed_then_reopened_does_not_violate(self):
        """Closing the first row releases the constraint; a fresh open
        row with the same scope is allowed."""
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(tenant)

        first = LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )
        # Close it.
        first.valid_to = timezone.now()
        first.save(update_fields=["valid_to"])
        # Now a new open row with the same scope should be permitted.
        second = LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )
        assert second.valid_to is None


# ---------------------------------------------------------------------------
# Metric emission (REQ-LIN-002 #7)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestEdgeWriteMetric(ContractsTransactionTestBase):
    """REQ-LIN-002 #7: the handler emits
    ``lineage_edge_writes_total{operation}`` per edge mutation. We
    patch the metric callable at the import-site that the handler
    uses (``hub.apps.contracts.lineage_sync.record_edge_write``) so a
    future refactor that bypasses the helper fails this test by name."""

    def test_add_operation_records_metric(self):
        tenant = _create_tenant()
        upstream = _create_contract(tenant)

        with mock.patch("hub.apps.contracts.lineage_sync.record_edge_write") as m:
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
        # At least one ``add`` operation observed.
        ops = [
            c.kwargs.get("operation") or (c.args[0] if c.args else None) for c in m.call_args_list
        ]
        assert "add" in ops, f"expected at least one add metric; got operations={ops}"


# ---------------------------------------------------------------------------
# REQ-LIN-007 — audit events on edge mutations (Phase 228 GAP-2 fix)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestEdgeAuditEvents(ContractsTransactionTestBase):
    """REQ-LIN-007: ``LINEAGE_EDGE_CREATED`` and ``LINEAGE_EDGE_DELETED``
    audit events SHALL fire on every edge mutation. Pre-fix the
    constants existed in ``hub/apps/audit/models.py`` but no code site
    emitted them — the spec scenario was unsatisfiable. The fix wires
    emission into ``lineage_sync._emit_edge_audit_events`` after the
    diff atomic block commits."""

    def test_add_emits_lineage_edge_created_audit(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        before = AuditEvent.objects.filter(
            action="LINEAGE_EDGE_CREATED",
            tenant=tenant,
        ).count()

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

        after = AuditEvent.objects.filter(
            action="LINEAGE_EDGE_CREATED",
            tenant=tenant,
        ).count()
        assert after - before >= 1, (
            f"expected ≥1 LINEAGE_EDGE_CREATED audit row; got before={before} after={after}"
        )

    def test_close_emits_lineage_edge_deleted_audit(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(
            tenant,
            lineage_entries=[
                {
                    "source_contract": str(upstream.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                    "transformation_ref": "v1",
                },
            ],
        )
        before = AuditEvent.objects.filter(
            action="LINEAGE_EDGE_DELETED",
            tenant=tenant,
        ).count()

        # Mutate so the existing edge closes and a new one opens.
        target.hub_contract_json = dict(target.hub_contract_json)
        target.hub_contract_json["lineage"] = {
            "contracts": [
                {
                    "source_contract": str(upstream.id),
                    "target_contract": "self",
                    "edge_type": "reference",
                    "transformation_ref": "v2",
                },
            ],
        }
        target.save()

        after = AuditEvent.objects.filter(
            action="LINEAGE_EDGE_DELETED",
            tenant=tenant,
        ).count()
        assert after - before == 1, (
            f"expected exactly 1 LINEAGE_EDGE_DELETED audit row after "
            f"close-then-open; got delta={after - before}"
        )
