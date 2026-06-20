from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive unit tests for BaaS CLI commands.

Tests all BaaS API key commands: create, list, get, update, revoke.
"""
import json
from datetime import UTC
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from datahub_cli.main import cli


@pytest.fixture
def runner():
    """Create a CliRunner instance"""
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock API client for baas commands"""
    mock_client = Mock()
    monkeypatch.setattr("datahub_cli.commands.baas.api_client", mock_client)
    return mock_client


class TestBaaSCommandGroup:
    """Test BaaS command group registration"""

    def test_baas_command_group_exists(self, runner):
        """Test that baas command group is registered"""
        result = runner.invoke(cli, ["baas", "--help"])
        assert result.exit_code == 0
        assert "BaaS (Backend as a Service) management commands" in result.output

    def test_api_keys_subcommand_exists(self, runner):
        """Test that api-keys subcommand is registered"""
        result = runner.invoke(cli, ["baas", "api-keys", "--help"])
        assert result.exit_code == 0
        assert "API key management commands" in result.output


class TestAPIKeyCreate:
    """Test API key create command"""

    def test_create_api_key_success_table_format(self, runner, mock_api_client):
        """Test creating API key in table format"""
        mock_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Test API Key",
            "api_key": "test-api-key-value-12345",
            "tier": "FREE",
            "expires_at": None,
            "created_at": "2025-01-01T00:00:00Z",
        }
        mock_api_client.post.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "create", "--name", "Test API Key"])

        assert result.exit_code == 0
        assert "API key created successfully" in result.output
        assert "Test API Key" in result.output
        assert "test-api-key-value-12345" in result.output
        assert "IMPORTANT" in result.output
        assert "Save this API key securely" in result.output
        mock_api_client.post.assert_called_once_with(
            "baas/api-keys/", json_data={"name": "Test API Key", "tier": "FREE"}
        )

    def test_create_api_key_success_json_format(self, runner, mock_api_client):
        """Test creating API key in JSON format"""
        mock_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Test API Key",
            "api_key": "test-api-key-value-12345",
            "tier": "FREE",
            "expires_at": None,
            "created_at": "2025-01-01T00:00:00Z",
        }
        mock_api_client.post.return_value = mock_data

        result = runner.invoke(
            cli, ["baas", "api-keys", "create", "--name", "Test API Key", "--format", "json"]
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert output_data["name"] == "Test API Key"
        assert output_data["api_key"] == "test-api-key-value-12345"

    def test_create_api_key_with_tier(self, runner, mock_api_client):
        """Test creating API key with specific tier"""
        mock_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Pro API Key",
            "api_key": "test-api-key-value-12345",
            "tier": "PRO",
            "expires_at": None,
            "created_at": "2025-01-01T00:00:00Z",
        }
        mock_api_client.post.return_value = mock_data

        result = runner.invoke(
            cli, ["baas", "api-keys", "create", "--name", "Pro API Key", "--tier", "PRO"]
        )

        assert result.exit_code == 0
        assert "PRO" in result.output
        mock_api_client.post.assert_called_once_with(
            "baas/api-keys/", json_data={"name": "Pro API Key", "tier": "PRO"}
        )

    def test_create_api_key_with_expiration(self, runner, mock_api_client):
        """Test creating API key with expiration date"""
        # Use a future date (1 year from now)
        from datetime import datetime, timedelta

        future_date = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")

        mock_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Test API Key",
            "api_key": "test-api-key-value-12345",
            "tier": "FREE",
            "expires_at": future_date,
            "created_at": "2025-01-01T00:00:00Z",
        }
        mock_api_client.post.return_value = mock_data

        result = runner.invoke(
            cli,
            ["baas", "api-keys", "create", "--name", "Test API Key", "--expires-at", future_date],
        )

        assert result.exit_code == 0
        # Verify the expiration date was parsed and sent correctly
        call_args = mock_api_client.post.call_args
        assert "expires_at" in call_args[1]["json_data"]

    def test_create_api_key_empty_name(self, runner):
        """Test creating API key with empty name"""
        result = runner.invoke(cli, ["baas", "api-keys", "create", "--name", ""])

        assert result.exit_code != 0
        assert "cannot be empty" in result.output.lower()

    def test_create_api_key_invalid_expiration_past(self, runner):
        """Test creating API key with past expiration date"""
        result = runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "create",
                "--name",
                "Test API Key",
                "--expires-at",
                "2020-01-01T00:00:00Z",
            ],
        )

        assert result.exit_code != 0
        assert "future" in result.output.lower()

    def test_create_api_key_invalid_expiration_format(self, runner):
        """Test creating API key with invalid expiration format"""
        result = runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "create",
                "--name",
                "Test API Key",
                "--expires-at",
                "invalid-date",
            ],
        )

        assert result.exit_code != 0
        assert "format" in result.output.lower() or "invalid" in result.output.lower()

    def test_create_api_key_api_error(self, runner, mock_api_client):
        """Test handling API errors when creating API key"""
        from click import ClickException

        mock_api_client.post.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ["baas", "api-keys", "create", "--name", "Test API Key"])

        assert result.exit_code != 0
        assert "API error: Connection failed" in result.output


class TestAPIKeyList:
    """Test API key list command"""

    def test_list_api_keys_success_table_format(self, runner, mock_api_client):
        """Test listing API keys in table format"""
        mock_data = {
            "results": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "Test API Key 1",
                    "tier": "FREE",
                    "is_active": True,
                    "expires_at": None,
                },
                {
                    "id": "223e4567-e89b-12d3-a456-426614174000",
                    "name": "Test API Key 2",
                    "tier": "PRO",
                    "is_active": False,
                    "expires_at": "2025-12-31T23:59:59Z",
                },
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "list"])

        assert result.exit_code == 0
        assert "Test API Key 1" in result.output
        assert "Test API Key 2" in result.output
        assert "FREE" in result.output
        assert "PRO" in result.output
        assert "ACTIVE" in result.output
        assert "INACTIVE" in result.output
        mock_api_client.get.assert_called_once_with(
            "baas/api-keys/", params={"limit": 20, "offset": 0}
        )

    def test_list_api_keys_success_json_format(self, runner, mock_api_client):
        """Test listing API keys in JSON format"""
        mock_data = {
            "results": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "Test API Key",
                    "tier": "FREE",
                    "is_active": True,
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "list", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1
        assert output_data[0]["id"] == "123e4567-e89b-12d3-a456-426614174000"

    def test_list_api_keys_with_tier_filter(self, runner, mock_api_client):
        """Test listing API keys with tier filter"""
        mock_data = {"results": []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "list", "--tier", "PRO"])

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            "baas/api-keys/", params={"limit": 20, "offset": 0, "tier": "PRO"}
        )

    def test_list_api_keys_with_pagination(self, runner, mock_api_client):
        """Test listing API keys with pagination"""
        mock_data = {"results": [], "count": 50}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "list", "--limit", "10", "--offset", "20"])

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            "baas/api-keys/", params={"limit": 10, "offset": 20}
        )

    def test_list_api_keys_empty_result(self, runner, mock_api_client):
        """Test listing API keys when no keys exist"""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["baas", "api-keys", "list"])

        assert result.exit_code == 0
        assert "No API keys found" in result.output

    def test_list_api_keys_direct_list_response(self, runner, mock_api_client):
        """Test handling direct list response (not paginated)"""
        mock_data = [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Test API Key",
                "tier": "FREE",
                "is_active": True,
            }
        ]
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "list"])

        assert result.exit_code == 0
        assert "Test API Key" in result.output

    def test_list_api_keys_api_error(self, runner, mock_api_client):
        """Test handling API errors when listing API keys"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ["baas", "api-keys", "list"])

        assert result.exit_code != 0
        assert "API error: Connection failed" in result.output


class TestAPIKeyGet:
    """Test API key get command"""

    def test_get_api_key_success_table_format(self, runner, mock_api_client):
        """Test getting API key in table format"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_data = {
            "id": api_key_id,
            "name": "Test API Key",
            "tier": "FREE",
            "is_active": True,
            "expires_at": None,
            "revoked_at": None,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "get", api_key_id])

        assert result.exit_code == 0
        assert api_key_id in result.output
        assert "Test API Key" in result.output
        assert "FREE" in result.output
        assert "ACTIVE" in result.output
        assert "not displayed" in result.output.lower()
        # Security: Ensure API key value is NOT in output
        assert (
            "api_key" not in result.output.lower() or "api key value" not in result.output.lower()
        )
        mock_api_client.get.assert_called_once_with(f"baas/api-keys/{api_key_id}/")

    def test_get_api_key_success_json_format(self, runner, mock_api_client):
        """Test getting API key in JSON format"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_data = {
            "id": api_key_id,
            "name": "Test API Key",
            "tier": "FREE",
            "is_active": True,
            "expires_at": None,
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "get", api_key_id, "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == api_key_id
        assert "api_key" not in output_data  # Security: no key value

    def test_get_api_key_security_no_key_value(self, runner, mock_api_client):
        """Test that API key value is never displayed in get command"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        # Simulate API returning key value (should be filtered out)
        mock_data = {
            "id": api_key_id,
            "name": "Test API Key",
            "api_key": "secret-key-value-12345",  # This should be removed
            "tier": "FREE",
            "is_active": True,
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "get", api_key_id, "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        # Security: API key value must not be in output
        assert "api_key" not in output_data
        assert "secret-key-value-12345" not in result.output

    def test_get_api_key_with_expiration(self, runner, mock_api_client):
        """Test getting API key with expiration date"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        # Use a future date for expiration
        from datetime import datetime, timedelta

        future_date = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")

        mock_data = {
            "id": api_key_id,
            "name": "Test API Key",
            "tier": "FREE",
            "is_active": True,
            "expires_at": future_date,
            "revoked_at": None,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "get", api_key_id])

        assert result.exit_code == 0
        # Check that expiration date appears in output (format may vary)
        assert (
            future_date[:10] in result.output or "2027" in result.output or "2026" in result.output
        )

    def test_get_api_key_revoked(self, runner, mock_api_client):
        """Test getting revoked API key"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_data = {
            "id": api_key_id,
            "name": "Test API Key",
            "tier": "FREE",
            "is_active": False,
            "expires_at": None,
            "revoked_at": "2025-01-15T00:00:00Z",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-15T00:00:00Z",
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "get", api_key_id])

        assert result.exit_code == 0
        assert "INACTIVE" in result.output
        assert "2025-01-15" in result.output  # revoked_at

    def test_get_api_key_empty_id(self, runner):
        """Test getting API key with empty ID"""
        result = runner.invoke(cli, ["baas", "api-keys", "get", ""])

        assert result.exit_code != 0
        assert "cannot be empty" in result.output.lower()

    def test_get_api_key_not_found(self, runner, mock_api_client):
        """Test getting non-existent API key"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("API error (404): Not found")

        result = runner.invoke(cli, ["baas", "api-keys", "get", api_key_id])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "404" in result.output


class TestAPIKeyUpdate:
    """Test API key update command"""

    def test_update_api_key_name(self, runner, mock_api_client):
        """Test updating API key name"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_data = {
            "id": api_key_id,
            "name": "Updated Name",
            "tier": "FREE",
            "expires_at": None,
            "updated_at": "2025-01-02T00:00:00Z",
        }
        mock_api_client.patch.return_value = mock_data

        result = runner.invoke(
            cli, ["baas", "api-keys", "update", api_key_id, "--name", "Updated Name"]
        )

        assert result.exit_code == 0
        assert "Updated Name" in result.output
        mock_api_client.patch.assert_called_once_with(
            f"baas/api-keys/{api_key_id}/", json_data={"name": "Updated Name"}
        )

    def test_update_api_key_tier(self, runner, mock_api_client):
        """Test updating API key tier"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_data = {
            "id": api_key_id,
            "name": "Test API Key",
            "tier": "PRO",
            "expires_at": None,
            "updated_at": "2025-01-02T00:00:00Z",
        }
        mock_api_client.patch.return_value = mock_data

        result = runner.invoke(cli, ["baas", "api-keys", "update", api_key_id, "--tier", "PRO"])

        assert result.exit_code == 0
        assert "PRO" in result.output
        mock_api_client.patch.assert_called_once_with(
            f"baas/api-keys/{api_key_id}/", json_data={"tier": "PRO"}
        )

    def test_update_api_key_expiration(self, runner, mock_api_client):
        """Test updating API key expiration"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        # Use a future date (1 year from now)
        from datetime import datetime, timedelta

        future_date = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")

        mock_data = {
            "id": api_key_id,
            "name": "Test API Key",
            "tier": "FREE",
            "expires_at": future_date,
            "updated_at": "2025-01-02T00:00:00Z",
        }
        mock_api_client.patch.return_value = mock_data

        result = runner.invoke(
            cli, ["baas", "api-keys", "update", api_key_id, "--expires-at", future_date]
        )

        assert result.exit_code == 0
        # Verify expiration was parsed and sent
        call_args = mock_api_client.patch.call_args
        assert "expires_at" in call_args[1]["json_data"]

    def test_update_api_key_multiple_fields(self, runner, mock_api_client):
        """Test updating multiple fields at once"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        # Use a future date (1 year from now)
        from datetime import datetime, timedelta

        future_date = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")

        mock_data = {
            "id": api_key_id,
            "name": "Updated Name",
            "tier": "PRO",
            "expires_at": future_date,
            "updated_at": "2025-01-02T00:00:00Z",
        }
        mock_api_client.patch.return_value = mock_data

        result = runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "update",
                api_key_id,
                "--name",
                "Updated Name",
                "--tier",
                "PRO",
                "--expires-at",
                future_date,
            ],
        )

        assert result.exit_code == 0
        call_args = mock_api_client.patch.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "Updated Name"
        assert json_data["tier"] == "PRO"
        assert "expires_at" in json_data

    def test_update_api_key_no_fields(self, runner):
        """Test updating API key without providing any fields"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(cli, ["baas", "api-keys", "update", api_key_id])

        assert result.exit_code != 0
        assert "at least one field" in result.output.lower()

    def test_update_api_key_empty_name(self, runner, mock_api_client):
        """Test updating API key with empty name"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        # When --name is provided with empty string, Click passes it as empty string
        # The validation checks if name.strip() is empty, which should fail
        # However, the check `if not any([name, tier, expires_at])` sees empty string as falsy
        # So it might fail on "at least one field" check first
        # Let's test with a non-empty name first to ensure the command works, then test empty
        result = runner.invoke(cli, ["baas", "api-keys", "update", api_key_id, "--name", ""])

        assert result.exit_code != 0
        # The validation should catch either empty name or missing fields
        # Since empty string is falsy, it might trigger "at least one field" error
        # But if name validation runs first, it should catch empty name
        output_lower = result.output.lower()
        assert "cannot be empty" in output_lower or "at least one field" in output_lower

    def test_update_api_key_invalid_expiration(self, runner):
        """Test updating API key with invalid expiration"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli, ["baas", "api-keys", "update", api_key_id, "--expires-at", "invalid-date"]
        )

        assert result.exit_code != 0
        assert "format" in result.output.lower() or "invalid" in result.output.lower()

    def test_update_api_key_not_found(self, runner, mock_api_client):
        """Test updating non-existent API key"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        from click import ClickException

        mock_api_client.patch.side_effect = ClickException("API error (404): Not found")

        result = runner.invoke(
            cli, ["baas", "api-keys", "update", api_key_id, "--name", "Updated Name"]
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "404" in result.output


class TestAPIKeyRevoke:
    """Test API key revoke command"""

    def test_revoke_api_key_success_table_format(self, runner, mock_api_client):
        """Test revoking API key in table format"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_api_client.delete.return_value = {}

        result = runner.invoke(cli, ["baas", "api-keys", "revoke", api_key_id])

        assert result.exit_code == 0
        assert "revoked successfully" in result.output.lower()
        assert api_key_id in result.output
        mock_api_client.delete.assert_called_once_with(f"baas/api-keys/{api_key_id}/")

    def test_revoke_api_key_success_json_format(self, runner, mock_api_client):
        """Test revoking API key in JSON format"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_api_client.delete.return_value = {}

        result = runner.invoke(cli, ["baas", "api-keys", "revoke", api_key_id, "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert "status" in output_data or output_data == {}

    def test_revoke_api_key_empty_id(self, runner):
        """Test revoking API key with empty ID"""
        result = runner.invoke(cli, ["baas", "api-keys", "revoke", ""])

        assert result.exit_code != 0
        assert "cannot be empty" in result.output.lower()

    def test_revoke_api_key_not_found(self, runner, mock_api_client):
        """Test revoking non-existent API key"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        from click import ClickException

        mock_api_client.delete.side_effect = ClickException("API error (404): Not found")

        result = runner.invoke(cli, ["baas", "api-keys", "revoke", api_key_id])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "404" in result.output

    def test_revoke_api_key_api_error(self, runner, mock_api_client):
        """Test handling API errors when revoking API key"""
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        from click import ClickException

        mock_api_client.delete.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ["baas", "api-keys", "revoke", api_key_id])

        assert result.exit_code != 0
        assert "API error: Connection failed" in result.output


class TestAPIKeyRotate:
    """Test API key rotate command"""

    def test_rotate_api_key_success_table_format(self, runner, mock_api_client):
        """Test rotating API key in table format"""
        mock_api_client.post.return_value = {
            "api_key": "new-rotated-key-value-xyz",
            "id": "key-1",
            "status": "ACTIVE",
        }

        result = runner.invoke(cli, ["baas", "api-keys", "rotate", "key-1", "--grace-hours", "48"])

        assert result.exit_code == 0
        assert "API key rotated!" in result.output
        assert "New Key: new-rotated-key-value-xyz" in result.output
        assert "Grace Period: 48h" in result.output
        assert "Save the new key" in result.output
        mock_api_client.post.assert_called_once_with(
            "baas/api-keys/key-1/rotate/", json_data={"grace_period_hours": 48}
        )

    def test_rotate_api_key_success_json_format(self, runner, mock_api_client):
        """Test rotating API key in JSON format"""
        mock_api_client.post.return_value = {
            "api_key": "rotated-key-json",
            "id": "key-1",
            "status": "ACTIVE",
        }

        result = runner.invoke(
            cli, ["baas", "api-keys", "rotate", "key-1", "--grace-hours", "24", "--format", "json"]
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["api_key"] == "rotated-key-json"
        assert output_data["status"] == "ACTIVE"

    def test_rotate_api_key_default_grace_hours(self, runner, mock_api_client):
        """Test rotating API key with default grace period"""
        mock_api_client.post.return_value = {"api_key": "new-key-default", "id": "key-1"}

        result = runner.invoke(cli, ["baas", "api-keys", "rotate", "key-1"])

        assert result.exit_code == 0
        # Default grace-hours is 24
        mock_api_client.post.assert_called_once_with(
            "baas/api-keys/key-1/rotate/", json_data={"grace_period_hours": 24}
        )

    def test_rotate_api_key_api_error(self, runner, mock_api_client):
        """Test rotating API key when API returns error"""
        from click import ClickException

        mock_api_client.post.side_effect = ClickException("API error: Key not found (404)")

        result = runner.invoke(
            cli, ["baas", "api-keys", "rotate", "nonexistent-key", "--grace-hours", "24"]
        )

        assert result.exit_code != 0
        assert "Key not found" in result.output


class TestUsageCommandGroup:
    """Test Usage command group registration"""

    def test_usage_command_group_exists(self, runner):
        """Test that usage command group is registered"""
        result = runner.invoke(cli, ["baas", "usage", "--help"])
        assert result.exit_code == 0
        assert "Usage tracking commands" in result.output

    def test_usage_stats_command_exists(self, runner):
        """Test that usage stats command is registered"""
        result = runner.invoke(cli, ["baas", "usage", "stats", "--help"])
        assert result.exit_code == 0
        assert "Get usage statistics" in result.output

    def test_usage_by_endpoint_command_exists(self, runner):
        """Test that usage by-endpoint command is registered"""
        result = runner.invoke(cli, ["baas", "usage", "by-endpoint", "--help"])
        assert result.exit_code == 0
        assert "Get usage breakdown by endpoint" in result.output

    def test_usage_by_tenant_command_exists(self, runner):
        """Test that usage by-tenant command is registered"""
        result = runner.invoke(cli, ["baas", "usage", "by-tenant", "--help"])
        assert result.exit_code == 0
        assert "Get usage breakdown by tenant" in result.output


class TestUsageStats:
    """Test usage stats command"""

    def test_usage_stats_success_table_format(self, runner, mock_api_client):
        """Test getting usage stats in table format"""
        mock_data = {
            "total_requests": 1000,
            "success_count": 950,
            "error_count": 50,
            "success_rate": 95.0,
            "avg_response_time_ms": 125.5,
            "total_request_bytes": 5000000,
            "total_response_bytes": 10000000,
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "usage", "stats"])

        assert result.exit_code == 0
        assert "Usage Statistics" in result.output
        assert "1,000" in result.output or "1000" in result.output
        assert "950" in result.output
        assert "50" in result.output
        assert "95.00%" in result.output
        assert "125.50" in result.output
        mock_api_client.get.assert_called_once_with("baas/usage/stats/", params={})

    def test_usage_stats_success_json_format(self, runner, mock_api_client):
        """Test getting usage stats in JSON format"""
        mock_data = {
            "total_requests": 1000,
            "success_count": 950,
            "error_count": 50,
            "success_rate": 95.0,
            "avg_response_time_ms": 125.5,
            "total_request_bytes": 5000000,
            "total_response_bytes": 10000000,
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "usage", "stats", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["total_requests"] == 1000
        assert output_data["success_rate"] == 95.0

    def test_usage_stats_with_api_key_filter(self, runner, mock_api_client):
        """Test usage stats with API key filter"""
        mock_data = {
            "total_requests": 500,
            "success_count": 480,
            "error_count": 20,
            "success_rate": 96.0,
            "avg_response_time_ms": 100.0,
            "total_request_bytes": 2500000,
            "total_response_bytes": 5000000,
        }
        mock_api_client.get.return_value = mock_data
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"

        result = runner.invoke(cli, ["baas", "usage", "stats", "--api-key-id", api_key_id])

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            "baas/usage/stats/", params={"api_key_id": api_key_id}
        )

    def test_usage_stats_with_date_range(self, runner, mock_api_client):
        """Test usage stats with date range"""
        mock_data = {
            "total_requests": 200,
            "success_count": 190,
            "error_count": 10,
            "success_rate": 95.0,
            "avg_response_time_ms": 110.0,
            "total_request_bytes": 1000000,
            "total_response_bytes": 2000000,
        }
        mock_api_client.get.return_value = mock_data
        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-01-31T23:59:59Z"

        result = runner.invoke(
            cli, ["baas", "usage", "stats", "--start-date", start_date, "--end-date", end_date]
        )

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        assert "start_date" in call_args[1]["params"]
        assert "end_date" in call_args[1]["params"]

    def test_usage_stats_invalid_date_format(self, runner):
        """Test usage stats with invalid date format"""
        result = runner.invoke(cli, ["baas", "usage", "stats", "--start-date", "invalid-date"])

        assert result.exit_code != 0
        assert "format" in result.output.lower() or "invalid" in result.output.lower()

    def test_usage_stats_invalid_date_range(self, runner):
        """Test usage stats with invalid date range (start > end)"""
        result = runner.invoke(
            cli,
            [
                "baas",
                "usage",
                "stats",
                "--start-date",
                "2025-12-31T23:59:59Z",
                "--end-date",
                "2025-01-01T00:00:00Z",
            ],
        )

        assert result.exit_code != 0
        assert "before" in result.output.lower() or "range" in result.output.lower()

    def test_usage_stats_invalid_api_key_id_format(self, runner):
        """Test usage stats with invalid API key ID format"""
        result = runner.invoke(cli, ["baas", "usage", "stats", "--api-key-id", "invalid-id"])

        assert result.exit_code != 0
        assert "format" in result.output.lower() or "invalid" in result.output.lower()

    def test_usage_stats_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting usage stats"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ["baas", "usage", "stats"])

        assert result.exit_code != 0
        assert "API error: Connection failed" in result.output


class TestUsageByEndpoint:
    """Test usage by-endpoint command"""

    def test_usage_by_endpoint_success_table_format(self, runner, mock_api_client):
        """Test getting usage by endpoint in table format"""
        mock_data = [
            {
                "endpoint": "/api/v1/assets/",
                "method": "GET",
                "total_requests": 500,
                "success_count": 480,
                "error_count": 20,
                "avg_response_time_ms": 100.5,
            },
            {
                "endpoint": "/api/v1/contracts/",
                "method": "POST",
                "total_requests": 300,
                "success_count": 290,
                "error_count": 10,
                "avg_response_time_ms": 150.0,
            },
        ]
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "usage", "by-endpoint"])

        assert result.exit_code == 0
        assert "/api/v1/assets/" in result.output
        assert "/api/v1/contracts/" in result.output
        assert "GET" in result.output
        assert "POST" in result.output
        assert "500" in result.output
        assert "300" in result.output
        mock_api_client.get.assert_called_once_with("baas/usage/by-endpoint/", params={})

    def test_usage_by_endpoint_success_json_format(self, runner, mock_api_client):
        """Test getting usage by endpoint in JSON format"""
        mock_data = [
            {
                "endpoint": "/api/v1/assets/",
                "method": "GET",
                "total_requests": 500,
                "success_count": 480,
                "error_count": 20,
                "avg_response_time_ms": 100.5,
            }
        ]
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "usage", "by-endpoint", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1
        assert output_data[0]["endpoint"] == "/api/v1/assets/"

    def test_usage_by_endpoint_with_filters(self, runner, mock_api_client):
        """Test usage by endpoint with filters"""
        mock_data = []
        mock_api_client.get.return_value = mock_data
        api_key_id = "123e4567-e89b-12d3-a456-426614174000"
        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-01-31T23:59:59Z"

        result = runner.invoke(
            cli,
            [
                "baas",
                "usage",
                "by-endpoint",
                "--api-key-id",
                api_key_id,
                "--start-date",
                start_date,
                "--end-date",
                end_date,
            ],
        )

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        assert call_args[1]["params"]["api_key_id"] == api_key_id
        assert "start_date" in call_args[1]["params"]
        assert "end_date" in call_args[1]["params"]

    def test_usage_by_endpoint_empty_results(self, runner, mock_api_client):
        """Test usage by endpoint with no results"""
        mock_data = []
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "usage", "by-endpoint"])

        assert result.exit_code == 0
        assert "No usage data found" in result.output

    def test_usage_by_endpoint_invalid_date_format(self, runner):
        """Test usage by endpoint with invalid date format"""
        result = runner.invoke(
            cli, ["baas", "usage", "by-endpoint", "--start-date", "invalid-date"]
        )

        assert result.exit_code != 0
        assert "format" in result.output.lower() or "invalid" in result.output.lower()

    def test_usage_by_endpoint_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting usage by endpoint"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ["baas", "usage", "by-endpoint"])

        assert result.exit_code != 0
        assert "API error: Connection failed" in result.output


class TestUsageByTenant:
    """Test usage by-tenant command"""

    def test_usage_by_tenant_success_table_format(self, runner, mock_api_client):
        """Test getting usage by tenant in table format"""
        mock_data = [
            {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_name": "Test Tenant 1",
                "total_requests": 1000,
                "success_count": 950,
                "error_count": 50,
                "avg_response_time_ms": 120.0,
            },
            {
                "tenant_id": "223e4567-e89b-12d3-a456-426614174000",
                "tenant_name": "Test Tenant 2",
                "total_requests": 500,
                "success_count": 480,
                "error_count": 20,
                "avg_response_time_ms": 110.0,
            },
        ]
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "usage", "by-tenant"])

        assert result.exit_code == 0
        assert "Test Tenant 1" in result.output
        assert "Test Tenant 2" in result.output
        assert "1,000" in result.output or "1000" in result.output
        assert "500" in result.output
        mock_api_client.get.assert_called_once_with("baas/usage/by-tenant/", params={})

    def test_usage_by_tenant_success_json_format(self, runner, mock_api_client):
        """Test getting usage by tenant in JSON format"""
        mock_data = [
            {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_name": "Test Tenant",
                "total_requests": 1000,
                "success_count": 950,
                "error_count": 50,
                "avg_response_time_ms": 120.0,
            }
        ]
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "usage", "by-tenant", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1
        assert output_data[0]["tenant_name"] == "Test Tenant"

    def test_usage_by_tenant_with_date_range(self, runner, mock_api_client):
        """Test usage by tenant with date range"""
        mock_data = []
        mock_api_client.get.return_value = mock_data
        start_date = "2025-01-01T00:00:00Z"
        end_date = "2025-01-31T23:59:59Z"

        result = runner.invoke(
            cli, ["baas", "usage", "by-tenant", "--start-date", start_date, "--end-date", end_date]
        )

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        assert "start_date" in call_args[1]["params"]
        assert "end_date" in call_args[1]["params"]

    def test_usage_by_tenant_empty_results(self, runner, mock_api_client):
        """Test usage by tenant with no results"""
        mock_data = []
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["baas", "usage", "by-tenant"])

        assert result.exit_code == 0
        assert "No usage data found" in result.output

    def test_usage_by_tenant_invalid_date_format(self, runner):
        """Test usage by tenant with invalid date format"""
        result = runner.invoke(cli, ["baas", "usage", "by-tenant", "--start-date", "invalid-date"])

        assert result.exit_code != 0
        assert "format" in result.output.lower() or "invalid" in result.output.lower()

    def test_usage_by_tenant_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting usage by tenant"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ["baas", "usage", "by-tenant"])

        assert result.exit_code != 0
        assert "API error: Connection failed" in result.output
