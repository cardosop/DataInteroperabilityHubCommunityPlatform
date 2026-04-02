"""
Phase 121G-A — Webhook Encryption Vault Transit Tests

Tests the Vault Transit integration in webhooks/encryption.py:
1. encrypt_secret tries Vault Transit first, falls back to Fernet
2. decrypt_secret routes vault: prefix to Vault Transit
3. Idempotency for both vault: and v1: prefixes
4. Error handling: decrypt raises ValueError on Vault Transit failure
5. Fernet round-trip still works (backward compat)
6. Legacy plaintext pass-through
"""

import os
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase, override_settings

from hub.apps.webhooks.encryption import (
    encrypt_secret,
    decrypt_secret,
    _VAULT_PREFIX,
    _PREFIX,
)

# Webhook encryption.py imports from integrations.encryption inside function
# bodies, so we patch at the source module (hub.apps.integrations.encryption).
_INT_ENC = "hub.apps.integrations.encryption"


class WebhookVaultTransitEncryptTest(TestCase):
    """Test Vault Transit encrypt path in webhook encryption."""

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_encrypt_uses_transit_when_available(self):
        """encrypt_secret should use Vault Transit when available."""
        mock_encrypt = MagicMock(return_value="vault:v1:webhook-cipher")

        with patch.dict(os.environ, {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_TOKEN": "s.test",
        }):
            with patch(
                f"{_INT_ENC}._is_vault_transit_available",
                return_value=True,
            ), patch(
                f"{_INT_ENC}._vault_transit_encrypt",
                mock_encrypt,
            ):
                result = encrypt_secret("my-webhook-secret")

        self.assertEqual(result, "vault:v1:webhook-cipher")
        mock_encrypt.assert_called_once_with(b"my-webhook-secret")

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_encrypt_falls_back_to_fernet_on_vault_error(self):
        """When Vault Transit fails, encrypt_secret should fall back to Fernet."""
        mock_encrypt = MagicMock(side_effect=Exception("Vault down"))

        with patch.dict(os.environ, {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_TOKEN": "s.test",
        }):
            with patch(
                f"{_INT_ENC}._is_vault_transit_available",
                return_value=True,
            ), patch(
                f"{_INT_ENC}._vault_transit_encrypt",
                mock_encrypt,
            ):
                result = encrypt_secret("fallback-secret")

        # Should fall back to Fernet (v1: prefix)
        self.assertTrue(result.startswith(_PREFIX))
        # Should round-trip via Fernet
        decrypted = decrypt_secret(result)
        self.assertEqual(decrypted, "fallback-secret")

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_encrypt_uses_fernet_when_vault_unavailable(self):
        """Without Vault env vars, encrypt_secret should use Fernet."""
        with patch.dict(os.environ, {}, clear=True):
            result = encrypt_secret("fernet-only-secret")

        self.assertTrue(result.startswith(_PREFIX))
        decrypted = decrypt_secret(result)
        self.assertEqual(decrypted, "fernet-only-secret")


class WebhookVaultTransitDecryptTest(TestCase):
    """Test Vault Transit decrypt path in webhook encryption."""

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_decrypt_routes_vault_prefix_to_transit(self):
        """Ciphertext starting with vault: should use Vault Transit."""
        mock_decrypt = MagicMock(return_value=b"decrypted-webhook-secret")

        with patch(
            f"{_INT_ENC}._vault_transit_decrypt",
            mock_decrypt,
        ):
            result = decrypt_secret("vault:v1:someciphertext")

        self.assertEqual(result, "decrypted-webhook-secret")
        mock_decrypt.assert_called_once_with("vault:v1:someciphertext")

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_decrypt_raises_valueerror_on_vault_failure(self):
        """Vault Transit decrypt failure should raise ValueError."""
        mock_decrypt = MagicMock(side_effect=Exception("Vault unreachable"))

        with patch(
            f"{_INT_ENC}._vault_transit_decrypt",
            mock_decrypt,
        ):
            with self.assertRaises(ValueError) as ctx:
                decrypt_secret("vault:v1:bad-cipher")

        self.assertIn("Vault Transit", str(ctx.exception))

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_decrypt_fernet_roundtrip(self):
        """Fernet-encrypted values should decrypt correctly."""
        with patch.dict(os.environ, {}, clear=True):
            encrypted = encrypt_secret("fernet-secret")
        self.assertTrue(encrypted.startswith(_PREFIX))
        decrypted = decrypt_secret(encrypted)
        self.assertEqual(decrypted, "fernet-secret")

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_decrypt_legacy_plaintext(self):
        """Values without prefix are legacy plaintext."""
        self.assertEqual(decrypt_secret("legacy-plain"), "legacy-plain")


class WebhookEncryptIdempotencyTest(TestCase):
    """Test idempotency for both encryption formats."""

    @override_settings(ENCRYPTION_KEY="test-key-for-webhook-tests")
    def test_idempotent_for_fernet_prefix(self):
        """Re-encrypting a v1: value returns it unchanged."""
        with patch.dict(os.environ, {}, clear=True):
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
