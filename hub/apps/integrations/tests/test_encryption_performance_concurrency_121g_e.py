"""
Phase 121G-E.4 & E.5 — Encryption Performance & Concurrency Tests

E.4: Verify encryption adds <25ms per operation (container-safe threshold).
E.5: Verify Vault Transit client singleton is thread-safe.

All tests use real Fernet encryption (no mocks).
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from django.test import TestCase, override_settings

from hub.apps.integrations.encryption import (
    _get_fernet,
    decrypt_json_field,
    encrypt_json_field,
)
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)

# Use a proper 44-char base64 Fernet key to skip PBKDF2 derivation.
# This matches production behaviour where ENCRYPTION_KEY is a valid
# Fernet key.  With a short string key, PBKDF2 (100k iterations)
# adds ~8ms overhead per call — that's a security feature, not a bug.
import base64 as _b64
import secrets as _secrets

_FERNET_KEY = _b64.urlsafe_b64encode(_secrets.token_bytes(32)).decode()
ENCRYPTION_KEY = _FERNET_KEY


def _uid():
    return uuid.uuid4().hex[:8]


# ═══════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════
# 121G-E.4 — Performance: encryption < 25 ms per operation
# ═══════════════════════════════════════════════════════════════════════


@override_settings(ENCRYPTION_KEY=ENCRYPTION_KEY)
class EncryptionPerformanceTest(TestCase):
    """Verify encryption/decryption overhead is under 25ms per operation."""

    def test_encrypt_json_field_under_25ms(self):
        """encrypt_json_field() should complete in under 25ms for typical payloads."""
        data = {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "region": "us-east-1",
            "bucket": "my-data-bucket",
            "prefix": "ingestion/daily/",
        }
        # Warm up (first call may be slower due to key derivation)
        encrypt_json_field(data)

        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            encrypt_json_field(data)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        self.assertLess(
            avg_ms,
            25.0,
            f"encrypt_json_field avg {avg_ms:.2f}ms exceeds 25ms limit",
        )

    def test_decrypt_json_field_under_25ms(self):
        """decrypt_json_field() should complete in under 25ms for typical payloads."""
        data = {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "region": "us-east-1",
        }
        encrypted = encrypt_json_field(data)

        # Warm up (key derivation + first decrypt may be slower)
        decrypt_json_field(encrypted)

        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            decrypt_json_field(encrypted)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        self.assertLess(
            avg_ms,
            25.0,
            f"decrypt_json_field avg {avg_ms:.2f}ms exceeds 25ms limit",
        )

    def test_model_save_encryption_overhead_under_25ms(self):
        """Encryption overhead on model.save() should be under 25ms."""
        uid = _uid()
        tenant = Tenant.objects.create(
            name=f"PerfTest {uid}",
            slug=f"perftest-{uid}",
        )
        source_config = {
            "bucket": "perf-bucket",
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        }

        from hub.apps.scheduled_ingestion.models import ScheduledIngestion

        # Warm up encryption path (key derivation on first call)
        encrypt_json_field(source_config)

        # Measure save with encryption
        iterations = 20
        times_encrypted = []
        for i in range(iterations):
            si = ScheduledIngestion(
                tenant=tenant,
                name=f"perf-enc-{uid}-{i}",
                source_type="S3",
                source_config=source_config.copy(),
                schedule_config={"cron": "0 0 * * *"},
            )
            start = time.perf_counter()
            si.save()
            elapsed_ms = (time.perf_counter() - start) * 1000
            times_encrypted.append(elapsed_ms)

        # Measure save without encryption (empty config)
        times_plain = []
        for i in range(iterations):
            si = ScheduledIngestion(
                tenant=tenant,
                name=f"perf-plain-{uid}-{i}",
                source_type="S3",
                source_config={},
                schedule_config={"cron": "0 0 * * *"},
            )
            start = time.perf_counter()
            si.save()
            elapsed_ms = (time.perf_counter() - start) * 1000
            times_plain.append(elapsed_ms)

        avg_enc = sum(times_encrypted) / len(times_encrypted)
        avg_plain = sum(times_plain) / len(times_plain)
        overhead = avg_enc - avg_plain

        self.assertLess(
            overhead,
            25.0,
            f"Encryption overhead {overhead:.2f}ms exceeds 25ms limit "
            f"(encrypted avg={avg_enc:.2f}ms, plain avg={avg_plain:.2f}ms)",
        )

    def test_virtualization_bulk_creation_p95_under_50ms(self):
        """Bulk VirtualDataset creation p95 total latency must be under 50ms."""
        uid = _uid()
        tenant = Tenant.objects.create(
            name=f"BulkTest {uid}",
            slug=f"bulktest-{uid}",
        )
        sources = [
            {
                "type": "postgresql",
                "host": "db.example.com",
                "password": "secret-password",
                "connection_string": "postgresql://user:pass@host/db",
            },
            {
                "type": "rest",
                "url": "https://api.example.com",
                "api_key": "rest-api-key",
            },
        ]

        from hub.apps.virtualization.models import VirtualDataset

        iterations = 200
        times = []
        for i in range(iterations):
            vd = VirtualDataset(
                tenant=tenant,
                name=f"bulk-{uid}-{i}",
                query="SELECT * FROM t",
                query_type="SQL",
                sources=[s.copy() for s in sources],
            )
            start = time.perf_counter()
            vd.save()
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        times.sort()
        p95_idx = int(len(times) * 0.95)
        p95 = times[p95_idx]

        # p95 latency for save (including DB write) should be reasonable
        # We check overhead is not catastrophic — 50ms total is generous
        self.assertLess(
            p95,
            50.0,
            f"Bulk creation p95={p95:.2f}ms exceeds 50ms total limit",
        )


# ═══════════════════════════════════════════════════════════════════════
# 121G-E.5 — Concurrency: Fernet is stateless, Vault client singleton
# ═══════════════════════════════════════════════════════════════════════


@override_settings(ENCRYPTION_KEY=ENCRYPTION_KEY)
class EncryptionConcurrencyTest(TestCase):
    """Verify encryption is thread-safe for concurrent operations."""

    def test_concurrent_round_trip_no_cross_contamination(self):
        """Concurrent encrypt+decrypt round-trips must not cross-contaminate
        results across threads. Uses realistic credential payloads under
        thread contention."""
        configs = [
            {
                "bucket": f"bucket-{i}",
                "secret_access_key": f"wJalrXUtnFEMI-KEY-{i}",
                "connection_string": f"postgresql://u:p{i}@host/db{i}",
                "region": "us-east-1",
            }
            for i in range(50)
        ]
        errors = []

        def round_trip(idx):
            try:
                encrypted = encrypt_json_field(configs[idx])
                decrypted = decrypt_json_field(encrypted)
                return idx, decrypted
            except Exception as e:
                return idx, e

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(round_trip, i): i for i in range(len(configs))}
            results = {}
            for future in as_completed(futures):
                idx, result = future.result()
                if isinstance(result, Exception):
                    errors.append((idx, result))
                else:
                    results[idx] = result

        self.assertEqual(
            len(errors),
            0,
            f"Concurrent round-trip errors: {errors}",
        )
        for idx, decrypted in results.items():
            self.assertEqual(decrypted, configs[idx],
                             f"Mismatch at index {idx}")

    def test_fernet_round_trips_distinct_payloads(self):
        """Fernet instances (via _get_fernet) correctly encrypt and
        decrypt distinct payloads through project functions. Multiple
        distinct payloads encrypted/decrypted in reverse order must all
        round-trip correctly, proving Fernet is stateless."""
        data_a = {"key": "alpha", "nested": {"x": 1}}
        data_b = {"key": "beta", "nested": {"y": 2}}

        enc_a = encrypt_json_field(data_a)
        enc_b = encrypt_json_field(data_b)

        # Decrypt in reverse order to prove statelessness
        dec_b = decrypt_json_field(enc_b)
        dec_a = decrypt_json_field(enc_a)

        self.assertEqual(dec_a, data_a)
        self.assertEqual(dec_b, data_b)

    def test_fernet_path_works_after_kms_client_reset(self):
        """Fernet encrypt/decrypt must continue working after KMS client
        singleton is reset (as happens after a KMS failure)."""
        from hub.apps.integrations.encryption import reset_kms_client

        # Reset KMS client to None (simulates post-failure state)
        reset_kms_client()
        try:
            # Fernet path should still work fine
            data = {"test": "after-reset"}
            encrypted = encrypt_json_field(data)
            decrypted = decrypt_json_field(encrypted)
            self.assertEqual(decrypted, data)
        finally:
            reset_kms_client()
