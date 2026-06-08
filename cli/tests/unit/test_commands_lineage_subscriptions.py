"""Unit tests for ``datahub lineage-subscriptions`` commands (283.5.14)."""
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
    monkeypatch.setattr("datahub_cli.commands.lineage_subscriptions.api_client", mock)
    return mock


class TestLineageSubscriptionsList:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "sub-1", "resource_type": "asset", "status": "ACTIVE"},
                {"id": "sub-2", "resource_type": "dataset", "status": "INACTIVE"},
            ]
        }
        result = runner.invoke(cli, ["lineage-subscriptions", "list"])
        assert result.exit_code == 0
        assert "sub-1" in result.output
        assert "ACTIVE" in result.output

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["lineage-subscriptions", "list"])
        assert result.exit_code == 0
        assert "No lineage subscriptions" in result.output


class TestLineageSubscriptionsCreate:
    @pytest.mark.unit
    def test_create_table(self, runner, mock_api):
        mock_api.post.return_value = {"id": "sub-new", "resource_type": "asset", "resource_id": "r1"}
        result = runner.invoke(cli, ["lineage-subscriptions", "create", "--resource-type", "asset", "--resource-id", "r1"])
        assert result.exit_code == 0
        assert "sub-new" in result.output

    @pytest.mark.unit
    def test_create_json(self, runner, mock_api):
        mock_api.post.return_value = {"id": "sub-new"}
        result = runner.invoke(cli, ["lineage-subscriptions", "create", "--resource-type", "asset",
                                     "--resource-id", "r1", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["id"] == "sub-new"

    @pytest.mark.unit
    def test_create_api_error(self, runner, mock_api):
        mock_api.post.side_effect = Exception("resource not found")
        result = runner.invoke(cli, ["lineage-subscriptions", "create", "--resource-type", "asset", "--resource-id", "x"])
        assert result.exit_code != 0


class TestLineageSubscriptionsGet:
    @pytest.mark.unit
    def test_get(self, runner, mock_api):
        mock_api.get.return_value = {"id": "sub-1", "resource_type": "asset", "status": "ACTIVE"}
        result = runner.invoke(cli, ["lineage-subscriptions", "get", "sub-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["id"] == "sub-1"


class TestLineageSubscriptionsDelete:
    @pytest.mark.unit
    def test_delete(self, runner, mock_api):
        mock_api.delete.return_value = None
        result = runner.invoke(cli, ["lineage-subscriptions", "delete", "sub-1", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.output
