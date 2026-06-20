"""
Encryption utilities for credential JSONFields.

Primary: AWS KMS envelope encryption (Phase 211: Vault → AWS migration)
Fallback: Fernet symmetric encryption via ENCRYPTION_KEY
Legacy:   Vault Transit ciphertexts (``vault:v1:...``) raise EncryptionError (requires re-encryption migration)

Ciphertext format detection:
- ``aws-kms:...``  → AWS KMS (new, Phase 211+)
- ``vault:v1:...`` → Legacy Vault Transit (decrypt via Fernet fallback)
- base64 string    → Fernet
- plaintext dict   → legacy (pre-encryption migration)
"""

import base64
import binascii
import hashlib
import json
import os
from typing import Any

import structlog
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings

logger = structlog.get_logger(__name__)

# ── AWS KMS constants ─────────────────────────────────────

_AWS_KMS_PREFIX = "aws-kms:"
_VAULT_TRANSIT_PREFIX = "vault:"

# Lazy singleton KMS client
_kms_client = None


class EncryptionError(Exception):
    """Exception raised when encryption/decryption fails."""


# ── AWS KMS helpers ───────────────────────────────────────


def _is_kms_available() -> bool:
    """Check if AWS KMS can be used for field-level encryption."""
    return bool(os.environ.get("AWS_KMS_KEY_ID", "").strip())


def _get_kms_client():
    """Get boto3 KMS client (lazy singleton)."""
    global _kms_client
    if _kms_client is not None:
        return _kms_client

    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1").strip()
    _kms_client = boto3.client("kms", region_name=region)
    return _kms_client


def _kms_encrypt(data_bytes: bytes) -> str:
    """Encrypt via AWS KMS. Returns aws-kms:<base64-ciphertext> string."""
    client = _get_kms_client()
    key_id = os.environ.get("AWS_KMS_KEY_ID", "").strip()
    response = client.encrypt(
        KeyId=key_id,
        Plaintext=data_bytes,
    )
    ciphertext_blob = response["CiphertextBlob"]
    return _AWS_KMS_PREFIX + base64.b64encode(ciphertext_blob).decode("utf-8")


def _kms_decrypt(ciphertext: str) -> bytes:
    """Decrypt an AWS KMS ciphertext (strip prefix, decode, call KMS)."""
    client = _get_kms_client()
    ciphertext_blob = base64.b64decode(ciphertext[len(_AWS_KMS_PREFIX) :])
    response = client.decrypt(CiphertextBlob=ciphertext_blob)
    return response["Plaintext"]


def reset_kms_client() -> None:
    """Reset the KMS client singleton (for testing)."""
    global _kms_client
    _kms_client = None


def _get_encryption_key() -> bytes:
    """
    Get or derive the encryption key from Django settings.

    If ENCRYPTION_KEY is a valid Fernet key (44 bytes base64), use it directly.
    Otherwise, derive a key from the ENCRYPTION_KEY string using PBKDF2.

    Returns:
        Encryption key as bytes

    Raises:
        EncryptionError: If encryption key cannot be derived
    """
    encryption_key_str = getattr(settings, "ENCRYPTION_KEY", None)

    if not encryption_key_str:
        raise EncryptionError(
            "ENCRYPTION_KEY not configured in Django settings. "
            "Set ENCRYPTION_KEY environment variable."
        )

    # Try to use ENCRYPTION_KEY as a Fernet key directly
    try:
        # Fernet keys are 32 bytes base64-encoded (44 characters)
        if len(encryption_key_str) == 44:
            # Try to decode as base64 Fernet key
            key_bytes = base64.urlsafe_b64decode(encryption_key_str.encode())
            if len(key_bytes) == 32:
                return encryption_key_str.encode()
    except (binascii.Error, ValueError) as e:
        # KEY is 44-char but not valid base64 → fall through to PBKDF2.
        logger.debug(
            "encryption_key_not_fernet_base64",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )

    # Derive key from string using PBKDF2
    # Use a salt derived from the key string itself for consistency
    salt = hashlib.sha256(encryption_key_str.encode()).digest()[:16]

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend(),
    )

    key = base64.urlsafe_b64encode(kdf.derive(encryption_key_str.encode()))
    return key


def _get_fernet() -> Fernet:
    """
    Get Fernet cipher instance.

    Returns:
        Fernet cipher instance

    Raises:
        EncryptionError: If Fernet cannot be initialized
    """
    try:
        key = _get_encryption_key()
        return Fernet(key)
    except Exception as e:
        raise EncryptionError(f"Failed to initialize Fernet cipher: {e!s}") from e


def encrypt_json_field(data: dict[str, Any]) -> str:
    """
    Encrypt a JSON-serializable dictionary for storage in a JSONField.

    The data is first serialized to JSON, then encrypted using Fernet.
    The encrypted data is base64-encoded for safe storage in JSONField.

    Args:
        data: Dictionary to encrypt (must be JSON-serializable)

    Returns:
        Base64-encoded encrypted string

    Raises:
        EncryptionError: If encryption fails

    Example:
        config = {"api_key": "secret123", "endpoint": "https://api.example.com"}
        encrypted = encrypt_json_field(config)
    """
    if not isinstance(data, dict):
        raise EncryptionError(f"Data must be a dictionary, got {type(data).__name__}")

    try:
        json_str = json.dumps(data, sort_keys=True)
        json_bytes = json_str.encode("utf-8")

        # Try AWS KMS first
        if _is_kms_available():
            try:
                ciphertext = _kms_encrypt(json_bytes)
                logger.debug("kms_encrypt_success")
                return ciphertext  # "aws-kms:..."
            except Exception as e:
                logger.warning(
                    "kms_encrypt_fallback",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                reset_kms_client()

        # Fernet fallback
        fernet = _get_fernet()
        encrypted_bytes = fernet.encrypt(json_bytes)
        return base64.urlsafe_b64encode(
            encrypted_bytes,
        ).decode("utf-8")
    except (TypeError, ValueError) as e:
        raise EncryptionError(
            f"Failed to serialize data to JSON: {e!s}",
        ) from e
    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(
            f"Failed to encrypt data: {e!s}",
        ) from e


def decrypt_json_field(encrypted_str: str) -> dict[str, Any]:
    """
    Decrypt an encrypted JSON string back to a dictionary.

    The encrypted string is base64-decoded, decrypted using Fernet,
    then deserialized from JSON back to a dictionary.

    Args:
        encrypted_str: Base64-encoded encrypted string

    Returns:
        Decrypted dictionary

    Raises:
        EncryptionError: If decryption fails

    Example:
        decrypted = decrypt_json_field(encrypted)
        # Returns: {"api_key": "secret123", "endpoint": "https://api.example.com"}
    """
    if not encrypted_str:
        return {}

    if not isinstance(encrypted_str, str):
        raise EncryptionError(
            f"Encrypted data must be a string, got {type(encrypted_str).__name__}"
        )

    try:
        # AWS KMS ciphertext detection
        if encrypted_str.startswith(_AWS_KMS_PREFIX):
            decrypted_bytes = _kms_decrypt(encrypted_str)
            json_str = decrypted_bytes.decode("utf-8")
            data = json.loads(json_str)
            if not isinstance(data, dict):
                raise EncryptionError(
                    f"Decrypted data must be a dict, got {type(data).__name__}",
                )
            return data

        # Legacy Vault Transit ciphertext — use Fernet fallback.
        # Vault Transit is no longer available (Phase 211), but
        # existing vault:v1:* rows can't be decrypted without Vault.
        # These rows must be re-encrypted via a data migration.
        if encrypted_str.startswith(_VAULT_TRANSIT_PREFIX):
            raise EncryptionError(
                "Legacy Vault Transit ciphertext detected "
                f"({encrypted_str[:20]}...). Vault is no longer "
                "available. Run the re-encryption migration to "
                "convert vault:v1:* rows to Fernet or KMS."
            )

        # Fernet path (existing + backward compat)
        encrypted_bytes = base64.urlsafe_b64decode(
            encrypted_str.encode("utf-8"),
        )
        fernet = _get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        json_str = decrypted_bytes.decode("utf-8")
        data = json.loads(json_str)

        if not isinstance(data, dict):
            raise EncryptionError(
                f"Decrypted data must be a dict, got {type(data).__name__}",
            )
        return data
    except binascii.Error as e:
        raise EncryptionError(
            f"Failed to decode base64: {e!s}",
        ) from e
    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(
            f"Failed to decrypt data: {e!s}",
        ) from e
