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


def api_base_url() -> str:
    return os.environ.get(
        "MESHANT_API_URL",
        os.environ.get("ODH_BASE_URL", "http://localhost:8000/api/v1"),
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
    """Unauthenticated login with rate-limit retry.

    The staging backend enforces per-IP login rate limits (10
    attempts/minute).  When running many tests sequentially, the
    limit is easily hit.  Retry with exponential backoff on 429,
    respecting the Retry-After header if present.

    Uses up to 5 attempts with waits up to 60s to survive the
    rate-limit window (typically 60s).
    """
    url = f"{api_base_url()}/auth/login/"
    payload = {"email": email, "password": password}

    max_attempts = 5
    for attempt in range(max_attempts):
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code != 429:
            return resp
        # Parse Retry-After header if present, else exponential backoff
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            wait = int(retry_after)
        else:
            wait = min(2 ** (attempt + 2), 60)
        time.sleep(wait)

    return resp  # return last 429 if all retries exhausted


def api_unauthenticated_get(path: str, timeout: int = 15) -> requests.Response:
    """GET without any auth header."""
    return requests.get(f"{api_base_url()}{path}", timeout=timeout)
