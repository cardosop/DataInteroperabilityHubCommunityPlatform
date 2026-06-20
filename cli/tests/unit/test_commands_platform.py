"""Unit tests for ``datahub platform`` commands (283.5.6)."""

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
    monkeypatch.setattr("datahub_cli.commands.platform.api_client", mock)
    return mock


class TestPlatformTenants:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "t-1", "slug": "acme", "display_name": "Acme Corp", "status": "ACTIVE"},
                {"id": "t-2", "slug": "beta", "display_name": "Beta Inc", "status": "SUSPENDED"},
            ]
        }
        result = runner.invoke(cli, ["platform", "tenants", "list"])
        assert result.exit_code == 0
        assert "acme" in result.output
        assert "SUSPENDED" in result.output

    @pytest.mark.unit
    def test_list_json(self, runner, mock_api):
        mock_api.get.return_value = {"results": [{"id": "t-1"}]}
        result = runner.invoke(cli, ["platform", "tenants", "list", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["id"] == "t-1"

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["platform", "tenants", "list"])
        assert result.exit_code == 0
        assert "No tenants" in result.output

    @pytest.mark.unit
    def test_create_table(self, runner, mock_api):
        mock_api.post.return_value = {"id": "t-new", "slug": "newco", "display_name": "NewCo"}
        result = runner.invoke(
            cli,
            [
                "platform",
                "tenants",
                "create",
                "--slug",
                "newco",
                "--display-name",
                "NewCo",
                "--admin-email",
                "admin@newco.com",
            ],
        )
        assert result.exit_code == 0
        assert "t-new" in result.output

    @pytest.mark.unit
    def test_create_json(self, runner, mock_api):
        mock_api.post.return_value = {"id": "t-new", "slug": "newco"}
        result = runner.invoke(
            cli,
            [
                "platform",
                "tenants",
                "create",
                "--slug",
                "newco",
                "--display-name",
                "NewCo",
                "--admin-email",
                "a@b.com",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["slug"] == "newco"

    @pytest.mark.unit
    def test_get(self, runner, mock_api):
        mock_api.get.return_value = {"id": "t-1", "slug": "acme", "display_name": "Acme Corp"}
        result = runner.invoke(cli, ["platform", "tenants", "get", "t-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["slug"] == "acme"

    @pytest.mark.unit
    def test_delete(self, runner, mock_api):
        mock_api.delete.return_value = None
        result = runner.invoke(cli, ["platform", "tenants", "delete", "t-1", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.output


class TestPlatformUsers:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api):
        mock_api.get.return_value = {
            "results": [
                {"id": "u-1", "email": "alice@acme.com", "status": "ACTIVE"},
                {"id": "u-2", "email": "bob@acme.com", "status": "INACTIVE"},
            ]
        }
        result = runner.invoke(cli, ["platform", "users", "list"])
        assert result.exit_code == 0
        assert "alice@acme.com" in result.output
        assert "INACTIVE" in result.output

    @pytest.mark.unit
    def test_list_json(self, runner, mock_api):
        mock_api.get.return_value = {"results": [{"id": "u-1"}]}
        result = runner.invoke(cli, ["platform", "users", "list", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["id"] == "u-1"

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api):
        mock_api.get.return_value = {"results": []}
        result = runner.invoke(cli, ["platform", "users", "list"])
        assert result.exit_code == 0
        assert "No users" in result.output

    @pytest.mark.unit
    def test_create(self, runner, mock_api):
        mock_api.post.return_value = {"id": "u-new", "email": "new@acme.com"}
        result = runner.invoke(
            cli,
            [
                "platform",
                "users",
                "create",
                "--email",
                "new@acme.com",
                "--tenant-id",
                "t-1",
                "--display-name",
                "New User",
            ],
        )
        assert result.exit_code == 0
        assert "u-new" in result.output

    @pytest.mark.unit
    def test_get(self, runner, mock_api):
        mock_api.get.return_value = {"id": "u-1", "email": "alice@acme.com"}
        result = runner.invoke(cli, ["platform", "users", "get", "u-1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["email"] == "alice@acme.com"


class TestPlatformImpersonate:
    @pytest.mark.unit
    def test_impersonate(self, runner, mock_api):
        mock_api.post.return_value = {"session_id": "imp-1", "user_id": "u-1", "tenant_id": "t-1"}  # noqa: PHASE216-STATIC-ID
        result = runner.invoke(
            cli,
            [
                "platform",
                "impersonate",
                "--user-id",
                "u-1",
                "--tenant-id",
                "t-1",
                "--reason",
                "Debugging issue #42",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["session_id"] == "imp-1"

    @pytest.mark.unit
    def test_impersonate_exit(self, runner, mock_api):
        mock_api.post.return_value = {"status": "exited"}
        result = runner.invoke(cli, ["platform", "impersonate-exit"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["status"] == "exited"
