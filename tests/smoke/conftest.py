"""
Shared fixtures for the smoke test suite.

Usage
-----
    # Against a running deployment:
    pytest tests/smoke/ --base-url=https://staging.hub.example.com -v

    # Locally (docker-compose.test.yml):
    API_BASE_URL=http://localhost:8001 pytest tests/smoke/ -v

Environment variables
---------------------
    SMOKE_BASE_URL          Base URL of the deployed API (overridden by --base-url CLI option)
    SMOKE_ADMIN_EMAIL       Admin account email for authenticated tests
    SMOKE_ADMIN_PASSWORD    Admin account password for authenticated tests
    SMOKE_TEST_TIMEOUT      HTTP request timeout in seconds (default: 30)
"""
import os
import pytest
import requests


# ---------------------------------------------------------------------------
# CLI option — mirrors what the deploy workflow passes via --base-url
# ---------------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="Base URL of the deployed API (e.g. https://staging.hub.example.com)",
    )


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url(request: pytest.FixtureRequest) -> str:
    """
    Resolve the API base URL from --base-url CLI option or SMOKE_BASE_URL env.

    Strips trailing slash to ensure consistent URL construction.
    """
    url = (
        request.config.getoption("--base-url")
        or os.getenv("SMOKE_BASE_URL")
        or os.getenv("API_BASE_URL", "http://localhost:8001")
    )
    return url.rstrip("/")


@pytest.fixture(scope="session")
def timeout() -> int:
    return int(os.getenv("SMOKE_TEST_TIMEOUT", "30"))


@pytest.fixture(scope="session")
def api_session(timeout: int) -> requests.Session:
    """
    Unauthenticated requests.Session with consistent timeouts.
    Use this for public endpoints (health, login, OpenAPI schema).
    """
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def admin_credentials() -> dict:
    """
    Admin credentials from environment — set in GitHub secrets for CI.
    Tests that require this fixture are skipped if credentials are absent.
    """
    email = os.getenv("SMOKE_ADMIN_EMAIL")
    password = os.getenv("SMOKE_ADMIN_PASSWORD")
    if not email or not password:
        pytest.skip(
            "Admin credentials not set — export SMOKE_ADMIN_EMAIL and "
            "SMOKE_ADMIN_PASSWORD to run authenticated smoke tests"
        )
    return {"email": email, "password": password}


@pytest.fixture(scope="session")
def auth_token(base_url: str, api_session: requests.Session,
               admin_credentials: dict, timeout: int) -> str:
    """
    Authenticate once per session and return a JWT access token.

    Caches the token for all tests in the session to avoid repeated logins.
    """
    response = api_session.post(
        f"{base_url}/api/v1/auth/login/",
        json=admin_credentials,
        timeout=timeout,
    )
    assert response.status_code == 200, (
        f"Login failed ({response.status_code}): {response.text[:500]}"
    )
    data = response.json()
    token = data.get("access") or data.get("token") or data.get("access_token")
    assert token, f"No access token in login response: {list(data.keys())}"
    return token


@pytest.fixture(scope="session")
def authenticated_session(auth_token: str) -> requests.Session:
    """
    requests.Session pre-configured with Bearer auth header.
    Use this for all endpoints that require authentication.
    """
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
    })
    return session
