"""Unit tests for ``datahub observability`` commands (279.E.2)."""

import json
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from datahub_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("datahub_cli.commands.observability.api_client", mock)
    return mock


class TestObservabilityFreshness:
    @pytest.mark.unit
    def test_freshness_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "summary": {
                "total_datasets": 40,
                "fresh_count": 38,
                "stale_count": 2,
                "unknown_count": 0,
            },
            "stale": [{"name": "sales", "last_updated": "2025-06-01T00:00:00Z"}],
        }
        result = runner.invoke(cli, ["observability", "freshness"])
        assert result.exit_code == 0
        assert "40" in result.output
        assert "sales" in result.output

    @pytest.mark.unit
    def test_freshness_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"summary": {"total_datasets": 40}}
        result = runner.invoke(cli, ["observability", "freshness", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["summary"]["total_datasets"] == 40

    @pytest.mark.unit
    def test_freshness_api_error(self, runner, mock_api_client):
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("boom")
        result = runner.invoke(cli, ["observability", "freshness"])
        assert result.exit_code != 0


class TestObservabilitySLA:
    @pytest.mark.unit
    def test_sla_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "compliance_pct": 98.5,
            "violations": 1,
            "sla_type": "data_freshness",
        }
        result = runner.invoke(cli, ["observability", "sla", "--type", "data_freshness"])
        assert result.exit_code == 0
        mock_api_client.get.assert_called_once()

    @pytest.mark.unit
    def test_sla_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"compliance_pct": 98.5}
        result = runner.invoke(
            cli, ["observability", "sla", "--type", "data_freshness", "--format", "json"]
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["compliance_pct"] == 98.5


class TestObservabilityIncidents:
    @pytest.mark.unit
    def test_incidents_list_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "results": [
                {"name": "sales", "sla_hours": 24, "last_updated": "2025-06-01T00:00:00Z"},
                {"name": "users", "sla_hours": 48, "last_updated": "2025-05-28T00:00:00Z"},
            ]
        }
        result = runner.invoke(cli, ["observability", "incidents", "list"])
        assert result.exit_code == 0
        assert "sales" in result.output

    @pytest.mark.unit
    def test_incidents_list_empty(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": []}
        result = runner.invoke(cli, ["observability", "incidents", "list"])
        assert result.exit_code == 0
        assert "all datasets" in result.output

    @pytest.mark.unit
    def test_incidents_list_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": [{"name": "sales"}]}
        result = runner.invoke(cli, ["observability", "incidents", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["results"][0]["name"] == "sales"

    @pytest.mark.unit
    def test_incidents_get_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "id": "i1",
            "dataset_name": "sales",
            "severity": "HIGH",
            "status": "OPEN",
            "created_at": "2025-06-01T00:00:00Z",
        }
        result = runner.invoke(cli, ["observability", "incidents", "get", "i1"])
        assert result.exit_code == 0
        assert "sales" in result.output

    @pytest.mark.unit
    def test_incidents_get_api_error(self, runner, mock_api_client):
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("not found")
        result = runner.invoke(cli, ["observability", "incidents", "get", "i1"])
        assert result.exit_code != 0
