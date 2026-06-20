"""
Unit tests for Scheduled Ingestion CLI commands.

Tests: list, get, create, update, delete, pause, resume, trigger, history, logs, status commands.
"""

from datahub_cli.main import cli


class TestScheduledIngestionList:
    """Test scheduled-ingestion list command"""

    def test_list_ingestions(self, runner, mock_api_client):
        """Test listing scheduled ingestions"""
        mock_api_client.get.return_value = {
            "results": [
                {
                    "id": "ing-1",
                    "name": "Hourly import",
                    "source_type": "S3",
                    "status": "ACTIVE",
                    "next_run_at": "2026-06-15T00:00:00Z",
                }
            ]
        }

        result = runner.invoke(cli, ["scheduled-ingestion", "list"])

        assert result.exit_code == 0
        assert "Hourly import" in result.output

    def test_list_ingestions_empty(self, runner, mock_api_client):
        """Test listing when no ingestions exist"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["scheduled-ingestion", "list"])

        assert result.exit_code == 0
        assert "No scheduled" in result.output.lower()

    def test_list_ingestions_with_status_filter(self, runner, mock_api_client):
        """Test listing with status filter"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["scheduled-ingestion", "list", "--status", "ERROR"])

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        assert call_args[1]["params"]["status"] == "ERROR"


class TestScheduledIngestionGet:
    """Test scheduled-ingestion get command"""

    def test_get_ingestion(self, runner, mock_api_client):
        """Test getting ingestion details"""
        mock_api_client.get.return_value = {
            "id": "ing-1",
            "name": "Hourly import",
            "status": "ACTIVE",
            "source_config": {"bucket": "data-lake"},
        }

        result = runner.invoke(cli, ["scheduled-ingestion", "get", "ing-1"])

        assert result.exit_code == 0
        assert "Hourly import" in result.output
        mock_api_client.get.assert_called_once_with("scheduled-ingestions/ing-1/")

    def test_get_ingestion_not_found(self, runner, mock_api_client):
        """Test getting non-existent ingestion"""
        mock_api_client.get.side_effect = Exception("Not found")

        result = runner.invoke(cli, ["scheduled-ingestion", "get", "nonexistent"])

        assert result.exit_code != 0


class TestScheduledIngestionCreate:
    """Test scheduled-ingestion create command"""

    def test_create_ingestion(self, runner, mock_api_client):
        """Test creating a scheduled ingestion"""
        mock_api_client.post.return_value = {
            "id": "ing-new",
            "name": "Daily CSV import",
            "status": "ACTIVE",
        }

        result = runner.invoke(
            cli,
            [
                "scheduled-ingestion",
                "create",
                "--name",
                "Daily CSV import",
                "--source-type",
                "S3",
                "--source-config",
                '{"bucket":"data-lake","prefix":"daily/"}',
                "--cron-expression",
                "0 6 * * *",
            ],
        )

        assert result.exit_code == 0
        assert "Daily CSV import" in result.output

    def test_create_ingestion_with_destination(self, runner, mock_api_client):
        """Test creating ingestion with destination dataset"""
        mock_api_client.post.return_value = {"id": "ing-new", "status": "ACTIVE"}

        result = runner.invoke(
            cli,
            [
                "scheduled-ingestion",
                "create",
                "--name",
                "Import to dataset",
                "--source-type",
                "HTTP",
                "--source-config",
                '{"url":"https://example.com/data.csv"}',
                "--cron-expression",
                "0 */6 * * *",
                "--destination-dataset-id",
                "ds-1",
            ],
        )

        assert result.exit_code == 0

    def test_create_ingestion_error(self, runner, mock_api_client):
        """Test create with validation error"""
        mock_api_client.post.side_effect = Exception("Invalid cron expression")

        result = runner.invoke(
            cli,
            [
                "scheduled-ingestion",
                "create",
                "--name",
                "Bad",
                "--source-type",
                "S3",
                "--source-config",
                "{}",
                "--cron-expression",
                "bad",
            ],
        )

        assert result.exit_code != 0


class TestScheduledIngestionControl:
    """Test pause, resume, trigger-run commands"""

    def test_pause_ingestion(self, runner, mock_api_client):
        """Test pausing an ingestion"""
        mock_api_client.post.return_value = {"status": "PAUSED"}

        result = runner.invoke(cli, ["scheduled-ingestion", "pause", "ing-1"])

        assert result.exit_code == 0
        assert "PAUSED" in result.output

    def test_resume_ingestion(self, runner, mock_api_client):
        """Test resuming an ingestion"""
        mock_api_client.post.return_value = {"status": "ACTIVE"}

        result = runner.invoke(cli, ["scheduled-ingestion", "resume", "ing-1"])

        assert result.exit_code == 0
        assert "ACTIVE" in result.output

    def test_trigger_run(self, runner, mock_api_client):
        """Test triggering an immediate ingestion run"""
        mock_api_client.post.return_value = {"id": "run-1", "status": "RUNNING"}

        result = runner.invoke(cli, ["scheduled-ingestion", "trigger-run", "ing-1"])

        assert result.exit_code == 0
        assert "run-1" in result.output


class TestScheduledIngestionHistory:
    """Test history and logs commands"""

    def test_history(self, runner, mock_api_client):
        """Test viewing ingestion run history"""
        mock_api_client.get.return_value = {
            "results": [
                {"id": "run-1", "status": "COMPLETED", "started_at": "2026-06-14T00:00:00Z"},
                {"id": "run-2", "status": "FAILED", "started_at": "2026-06-13T00:00:00Z"},
            ]
        }

        result = runner.invoke(cli, ["scheduled-ingestion", "history", "ing-1"])

        assert result.exit_code == 0
        assert "COMPLETED" in result.output

    def test_logs(self, runner, mock_api_client):
        """Test viewing ingestion run logs"""
        mock_api_client.get.return_value = {
            "run_id": "run-1",
            "logs": "Starting ingestion...\nProcessing 100 rows\nComplete",
        }

        result = runner.invoke(cli, ["scheduled-ingestion", "logs", "run-1"])

        assert result.exit_code == 0
        assert "Processing" in result.output


class TestScheduledIngestionDelete:
    """Test delete command"""

    def test_delete_ingestion(self, runner, mock_api_client):
        """Test deleting an ingestion"""
        result = runner.invoke(cli, ["scheduled-ingestion", "delete", "ing-1"])

        assert result.exit_code == 0
        mock_api_client.delete.assert_called()
