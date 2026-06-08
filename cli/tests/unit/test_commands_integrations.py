"""Unit tests for ``datahub integrations`` commands (283.5.11)."""
import json

import pytest
from click.testing import CliRunner
from unittest.mock import Mock

from datahub_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_api(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("datahub_cli.commands.integrations.api_client", mock)
    return mock


class TestIntegrationsConnectionsList:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "conn-1", "source_type": "snowflake", "status": "CONNECTED"},
                {"id": "conn-2", "source_type": "bigquery", "status": "DISCONNECTED"},
            ]
        }
        result = runner.invoke(cli, ["integrations", "connections", "list"])
        assert result.exit_code == 0
        assert "conn-1" in result.output
        assert "snowflake" in result.output

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["integrations", "connections", "list"])
        assert result.exit_code == 0
        assert "No connections" in result.output


class TestIntegrationsConnectionsCreate:
    @pytest.mark.unit
    def test_create_success(self, runner, mock_api):
        mock_api.post.return_value = {"id": "conn-new", "source_type": "snowflake", "status": "CONNECTED"}
        result = runner.invoke(cli, ["integrations", "connections", "create",
                                     "--source-type", "snowflake",
                                     "--config", '{"host":"localhost","port":5432}'])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["id"] == "conn-new"

    @pytest.mark.unit
    def test_create_invalid_json(self, runner, mock_api):
        result = runner.invoke(cli, ["integrations", "connections", "create",
                                     "--source-type", "snowflake", "--config", "bad-json"])
        assert result.exit_code != 0
        assert "Invalid JSON" in result.output


class TestIntegrationsConnectionsGet:
    @pytest.mark.unit
    def test_get(self, runner, mock_api):
        mock_api.get.return_value = {"id": "conn-1", "source_type": "snowflake"}
        result = runner.invoke(cli, ["integrations", "connections", "get", "conn-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["id"] == "conn-1"

    @pytest.mark.unit
    def test_get_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("not found")
        result = runner.invoke(cli, ["integrations", "connections", "get", "missing"])
        assert result.exit_code != 0


class TestIntegrationsConnectionsDelete:
    @pytest.mark.unit
    def test_delete(self, runner, mock_api):
        mock_api.delete.return_value = None
        result = runner.invoke(cli, ["integrations", "connections", "delete", "conn-1", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.output


class TestIntegrationsSyncJobs:
    @pytest.mark.unit
    def test_list(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "sync-1", "status": "SUCCESS", "created_at": "2026-01-01T00:00:00Z"},
                {"id": "sync-2", "status": "FAILED", "created_at": "2026-02-01T00:00:00Z"},
            ]
        }
        result = runner.invoke(cli, ["integrations", "sync-jobs"])
        assert result.exit_code == 0
        assert "sync-1" in result.output
        assert "SUCCESS" in result.output

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["integrations", "sync-jobs"])
        assert result.exit_code == 0
        assert "No sync jobs" in result.output


class TestIntegrationsMarketplaceConnectors:
    @pytest.mark.unit
    def test_list(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "mkt-1", "name": "Snowflake Connector"},
                {"id": "mkt-2", "name": "BigQuery Connector"},
            ]
        }
        result = runner.invoke(cli, ["integrations", "marketplace", "list"])
        assert result.exit_code == 0
        assert "Snowflake" in result.output
        assert "mkt-2" in result.output

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["integrations", "marketplace", "list"])
        assert result.exit_code == 0
        assert "No marketplace connectors" in result.output

    @pytest.mark.unit
    def test_get(self, runner, mock_api):
        mock_api.get.return_value = {"id": "mkt-1", "name": "Snowflake Connector"}
        result = runner.invoke(cli, ["integrations", "marketplace", "get", "mkt-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["name"] == "Snowflake Connector"
