import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.16 — Security: secret redaction.

Verifies that error responses and API output do NOT leak sensitive
values (access tokens, passwords, refresh tokens, Stripe keys, etc.)
in the response body or headers.
"""

import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url

SENSITIVE_PATTERNS = [
    "TestPass123",  # seeded E2E persona password
    "sk_test_",  # Stripe test key prefix
    "whsec_",  # Stripe webhook secret prefix
]


def _assert_pattern_not_in_headers(resp: requests.Response, pattern: str) -> None:
    """Assert *pattern* does not appear in any response header value."""
    pattern_lower = pattern.lower()
    for name, value in resp.headers.items():
        assert pattern_lower not in str(value).lower(), (
            f"Response header {name!r} contains sensitive pattern {pattern!r}"
        )


def test_401_error_body_does_not_contain_token():
    """A 401 response must not echo back the submitted token."""
    fake_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.secret-payload.signature"
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={"Authorization": f"Bearer {fake_token}"},
        timeout=15,
    )
    assert resp.status_code == 401

    body = resp.text
    assert "secret-payload" not in body, "401 response body contains the submitted token payload"
    # Also check headers for the token payload
    _assert_pattern_not_in_headers(resp, "secret-payload")


def test_login_error_does_not_echo_password():
    """Failed login must not echo the submitted password, in body or headers."""
    password = "SuperSecretPassword123!"
    resp = requests.post(
        f"{api_base_url()}/auth/login/",
        json={"email": "nonexistent@test.com", "password": password},
        timeout=15,
    )

    # Must be a client error, not a successful login.
    # 429 (rate-limit) is valid — the auth rate limiter may throttle.
    assert resp.status_code in (400, 401, 403, 422, 429), (
        f"Login with bad credentials returned {resp.status_code}, expected 4xx"
    )

    body = resp.text
    assert password not in body, "Login error response body contains the submitted password"
    _assert_pattern_not_in_headers(resp, password)


def test_validation_error_does_not_leak_api_key():
    """Validation errors must not include the access token in body or headers."""
    creds = provision_persona("data_engineer")

    # Trigger a validation error by sending empty JSON
    resp = requests.post(
        f"{api_base_url()}/assets/",
        headers={"Authorization": f"Bearer {creds.api_key}"},
        json={},  # Missing required fields
        timeout=15,
    )

    # Must be a client error, not a success
    assert resp.status_code in (400, 422), (
        f"Validation error request returned {resp.status_code}, expected 400/422"
    )

    body = resp.text
    # The access token must not appear in the error response
    if creds.api_key and len(creds.api_key) > 20:
        assert creds.api_key not in body, "Error response body contains the access token"
        _assert_pattern_not_in_headers(resp, creds.api_key)


def test_error_responses_do_not_contain_sensitive_patterns():
    """No error response body or header should contain known sensitive patterns."""
    endpoints = [
        ("/auth/login/", {"email": "", "password": ""}),
        ("/auth/register/", {"email": "bad", "password": "x"}),
    ]
    for path, payload in endpoints:
        resp = requests.post(
            f"{api_base_url()}{path}",
            json=payload,
            timeout=15,
        )
        # Must be a client error, not silently succeeding.
        # 429 (rate-limit) is valid — the auth rate limiter may
        # throttle after repeated test requests.
        assert resp.status_code in (400, 401, 403, 422, 429), (
            f"{path} returned {resp.status_code} — expected a client error"
        )

        body = resp.text
        for pattern in SENSITIVE_PATTERNS:
            assert pattern not in body, (
                f"Response from {path} contains sensitive pattern {pattern!r}"
            )
            _assert_pattern_not_in_headers(resp, pattern)
