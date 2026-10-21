"""Unit tests for the Databricks `dlt` CLI commands (openspec
add-databricks-dlt-pipelines task 10.7).

The commands ride the SAME API surface as the DLT page (design D7) —
every pin asserts the EXACT endpoint and the exact payload the view
expects (the 9-3-c lesson: the mock asserts the real contract, not a
shape the backend would refuse).
"""

import json

from click.testing import CliRunner
from datahub_cli.main import cli


def _run(*args):
    runner = CliRunner()
    return runner.invoke(cli, ["databricks", "dlt", *args])


class TestDltList:
    def test_list_renders_the_mirror_rows(self, mock_api_client):
        mock_api_client.get.return_value = {
            "results": [
                {
                    "id": "row-1",
                    "pipeline_id": "p-1",
                    "name": "nightly-dlt",
                    "state": "IDLE",
                    "latest_update_state": "COMPLETED",
                }
            ]
        }

        result = _run("list", "ws-1")

        assert result.exit_code == 0
        assert "nightly-dlt" in result.output
        assert "IDLE" in result.output
        mock_api_client.get.assert_called_once_with("databricks/workspaces/ws-1/dlt-pipelines/")

    def test_list_empty(self, mock_api_client):
        mock_api_client.get.return_value = {"results": []}

        result = _run("list", "ws-1")

        assert result.exit_code == 0
        assert "No DLT pipelines" in result.output

    def test_list_json(self, mock_api_client):
        mock_api_client.get.return_value = {"results": []}

        result = _run("list", "ws-1", "--format", "json")

        assert result.exit_code == 0
        assert '"results"' in result.output


class TestDltCreate:
    def test_create_ships_the_settings_file(self, mock_api_client, tmp_path):
        settings = {
            "name": "managed-dlt",
            "edition": "CORE",
            "channel": "CURRENT",
            "catalog": "meshant",
            "target": "gold",
            "continuous": False,
            "development": False,
            "clusters": [{"label": "default", "num_workers": 0, "policy_id": "pol-1"}],
        }
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps(settings))
        mock_api_client.post.return_value = {"pipeline_id": "p-new"}

        result = _run("create", "ws-1", "--file", str(settings_file))

        assert result.exit_code == 0
        assert "p-new" in result.output
        mock_api_client.post.assert_called_once_with(
            "databricks/workspaces/ws-1/dlt-pipelines/", json_data=settings
        )

    def test_create_requires_the_file(self, mock_api_client):
        result = _run("create", "ws-1")

        assert result.exit_code != 0
        mock_api_client.post.assert_not_called()


class TestDltStart:
    def test_start_full_refresh(self, mock_api_client):
        mock_api_client.post.return_value = {"update_id": "u-1"}

        result = _run("start", "ws-1", "p-1", "--full-refresh")

        assert result.exit_code == 0
        assert "u-1" in result.output
        mock_api_client.post.assert_called_once_with(
            "databricks/workspaces/ws-1/dlt-pipelines/p-1/start/",
            json_data={"full_refresh": True},
        )

    def test_start_selective_refresh(self, mock_api_client):
        mock_api_client.post.return_value = {"update_id": "u-2"}

        result = _run(
            "start",
            "ws-1",
            "p-1",
            "--refresh-selection",
            '{"tables": ["bronze_customers"]}',
        )

        assert result.exit_code == 0
        mock_api_client.post.assert_called_once_with(
            "databricks/workspaces/ws-1/dlt-pipelines/p-1/start/",
            json_data={
                "full_refresh": False,
                "refresh_selection": {"tables": ["bronze_customers"]},
            },
        )

    def test_start_rejects_malformed_refresh_selection(self, mock_api_client):
        result = _run("start", "ws-1", "p-1", "--refresh-selection", "{not json")

        assert result.exit_code != 0
        assert "valid JSON" in result.output
        mock_api_client.post.assert_not_called()

    def test_start_surfaces_the_conflict(self, mock_api_client):
        import click

        mock_api_client.post.side_effect = click.ClickException(
            "DATABRICKS_DLT_UPDATE_CONFLICT; An update is already active for this pipeline"
        )

        result = _run("start", "ws-1", "p-1")

        assert result.exit_code != 0
        assert "DATABRICKS_DLT_UPDATE_CONFLICT" in result.output


class TestDltStop:
    def test_stop(self, mock_api_client):
        mock_api_client.post.return_value = {"stopped": True}

        result = _run("stop", "ws-1", "p-1")

        assert result.exit_code == 0
        mock_api_client.post.assert_called_once_with(
            "databricks/workspaces/ws-1/dlt-pipelines/p-1/stop/"
        )

    def test_stop_reports_the_idle_noop(self, mock_api_client):
        mock_api_client.post.return_value = {"stopped": False, "reason": "idle"}

        result = _run("stop", "ws-1", "p-1")

        assert result.exit_code == 0
        assert "idle" in result.output
