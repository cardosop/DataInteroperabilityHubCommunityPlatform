import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.18 — Security: input fuzzing.

Sends oversized payloads, SQL-injection-shaped strings, XSS payloads,
and path-traversal attempts to verify the API rejects them gracefully
(4xx, not 500).
"""

import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url, api_post, api_get


@pytest.fixture(scope="module")
def fuzz_creds():
    """Provision a data_engineer for fuzzing tests."""
    return provision_persona("data_engineer")


# ---------------------------------------------------------------------------
# SQL injection
# ---------------------------------------------------------------------------

SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE assets; --",
    "1' OR '1'='1",
    "' UNION SELECT * FROM users --",
    "admin'--",
    "1; DELETE FROM contracts WHERE 1=1",
]


@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sql_injection_in_asset_name(fuzz_creds, payload):
    """SQL injection in asset name must not cause 500."""
    resp = api_post("/assets/", fuzz_creds, json={
        "name": payload,
        "key": "fuzz-sql-test",
    })
    assert resp.status_code < 500, (
        f"SQL injection payload caused server error: {resp.status_code} {resp.text[:200]}"
    )


@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sql_injection_in_search_param(fuzz_creds, payload):
    """SQL injection in search query param must not cause 500."""
    resp = api_get("/assets/", fuzz_creds, params={"search": payload})
    assert resp.status_code < 500, (
        f"SQL injection in search caused server error: {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# XSS
# ---------------------------------------------------------------------------

XSS_PAYLOADS = [
    '<script>alert("xss")</script>',
    '<img src=x onerror=alert(1)>',
    '"><svg onload=alert(1)>',
    "javascript:alert(document.cookie)",
]


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_xss_in_asset_name(fuzz_creds, payload):
    """XSS payload in asset name must not cause 500."""
    resp = api_post("/assets/", fuzz_creds, json={
        "name": payload,
        "key": "fuzz-xss-test",
    })
    assert resp.status_code < 500


# ---------------------------------------------------------------------------
# Oversized payloads
# ---------------------------------------------------------------------------

def test_oversized_payload_rejected(fuzz_creds):
    """A 10MB JSON payload must be rejected, not crash the server."""
    big_name = "A" * (10 * 1024 * 1024)
    resp = api_post("/assets/", fuzz_creds, json={"name": big_name})
    assert resp.status_code in (400, 413, 422), (
        f"10MB payload returned {resp.status_code}, expected 400/413/422"
    )


def test_deeply_nested_json_rejected(fuzz_creds):
    """Deeply nested JSON must not cause stack overflow."""
    # Build 200-level deep nesting
    payload = {"a": None}
    current = payload
    for _ in range(200):
        inner = {"a": None}
        current["a"] = inner
        current = inner

    resp = requests.post(
        f"{api_base_url()}/assets/",
        headers={"Authorization": f"Bearer {fuzz_creds.api_key}"},
        json=payload,
        timeout=30,
    )
    assert resp.status_code < 500


# ---------------------------------------------------------------------------
# Path traversal
# ---------------------------------------------------------------------------

PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..%2F..%2F..%2Fetc%2Fpasswd",
    "....//....//....//etc/passwd",
]


@pytest.mark.parametrize("payload", PATH_TRAVERSAL_PAYLOADS)
def test_path_traversal_in_asset_key(fuzz_creds, payload):
    """Path traversal in asset key must not cause 500 or leak files."""
    resp = api_post("/assets/", fuzz_creds, json={
        "name": "path-traversal-test",
        "key": payload,
    })
    assert resp.status_code < 500
    if resp.status_code == 200 or resp.status_code == 201:
        # Even if created, the response must not contain file system content
        body = resp.text
        assert "root:" not in body
        assert "/bin/" not in body
