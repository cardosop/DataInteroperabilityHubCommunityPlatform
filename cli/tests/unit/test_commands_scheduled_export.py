"""
Unit tests for Scheduled Export CLI commands.

Tests: list, get, create, update, delete, pause, resume, trigger-run commands.
"""

import json

from datahub_cli.main import cli


class TestScheduledExportList:
    """Test scheduled-export list command"""

    def test_list_exports(self, runner, mock_api_client):
        """Test listing scheduled exports"""
        mock_api_client.get.return_value = {
            "results": [
                {
                    "id": "export-1",
                    "name": "Daily CSV",
                    "destination_type": "S3",
                    "status": "ACTIVE",
                    "next_run_at": "2026-06-15T00:00:00Z",
                }
            ]
        }

        result = runner.invoke(cli, ["scheduled-export", "list"])

        assert result.exit_code == 0
        assert "Daily CSV" in result.output
        mock_api_client.get.assert_called_once_with(
            "scheduled-exports/", params={"limit": 20, "offset": 0}
        )

    def test_list_exports_empty(self, runner, mock_api_client):
        """Test listing when no exports exist"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["scheduled-export", "list"])

        assert result.exit_code == 0
        assert "No scheduled exports" in result.output

    def test_list_exports_with_filter(self, runner, mock_api_client):
        """Test listing with status filter"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["scheduled-export", "list", "--status", "ACTIVE"])

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        assert call_args[1]["params"]["status"] == "ACTIVE"


class TestScheduledExportGet:
    """Test scheduled-export get command"""

    def test_get_export(self, runner, mock_api_client):
        """Test getting export details"""
        mock_api_client.get.return_value = {
            "id": "export-1",
            "name": "Daily CSV",
            "status": "ACTIVE",
        }

        result = runner.invoke(cli, ["scheduled-export", "get", "export-1"])

        assert result.exit_code == 0
        assert "Daily CSV" in result.output

    def test_get_export_json(self, runner, mock_api_client):
        """Test getting export in JSON"""
        mock_api_client.get.return_value = {"id": "export-1", "name": "Daily CSV"}

        result = runner.invoke(cli, ["scheduled-export", "get", "export-1", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "export-1"


class TestScheduledExportCreate:
    """Test scheduled-export create command"""

    def test_create_export(self, runner, mock_api_client):
        """Test creating a scheduled export"""
        mock_api_client.post.return_value = {
            "id": "export-new",
            "name": "Weekly backup",
            "status": "ACTIVE",
        }

        result = runner.invoke(
            cli,
            [
                "scheduled-export",
                "create",
                "--name",
                "Weekly backup",
                "--asset-id",
                "asset-1",
                "--destination-type",
                "S3",
                "--destination-config",
                '{"bucket":"my-bucket"}',
                "--cron-expression",
                "0 0 * * 0",
            ],
        )

        assert result.exit_code == 0
        assert "Weekly backup" in result.output

    def test_create_export_error(self, runner, mock_api_client):
        """Test create with API error"""
        mock_api_client.post.side_effect = Exception("Validation error")

        result = runner.invoke(
            cli,
            [
                "scheduled-export",
                "create",
                "--name",
                "Bad export",
                "--asset-id",
                "bad-id",
                "--destination-type",
                "S3",
                "--destination-config",
                "{}",
                "--cron-expression",
                "invalid",
            ],
        )

        assert result.exit_code != 0


class TestScheduledExportPauseResume:
    """Test scheduled-export pause and resume commands"""

    def test_pause_export(self, runner, mock_api_client):
        """Test pausing an export"""
        mock_api_client.post.return_value = {"status": "PAUSED"}

        result = runner.invoke(cli, ["scheduled-export", "pause", "export-1"])

        assert result.exit_code == 0
        assert "PAUSED" in result.output

    def test_resume_export(self, runner, mock_api_client):
        """Test resuming an export"""
        mock_api_client.post.return_value = {"status": "ACTIVE"}

        result = runner.invoke(cli, ["scheduled-export", "resume", "export-1"])

        assert result.exit_code == 0
        assert "ACTIVE" in result.output


class TestScheduledExportTrigger:
    """Test scheduled-export trigger-run command"""

    def test_trigger_run(self, runner, mock_api_client):
        """Test triggering an immediate export run"""
        mock_api_client.post.return_value = {"id": "run-1", "status": "RUNNING"}

        result = runner.invoke(cli, ["scheduled-export", "trigger-run", "export-1"])

        assert result.exit_code == 0
        assert "run-1" in result.output


class TestScheduledExportDelete:
    """Test scheduled-export delete command"""

    def test_delete_export(self, runner, mock_api_client):
        """Test deleting a scheduled export"""
        result = runner.invoke(cli, ["scheduled-export", "delete", "export-1"])

        assert result.exit_code == 0
        mock_api_client.delete.assert_called()
