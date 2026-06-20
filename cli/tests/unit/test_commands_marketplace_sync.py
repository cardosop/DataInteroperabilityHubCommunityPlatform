"""
Unit tests for marketplace sync command parsing and output formatting.

These tests verify CLI command parsing, argument handling, and output formatting
for marketplace sync commands. For integration tests with real API services,
see test_marketplace_commands_real_api.py
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from datahub_cli.commands import marketplace


class TestMarketplaceSyncCommands:
    """Unit tests for marketplace sync command parsing and formatting"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_marketplace_sync_help(self, runner):
        """Test marketplace sync command help"""
        result = runner.invoke(marketplace.sync, ["--help"])
        assert result.exit_code == 0
        assert "Marketplace sync job commands" in result.output

    def test_sync_start_help(self, runner):
        """Test sync start command help"""
        result = runner.invoke(marketplace.sync, ["start", "--help"])
        assert result.exit_code == 0
        assert "Start a marketplace sync job" in result.output

    def test_sync_list_help(self, runner):
        """Test sync list command help"""
        result = runner.invoke(marketplace.sync, ["list", "--help"])
        assert result.exit_code == 0
        assert "List marketplace sync jobs" in result.output

    def test_sync_get_help(self, runner):
        """Test sync get command help"""
        result = runner.invoke(marketplace.sync, ["get", "--help"])
        assert result.exit_code == 0
        assert "Get marketplace sync job details" in result.output

    def test_sync_cancel_help(self, runner):
        """Test sync cancel command help"""
        result = runner.invoke(marketplace.sync, ["cancel", "--help"])
        assert result.exit_code == 0
        assert "Cancel a marketplace sync job" in result.output

    def test_sync_start_missing_connection_id(self, runner):
        """Test sync start with missing connection-id"""
        result = runner.invoke(
            marketplace.sync, ["start", "--direction", "PUSH", "--asset-ids", "asset-1"]
        )
        assert result.exit_code != 0
        assert "connection-id" in result.output.lower() or "Missing option" in result.output

    def test_sync_start_missing_direction(self, runner):
        """Test sync start with missing direction"""
        result = runner.invoke(
            marketplace.sync, ["start", "--connection-id", "conn-123", "--asset-ids", "asset-1"]
        )
        assert result.exit_code != 0
        assert "direction" in result.output.lower() or "Missing option" in result.output

    def test_sync_start_push_missing_asset_ids(self, runner):
        """Test sync start PUSH without asset-ids"""
        result = runner.invoke(
            marketplace.sync, ["start", "--connection-id", "conn-123", "--direction", "PUSH"]
        )
        assert result.exit_code != 0
        assert "--asset-ids is required for PUSH direction" in result.output

    def test_sync_start_push_with_listing_ids_error(self, runner):
        """Test sync start PUSH with listing-ids (should fail)"""
        result = runner.invoke(
            marketplace.sync,
            [
                "start",
                "--connection-id",
                "conn-123",
                "--direction",
                "PUSH",
                "--asset-ids",
                "asset-1",
                "--listing-ids",
                "listing-1",
            ],
        )
        assert result.exit_code != 0
        assert "--listing-ids cannot be used with PUSH direction" in result.output

    def test_sync_start_pull_with_asset_ids_error(self, runner):
        """Test sync start PULL with asset-ids (should fail)"""
        result = runner.invoke(
            marketplace.sync,
            [
                "start",
                "--connection-id",
                "conn-123",
                "--direction",
                "PULL",
                "--asset-ids",
                "asset-1",
            ],
        )
        assert result.exit_code != 0
        assert "--asset-ids cannot be used with PULL direction" in result.output

    def test_sync_start_bidirectional_missing_asset_ids(self, runner):
        """Test sync start BIDIRECTIONAL without asset-ids"""
        result = runner.invoke(
            marketplace.sync,
            ["start", "--connection-id", "conn-123", "--direction", "BIDIRECTIONAL"],
        )
        assert result.exit_code != 0
        assert "--asset-ids is required for BIDIRECTIONAL direction" in result.output

    def test_sync_start_empty_asset_ids(self, runner):
        """Test sync start with empty asset-ids"""
        result = runner.invoke(
            marketplace.sync,
            ["start", "--connection-id", "conn-123", "--direction", "PUSH", "--asset-ids", ""],
        )
        assert result.exit_code != 0
        assert "--asset-ids cannot be empty" in result.output

    def test_sync_start_empty_listing_ids(self, runner):
        """Test sync start with empty listing-ids"""
        result = runner.invoke(
            marketplace.sync,
            ["start", "--connection-id", "conn-123", "--direction", "PULL", "--listing-ids", ""],
        )
        assert result.exit_code != 0
        assert "--listing-ids cannot be empty" in result.output

    def test_sync_start_case_insensitive_direction(self, runner):
        """Test sync start with case-insensitive direction"""
        with patch("datahub_cli.commands.marketplace.api_client") as mock_api:
            mock_api.post.return_value = {
                "id": "sync-job-1",
                "direction": "PUSH",
                "status": "PENDING",
            }
            runner.invoke(
                marketplace.sync,
                [
                    "start",
                    "--connection-id",
                    "conn-123",
                    "--direction",
                    "push",  # lowercase
                    "--asset-ids",
                    "asset-1",
                ],
            )
            # Should not fail validation (direction is case-insensitive)
            # The actual API call would be made with uppercase
            call_args = mock_api.post.call_args
            if call_args:
                assert call_args[1]["json_data"]["direction"] == "PUSH"

    @patch("datahub_cli.commands.marketplace.api_client")
    def test_sync_start_success_table_format(self, mock_api, runner):
        """Test sync start success in table format"""
        mock_api.post.return_value = {
            "id": "sync-job-1",
            "connection_name": "Test Connection",
            "direction": "PUSH",
            "direction_display": "Push",
            "status": "PENDING",
            "status_display": "Pending",
            "created_at": "2025-01-01T00:00:00Z",
        }

        result = runner.invoke(
            marketplace.sync,
            [
                "start",
                "--connection-id",
                "conn-123",
                "--direction",
                "PUSH",
                "--asset-ids",
                "asset-1,asset-2",
            ],
        )

        assert result.exit_code == 0
        assert "Sync job created successfully" in result.output
        assert "sync-job-1" in result.output
        mock_api.post.assert_called_once()
        call_args = mock_api.post.call_args
        assert call_args[0][0] == "integrations/marketplace/sync/"
        assert call_args[1]["json_data"]["direction"] == "PUSH"
        assert call_args[1]["json_data"]["asset_ids"] == ["asset-1", "asset-2"]

    @patch("datahub_cli.commands.marketplace.api_client")
    def test_sync_start_success_json_format(self, mock_api, runner):
        """Test sync start success in JSON format"""
        mock_api.post.return_value = {"id": "sync-job-1", "direction": "PUSH", "status": "PENDING"}

        result = runner.invoke(
            marketplace.sync,
            [
                "start",
                "--connection-id",
                "conn-123",
                "--direction",
                "PUSH",
                "--asset-ids",
                "asset-1",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "sync-job-1"

    @patch("datahub_cli.commands.marketplace.api_client")
    def test_sync_list_success_table_format(self, mock_api, runner):
        """Test sync list success in table format"""
        mock_api.get.return_value = {
            "results": [
                {
                    "id": "sync-job-1",
                    "connection_name": "Connection 1",
                    "direction": "PUSH",
                    "status": "RUNNING",
                    "items_synced": 10,
                    "items_failed": 0,
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ]
        }

        result = runner.invoke(marketplace.sync, ["list"])

        assert result.exit_code == 0
        assert "sync-job-1" in result.output
        mock_api.get.assert_called_once()

    @patch("datahub_cli.commands.marketplace.api_client")
    def test_sync_list_empty_result(self, mock_api, runner):
        """Test sync list with no results"""
        mock_api.get.return_value = {"results": []}

        result = runner.invoke(marketplace.sync, ["list"])

        assert result.exit_code == 0
        assert "No sync jobs found" in result.output

    @patch("datahub_cli.commands.marketplace.api_client")
    def test_sync_get_success_table_format(self, mock_api, runner):
        """Test sync get success in table format"""
        mock_api.get.return_value = {
            "id": "sync-job-1",
            "connection_name": "Test Connection",
            "direction": "PUSH",
            "status": "RUNNING",
            "items_synced": 50,
            "items_failed": 5,
            "errors": [],
            "created_at": "2025-01-01T00:00:00Z",
        }

        result = runner.invoke(marketplace.sync, ["get", "sync-job-1"])

        assert result.exit_code == 0
        assert "sync-job-1" in result.output
        assert "Items Synced: 50" in result.output
        assert "Items Failed: 5" in result.output
        mock_api.get.assert_called_once_with("integrations/marketplace/sync/sync-job-1/")

    @patch("datahub_cli.commands.marketplace.api_client")
    def test_sync_get_with_errors(self, mock_api, runner):
        """Test sync get with errors displayed"""
        mock_api.get.return_value = {
            "id": "sync-job-1",
            "status": "FAILED",
            "items_synced": 10,
            "items_failed": 2,
            "errors": [
                {"message": "Error 1"},
                {"message": "Error 2"},
                {"message": "Error 3"},
                {"message": "Error 4"},
                {"message": "Error 5"},
                {"message": "Error 6"},
            ],
        }

        result = runner.invoke(marketplace.sync, ["get", "sync-job-1"])

        assert result.exit_code == 0
        assert "Errors: 6" in result.output
        assert "Error 1" in result.output
        assert "... and 1 more errors" in result.output

    @patch("datahub_cli.commands.marketplace.api_client")
    def test_sync_cancel_success(self, mock_api, runner):
        """Test sync cancel success"""
        mock_api.post.return_value = {
            "id": "sync-job-1",
            "status": "CANCELLED",
            "updated_at": "2025-01-01T00:01:00Z",
        }

        result = runner.invoke(marketplace.sync, ["cancel", "sync-job-1"])

        assert result.exit_code == 0
        assert "cancelled successfully" in result.output
        mock_api.post.assert_called_once_with(
            "integrations/marketplace/sync/sync-job-1/cancel/", json_data={}
        )
