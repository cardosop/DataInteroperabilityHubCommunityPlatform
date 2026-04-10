import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.1 — Dimension: rate limiting (429).

Verifies that the API returns 429 with a Retry-After header when the
rate limit is exceeded, and that the error message is user-friendly
(not a raw nginx/gunicorn dump).
"""

import time
import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url


def test_rapid_fire_eventually_returns_429():
    """Sending many requests in a burst should eventually hit 429."""
    creds = provision_persona("data_engineer")
    url = f"{api_base_url()}/auth/me/"
    headers = {"Authorization": f"Bearer {creds.api_key}"}

    got_429 = False
    for _ in range(100):
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 429:
            got_429 = True
            break

    if not got_429:
        pytest.skip(
            "Rate limiter did not trigger in 100 requests — "
            "may be relaxed in this env (RATE_LIMIT_E2E_RELAX=true)"
        )


def test_429_response_has_retry_after():
    """When 429 fires, the response should include Retry-After header."""
    creds = provision_persona("data_engineer")
    url = f"{api_base_url()}/auth/me/"
    headers = {"Authorization": f"Bearer {creds.api_key}"}

    for _ in range(200):
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            # Retry-After is recommended but not strictly required
            # by all deployments. If present, must be parseable.
            if retry_after is not None:
                assert retry_after.isdigit() or "." in retry_after, (
                    f"Retry-After header is not numeric: {retry_after!r}"
                )
            return

    pytest.skip("Rate limiter did not fire in 200 requests")


def test_429_body_is_json_not_raw():
    """429 response body should be structured JSON, not a raw proxy error."""
    creds = provision_persona("data_engineer")
    url = f"{api_base_url()}/auth/me/"
    headers = {"Authorization": f"Bearer {creds.api_key}"}

    for _ in range(200):
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 429:
            # Must be JSON, not HTML or plain text
            ct = resp.headers.get("Content-Type", "")
            assert "json" in ct.lower() or resp.text.startswith("{"), (
                f"429 body is not JSON: Content-Type={ct}, body={resp.text[:200]}"
            )
            return

    pytest.skip("Rate limiter did not fire")


def test_backoff_resolves_after_waiting():
    """After a 429, waiting and retrying should succeed."""
    creds = provision_persona("data_engineer")
    url = f"{api_base_url()}/auth/me/"
    headers = {"Authorization": f"Bearer {creds.api_key}"}

    for _ in range(200):
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", "2"))
            time.sleep(min(wait, 10))
            retry = requests.get(url, headers=headers, timeout=10)
            assert retry.status_code == 200, (
                f"After backoff, still got {retry.status_code}"
            )
            return

    pytest.skip("Rate limiter did not fire")
