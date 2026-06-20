"""
Pact consumer test: Frontend Auth → /api/v1/auth/ (281.A.2.2).

Consumer #3 of 5 critical API consumers.
"""

import pytest
from pact import Pact
from pact.matchers import Like, Term

PACT_DIR = "tests/pact/pacts"


@pytest.fixture(scope="module")
def auth_pact():
    pact = Pact("FrontendAuth", "MeshantAPI")
    pact.with_specification("V4").with_pact_dir(PACT_DIR)
    with pact.start_mocking(port=1236):
        yield pact


class TestFrontendAuthContract:
    """Frontend Auth consumer expectations."""

    def test_login_success(self, auth_pact):
        auth_pact.given("valid credentials").upon_receiving(
            "login with email and password"
        ).with_request(
            "POST",
            "/api/v1/auth/login/",
            body={
                "email": Like("user@meshant.com"),
                "password": Like("password123"),
            },
        ).will_respond_with(
            200,
            body={
                "access_token": Term(r"^[A-Za-z0-9\-_.]+$", "eyJhbGciOi..."),
                "refresh_token": Like("refresh-token"),
                "user": {
                    "id": Term(r"^[0-9a-f-]+$", "user-uuid"),
                    "email": Like("user@meshant.com"),
                },
            },
        )

        import requests

        result = requests.post(
            "http://localhost:1236/api/v1/auth/login/",
            json={
                "email": "user@meshant.com",
                "password": "password123",
            },
        )
        assert result.status_code == 200
        assert "access_token" in result.json()

    def test_login_invalid(self, auth_pact):
        auth_pact.given("invalid credentials").upon_receiving(
            "login with wrong password"
        ).with_request(
            "POST",
            "/api/v1/auth/login/",
            body={
                "email": Like("user@meshant.com"),
                "password": Like("wrong"),
            },
        ).will_respond_with(
            401,
            body={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": Like("Invalid email or password"),
                },
            },
        )

        import requests

        result = requests.post(
            "http://localhost:1236/api/v1/auth/login/",
            json={
                "email": "user@meshant.com",
                "password": "wrong",
            },
        )
        assert result.status_code == 401

    def test_register(self, auth_pact):
        auth_pact.given("registration enabled").upon_receiving("register new user").with_request(
            "POST",
            "/api/v1/auth/register/",
            body={
                "email": Like("new@meshant.com"),
                "password": Like("SecurePass1!"),
                "name": Like("New User"),
            },
        ).will_respond_with(
            201,
            body={
                "id": Term(r"^[0-9a-f-]+$", "new-uuid"),
                "email": "new@meshant.com",
                "message": Like("Verification email sent"),
            },
        )

        import requests

        result = requests.post(
            "http://localhost:1236/api/v1/auth/register/",
            json={
                "email": "new@meshant.com",
                "password": "SecurePass1!",
                "name": "New User",
            },
        )
        assert result.status_code == 201
