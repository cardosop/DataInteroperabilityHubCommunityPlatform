"""
Smoke test — authentication flow.

Validates that the JWT auth endpoints work correctly after deployment:
- Valid credentials → access + refresh tokens returned
- Refresh token → new access token
- Invalid credentials → 401 (not 500)
- Protected endpoints reject unauthenticated requests

Required env vars (set as GitHub secrets in CI):
    SMOKE_ADMIN_EMAIL
    SMOKE_ADMIN_PASSWORD
"""
import pytest
import requests


class TestLogin:
    """POST /api/v1/auth/login/ — obtain JWT tokens."""

    def test_login_with_valid_credentials_returns_200(
        self,
        base_url: str,
        api_session: requests.Session,
        admin_credentials: dict,
        timeout: int,
    ) -> None:
        """Valid admin credentials must return HTTP 200."""
        response = api_session.post(
            f"{base_url}/api/v1/auth/login/",
            json=admin_credentials,
            timeout=timeout,
        )
        assert response.status_code == 200, (
            f"Login returned {response.status_code}: {response.text[:500]}"
        )

    def test_login_returns_access_token(
        self,
        base_url: str,
        api_session: requests.Session,
        admin_credentials: dict,
        timeout: int,
    ) -> None:
        """Login response must include a non-empty 'access' JWT."""
        response = api_session.post(
            f"{base_url}/api/v1/auth/login/",
            json=admin_credentials,
            timeout=timeout,
        )
        assert response.status_code == 200
        data = response.json()
        # Support both DRF Simple JWT ('access') and custom key names
        token = data.get("access") or data.get("token") or data.get("access_token")
        assert token, f"No access token in login response keys: {list(data.keys())}"
        # JWT format: three base64url segments separated by dots
        assert len(token.split(".")) == 3, (
            f"access token does not look like a JWT: {token[:50]}..."
        )

    def test_login_returns_refresh_token(
        self,
        base_url: str,
        api_session: requests.Session,
        admin_credentials: dict,
        timeout: int,
    ) -> None:
        """Login response must include a 'refresh' JWT for token rotation."""
        response = api_session.post(
            f"{base_url}/api/v1/auth/login/",
            json=admin_credentials,
            timeout=timeout,
        )
        assert response.status_code == 200
        data = response.json()
        refresh = data.get("refresh") or data.get("refresh_token")
        assert refresh, f"No refresh token in response keys: {list(data.keys())}"

    def test_login_with_invalid_credentials_returns_401(
        self,
        base_url: str,
        api_session: requests.Session,
        timeout: int,
    ) -> None:
        """Wrong password must return 401 — not 500 (not an unhandled error)."""
        response = api_session.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": "nonexistent@example.com", "password": "wrong-password-smoke"},
            timeout=timeout,
        )
        assert response.status_code == 401, (
            f"Expected 401 for bad credentials, got {response.status_code}"
        )

    def test_login_with_missing_fields_returns_400(
        self,
        base_url: str,
        api_session: requests.Session,
        timeout: int,
    ) -> None:
        """Empty payload must return 400 (validation error) — not 500."""
        response = api_session.post(
            f"{base_url}/api/v1/auth/login/",
            json={},
            timeout=timeout,
        )
        assert response.status_code in (400, 401), (
            f"Expected 400/401 for empty payload, got {response.status_code}"
        )


class TestTokenRefresh:
    """POST /api/v1/auth/token/refresh/ — rotate access token via refresh token."""

    def test_refresh_token_returns_new_access_token(
        self,
        base_url: str,
        api_session: requests.Session,
        admin_credentials: dict,
        timeout: int,
    ) -> None:
        """A valid refresh token must yield a new access token."""
        # Step 1: obtain tokens
        login_resp = api_session.post(
            f"{base_url}/api/v1/auth/login/",
            json=admin_credentials,
            timeout=timeout,
        )
        assert login_resp.status_code == 200
        refresh_token = login_resp.json().get("refresh") or login_resp.json().get("refresh_token")
        if not refresh_token:
            pytest.skip("Login response does not include a refresh token")

        # Step 2: exchange refresh token
        refresh_resp = api_session.post(
            f"{base_url}/api/v1/auth/token/refresh/",
            json={"refresh": refresh_token},
            timeout=timeout,
        )
        assert refresh_resp.status_code == 200, (
            f"Token refresh returned {refresh_resp.status_code}: {refresh_resp.text[:300]}"
        )
        new_access = refresh_resp.json().get("access") or refresh_resp.json().get("access_token")
        assert new_access, "Token refresh response missing new access token"


class TestProtectedEndpoints:
    """Verify authentication is enforced on protected resources."""

    def test_unauthenticated_request_returns_401(
        self,
        base_url: str,
        api_session: requests.Session,
        timeout: int,
    ) -> None:
        """GET /api/v1/datasets/ without a token must return 401 or 403."""
        response = api_session.get(
            f"{base_url}/api/v1/datasets/",
            timeout=timeout,
        )
        assert response.status_code in (401, 403), (
            f"Unauthenticated GET /datasets/ returned {response.status_code} "
            f"(expected 401/403 — endpoint may be public, verify this is intentional)"
        )

    def test_authenticated_request_does_not_return_401(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        """GET /api/v1/datasets/ with a valid Bearer token must not return 401/403."""
        response = authenticated_session.get(
            f"{base_url}/api/v1/datasets/",
            timeout=timeout,
        )
        assert response.status_code not in (401, 403), (
            f"Authenticated request to /datasets/ returned {response.status_code} "
            f"— JWT may be invalid or expired"
        )
