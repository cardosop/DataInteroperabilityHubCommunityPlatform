"""
Unit tests for OpenLineage model helpers and model methods.

Covers :func:`generate_ingest_key_plaintext`, :func:`hash_ingest_key`,
:func:`verify_ingest_key`, :meth:`OpenLineageIngestApiKey.is_active`, and
:class:`OpenLineageDeadLetter` encryption round-trip.

Previously these functions were only exercised indirectly through view /
integration tests; this file adds direct, deterministic unit coverage.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.test import TransactionTestCase
from django.utils import timezone

from hub.apps.integrations.openlineage.models import (
    OpenLineageDeadLetter,
    OpenLineageIngestApiKey,
    generate_ingest_key_plaintext,
    hash_ingest_key,
    verify_ingest_key,
)


def _create_tenant():
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"OLModelTest Co {suffix}",
        slug=f"olmt-{suffix}",
    )


# ---------------------------------------------------------------------------
# generate_ingest_key_plaintext
# ---------------------------------------------------------------------------


class TestGenerateIngestKeyPlaintext(TransactionTestCase):
    def test_format_and_length(self):
        """Generated key must start with ``msh_ol_`` and have sufficient entropy."""
        key = generate_ingest_key_plaintext()
        assert key.startswith("msh_ol_"), f"unexpected prefix: {key[:20]}"
        # 6-char prefix + 48 url-safe chars ≈ 54 chars total
        assert len(key) >= 54, f"key too short: {len(key)}"

    def test_uniqueness(self):
        """Two consecutive calls must produce different keys."""
        keys = {generate_ingest_key_plaintext() for _ in range(10)}
        assert len(keys) == 10, "keys should be unique across calls"

    def test_url_safe_characters(self):
        """Key must contain only URL-safe (base64url) characters after the prefix."""
        import base64

        key = generate_ingest_key_plaintext()
        body = key.removeprefix("msh_ol_")
        # All characters should be in the base64url alphabet + padding
        for ch in body:
            assert ch in (
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            ), f"non-url-safe character {ch!r} in key body"


# ---------------------------------------------------------------------------
# hash_ingest_key / verify_ingest_key
# ---------------------------------------------------------------------------


class TestHashAndVerifyIngestKey(TransactionTestCase):
    def test_hash_produces_bcrypt_format(self):
        """Hash must be a bcrypt $2b$ string."""
        plaintext = generate_ingest_key_plaintext()
        hashed = hash_ingest_key(plaintext)
        assert hashed.startswith("$2b$12$"), f"unexpected hash format: {hashed[:20]}"

    def test_verify_roundtrip(self):
        """Plaintext → hash → verify returns True."""
        plaintext = generate_ingest_key_plaintext()
        hashed = hash_ingest_key(plaintext)
        assert verify_ingest_key(plaintext, hashed) is True

    def test_verify_rejects_different_plaintext(self):
        """Wrong plaintext against the same hash must return False."""
        plaintext = generate_ingest_key_plaintext()
        other = generate_ingest_key_plaintext()
        hashed = hash_ingest_key(plaintext)
        assert verify_ingest_key(other, hashed) is False

    def test_verify_rejects_empty_plaintext(self):
        """Empty plaintext must not match."""
        hashed = hash_ingest_key(generate_ingest_key_plaintext())
        assert verify_ingest_key("", hashed) is False

    def test_verify_rejects_tampered_hash(self):
        """A tampered hash string should cause verify to return False, not raise."""
        plaintext = generate_ingest_key_plaintext()
        assert verify_ingest_key(plaintext, "not-a-valid-bcrypt-hash") is False

    def test_hash_deterministic_same_input(self):
        """Two hashes of the same plaintext are NOT equal (bcrypt salts differ)."""
        plaintext = "fixed-test-plaintext-key"
        h1 = hash_ingest_key(plaintext)
        h2 = hash_ingest_key(plaintext)
        # Bcrypt includes a random salt — hashes must differ
        assert h1 != h2, "bcrypt hashes of same input should differ due to salt"
        # But both must verify
        assert verify_ingest_key(plaintext, h1) is True
        assert verify_ingest_key(plaintext, h2) is True


# ---------------------------------------------------------------------------
# OpenLineageIngestApiKey.is_active
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestIngestApiKeyIsActive(TransactionTestCase):
    def test_active_when_no_expiry_and_not_revoked(self):
        tenant = _create_tenant()
        key = OpenLineageIngestApiKey.objects.create(
            tenant=tenant,
            label="test-active",
            key_prefix="test0001",
            key_hash=hash_ingest_key(generate_ingest_key_plaintext()),
        )
        assert key.is_active() is True

    def test_inactive_when_revoked(self):
        tenant = _create_tenant()
        key = OpenLineageIngestApiKey.objects.create(
            tenant=tenant,
            label="test-revoked",
            key_prefix="test0002",
            key_hash=hash_ingest_key(generate_ingest_key_plaintext()),
            revoked_at=timezone.now(),
        )
        assert key.is_active() is False

    def test_inactive_when_expired(self):
        tenant = _create_tenant()
        key = OpenLineageIngestApiKey.objects.create(
            tenant=tenant,
            label="test-expired",
            key_prefix="test0003",
            key_hash=hash_ingest_key(generate_ingest_key_plaintext()),
            expires_at=timezone.now() - timedelta(days=1),
        )
        assert key.is_active() is False

    def test_active_when_expires_in_future(self):
        """Key whose expires_at is in the future is still active."""
        tenant = _create_tenant()
        key = OpenLineageIngestApiKey.objects.create(
            tenant=tenant,
            label="test-grace",
            key_prefix="test0004",
            key_hash=hash_ingest_key(generate_ingest_key_plaintext()),
            expires_at=timezone.now() + timedelta(days=7),
        )
        assert key.is_active() is True

    def test_revoked_takes_priority_over_expiry(self):
        """A revoked key is inactive even if expires_at is in the future."""
        tenant = _create_tenant()
        key = OpenLineageIngestApiKey.objects.create(
            tenant=tenant,
            label="test-revoked-grace",
            key_prefix="test0005",
            key_hash=hash_ingest_key(generate_ingest_key_plaintext()),
            expires_at=timezone.now() + timedelta(days=7),
            revoked_at=timezone.now(),
        )
        assert key.is_active() is False

    def test_is_active_accepts_explicit_now(self):
        """Explicit ``now`` parameter should be used instead of timezone.now()."""
        tenant = _create_tenant()
        key = OpenLineageIngestApiKey.objects.create(
            tenant=tenant,
            label="test-explicit-now",
            key_prefix="test0006",
            key_hash=hash_ingest_key(generate_ingest_key_plaintext()),
            expires_at=timezone.now() + timedelta(days=1),
        )
        # Fast forward past expiry
        far_future = timezone.now() + timedelta(days=30)
        assert key.is_active(now=far_future) is False


# ---------------------------------------------------------------------------
# OpenLineageDeadLetter — payload encryption round-trip
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestDeadLetterPayloadEncryption(TransactionTestCase):
    def test_payload_roundtrip(self):
        """Set then read back the event_payload; it must survive encryption."""
        tenant = _create_tenant()
        original = {
            "eventType": "COMPLETE",
            "eventTime": "2026-06-20T12:00:00Z",
            "producer": "https://meshant.com/",
            "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
            "run": {"runId": str(uuid.uuid4())},
            "job": {"namespace": "test.ns", "name": "test-job"},
            "inputs": [],
            "outputs": [],
        }
        dlq = OpenLineageDeadLetter.objects.create(
            tenant=tenant,
            event_id=original["run"]["runId"],
            target_url="http://marquez.example/api/v1/lineage",
            failure_reason="http_503",
            failure_detail="test failure",
            attempts=5,
        )
        dlq.event_payload = original
        dlq.save()

        # Re-fetch to ensure we get the persisted, encrypted value
        dlq.refresh_from_db()
        round_tripped = dlq.event_payload
        assert round_tripped == original, (
            f"payload round-trip failed: {round_tripped} != {original}"
        )

    def test_payload_encrypted_at_rest(self):
        """The ``event_payload_encrypted`` column must not contain plaintext."""
        tenant = _create_tenant()
        dlq = OpenLineageDeadLetter.objects.create(
            tenant=tenant,
            event_id=str(uuid.uuid4()),
            target_url="http://marquez.example/api/v1/lineage",
            failure_reason="http_503",
            failure_detail="test failure",
            attempts=3,
        )
        # Set a payload containing a known plaintext value
        secret_value = "CONFIDENTIAL-MESHANT-LINEAGE-DATA"
        dlq.event_payload = {
            "eventType": "COMPLETE",
            "eventTime": "2026-06-20T12:00:00Z",
            "producer": "https://meshant.com/",
            "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
            "run": {"runId": str(uuid.uuid4())},
            "job": {"namespace": "secret", "name": secret_value},
            "inputs": [],
            "outputs": [],
        }
        dlq.save()
        dlq.refresh_from_db()

        encrypted = dlq.event_payload_encrypted
        assert secret_value not in encrypted, (
            f"plaintext secret found in event_payload_encrypted: {encrypted[:100]}..."
        )
        # It should be non-empty base64-encoded ciphertext
        assert len(encrypted) > 0
        assert encrypted != "{}"

    def test_event_payload_uses_encryption_helper(self):
        """Verify that the encryption path goes through decrypt_secret/encrypt_secret."""
        from hub.apps.webhooks.encryption import decrypt_secret

        tenant = _create_tenant()
        dlq = OpenLineageDeadLetter.objects.create(
            tenant=tenant,
            event_id=str(uuid.uuid4()),
            target_url="http://marquez.example/api/v1/lineage",
            failure_reason="http_503",
            failure_detail="encryption test",
            attempts=1,
        )
        payload = {"test": "value", "run": {"runId": str(uuid.uuid4())}}
        dlq.event_payload = payload
        dlq.save()
        dlq.refresh_from_db()

        # The raw encrypted column must be directly decryptable
        plain = decrypt_secret(dlq.event_payload_encrypted)
        import json

        assert json.loads(plain) == payload
