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


def _retry_on_throttle(
    make_request,
    *,
    max_attempts: int = 4,
    timeout: int = 15,
) -> requests.Response:
    """Execute *make_request()*, retrying with backoff on 429 / 5xx.

    Rate-limit responses (429) are retried up to *max_attempts* times.
    The ``Retry-After`` header is respected when present; otherwise
    exponential backoff starting at 2 s is used.

    5xx infrastructure errors are retried with shorter backoff (max 30 s)
    so transient Redis/DB blips don't fail the suite.

    Non-retryable 4xx errors are returned immediately.
    """
    last_resp: Optional[requests.Response] = None

    for attempt in range(max_attempts):
        try:
            resp = make_request(timeout=timeout)
        except (requests.ConnectionError, requests.Timeout):
            wait = min(2**attempt, 30)
            if attempt < max_attempts - 1:
                time.sleep(wait)
                continue
            raise

        # ── 429 rate-limit ─────────────────────────────────────────
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    wait = int(retry_after)
                except (ValueError, TypeError):
                    wait = min(2 ** (attempt + 2), 60)
            else:
                wait = min(2 ** (attempt + 2), 60)
            time.sleep(wait)
            last_resp = resp
            continue

        # ── 5xx infrastructure error ───────────────────────────────
        if resp.status_code >= 500:
            wait = min(2**attempt, 30)
            if attempt < max_attempts - 1:
                time.sleep(wait)
                last_resp = resp
                continue
            return resp

        # Success or non-retryable client error — return immediately
        return resp

    # All retries exhausted
    if last_resp is not None:
        return last_resp
    return resp  # type: ignore[return-value]


def api_get(
    path: str,
    creds: PersonaCredentials,
    *,
    params: Optional[dict] = None,
    timeout: int = 15,
    retry_on_throttle: bool = True,
) -> requests.Response:
    """Authenticated GET against the staging API.

    When *retry_on_throttle* is True (default), 429 and 5xx responses
    are retried with exponential backoff.
    """
    url = f"{api_base_url()}{path}"

    def _do(timeout: int = timeout) -> requests.Response:
        return requests.get(
            url,
            headers={"Authorization": f"Bearer {creds.api_key}"},
            params=params,
            timeout=timeout,
        )

    if retry_on_throttle:
        return _retry_on_throttle(_do, timeout=timeout)
    return _do()


def api_post(
    path: str,
    creds: PersonaCredentials,
    *,
    json: Optional[dict] = None,
    timeout: int = 15,
    retry_on_throttle: bool = True,
) -> requests.Response:
    """Authenticated POST against the staging API.

    When *retry_on_throttle* is True (default), 429 and 5xx responses
    are retried with exponential backoff.
    """
    url = f"{api_base_url()}{path}"

    def _do(timeout: int = timeout) -> requests.Response:
        return requests.post(
            url,
            headers={
                "Authorization": f"Bearer {creds.api_key}",
                "Content-Type": "application/json",
            },
            json=json,
            timeout=timeout,
        )

    if retry_on_throttle:
        return _retry_on_throttle(_do, timeout=timeout)
    return _do()


def api_put(
    path: str,
    creds: PersonaCredentials,
    *,
    json: Optional[dict] = None,
    timeout: int = 15,
    retry_on_throttle: bool = True,
) -> requests.Response:
    """Authenticated PUT against the staging API.

    When *retry_on_throttle* is True (default), 429 and 5xx responses
    are retried with exponential backoff.
    """
    url = f"{api_base_url()}{path}"

    def _do(timeout: int = timeout) -> requests.Response:
        return requests.put(
            url,
            headers={
                "Authorization": f"Bearer {creds.api_key}",
                "Content-Type": "application/json",
            },
            json=json,
            timeout=timeout,
        )

    if retry_on_throttle:
        return _retry_on_throttle(_do, timeout=timeout)
    return _do()


def api_delete(
    path: str,
    creds: PersonaCredentials,
    *,
    timeout: int = 15,
    retry_on_throttle: bool = True,
) -> requests.Response:
    """Authenticated DELETE against the staging API.

    When *retry_on_throttle* is True (default), 429 and 5xx responses
    are retried with exponential backoff.
    """
    url = f"{api_base_url()}{path}"

    def _do(timeout: int = timeout) -> requests.Response:
        return requests.delete(
            url,
            headers={"Authorization": f"Bearer {creds.api_key}"},
            timeout=timeout,
        )

    if retry_on_throttle:
        return _retry_on_throttle(_do, timeout=timeout)
    return _do()


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
            wait = min(2**attempt, 30)
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
            wait = min(2**attempt, 30)
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


def api_unauthenticated_get(
    path: str, *, timeout: int = 15, retry_on_throttle: bool = True
) -> requests.Response:
    """GET without any auth header.

    When *retry_on_throttle* is True (default), 429 and 5xx responses
    are retried with exponential backoff.
    """
    url = f"{api_base_url()}{path}"

    def _do(timeout: int = timeout) -> requests.Response:
        return requests.get(url, timeout=timeout)

    if retry_on_throttle:
        return _retry_on_throttle(_do, timeout=timeout)
    return _do()


def api_unauthenticated_post(
    path: str,
    *,
    json: Optional[dict] = None,
    timeout: int = 15,
    retry_on_throttle: bool = True,
) -> requests.Response:
    """POST without any auth header (e.g. login, accept-invitation).

    When *retry_on_throttle* is True (default), 429 and 5xx responses
    are retried with exponential backoff.
    """
    url = f"{api_base_url()}{path}"

    def _do(timeout: int = timeout) -> requests.Response:
        return requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=json,
            timeout=timeout,
        )

    if retry_on_throttle:
        return _retry_on_throttle(_do, timeout=timeout)
    return _do()
