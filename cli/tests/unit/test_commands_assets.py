"""
Comprehensive unit tests for assets CLI commands.

Tests all asset commands: list, get, create, update, delete, activate.
"""

import json
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from datahub_cli.main import cli


class TestAssetsList:
    """Test assets list command"""

    def test_list_assets_success_table_format(self, runner, mock_api_client):
        """Test listing assets in table format"""
        mock_data = {
            "results": [
                {"id": "asset-1", "name": "Test Asset 1", "status": "ACTIVE", "domain": "domain1"},
                {"id": "asset-2", "name": "Test Asset 2", "status": "DRAFT", "domain": "domain2"},
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code == 0
        assert "asset-1" in result.output
        assert "asset-2" in result.output
        assert "ACTIVE" in result.output
        assert "DRAFT" in result.output
        mock_api_client.get.assert_called_once_with("assets/", params={"limit": 20, "offset": 0})

    def test_list_assets_success_json_format(self, runner, mock_api_client):
        """Test listing assets in JSON format"""
        mock_data = {"results": [{"id": "asset-1", "name": "Test Asset", "status": "ACTIVE"}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["assets", "list", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1

    def test_list_assets_with_filters(self, runner, mock_api_client):
        """Test listing assets with status and domain filters"""
        mock_data = {"results": []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(
            cli,
            [
                "assets",
                "list",
                "--status",
                "ACTIVE",
                "--domain",
                "domain1",
                "--limit",
                "10",
                "--offset",
                "5",
            ],
        )

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            "assets/", params={"status": "ACTIVE", "domain": "domain1", "limit": 10, "offset": 5}
        )

    def test_list_assets_empty_result(self, runner, mock_api_client):
        """Test listing assets when no assets exist"""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code == 0
        assert "No assets found" in result.output

    def test_list_assets_with_non_dict_items(self, runner, mock_api_client):
        """Test listing assets when response contains non-dict items (edge case)"""
        # Test the isinstance check that skips non-dict items
        mock_data = {
            "results": [
                {"id": "asset-1", "name": "Test Asset", "status": "ACTIVE"},
                "invalid-item",  # Non-dict item
                {"id": "asset-2", "name": "Test Asset 2", "status": "DRAFT"},
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code == 0
        assert "asset-1" in result.output
        assert "asset-2" in result.output
        # Invalid item should be skipped

    def test_list_assets_unexpected_response_type(self, runner, mock_api_client):
        """Test listing assets with unexpected response type (not dict or list)"""
        # Test edge case where API returns something unexpected
        mock_api_client.get.return_value = None

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code == 0
        assert "No assets found" in result.output

    def test_list_assets_api_error(self, runner, mock_api_client):
        """Test handling API errors when listing assets"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code != 0
        assert "Failed to list assets" in result.output or "API error" in result.output


class TestAssetsGet:
    """Test assets get command"""

    def test_get_asset_success_table_format(self, runner, mock_api_client):
        """Test getting an asset in table format"""
        mock_data = {
            "id": "asset-1",
            "name": "Test Asset",
            "key": "test-asset",
            "status": "ACTIVE",
            "domain": "domain1",
            "visibility": "INTERNAL",
            "description": "Test description",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["assets", "get", "asset-1"])

        assert result.exit_code == 0
        assert "asset-1" in result.output
        assert "Test Asset" in result.output
        assert "ACTIVE" in result.output
        mock_api_client.get.assert_called_once_with("assets/asset-1/", params={})

    def test_get_asset_with_include(self, runner, mock_api_client):
        """Test getting an asset with include parameter"""
        mock_data = {"id": "asset-1", "name": "Test Asset"}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["assets", "get", "asset-1", "--include", "contract,datasets"])

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            "assets/asset-1/", params={"include": "contract,datasets"}
        )

    def test_get_asset_success_json_format(self, runner, mock_api_client):
        """Test getting an asset in JSON format"""
        mock_data = {"id": "asset-1", "name": "Test Asset", "status": "ACTIVE"}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["assets", "get", "asset-1", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "asset-1"

    def test_get_asset_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting an asset"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("API error: Not found")

        result = runner.invoke(cli, ["assets", "get", "asset-1"])

        assert result.exit_code != 0
        assert "Failed to get asset" in result.output or "API error" in result.output


class TestAssetsCreate:
    """Test assets create command"""

    def test_create_asset_success_table_format(self, runner, mock_api_client):
        """Test creating an asset in table format"""
        mock_result = {"id": "asset-1", "name": "Test Asset", "status": "DRAFT"}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(
            cli, ["assets", "create", "--name", "Test Asset", "--key", "test-asset"]
        )

        assert result.exit_code == 0
        assert "Asset created successfully" in result.output
        assert "asset-1" in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == "assets/"
        assert call_args[1]["json_data"]["name"] == "Test Asset"
        assert call_args[1]["json_data"]["key"] == "test-asset"
        assert call_args[1]["json_data"]["visibility"] == "INTERNAL"

    def test_create_asset_with_all_options(self, runner, mock_api_client):
        """Test creating an asset with all options"""
        mock_result = {"id": "asset-1", "name": "Test Asset", "status": "DRAFT"}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Test Asset",
                "--key",
                "test-asset",
                "--description",
                "Test description",
                "--domain",
                "domain1",
                "--visibility",
                "PUBLIC",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["description"] == "Test description"
        assert json_data["domain"] == "domain1"
        assert json_data["visibility"] == "PUBLIC"

    def test_create_asset_json_output(self, runner, mock_api_client):
        """Test creating an asset with JSON output"""
        mock_result = {"id": "asset-1", "name": "Test Asset", "status": "DRAFT"}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(
            cli,
            ["assets", "create", "--name", "Test Asset", "--key", "test-asset", "--format", "json"],
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "asset-1"

    def test_create_asset_api_error(self, runner, mock_api_client):
        """Test handling API errors when creating an asset"""
        from click import ClickException

        mock_api_client.post.side_effect = ClickException("API error: Validation failed")

        result = runner.invoke(
            cli, ["assets", "create", "--name", "Test Asset", "--key", "test-asset"]
        )

        assert result.exit_code != 0
        assert "Failed to create asset" in result.output or "API error" in result.output


class TestAssetsUpdate:
    """Test assets update command"""

    def test_update_asset_success_table_format(self, runner, mock_api_client):
        """Test updating an asset in table format"""
        mock_result = {"id": "asset-1", "name": "Updated Asset"}
        mock_api_client.patch.return_value = mock_result

        result = runner.invoke(cli, ["assets", "update", "asset-1", "--name", "Updated Asset"])

        assert result.exit_code == 0
        assert "Asset updated successfully" in result.output
        mock_api_client.patch.assert_called_once()
        call_args = mock_api_client.patch.call_args
        assert call_args[0][0] == "assets/asset-1/"
        assert call_args[1]["json_data"]["name"] == "Updated Asset"

    def test_update_asset_multiple_fields(self, runner, mock_api_client):
        """Test updating an asset with multiple fields"""
        mock_result = {"id": "asset-1", "name": "Updated Asset"}
        mock_api_client.patch.return_value = mock_result

        result = runner.invoke(
            cli,
            [
                "assets",
                "update",
                "asset-1",
                "--name",
                "Updated Asset",
                "--description",
                "Updated description",
                "--domain",
                "new-domain",
                "--visibility",
                "PUBLIC",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_api_client.patch.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "Updated Asset"
        assert json_data["description"] == "Updated description"
        assert json_data["domain"] == "new-domain"
        assert json_data["visibility"] == "PUBLIC"

    def test_update_asset_no_fields(self, runner):
        """Test updating an asset with no fields specified"""
        result = runner.invoke(cli, ["assets", "update", "asset-1"])

        assert result.exit_code != 0
        assert "No fields to update" in result.output

    def test_update_asset_json_output(self, runner, mock_api_client):
        """Test updating an asset with JSON output"""
        mock_result = {"id": "asset-1", "name": "Updated Asset"}
        mock_api_client.patch.return_value = mock_result

        result = runner.invoke(
            cli, ["assets", "update", "asset-1", "--name", "Updated Asset", "--format", "json"]
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "asset-1"

    def test_update_asset_api_error(self, runner, mock_api_client):
        """Test handling API errors when updating an asset"""
        from click import ClickException

        mock_api_client.patch.side_effect = ClickException("API error: Not found")

        result = runner.invoke(cli, ["assets", "update", "asset-1", "--name", "Updated Asset"])

        assert result.exit_code != 0
        assert "Failed to update asset" in result.output or "API error" in result.output


class TestAssetsDelete:
    """Test assets delete command"""

    def test_delete_asset_with_confirm_flag(self, runner, mock_api_client):
        """Test deleting an asset with --confirm flag"""
        mock_api_client.delete.return_value = {}

        result = runner.invoke(cli, ["assets", "delete", "asset-1", "--confirm"])

        assert result.exit_code == 0
        assert "deleted successfully" in result.output
        mock_api_client.delete.assert_called_once_with("assets/asset-1/")

    def test_delete_asset_with_confirmation_prompt(self, runner, mock_api_client):
        """Test deleting an asset with confirmation prompt"""
        mock_api_client.delete.return_value = {}

        result = runner.invoke(cli, ["assets", "delete", "asset-1"], input="y\n")

        assert result.exit_code == 0
        assert "deleted successfully" in result.output

    def test_delete_asset_cancelled(self, runner, mock_api_client):
        """Test cancelling asset deletion"""
        result = runner.invoke(cli, ["assets", "delete", "asset-1"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        mock_api_client.delete.assert_not_called()

    def test_delete_asset_api_error(self, runner, mock_api_client):
        """Test handling API errors when deleting an asset"""
        from click import ClickException

        mock_api_client.delete.side_effect = ClickException("API error: Not found")

        result = runner.invoke(cli, ["assets", "delete", "asset-1", "--confirm"])

        assert result.exit_code != 0
        assert "Failed to delete asset" in result.output or "API error" in result.output


class TestAssetsActivate:
    """Test assets activate command"""

    def test_activate_asset_success_table_format(self, runner, mock_api_client):
        """Test activating an asset in table format"""
        mock_result = {"id": "asset-1", "status": "ACTIVE"}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ["assets", "activate", "asset-1"])

        assert result.exit_code == 0
        assert "Asset activated successfully" in result.output
        assert "ACTIVE" in result.output
        mock_api_client.post.assert_called_once_with(
            "assets/asset-1/activate/",
            json_data={"version": mock_api_client.get.return_value.get.return_value},
        )

    def test_activate_asset_json_output(self, runner, mock_api_client):
        """Test activating an asset with JSON output"""
        mock_result = {"id": "asset-1", "status": "ACTIVE"}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ["assets", "activate", "asset-1", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["status"] == "ACTIVE"

    def test_activate_asset_api_error(self, runner, mock_api_client):
        """Test handling API errors when activating an asset"""
        from click import ClickException

        mock_api_client.post.side_effect = ClickException("API error: Not found")

        result = runner.invoke(cli, ["assets", "activate", "asset-1"])

        assert result.exit_code != 0
        assert "Failed to activate asset" in result.output or "API error" in result.output


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock API client"""
    mock_client = Mock()
    monkeypatch.setattr("datahub_cli.commands.assets.api_client", mock_client)
    return mock_client
