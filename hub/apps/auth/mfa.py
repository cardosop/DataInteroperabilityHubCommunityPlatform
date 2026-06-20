"""
285.8.1.1 — TOTP-based MFA for PLATFORM_ADMIN and TENANT_ADMIN roles.

Uses pyotp for RFC 6238 TOTP generation/verification. Recovery codes
are SHA-256 hashed and stored per-user. MFA is enforced at login
when the tenant has `mfa_required=True`.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

import pyotp
from django.conf import settings
from django.utils import timezone

# ── TOTP configuration ──────────────────────────────────────────────

TOTP_ISSUER = getattr(settings, "MFA_TOTP_ISSUER", "Meshant")
TOTP_DIGITS = 6
TOTP_INTERVAL = 30
RECOVERY_CODE_COUNT = 8
RECOVERY_CODE_LENGTH = 12


def generate_totp_secret() -> str:
    """Generate a new TOTP secret (Base32-encoded)."""
    return pyotp.random_base32()


def generate_totp_uri(user_email: str, secret: str) -> str:
    """Generate an otpauth:// URI for QR code provisioning."""
    totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
    return totp.provisioning_uri(name=user_email, issuer_name=TOTP_ISSUER)


def verify_totp(secret: str, token: str) -> bool:
    """Verify a TOTP token against the stored secret."""
    totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
    return totp.verify(token, valid_window=1)


def generate_recovery_codes() -> list[str]:
    """Generate a set of recovery codes. Return plaintext codes (store hashed)."""
    return [secrets.token_hex(RECOVERY_CODE_LENGTH // 2) for _ in range(RECOVERY_CODE_COUNT)]


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def verify_recovery_code(stored_hashes: list[str], code: str) -> tuple[bool, list[str]]:
    """
    Verify a recovery code against stored hashes.
    Returns (valid, remaining_hashes) — consumed code is removed.
    """
    code_hash = hash_recovery_code(code)
    if code_hash in stored_hashes:
        stored_hashes.remove(code_hash)
        return True, stored_hashes
    return False, stored_hashes


def is_mfa_required(user) -> bool:
    """
    285.8.1.1 — Check if MFA is required for this user.

    MFA is required when:
    1. The user's tenant has `mfa_required=True`, AND
    2. The user has a PLATFORM_ADMIN or TENANT_ADMIN role

    Returns False for users without admin roles.
    """
    if not user.is_authenticated:
        return False

    tenant = getattr(user, "tenant", None)
    if tenant is None:
        return False

    if not getattr(tenant, "mfa_required", False):
        return False

    # Check admin roles
    from hub.apps.users.models import UserRole

    admin_role_names = {"PLATFORM_ADMIN", "TENANT_ADMIN"}
    user_roles = UserRole.objects.filter(
        user=user,
        tenant=tenant,
        role__name__in=admin_role_names,
    ).exists()

    return user_roles


# ── MFA session management ──────────────────────────────────────────

MFA_SESSION_KEY = "mfa_verified_at"
MFA_SESSION_TTL_HOURS = 8


def mark_mfa_verified(request) -> None:
    """Mark the current session as MFA-verified."""
    request.session[MFA_SESSION_KEY] = timezone.now().isoformat()
    request.session.modified = True


def is_mfa_verified(request) -> bool:
    """Check if the current session has passed MFA within the TTL."""
    verified_at_str = request.session.get(MFA_SESSION_KEY)
    if not verified_at_str:
        return False
    try:
        verified_at = datetime.fromisoformat(verified_at_str)
        if timezone.is_naive(verified_at):
            verified_at = timezone.make_aware(verified_at)
        return (timezone.now() - verified_at) < timedelta(hours=MFA_SESSION_TTL_HOURS)
    except (ValueError, TypeError):
        return False
