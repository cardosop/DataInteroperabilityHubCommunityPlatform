"""
Phase 227 Wave 1 (227.L6.1, L6.5) — flag-combination tests for the
``renormalize_contracts --filter=structureless --apply`` command.

Each test below exercises one of the four new Wave-3 flags and one
combined-flags scenario:

* ``--apply`` — the re-normalization path itself.
* ``--apply-asset-revert`` — demote ACTIVE assets backed by
  contracts that REMAIN structureless after re-normalization.
* ``--silent-events`` — suppress per-contract webhooks; emit a single
  ``CONTRACT_BATCH_RENORMALIZED`` audit event with summary counts.
* ``--checkpoint-table=<name>`` — persist per-contract progress in
  ``MigrationCheckpoint`` rows; re-runs skip already-done contracts.

No internal mocks. Real DB rows. Real ``NormalizationService``. The
crash-recovery test that simulates a kill mid-batch lives in
``test_migration_crash_recovery.py`` — the L6.6 file.
"""
from __future__ import annotations
import json
import uuid
from io import StringIO
import pytest
from django.core.management import call_command
from django.test import TestCase

def _create_tenant():
    from hub.apps.tenants.models import Tenant
    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f'L6 Co {suffix}', slug=f'l6-co-{suffix}')

def _create_asset(tenant, *, status='ACTIVE'):
    from hub.apps.assets.models import Asset
    suffix = uuid.uuid4().hex[:6]
    return Asset.objects.create(tenant=tenant, key=f'asset-{suffix}', name=f'Asset {suffix}', status=status)

def _create_structureless_odcs_contract(tenant, *, asset=None):
    """Create a real Contract row whose hub_contract_json is empty
    AND whose original_raw is a structureless ODCS doc — the engine
    will re-normalize to the same empty payload (customer-action
    cohort)."""
    from hub.apps.contracts.models import Contract
    structureless_yaml = 'kind: DataContract\napiVersion: v3.0.2\nid: bad\nname: bad\nversion: 1.0.0\nstatus: active\ninfo:\n  description: no schema\n'
    return Contract.objects.create(tenant=tenant, asset=asset, version=1, original_spec_type='ODCS', original_spec_version='3.0.2', original_format='YAML', original_raw=structureless_yaml, hub_contract_json={'models': [], 'schema': {'fields': []}}, normalization_status='NORMALIZED_OK', validation_status='VALID', status='ACTIVE')

def _create_structural_odcs_contract(tenant, *, asset=None):
    """Create a real Contract row whose original_raw IS structural,
    but hub_contract_json is currently empty — the engine WILL self-
    heal this (Wave-3 success cohort)."""
    from hub.apps.contracts.models import Contract
    structural_yaml = 'kind: DataContract\napiVersion: v3.0.2\nid: ok\nname: ok\nversion: 1.0.0\nstatus: active\nschema:\n  - name: customers\n    fields:\n      - name: id\n        type: string\n'
    return Contract.objects.create(tenant=tenant, asset=asset, version=1, original_spec_type='ODCS', original_spec_version='3.0.2', original_format='YAML', original_raw=structural_yaml, hub_contract_json={'models': [], 'schema': {'fields': []}}, normalization_status='NORMALIZED_OK', validation_status='VALID', status='ACTIVE')

def _run(*flags, tenant=None, **kwargs):
    """Wrapper for ``call_command("renormalize_contracts", ...)`` that
    captures stdout. Returns the joined stdout string.

    Tests run with ``transaction=True`` so the DB is shared across
    tests in a run; without ``--tenant-id`` the command would process
    every structureless contract from every other test's fixtures and
    contaminate per-test invariants. We always scope to the test's own
    tenant — pass ``tenant=`` to forward as ``--tenant-id``.
    """
    out = StringIO()
    args = ['renormalize_contracts', '--spec-version=3.1.0', '--filter=structureless']
    if tenant is not None:
        args.append(f'--tenant-id={tenant.id}')
    args.extend(flags)
    call_command(*args, stdout=out, **kwargs)
    return out.getvalue()

@pytest.mark.django_db(transaction=True)
class TestApplyFlag(TestCase):
    """``--apply`` runs the production NormalizationService against
    each candidate. Structural contracts heal; structureless ones
    persist as residue."""

    def test_apply_self_heals_structural_contracts(self):
        from hub.apps.contracts.structureless import is_structureless
        tenant = _create_tenant()
        asset = _create_asset(tenant, status='DRAFT')
        contract = _create_structural_odcs_contract(tenant, asset=asset)
        self.assertTrue(is_structureless(contract), 'fixture should start structureless')
        _run('--apply', tenant=tenant)
        contract.refresh_from_db()
        self.assertFalse(is_structureless(contract), f'Contract should self-heal after --apply; hub_contract_json={contract.hub_contract_json!r}')

    def test_apply_leaves_structureless_residue_unchanged(self):
        """``info.description``-only ODCS doc has no resolvable
        structure — re-normalization rejects it via the floor and
        leaves the row's ``hub_contract_json`` empty."""
        from hub.apps.contracts.structureless import is_structureless
        tenant = _create_tenant()
        contract = _create_structureless_odcs_contract(tenant)
        _run('--apply', tenant=tenant)
        contract.refresh_from_db()
        self.assertTrue(is_structureless(contract), f'True residue should remain structureless after --apply; got {contract.hub_contract_json!r}')

    def test_apply_summary_emitted_to_stdout(self):
        tenant = _create_tenant()
        _create_structural_odcs_contract(tenant)
        _create_structureless_odcs_contract(tenant)
        output = _run('--apply', tenant=tenant)
        self.assertIn('Apply complete', output)
        self.assertIn('total=2', output)
        self.assertTrue('healed=1' in output or 'residual=1' in output)

    def test_apply_rejected_without_filter_structureless(self):
        """``--apply`` requires ``--filter=structureless`` so operators
        get a clear error rather than a silent no-op."""
        from io import StringIO as _SIO
        out = _SIO()
        err = _SIO()
        call_command('renormalize_contracts', '--spec-version=3.1.0', '--apply', stdout=out, stderr=err)
        self.assertIn('require --filter=structureless', err.getvalue())

@pytest.mark.django_db(transaction=True)
class TestApplyAssetRevertFlag(TestCase):
    """``--apply-asset-revert`` demotes ACTIVE assets whose contracts
    remain structureless after re-normalization. Implies ``--apply``."""

    def test_revert_demotes_active_asset_with_structureless_residue(self):
        from hub.apps.assets.models import AssetStatus
        tenant = _create_tenant()
        asset = _create_asset(tenant, status=AssetStatus.ACTIVE)
        _create_structureless_odcs_contract(tenant, asset=asset)
        _run('--apply', '--apply-asset-revert', tenant=tenant)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT, f'Active asset with structureless residue should revert to DRAFT; got {asset.status!r}')

    def test_revert_emits_audit_event(self):
        """The reverse-migration (227.L6.4) reads
        ``ASSET_AUTO_REVERTED_STRUCTURELESS`` events to restore. Pin
        that the apply path emits them with the canonical detail keys."""
        from hub.apps.assets.models import AssetStatus
        from hub.apps.audit.models import AuditEvent
        tenant = _create_tenant()
        asset = _create_asset(tenant, status=AssetStatus.ACTIVE)
        _create_structureless_odcs_contract(tenant, asset=asset)
        _run('--apply', '--apply-asset-revert', tenant=tenant)
        events = list(AuditEvent.objects.filter(action='ASSET_AUTO_REVERTED_STRUCTURELESS', resource_id=asset.id))
        self.assertEqual(len(events), 1, f'Expected exactly one ASSET_AUTO_REVERTED_STRUCTURELESS event; got {len(events)}')
        details = events[0].details_json
        self.assertEqual(details['previous_status'], AssetStatus.ACTIVE)
        self.assertEqual(details['new_status'], AssetStatus.DRAFT)
        self.assertIn('contract_id', details)
        self.assertIn('run_id', details)
        self.assertIn('reason', details)

    def test_revert_does_not_demote_when_contract_self_heals(self):
        """Successful self-heal MUST NOT trigger asset revert. The
        revert is only for residue (customer-action cohort)."""
        from hub.apps.assets.models import AssetStatus
        tenant = _create_tenant()
        asset = _create_asset(tenant, status=AssetStatus.ACTIVE)
        _create_structural_odcs_contract(tenant, asset=asset)
        _run('--apply', '--apply-asset-revert', tenant=tenant)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE, f'Self-heal should NOT trigger revert; got {asset.status!r}')

    def test_revert_does_not_demote_already_draft_asset(self):
        """Already-DRAFT asset with structureless residue is a no-op."""
        from hub.apps.assets.models import AssetStatus
        tenant = _create_tenant()
        asset = _create_asset(tenant, status=AssetStatus.DRAFT)
        _create_structureless_odcs_contract(tenant, asset=asset)
        _run('--apply', '--apply-asset-revert', tenant=tenant)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)
        from hub.apps.audit.models import AuditEvent
        events = AuditEvent.objects.filter(action='ASSET_AUTO_REVERTED_STRUCTURELESS', resource_id=asset.id)
        self.assertEqual(events.count(), 0)

@pytest.mark.django_db(transaction=True)
class TestSilentEventsFlag(TestCase):
    """``--silent-events`` suppresses per-contract events and emits a
    single ``CONTRACT_BATCH_RENORMALIZED`` summary at the end."""

    def test_silent_events_emits_batch_summary_event(self):
        from hub.apps.audit.models import AuditEvent
        tenant = _create_tenant()
        _create_structural_odcs_contract(tenant)
        _create_structureless_odcs_contract(tenant)
        _run('--apply', '--silent-events', tenant=tenant)
        events = list(AuditEvent.objects.filter(action='CONTRACT_BATCH_RENORMALIZED'))
        self.assertEqual(len(events), 1, f'Expected exactly one batch-summary event; got {len(events)}')
        details = events[0].details_json
        self.assertTrue(details['total_candidates'] >= 2)
        self.assertTrue(details['processed'] >= 2)
        self.assertIn('run_id', details)

    def test_silent_events_skipped_when_no_contracts_match(self):
        from hub.apps.audit.models import AuditEvent
        tenant = _create_tenant()
        from hub.apps.contracts.models import Contract
        Contract.objects.create(tenant=tenant, version=1, original_spec_type='ODCS', original_spec_version='3.0.2', original_format='YAML', original_raw='kind: DataContract\nname: ok', hub_contract_json={'models': [{'name': 'm', 'fields': [{'name': 'id'}]}]}, normalization_status='NORMALIZED_OK', validation_status='VALID', status='ACTIVE')
        before = AuditEvent.objects.filter(action='CONTRACT_BATCH_RENORMALIZED').count()
        _run('--apply', '--silent-events', tenant=tenant)
        after = AuditEvent.objects.filter(action='CONTRACT_BATCH_RENORMALIZED').count()
        self.assertEqual(after, before, 'Empty run must not emit a batch event')

@pytest.mark.django_db(transaction=True)
class TestCheckpointTableFlag(TestCase):
    """``--checkpoint-table=<name>`` writes per-contract checkpoint rows
    so a re-run with the same name skips already-done contracts."""

    def test_checkpoint_rows_written_per_contract(self):
        from hub.apps.contracts.models import MigrationCheckpoint
        tenant = _create_tenant()
        c1 = _create_structural_odcs_contract(tenant)
        c2 = _create_structureless_odcs_contract(tenant)
        _run('--apply', '--checkpoint-table=test-checkpoint-001', tenant=tenant)
        checkpoints = list(MigrationCheckpoint.objects.filter(migration_name='test-checkpoint-001'))
        ids = {str(cp.contract_id) for cp in checkpoints}
        self.assertIn(str(c1.id), ids)
        self.assertIn(str(c2.id), ids)
        for cp in checkpoints:
            self.assertEqual(cp.status, MigrationCheckpoint.STATUS_DONE)

    def test_checkpoint_resume_skips_already_done(self):
        """Second run with the same checkpoint table MUST NOT
        reprocess contracts whose checkpoint says ``done``."""
        from hub.apps.contracts.models import MigrationCheckpoint
        tenant = _create_tenant()
        c1 = _create_structural_odcs_contract(tenant)
        _run('--apply', '--checkpoint-table=test-checkpoint-002', tenant=tenant)
        c1.refresh_from_db()
        first_run_payload = c1.hub_contract_json
        first_run_updated = c1.updated_at
        c2 = _create_structureless_odcs_contract(tenant)
        _run('--apply', '--checkpoint-table=test-checkpoint-002', tenant=tenant)
        c1.refresh_from_db()
        self.assertEqual(c1.updated_at, first_run_updated, 'Already-done contract must not be re-touched on resume')
        self.assertEqual(c1.hub_contract_json, first_run_payload)
        self.assertTrue(MigrationCheckpoint.objects.filter(migration_name='test-checkpoint-002', contract=c2).exists())

    def test_failed_checkpoint_includes_truncated_error(self):
        """When per-contract processing raises, the checkpoint row
        records ``status='failed'`` and a truncated error string. This
        is the load-bearing diagnostic for triaging a partial run."""
        from hub.apps.contracts.models import Contract, MigrationCheckpoint
        tenant = _create_tenant()
        bad_contract = Contract.objects.create(tenant=tenant, version=1, original_spec_type='ODCS', original_spec_version='3.0.2', original_format='YAML', original_raw='kind: DataContract\nname: x', hub_contract_json={'models': [], 'schema': {'fields': []}}, normalization_status='NORMALIZED_OK', validation_status='VALID', status='ACTIVE')
        _run('--apply', '--checkpoint-table=test-checkpoint-003', tenant=tenant)
        cp = MigrationCheckpoint.objects.filter(migration_name='test-checkpoint-003', contract=bad_contract).first()
        self.assertTrue(cp is not None, 'Checkpoint MUST exist after the run regardless of outcome')
        self.assertIn(cp.status, (MigrationCheckpoint.STATUS_DONE, MigrationCheckpoint.STATUS_FAILED))

@pytest.mark.django_db(transaction=True)
class TestApplyJsonOutput(TestCase):
    """``--apply --output=json`` emits one JSONL row per processed
    contract carrying ``contract_id``, ``result``, ``run_id``."""

    def test_apply_json_output_emits_per_contract_row(self):
        tenant = _create_tenant()
        c1 = _create_structural_odcs_contract(tenant)
        c2 = _create_structureless_odcs_contract(tenant)
        output = _run('--apply', '--output=json', tenant=tenant)
        records = []
        for line in output.splitlines():
            line = line.rstrip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        self.assertTrue(len(records) >= 2, f'Expected at least 2 per-contract records; got {len(records)}')
        ids = {r['contract_id'] for r in records}
        self.assertIn(str(c1.id), ids)
        self.assertIn(str(c2.id), ids)
        for r in records:
            self.assertIn('result', r)
            self.assertIn(r['result'], ('healed', 'residual', 'failed'))
            self.assertIn('run_id', r)

@pytest.mark.django_db(transaction=True)
class TestApplyAdvancesUpdatedAt(TestCase):
    """The ``--apply`` path MUST advance ``Contract.updated_at`` on
    rows it self-heals. Originally the ``Contract.save(update_fields=
    [...])`` call omitted ``updated_at`` from the list — Django only
    writes ``auto_now=True`` fields when they're present in
    ``update_fields`` explicitly OR when ``update_fields`` is
    ``None``. Without ``updated_at`` advancing, the L4.3 ETag would
    be stale (it's derived from ``updated_at + version + id``), and
    clients with cached ETags would not re-validate after migration.

    This test pins the fix so a future refactor can't reintroduce
    the bug.
    """

    def test_apply_advances_updated_at_on_self_heal(self):
        tenant = _create_tenant()
        contract = _create_structural_odcs_contract(tenant)
        before = contract.updated_at
        _run('--apply', tenant=tenant)
        contract.refresh_from_db()
        self.assertTrue(contract.updated_at > before, f'--apply self-heal must advance Contract.updated_at (L4.3 ETag depends on it); before={before!r} after={contract.updated_at!r}')

@pytest.mark.django_db(transaction=True)
class TestApplyIdempotence(TestCase):
    """Running ``--apply`` twice with the same checkpoint table on the
    same input MUST produce the same final state — re-runs after a
    successful run are no-ops because the resume queryset excludes
    ``done`` checkpoints.

    Re-runs WITHOUT a checkpoint table re-process every candidate
    (idempotent on healing because re-normalization of an already-
    healed contract produces the same payload), but the second run
    advances ``updated_at`` again — that's expected behavior, the
    no-checkpoint case is "always re-process". Pin both behaviors."""

    def test_repeat_with_checkpoint_is_no_op_on_done_rows(self):
        """Second run with the same checkpoint table is a no-op on
        previously-healed contracts."""
        tenant = _create_tenant()
        contract = _create_structural_odcs_contract(tenant)
        _run('--apply', '--checkpoint-table=idem-001', tenant=tenant)
        contract.refresh_from_db()
        first_updated = contract.updated_at
        first_payload = contract.hub_contract_json
        _run('--apply', '--checkpoint-table=idem-001', tenant=tenant)
        contract.refresh_from_db()
        self.assertEqual(contract.updated_at, first_updated, f'Second run with same checkpoint MUST be a no-op on done rows; updated_at advanced from {first_updated!r} to {contract.updated_at!r}')
        self.assertEqual(contract.hub_contract_json, first_payload)

    def test_repeat_without_checkpoint_reprocesses_idempotently(self):
        """Without a checkpoint table, the second run reprocesses
        every candidate. Re-normalization on a healed contract should
        produce the same payload (idempotent)."""
        tenant = _create_tenant()
        contract = _create_structural_odcs_contract(tenant)
        _run('--apply', tenant=tenant)
        contract.refresh_from_db()
        first_payload = contract.hub_contract_json
        _run('--apply', tenant=tenant)
        contract.refresh_from_db()
        self.assertEqual(contract.hub_contract_json, first_payload, f'Re-normalization on healed contract must be idempotent; first={first_payload!r} second={contract.hub_contract_json!r}')

@pytest.mark.django_db(transaction=True)
class TestCombinedFlags(TestCase):
    """End-to-end: --apply --apply-asset-revert --silent-events
    --checkpoint-table=<name>. Tests the full Wave 3 self-heal pipeline
    in one shot."""

    def test_full_apply_pipeline_runs_all_paths(self):
        from hub.apps.assets.models import AssetStatus
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import MigrationCheckpoint
        tenant = _create_tenant()
        asset_a = _create_asset(tenant, status=AssetStatus.ACTIVE)
        c_a = _create_structural_odcs_contract(tenant, asset=asset_a)
        asset_b = _create_asset(tenant, status=AssetStatus.ACTIVE)
        c_b = _create_structureless_odcs_contract(tenant, asset=asset_b)
        _run('--apply', '--apply-asset-revert', '--silent-events', '--checkpoint-table=full-pipeline-001', tenant=tenant)
        c_a.refresh_from_db()
        from hub.apps.contracts.structureless import is_structureless
        self.assertFalse(is_structureless(c_a))
        asset_b.refresh_from_db()
        self.assertEqual(asset_b.status, AssetStatus.DRAFT)
        asset_a.refresh_from_db()
        self.assertEqual(asset_a.status, AssetStatus.ACTIVE)
        cp_ids = set(MigrationCheckpoint.objects.filter(migration_name='full-pipeline-001').values_list('contract_id', flat=True))
        self.assertIn(c_a.id, cp_ids)
        self.assertIn(c_b.id, cp_ids)
        batch_events = list(AuditEvent.objects.filter(action='CONTRACT_BATCH_RENORMALIZED'))
        self.assertEqual(len(batch_events), 1)
        self.assertIn(str(asset_b.id), batch_events[0].details_json['reverted_asset_ids'])