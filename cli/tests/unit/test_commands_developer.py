"""Unit tests for ``datahub developer`` commands (283.5.12)."""
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
    monkeypatch.setattr("datahub_cli.commands.developer.api_client", mock)
    return mock


class TestDeveloperPlugins:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "plg-1", "name": "Auth Plugin"},
                {"id": "plg-2", "name": "Transform Plugin"},
            ]
        }
        result = runner.invoke(cli, ["developer", "plugins", "list"])
        assert result.exit_code == 0
        assert "plg-1" in result.output
        assert "Auth Plugin" in result.output

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["developer", "plugins", "list"])
        assert result.exit_code == 0
        assert "No plugins" in result.output

    @pytest.mark.unit
    def test_create(self, runner, mock_api):
        mock_api.post.return_value = {"id": "plg-new", "name": "My Plugin"}
        result = runner.invoke(cli, ["developer", "plugins", "create", "--name", "My Plugin",
                                     "--config", '{"key":"value"}'])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["name"] == "My Plugin"

    @pytest.mark.unit
    def test_create_invalid_config(self, runner, mock_api):
        result = runner.invoke(cli, ["developer", "plugins", "create", "--name", "P",
                                     "--config", "bad-json"])
        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    @pytest.mark.unit
    def test_get(self, runner, mock_api):
        mock_api.get.return_value = {"id": "plg-1", "name": "Auth Plugin"}
        result = runner.invoke(cli, ["developer", "plugins", "get", "plg-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["name"] == "Auth Plugin"

    @pytest.mark.unit
    def test_delete(self, runner, mock_api):
        mock_api.delete.return_value = None
        result = runner.invoke(cli, ["developer", "plugins", "delete", "plg-1", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.output


class TestDeveloperApiKeys:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "key-1", "name": "Production Key", "created_at": "2026-01-01T00:00:00Z"},
            ]
        }
        result = runner.invoke(cli, ["developer", "api-keys", "list"])
        assert result.exit_code == 0
        assert "key-1" in result.output
        assert "Production Key" in result.output

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["developer", "api-keys", "list"])
        assert result.exit_code == 0
        assert "No API keys" in result.output

    @pytest.mark.unit
    def test_create(self, runner, mock_api):
        mock_api.post.return_value = {"id": "key-new", "name": "My Key", "key": "secret-abc123"}
        result = runner.invoke(cli, ["developer", "api-keys", "create", "--name", "My Key"])
        assert result.exit_code == 0
        assert "secret-abc123" in result.output

    @pytest.mark.unit
    def test_revoke(self, runner, mock_api):
        mock_api.delete.return_value = None
        result = runner.invoke(cli, ["developer", "api-keys", "revoke", "key-1", "--yes"])
        assert result.exit_code == 0
        assert "Revoked" in result.output


class TestDeveloperSdkDocsPortal:
    @pytest.mark.unit
    def test_sdk(self, runner, mock_api):
        mock_api.get.return_value = {"sdk_versions": ["1.0.0", "2.0.0"]}
        result = runner.invoke(cli, ["developer", "sdk"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    @pytest.mark.unit
    def test_docs(self, runner, mock_api):
        mock_api.get.return_value = {"docs_url": "https://docs.example.com"}
        result = runner.invoke(cli, ["developer", "docs"])
        assert result.exit_code == 0
        assert "docs.example.com" in result.output

    @pytest.mark.unit
    def test_portal(self, runner, mock_api):
        mock_api.get.return_value = {"portal_url": "https://dev.example.com"}
        result = runner.invoke(cli, ["developer", "portal"])
        assert result.exit_code == 0
        assert "dev.example.com" in result.output

    @pytest.mark.unit
    def test_api_usage(self, runner, mock_api):
        mock_api.get.return_value = {"total_requests": 1234, "period": "2026-05"}
        result = runner.invoke(cli, ["developer", "api-usage"])
        assert result.exit_code == 0
        assert "1234" in result.output
