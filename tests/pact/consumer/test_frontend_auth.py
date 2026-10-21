"""
Pact consumer test: Frontend Auth → /api/v1/auth/ (281.A.2.2).

Consumer #3 of 5 critical API consumers.
Written against the pact-python 3.x FFI DSL (``match.like`` / ``match.regex``,
``pact.serve()`` context manager, ``write_file`` on module teardown).
"""

import pytest

try:
    import pact as _pact
    from pact import Pact, match
except ImportError:
    from envpolicy import environment_guard

    environment_guard("pact-python is not installed — install it to run the Pact consumer tests")
    pytest.skip("pact-python is not installed", allow_module_level=True)

PACT_DIR = "tests/pact/pacts"


@pytest.fixture
def auth_pact():
    """Per-test Pact for the Frontend Auth consumer.

    The FFI pact handle is finalized by the first ``serve()`` session, so
    each test gets a fresh Pact. ``write_file(overwrite=False)`` MERGES
    the test's interactions into the committed pact file on teardown.
    """
    pact = Pact(consumer="FrontendAuth", provider="MeshantAPI")
    yield pact
    pact.write_file(PACT_DIR, overwrite=False)


class TestFrontendAuthContract:
    """Frontend Auth consumer expectations."""

    def test_login_success(self, auth_pact):
        pact = auth_pact
        (
            pact.upon_receiving("login with email and password")
            .given("valid credentials")
            .with_request("POST", "/api/v1/auth/login/")
            .with_body(
                {
                    "email": match.like("user@meshant.com"),
                    "password": match.like("password123"),
                },
                part="Request",
            )
            .will_respond_with(200)
            .with_body(
                {
                    "access_token": match.regex("eyJhbGciOi...", regex=r"^[A-Za-z0-9\-_.]+$"),
                    "refresh_token": match.like("refresh-token"),
                    "user": {
                        "id": match.regex("user-uuid", regex=r"^[0-9a-f-]+$"),
                        "email": match.like("user@meshant.com"),
                    },
                },
                part="Response",
            )
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.post(
                f"{srv.url}/api/v1/auth/login/",
                json={
                    "email": "user@meshant.com",
                    "password": "password123",
                },
            )
            assert result.status_code == 200
            assert "access_token" in result.json()

    def test_login_invalid(self, auth_pact):
        pact = auth_pact
        (
            pact.upon_receiving("login with wrong password")
            .given("invalid credentials")
            .with_request("POST", "/api/v1/auth/login/")
            .with_body(
                {
                    "email": match.like("user@meshant.com"),
                    "password": match.like("wrong"),
                },
                part="Request",
            )
            .will_respond_with(401)
            .with_body(
                {
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": match.like("Invalid email or password"),
                    },
                },
                part="Response",
            )
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.post(
                f"{srv.url}/api/v1/auth/login/",
                json={
                    "email": "user@meshant.com",
                    "password": "wrong",
                },
            )
            assert result.status_code == 401

    def test_register(self, auth_pact):
        pact = auth_pact
        (
            pact.upon_receiving("register new user")
            .given("registration enabled")
            .with_request("POST", "/api/v1/auth/register/")
            .with_body(
                {
                    "email": match.like("new@meshant.com"),
                    "password": match.like("SecurePass1!"),
                    "name": match.like("New User"),
                },
                part="Request",
            )
            .will_respond_with(201)
            .with_body(
                {
                    "id": match.regex("new-uuid", regex=r"^[0-9a-f-]+$"),
                    "email": "new@meshant.com",
                    "message": match.like("Verification email sent"),
                },
                part="Response",
            )
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.post(
                f"{srv.url}/api/v1/auth/register/",
                json={
                    "email": "new@meshant.com",
                    "password": "SecurePass1!",
                    "name": "New User",
                },
            )
            assert result.status_code == 201
