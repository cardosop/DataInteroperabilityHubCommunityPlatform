"""
Phase 234.1 — Tamper-evidence: hash chain + Merkle snapshot + verify endpoint.

Engineering contract this suite pins (D234.1 / preprod01 tasks.md):

1.  ``canonical_form`` is deterministic and excludes self-referential /
    positional / archival fields.
2.  ``compute_chain_hash`` is a pure function of canonical bytes + prev_hash
    + timestamp; identical inputs → identical hash.
3.  ``AuditEvent.save()`` populates ``chain_sequence`` monotonically per
    tenant, links ``prev_chain_hash`` to the previous row, and stores
    ``chain_hash`` matching the canonical recomputation.
4.  The verify endpoint detects content tampering (raw SQL UPDATE),
    insertion attempts (broken prev-link), and reports GDPR-erasure gaps
    informationally rather than as mismatches.
5.  The Merkle snapshot job builds a deterministic root, signs it with the
    tenant's current key, persists an ``AuditMerkleSnapshot`` row, and
    uploads the root + signature to S3 (Object Lock attempted; falls back
    to ``default_storage`` when S3 isn't available).
6.  The backfill management command produces the SAME chain a fresh-write
    workflow would, including dry-run + ``--resume-from``.

The suite uses real DB rows and real signing material; no mocks of the
chain logic. ``boto3`` is patched at the import boundary only when the
test explicitly exercises the S3-upload branch — otherwise the snapshot
job writes through Django's ``default_storage`` (FileSystemStorage in CI).
"""
from __future__ import annotations
import pytest

import hashlib
import json
import uuid
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit import chain as chain_mod
from hub.apps.audit.chain import (
    ChainMismatch,
    ChainVerification,
    canonical_form,
    compute_chain_hash,
    merkle_root,
    verify_chain_segment,
)
from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _hex_key(seed: int) -> str:
    return f"{seed:x}".rjust(64, "0")


# ---------------------------------------------------------------------------
# Tier 1 — pure-function tests (no DB)
# ---------------------------------------------------------------------------


class CanonicalFormTests(TestCase):
    """234.1.4 — deterministic JSON serialization contract."""

    def _make_dict_event(self, **overrides):
        base = {
            "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
            "tenant_id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
            "actor_user_id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
            "resource_type": "ASSET",
            "resource_id": uuid.UUID("44444444-4444-4444-4444-444444444444"),
            "action": "CREATED",
            "result": "SUCCESS",
            "details_json": {"b": 2, "a": 1},
            "full_details_json": None,
        }
        base.update(overrides)
        return base

    @pytest.mark.integration
    def test_canonical_form_is_bytes(self):
        out = canonical_form(self._make_dict_event())
        self.assertIsInstance(out, bytes)

    @pytest.mark.integration
    def test_canonical_form_is_deterministic(self):
        ev = self._make_dict_event()
        self.assertEqual(canonical_form(ev), canonical_form(ev))

    @pytest.mark.integration
    def test_canonical_form_dict_key_order_independent(self):
        ev1 = self._make_dict_event(details_json={"a": 1, "b": 2})
        ev2 = self._make_dict_event(details_json={"b": 2, "a": 1})
        self.assertEqual(canonical_form(ev1), canonical_form(ev2))

    @pytest.mark.integration
    def test_canonical_form_excludes_chain_hash_field(self):
        ev = self._make_dict_event()
        ev["chain_hash"] = "deadbeef" * 8
        base = canonical_form(self._make_dict_event())
        with_hash = canonical_form(ev)
        # Adding chain_hash to the dict must NOT change the canonical bytes;
        # otherwise the hash would be self-referential.
        self.assertEqual(base, with_hash)

    @pytest.mark.integration
    def test_canonical_form_excludes_chain_sequence_field(self):
        ev = self._make_dict_event()
        ev["chain_sequence"] = 9999
        base = canonical_form(self._make_dict_event())
        self.assertEqual(base, canonical_form(ev))

    @pytest.mark.integration
    def test_canonical_form_excludes_timestamp_field(self):
        ev = self._make_dict_event()
        ev["timestamp"] = "2026-01-01T00:00:00Z"
        base = canonical_form(self._make_dict_event())
        # Timestamp is supplied separately to compute_chain_hash; including
        # it inside the canonical would create two places where time is
        # spliced into the hash input and complicate the verifier.
        self.assertEqual(base, canonical_form(ev))

    @pytest.mark.integration
    def test_canonical_form_excludes_archival_fields(self):
        ev = self._make_dict_event()
        ev["is_archived"] = True
        ev["archived_at"] = "2026-01-01T00:00:00Z"
        # Per 232 retention spec: flipping is_archived MUST NOT invalidate
        # the chain. So canonical must not depend on archival metadata.
        self.assertEqual(
            canonical_form(self._make_dict_event()), canonical_form(ev)
        )

    @pytest.mark.integration
    def test_canonical_form_uuid_normalized_to_string(self):
        out = canonical_form(self._make_dict_event())
        parsed = json.loads(out.decode("utf-8"))
        self.assertEqual(parsed["id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(parsed["tenant_id"], "22222222-2222-2222-2222-222222222222")


class ComputeChainHashTests(TestCase):
    """234.1.3 — hash composition is canonical || prev || timestamp."""

    @pytest.mark.integration
    def test_returns_64_hex_chars(self):
        h = compute_chain_hash(b"x", None, "2026-01-01T00:00:00+00:00")
        self.assertEqual(len(h), 64)
        int(h, 16)  # raises if not valid hex

    @pytest.mark.integration
    def test_deterministic(self):
        a = compute_chain_hash(b"x", "abc", "2026-01-01T00:00:00+00:00")
        b = compute_chain_hash(b"x", "abc", "2026-01-01T00:00:00+00:00")
        self.assertEqual(a, b)

    @pytest.mark.integration
    def test_genesis_uses_empty_prev(self):
        # None prev -> hashed as empty string (genesis convention).
        none_h = compute_chain_hash(b"x", None, "t")
        empty_h = compute_chain_hash(b"x", "", "t")
        self.assertEqual(none_h, empty_h)

    @pytest.mark.integration
    def test_prev_changes_hash(self):
        a = compute_chain_hash(b"x", "abc", "t")
        b = compute_chain_hash(b"x", "abd", "t")
        self.assertNotEqual(a, b)

    @pytest.mark.integration
    def test_timestamp_changes_hash(self):
        a = compute_chain_hash(b"x", None, "t1")
        b = compute_chain_hash(b"x", None, "t2")
        self.assertNotEqual(a, b)

    @pytest.mark.integration
    def test_matches_manual_sha256(self):
        expected = hashlib.sha256(b"x" + b"prev" + b"t").hexdigest()
        self.assertEqual(compute_chain_hash(b"x", "prev", "t"), expected)


class MerkleRootTests(TestCase):
    """234.1.5 — Merkle tree builds deterministically."""

    @pytest.mark.integration
    def test_empty_returns_sha256_empty(self):
        self.assertEqual(merkle_root([]), hashlib.sha256(b"").hexdigest())

    @pytest.mark.integration
    def test_single_leaf_returns_leaf(self):
        leaf = hashlib.sha256(b"a").hexdigest()
        self.assertEqual(merkle_root([leaf]), leaf)

    @pytest.mark.integration
    def test_two_leaves_concat_hashed(self):
        a = hashlib.sha256(b"a").hexdigest()
        b = hashlib.sha256(b"b").hexdigest()
        expected = hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest()
        self.assertEqual(merkle_root([a, b]), expected)

    @pytest.mark.integration
    def test_odd_layer_duplicates_last(self):
        a = hashlib.sha256(b"a").hexdigest()
        b = hashlib.sha256(b"b").hexdigest()
        c = hashlib.sha256(b"c").hexdigest()
        # Manual: layer1 = [H(a||b), H(c||c)], root = H(layer1[0]||layer1[1])
        layer1_left = hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest()
        layer1_right = hashlib.sha256(bytes.fromhex(c) + bytes.fromhex(c)).hexdigest()
        expected = hashlib.sha256(
            bytes.fromhex(layer1_left) + bytes.fromhex(layer1_right)
        ).hexdigest()
        self.assertEqual(merkle_root([a, b, c]), expected)


# ---------------------------------------------------------------------------
# Tier 2 — DB integration: save() wiring
# ---------------------------------------------------------------------------


def _make_tenant_user():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"234.1 T {uid}",
        slug=f"t-{uid}",
        status="ACTIVE",
        kyc_status="VERIFIED",
    )
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="M3sh@nt!Hub#2026",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return tenant, user


class AuditEventChainOnSaveTests(TestCase):
    """234.1.1 / 234.1.3 — save() populates chain fields correctly."""

    def setUp(self):
        self.tenant, self.user = _make_tenant_user()

    @pytest.mark.integration
    def test_first_event_genesis(self):
        ev = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            details={"k": "v"},
        )
        ev.refresh_from_db()
        self.assertEqual(ev.chain_sequence, 1)
        self.assertIsNone(ev.prev_chain_hash)
        # chain_hash matches a recompute
        recomputed = compute_chain_hash(
            canonical_form(ev), None, ev.timestamp.isoformat()
        )
        self.assertEqual(ev.chain_hash, recomputed)

    @pytest.mark.integration
    def test_second_event_links_to_first(self):
        e1 = create_audit_event(
            resource_type="ASSET", action="CREATED",
            actor_user=self.user, tenant=self.tenant, details={"n": 1},
        )
        e2 = create_audit_event(
            resource_type="ASSET", action="UPDATED",
            actor_user=self.user, tenant=self.tenant, details={"n": 2},
        )
        e1.refresh_from_db(); e2.refresh_from_db()
        self.assertEqual(e2.chain_sequence, e1.chain_sequence + 1)
        self.assertEqual(e2.prev_chain_hash, e1.chain_hash)

    @pytest.mark.integration
    def test_chain_sequence_is_per_tenant(self):
        other_tenant, other_user = _make_tenant_user()
        e1_t1 = create_audit_event(
            resource_type="ASSET", action="CREATED",
            actor_user=self.user, tenant=self.tenant, details={"x": 1},
        )
        e1_t2 = create_audit_event(
            resource_type="ASSET", action="CREATED",
            actor_user=other_user, tenant=other_tenant, details={"y": 1},
        )
        e1_t1.refresh_from_db(); e1_t2.refresh_from_db()
        # Both tenants start at 1 — sequences are scoped, not global.
        self.assertEqual(e1_t1.chain_sequence, 1)
        self.assertEqual(e1_t2.chain_sequence, 1)
        # And the hashes differ (different canonical content).
        self.assertNotEqual(e1_t1.chain_hash, e1_t2.chain_hash)

    @pytest.mark.integration
    def test_null_tenant_event_still_chains(self):
        # Platform-level events have tenant=None; they form their own chain.
        # The shared test DB may already contain platform events from earlier
        # tests/runs, so we assert RELATIVE-to-current-head behaviour: the
        # contract under test is "null-tenant writes participate in the
        # chain", not "this run gets sequence 1".
        head_before = (
            AuditEvent.all_objects.filter(
                tenant__isnull=True, chain_sequence__isnull=False
            )
            .order_by("-chain_sequence")
            .values_list("chain_sequence", "chain_hash")
            .first()
        )
        head_seq, head_hash = (head_before or (0, None))

        e = create_audit_event(
            resource_type="PLATFORM",
            action="STARTUP",
            actor_user=None,
            tenant=None,
            details={"v": 1},
        )
        e.refresh_from_db()
        self.assertEqual(e.chain_sequence, head_seq + 1)
        self.assertIsNotNone(e.chain_hash)
        self.assertEqual(e.prev_chain_hash, head_hash)
        # Second null-tenant event continues the platform chain off ``e``.
        e2 = create_audit_event(
            resource_type="PLATFORM", action="SHUTDOWN",
            actor_user=None, tenant=None, details={"v": 2},
        )
        e2.refresh_from_db()
        self.assertEqual(e2.chain_sequence, e.chain_sequence + 1)
        self.assertEqual(e2.prev_chain_hash, e.chain_hash)


# ---------------------------------------------------------------------------
# Tier 3 — verifier: catches tampering + tolerates erasure gaps
# ---------------------------------------------------------------------------


class VerifyChainSegmentTests(TestCase):
    """234.1.8 / 234.1.12 — verify_chain_segment correctness."""

    def setUp(self):
        self.tenant, self.user = _make_tenant_user()
        self.events = []
        for i in range(5):
            self.events.append(
                create_audit_event(
                    resource_type="ASSET", action=f"A{i}",
                    actor_user=self.user, tenant=self.tenant,
                    details={"n": i},
                )
            )
        for e in self.events:
            e.refresh_from_db()

    @pytest.mark.integration
    def test_clean_segment_verifies(self):
        result = verify_chain_segment(self.events)
        self.assertTrue(result.verified, msg=str(result.mismatches))
        self.assertEqual(result.checked, 5)
        self.assertEqual(result.mismatches, [])
        self.assertEqual(result.gaps, [])

    @pytest.mark.integration
    def test_content_tampering_via_raw_sql_detected(self):
        # 234.1.12 — forge details_json via raw SQL, bypassing the model's
        # immutability guard. The verifier must spot it.
        target = self.events[2]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE audit_events SET details_json = %s WHERE id = %s",
                [json.dumps({"forged": True}), str(target.id)],
            )
        # Re-read with all_objects (includes archived; chain rows are not).
        fresh = list(
            AuditEvent.all_objects.filter(tenant=self.tenant)
            .order_by("chain_sequence")
        )
        result = verify_chain_segment(fresh)
        self.assertFalse(result.verified)
        # The tampered row's chain_hash should no longer match its content.
        self.assertTrue(
            any(m.reason == "chain_hash_mismatch" and m.event_id == str(target.id)
                for m in result.mismatches),
            f"expected chain_hash_mismatch on {target.id}, got {result.mismatches!r}",
        )

    @pytest.mark.integration
    def test_prev_link_tampering_detected(self):
        # Forge the chain by rewriting a row's prev_chain_hash; the link
        # check between rows must fail.
        target = self.events[3]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE audit_events SET prev_chain_hash = %s WHERE id = %s",
                ["0" * 64, str(target.id)],
            )
        fresh = list(
            AuditEvent.all_objects.filter(tenant=self.tenant)
            .order_by("chain_sequence")
        )
        result = verify_chain_segment(fresh)
        self.assertFalse(result.verified)
        # Note: the chain_hash check ALSO fails (because canonical uses
        # the same row but prev was changed in storage, recompute uses
        # the new prev and won't match stored). Either is acceptable
        # tamper-evidence; the test pins at least one mismatch was seen.
        self.assertTrue(
            any(m.event_id == str(target.id) for m in result.mismatches)
        )

    @pytest.mark.integration
    def test_gdpr_erasure_gap_reported_but_not_failed(self):
        # 234 + 232.2 cross-spec: hard-deleting a row mid-chain is
        # legitimate. The verifier MUST surface the gap informationally
        # but MUST NOT flip ``verified`` to False — the spec explicitly
        # says "the tamper-evidence spec MUST tolerate missing rows in
        # the chain." A clean GDPR-erasure leaves the surviving rows
        # untouched, so the only signal that something was deleted is
        # the sequence gap (and the broken prev_chain_hash link across
        # that gap — which we treat as expected, NOT as a tamper
        # indicator). The Merkle-snapshot cross-check is the secondary
        # defence for malicious-deletion-masquerading-as-erasure.
        gone = self.events[2]
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM audit_events WHERE id = %s", [str(gone.id)]
            )
        fresh = list(
            AuditEvent.all_objects.filter(tenant=self.tenant)
            .order_by("chain_sequence")
        )
        result = verify_chain_segment(fresh)
        # GAP reported AND verified=True (legitimate erasure does NOT
        # fail the per-row check).
        self.assertEqual(result.gaps, [(2, 4)])
        self.assertTrue(
            result.verified,
            f"GDPR-erasure gap MUST NOT fail verify; got mismatches: {result.mismatches!r}",
        )
        # No prev_link_mismatch should fire across the gap — the
        # cross-spec contract is "gaps are informational, not tamper".
        self.assertEqual(
            [m.reason for m in result.mismatches], [],
            "no per-row mismatches expected for a legitimate erasure gap",
        )

    @pytest.mark.integration
    def test_prev_link_tampering_without_gap_still_flagged(self):
        # The complement to the erasure test: if the prev_chain_hash is
        # broken WITHOUT a sequence gap, that's a forged insertion /
        # row rewrite and the verifier MUST flip ``verified=False``.
        target = self.events[2]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE audit_events SET prev_chain_hash = %s WHERE id = %s",
                ["0" * 64, str(target.id)],
            )
        fresh = list(
            AuditEvent.all_objects.filter(tenant=self.tenant)
            .order_by("chain_sequence")
        )
        result = verify_chain_segment(fresh)
        self.assertFalse(result.verified)
        # Expect at least one ``prev_link_mismatch`` OR
        # ``chain_hash_mismatch`` on the target row.
        offending = [
            m for m in result.mismatches if m.event_id == str(target.id)
        ]
        self.assertTrue(offending, f"target row not flagged: {result.mismatches!r}")


# ---------------------------------------------------------------------------
# Tier 4 — verify endpoint
# ---------------------------------------------------------------------------


class VerifyEndpointTests(TestCase):
    """234.1.8 — REST contract for the integrity-verify endpoint."""

    def setUp(self):
        self.tenant, self.user = _make_tenant_user()
        # The endpoint requires TENANT_ADMIN / AUDITOR / PLATFORM_ADMIN.
        admin_role = Role.objects.create(
            tenant=self.tenant, name="TENANT_ADMIN", description=""
        )
        UserRole.objects.create(
            user=self.user, tenant=self.tenant, role=admin_role
        )
        for i in range(3):
            create_audit_event(
                resource_type="ASSET", action=f"A{i}",
                actor_user=self.user, tenant=self.tenant, details={"n": i},
            )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @pytest.mark.integration
    def test_verify_clean_chain_returns_verified_true(self):
        resp = self.client.get(
            "/api/v1/audit/integrity/verify/",
            {"tenant_id": str(self.tenant.id)},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        body = resp.json()
        self.assertTrue(body["verified"], body)
        self.assertEqual(body["checked"], 3)
        self.assertEqual(body["mismatches"], [])

    @pytest.mark.integration
    def test_verify_after_forge_returns_verified_false(self):
        ev = AuditEvent.all_objects.filter(tenant=self.tenant).order_by(
            "chain_sequence"
        )[1]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE audit_events SET action = %s WHERE id = %s",
                ["FORGED", str(ev.id)],
            )
        resp = self.client.get(
            "/api/v1/audit/integrity/verify/",
            {"tenant_id": str(self.tenant.id)},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertFalse(body["verified"])
        self.assertGreaterEqual(len(body["mismatches"]), 1)


# ---------------------------------------------------------------------------
# Tier 5 — Merkle snapshot job + S3 upload
# ---------------------------------------------------------------------------


class MerkleSnapshotJobTests(TestCase):
    """234.1.5 / 234.1.6 / 234.1.7 — snapshot pipeline.

    The snapshot job is invoked as a function (``snapshot_tenant_window``)
    so the test can assert it directly without going through Celery / the
    job queue. The function MUST be idempotent within a window: re-running
    the same window does not create duplicate snapshot rows (uniqueness on
    ``tenant + period_start + period_end``).
    """

    def setUp(self):
        self.tenant, self.user = _make_tenant_user()
        self.events = [
            create_audit_event(
                resource_type="ASSET", action=f"A{i}",
                actor_user=self.user, tenant=self.tenant, details={"n": i},
            )
            for i in range(4)
        ]
        self.keys_override = override_settings(
            AUDIT_CHAIN_SIGNING_KEYS_JSON={
                str(self.tenant.id): [_hex_key(0xAA)]
            },
            AUDIT_RETENTION_YEARS=3,
            AUDIT_MERKLE_S3_BUCKET="",  # no-S3 path → default_storage
        )
        self.keys_override.enable()
        self.addCleanup(self.keys_override.disable)

    @pytest.mark.integration
    def test_snapshot_creates_persisted_row_with_root_and_signature(self):
        from hub.apps.audit.merkle import snapshot_tenant_window
        from hub.apps.audit.models import AuditMerkleSnapshot

        start = timezone.now() - timedelta(hours=1)
        end = timezone.now() + timedelta(hours=1)
        snapshot = snapshot_tenant_window(
            tenant=self.tenant, period_start=start, period_end=end
        )
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.event_count, 4)
        self.assertEqual(len(snapshot.root_hex), 64)
        self.assertGreater(len(snapshot.signature_hex), 0)
        # Round-trip via DB
        row = AuditMerkleSnapshot.objects.get(pk=snapshot.pk)
        self.assertEqual(row.root_hex, snapshot.root_hex)

    @pytest.mark.integration
    def test_snapshot_root_matches_manual_compute(self):
        from hub.apps.audit.merkle import snapshot_tenant_window

        start = timezone.now() - timedelta(hours=1)
        end = timezone.now() + timedelta(hours=1)
        snapshot = snapshot_tenant_window(
            tenant=self.tenant, period_start=start, period_end=end
        )
        # Manual: leaves = each event.chain_hash in chain_sequence order.
        leaves = [
            e.chain_hash for e in
            AuditEvent.all_objects.filter(tenant=self.tenant)
            .order_by("chain_sequence")
        ]
        self.assertEqual(snapshot.root_hex, merkle_root(leaves))

    @pytest.mark.integration
    def test_snapshot_idempotent_for_same_window(self):
        from hub.apps.audit.merkle import snapshot_tenant_window
        from hub.apps.audit.models import AuditMerkleSnapshot

        start = timezone.now() - timedelta(hours=1)
        end = timezone.now() + timedelta(hours=1)
        s1 = snapshot_tenant_window(
            tenant=self.tenant, period_start=start, period_end=end
        )
        s2 = snapshot_tenant_window(
            tenant=self.tenant, period_start=start, period_end=end
        )
        self.assertEqual(s1.pk, s2.pk)
        self.assertEqual(
            AuditMerkleSnapshot.objects.filter(tenant=self.tenant).count(),
            1,
        )

    @pytest.mark.integration
    def test_signature_verifies_with_current_key(self):
        from hub.apps.audit.merkle import (
            snapshot_tenant_window, verify_root_signature,
        )

        start = timezone.now() - timedelta(hours=1)
        end = timezone.now() + timedelta(hours=1)
        snap = snapshot_tenant_window(
            tenant=self.tenant, period_start=start, period_end=end
        )
        self.assertTrue(
            verify_root_signature(
                tenant_id=str(self.tenant.id),
                root_hex=snap.root_hex,
                signature_hex=snap.signature_hex,
            )
        )

    @pytest.mark.integration
    def test_signature_rejects_forged_root(self):
        from hub.apps.audit.merkle import verify_root_signature
        # No signature should validate against a root we never signed.
        self.assertFalse(
            verify_root_signature(
                tenant_id=str(self.tenant.id),
                root_hex="0" * 64,
                signature_hex="0" * 64,
            )
        )

    @pytest.mark.integration
    def test_db_row_persists_when_s3_upload_fails(self):
        # 234.1 audit-fix Gap E — DB-first ordering. We force the S3
        # upload to fail; the snapshot row MUST still persist with
        # empty s3_* fields so the cryptographic proof
        # (``root_hex`` + ``signature_hex``) is durable. The failure
        # mode the previous order had was the opposite: an orphan S3
        # object with no DB pointer.
        from hub.apps.audit.merkle import snapshot_tenant_window
        from hub.apps.audit.models import AuditMerkleSnapshot

        start = timezone.now() - timedelta(hours=1)
        end = timezone.now() + timedelta(hours=1)
        with patch(
            "hub.apps.audit.merkle._upload_proof",
            side_effect=RuntimeError("simulated S3 outage"),
        ):
            snap = snapshot_tenant_window(
                tenant=self.tenant, period_start=start, period_end=end,
            )
        # Row persisted with the cryptographic fields populated; S3
        # fields empty so a follow-up sweep can detect + re-shoot the PUT.
        row = AuditMerkleSnapshot.objects.get(pk=snap.pk)
        self.assertEqual(row.root_hex, snap.root_hex)
        self.assertEqual(row.signature_hex, snap.signature_hex)
        self.assertEqual(row.s3_bucket, "")
        self.assertEqual(row.s3_key, "")


# ---------------------------------------------------------------------------
# Tier 5b — snapshot cross-check (audit-fix Gap C)
# ---------------------------------------------------------------------------


class SnapshotCrossCheckTests(TestCase):
    """234.1 audit-fix — snapshot cross-check catches full-chain rewrite.

    The per-row verifier in tier 3 catches single-row forgery + neighbour
    link tampering when there's no gap. It CANNOT catch a full-chain
    rewrite where every row's ``chain_hash`` AND ``prev_chain_hash`` are
    forged to be internally consistent. The signed Merkle snapshot is
    the anchor that catches this case.
    """

    def setUp(self):
        self.tenant, self.user = _make_tenant_user()
        admin_role = Role.objects.create(
            tenant=self.tenant, name="TENANT_ADMIN", description=""
        )
        UserRole.objects.create(
            user=self.user, tenant=self.tenant, role=admin_role
        )
        self.keys_override = override_settings(
            AUDIT_CHAIN_SIGNING_KEYS_JSON={
                str(self.tenant.id): [_hex_key(0xCC)]
            },
            AUDIT_RETENTION_YEARS=3,
            AUDIT_MERKLE_S3_BUCKET="",
        )
        self.keys_override.enable()
        self.addCleanup(self.keys_override.disable)
        for i in range(4):
            create_audit_event(
                resource_type="ASSET", action=f"A{i}",
                actor_user=self.user, tenant=self.tenant, details={"n": i},
            )
        # Produce a snapshot covering the just-written events.
        from hub.apps.audit.merkle import snapshot_tenant_window
        self.period_start = timezone.now() - timedelta(hours=1)
        self.period_end = timezone.now() + timedelta(hours=1)
        self.snapshot = snapshot_tenant_window(
            tenant=self.tenant,
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @pytest.mark.integration
    def test_clean_chain_snapshot_check_verifies(self):
        resp = self.client.get(
            "/api/v1/audit/integrity/verify/",
            {
                "tenant_id": str(self.tenant.id),
                "include_snapshots": "true",
            },
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body["verified"], body)
        self.assertEqual(body["snapshots_checked"], 1)
        self.assertEqual(body["snapshot_mismatches"], [])

    @pytest.mark.integration
    def test_full_chain_rewrite_caught_by_snapshot_check(self):
        # Forge an internally-consistent chain rewrite. We rebuild every
        # row's chain_hash + prev_chain_hash using NEW canonical content
        # (forged action), then walk the rows in order. The per-row
        # verifier sees nothing wrong (links are self-consistent), but
        # the recomputed Merkle root no longer matches the signed root.
        rows = list(
            AuditEvent.all_objects.filter(tenant=self.tenant)
            .order_by("chain_sequence")
        )
        prev_hash = None
        for row in rows:
            # Forge content + recompute hash. We bypass save() via raw SQL.
            forged_action = f"FORGED_{row.action}"
            forged_canonical = canonical_form({
                "id": row.id,
                "tenant_id": row.tenant_id,
                "actor_user_id": row.actor_user_id,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "action": forged_action,
                "result": row.result,
                "details_json": row.details_json,
                "full_details_json": row.full_details_json,
            })
            new_hash = compute_chain_hash(
                forged_canonical, prev_hash, row.timestamp.isoformat()
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE audit_events SET action=%s, prev_chain_hash=%s, "
                    "chain_hash=%s WHERE id=%s",
                    [forged_action, prev_hash, new_hash, str(row.id)],
                )
            prev_hash = new_hash

        # The per-row verifier sees a consistent chain (no mismatches)
        # — but the snapshot cross-check catches it.
        resp = self.client.get(
            "/api/v1/audit/integrity/verify/",
            {
                "tenant_id": str(self.tenant.id),
                "include_snapshots": "true",
            },
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertFalse(body["verified"], body)
        self.assertEqual(body["snapshots_checked"], 1)
        self.assertEqual(len(body["snapshot_mismatches"]), 1)
        mismatch = body["snapshot_mismatches"][0]
        self.assertEqual(mismatch["stored_root_hex"], self.snapshot.root_hex)
        self.assertNotEqual(mismatch["recomputed_root_hex"], self.snapshot.root_hex)
        self.assertTrue(mismatch["signature_valid"], "signature itself was not forged")

    @pytest.mark.integration
    def test_snapshot_with_forged_signature_caught(self):
        # The other tamper surface: the snapshot row itself is mutated
        # (signature swapped). Catches the case where an attacker who
        # gets DB write access tries to re-sign with a key they control.
        from hub.apps.audit.models import AuditMerkleSnapshot

        AuditMerkleSnapshot.objects.filter(pk=self.snapshot.pk).update(
            signature_hex="0" * 64,
        )
        resp = self.client.get(
            "/api/v1/audit/integrity/verify/",
            {
                "tenant_id": str(self.tenant.id),
                "include_snapshots": "true",
            },
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertFalse(body["verified"], body)
        self.assertEqual(len(body["snapshot_mismatches"]), 1)
        self.assertFalse(body["snapshot_mismatches"][0]["signature_valid"])


# ---------------------------------------------------------------------------
# Tier 7 — job dispatcher + management command wire-up (audit-fix Gap A)
# ---------------------------------------------------------------------------


class AuditMerkleJobDispatcherTests(TestCase):
    """234.1.5 audit-fix — JobType.AUDIT_MERKLE_SNAPSHOT IS routed.

    The previous implementation declared the enum value but the generic
    dispatcher at ``hub/apps/jobs/tasks_base.py:execute_job_by_type`` had
    no branch for it, so any Job row of that type would hit ``raise
    ValueError("Unknown job type")``. We add a real handler in
    ``hub/apps/audit/tasks.py`` and exercise it end-to-end here.
    """

    def setUp(self):
        self.tenant, self.user = _make_tenant_user()
        self.keys_override = override_settings(
            AUDIT_CHAIN_SIGNING_KEYS_JSON={
                str(self.tenant.id): [_hex_key(0xDE)]
            },
            AUDIT_MERKLE_S3_BUCKET="",
        )
        self.keys_override.enable()
        self.addCleanup(self.keys_override.disable)
        for i in range(3):
            create_audit_event(
                resource_type="ASSET", action=f"A{i}",
                actor_user=self.user, tenant=self.tenant, details={"n": i},
            )

    @pytest.mark.integration
    def test_dispatcher_routes_audit_merkle_snapshot_to_handler(self):
        from hub.apps.audit.models import AuditMerkleSnapshot
        from hub.apps.jobs.models import (
            Job, JobPriority, JobStatus, JobType,
        )
        from hub.apps.jobs.tasks_base import _execute_job_logic

        # Trim any pre-existing snapshot rows from the shared test DB so
        # the assertion is about THIS dispatch's output.
        baseline = AuditMerkleSnapshot.objects.count()

        job = Job.objects.create(
            tenant=None,
            type=JobType.AUDIT_MERKLE_SNAPSHOT,
            status=JobStatus.RUNNING,
            priority=JobPriority.NORMAL,
            resource_type="SYSTEM",
            resource_id=uuid.uuid4(),
            started_at=timezone.now(),
            details_json={"window_hours": 1},
        )
        # The dispatcher should run our handler and return a structured
        # result instead of raising ``Unknown job type``.
        result = _execute_job_logic(job, JobType.AUDIT_MERKLE_SNAPSHOT)
        self.assertTrue(result["success"])
        self.assertIn("snapshots_produced", result["summary"])
        # At least one snapshot row was produced for at least one tenant.
        self.assertGreaterEqual(AuditMerkleSnapshot.objects.count(), baseline + 1)

    @pytest.mark.integration
    def test_management_command_creates_job_row_and_completes(self):
        from hub.apps.audit.models import AuditMerkleSnapshot
        from hub.apps.jobs.models import Job, JobStatus, JobType

        before_jobs = Job.objects.filter(type=JobType.AUDIT_MERKLE_SNAPSHOT).count()
        before_snaps = AuditMerkleSnapshot.objects.count()
        call_command("audit_merkle_snapshot_sweep", "--tenant-id", str(self.tenant.id))
        # One new Job row, status=COMPLETED.
        job = (
            Job.objects.filter(type=JobType.AUDIT_MERKLE_SNAPSHOT)
            .order_by("-created_at")
            .first()
        )
        assert job is not None
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertGreater(
            Job.objects.filter(type=JobType.AUDIT_MERKLE_SNAPSHOT).count(),
            before_jobs,
        )
        self.assertGreaterEqual(
            AuditMerkleSnapshot.objects.count(), before_snaps + 1
        )


# ---------------------------------------------------------------------------
# Tier 6 — backfill management command (234.1.9)
# ---------------------------------------------------------------------------


class BackfillAuditChainCommandTests(TestCase):
    """234.1.9 — backfill_audit_chain command produces a valid chain."""

    def setUp(self):
        self.tenant, self.user = _make_tenant_user()
        # Create rows WITHOUT chain fields by going through raw SQL — this
        # simulates pre-234 rows that need to be back-filled.
        self.event_ids = []
        for i in range(5):
            ev_id = uuid.uuid4()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO audit_events
                        (id, tenant_id, resource_type, action, result,
                         details_json, full_details_json, timestamp,
                         is_archived, chain_sequence, prev_chain_hash, chain_hash)
                    VALUES (%s, %s, %s, %s, 'SUCCESS', %s, NULL,
                            NOW() + (interval '1 second' * %s), false, NULL, NULL, NULL)
                    """,
                    [
                        str(ev_id),
                        str(self.tenant.id),
                        "ASSET",
                        f"A{i}",
                        json.dumps({"n": i}),
                        i,
                    ],
                )
            self.event_ids.append(ev_id)

    @pytest.mark.integration
    def test_dry_run_does_not_persist_changes(self):
        call_command("backfill_audit_chain", "--dry-run", "--tenant-id", str(self.tenant.id))
        rows = list(
            AuditEvent.all_objects.filter(tenant=self.tenant).order_by("timestamp")
        )
        for r in rows:
            self.assertIsNone(r.chain_hash, "dry-run must not write chain_hash")
            self.assertIsNone(r.chain_sequence, "dry-run must not write chain_sequence")

    @pytest.mark.integration
    def test_backfill_populates_full_chain(self):
        call_command("backfill_audit_chain", "--tenant-id", str(self.tenant.id))
        rows = list(
            AuditEvent.all_objects.filter(tenant=self.tenant).order_by("chain_sequence")
        )
        self.assertEqual(len(rows), 5)
        # Sequences 1..5, links match, hashes match recompute.
        for idx, row in enumerate(rows):
            self.assertEqual(row.chain_sequence, idx + 1)
            expected_prev = rows[idx - 1].chain_hash if idx > 0 else None
            self.assertEqual(row.prev_chain_hash, expected_prev)
            self.assertEqual(
                row.chain_hash,
                compute_chain_hash(
                    canonical_form(row),
                    row.prev_chain_hash,
                    row.timestamp.isoformat(),
                ),
            )
        # And verify_chain_segment is happy.
        self.assertTrue(verify_chain_segment(rows).verified)

    @pytest.mark.integration
    def test_backfill_fails_when_post_verify_detects_mismatch(self):
        # 234.1 audit-fix Gap D — the end-of-run verifier MUST catch a
        # broken chain even if backfill thought it succeeded. We simulate
        # the failure mode by pre-corrupting one row's chain_hash field
        # to a non-NULL value the backfill won't overwrite (because it
        # only touches rows where ``chain_hash IS NULL``). The post-run
        # verify then sees the inconsistency and raises CommandError.
        target_id = self.event_ids[2]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE audit_events SET chain_hash = %s, chain_sequence = 999 "
                "WHERE id = %s",
                ["f" * 64, str(target_id)],
            )
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError) as cm:
            call_command(
                "backfill_audit_chain", "--tenant-id", str(self.tenant.id),
            )
        self.assertIn("invalid chain", str(cm.exception))

    @pytest.mark.integration
    def test_backfill_skip_verify_flag_disables_post_check(self):
        # The same corruption no longer raises when ``--skip-verify`` is
        # passed — ops opt-in for re-runs after an independent audit.
        target_id = self.event_ids[2]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE audit_events SET chain_hash = %s, chain_sequence = 999 "
                "WHERE id = %s",
                ["f" * 64, str(target_id)],
            )
        call_command(
            "backfill_audit_chain", "--tenant-id", str(self.tenant.id),
            "--skip-verify",
        )

    @pytest.mark.integration
    def test_resume_from_skips_already_chained_rows(self):
        call_command("backfill_audit_chain", "--tenant-id", str(self.tenant.id))
        # Take a snapshot of the chained state.
        before = {
            str(r.id): r.chain_hash for r in
            AuditEvent.all_objects.filter(tenant=self.tenant)
        }
        # Insert one MORE un-chained row.
        new_id = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit_events
                    (id, tenant_id, resource_type, action, result,
                     details_json, full_details_json, timestamp,
                     is_archived, chain_sequence, prev_chain_hash, chain_hash)
                VALUES (%s, %s, 'ASSET', 'A_NEW', 'SUCCESS', %s, NULL,
                        NOW() + interval '1 hour', false, NULL, NULL, NULL)
                """,
                [str(new_id), str(self.tenant.id), json.dumps({"n": 99})],
            )
        # Resume from the LATEST sequence — chained rows are not re-hashed.
        call_command(
            "backfill_audit_chain",
            "--tenant-id", str(self.tenant.id),
            "--resume-from", "auto",
        )
        after = {
            str(r.id): r.chain_hash for r in
            AuditEvent.all_objects.filter(tenant=self.tenant)
        }
        # Pre-existing rows unchanged.
        for k, v in before.items():
            self.assertEqual(after[k], v, "resume must not mutate already-chained rows")
        # New row now chained.
        new_row = AuditEvent.all_objects.get(id=new_id)
        self.assertIsNotNone(new_row.chain_hash)
        self.assertEqual(new_row.chain_sequence, 6)
