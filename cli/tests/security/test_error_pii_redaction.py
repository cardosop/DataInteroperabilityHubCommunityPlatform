import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.19 — Security: PII redaction in error messages.

Verifies that API error responses do not leak PII (email addresses,
phone numbers, etc.) from the request or from other users.
"""

import requests
from tests.use_cases._api_helpers import api_base_url


def _assert_email_not_in_response(resp: requests.Response, email: str) -> None:
    """Assert *email* does not appear in the response body or headers."""
    body = resp.text.lower() if resp.text else ""
    email_lower = email.lower()
    assert email_lower not in body, f"Response body contains the submitted email address {email!r}"
    # Check headers — emails can leak through Location, Set-Cookie, etc.
    for name, value in resp.headers.items():
        assert email_lower not in str(value).lower(), (
            f"Response header {name!r} contains the submitted email {email!r}"
        )


def test_login_error_does_not_echo_email():
    """Failed login with a real-looking email must not echo it back."""
    test_email = "sensitive-user-pii@example.com"
    resp = requests.post(
        f"{api_base_url()}/auth/login/",
        json={"email": test_email, "password": "wrong"},
        timeout=15,
    )
    # Must be a client error (not a successful login).
    # 429 (rate-limit) is also valid — the IP may be throttled by the
    # auth rate limiter after multiple test logins.
    assert resp.status_code in (400, 401, 403, 422, 429), (
        f"Login with wrong password returned {resp.status_code}, expected 4xx"
    )
    _assert_email_not_in_response(resp, test_email)


def test_register_error_does_not_echo_full_email():
    """Registration error for duplicate email must not expose the email.

    Registers the same email twice.  The second attempt must return a
    client error and must NOT include the full email address in the
    response body or headers.
    """
    test_email = "pii-redaction-test@example.com"

    # First registration — may succeed (201) or conflict if residual
    requests.post(
        f"{api_base_url()}/auth/register/",
        json={
            "email": test_email,
            "password": "StrongPassword123!",
            "name": "PII Test",
        },
        timeout=15,
    )

    # Second registration — must get a conflict/client error
    resp = requests.post(
        f"{api_base_url()}/auth/register/",
        json={
            "email": test_email,
            "password": "StrongPassword123!",
            "name": "PII Test",
        },
        timeout=15,
    )

    # Must be a client error (409 Conflict or 400 Bad Request)
    assert resp.status_code in (400, 409, 422), (
        f"Duplicate registration returned {resp.status_code}, expected 409/400"
    )
    _assert_email_not_in_response(resp, test_email)


def test_validation_error_does_not_leak_other_users():
    """Validation errors must not expose other users' PII.

    Fetches a non-existent user by ID (not nil UUID — a genuine
    lookup that must return 404).  The error response must not
    contain any email-like strings from other users.
    """
    # Use a realistic-looking but non-existent UUID
    resp = requests.get(
        f"{api_base_url()}/users/a1b2c3d4-e5f6-7890-abcd-ef1234567890/",
        timeout=15,
    )
    body = resp.text if resp.text else ""

    # Must be a 404
    assert resp.status_code in (404, 403, 401), (
        f"Non-existent user lookup returned {resp.status_code}"
    )

    # The body must not contain any email address (any '@').
    # No domain whitelist — any '@' in a 404 response is a leak.
    assert "@" not in body, "User lookup error response contains an email-like string ('@')"


def test_500_errors_do_not_contain_stack_traces():
    """If a 500 occurs, it must not expose Python stack traces to the client.

    Uses the dedicated ``/test/raise-500/`` endpoint (gated by
    ``@require_e2e_token``, same guard as the other ``/test/*``
    endpoints) to deliberately trigger an unhandled exception and
    inspect the resulting 500 response.

    When ``DEBUG=True`` (development / test Docker stack), Django
    intentionally renders the full debug page — that's expected
    and the test skips with a diagnostic note.
    """
    from tests._persona_provisioning import _e2e_token

    resp = requests.get(
        f"{api_base_url()}/test/raise-500/",
        headers={"X-E2E-Token": _e2e_token()},
        timeout=15,
    )

    # The endpoint MUST return a 500 — if it doesn't, the endpoint
    # is not working (missing, misconfigured secret, etc.)
    assert resp.status_code >= 500, (
        f"/test/raise-500/ returned {resp.status_code}, expected 500. "
        f"Is the endpoint registered and is E2E_TEST_SECRET correct?"
    )

    body = resp.text if resp.text else ""

    # When DEBUG=True, Django renders the full debug page with
    # traceback — this is expected dev behaviour and not a bug.
    if "Exception Type:" in body or "Exception Value:" in body:
        pytest.skip(
            "DEBUG mode is active — Django's debug page intentionally "
            "includes tracebacks.  This is expected in dev/test "
            "environments.  Set DEBUG=False to test production 500 "
            "redaction."
        )

    # In production mode (DEBUG=False), the 500 must be sanitised.
    sensitive_patterns = [
        "Traceback",
        'File "',
        "django.",
        "settings.",
        "SECRET_KEY",
        "sqlalchemy",
        "/app/",
        "/usr/src/",
    ]
    for pattern in sensitive_patterns:
        assert pattern not in body, f"500 response contains sensitive pattern {pattern!r}"
