"""
W16 environment-policy pins for the Snowflake live-test guards (task 7.1).

The Snowflake connector tests exercise a real external service. Per the W16
contract (Phase T.4 / envpolicy.py), every "service unavailable / not
authenticated / dependency missing" branch must RAISE in CI and skip only
locally. This file pins that the integrations Snowflake guards implement the
policy:

- ``get_snowflake_credentials()`` — CI raises EnvironmentFailureError when
  the required SNOWFLAKE_* env vars are missing; local raises pytest.skip.
- ``_snowflake_package_available()`` — CI raises when snowflake-connector-python
  is absent; local returns False (the class-level skipif skips).
- ``has_snowflake_connection()`` — missing credentials follow the same policy
  BEFORE any connector construction (no network access in CI when the
  environment is unprovisioned).

No mocks: real environment manipulation only (monkeypatch) — the functions
under test read the real environment and the real connector package state.
"""

import pytest

import hub.apps.integrations.tests.test_snowflake_connector as snowflake_tests
from envpolicy import EnvironmentFailureError
from hub.apps.integrations.tests.test_snowflake_connector import (
    _snowflake_package_available,
    get_snowflake_credentials,
    has_snowflake_connection,
)

SNOWFLAKE_ENV_VARS = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_TOKEN",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_DATABASE",
)


@pytest.fixture
def clear_snowflake_env(monkeypatch):
    """Remove every SNOWFLAKE_* var so the missing-creds branch is taken."""
    for var in SNOWFLAKE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def ci_env(monkeypatch):
    monkeypatch.setenv("CI", "true")


@pytest.fixture
def local_env(monkeypatch):
    monkeypatch.delenv("CI", raising=False)


def test_missing_credentials_raise_in_ci(clear_snowflake_env, ci_env):
    """CI=true + missing env → EnvironmentFailureError (fails loudly)."""
    with pytest.raises(EnvironmentFailureError):
        get_snowflake_credentials()


def test_missing_credentials_skip_locally(clear_snowflake_env, local_env):
    """Local + missing env → pytest.skip (graceful local skip)."""
    with pytest.raises(pytest.skip.Exception):
        get_snowflake_credentials()


def test_full_env_returns_real_credentials(monkeypatch, local_env):
    """All six vars set → the real dict, optional keys preserved."""
    expected = {
        "SNOWFLAKE_ACCOUNT": "xy12345.us-east-1",
        "SNOWFLAKE_USER": "hub_test_reader",
        "SNOWFLAKE_TOKEN": "pat-token-value",
        "SNOWFLAKE_WAREHOUSE": "COMPUTE_WH",
        "SNOWFLAKE_ROLE": "PUBLIC",
        "SNOWFLAKE_DATABASE": "SNOWFLAKE_SAMPLE_DATA",
    }
    for var, value in expected.items():
        monkeypatch.setenv(var, value)

    credentials = get_snowflake_credentials()
    assert credentials["account"] == expected["SNOWFLAKE_ACCOUNT"]
    assert credentials["user"] == expected["SNOWFLAKE_USER"]
    assert credentials["token"] == expected["SNOWFLAKE_TOKEN"]
    assert credentials["warehouse"] == expected["SNOWFLAKE_WAREHOUSE"]
    assert credentials["role"] == expected["SNOWFLAKE_ROLE"]
    assert credentials["database"] == expected["SNOWFLAKE_DATABASE"]


def test_package_guard_raises_in_ci(monkeypatch, ci_env):
    """CI=true + package absent → EnvironmentFailureError at the guard."""
    monkeypatch.setattr(snowflake_tests, "SNOWFLAKE_AVAILABLE", False)
    with pytest.raises(EnvironmentFailureError):
        _snowflake_package_available()


def test_package_guard_false_locally(monkeypatch, local_env):
    """Local + package absent → False (the skipif skips the class)."""
    monkeypatch.setattr(snowflake_tests, "SNOWFLAKE_AVAILABLE", False)
    assert _snowflake_package_available() is False


def test_probe_raises_in_ci_before_any_connector(clear_snowflake_env, ci_env):
    """CI=true + no creds → EnvironmentFailureError before network access."""
    with pytest.raises(EnvironmentFailureError):
        has_snowflake_connection()


def test_probe_skips_locally(clear_snowflake_env, local_env):
    """Local + no creds → pytest.skip."""
    with pytest.raises(pytest.skip.Exception):
        has_snowflake_connection()
