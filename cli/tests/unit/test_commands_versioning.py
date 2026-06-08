"""Unit tests for ``datahub versioning`` commands (283.6.2)."""
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
    monkeypatch.setattr("datahub_cli.commands.versioning.api_client", mock)
    return mock


class TestVersioningList:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "results": [
                {"id": "v1-uuid", "version_number": 1, "created_at": "2026-01-01", "status": "current"},
                {"id": "v2-uuid", "version_number": 2, "created_at": "2026-02-01", "status": "archived"},
            ]
        }
        result = runner.invoke(cli, ["versioning", "list", "datasets", "abc-123"])
        assert result.exit_code == 0
        assert "v1-uuid" in result.output
        assert "1" in result.output
        assert "current" in result.output

    @pytest.mark.unit
    def test_list_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": [{"id": "v1", "version_number": 1}]}
        result = runner.invoke(cli, ["versioning", "list", "datasets", "abc-123", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["results"][0]["id"] == "v1"

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": []}
        result = runner.invoke(cli, ["versioning", "list", "datasets", "abc-123"])
        assert result.exit_code == 0
        assert "No versions found" in result.output

    @pytest.mark.unit
    def test_list_with_pagination(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": []}
        result = runner.invoke(cli, ["versioning", "list", "contracts", "def-456", "--page", "2", "--page-size", "20"])
        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            "versioning/versions/",
            params={"resource_type": "contract", "resource_id": "def-456", "page": 2, "page_size": 20},
        )

    @pytest.mark.unit
    def test_list_invalid_resource_type(self, runner, mock_api_client):
        result = runner.invoke(cli, ["versioning", "list", "invalid", "abc"])
        assert result.exit_code != 0


class TestVersioningGet:
    @pytest.mark.unit
    def test_get_detail(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "id": "v1-uuid",
            "resource_id": "abc-123",
            "version_number": 3,
            "status": "current",
            "created_at": "2026-03-15T10:00:00Z",
            "schema": {"fields": [{"name": "col1", "type": "string"}]},
            "metadata": {"source": "upload"},
        }
        result = runner.invoke(cli, ["versioning", "get", "datasets", "v1-uuid"])
        assert result.exit_code == 0
        assert "v1-uuid" in result.output
        assert "3" in result.output
        assert "current" in result.output
        assert "col1" in result.output

    @pytest.mark.unit
    def test_get_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"id": "v1", "version_number": 1}
        result = runner.invoke(cli, ["versioning", "get", "datasets", "v1", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["id"] == "v1"

    @pytest.mark.unit
    def test_get_invalid_resource_type(self, runner, mock_api_client):
        result = runner.invoke(cli, ["versioning", "get", "invalid", "abc", "v1"])
        assert result.exit_code != 0


class TestVersioningDiff:
    @pytest.mark.unit
    def test_diff_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "changes": [
                {"field": "schema.col1.type", "old": "string", "new": "integer"},
                {"field": "row_count", "old": 100, "new": 200},
            ]
        }
        result = runner.invoke(cli, ["versioning", "diff", "datasets", "v1", "v2"])
        assert result.exit_code == 0
        assert "v1" in result.output
        assert "v2" in result.output
        assert "string" in result.output
        assert "integer" in result.output

    @pytest.mark.unit
    def test_diff_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"changes": [{"field": "x", "old": 1, "new": 2}]}
        result = runner.invoke(cli, ["versioning", "diff", "datasets", "v1", "v2", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["changes"]) == 1

    @pytest.mark.unit
    def test_diff_no_changes(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"changes": []}
        result = runner.invoke(cli, ["versioning", "diff", "datasets", "v1", "v2"])
        assert result.exit_code == 0
        assert "No differences found" in result.output

    @pytest.mark.unit
    def test_diff_dict_format(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "changes": {"schema": {"old": "v1_schema", "new": "v2_schema"}}
        }
        result = runner.invoke(cli, ["versioning", "diff", "datasets", "v1", "v2"])
        assert result.exit_code == 0
        assert "schema" in result.output


class TestVersioningRollback:
    # Rollback is intentionally de-registered in main.py (line 139) until
    # the Phase 286 backend endpoint is available.  The command code is
    # preserved in versioning.py for future activation.
    @pytest.mark.unit
    @pytest.mark.skip(reason="Rollback de-registered in main.py until Phase 286 backend endpoint")
    def test_rollback_confirm(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"new_version_id": "v3", "status": "rolled_back"}
        mock_api_client.request.return_value = mock_resp

        result = runner.invoke(
            cli,
            ["versioning", "rollback", "datasets", "abc-123", "v1", "--reason", "Bad schema", "--confirm"],
        )
        assert result.exit_code == 0
        assert "Rollback complete" in result.output
        assert "v3" in result.output

    @pytest.mark.unit
    @pytest.mark.skip(reason="Rollback de-registered in main.py until Phase 286 backend endpoint")
    def test_rollback_aborted(self, runner, mock_api_client):
        result = runner.invoke(
            cli,
            ["versioning", "rollback", "datasets", "abc-123", "v1", "--reason", "Test"],
            input="n",
        )
        assert result.exit_code == 0
        assert "Aborted" in result.output

    @pytest.mark.unit
    @pytest.mark.skip(reason="Rollback de-registered in main.py until Phase 286 backend endpoint")
    def test_rollback_json(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"new_version_id": "v3", "status": "rolled_back"}
        mock_api_client.request.return_value = mock_resp

        result = runner.invoke(
            cli,
            [
                "versioning", "rollback", "datasets", "abc", "v1",
                "--reason", "Test", "--confirm", "--json",
            ],
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["new_version_id"] == "v3"

    @pytest.mark.unit
    @pytest.mark.skip(reason="Rollback de-registered in main.py until Phase 286 backend endpoint")
    def test_rollback_api_error(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.status_code = 409
        mock_resp.text = "Version conflict"
        mock_api_client.request.return_value = mock_resp

        result = runner.invoke(
            cli,
            ["versioning", "rollback", "datasets", "abc", "v1", "--reason", "Test", "--confirm"],
        )
        assert result.exit_code == 1
        assert "409" in result.output

    @pytest.mark.unit
    @pytest.mark.skip(reason="Rollback de-registered in main.py until Phase 286 backend endpoint")
    def test_rollback_missing_reason(self, runner):
        result = runner.invoke(cli, ["versioning", "rollback", "datasets", "abc", "v1"])
        assert result.exit_code != 0
