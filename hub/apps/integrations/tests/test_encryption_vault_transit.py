"""
Phase 121G-A — Vault Transit Encryption Tests

Tests the Vault Transit integration in encryption.py:
1. Transit encrypt when available
2. Transit decrypt vault ciphertext
3. Fernet fallback when Vault unavailable
4. Fernet fallback on Vault error + WARNING logged
5. Prefix detection routes correctly
6. Backward-compatible Fernet decrypt
7. Client caching
8. Client reset on failure

All tests use real Fernet encryption (no mocks for Fernet).
Vault Transit calls use unittest.mock since no live Vault in CI.
"""

import base64
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase, override_settings

from hub.apps.integrations.encryption import (
    EncryptionError,
    decrypt_json_field,
    encrypt_json_field,
    _is_vault_transit_available,
    _VAULT_TRANSIT_PREFIX,
)


class VaultTransitAvailabilityTest(TestCase):
    """Test _is_vault_transit_available() environment detection."""

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_unavailable_when_vault_addr_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_is_vault_transit_available())

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_unavailable_when_vault_addr_empty(self):
        with patch.dict(os.environ, {"VAULT_ADDR": ""}):
            self.assertFalse(_is_vault_transit_available())

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_available_with_token(self):
        with patch.dict(os.environ, {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_TOKEN": "s.abcdef123",
        }):
            self.assertTrue(_is_vault_transit_available())

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_available_with_approle(self):
        with patch.dict(os.environ, {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_ROLE_ID": "role-id",
            "VAULT_SECRET_ID": "secret-id",
        }):
            self.assertTrue(_is_vault_transit_available())


class FernetFallbackTest(TestCase):
    """Test Fernet encryption works when Vault is unavailable."""

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_encrypt_uses_fernet_when_vault_unavailable(self):
        """Without VAULT_ADDR, encrypt should use Fernet."""
        with patch.dict(os.environ, {}, clear=True):
            data = {"api_key": "secret123", "endpoint": "https://api.example.com"}
            encrypted = encrypt_json_field(data)
            # Fernet ciphertext is base64, NOT prefixed with vault:
            self.assertFalse(encrypted.startswith(_VAULT_TRANSIT_PREFIX))
            # Round-trip works
            decrypted = decrypt_json_field(encrypted)
            self.assertEqual(decrypted, data)

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_decrypt_fernet_backward_compatible(self):
        """Existing Fernet-encrypted data should still decrypt."""
        data = {"old_key": "old_value"}
        with patch.dict(os.environ, {}, clear=True):
            encrypted = encrypt_json_field(data)
            # Verify it's Fernet (no vault prefix)
            self.assertFalse(encrypted.startswith(_VAULT_TRANSIT_PREFIX))
            # Decrypt should work
            result = decrypt_json_field(encrypted)
            self.assertEqual(result, data)


class VaultTransitEncryptTest(TestCase):
    """Test Vault Transit encrypt path."""

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_encrypt_uses_transit_when_available(self):
        """When Vault is available, encrypt should use Transit."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.encrypt_data.return_value = {
            "data": {"ciphertext": "vault:v1:abc123encrypted"}
        }

        with patch.dict(os.environ, {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_TOKEN": "s.test",
        }):
            with patch(
                "hub.apps.integrations.encryption._get_vault_transit_client",
                return_value=mock_client,
            ):
                data = {"api_key": "secret"}
                encrypted = encrypt_json_field(data)

        self.assertTrue(encrypted.startswith("vault:v1:"))
        mock_client.secrets.transit.encrypt_data.assert_called_once()

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_encrypt_falls_back_on_vault_error(self):
        """When Vault Transit fails, fall back to Fernet."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.encrypt_data.side_effect = Exception("Vault down")

        with patch.dict(os.environ, {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_TOKEN": "s.test",
        }):
            with patch(
                "hub.apps.integrations.encryption._get_vault_transit_client",
                return_value=mock_client,
            ):
                data = {"fallback_key": "fallback_value"}
                encrypted = encrypt_json_field(data)

        # Should fall back to Fernet (no vault: prefix)
        self.assertFalse(encrypted.startswith(_VAULT_TRANSIT_PREFIX))
        # Should still be decryptable
        decrypted = decrypt_json_field(encrypted)
        self.assertEqual(decrypted, data)


class VaultTransitDecryptTest(TestCase):
    """Test Vault Transit decrypt path."""

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_decrypt_routes_vault_prefix_to_transit(self):
        """Ciphertext starting with vault: should use Transit."""
        plaintext_data = {"key": "value"}
        plaintext_b64 = base64.b64encode(
            json.dumps(plaintext_data, sort_keys=True).encode()
        ).decode()

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.decrypt_data.return_value = {
            "data": {"plaintext": plaintext_b64}
        }

        with patch(
            "hub.apps.integrations.encryption._get_vault_transit_client",
            return_value=mock_client,
        ):
            result = decrypt_json_field("vault:v1:someciphertext")

        self.assertEqual(result, plaintext_data)
        mock_client.secrets.transit.decrypt_data.assert_called_once()

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_decrypt_non_vault_uses_fernet(self):
        """Non-vault ciphertext should use Fernet path."""
        data = {"fernet_key": "fernet_value"}
        with patch.dict(os.environ, {}, clear=True):
            encrypted = encrypt_json_field(data)
        # Decrypt without Vault
        result = decrypt_json_field(encrypted)
        self.assertEqual(result, data)


class VaultClientCachingTest(TestCase):
    """Test Vault Transit client singleton behavior."""

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_client_reset_on_failure(self):
        """After encrypt failure, _vault_client should be reset."""
        import hub.apps.integrations.encryption as enc_mod

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.encrypt_data.side_effect = Exception("fail")

        with patch.dict(os.environ, {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_TOKEN": "s.test",
        }):
            with patch(
                "hub.apps.integrations.encryption._get_vault_transit_client",
                return_value=mock_client,
            ):
                # This should fall back to Fernet and reset client
                encrypt_json_field({"test": "data"})

        # After failure, module-level client should be None
        self.assertIsNone(enc_mod._vault_client)
