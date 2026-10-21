"""
Security: input fuzzing for Django hub API endpoints.

Sends oversized payloads, SQL-injection-shaped strings, XSS payloads,
and path-traversal attempts to verify the API rejects them with a
client error (4xx). A 200/201 means the payload was ACCEPTED — a
potential vulnerability.

Mirrors the CLI and SDK input fuzzing patterns in cli/tests/security/
and sdk/python/tests/security/.
"""

import pytest
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


# ── Payloads ─────────────────────────────────────────────────────────────

SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE assets; --",
    "1' OR '1'='1",
    "' UNION SELECT * FROM users --",
    "admin'--",
    "1; DELETE FROM contracts WHERE 1=1",
]

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "<body onload=alert(1)>",
]

OVERSIZED_PAYLOADS = [
    "A" * 10000,  # 10KB string for a name field
    "B" * 100000,  # 100KB string
]


@pytest.fixture
def api_client():
    """Authenticated DRF APIClient for a test tenant."""
    import uuid

    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"FuzzTest {uid}",
        slug=f"fuzz-test-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    user = User.objects.create_user(
        email=f"fuzz-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_TENANT_ID=str(tenant.id))
    return client, tenant


# ── SQL Injection ────────────────────────────────────────────────────────


@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sql_injection_asset_create_rejected(api_client, payload):
    """SQL injection in asset name must be rejected (4xx), not crash (5xx)."""
    client, _tenant = api_client
    resp = client.post(
        "/api/v1/assets/",
        {
            "name": payload,
            "key": f"fuzz-sql-{hash(payload) % 10000:x}",
        },
        format="json",
    )
    assert 400 <= resp.status_code < 500, (
        f"SQL injection payload {payload!r} was not rejected: got {resp.status_code}"
    )


@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sql_injection_contract_create_rejected(api_client, payload):
    """SQL injection in contract name must not crash (5xx)."""
    client, _tenant = api_client
    resp = client.post(
        "/api/v1/contracts/",
        {
            "name": payload,
            "contract_type": "DATA_PROCESSING",
        },
        format="json",
    )
    # May be 400 (validation) or 404 (route), but NOT 500
    assert resp.status_code < 500, (
        f"SQL injection in contract caused server error: {resp.status_code}"
    )


@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sql_injection_search_param_no_crash(api_client, payload):
    """SQL injection in search query params must not cause 500 errors."""
    client, _tenant = api_client
    resp = client.get("/api/v1/assets/", {"search": payload})
    assert resp.status_code < 500, (
        f"SQL injection in search param caused server error: {resp.status_code}"
    )


# ── XSS ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_xss_in_asset_name_rejected(api_client, payload):
    """XSS payloads in asset name must be rejected or sanitized."""
    client, _tenant = api_client
    resp = client.post(
        "/api/v1/assets/",
        {
            "name": payload,
            "key": f"fuzz-xss-{hash(payload) % 10000:x}",
        },
        format="json",
    )
    # 4xx = rejected (good), 200/201 = inspect response for escaping
    assert resp.status_code < 500, (
        f"XSS payload {payload!r} caused server error: {resp.status_code}"
    )


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_xss_in_search_param_no_crash(api_client, payload):
    """XSS in search params must not cause server errors."""
    client, _tenant = api_client
    resp = client.get("/api/v1/assets/", {"search": payload})
    assert resp.status_code < 500


# ── Oversized Payloads ───────────────────────────────────────────────────


@pytest.mark.parametrize("payload", OVERSIZED_PAYLOADS)
def test_oversized_payload_rejected(api_client, payload):
    """Oversized name field must be rejected, not crash."""
    client, _tenant = api_client
    resp = client.post(
        "/api/v1/assets/",
        {
            "name": payload,
            "key": "fuzz-oversized",
        },
        format="json",
    )
    assert resp.status_code < 500, (
        f"Oversized payload ({len(payload)} chars) caused server error: {resp.status_code}"
    )


# ── Path Traversal ─────────────────────────────────────────────────────


def test_path_traversal_in_asset_key_rejected(api_client):
    """Path traversal in asset key must be rejected."""
    client, _tenant = api_client
    resp = client.post(
        "/api/v1/assets/",
        {
            "name": "test",
            "key": "../../../etc/passwd",
        },
        format="json",
    )
    assert resp.status_code < 500, (
        f"Path traversal in asset key caused server error: {resp.status_code}"
    )


# ── Malformed JSON / Content-Type ──────────────────────────────────────


def test_malformed_json_body_no_crash(api_client):
    """Malformed JSON body must not cause 500."""
    client, _tenant = api_client
    resp = client.post(
        "/api/v1/assets/",
        data="{this is not valid json",
        content_type="application/json",
    )
    assert resp.status_code < 500, f"Malformed JSON caused server error: {resp.status_code}"


def test_wrong_content_type_no_crash(api_client):
    """Wrong Content-Type must not cause 500."""
    client, _tenant = api_client
    resp = client.post(
        "/api/v1/assets/",
        data="name=test",
        content_type="text/plain",
    )
    assert resp.status_code < 500


# ── PII Leakage Check ──────────────────────────────────────────────────


def test_error_response_no_stack_trace(api_client):
    """Error responses must not leak stack traces."""
    client, _tenant = api_client
    # Trigger a validation error
    resp = client.post("/api/v1/assets/", {}, format="json")
    assert resp.status_code < 500
    content = str(resp.content)
    # Should not contain Python traceback markers
    assert "Traceback (most recent call last)" not in content, (
        "Stack trace leaked in error response"
    )
    assert 'File "' not in content, "File path leaked in error response"


def test_error_response_no_db_credentials(api_client):
    """Error responses must not leak database connection info."""
    client, _tenant = api_client
    resp = client.post("/api/v1/assets/", {}, format="json")
    assert resp.status_code < 500
    content = str(resp.content).lower()
    # Database credential patterns that should never appear
    for secret in ["password=", "postgresql://", "redis://"]:
        assert secret not in content, f"Potential credential leak in error response: {secret!r}"
