"""Unit tests for ``datahub events`` commands (283.5.9)."""

import json
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from datahub_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_api(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("datahub_cli.commands.events.api_client", mock)
    return mock


class TestEventsReplay:
    @pytest.mark.unit
    def test_replay_success(self, runner, mock_api):
        mock_api.post.return_value = {"id": "evt-1", "status": "REPLAYED"}
        result = runner.invoke(cli, ["events", "replay", "evt-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["status"] == "REPLAYED"

    @pytest.mark.unit
    def test_replay_api_error(self, runner, mock_api):
        mock_api.post.side_effect = Exception("not found")
        result = runner.invoke(cli, ["events", "replay", "missing"])
        assert result.exit_code != 0


class TestDlqList:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "dlq-1", "event_type": "ASSET_CREATED", "status": "PENDING"},
                {"id": "dlq-2", "event_type": "CONTRACT_UPDATED", "status": "FAILED"},
            ]
        }
        result = runner.invoke(cli, ["events", "dlq", "list"])
        assert result.exit_code == 0
        assert "dlq-1" in result.output
        assert "ASSET_CREATED" in result.output

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["events", "dlq", "list"])
        assert result.exit_code == 0
        assert "empty" in result.output

    @pytest.mark.unit
    def test_list_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("boom")
        result = runner.invoke(cli, ["events", "dlq", "list"])
        assert result.exit_code != 0


class TestDlqRetry:
    @pytest.mark.unit
    def test_retry_success(self, runner, mock_api):
        mock_api.post.return_value = {"id": "dlq-1", "status": "RETRIED"}
        result = runner.invoke(cli, ["events", "dlq", "retry", "dlq-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["status"] == "RETRIED"


class TestDlqResolve:
    @pytest.mark.unit
    def test_resolve_success(self, runner, mock_api):
        mock_api.post.return_value = {"id": "dlq-1", "status": "RESOLVED"}
        result = runner.invoke(cli, ["events", "dlq", "resolve", "dlq-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["status"] == "RESOLVED"
