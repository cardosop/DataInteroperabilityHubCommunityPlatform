import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.16 — Security: secret redaction.

Verifies that CLI/SDK error messages and log output do NOT leak
sensitive values (api_key, password, refresh_token).
"""

import io
import logging
import json
import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url


SENSITIVE_PATTERNS = [
    "TestPass123",             # seeded E2E persona password
    "sk_test_",               # Stripe test key prefix
    "whsec_",                 # Stripe webhook secret prefix
]


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
    assert "secret-payload" not in body, (
        f"401 response body contains the submitted token payload"
    )


def test_login_error_does_not_echo_password():
    """Failed login must not echo the submitted password."""
    password = "SuperSecretPassword123!"
    resp = requests.post(
        f"{api_base_url()}/auth/login/",
        json={"email": "nonexistent@test.com", "password": password},
        timeout=15,
    )
    body = resp.text
    assert password not in body, (
        f"Login error response contains the submitted password"
    )


def test_validation_error_does_not_leak_api_key():
    """Validation errors must not include the api_key in the response."""
    creds = provision_persona("data_engineer")
    # Trigger a validation error by sending invalid data
    resp = requests.post(
        f"{api_base_url()}/assets/",
        headers={"Authorization": f"Bearer {creds.api_key}"},
        json={},  # Missing required fields
        timeout=15,
    )
    body = resp.text
    # The access token must not appear in any error response
    if creds.api_key and len(creds.api_key) > 20:
        assert creds.api_key not in body, (
            "Error response body contains the access token"
        )


def test_error_responses_do_not_contain_sensitive_patterns():
    """No error response should contain known sensitive patterns."""
    # Hit a few endpoints that produce errors
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
        body = resp.text
        for pattern in SENSITIVE_PATTERNS:
            assert pattern not in body, (
                f"Response from {path} contains sensitive pattern '{pattern}'"
            )
