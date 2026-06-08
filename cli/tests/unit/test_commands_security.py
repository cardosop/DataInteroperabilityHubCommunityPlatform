"""Unit tests for ``datahub security`` commands (283.5.7)."""
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
    monkeypatch.setattr("datahub_cli.commands.security.api_client", mock)
    return mock


class TestSecurityIncidentsList:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "inc-1", "severity": "HIGH", "status": "OPEN", "title": "Unauthorized access"},
                {"id": "inc-2", "severity": "LOW", "status": "RESOLVED", "title": "Expired cert"},
            ]
        }
        result = runner.invoke(cli, ["security", "incidents", "list"])
        assert result.exit_code == 0
        assert "inc-1" in result.output
        assert "HIGH" in result.output
        assert "Unauthorized" in result.output

    @pytest.mark.unit
    def test_list_json(self, runner, mock_api):
        mock_api.get.return_value = {"results": [{"id": "inc-1"}]}
        result = runner.invoke(cli, ["security", "incidents", "list", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["id"] == "inc-1"

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["security", "incidents", "list"])
        assert result.exit_code == 0
        assert "No incidents" in result.output

    @pytest.mark.unit
    def test_list_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("forbidden")
        result = runner.invoke(cli, ["security", "incidents", "list"])
        assert result.exit_code != 0


class TestSecurityIncidentsCreate:
    @pytest.mark.unit
    def test_create_table(self, runner, mock_api):
        mock_api.post.return_value = {"id": "inc-new", "title": "Test Incident", "severity": "MEDIUM"}
        result = runner.invoke(cli, ["security", "incidents", "create", "--title", "Test Incident",
                                     "--severity", "MEDIUM", "--description", "Something happened"])
        assert result.exit_code == 0
        assert "inc-new" in result.output

    @pytest.mark.unit
    def test_create_json(self, runner, mock_api):
        mock_api.post.return_value = {"id": "inc-new"}
        result = runner.invoke(cli, ["security", "incidents", "create", "--title", "T",
                                     "--severity", "LOW", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["id"] == "inc-new"


class TestSecurityIncidentsGet:
    @pytest.mark.unit
    def test_get(self, runner, mock_api):
        mock_api.get.return_value = {"id": "inc-1", "title": "Unauthorized access", "severity": "HIGH"}
        result = runner.invoke(cli, ["security", "incidents", "get", "inc-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["severity"] == "HIGH"

    @pytest.mark.unit
    def test_get_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("not found")
        result = runner.invoke(cli, ["security", "incidents", "get", "missing"])
        assert result.exit_code != 0


class TestSecurityIncidentsUpdate:
    @pytest.mark.unit
    def test_update_status(self, runner, mock_api):
        mock_api.patch.return_value = {"id": "inc-1", "status": "RESOLVED"}
        result = runner.invoke(cli, ["security", "incidents", "update", "inc-1", "--status", "RESOLVED"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["status"] == "RESOLVED"

    @pytest.mark.unit
    def test_update_severity(self, runner, mock_api):
        mock_api.patch.return_value = {"id": "inc-1", "severity": "CRITICAL"}
        result = runner.invoke(cli, ["security", "incidents", "update", "inc-1", "--severity", "CRITICAL"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["severity"] == "CRITICAL"


class TestSecurityAuditLogs:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "log-1", "event_type": "ASSET_CREATED", "created_at": "2026-01-01T00:00:00Z"},
                {"id": "log-2", "event_type": "USER_LOGIN", "created_at": "2026-02-01T00:00:00Z"},
            ]
        }
        result = runner.invoke(cli, ["security", "audit-logs", "list"])
        assert result.exit_code == 0
        assert "log-1" in result.output
        assert "ASSET_CREATED" in result.output

    @pytest.mark.unit
    def test_list_json(self, runner, mock_api):
        mock_api.get.return_value = {"results": [{"id": "log-1"}]}
        result = runner.invoke(cli, ["security", "audit-logs", "list", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["id"] == "log-1"

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["security", "audit-logs", "list"])
        assert result.exit_code == 0
        assert "No audit logs" in result.output

    @pytest.mark.unit
    def test_get(self, runner, mock_api):
        mock_api.get.return_value = {"id": "log-1", "event_type": "ASSET_CREATED"}
        result = runner.invoke(cli, ["security", "audit-logs", "get", "log-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["event_type"] == "ASSET_CREATED"
