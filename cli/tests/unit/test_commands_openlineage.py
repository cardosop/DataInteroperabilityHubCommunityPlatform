"""Unit tests for ``datahub openlineage`` commands (283.5.13)."""

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
    monkeypatch.setattr("datahub_cli.commands.openlineage.api_client", mock)
    return mock


class TestOpenLineageKeys:
    @pytest.mark.unit
    def test_keys_list(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "key-1", "name": "prod-key", "created_at": "2026-01-01T00:00:00Z"},
                {"id": "key-2", "name": "staging-key", "created_at": "2026-02-01T00:00:00Z"},
            ]
        }
        result = runner.invoke(cli, ["openlineage", "keys"])
        assert result.exit_code == 0
        assert "prod-key" in result.output
        assert "key-2" in result.output

    @pytest.mark.unit
    def test_keys_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["openlineage", "keys"])
        assert result.exit_code == 0
        assert "No OpenLineage" in result.output


class TestOpenLineageCreateKey:
    @pytest.mark.unit
    def test_create_key(self, runner, mock_api):
        mock_api.post.return_value = {"id": "key-new", "name": "my-key", "key": "secret-hmac"}
        result = runner.invoke(cli, ["openlineage", "create-key", "--name", "my-key"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["name"] == "my-key"

    @pytest.mark.unit
    def test_create_key_api_error(self, runner, mock_api):
        mock_api.post.side_effect = Exception("quota exceeded")
        result = runner.invoke(cli, ["openlineage", "create-key", "--name", "bad"])
        assert result.exit_code != 0


class TestOpenLineageRevokeKey:
    @pytest.mark.unit
    def test_revoke_key(self, runner, mock_api):
        mock_api.delete.return_value = None
        result = runner.invoke(cli, ["openlineage", "revoke-key", "key-1", "--yes"])
        assert result.exit_code == 0
        assert "Revoked" in result.output


class TestOpenLineageStatus:
    @pytest.mark.unit
    def test_status(self, runner, mock_api):
        mock_api.get.return_value = {"status": "healthy", "version": "1.2.3"}
        result = runner.invoke(cli, ["openlineage", "status"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["status"] == "healthy"

    @pytest.mark.unit
    def test_status_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("service unavailable")
        result = runner.invoke(cli, ["openlineage", "status"])
        assert result.exit_code != 0
