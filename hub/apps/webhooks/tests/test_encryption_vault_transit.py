"""
Phase 211 — Webhook Encryption AWS KMS Tests (replaces Vault Transit tests)

Tests the AWS KMS integration in webhooks/encryption.py:
1. encrypt_secret tries KMS first, falls back to Fernet
2. decrypt_secret routes aws-kms: prefix to KMS
3. Idempotency for aws-kms:, vault:, and v1: prefixes
4. Error handling: decrypt raises ValueError on legacy vault: prefix
5. Fernet round-trip still works (backward compat)
6. Legacy plaintext pass-through

KMS calls use moto for realistic AWS simulation.
"""

import os

import boto3
from django.test import TestCase, override_settings
from moto import mock_aws

from hub.apps.integrations.encryption import reset_kms_client
from hub.apps.webhooks.encryption import (
    _AWS_KMS_PREFIX,
    _PREFIX,
    decrypt_secret,
    encrypt_secret,
)


@mock_aws
class WebhookKmsEncryptTest(TestCase):
    """Test AWS KMS encrypt path in webhook encryption."""

    def setUp(self):
        reset_kms_client()
        self._orig_key = os.environ.pop("AWS_KMS_KEY_ID", None)
        self._orig_region = os.environ.get("AWS_REGION")
        os.environ["AWS_REGION"] = "us-east-1"
        client = boto3.client("kms", region_name="us-east-1")
        key = client.create_key(Description="test-webhook-key")
        self._key_id = key["KeyMetadata"]["KeyId"]
        os.environ["AWS_KMS_KEY_ID"] = self._key_id

    def tearDown(self):
        if self._orig_key is not None:
            os.environ["AWS_KMS_KEY_ID"] = self._orig_key
        else:
            os.environ.pop("AWS_KMS_KEY_ID", None)
        if self._orig_region is not None:
            os.environ["AWS_REGION"] = self._orig_region
        else:
            os.environ.pop("AWS_REGION", None)
        reset_kms_client()

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_encrypt_uses_kms_when_available(self):
        """encrypt_secret should use KMS when AWS_KMS_KEY_ID is set."""
        result = encrypt_secret("my-webhook-secret")
        self.assertTrue(result.startswith(_AWS_KMS_PREFIX))
        decrypted = decrypt_secret(result)
        self.assertEqual(decrypted, "my-webhook-secret")

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_encrypt_kms_roundtrip(self):
        """KMS-encrypted webhook secret should decrypt correctly."""
        encrypted = encrypt_secret("kms-webhook-secret")
        self.assertTrue(encrypted.startswith(_AWS_KMS_PREFIX))
        decrypted = decrypt_secret(encrypted)
        self.assertEqual(decrypted, "kms-webhook-secret")

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_encrypt_falls_back_to_fernet_on_kms_error(self):
        """When KMS fails, encrypt_secret should fall back to Fernet."""
        reset_kms_client()
        os.environ["AWS_KMS_KEY_ID"] = "nonexistent-key-id"
        result = encrypt_secret("fallback-secret")
        self.assertTrue(result.startswith(_PREFIX))
        decrypted = decrypt_secret(result)
        self.assertEqual(decrypted, "fallback-secret")


class WebhookFernetEncryptTest(TestCase):
    """Test Fernet path when KMS is unavailable."""

    def setUp(self):
        self._orig_key = os.environ.pop("AWS_KMS_KEY_ID", None)
        reset_kms_client()

    def tearDown(self):
        if self._orig_key is not None:
            os.environ["AWS_KMS_KEY_ID"] = self._orig_key
        else:
            os.environ.pop("AWS_KMS_KEY_ID", None)
        reset_kms_client()

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_encrypt_uses_fernet_when_kms_unavailable(self):
        """Without AWS_KMS_KEY_ID, encrypt_secret should use Fernet."""
        result = encrypt_secret("fernet-only-secret")
        self.assertTrue(result.startswith(_PREFIX))
        decrypted = decrypt_secret(result)
        self.assertEqual(decrypted, "fernet-only-secret")


class WebhookDecryptTest(TestCase):
    """Test decrypt routing by prefix."""

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_decrypt_raises_on_vault_prefix(self):
        """vault: prefix raises ValueError (Vault no longer available)."""
        with self.assertRaises(ValueError) as ctx:
            decrypt_secret("vault:v1:someciphertext")
        self.assertIn("Vault", str(ctx.exception))
        self.assertIn("no longer available", str(ctx.exception))

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_decrypt_fernet_roundtrip(self):
        """Fernet-encrypted values should decrypt correctly."""
        os.environ.pop("AWS_KMS_KEY_ID", None)
        reset_kms_client()
        encrypted = encrypt_secret("fernet-secret")
        self.assertTrue(encrypted.startswith(_PREFIX))
        decrypted = decrypt_secret(encrypted)
        self.assertEqual(decrypted, "fernet-secret")

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_decrypt_legacy_plaintext(self):
        """Values without prefix are legacy plaintext."""
        self.assertEqual(decrypt_secret("legacy-plain"), "legacy-plain")


class WebhookEncryptIdempotencyTest(TestCase):
    """Test idempotency for all encryption formats."""

    def setUp(self):
        self._orig_key = os.environ.pop("AWS_KMS_KEY_ID", None)
        reset_kms_client()

    def tearDown(self):
        if self._orig_key is not None:
            os.environ["AWS_KMS_KEY_ID"] = self._orig_key
        else:
            os.environ.pop("AWS_KMS_KEY_ID", None)
        reset_kms_client()

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_idempotent_for_fernet_prefix(self):
        """Re-encrypting a v1: value returns it unchanged."""
        encrypted = encrypt_secret("secret")
        self.assertTrue(encrypted.startswith(_PREFIX))
        double = encrypt_secret(encrypted)
        self.assertEqual(encrypted, double)

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_idempotent_for_vault_prefix(self):
        """Re-encrypting a vault: value returns it unchanged."""
        vault_cipher = "vault:v1:already-encrypted"
        result = encrypt_secret(vault_cipher)
        self.assertEqual(result, vault_cipher)

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_idempotent_for_kms_prefix(self):
        """Re-encrypting an aws-kms: value returns it unchanged."""
        kms_cipher = "aws-kms:someciphertext"
        result = encrypt_secret(kms_cipher)
        self.assertEqual(result, kms_cipher)
