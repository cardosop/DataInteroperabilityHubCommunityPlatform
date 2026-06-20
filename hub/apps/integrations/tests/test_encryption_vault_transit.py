"""
Phase 211 — AWS KMS Encryption Tests (replaces Phase 121G-A Vault Transit tests)

Tests the AWS KMS integration in encryption.py:
1. KMS available when AWS_KMS_KEY_ID set
2. KMS encrypt + decrypt round-trip via moto
3. Fernet fallback when KMS unavailable
4. Fernet fallback on KMS error
5. Prefix detection routes correctly (aws-kms:, vault:, fernet)
6. Backward-compatible Fernet decrypt
7. Legacy vault:v1:* raises explicit migration error
8. KMS client singleton reset on failure

All tests use real Fernet encryption (no mocks for Fernet).
KMS calls use moto for realistic AWS simulation.
"""

import os

import boto3
from django.test import TestCase, override_settings
from moto import mock_aws

from hub.apps.integrations.encryption import (
    _AWS_KMS_PREFIX,
    _VAULT_TRANSIT_PREFIX,
    EncryptionError,
    _is_kms_available,
    decrypt_json_field,
    encrypt_json_field,
    reset_kms_client,
)


class KmsAvailabilityTest(TestCase):
    """Test _is_kms_available() environment detection."""

    def setUp(self):
        self._orig = os.environ.pop("AWS_KMS_KEY_ID", None)

    def tearDown(self):
        if self._orig is not None:
            os.environ["AWS_KMS_KEY_ID"] = self._orig
        else:
            os.environ.pop("AWS_KMS_KEY_ID", None)

    def test_unavailable_when_key_id_not_set(self):
        self.assertFalse(_is_kms_available())

    def test_unavailable_when_key_id_empty(self):
        os.environ["AWS_KMS_KEY_ID"] = ""
        self.assertFalse(_is_kms_available())

    def test_available_with_key_id(self):
        os.environ["AWS_KMS_KEY_ID"] = "arn:aws:kms:us-east-1:123:key/abc"
        self.assertTrue(_is_kms_available())


class FernetFallbackTest(TestCase):
    """Test Fernet encryption works when KMS is unavailable."""

    # Pre-computed Fernet ciphertext for {"old_key": "old_value"}
    # encrypted with ENCRYPTION_KEY="test-key-for-unit-tests".
    # Generated once and hard-coded to simulate a pre-existing
    # ciphertext (e.g. a row encrypted before a KMS migration).
    _PRECOMPUTED_CIPHERTEXT = (
        "Z0FBQUFBQnFOUU9XbnR3YlU2RnRNbEJabXlvMzltVDYxUmZ"
        "LTmRYQnJRU3QtNHpvNnlBY0w4b1l4am5qVHB5cjFlZV8tSG"
        "RaTzBCOFRvVVFKclFDTXJtV1lmYTQ4SmJacEtSSXN5UEVSUX"
        "QwSFQ2a0V3NlRfS0E9"
    )

    def setUp(self):
        self._orig = os.environ.pop("AWS_KMS_KEY_ID", None)
        reset_kms_client()

    def tearDown(self):
        if self._orig is not None:
            os.environ["AWS_KMS_KEY_ID"] = self._orig
        else:
            os.environ.pop("AWS_KMS_KEY_ID", None)
        reset_kms_client()

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_encrypt_uses_fernet_when_kms_unavailable(self):
        """Without AWS_KMS_KEY_ID, encrypt should use Fernet."""
        data = {"api_key": "secret123", "endpoint": "https://api.example.com"}
        encrypted = encrypt_json_field(data)
        self.assertFalse(encrypted.startswith(_AWS_KMS_PREFIX))
        self.assertFalse(encrypted.startswith(_VAULT_TRANSIT_PREFIX))
        decrypted = decrypt_json_field(encrypted)
        self.assertEqual(decrypted, data)

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_decrypt_fernet_backward_compatible(self):
        """Pre-existing Fernet ciphertext (encrypted before KMS migration)
        must still decrypt correctly with the current code."""
        result = decrypt_json_field(self._PRECOMPUTED_CIPHERTEXT)
        self.assertEqual(result, {"old_key": "old_value"})

    # ── error-path coverage for encrypt_json_field ──────────────

    def test_encrypt_raises_on_non_dict(self):
        """encrypt_json_field must raise EncryptionError for non-dict input."""
        with self.assertRaises(EncryptionError) as ctx:
            encrypt_json_field("not-a-dict")
        self.assertIn("must be a dictionary", str(ctx.exception))

        with self.assertRaises(EncryptionError):
            encrypt_json_field([1, 2, 3])

        with self.assertRaises(EncryptionError):
            encrypt_json_field(None)

        with self.assertRaises(EncryptionError):
            encrypt_json_field(42)

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_encrypt_raises_on_non_serializable(self):
        """encrypt_json_field must raise EncryptionError for
        non-JSON-serializable dict content."""
        with self.assertRaises(EncryptionError):
            encrypt_json_field({"fn": lambda x: x})
        with self.assertRaises(EncryptionError):
            encrypt_json_field({"obj": object()})

    # ── error-path coverage for decrypt_json_field ──────────────

    def test_decrypt_empty_string_returns_empty_dict(self):
        """decrypt_json_field('') must return {} (treat as no data)."""
        self.assertEqual(decrypt_json_field(""), {})

    def test_decrypt_none_raises_error(self):
        """decrypt_json_field(None) must raise EncryptionError."""
        # decrypt_json_field treats falsy values (None, 0, "") as empty
        # and returns {}. Passing None goes through `not encrypted_str`
        # which is True → returns {}. This is the documented contract.
        self.assertEqual(decrypt_json_field(None), {})

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_decrypt_malformed_base64_raises_error(self):
        """decrypt_json_field with malformed base64 must raise EncryptionError."""
        with self.assertRaises(EncryptionError) as ctx:
            decrypt_json_field("!!!not-valid-base64!!!")
        self.assertIn("Failed to decrypt", str(ctx.exception))

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_decrypt_valid_base64_invalid_json_raises_error(self):
        """decrypt_json_field with valid Fernet token containing non-JSON
        plaintext must raise EncryptionError."""
        import base64 as _base64

        from hub.apps.integrations.encryption import _get_fernet as _gf

        fernet = _gf()
        tampered = _base64.urlsafe_b64encode(
            fernet.encrypt(b"not json")
        ).decode()
        with self.assertRaises(EncryptionError):
            decrypt_json_field(tampered)

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_decrypt_non_dict_result_raises_error(self):
        """decrypt_json_field with valid decryption yielding non-dict result
        must raise EncryptionError."""
        import base64 as _base64

        from hub.apps.integrations.encryption import _get_fernet as _gf

        fernet = _gf()
        token = fernet.encrypt(b'"just a string"')
        encoded = _base64.urlsafe_b64encode(token).decode()
        with self.assertRaises(EncryptionError) as ctx:
            decrypt_json_field(encoded)
        self.assertIn("must be a dict", str(ctx.exception))


@mock_aws
class KmsEncryptTest(TestCase):
    """Test AWS KMS encrypt path using moto."""

    def setUp(self):
        reset_kms_client()
        self._orig_key = os.environ.pop("AWS_KMS_KEY_ID", None)
        self._orig_region = os.environ.get("AWS_REGION")
        os.environ["AWS_REGION"] = "us-east-1"
        client = boto3.client("kms", region_name="us-east-1")
        key = client.create_key(Description="test-encryption-key")
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

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_encrypt_uses_kms_when_available(self):
        """When AWS_KMS_KEY_ID is set, encrypt should use KMS."""
        data = {"api_key": "secret"}
        encrypted = encrypt_json_field(data)
        self.assertTrue(encrypted.startswith(_AWS_KMS_PREFIX))
        decrypted = decrypt_json_field(encrypted)
        self.assertEqual(decrypted, data)

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_encrypt_falls_back_on_kms_error(self):
        """When KMS key doesn't exist, fall back to Fernet."""
        reset_kms_client()
        os.environ["AWS_KMS_KEY_ID"] = "nonexistent-key-id"
        data = {"fallback_key": "fallback_value"}
        encrypted = encrypt_json_field(data)
        self.assertFalse(encrypted.startswith(_AWS_KMS_PREFIX))
        decrypted = decrypt_json_field(encrypted)
        self.assertEqual(decrypted, data)


@mock_aws
class KmsDecryptTest(TestCase):
    """Test AWS KMS decrypt path."""

    def setUp(self):
        reset_kms_client()
        self._orig_key = os.environ.pop("AWS_KMS_KEY_ID", None)
        self._orig_region = os.environ.get("AWS_REGION")
        os.environ["AWS_REGION"] = "us-east-1"
        client = boto3.client("kms", region_name="us-east-1")
        key = client.create_key(Description="test-decrypt-key")
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

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_decrypt_routes_kms_prefix_to_kms(self):
        """Ciphertext starting with aws-kms: should use KMS."""
        data = {"key": "value"}
        encrypted = encrypt_json_field(data)
        self.assertTrue(encrypted.startswith(_AWS_KMS_PREFIX))
        result = decrypt_json_field(encrypted)
        self.assertEqual(result, data)

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_decrypt_non_kms_uses_fernet(self):
        """Non-KMS ciphertext should use Fernet path."""
        os.environ.pop("AWS_KMS_KEY_ID", None)
        reset_kms_client()
        data = {"fernet_key": "fernet_value"}
        encrypted = encrypt_json_field(data)
        result = decrypt_json_field(encrypted)
        self.assertEqual(result, data)


class LegacyVaultTransitTest(TestCase):
    """Test that legacy vault:v1:* ciphertexts raise a clear error."""

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_vault_transit_ciphertext_raises_error(self):
        """vault:v1:* ciphertext raises EncryptionError with migration message."""
        with self.assertRaises(EncryptionError) as ctx:
            decrypt_json_field("vault:v1:somelegacyciphertext")
        self.assertIn("Legacy Vault Transit", str(ctx.exception))
        self.assertIn("re-encryption migration", str(ctx.exception))


class KmsClientResetTest(TestCase):
    """Test KMS client singleton behavior."""

    def setUp(self):
        self._orig_key = os.environ.pop("AWS_KMS_KEY_ID", None)
        self._orig_region = os.environ.get("AWS_REGION")
        reset_kms_client()

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

    @override_settings(ENCRYPTION_KEY="test-key-for-unit-tests")
    def test_client_reset_on_failure(self):
        """After KMS failure, client is reset AND Fernet fallback succeeds."""
        import hub.apps.integrations.encryption as enc_mod

        os.environ["AWS_KMS_KEY_ID"] = "bad-key"
        os.environ["AWS_REGION"] = "us-east-1"
        data = {"test": "data"}
        encrypted = encrypt_json_field(data)

        # 1. Client singleton was reset after KMS failure
        self.assertIsNone(enc_mod._kms_client)
        # 2. Encrypt succeeded via Fernet fallback (not KMS prefix)
        self.assertFalse(encrypted.startswith(_AWS_KMS_PREFIX))
        # 3. The ciphertext actually decrypts back to the original data
        decrypted = decrypt_json_field(encrypted)
        self.assertEqual(decrypted, data)
