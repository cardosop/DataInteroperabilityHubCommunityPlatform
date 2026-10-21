"""Tests for the CI Merkle integrity verification command (277.B.077)."""

import json
import uuid
from io import StringIO

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.audit.chain import verify_chain_segment
from hub.apps.audit.management.commands.verify_audit_integrity import (
    _CI_SIGNING_KEY,
    _ci_signature_verifier,
    _create_ci_smoke_test_events,
    _sign_root,
    run_integrity_verification,
)
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class VerifyIntegrityCommandTest(TestCase):
    """Tests for verify_audit_integrity management command (277.B.077)."""

    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(
            name="AuditIntegrityTest",
            slug=f"audit-int-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        self.tenant_id = str(self.tenant.id)

    @pytest.mark.integration
    def test_create_test_data_produces_verifiable_chain(self):
        """Smoke-test events create a valid, verifiable hash chain."""
        run_integrity_verification(
            tenant_id=self.tenant_id,
            include_snapshots=False,
            create_test_data=True,
        )

        events = list(
            AuditEvent.objects.filter(tenant_id=self.tenant_id).order_by("chain_sequence")
        )
        self.assertGreaterEqual(len(events), 1)

        result = verify_chain_segment(events)
        self.assertTrue(result.verified, f"Chain should be valid, got {result.mismatches}")
        self.assertEqual(len(result.mismatches), 0)

    @pytest.mark.integration
    def test_verification_with_snapshots_passes(self):
        """Full pipeline with snapshot cross-check passes for clean data."""
        result = run_integrity_verification(
            tenant_id=self.tenant_id,
            include_snapshots=True,
            create_test_data=True,
        )

        self.assertTrue(result["verified"], f"Expected verified=True, got {result}")
        self.assertGreater(result["checked"], 0)
        self.assertGreater(result["snapshots_checked"], 0)
        self.assertEqual(len(result["snapshot_mismatches"]), 0)

    @pytest.mark.integration
    def test_verification_detects_tampered_chain_hash(self):
        """A modified chain_hash must be detected."""
        run_integrity_verification(
            tenant_id=self.tenant_id,
            include_snapshots=False,
            create_test_data=True,
        )

        # Tamper: flip one byte in the first event's chain_hash
        event = (
            AuditEvent.objects.filter(tenant_id=self.tenant_id).order_by("chain_sequence").first()
        )
        original_hash = event.chain_hash
        tampered = original_hash[:60] + ("F" if original_hash[60] != "F" else "0") * 4
        AuditEvent.objects.filter(pk=event.pk).update(chain_hash=tampered)

        result = run_integrity_verification(
            tenant_id=self.tenant_id,
            include_snapshots=False,
            create_test_data=False,
        )

        self.assertFalse(result["verified"])
        self.assertGreater(len(result["mismatches"]), 0)
        self.assertEqual(result["mismatches"][0]["reason"], "chain_hash_mismatch")

    @pytest.mark.integration
    def test_verification_detects_broken_prev_link(self):
        """A modified prev_chain_hash without a sequence gap is detected."""
        run_integrity_verification(
            tenant_id=self.tenant_id,
            include_snapshots=False,
            create_test_data=True,
        )

        # Tamper: corrupt prev_chain_hash on the second event
        events = list(
            AuditEvent.objects.filter(tenant_id=self.tenant_id).order_by("chain_sequence")
        )
        self.assertGreaterEqual(len(events), 2)
        AuditEvent.objects.filter(pk=events[1].pk).update(prev_chain_hash="0" * 64)

        result = run_integrity_verification(
            tenant_id=self.tenant_id,
            include_snapshots=False,
            create_test_data=False,
        )

        self.assertFalse(result["verified"])
        prev_link_mismatches = [
            m for m in result["mismatches"] if m["reason"] == "prev_link_mismatch"
        ]
        self.assertGreater(len(prev_link_mismatches), 0)

    @pytest.mark.integration
    def test_snapshot_cross_check_detects_root_mismatch(self):
        """Snapshot cross-check catches a full-chain rewrite that would
        otherwise pass the in-row verification."""
        run_integrity_verification(
            tenant_id=self.tenant_id,
            include_snapshots=True,
            create_test_data=True,
        )

        # Rewrite every row's chain_hash with consistent self-forged values
        # so the in-row check sees no mismatch, but the Merkle root diverges.
        events = list(
            AuditEvent.objects.filter(tenant_id=self.tenant_id).order_by("chain_sequence")
        )
        for ev in events:
            AuditEvent.objects.filter(pk=ev.pk).update(
                chain_hash="a" * 64,
                prev_chain_hash="b" * 64,
            )

        result = run_integrity_verification(
            tenant_id=self.tenant_id,
            include_snapshots=True,
            create_test_data=False,
        )

        # In-row chain check passes (all hashes are self-consistent forgeries)
        # But the snapshot root recomputation must catch the divergence
        self.assertFalse(result["verified"])
        self.assertGreater(
            len(result["snapshot_mismatches"]),
            0,
            "Snapshot cross-check must detect full-chain rewrite",
        )

    @pytest.mark.integration
    def test_json_output_flag(self):
        """The --json flag produces valid JSON."""
        buf = StringIO()
        call_command(
            "verify_audit_integrity",
            "--create-test-data",
            "--tenant-id",
            self.tenant_id,
            "--no-snapshots",
            "--json",
            stdout=buf,
        )

        output = buf.getvalue()
        parsed = json.loads(output)
        self.assertIn("verified", parsed)
        self.assertIn("checked", parsed)
        self.assertIn("tenant_id", parsed)

    @pytest.mark.integration
    def test_command_exit_code_zero_on_pass(self):
        """Command exits cleanly when verification passes."""
        buf = StringIO()
        call_command(
            "verify_audit_integrity",
            "--create-test-data",
            "--tenant-id",
            self.tenant_id,
            "--no-snapshots",
            stdout=buf,
        )
        self.assertIn("PASSED", buf.getvalue())

    @pytest.mark.integration
    def test_command_exit_code_one_on_failure(self):
        """Command raises SystemExit(1) when verification fails."""
        run_integrity_verification(
            tenant_id=self.tenant_id,
            include_snapshots=False,
            create_test_data=True,
        )
        # Tamper
        event = (
            AuditEvent.objects.filter(tenant_id=self.tenant_id).order_by("chain_sequence").first()
        )
        AuditEvent.objects.filter(pk=event.pk).update(chain_hash="0" * 64)

        with self.assertRaises(SystemExit) as ctx:
            call_command(
                "verify_audit_integrity",
                "--tenant-id",
                self.tenant_id,
                "--no-snapshots",
            )
        self.assertEqual(ctx.exception.code, 1)


class CachingCISigningVerifierTest(TestCase):
    """Unit tests for the CI signing/verification helpers (277.B.077)."""

    @pytest.mark.integration
    def test_sign_and_verify_round_trip(self):
        root_hex = "a" * 64
        sig = _sign_root(root_hex, _CI_SIGNING_KEY)
        self.assertTrue(
            _ci_signature_verifier(
                tenant_id=None,
                root_hex=root_hex,
                signature_hex=sig,
            )
        )

    @pytest.mark.integration
    def test_wrong_signature_rejected(self):
        root_hex = "a" * 64
        self.assertFalse(
            _ci_signature_verifier(
                tenant_id=None,
                root_hex=root_hex,
                signature_hex="b" * 64,
            )
        )

    @pytest.mark.integration
    def test_wrong_root_rejected(self):
        root_hex = "a" * 64
        sig = _sign_root(root_hex, _CI_SIGNING_KEY)
        self.assertFalse(
            _ci_signature_verifier(
                tenant_id=None,
                root_hex="b" * 64,
                signature_hex=sig,
            )
        )


class SmokeTestEventCreationTest(TestCase):
    """Tests for synthetic CI smoke-test event creation (277.B.077)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="SmokeTest",
            slug=f"smoke-test-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )

    @pytest.mark.integration
    def test_events_are_properly_chained(self):
        tenant_id = str(self.tenant.id)
        _create_ci_smoke_test_events(tenant_id, 5, timezone.now())

        events = list(AuditEvent.objects.filter(tenant_id=tenant_id).order_by("chain_sequence"))
        self.assertEqual(len(events), 5)
        for ev in events:
            self.assertIsNotNone(ev.chain_hash)
            self.assertIsNotNone(ev.chain_sequence)

    @pytest.mark.integration
    def test_chain_sequence_is_monotonic(self):
        tenant_id = str(self.tenant.id)
        _create_ci_smoke_test_events(tenant_id, 5, timezone.now())

        events = list(AuditEvent.objects.filter(tenant_id=tenant_id).order_by("chain_sequence"))
        seqs = [ev.chain_sequence for ev in events]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(len(set(seqs)), len(seqs))
