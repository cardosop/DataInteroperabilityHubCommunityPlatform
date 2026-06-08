"""
Phase 216.2 — shared API helpers for use-case and security tests.

Thin wrapper around requests that uses persona credentials to hit the
live staging API. Every helper returns the raw response so tests can
assert on status codes, headers, and bodies.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import requests

from tests._persona_provisioning import PersonaCredentials


def _default_api_base_url() -> str:
    """Return the default API base URL, honoring API_TEST_PORT for host-based tests."""
    port = os.environ.get("API_TEST_PORT", "8000")
    return f"http://localhost:{port}/api/v1"


def api_base_url() -> str:
    return os.environ.get(
        "MESHANT_API_URL",
        os.environ.get("ODH_BASE_URL", _default_api_base_url()),
    )


def api_get(
    path: str,
    creds: PersonaCredentials,
    *,
    params: Optional[dict] = None,
    timeout: int = 15,
) -> requests.Response:
    """Authenticated GET against the staging API."""
    url = f"{api_base_url()}{path}"
    return requests.get(
        url,
        headers={"Authorization": f"Bearer {creds.api_key}"},
        params=params,
        timeout=timeout,
    )


def api_post(
    path: str,
    creds: PersonaCredentials,
    *,
    json: Optional[dict] = None,
    timeout: int = 15,
) -> requests.Response:
    """Authenticated POST against the staging API."""
    url = f"{api_base_url()}{path}"
    return requests.post(
        url,
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "Content-Type": "application/json",
        },
        json=json,
        timeout=timeout,
    )


def api_put(
    path: str,
    creds: PersonaCredentials,
    *,
    json: Optional[dict] = None,
    timeout: int = 15,
) -> requests.Response:
    url = f"{api_base_url()}{path}"
    return requests.put(
        url,
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "Content-Type": "application/json",
        },
        json=json,
        timeout=timeout,
    )


def api_delete(
    path: str,
    creds: PersonaCredentials,
    *,
    timeout: int = 15,
) -> requests.Response:
    url = f"{api_base_url()}{path}"
    return requests.delete(
        url,
        headers={"Authorization": f"Bearer {creds.api_key}"},
        timeout=timeout,
    )


def api_login(email: str, password: str, timeout: int = 15) -> requests.Response:
    """Unauthenticated login with retry on transient errors.

    The staging backend enforces per-IP login rate limits (10
    attempts/minute).  When running many tests sequentially, the
    limit is easily hit.  Retry with exponential backoff on:

    - 429 (rate-limit): respects the Retry-After header if present,
      else exponential backoff up to 60s.
    - 5xx (infrastructure): Redis, DB, or other backend failures.
    - Connection errors (DNS, network, timeout).

    Uses up to 5 attempts so transient infrastructure blips (e.g.
    Redis DNS resolution failures inside the Docker stack) don't
    cause the entire test suite to fail.

    Non-transient errors (4xx auth failures other than 429) are
    returned immediately so callers can inspect and self-heal.
    """
    url = f"{api_base_url()}/auth/login/"
    payload = {"email": email, "password": password}

    max_attempts = 5
    last_resp: Optional[requests.Response] = None

    for attempt in range(max_attempts):
        # ---- connection-level errors: DNS, network, timeout ----
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout):
            wait = min(2 ** attempt, 30)
            if attempt < max_attempts - 1:
                time.sleep(wait)
                continue
            raise  # Final attempt exhausted — let caller handle

        # ---- 429 rate-limit ----
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                wait = int(retry_after)
            else:
                wait = min(2 ** (attempt + 2), 60)
            time.sleep(wait)
            last_resp = resp
            continue

        if resp.status_code == 200:
            return resp

        # ---- 5xx infrastructure errors: Redis, DB, etc. ----
        if resp.status_code >= 500:
            wait = min(2 ** attempt, 30)
            if attempt < max_attempts - 1:
                time.sleep(wait)
                last_resp = resp
                continue
            # Final attempt exhausted — return last 5xx for caller to handle
            return resp

        # Non-transient error (4xx auth failures) — return immediately
        return resp

    # All retries exhausted — return last response
    if last_resp is not None:
        return last_resp
    return resp  # Should not be reached, but safe fallback


def api_unauthenticated_get(path: str, timeout: int = 15) -> requests.Response:
    """GET without any auth header."""
    return requests.get(f"{api_base_url()}{path}", timeout=timeout)
