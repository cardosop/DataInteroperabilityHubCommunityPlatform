"""
Shared authentication utilities.
"""

import hashlib


def sha256_hex(value: str) -> str:
    """Return the SHA-256 hex digest of *value*.

    Used wherever a sensitive token (invitation, password-reset, refresh)
    must be stored in the database as a hash rather than in plaintext (11.3).
    """
    return hashlib.sha256(value.encode()).hexdigest()
