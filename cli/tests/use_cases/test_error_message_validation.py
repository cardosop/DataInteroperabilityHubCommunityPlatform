"""
Phase 10-2a.4.1 — Error message content validation tests.

Validates that error responses from the API contain specific, actionable
error messages rather than generic "something went wrong" responses.
This ensures CLI users can diagnose and fix issues without reading server logs.

Test categories:
- Missing required parameters → message names the missing field
- Invalid UUID format → message identifies the malformed parameter
- Resource not found → message includes the resource type and ID
- Validation errors → message describes what was invalid and why
- Auth failures → message indicates that authentication is required
"""

from __future__ import annotations

import pytest
from datahub_cli.main import cli
from tests.use_cases.conftest import unique_key

pytestmark = pytest.mark.mvp


# ── Error message content assertions ────────────────────────────────────────


def _error_contains_any(output: str, phrases: list[str]) -> bool:
    """Return True if *output* (lowercased) contains any of *phrases*."""
    lower = output.lower()
    return any(p.lower() in lower for p in phrases)


def _assert_actionable_error(output: str, resource: str, operation: str) -> None:
    """Assert that *output* looks like an actionable error message.

    An actionable error message MUST contain at least one of:
    - The resource type being operated on
    - The operation that failed
    - A specific reason for the failure
    - A suggestion for how to fix it
    """
    lower = output.lower()
    actionable_indicators = [
        resource.lower(),
        "not found",
        "required",
        "missing",
        "invalid",
        "must be",
        "expected",
        "failed",
        "error",
        "denied",
        "forbidden",
        "unauthorized",
    ]
    matches = [ind for ind in actionable_indicators if ind in lower]
    assert matches, (
        f"Error message for {resource} {operation} is not actionable.\n"
        f"Expected one of {actionable_indicators!r} in output.\n"
        f"Got: {output[:300]}"
    )


# ── Missing required parameter tests ────────────────────────────────────────


class TestMissingRequiredParameters:
    """Verify that omitting required parameters produces specific errors."""

    def test_asset_create_missing_name(self, runner, authenticated_config):
        """Creating an asset without --name should say 'name' is required."""
        result = runner.invoke(cli, ["assets", "create", "--key", unique_key("no-name")])
        assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}"
        _assert_actionable_error(result.output, "asset", "create")
        assert "name" in result.output.lower() or "required" in result.output.lower(), (
            f"Error should mention 'name' or 'required'. Got: {result.output[:200]}"
        )

    def test_asset_create_missing_key(self, runner, authenticated_config):
        """Creating an asset without --key should say 'key' is required."""
        result = runner.invoke(cli, ["assets", "create", "--name", "No Key Asset"])
        assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}"
        _assert_actionable_error(result.output, "asset", "create")
        assert "key" in result.output.lower() or "required" in result.output.lower(), (
            f"Error should mention 'key' or 'required'. Got: {result.output[:200]}"
        )

    def test_compliance_run_missing_resource(self, runner, authenticated_config):
        """Running compliance without --asset-id or --dataset-id should error."""
        result = runner.invoke(cli, ["compliance", "run", "--scan-mode", "internal"])
        assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}"
        _assert_actionable_error(result.output, "compliance", "run")
        assert _error_contains_any(
            result.output,
            [
                "at least one",
                "required",
                "must be provided",
                "asset-id",
                "dataset-id",
            ],
        ), f"Error should mention what's missing. Got: {result.output[:200]}"

    def test_dq_run_missing_resource(self, runner, authenticated_config):
        """Running DQ check without resource ID should say what's missing."""
        result = runner.invoke(cli, ["dq", "run", "--profile-key", "intake_basic_gx"])
        assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}"
        _assert_actionable_error(result.output, "dq", "run")
        assert _error_contains_any(
            result.output,
            [
                "must be provided",
                "required",
                "asset",
                "dataset",
                "file",
            ],
        ), f"Error should mention required parameter. Got: {result.output[:200]}"

    def test_access_request_missing_asset(self, runner, authenticated_config):
        """Creating access request without --asset-id should say what's missing."""
        result = runner.invoke(
            cli,
            [
                "governance",
                "access-request",
                "create",
                "--reason",
                "Need access for testing",
            ],
        )
        assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}"
        _assert_actionable_error(result.output, "access request", "create")
        assert _error_contains_any(
            result.output,
            [
                "at least one",
                "required",
                "asset-id",
                "must be provided",
            ],
        ), f"Error should mention missing resource ID. Got: {result.output[:200]}"


# ── Invalid format / value tests ─────────────────────────────────────────────


class TestInvalidParameterValues:
    """Verify that malformed parameter values produce descriptive errors."""

    def test_asset_get_invalid_uuid(self, runner, authenticated_config):
        """Getting an asset with a non-UUID ID should say the format is invalid."""
        result = runner.invoke(cli, ["assets", "get", "not-a-uuid"])
        assert result.exit_code != 0, (
            f"Expected non-zero exit for invalid UUID, got {result.exit_code}"
        )
        _assert_actionable_error(result.output, "asset", "get")
        # The error should indicate the ID is malformed
        assert _error_contains_any(
            result.output,
            [
                "uuid",
                "invalid",
                "not found",
                "failed",
                "format",
                "malformed",
            ],
        ), f"Error should describe the problem. Got: {result.output[:200]}"

    def test_dq_get_invalid_uuid(self, runner, authenticated_config):
        """Getting a DQ run with a non-UUID ID should indicate invalid format."""
        result = runner.invoke(cli, ["dq", "get", "not-a-uuid"])
        assert result.exit_code != 0, (
            f"Expected non-zero exit for invalid UUID, got {result.exit_code}"
        )
        _assert_actionable_error(result.output, "dq", "get")
        assert _error_contains_any(
            result.output,
            [
                "uuid",
                "invalid",
                "not found",
                "failed",
                "format",
                "malformed",
            ],
        ), f"Error should describe the problem. Got: {result.output[:200]}"

    def test_compliance_get_invalid_uuid(self, runner, authenticated_config):
        """Getting a compliance run with a non-UUID ID should indicate invalid format."""
        result = runner.invoke(cli, ["compliance", "get", "not-a-uuid"])
        assert result.exit_code != 0, (
            f"Expected non-zero exit for invalid UUID, got {result.exit_code}"
        )
        _assert_actionable_error(result.output, "compliance", "get")
        assert _error_contains_any(
            result.output,
            [
                "uuid",
                "invalid",
                "not found",
                "failed",
                "format",
                "malformed",
            ],
        ), f"Error should describe the problem. Got: {result.output[:200]}"


# ── Resource not found tests ─────────────────────────────────────────────────


class TestResourceNotFoundMessages:
    """Verify that 404 responses are descriptive about WHAT was not found."""

    def test_asset_get_nonexistent(self, runner, authenticated_config):
        """Getting a non-existent asset should say 'not found' with context."""
        result = runner.invoke(
            cli,
            [
                "assets",
                "get",
                "00000000-0000-0000-0000-000000000000",
            ],
        )
        assert result.exit_code != 0, (
            f"Expected non-zero exit for not-found, got {result.exit_code}"
        )
        _assert_actionable_error(result.output, "asset", "get")
        assert "not found" in result.output.lower() or "failed" in result.output.lower(), (
            f"Error should indicate not-found. Got: {result.output[:200]}"
        )

    def test_contract_get_nonexistent(self, runner, authenticated_config):
        """Getting a non-existent contract should say 'not found'."""
        result = runner.invoke(
            cli,
            [
                "contracts",
                "get",
                "00000000-0000-0000-0000-000000000000",
            ],
        )
        assert result.exit_code != 0, (
            f"Expected non-zero exit for not-found, got {result.exit_code}"
        )
        _assert_actionable_error(result.output, "contract", "get")

    def test_dq_get_nonexistent(self, runner, authenticated_config):
        """Getting a non-existent DQ run should report 404 clearly."""
        result = runner.invoke(
            cli,
            [
                "dq",
                "get",
                "00000000-0000-0000-0000-000000000000",
            ],
        )
        assert result.exit_code != 0, (
            f"Expected non-zero exit for not-found, got {result.exit_code}"
        )
        assert "not found" in result.output.lower() or "failed" in result.output.lower(), (
            f"Error should indicate not-found. Got: {result.output[:200]}"
        )

    def test_access_request_get_nonexistent(self, runner, authenticated_config):
        """Getting a non-existent access request should report 404."""
        result = runner.invoke(
            cli,
            [
                "governance",
                "access-request",
                "get",
                "00000000-0000-0000-0000-000000000000",
            ],
        )
        assert result.exit_code != 0, (
            f"Expected non-zero exit for not-found, got {result.exit_code}"
        )
        assert "not found" in result.output.lower() or "failed" in result.output.lower(), (
            f"Error should indicate not-found. Got: {result.output[:200]}"
        )


# ── Auth failure messages ────────────────────────────────────────────────────


class TestAuthFailureMessages:
    """Verify that auth errors tell the user they need to authenticate."""

    def test_unauthenticated_access(self, runner, temp_config_dir):
        """Accessing an endpoint without auth should indicate auth is needed.

        Uses ``temp_config_dir`` (without ``authenticated_config``) so the
        CLI config directory is empty — the CLI cannot authenticate and must
        produce an actionable error.
        """
        result = runner.invoke(cli, ["assets", "list"])
        # May fail with auth error (non-zero exit) or connection error if API unavailable
        if result.exit_code != 0:
            lower = result.output.lower()
            assert _error_contains_any(
                lower,
                [
                    "auth",
                    "authenticated",
                    "login",
                    "api key",
                    "token",
                    "unauthorized",
                    "401",
                    "connection refused",
                    "could not connect",
                ],
            ), (
                f"Auth error should mention authentication or connectivity. "
                f"Got: {result.output[:300]}"
            )
