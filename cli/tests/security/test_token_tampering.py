import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.14 — Security: token tampering.

Verifies that mutated/fabricated JWTs are rejected with 401.
"""

import base64
import json

import requests
from tests.use_cases._api_helpers import api_base_url


def _fabricate_jwt(payload_overrides: dict | None = None) -> str:
    """Build a syntactically valid but unsigned JWT."""
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload = {
        "sub": "fake-user-id",
        "exp": 9999999999,
        "iat": 1000000000,
        "email": "attacker@evil.com",
    }
    if payload_overrides:
        payload.update(payload_overrides)
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fakesignature").rstrip(b"=").decode()
    return f"{header}.{payload_b64}.{sig}"


def test_fabricated_jwt_returns_401():
    """A completely fabricated JWT must be rejected."""
    token = _fabricate_jwt()
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert resp.status_code == 401, f"Fabricated JWT returned {resp.status_code}, expected 401"


def test_tampered_payload_returns_401():
    """JWT with modified payload (role escalation) must be rejected."""
    token = _fabricate_jwt({"roles": ["PLATFORM_ADMIN"], "is_staff": True})
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert resp.status_code == 401


def test_empty_signature_returns_401():
    """JWT with empty signature segment must be rejected."""
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload = (
        base64.urlsafe_b64encode(json.dumps({"sub": "admin", "exp": 9999999999}).encode())
        .rstrip(b"=")
        .decode()
    )
    token = f"{header}.{payload}."
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert resp.status_code == 401


def test_alg_none_with_signature_returns_401():
    """JWT with alg=none but a non-empty signature must be rejected.

    Some vulnerable JWT libraries accept ``alg: none`` even when a
    signature is present, bypassing verification entirely.
    """
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload = (
        base64.urlsafe_b64encode(json.dumps({"sub": "admin", "exp": 9999999999}).encode())
        .rstrip(b"=")
        .decode()
    )
    # Non-empty signature with alg=none — must still be rejected
    sig = base64.urlsafe_b64encode(b"malicious-sig").rstrip(b"=").decode()
    token = f"{header}.{payload}.{sig}"
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert resp.status_code == 401, (
        f"alg=none JWT with signature returned {resp.status_code}, expected 401"
    )


def test_truncated_token_returns_401():
    """A truncated JWT (missing segments) must be rejected."""
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9"},
        timeout=15,
    )
    assert resp.status_code == 401, f"Truncated JWT returned {resp.status_code}, expected 401"


def test_real_token_payload_tampering_returns_401():
    """A real token whose payload has been modified but signature kept
    unchanged must be rejected (signature no longer matches payload)."""
    from tests._persona_provisioning import provision_persona

    creds = provision_persona("data_engineer")
    token = creds.api_key
    if not token or "." not in token or len(token) < 50:
        pytest.skip("No valid JWT token available for tampering test")

    parts = token.split(".")
    if len(parts) != 3:
        pytest.skip(f"Token has {len(parts)} segments, expected 3")

    header_b64, payload_b64, sig_b64 = parts

    # Decode the real payload, modify a field, re-encode
    try:
        # Add padding for base64 decoding
        payload_json = base64.urlsafe_b64decode(
            payload_b64 + "=" * (4 - len(payload_b64) % 4)
        ).decode()
        payload = json.loads(payload_json)
    except Exception:
        pytest.skip("Could not decode real token payload")

    # Escalate privileges in the payload
    payload["roles"] = ["PLATFORM_ADMIN"]
    payload["is_platform_admin"] = True
    new_payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    # Reassemble with the ORIGINAL (now-invalid) signature
    tampered = f"{header_b64}.{new_payload_b64}.{sig_b64}"

    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": f"Bearer {tampered}"},
        timeout=15,
    )
    assert resp.status_code == 401, (
        f"Real-token payload tampering returned {resp.status_code}, expected 401"
    )
