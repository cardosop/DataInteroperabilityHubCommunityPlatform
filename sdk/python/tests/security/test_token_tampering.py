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
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload = {
        "sub": "fake-user-id",
        "exp": 9999999999,
        "iat": 1000000000,
        "email": "attacker@evil.com",
    }
    if payload_overrides:
        payload.update(payload_overrides)
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
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
    assert resp.status_code == 401, (
        f"Fabricated JWT returned {resp.status_code}, expected 401"
    )


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
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "admin", "exp": 9999999999}).encode()
    ).rstrip(b"=").decode()
    token = f"{header}.{payload}."
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert resp.status_code == 401


def test_truncated_token_returns_401():
    """A truncated JWT (missing segments) must be rejected."""
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9"},
        timeout=15,
    )
    assert resp.status_code == 401
