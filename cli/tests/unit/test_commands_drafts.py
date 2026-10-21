"""Unit tests for ``datahub drafts`` commands (283.5.8)."""

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
    monkeypatch.setattr("datahub_cli.commands.drafts.api_client", mock)
    return mock


class TestDraftsGet:
    @pytest.mark.unit
    def test_get_json(self, runner, mock_api):
        mock_api.get.return_value = {
            "resource_type": "asset",
            "draft_key": "default",
            "data": {"name": "test"},
        }
        result = runner.invoke(cli, ["drafts", "get", "--resource-type", "asset"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["resource_type"] == "asset"

    @pytest.mark.unit
    def test_get_with_draft_key(self, runner, mock_api):
        mock_api.get.return_value = {"resource_type": "asset", "draft_key": "my-key", "data": {}}
        result = runner.invoke(
            cli, ["drafts", "get", "--resource-type", "asset", "--draft-key", "my-key"]
        )
        assert result.exit_code == 0
        mock_api.get.assert_called_once()
        call_args = mock_api.get.call_args[1]["params"]
        assert call_args["draft_key"] == "my-key"

    @pytest.mark.unit
    def test_get_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("not found")
        result = runner.invoke(cli, ["drafts", "get", "--resource-type", "asset"])
        assert result.exit_code != 0


class TestDraftsSave:
    @pytest.mark.unit
    def test_save_success(self, runner, mock_api):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"id": "draft-1", "resource_type": "asset"}
        mock_api.request.return_value = mock_response

        result = runner.invoke(
            cli, ["drafts", "save", "--resource-type", "asset", "--data", '{"name":"test"}']
        )
        assert result.exit_code == 0
        assert "draft-1" in result.output

    @pytest.mark.unit
    def test_save_invalid_json(self, runner, mock_api):
        result = runner.invoke(
            cli, ["drafts", "save", "--resource-type", "asset", "--data", "not-json"]
        )
        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    @pytest.mark.unit
    def test_save_api_error(self, runner, mock_api):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 422
        mock_response.text = "Validation failed"
        mock_api.request.return_value = mock_response

        result = runner.invoke(cli, ["drafts", "save", "--resource-type", "asset", "--data", "{}"])
        assert result.exit_code != 0


class TestDraftsDelete:
    @pytest.mark.unit
    def test_delete_success(self, runner, mock_api):
        mock_response = Mock()
        mock_response.ok = True
        mock_api.request.return_value = mock_response

        result = runner.invoke(cli, ["drafts", "delete", "--resource-type", "asset", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    @pytest.mark.unit
    def test_delete_api_error(self, runner, mock_api):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_api.request.return_value = mock_response

        result = runner.invoke(cli, ["drafts", "delete", "--resource-type", "asset", "--yes"])
        assert result.exit_code != 0
