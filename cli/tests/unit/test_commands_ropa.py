"""Unit tests for ``datahub ropa`` commands (283.3.3.2)."""

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
    monkeypatch.setattr("datahub_cli.commands.ropa.api_client", mock)
    return mock


class TestRopaList:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "regulation": "GDPR",
                    "output_format": "json",
                    "status": "COMPLETED",
                    "created_at": "2026-01-15T00:00:00Z",
                },
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "regulation": "LGPD",
                    "output_format": "csv",
                    "status": "FAILED",
                    "created_at": "2026-02-01T00:00:00Z",
                },
            ]
        }
        result = runner.invoke(cli, ["ropa", "list"])
        assert result.exit_code == 0
        assert "GDPR" in result.output
        assert "FAILED" in result.output

    @pytest.mark.unit
    def test_list_json(self, runner, mock_api):
        mock_api.get.return_value = {"results": [{"id": "a", "regulation": "GDPR"}]}
        result = runner.invoke(cli, ["ropa", "list", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["regulation"] == "GDPR"

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["ropa", "list"])
        assert result.exit_code == 0
        assert "No RoPA" in result.output

    @pytest.mark.unit
    def test_list_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("connection refused")
        result = runner.invoke(cli, ["ropa", "list"])
        assert result.exit_code != 0
        assert "connection refused" in result.output


class TestRopaGet:
    @pytest.mark.unit
    def test_get_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "id": "abc",
            "regulation": "GDPR",
            "output_format": "json",
            "status": "COMPLETED",
            "byte_size": 1234,
            "created_at": "2026-01-01",
            "completed_at": "2026-01-02",
            "summary_json": {"asset_count": 42},  # noqa: PHASE216-STATIC-ID
        }
        result = runner.invoke(cli, ["ropa", "get", "abc"])
        assert result.exit_code == 0
        assert "GDPR" in result.output
        assert "42" in result.output

    @pytest.mark.unit
    def test_get_json(self, runner, mock_api):
        mock_api.get.return_value = {"id": "abc", "regulation": "GDPR"}
        result = runner.invoke(cli, ["ropa", "get", "abc", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["regulation"] == "GDPR"

    @pytest.mark.unit
    def test_get_api_error(self, runner, mock_api):
        mock_api.get.side_effect = Exception("not found")
        result = runner.invoke(cli, ["ropa", "get", "missing"])
        assert result.exit_code != 0


class TestRopaPreview:
    @pytest.mark.unit
    def test_preview_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "regulation": "GDPR",
            "cache_hit": True,
            "summary": {"asset_count": 10, "gap_count": 2},  # noqa: PHASE216-STATIC-ID
            "gaps": [{"code": "GAP1", "asset_key": "sales", "message": "Missing processor"}],  # noqa: PHASE216-STATIC-ID
        }
        result = runner.invoke(cli, ["ropa", "preview"])
        assert result.exit_code == 0
        assert "GDPR" in result.output
        assert "10" in result.output
        assert "sales" in result.output

    @pytest.mark.unit
    def test_preview_json(self, runner, mock_api):
        mock_api.get.return_value = {"regulation": "GDPR"}
        result = runner.invoke(cli, ["ropa", "preview", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["regulation"] == "GDPR"


class TestRopaGenerate:
    @pytest.mark.unit
    def test_generate_sync(self, runner, mock_api):
        mock_api.post.return_value = {
            "ropa_generation_id": "gen-1",
            "async": False,
            "status": "COMPLETED",
        }
        result = runner.invoke(cli, ["ropa", "generate", "--regulation", "GDPR"])
        assert result.exit_code == 0
        assert "gen-1" in result.output

    @pytest.mark.unit
    def test_generate_json(self, runner, mock_api):
        mock_api.post.return_value = {"ropa_generation_id": "gen-1", "async": False}
        result = runner.invoke(cli, ["ropa", "generate", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["ropa_generation_id"] == "gen-1"

    @pytest.mark.unit
    def test_generate_api_error(self, runner, mock_api):
        mock_api.post.side_effect = Exception("service unavailable")
        result = runner.invoke(cli, ["ropa", "generate"])
        assert result.exit_code != 0
        assert "service unavailable" in result.output


class TestRopaDownload:
    @pytest.mark.unit
    def test_download_with_url(self, runner, mock_api):
        mock_api.get.return_value = {
            "download_url": "https://s3.example.com/presigned/abc",
            "expires_in": 3600,
        }
        result = runner.invoke(cli, ["ropa", "download", "abc"])
        assert result.exit_code == 0
        assert "https://s3.example.com" in result.output

    @pytest.mark.unit
    def test_download_no_url(self, runner, mock_api):
        mock_api.get.return_value = {"status": "PENDING"}
        result = runner.invoke(cli, ["ropa", "download", "abc"])
        assert result.exit_code == 0
        assert "PENDING" in result.output


class TestRopaDelete:
    @pytest.mark.unit
    def test_delete_confirmed(self, runner, mock_api):
        mock_api.delete.return_value = None
        result = runner.invoke(cli, ["ropa", "delete", "abc", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    @pytest.mark.unit
    def test_delete_api_error(self, runner, mock_api):
        mock_api.delete.side_effect = Exception("not found")
        result = runner.invoke(cli, ["ropa", "delete", "abc", "--yes"])
        assert result.exit_code != 0


class TestRopaRegulationMap:
    @pytest.mark.unit
    def test_regulation_map_table(self, runner, mock_api):
        result = runner.invoke(cli, ["ropa", "regulation-map"])
        assert result.exit_code == 0
        assert "GDPR" in result.output
        assert "LGPD" in result.output

    @pytest.mark.unit
    def test_regulation_map_json(self, runner, mock_api):
        result = runner.invoke(cli, ["ropa", "regulation-map", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "GDPR" in parsed
