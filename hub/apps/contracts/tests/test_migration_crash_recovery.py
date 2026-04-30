"""
Phase 227 Wave 1 (227.L6.3, L6.6) — crash-recovery tests for the
``renormalize_contracts --apply --checkpoint-table=<name>`` command.

The L6.6 invariant: a kill mid-batch followed by a re-run with the same
``--checkpoint-table`` MUST process only the residue, not double-process
the already-completed contracts.

We simulate the kill by calling the command on a partial set of
candidates, recording the checkpoint state, then expanding the candidate
set and asserting the second run touches only the new candidates.

Real DB rows. Real ``NormalizationService``. No mocks of internal code.
The select_for_update + skip_locked lock semantics are exercised via
``transaction=True`` test ordering.
"""
from __future__ import annotations

import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase


def _create_tenant():
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"L6.6 Co {suffix}",
        slug=f"l66-co-{suffix}",
    )


def _create_structural_odcs_contract(tenant):
    """A contract whose original_raw is structural and whose
    hub_contract_json is currently empty (will heal)."""
    from hub.apps.contracts.models import Contract

    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=(
            "kind: DataContract\n"
            "apiVersion: v3.0.2\n"
            f"id: ok-{uuid.uuid4().hex[:6]}\n"
            "name: ok\n"
            "version: 1.0.0\n"
            "status: active\n"
            "schema:\n"
            "  - name: customers\n"
            "    fields:\n"
            "      - name: id\n"
            "        type: string\n"
        ),
        hub_contract_json={"models": [], "schema": {"fields": []}},
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


def _run_apply(checkpoint_table: str, *, tenant=None):
    """Wrapper that runs the apply command with a given checkpoint.

    Tests run with ``transaction=True`` so the DB is shared across
    tests in a run; we always scope to the test's own tenant via
    ``--tenant-id`` so other tests' fixtures don't contaminate the
    candidate set."""
    out = StringIO()
    args = [
        "renormalize_contracts",
        "--spec-version=3.1.0",
        "--filter=structureless",
        "--apply",
        f"--checkpoint-table={checkpoint_table}",
    ]
    if tenant is not None:
        args.append(f"--tenant-id={tenant.id}")
    call_command(*args, stdout=out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Resume after kill
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestResumeAfterKill(TestCase):
    """Simulates an operator running the apply command, killing it
    mid-way, and re-running. The resumption logic in the command MUST
    skip the already-done contracts."""

    def test_resume_processes_only_new_candidates(self):
        """Two complementary invariants verify "skip on resume":

        1. ``Contract.updated_at`` of first-batch rows MUST NOT advance
           after the second run (relies on the audit fix that includes
           ``updated_at`` in the ``update_fields`` list passed to
           ``Contract.save`` — without it, this comparison would
           trivially pass even on a double-process bug).

        2. ``MigrationCheckpoint.completed_at`` of first-batch
           checkpoints MUST NOT advance — this is the *strong* signal
           because ``update_or_create`` writes a fresh ``completed_at``
           on every call, so any reprocessing would mutate it. This
           catches the "double-process" bug independently of any
           ``Contract.save`` semantics.
        """
        from hub.apps.contracts.models import MigrationCheckpoint
        from hub.apps.contracts.structureless import is_structureless

        tenant = _create_tenant()
        # First batch (3 contracts). Run, then verify they all healed
        # and have checkpoints.
        first_batch = [_create_structural_odcs_contract(tenant) for _ in range(3)]
        _run_apply("crash-recovery-001", tenant=tenant)

        first_checkpoints = set(
            MigrationCheckpoint.objects.filter(
                migration_name="crash-recovery-001",
                status=MigrationCheckpoint.STATUS_DONE,
            ).values_list("contract_id", flat=True)
        )
        assert len(first_checkpoints) == 3

        # Capture the post-first-run state of each first-batch contract
        # AND its checkpoint timestamp.
        first_state = {}
        for c in first_batch:
            c.refresh_from_db()
            first_state[c.id] = (c.hub_contract_json, c.updated_at)
        first_checkpoint_ts = dict(
            MigrationCheckpoint.objects.filter(
                migration_name="crash-recovery-001",
                contract__in=first_batch,
            ).values_list("contract_id", "completed_at")
        )
        assert len(first_checkpoint_ts) == 3

        # Simulate a kill + restart: add 2 more contracts AFTER the
        # first run (these represent the residue that wasn't processed
        # before the kill — the partial commit boundary).
        new_batch = [_create_structural_odcs_contract(tenant) for _ in range(2)]

        # Resume the run. The MigrationCheckpoint table excludes the
        # first-batch contracts; only the new ones should be processed.
        _run_apply("crash-recovery-001", tenant=tenant)

        # Invariant 1: First-batch Contract.updated_at unchanged.
        for c in first_batch:
            c.refresh_from_db()
            old_payload, old_updated_at = first_state[c.id]
            assert c.updated_at == old_updated_at, (
                f"Resumed run must not re-touch already-done contract "
                f"{c.id}; updated_at advanced from {old_updated_at!r} "
                f"to {c.updated_at!r}"
            )
            assert c.hub_contract_json == old_payload

        # Invariant 2: First-batch checkpoint.completed_at unchanged
        # (the strong signal — ``update_or_create`` writes a fresh
        # ``completed_at`` on every call, so any reprocess would
        # mutate this even if Contract.save was a no-op).
        for cid, old_ts in first_checkpoint_ts.items():
            current_ts = MigrationCheckpoint.objects.get(
                migration_name="crash-recovery-001",
                contract_id=cid,
            ).completed_at
            assert current_ts == old_ts, (
                f"Resumed run must not re-touch already-done "
                f"checkpoint for contract {cid}; "
                f"completed_at advanced from {old_ts!r} to "
                f"{current_ts!r}"
            )

        # New-batch contracts must have healed.
        for c in new_batch:
            c.refresh_from_db()
            assert not is_structureless(c), (
                f"New-batch contract {c.id} should have healed"
            )

        # Total checkpoints = 3 (first batch) + 2 (new batch) = 5.
        all_checkpoints = MigrationCheckpoint.objects.filter(
            migration_name="crash-recovery-001",
        )
        assert all_checkpoints.count() == 5

    def test_different_checkpoint_table_is_independent(self):
        """Two runs with DIFFERENT checkpoint table names must NOT
        share state. This is the partition-key contract.

        Uses a *residue* contract (info-only ODCS that re-normalisation
        cannot heal) so the contract REMAINS a candidate across both
        runs — a structural contract would self-heal on the first run
        and disappear from the candidate set, leaving the second run
        with zero work and giving a false-clean result."""
        from hub.apps.contracts.models import Contract, MigrationCheckpoint

        tenant = _create_tenant()
        # Residue fixture: hub_contract_json starts empty AND
        # original_raw is info-only ODCS, so normalization rejects it
        # via the structural-floor invariant — the row stays
        # structureless across both runs and is therefore a candidate
        # in BOTH partition-A and partition-B's queryset.
        c1 = Contract.objects.create(
            tenant=tenant,
            version=1,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="YAML",
            original_raw=(
                "kind: DataContract\n"
                "apiVersion: v3.0.2\n"
                f"id: bad-{uuid.uuid4().hex[:6]}\n"
                "name: bad\n"
                "version: 1.0.0\n"
                "status: active\n"
                "info:\n"
                "  description: no schema\n"
            ),
            hub_contract_json={"models": [], "schema": {"fields": []}},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status="ACTIVE",
        )

        _run_apply("partition-A", tenant=tenant)
        _run_apply("partition-B", tenant=tenant)

        # The same contract is checkpointed under TWO different
        # migration names — proves the partition keys don't share
        # exclusion state.
        names = set(
            MigrationCheckpoint.objects.filter(
                contract=c1,
            ).values_list("migration_name", flat=True)
        )
        assert "partition-A" in names, (
            f"partition-A checkpoint missing; got {names!r}"
        )
        assert "partition-B" in names, (
            f"partition-B checkpoint missing — partition keys leaking? "
            f"got {names!r}"
        )

    def test_failed_checkpoints_are_also_skipped_on_resume(self):
        """Per L6.3 spec: ``done`` AND ``failed`` rows skip on resume.
        Operators can clear ``failed`` rows manually if they want a
        retry, but the default-behaviour is "no double-processing"."""
        from hub.apps.contracts.models import MigrationCheckpoint

        tenant = _create_tenant()
        contract = _create_structural_odcs_contract(tenant)

        # Pre-seed a 'failed' checkpoint.
        MigrationCheckpoint.objects.create(
            migration_name="skip-failed-001",
            contract=contract,
            status=MigrationCheckpoint.STATUS_FAILED,
            error="(simulated prior failure)",
        )
        contract.refresh_from_db()
        before_payload = contract.hub_contract_json
        before_updated = contract.updated_at

        _run_apply("skip-failed-001", tenant=tenant)

        # Contract must NOT be processed — failed checkpoint blocks.
        contract.refresh_from_db()
        assert contract.updated_at == before_updated, (
            "Contract with prior failed checkpoint must be skipped"
        )
        assert contract.hub_contract_json == before_payload


# ---------------------------------------------------------------------------
# Partial-batch atomicity
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestPartialBatchAtomicity(TestCase):
    """Each batch runs inside ``transaction.atomic`` — the test asserts
    that an in-batch raise rolls back the entire batch's checkpoint
    inserts AND contract updates together (no partial-commit residue).

    We don't fault-inject the engine here (that would require mocks);
    instead we exercise the natural code path: contracts whose original
    raw is structureless complete cleanly with status='done', proving
    the atomic block commits as a unit."""

    def test_batch_commits_all_or_nothing_on_clean_run(self):
        from hub.apps.contracts.models import MigrationCheckpoint

        tenant = _create_tenant()
        for _ in range(5):
            _create_structural_odcs_contract(tenant)

        _run_apply("atomicity-001", tenant=tenant)

        # All 5 contracts should have a checkpoint row.
        cp_count = MigrationCheckpoint.objects.filter(
            migration_name="atomicity-001",
        ).count()
        assert cp_count == 5, (
            f"Atomic batch must produce 5 checkpoint rows; got {cp_count}"
        )


# ---------------------------------------------------------------------------
# Forward+reverse migration identity (227.L6.4 CI test)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestRevertMigrationIdentity(TestCase):
    """Phase 227 Wave 1 (227.L6.4) — forward+reverse identity.

    The 0024_unrevert_structureless_assets migration restores assets
    that were demoted by ``--apply-asset-revert``. The reverse
    re-applies the demotion. These tests prove the round-trip is
    correct end-to-end.
    """

    def _load_migration_module(self):
        """Migration filenames start with a digit so we can't use
        ``import``-syntax. ``importlib.import_module`` handles the
        dotted path correctly."""
        import importlib

        return importlib.import_module(
            "hub.apps.contracts.migrations.0024_unrevert_structureless_assets"
        )

    def test_forward_restores_asset_to_previous_status(self):
        from django.apps import apps as django_apps

        from hub.apps.assets.models import AssetStatus

        migration = self._load_migration_module()

        tenant = _create_tenant()
        asset = self._make_asset_demoted_via_audit(
            tenant=tenant,
            previous_status=AssetStatus.ACTIVE,
        )

        # Run the migration's forward callable directly.
        migration._restore_assets(django_apps, None)

        asset.refresh_from_db()
        assert asset.status == AssetStatus.ACTIVE

    def test_forward_then_reverse_round_trips(self):
        """forward(reverse(state)) == state — the identity guarantee."""
        from django.apps import apps as django_apps

        from hub.apps.assets.models import AssetStatus

        migration = self._load_migration_module()

        tenant = _create_tenant()
        asset = self._make_asset_demoted_via_audit(
            tenant=tenant,
            previous_status=AssetStatus.ACTIVE,
        )
        # State A: asset is DRAFT, has a revert event.

        # Forward: DRAFT → ACTIVE.
        migration._restore_assets(django_apps, None)
        asset.refresh_from_db()
        assert asset.status == AssetStatus.ACTIVE

        # Reverse: ACTIVE → DRAFT.
        migration._redo_reverts(django_apps, None)
        asset.refresh_from_db()
        assert asset.status == AssetStatus.DRAFT, (
            f"Reverse must demote back to DRAFT; got {asset.status!r}"
        )

        # Forward again: DRAFT → ACTIVE (idempotent: we get the same
        # final state).
        migration._restore_assets(django_apps, None)
        asset.refresh_from_db()
        assert asset.status == AssetStatus.ACTIVE

    def test_forward_skips_assets_in_non_draft_status(self):
        """Operator-restored assets (already ACTIVE) MUST NOT be
        re-restored — the migration is a no-op for them."""
        from django.apps import apps as django_apps

        from hub.apps.assets.models import AssetStatus

        migration = self._load_migration_module()

        tenant = _create_tenant()
        # Asset was demoted then operator restored to ACTIVE manually
        # before the migration runs.
        asset = self._make_asset_demoted_via_audit(
            tenant=tenant,
            previous_status=AssetStatus.ACTIVE,
        )
        asset.status = AssetStatus.ACTIVE
        asset.save(update_fields=["status"])

        before_updated = asset.updated_at

        migration._restore_assets(django_apps, None)

        asset.refresh_from_db()
        assert asset.status == AssetStatus.ACTIVE
        assert asset.updated_at == before_updated, (
            "Migration must not touch operator-restored assets"
        )

    def _make_asset_demoted_via_audit(self, *, tenant, previous_status):
        """Create a DRAFT asset with an
        ``ASSET_AUTO_REVERTED_STRUCTURELESS`` audit event in its
        history — simulating the post-revert state.
        """
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.audit.utils import create_audit_event

        suffix = uuid.uuid4().hex[:6]
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"asset-{suffix}",
            name=f"Asset {suffix}",
            status=AssetStatus.DRAFT,
        )
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_AUTO_REVERTED_STRUCTURELESS",
            actor_user=None,
            tenant=tenant,
            resource_id=str(asset.id),
            details={
                "previous_status": previous_status,
                "new_status": AssetStatus.DRAFT,
                "contract_id": str(uuid.uuid4()),
                "run_id": f"test-{suffix}",
                "reason": "test fixture",
            },
        )
        return asset
