"""
Unit tests for DQ CLI commands.

Tests: run, get, list, alerts commands.

The backend (hub/apps/dq/urls.py) exposes only ``runs``, ``alerting-rules``
and ``quality`` — there is no ``rules`` endpoint and no ``list-runs``
subcommand; ``dq list`` lists runs and ``dq alerts --list`` lists rules.
"""

import json

from datahub_cli.main import cli
from tests.fixtures.test_data import fresh_id

# Unique per test process (and per xdist worker) so a static literal
# can never collide across parallel runs — Phase 216.X.2.
ASSET_ID = fresh_id("asset")


class TestDQRun:
    """Test dq run command"""

    def test_run_dq_on_asset(self, runner, mock_api_client):
        """Test running DQ check on an asset"""
        mock_api_client.post.return_value = {
            "id": "dq-run-1",
            "status": "PENDING",
            "profile_key": "intake_basic_gx",
            "job": "job-1",
        }

        result = runner.invoke(cli, ["dq", "run", "--asset-id", ASSET_ID])

        assert result.exit_code == 0
        assert "dq-run-1" in result.output
        assert "PENDING" in result.output
        mock_api_client.post.assert_called_once_with(
            "dq/runs/", json_data={"profile_key": "intake_basic_gx", "asset_id": ASSET_ID}
        )

    def test_run_dq_on_dataset(self, runner, mock_api_client):
        """Test running DQ check on a dataset"""
        mock_api_client.post.return_value = {
            "id": "dq-run-2",
            "status": "RUNNING",
            "profile_key": "basic",
        }

        result = runner.invoke(cli, ["dq", "run", "--dataset-id", "ds-1", "--profile-key", "basic"])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]["json_data"]["dataset_id"] == "ds-1"
        assert call_args[1]["json_data"]["profile_key"] == "basic"

    def test_run_dq_json_format(self, runner, mock_api_client):
        """Test run with JSON output"""
        mock_api_client.post.return_value = {"id": "dq-run-3", "status": "COMPLETED"}

        result = runner.invoke(cli, ["dq", "run", "--asset-id", ASSET_ID, "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "dq-run-3"

    def test_run_dq_no_target(self, runner, mock_api_client):
        """Test run without asset/dataset/file raises error"""
        result = runner.invoke(cli, ["dq", "run"])

        assert result.exit_code != 0
        assert "At least one of" in result.output

    def test_run_dq_api_error(self, runner, mock_api_client):
        """Test run handles API error"""
        mock_api_client.post.side_effect = Exception("Service unavailable")

        result = runner.invoke(cli, ["dq", "run", "--asset-id", ASSET_ID])

        assert result.exit_code != 0
        assert "Failed to run DQ check" in result.output


class TestDQGet:
    """Test dq get command"""

    def test_get_dq_run(self, runner, mock_api_client):
        """Test getting DQ run details"""
        mock_api_client.get.return_value = {
            "id": "dq-run-1",
            "status": "COMPLETED",
            "profile_key": "intake_basic_gx",
        }

        result = runner.invoke(cli, ["dq", "get", "dq-run-1"])

        assert result.exit_code == 0
        assert "dq-run-1" in result.output
        mock_api_client.get.assert_called_once_with("dq/runs/dq-run-1/")

    def test_get_dq_run_json(self, runner, mock_api_client):
        """Test getting DQ run in JSON format"""
        mock_api_client.get.return_value = {"id": "dq-run-1", "status": "COMPLETED"}

        result = runner.invoke(cli, ["dq", "get", "dq-run-1", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "dq-run-1"

    def test_get_dq_run_not_found(self, runner, mock_api_client):
        """Test getting non-existent DQ run"""
        mock_api_client.get.side_effect = Exception("Not found")

        result = runner.invoke(cli, ["dq", "get", "nonexistent"])

        assert result.exit_code != 0


class TestDQList:
    """Test dq list commands"""

    def test_list_rules(self, runner, mock_api_client):
        """Test listing DQ alerting rules"""
        mock_api_client.get.return_value = {
            "results": [
                {"id": "rule-1", "asset_id": ASSET_ID, "threshold": 80.0, "status": "ACTIVE"}
            ]
        }

        result = runner.invoke(cli, ["dq", "alerts", "--list"])

        assert result.exit_code == 0
        assert "rule-1" in result.output
        mock_api_client.get.assert_called_once_with("dq/alerting-rules/")

    def test_list_runs(self, runner, mock_api_client):
        """Test listing DQ runs"""
        mock_api_client.get.return_value = {"results": [{"id": "dq-run-1", "status": "COMPLETED"}]}

        result = runner.invoke(cli, ["dq", "list"])

        assert result.exit_code == 0
        assert "dq-run-1" in result.output
        mock_api_client.get.assert_called_once_with("dq/runs/", params={"limit": 20, "offset": 0})
