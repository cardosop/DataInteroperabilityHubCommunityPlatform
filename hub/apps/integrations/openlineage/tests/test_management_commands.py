"""
Phase 228 F4 (228.F4.27 self-audit GAP-2 + GAP-3) — coverage for the
two operator-driven management commands.

Pre-fix the closeout claimed ``rotate_openlineage_keys`` and
``replay_openlineage_dlq`` were "shipped + documented", but neither
had a single test. A regression in the rotation grace window or the
DLQ filter would slip through CI silently. These tests pin the
contracts both commands satisfy:

* ``rotate_openlineage_keys`` — issues a successor key, sets
  ``expires_at = now + grace_days`` on every still-active outgoing key
  (the 7-day grace window per REQ-LIN-F4-003), surfaces the new
  plaintext exactly once on stdout, and supports ``--dry-run`` /
  ``--label`` overrides.
* ``replay_openlineage_dlq`` — drains pending rows, skips already-
  delivered + already-permanently-failed rows, supports ``--dry-run``
  for a no-op listing, and threads ``--max=N`` through to the sweep.

The tests use real ``OpenLineageIngestApiKey`` / ``OpenLineageDeadLetter``
rows + real ``call_command`` invocations so the assertions cover the
full Django plumbing (argparse, URL routing, JSON output shape).
"""
from __future__ import annotations

import json
import uuid
from datetime import timedelta
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase
from django.utils import timezone


def _create_tenant(prefix: str = "OLM"):
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{prefix} Co {suffix}",
        slug=f"{prefix.lower()}-co-{suffix}",
    )


def _create_ingest_key(tenant, *, label: str = "init", expires_at=None):
    from hub.apps.integrations.openlineage.models import (
        OpenLineageIngestApiKey,
        generate_ingest_key_plaintext,
        hash_ingest_key,
    )

    plaintext = generate_ingest_key_plaintext()
    return OpenLineageIngestApiKey.objects.create(
        tenant=tenant,
        label=label,
        key_prefix=plaintext.removeprefix("msh_ol_")[:8],
        key_hash=hash_ingest_key(plaintext),
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# rotate_openlineage_keys
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestRotateOpenLineageKeysCommand(TransactionTestCase):
    """Pins REQ-LIN-F4-003 — 7-day grace window on rotation."""

    def test_rotate_issues_successor_and_graces_outgoing(self):
        from hub.apps.integrations.openlineage.models import (
            OpenLineageIngestApiKey,
        )

        tenant = _create_tenant()
        outgoing = _create_ingest_key(tenant, label="legacy")
        # Sanity: outgoing has no expiry yet.
        assert outgoing.expires_at is None

        out = StringIO()
        before_count = OpenLineageIngestApiKey.objects.filter(tenant=tenant).count()
        call_command(
            "rotate_openlineage_keys",
            f"--tenant={tenant.id}",
            stdout=out,
        )
        after_count = OpenLineageIngestApiKey.objects.filter(tenant=tenant).count()

        # Successor key inserted.
        assert after_count == before_count + 1, (
            f"expected one new key; before={before_count} after={after_count}"
        )

        # Outgoing key now has expires_at ≈ now + 7d (default grace).
        outgoing.refresh_from_db()
        assert outgoing.expires_at is not None, (
            "outgoing key must have expires_at set after rotation"
        )
        delta = outgoing.expires_at - timezone.now()
        assert timedelta(days=6, hours=23) <= delta <= timedelta(days=7, hours=1), (
            f"grace window must be ~7 days; got {delta}"
        )

        # Plaintext line printed exactly once on stdout (the operator
        # has one shot to copy it).
        text = out.getvalue()
        assert "msh_ol_" in text, "plaintext key must be visible on stdout"
        # The plaintext must NOT appear twice (paranoia: a duplicate
        # print would let a subsequent stdout flush leak it).
        # We accept the JSON envelope's prefix + the plaintext line (= 1 occurrence each).
        plaintext_lines = [l for l in text.splitlines() if l.startswith("msh_ol_")]
        assert len(plaintext_lines) == 1, (
            f"expected one plaintext line; got {len(plaintext_lines)}"
        )

    def test_rotate_dry_run_does_not_mutate(self):
        from hub.apps.integrations.openlineage.models import (
            OpenLineageIngestApiKey,
        )

        tenant = _create_tenant()
        outgoing = _create_ingest_key(tenant)
        before_count = OpenLineageIngestApiKey.objects.filter(tenant=tenant).count()
        out = StringIO()

        call_command(
            "rotate_openlineage_keys",
            f"--tenant={tenant.id}",
            "--dry-run",
            stdout=out,
        )
        after_count = OpenLineageIngestApiKey.objects.filter(tenant=tenant).count()

        # No new key, no expiry mutation.
        assert before_count == after_count, "dry-run must not insert"
        outgoing.refresh_from_db()
        assert outgoing.expires_at is None, "dry-run must not set expires_at"

        # Output is structured JSON with dry_run=True.
        envelope = json.loads(out.getvalue().strip())
        assert envelope["dry_run"] is True
        assert envelope["outgoing_keys_to_grace"] == 1
        assert "would_create_prefix" in envelope

    def test_rotate_unknown_tenant_raises_command_error(self):
        unknown = uuid.uuid4()
        with pytest.raises(CommandError):
            call_command(
                "rotate_openlineage_keys",
                f"--tenant={unknown}",
                stdout=StringIO(),
            )

    def test_rotate_label_override(self):
        from hub.apps.integrations.openlineage.models import (
            OpenLineageIngestApiKey,
        )

        tenant = _create_tenant()
        out = StringIO()
        call_command(
            "rotate_openlineage_keys",
            f"--tenant={tenant.id}",
            "--label=marquez-prod-2026Q2",
            stdout=out,
        )
        # Most-recent key for the tenant is the new one — its label
        # should be the override, not the auto-generated date.
        new_key = OpenLineageIngestApiKey.objects.filter(
            tenant=tenant
        ).order_by("-created_at").first()
        assert new_key is not None
        assert new_key.label == "marquez-prod-2026Q2"

    def test_rotate_already_grace_tail_keys_untouched(self):
        """A key whose ``expires_at`` is BEFORE the cutoff is already in
        its grace tail — the rotation must not extend it."""
        tenant = _create_tenant()
        already_short = _create_ingest_key(
            tenant,
            label="short-tail",
            expires_at=timezone.now() + timedelta(days=2),
        )
        original_expiry = already_short.expires_at

        call_command(
            "rotate_openlineage_keys",
            f"--tenant={tenant.id}",
            stdout=StringIO(),
        )
        already_short.refresh_from_db()
        assert already_short.expires_at == original_expiry, (
            "rotation must not extend a key already in its grace tail"
        )


# ---------------------------------------------------------------------------
# replay_openlineage_dlq + openlineage_dlq_replay_sweep
# ---------------------------------------------------------------------------


def _create_dlq_row(tenant, *, event_id=None, replay_attempts=0,
                    permanently_failed=False, delivered_at=None,
                    target_url="http://marquez.example/api/v1/lineage"):
    from hub.apps.integrations.openlineage.models import OpenLineageDeadLetter

    row = OpenLineageDeadLetter(
        tenant=tenant,
        event_id=str(event_id or uuid.uuid4()),
        target_url=target_url,
        failure_reason="http_503",
        failure_detail="initial",
        attempts=5,
        replay_attempts=replay_attempts,
        permanently_failed=permanently_failed,
        delivered_at=delivered_at,
    )
    row.event_payload = {
        "eventType": "COMPLETE",
        "eventTime": "2026-04-30T12:00:00Z",
        "producer": "https://meshant.com/lineage/openlineage",
        "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
        "run": {"runId": str(event_id or uuid.uuid4())},
        "job": {"namespace": "meshant.lineage", "name": "edge:complete"},
        "inputs": [{"namespace": "meshant.contracts", "name": "src"}],
        "outputs": [{"namespace": "meshant.contracts", "name": "tgt"}],
    }
    row.save()
    return row


@pytest.mark.django_db(transaction=True)
class TestReplayOpenLineageDlqCommand(TransactionTestCase):
    """Pins ``replay_openlineage_dlq`` argparse + dry-run + sweep
    delegation."""

    def test_dry_run_lists_pending_without_mutation(self):
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome

        tenant = _create_tenant()
        pending_row = _create_dlq_row(tenant)
        already_delivered = _create_dlq_row(
            tenant, delivered_at=timezone.now()
        )
        already_permafail = _create_dlq_row(
            tenant, permanently_failed=True, replay_attempts=10
        )

        out = StringIO()
        # Patch the sweep's adapter so a non-dry-run wouldn't actually
        # POST. (Dry-run shouldn't reach it; the patch is paranoia.)
        with mock.patch(
            "hub.apps.integrations.openlineage.tasks.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
            call_command(
                "replay_openlineage_dlq",
                "--dry-run",
                stdout=out,
            )

            # Adapter MUST NOT be called in dry-run.
            adapter_cls.return_value.deliver.assert_not_called()

        envelope = json.loads(out.getvalue().strip())
        assert envelope["dry_run"] is True
        assert envelope["pending_count"] == 1, (
            f"only the un-delivered, non-permafail row counts as pending; "
            f"got {envelope['pending_count']}"
        )
        ids = {r["id"] for r in envelope["pending"]}
        assert str(pending_row.id) in ids
        assert str(already_delivered.id) not in ids
        assert str(already_permafail.id) not in ids

    def test_replay_invokes_sweep_and_threads_max(self):
        tenant = _create_tenant()
        for _ in range(3):
            _create_dlq_row(tenant)

        out = StringIO()
        with mock.patch(
            "hub.apps.integrations.management.commands.replay_openlineage_dlq."
            "openlineage_dlq_replay_sweep"
        ) as sweep:
            sweep.return_value = {
                "processed": 2,
                "replayed_ok": 2,
                "replayed_dead": 0,
                "permanently_failed_now": 0,
            }
            call_command(
                "replay_openlineage_dlq",
                "--max=2",
                stdout=out,
            )
            sweep.assert_called_once_with(max_rows=2)

        envelope = json.loads(out.getvalue().strip())
        assert envelope["dry_run"] is False
        assert envelope["max_rows"] == 2
        assert envelope["processed"] == 2
        assert envelope["replayed_ok"] == 2


# ---------------------------------------------------------------------------
# openlineage_dlq_replay_sweep — directly exercise the RQ task body
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestOpenLineageDlqReplaySweep(TransactionTestCase):
    """Pins the sweep's contract: idempotent, threshold-based
    permafail, fail-soft on poisoned rows."""

    def test_sweep_replays_pending_and_deletes_row(self):
        """Phase 228 F4 (REQ-LIN-F4-004 spec scenario "DLQ retry
        succeeds") — the spec says "the row is deleted" on a
        successful replay. We assert the row is gone."""
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        tenant = _create_tenant()
        pending = _create_dlq_row(tenant)
        pending_id = pending.id

        with mock.patch(
            "hub.apps.integrations.openlineage.tasks.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
            result = openlineage_dlq_replay_sweep(max_rows=10)

        assert result["processed"] == 1
        assert result["replayed_ok"] == 1
        assert result["replayed_dead"] == 0
        assert result["permanently_failed_now"] == 0

        # Row is DELETED, not just marked.
        assert not OpenLineageDeadLetter.objects.filter(pk=pending_id).exists(), (
            "spec scenario 'DLQ retry succeeds' requires the row be deleted "
            "on successful replay; got the row still in the DLQ table"
        )

    def test_sweep_skips_already_delivered_and_permafail(self):
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        tenant = _create_tenant()
        _create_dlq_row(tenant, delivered_at=timezone.now())
        _create_dlq_row(
            tenant, permanently_failed=True, replay_attempts=10
        )

        with mock.patch(
            "hub.apps.integrations.openlineage.tasks.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
            result = openlineage_dlq_replay_sweep(max_rows=10)
            adapter_cls.return_value.deliver.assert_not_called()

        assert result["processed"] == 0, (
            "sweep must not touch already-delivered or permafail rows; "
            f"got processed={result['processed']}"
        )

    def test_sweep_marks_permafail_after_threshold(self):
        """A row that has already been replayed 9 times and fails once
        more crosses the 10-attempt threshold and is marked permafail."""
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        tenant = _create_tenant()
        row = _create_dlq_row(tenant, replay_attempts=9)

        with mock.patch(
            "hub.apps.integrations.openlineage.tasks.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DEAD_LETTERED
            result = openlineage_dlq_replay_sweep(max_rows=10)

        assert result["processed"] == 1
        assert result["replayed_ok"] == 0
        assert result["replayed_dead"] == 1
        assert result["permanently_failed_now"] == 1

        row.refresh_from_db()
        assert row.replay_attempts == 10
        assert row.permanently_failed is True

    def test_sweep_idempotent_rerun_after_delivered(self):
        """Running the sweep twice in a row when the first run delivered
        all pending rows produces processed=0 on the second run.

        Phase 228 F4 (DoD self-audit DD-B) — successful replays now
        DELETE the row (per spec). Idempotent rerun = the second
        sweep finds no pending rows because the first run deleted
        them."""
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        tenant = _create_tenant()
        _create_dlq_row(tenant)

        with mock.patch(
            "hub.apps.integrations.openlineage.tasks.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
            result_first = openlineage_dlq_replay_sweep(max_rows=10)
            result_second = openlineage_dlq_replay_sweep(max_rows=10)

        assert result_first["processed"] == 1
        assert result_second["processed"] == 0, (
            "sweep must skip already-delivered (now: deleted) rows on "
            f"re-run; got processed={result_second['processed']}"
        )

    def test_sweep_swallows_decrypt_failure(self):
        """A poisoned row (decrypt fails) must not abort the sweep —
        it logs + continues to the next row."""
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        tenant = _create_tenant()
        poisoned = _create_dlq_row(tenant)
        clean = _create_dlq_row(tenant)

        # Mutate the poisoned row's encrypted column to garbage so
        # ``event_payload`` raises on access.
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )
        OpenLineageDeadLetter.objects.filter(pk=poisoned.pk).update(
            event_payload_encrypted="garbage-not-valid-base64-or-cipher",
        )

        clean_id = clean.id
        poisoned_id = poisoned.id
        with mock.patch(
            "hub.apps.integrations.openlineage.tasks.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
            result = openlineage_dlq_replay_sweep(max_rows=10)

        # The clean row was delivered + deleted (per spec); the
        # poisoned row was skipped + still in the DLQ for ops to
        # investigate manually.
        assert result["replayed_ok"] == 1, (
            f"clean row must still be delivered when a sibling is poisoned; "
            f"got replayed_ok={result['replayed_ok']}"
        )
        assert not OpenLineageDeadLetter.objects.filter(pk=clean_id).exists()
        assert OpenLineageDeadLetter.objects.filter(pk=poisoned_id).exists()
