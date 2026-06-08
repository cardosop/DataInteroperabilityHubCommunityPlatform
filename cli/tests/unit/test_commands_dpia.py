"""Unit tests for ``datahub dpia`` commands (283.3.5.2)."""
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
    monkeypatch.setattr("datahub_cli.commands.dpia.api_client", mock)
    return mock


class TestDpiaCreate:
    @pytest.mark.unit
    def test_create_table(self, runner, mock_api):
        mock_api.post.return_value = {"id": "dpia-1", "status": "DRAFT", "risk_level": "MEDIUM"}
        result = runner.invoke(cli, ["dpia", "create", "--title", "Test DPIA", "--description", "Processing customer data"])
        assert result.exit_code == 0
        assert "dpia-1" in result.output
        assert "DRAFT" in result.output

    @pytest.mark.unit
    def test_create_json(self, runner, mock_api):
        mock_api.post.return_value = {"id": "dpia-1", "status": "DRAFT"}
        result = runner.invoke(cli, ["dpia", "create", "--title", "T", "--description", "D", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["id"] == "dpia-1"

    @pytest.mark.unit
    def test_create_with_data_categories(self, runner, mock_api):
        mock_api.post.return_value = {"id": "dpia-2"}
        result = runner.invoke(cli, ["dpia", "create", "--title", "T", "--description", "D",
                                     "--data-categories", "health,financial", "--risk-level", "HIGH"])
        assert result.exit_code == 0
        call_args = mock_api.post.call_args[1]["data"]
        assert "health" in call_args["data_categories"]
        assert call_args["risk_level"] == "HIGH"

    @pytest.mark.unit
    def test_create_api_error(self, runner, mock_api):
        mock_api.post.side_effect = Exception("validation failed")
        result = runner.invoke(cli, ["dpia", "create", "--title", "T", "--description", "D"])
        assert result.exit_code != 0


class TestDpiaList:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "11111111-1111-1111-1111-111111111111", "status": "DRAFT",
                 "risk_level": "HIGH", "title": "Customer data processing"},
            ],
            "count": 1,
        }
        result = runner.invoke(cli, ["dpia", "list"])
        assert result.exit_code == 0
        assert "DRAFT" in result.output
        assert "HIGH" in result.output

    @pytest.mark.unit
    def test_list_json(self, runner, mock_api):
        mock_api.get.return_value = {"results": [], "count": 0}
        result = runner.invoke(cli, ["dpia", "list", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["count"] == 0

    @pytest.mark.unit
    def test_list_with_filter(self, runner, mock_api):
        mock_api.get.return_value = {"results": [], "count": 0}
        result = runner.invoke(cli, ["dpia", "list", "--status", "SUBMITTED"])
        assert result.exit_code == 0
        call_args = mock_api.get.call_args[1]["params"]
        assert call_args["status"] == "SUBMITTED"

    @pytest.mark.unit
    def test_list_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("boom")
        result = runner.invoke(cli, ["dpia", "list"])
        assert result.exit_code != 0


class TestDpiaGet:
    @pytest.mark.unit
    def test_get_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "id": "dpia-1", "title": "Test", "status": "DRAFT",
            "risk_level": "LOW", "description": "Some processing activity",
        }
        result = runner.invoke(cli, ["dpia", "get", "--dpia-id", "dpia-1"])
        assert result.exit_code == 0
        assert "Test" in result.output
        assert "DRAFT" in result.output

    @pytest.mark.unit
    def test_get_json(self, runner, mock_api):
        mock_api.get.return_value = {"id": "dpia-1"}
        result = runner.invoke(cli, ["dpia", "get", "--dpia-id", "dpia-1", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["id"] == "dpia-1"

    @pytest.mark.unit
    def test_get_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("not found")
        result = runner.invoke(cli, ["dpia", "get", "--dpia-id", "missing"])
        assert result.exit_code != 0


class TestDpiaSubmit:
    @pytest.mark.unit
    def test_submit_table(self, runner, mock_api):
        mock_api.post.return_value = {"status": "SUBMITTED"}
        result = runner.invoke(cli, ["dpia", "submit", "--dpia-id", "dpia-1"])
        assert result.exit_code == 0
        assert "SUBMITTED" in result.output

    @pytest.mark.unit
    def test_submit_json(self, runner, mock_api):
        mock_api.post.return_value = {"status": "SUBMITTED"}
        result = runner.invoke(cli, ["dpia", "submit", "--dpia-id", "dpia-1", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["status"] == "SUBMITTED"

    @pytest.mark.unit
    def test_submit_api_error(self, runner, mock_api):
        mock_api.post.side_effect = Exception("already submitted")
        result = runner.invoke(cli, ["dpia", "submit", "--dpia-id", "dpia-1"])
        assert result.exit_code != 0


class TestDpiaWizard:
    @pytest.mark.unit
    def test_wizard_confirm(self, runner, mock_api):
        mock_api.post.return_value = {"id": "dpia-wiz", "status": "DRAFT"}
        result = runner.invoke(cli, ["dpia", "wizard", "--title", "My DPIA", "--description",
                                     "Processing data", "--data-categories", "health",
                                     "--risk-level", "MEDIUM"],
                               input="y\n")
        assert result.exit_code == 0
        assert "dpia-wiz" in result.output

    @pytest.mark.unit
    def test_wizard_cancel(self, runner, mock_api):
        # wizard prompts for: data_categories, risk_level, then confirm.
        # Two empty newlines accept defaults for data_categories + risk_level;
        # "n" answers the confirmation prompt to cancel.
        result = runner.invoke(cli, ["dpia", "wizard", "--title", "T", "--description", "D"],
                               input="\n\nn\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.output

    @pytest.mark.unit
    def test_wizard_api_error(self, runner, mock_api):
        mock_api.post.side_effect = Exception("validation failed")
        result = runner.invoke(cli, ["dpia", "wizard", "--title", "T", "--description", "D"],
                               input="y\n")
        assert result.exit_code != 0
