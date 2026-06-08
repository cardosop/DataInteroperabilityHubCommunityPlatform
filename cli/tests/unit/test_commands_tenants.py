"""Unit tests for ``datahub tenants`` commands (279.E.1)."""
import json

import pytest
from click.testing import CliRunner
from unittest.mock import Mock

from datahub_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("datahub_cli.commands.tenants.api_client", mock)
    return mock


# ``tenants list`` and ``tenants get`` were removed; replaced by
# ``tenants me`` (current tenant) and ``tenants admin`` (PLATFORM_ADMIN).


class TestTenantsMe:
    @pytest.mark.unit
    def test_me_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "id": "t1", "name": "acme", "slug": "acme",
            "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-02-01T00:00:00Z",
        }
        result = runner.invoke(cli, ["tenants", "me"])
        assert result.exit_code == 0
        assert "acme" in result.output
        mock_api_client.get.assert_called_once_with("tenants/me/")

    @pytest.mark.unit
    def test_me_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"id": "t1", "slug": "acme"}
        result = runner.invoke(cli, ["tenants", "me", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["id"] == "t1"


class TestTenantsConfig:
    @pytest.mark.unit
    def test_config_get(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "name": "acme", "slug": "acme", "plan": "pro",
        }
        result = runner.invoke(cli, ["tenants", "config", "get"])
        assert result.exit_code == 0
        # config get always outputs JSON (no --format flag)
        assert "acme" in result.output
        mock_api_client.get.assert_called_once_with("tenants/me/config/")

    @pytest.mark.unit
    def test_config_get_json_parsed(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"name": "acme", "plan": "pro"}
        result = runner.invoke(cli, ["tenants", "config", "get"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "acme"
        assert data["plan"] == "pro"


class TestTenantsUsage:
    @pytest.mark.unit
    def test_usage_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "plan_slug": "pro", "plan_tier": "pro",
            "asset_count": 10, "dataset_count": 5, "storage_gb": 2.5,  # noqa: PHASE216-STATIC-ID
            "api_calls_this_month": 1200,
        }
        result = runner.invoke(cli, ["tenants", "usage"])
        assert result.exit_code == 0
        assert "pro" in result.output
        mock_api_client.get.assert_called_once_with("tenants/me/usage/")

    @pytest.mark.unit
    def test_usage_api_error(self, runner, mock_api_client):
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("boom")
        result = runner.invoke(cli, ["tenants", "usage"])
        assert result.exit_code != 0
