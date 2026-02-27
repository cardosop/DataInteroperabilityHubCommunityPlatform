"""
Encryption utilities for marketplace connection configurations.

Provides secure encryption/decryption of sensitive JSONField data using Fernet
symmetric encryption. The encryption key is stored in Django settings.
"""
import base64
import binascii
import hashlib
import json
from typing import Any, Dict, Optional

import structlog
from django.conf import settings
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = structlog.get_logger(__name__)


class EncryptionError(Exception):
    """Exception raised when encryption/decryption fails."""
    pass


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
    encryption_key_str = getattr(settings, 'ENCRYPTION_KEY', None)

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
    except Exception as e:
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
        backend=default_backend()
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
        raise EncryptionError(f"Failed to initialize Fernet cipher: {str(e)}") from e


def encrypt_json_field(data: Dict[str, Any]) -> str:
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
        # Serialize to JSON
        json_str = json.dumps(data, sort_keys=True)
        json_bytes = json_str.encode('utf-8')

        # Encrypt
        fernet = _get_fernet()
        encrypted_bytes = fernet.encrypt(json_bytes)

        # Base64 encode for safe storage in JSONField
        encrypted_str = base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')

        return encrypted_str
    except (TypeError, ValueError) as e:
        # JSONEncodeError doesn't exist - json.dumps raises TypeError or ValueError
        raise EncryptionError(f"Failed to serialize data to JSON: {str(e)}") from e
    except Exception as e:
        raise EncryptionError(f"Failed to encrypt data: {str(e)}") from e


def decrypt_json_field(encrypted_str: str) -> Dict[str, Any]:
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
        raise EncryptionError(f"Encrypted data must be a string, got {type(encrypted_str).__name__}")

    try:
        # Base64 decode
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_str.encode('utf-8'))

        # Decrypt
        fernet = _get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted_bytes)

        # Deserialize from JSON
        json_str = decrypted_bytes.decode('utf-8')
        data = json.loads(json_str)

        if not isinstance(data, dict):
            raise EncryptionError(f"Decrypted data must be a dictionary, got {type(data).__name__}")

        return data
    except binascii.Error as e:
        raise EncryptionError(f"Failed to decode base64: {str(e)}") from e
    except Exception as e:
        raise EncryptionError(f"Failed to decrypt data: {str(e)}") from e

