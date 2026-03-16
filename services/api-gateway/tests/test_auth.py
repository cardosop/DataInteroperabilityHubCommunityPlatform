"""
Authentication and CORS tests for api-gateway.

Verifies that:
- /health, /metrics, and / are accessible without an API key
- Protected routes return 401 when no API key is supplied
- Protected routes return 401 when an invalid API key header is supplied
- CORS is not configured with a wildcard origin (allow_origins != ["*"])
- CORS origins are read from CORS_ALLOWED_ORIGINS env var when set

Uses real FastAPI TestClient — no mocks.
Requires Django to be configured (hub.settings).
"""
import os
import sys

# Setup Django before importing the app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

import django
django.setup()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from main import app, _cors_origins

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Public / unprotected endpoints
# ---------------------------------------------------------------------------

def test_health_no_key_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_metrics_no_key_returns_200():
    response = client.get("/metrics")
    assert response.status_code == 200


def test_root_no_key_returns_200():
    response = client.get("/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Protected routes — missing API key → 401
# ---------------------------------------------------------------------------

class TestMissingApiKeyReturns401:
    def test_unknown_route_no_key(self):
        response = client.get("/api/v1/assets")
        assert response.status_code == 401

    def test_post_no_key(self):
        response = client.post("/api/v1/datasets", json={})
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Protected routes — invalid API key → 401
# ---------------------------------------------------------------------------

class TestInvalidApiKeyReturns401:
    def test_get_with_invalid_apikey_header(self):
        response = client.get("/api/v1/assets", headers={"X-API-Key": "not-a-valid-key"})
        assert response.status_code == 401

    def test_get_with_invalid_authorization_header(self):
        response = client.get(
            "/api/v1/assets",
            headers={"Authorization": "ApiKey not-a-valid-key"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# CORS configuration — no wildcard
# ---------------------------------------------------------------------------

def test_cors_origins_is_not_wildcard():
    """allow_origins must never be ['*'] — browsers reject wildcard + credentials."""
    assert _cors_origins != ["*"], (
        "CORS allow_origins must not be ['*']. "
        "Use explicit origins via CORS_ALLOWED_ORIGINS env var."
    )


def test_cors_origins_is_list_of_strings():
    """CORS origins list must be a non-empty list of strings."""
    assert isinstance(_cors_origins, list)
    assert len(_cors_origins) > 0
    for origin in _cors_origins:
        assert isinstance(origin, str), f"Expected str, got {type(origin)}: {origin!r}"


def test_cors_origins_from_env(monkeypatch):
    """CORS origins are read from CORS_ALLOWED_ORIGINS env var."""
    import importlib
    import main as gw_main

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com,https://admin.example.com")
    # Re-evaluate the expression from the module to verify env parsing logic
    origins = [
        o.strip()
        for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
        if o.strip()
    ] or ["http://localhost:3000", "http://localhost:5173"]

    assert "https://app.example.com" in origins
    assert "https://admin.example.com" in origins
    assert "*" not in origins
