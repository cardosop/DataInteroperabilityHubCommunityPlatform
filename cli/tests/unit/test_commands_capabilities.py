"""Unit tests for ``datahub capabilities`` commands (283.5.10)."""
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
    monkeypatch.setattr("datahub_cli.commands.capabilities.api_client", mock)
    return mock


class TestCapabilitiesList:
    @pytest.mark.unit
    def test_list_json(self, runner, mock_api):
        mock_api.get.return_value = {
            "capabilities": [{"name": "asset_creation", "available": True}],  # noqa: PHASE216-STATIC-ID
            "feature_flags": {"semantic_memento_enabled": False},
        }
        result = runner.invoke(cli, ["capabilities", "list"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "capabilities" in parsed

    @pytest.mark.unit
    def test_list_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("connection refused")
        result = runner.invoke(cli, ["capabilities", "list"])
        assert result.exit_code != 0
