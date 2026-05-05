"""
Signed state token helpers for SSO callbacks.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid

from django.conf import settings
from django.core.cache import cache


_STATE_TTL_SECONDS = 300
_STATE_CACHE_PREFIX = "consume:state:"
_STATE_USED_SUFFIX = ":used"


class SSOStateError(ValueError):
    """Raised when SSO state is missing, invalid, expired, or reused."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _state_sig(
    tenant_id: str,
    nonce: str,
    issued_ts: str,
    ip_class: str,
) -> str:
    message = f"{tenant_id}|{nonce}|{issued_ts}|{ip_class}".encode("utf-8")
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def issue_state(tenant_id: str, ip_class: str) -> str:
    """
    Issue a short-lived signed state payload.
    """
    nonce = uuid.uuid4().hex
    issued_ts = str(int(time.time()))
    sig = _state_sig(tenant_id, nonce, issued_ts, ip_class)
    payload = (
        f"{tenant_id}|{nonce}|{issued_ts}|{ip_class}|{sig}"
    ).encode("utf-8")
    state = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
    cache.set(
        f"{_STATE_CACHE_PREFIX}{nonce}",
        "issued",
        timeout=_STATE_TTL_SECONDS,
    )
    return state


def consume_state(state: str | None, ip_class: str) -> str:
    """
    Consume signed state and return tenant_id.
    """
    if not state:
        raise SSOStateError("SSO_STATE_MISSING")

    try:
        padded = state + "=" * (-len(state) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        tenant_id, nonce, issued_ts, token_ip_class, sig = raw.split("|", 4)
    except Exception as exc:  # pragma: no cover - defensive parse guard
        raise SSOStateError("SSO_STATE_INVALID") from exc

    expected_sig = _state_sig(tenant_id, nonce, issued_ts, token_ip_class)
    if not hmac.compare_digest(sig, expected_sig):
        raise SSOStateError("SSO_STATE_INVALID")

    try:
        issued_ts_int = int(issued_ts)
    except ValueError as exc:
        raise SSOStateError("SSO_STATE_INVALID") from exc

    now_ts = int(time.time())
    if now_ts - issued_ts_int > _STATE_TTL_SECONDS:
        raise SSOStateError("SSO_STATE_EXPIRED")

    if token_ip_class != ip_class:
        raise SSOStateError("SSO_STATE_IP_MISMATCH")

    cache_key = f"{_STATE_CACHE_PREFIX}{nonce}"
    used_key = f"{cache_key}{_STATE_USED_SUFFIX}"
    if not cache.add(used_key, "1", timeout=_STATE_TTL_SECONDS):
        raise SSOStateError("SSO_STATE_REUSED")
    if cache.get(cache_key) is None:
        raise SSOStateError("SSO_STATE_REUSED")
    cache.delete(cache_key)

    return tenant_id
