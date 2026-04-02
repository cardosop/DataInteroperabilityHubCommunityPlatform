"""
Email verification tokens (Phase 204).

Plaintext token is URL-safe base64 of ``user_id|issued_ts|nonce|hmac_hex`` where the HMAC is
``HMAC-SHA256(SECRET_KEY, UTF-8(email + user_id + issued_ts + nonce))``.

The database stores SHA-256(plaintext) hex digest for lookup and invalidation on resend; expiry is
72 hours from ``email_verification_sent_at``. A random ``nonce`` ensures distinct hashes when
multiple tokens are issued in the same wall-clock second.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from hub.apps.auth.utils import sha256_hex


def _verification_hmac_hex(email: str, user_id: str, issued_ts: int, nonce: str) -> str:
    # Task: HMAC-SHA256(SECRET_KEY, email+user_id+...) — issued_ts + nonce keep resends unique.
    msg = f"{email}{user_id}{issued_ts}{nonce}".encode("utf-8")
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def issue_verification_token_plaintext(user) -> str:
    """
    Persist a new verification token for *user* and return the plaintext value for the email link.

    Updates ``email_verification_token`` (hash) and ``email_verification_sent_at``.
    """
    issued = int(timezone.now().timestamp())
    uid = str(user.id)
    nonce = secrets.token_hex(16)
    sig = _verification_hmac_hex(user.email, uid, issued, nonce)
    inner = f"{uid}|{issued}|{nonce}|{sig}"
    plaintext = base64.urlsafe_b64encode(inner.encode("utf-8")).decode("ascii").rstrip("=")

    user.email_verification_token = sha256_hex(plaintext)
    user.email_verification_sent_at = timezone.now()
    user.save(
        update_fields=[
            "email_verification_token",
            "email_verification_sent_at",
            "updated_at",
        ]
    )
    return plaintext


def plaintext_valid_for_user(user, plaintext: str) -> bool:
    """
    Return True if *plaintext* decodes, matches *user*'s id, HMAC verifies, and sent_at is within 72h.

    Call with a row already locked (e.g. ``select_for_update``) when handling verify-email to avoid
    races with resend replacing ``email_verification_token``.
    """
    if not plaintext or not isinstance(plaintext, str):
        return False

    try:
        pad = "=" * ((4 - len(plaintext) % 4) % 4)
        raw = base64.urlsafe_b64decode(plaintext + pad)
        parts = raw.decode("utf-8").split("|")
        if len(parts) != 4:
            return False
        uid, issued_s, nonce, sig = parts
        issued = int(issued_s)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return False

    if str(user.id) != uid:
        return False

    expected = _verification_hmac_hex(user.email, uid, issued, nonce)
    if not hmac.compare_digest(expected, sig):
        return False

    if user.email_verification_sent_at is None:
        return False
    if timezone.now() > user.email_verification_sent_at + timedelta(hours=72):
        return False

    return True


def verify_plaintext_token(plaintext: str):
    """
    Return the ``User`` if *plaintext* is valid (signature, hash match, not expired), else ``None``.
    """
    from hub.apps.users.models import User

    if not plaintext or not isinstance(plaintext, str):
        return None

    token_hash = sha256_hex(plaintext)
    try:
        user = User.objects.get(email_verification_token=token_hash)
    except (User.DoesNotExist, User.MultipleObjectsReturned):
        return None

    if not plaintext_valid_for_user(user, plaintext):
        return None

    return user


def mark_user_email_verified(user) -> None:
    user.email_verified = True
    user.email_verified_at = timezone.now()
    user.email_verification_token = None
    user.email_verification_sent_at = None
    user.save(
        update_fields=[
            "email_verified",
            "email_verified_at",
            "email_verification_token",
            "email_verification_sent_at",
            "updated_at",
        ]
    )
