"""
Webhook Secret Encryption

Primary: AWS KMS (Phase 211: Vault → AWS migration)
Fallback: Fernet symmetric encryption via ENCRYPTION_KEY

Ciphertext format:
- ``aws-kms:...``   → AWS KMS (new, Phase 211+)
- ``vault:v1:...``  → Legacy Vault Transit (no longer decryptable)
- ``v1:<fernet>``   → Fernet (Phase 11.4)
- plain text        → legacy pre-migration record
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

_PREFIX = "v1:"
_VAULT_PREFIX = "vault:"
_AWS_KMS_PREFIX = "aws-kms:"

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

    Tries AWS KMS first, falls back to Fernet.
    Idempotent: already-encrypted values returned unchanged.
    """
    if (plaintext.startswith(_PREFIX)
            or plaintext.startswith(_VAULT_PREFIX)
            or plaintext.startswith(_AWS_KMS_PREFIX)):
        return plaintext

    # Try AWS KMS
    from hub.apps.integrations.encryption import (
        _is_kms_available,
        _kms_encrypt,
    )
    if _is_kms_available():
        try:
            ciphertext = _kms_encrypt(
                plaintext.encode("utf-8"),
            )
            return ciphertext  # "aws-kms:..."
        except Exception as e:
            logger.warning(
                "webhook_kms_encrypt_fallback: %s", e,
            )

    # Fernet fallback
    ciphertext = _get_fernet().encrypt(
        plaintext.encode(),
    ).decode()
    return _PREFIX + ciphertext


def decrypt_secret(value: str) -> str:
    """Decrypt a webhook secret ciphertext.

    Routes by prefix:
    - aws-kms: → AWS KMS
    - vault:   → Legacy (raise error — Vault no longer available)
    - v1:      → Fernet
    - else     → legacy plaintext (pre-migration)
    """
    # AWS KMS path
    if value.startswith(_AWS_KMS_PREFIX):
        from hub.apps.integrations.encryption import (
            _kms_decrypt,
        )
        try:
            return _kms_decrypt(value).decode("utf-8")
        except Exception as exc:
            raise ValueError(
                "Failed to decrypt webhook secret via AWS KMS "
                "– check IAM permissions and key availability",
            ) from exc

    # Legacy Vault Transit — no longer decryptable
    if value.startswith(_VAULT_PREFIX):
        raise ValueError(
            "Legacy Vault Transit webhook secret detected. "
            "Vault is no longer available (Phase 211). "
            "Run the re-encryption migration."
        )

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
