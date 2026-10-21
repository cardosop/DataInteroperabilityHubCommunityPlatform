"""Unit tests for ``datahub datasets`` commands (278.AA.5)."""

import json
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from datahub_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("datahub_cli.commands.datasets.api_client", mock)
    return mock


class TestDatasetsList:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "results": [
                {
                    "id": "d1",
                    "name": "sales",
                    "format": "CSV",
                    "status": "ACTIVE",
                    "row_count": 1000,
                },
                {
                    "id": "d2",
                    "name": "users",
                    "format": "JSON",
                    "status": "DRAFT",
                    "row_count": 500,
                },
            ]
        }
        result = runner.invoke(cli, ["datasets", "list"])
        assert result.exit_code == 0
        assert "sales" in result.output
        assert "CSV" in result.output
        assert "1000" in result.output

    @pytest.mark.unit
    def test_list_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": [{"id": "d1", "name": "sales"}]}
        result = runner.invoke(cli, ["datasets", "list", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)[0]["name"] == "sales"

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": []}
        result = runner.invoke(cli, ["datasets", "list"])
        assert result.exit_code == 0
        assert "No datasets found" in result.output

    @pytest.mark.unit
    def test_list_with_status_filter(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": []}
        result = runner.invoke(cli, ["datasets", "list", "--status", "ACTIVE"])
        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            "datasets/", params={"limit": 50, "offset": 0, "status": "ACTIVE"}
        )

    @pytest.mark.unit
    def test_list_api_error(self, runner, mock_api_client):
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("boom")
        result = runner.invoke(cli, ["datasets", "list"])
        assert result.exit_code != 0


class TestDatasetsGet:
    @pytest.mark.unit
    def test_get_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "id": "d1",
            "name": "sales",
            "format": "CSV",
            "status": "ACTIVE",
            "row_count": 1000,
            "size_bytes": 1048576,
            "version": 3,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-02-01T00:00:00Z",
        }
        result = runner.invoke(cli, ["datasets", "get", "d1"])
        assert result.exit_code == 0
        assert "sales" in result.output
        assert "1.00 MB" in result.output
        assert "3" in result.output

    @pytest.mark.unit
    def test_get_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"id": "d1", "name": "sales"}
        result = runner.invoke(cli, ["datasets", "get", "d1", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["id"] == "d1"

    @pytest.mark.unit
    def test_get_api_error(self, runner, mock_api_client):
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("not found")
        result = runner.invoke(cli, ["datasets", "get", "d1"])
        assert result.exit_code != 0


class TestDatasetsVersions:
    @pytest.mark.unit
    def test_versions_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "id": "d1",
            "versions": [
                {
                    "version": 3,
                    "created_at": "2025-02-01T00:00:00Z",
                    "row_count": 1000,
                    "size_bytes": 1048576,
                },
                {
                    "version": 2,
                    "created_at": "2025-01-15T00:00:00Z",
                    "row_count": 900,
                    "size_bytes": 950272,
                },
            ],
        }
        result = runner.invoke(cli, ["datasets", "versions", "d1"])
        assert result.exit_code == 0
        assert "3" in result.output
        assert "2" in result.output

    @pytest.mark.unit
    def test_versions_empty(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"id": "d1", "versions": []}
        result = runner.invoke(cli, ["datasets", "versions", "d1"])
        assert result.exit_code == 0
        assert "No version history" in result.output

    @pytest.mark.unit
    def test_versions_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"id": "d1", "versions": [{"version": 1}]}
        result = runner.invoke(cli, ["datasets", "versions", "d1", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)[0]["version"] == 1


class TestDatasetsRefresh:
    @pytest.mark.unit
    def test_refresh_table(self, runner, mock_api_client):
        mock_api_client.post.return_value = {"status": "QUEUED", "job_id": "j1"}
        result = runner.invoke(cli, ["datasets", "refresh", "d1"])
        assert result.exit_code == 0
        assert "Refresh triggered" in result.output
        assert "j1" in result.output

    @pytest.mark.unit
    def test_refresh_json(self, runner, mock_api_client):
        mock_api_client.post.return_value = {"status": "QUEUED", "job_id": "j1"}
        result = runner.invoke(cli, ["datasets", "refresh", "d1", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["job_id"] == "j1"

    @pytest.mark.unit
    def test_refresh_api_error(self, runner, mock_api_client):
        from click import ClickException

        mock_api_client.post.side_effect = ClickException("not found")
        result = runner.invoke(cli, ["datasets", "refresh", "d1"])
        assert result.exit_code != 0
