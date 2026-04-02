"""
Webhook Secret Encryption

Primary: Vault Transit (AES256-GCM96, auto-rotate 720h)
Fallback: Fernet symmetric encryption via ENCRYPTION_KEY

Ciphertext format:
- ``vault:v1:...`` → Vault Transit
- ``v1:<fernet-token>`` → Fernet (Phase 11.4)
- plain text → legacy pre-migration record
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

_PREFIX = "v1:"
_VAULT_PREFIX = "vault:"

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Build a Fernet instance derived from settings.ENCRYPTION_KEY."""
    from django.conf import settings
    raw = settings.ENCRYPTION_KEY
    derived = hashlib.sha256(raw.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a webhook secret.

    Tries Vault Transit first, falls back to Fernet.
    Idempotent: already-encrypted values returned unchanged.
    """
    if plaintext.startswith(_PREFIX) or plaintext.startswith(_VAULT_PREFIX):
        return plaintext

    # Try Vault Transit
    from hub.apps.integrations.encryption import (
        _is_vault_transit_available,
        _vault_transit_encrypt,
    )
    if _is_vault_transit_available():
        try:
            ciphertext = _vault_transit_encrypt(
                plaintext.encode("utf-8"),
            )
            return ciphertext  # "vault:v1:..."
        except Exception as e:
            logger.warning(
                "webhook_vault_transit_fallback: %s", e,
            )

    # Fernet fallback
    ciphertext = _get_fernet().encrypt(
        plaintext.encode(),
    ).decode()
    return _PREFIX + ciphertext


def decrypt_secret(value: str) -> str:
    """Decrypt a webhook secret ciphertext.

    Routes by prefix:
    - vault: → Vault Transit
    - v1: → Fernet
    - else → legacy plaintext (pre-migration)
    """
    # Vault Transit path
    if value.startswith(_VAULT_PREFIX):
        from hub.apps.integrations.encryption import (
            _vault_transit_decrypt,
        )
        try:
            return _vault_transit_decrypt(value).decode("utf-8")
        except Exception as exc:
            raise ValueError(
                "Failed to decrypt webhook secret via Vault Transit "
                "– check Vault connectivity and key availability",
            ) from exc

    # Fernet path
    if value.startswith(_PREFIX):
        try:
            return _get_fernet().decrypt(
                value[len(_PREFIX):].encode(),
            ).decode()
        except InvalidToken as exc:
            raise ValueError(
                "Failed to decrypt webhook secret "
                "– ENCRYPTION_KEY mismatch?",
            ) from exc

    # Legacy plaintext
    return value
