"""HMAC-SHA256 proofs for consent records (rolling 3-key verification window)."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from typing import Any

from django.conf import settings


def _normalize_key_ring(raw: Mapping[str, Any] | None, tenant_id: str) -> list[bytes]:
    if not raw:
        return []
    tid = str(tenant_id)
    entry = raw.get(tid)
    if entry is None:
        return []
    if isinstance(entry, str):
        return [_decode_hex_key(entry)]
    if isinstance(entry, (list, tuple)):
        out: list[bytes] = []
        for item in entry[:3]:
            if isinstance(item, str):
                out.append(_decode_hex_key(item))
        return out
    if isinstance(entry, dict) and "keys" in entry:
        keys = entry["keys"]
        if isinstance(keys, (list, tuple)):
            return _normalize_key_ring({tid: list(keys)}, tenant_id)
    return []


def _decode_hex_key(s: str) -> bytes:
    key = s.strip()
    if key.startswith("hex:"):
        key = key[4:]
    b = bytes.fromhex(key)
    if len(b) < 16:
        raise ValueError("consent signing key must be at least 16 bytes (32 hex chars)")
    return b


def get_signing_key_ring_for_tenant(tenant_id: str) -> list[bytes]:
    """
    Return up to 3 signing keys for *tenant_id*, newest first.

    ``settings.CONSENT_SIGNING_KEYS_JSON`` shape:
      { "<tenant_uuid>": ["<hex>", ...] }  # max 3 entries, index 0 = current
    or { "<tenant_uuid>": { "keys": ["<hex>", ...] } }

    Falls back to ``"__default__"`` key entry when the tenant-specific
    entry is absent.
    """
    raw = getattr(settings, "CONSENT_SIGNING_KEYS_JSON", None)
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        return []
    keys = _normalize_key_ring(raw, str(tenant_id))
    if not keys:
        keys = _normalize_key_ring(raw, "__default__")
    return keys


def build_canonical_bytes(
    *, tenant_id: str, user_id: str, purpose_id: str, payload: Mapping[str, Any]
) -> bytes:
    """Deterministic canonical representation for HMAC input."""
    body = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "purpose_id": str(purpose_id),
        "payload": dict(sorted(payload.items())),
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def compute_proof_hmac(
    *, key: bytes, tenant_id: str, user_id: str, purpose_id: str, payload: Mapping[str, Any]
) -> str:
    msg = build_canonical_bytes(
        tenant_id=tenant_id, user_id=user_id, purpose_id=purpose_id, payload=payload
    )
    digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return digest


def verify_proof_hmac(
    *,
    proof_hex: str,
    tenant_id: str,
    user_id: str,
    purpose_id: str,
    payload: Mapping[str, Any],
    key_ring: Sequence[bytes],
) -> tuple[bool, int | None]:
    """
    Try each key in *key_ring* (newest first). Returns (ok, key_index) or (False, None) if tampered.
    """
    if not key_ring:
        return (False, None)
    msg = build_canonical_bytes(
        tenant_id=tenant_id, user_id=user_id, purpose_id=purpose_id, payload=payload
    )
    expected_len = 64
    if len(proof_hex) != expected_len:
        return (False, None)
    for idx, key in enumerate(key_ring):
        digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
        if hmac.compare_digest(digest, proof_hex):
            return (True, idx)
    return (False, None)
