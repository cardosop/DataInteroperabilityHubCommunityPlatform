"""
Smoke test — cookie auth mode headers.

Validates that login sets secure httpOnly cookies for staging/prod hosts.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import pytest
import requests

COOKIE_SECURITY_PATTERN = re.compile(
    r"Set-Cookie:.*HttpOnly.*Secure.*SameSite=Strict.*Domain=\.meshant\.com",
    re.IGNORECASE,
)


def _set_cookie_headers(response: requests.Response) -> list[str]:
    raw_headers = getattr(getattr(response, "raw", None), "headers", None)
    if raw_headers is not None and hasattr(raw_headers, "get_all"):
        values = raw_headers.get_all("Set-Cookie")
        if values:
            return [f"Set-Cookie: {v}" for v in values]
    header = response.headers.get("Set-Cookie", "")
    return [f"Set-Cookie: {header}"] if header else []


def test_login_sets_secure_httponly_domain_cookie(
    base_url: str,
    api_session: requests.Session,
    admin_credentials: dict,
    timeout: int,
) -> None:
    """
    Equivalent to:
      curl -i ... | grep \
        "Set-Cookie:.*HttpOnly.*Secure.*SameSite=Strict.*Domain=\\.meshant\\.com"
    """
    host = (urlparse(base_url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1"}:
        pytest.skip(  # noqa: skip-in-body — runtime service dependency
            "Cookie domain smoke check targets staging/production hostnames",
        )

    response = api_session.post(
        f"{base_url}/api/v1/auth/login/",
        json=admin_credentials,
        timeout=timeout,
    )
    assert response.status_code == 200, (
        f"Login returned {response.status_code}: {response.text[:500]}"
    )

    cookie_lines = _set_cookie_headers(response)
    assert cookie_lines, "No Set-Cookie headers returned from login"
    assert any(COOKIE_SECURITY_PATTERN.search(line) for line in cookie_lines), (
        f"Expected secure strict domain cookie not found. Set-Cookie lines: {cookie_lines}"
    )
