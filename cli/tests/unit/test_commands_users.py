"""Unit tests for ``datahub users`` commands (278.AA.4)."""

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
    monkeypatch.setattr("datahub_cli.commands.users.api_client", mock)
    return mock


class TestUsersList:
    @pytest.mark.unit
    def test_list_users_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "results": [
                {"id": "u1", "name": "Alice", "email": "a@x.com", "roles": ["DATA_ENGINEER"]},
                {"id": "u2", "name": "Bob", "email": "b@x.com", "roles": ["TENANT_ADMIN"]},
            ]
        }
        result = runner.invoke(cli, ["users", "list"])
        assert result.exit_code == 0
        assert "Alice" in result.output
        assert "Bob" in result.output
        assert "DATA_ENGINEER" in result.output
        mock_api_client.get.assert_called_once_with("users/", params={"limit": 50, "offset": 0})

    @pytest.mark.unit
    def test_list_users_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": [{"id": "u1", "email": "a@x.com"}]}
        result = runner.invoke(cli, ["users", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["email"] == "a@x.com"

    @pytest.mark.unit
    def test_list_users_empty(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": []}
        result = runner.invoke(cli, ["users", "list"])
        assert result.exit_code == 0
        assert "No users found" in result.output

    @pytest.mark.unit
    def test_list_users_filters(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"results": []}
        result = runner.invoke(cli, ["users", "list", "--limit", "10", "--offset", "5"])
        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with("users/", params={"limit": 10, "offset": 5})

    @pytest.mark.unit
    def test_list_users_api_error(self, runner, mock_api_client):
        from datahub_cli.errors import CLIError

        mock_api_client.get.side_effect = CLIError("boom", "TEST")
        result = runner.invoke(cli, ["users", "list"])
        assert result.exit_code != 0
        assert "boom" in result.output


class TestUsersGet:
    @pytest.mark.unit
    def test_get_user_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "id": "u1",
            "name": "Alice",
            "email": "a@x.com",
            "roles": ["DATA_ENGINEER"],
            "tenant_name": "acme",  # noqa: PHASE216-STATIC-ID
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
        }
        result = runner.invoke(cli, ["users", "get", "u1"])
        assert result.exit_code == 0
        assert "a@x.com" in result.output
        assert "DATA_ENGINEER" in result.output
        mock_api_client.get.assert_called_once_with("users/u1/")

    @pytest.mark.unit
    def test_get_user_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"id": "u1", "email": "a@x.com"}
        result = runner.invoke(cli, ["users", "get", "u1", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["email"] == "a@x.com"

    @pytest.mark.unit
    def test_get_user_api_error(self, runner, mock_api_client):
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("not found")
        result = runner.invoke(cli, ["users", "get", "u1"])
        assert result.exit_code != 0


class TestUsersInvite:
    @pytest.mark.unit
    def test_invite_minimal(self, runner, mock_api_client):
        mock_api_client.post.return_value = {"id": "u1", "invitation_token": "tok123"}
        result = runner.invoke(cli, ["users", "invite", "--email", "a@x.com"])
        assert result.exit_code == 0
        assert "a@x.com" in result.output
        mock_api_client.post.assert_called_once_with(
            "users/invite/", json_data={"email": "a@x.com"}
        )

    @pytest.mark.unit
    def test_invite_with_name_and_roles(self, runner, mock_api_client):
        mock_api_client.post.return_value = {"id": "u1"}
        result = runner.invoke(
            cli,
            [
                "users",
                "invite",
                "--email",
                "a@x.com",
                "--name",
                "Alice",
                "--role",
                "DATA_ENGINEER",
                "--role",
                "TENANT_ADMIN",
            ],
        )
        assert result.exit_code == 0
        call = mock_api_client.post.call_args
        assert call[1]["json_data"]["email"] == "a@x.com"
        assert call[1]["json_data"]["name"] == "Alice"
        assert call[1]["json_data"]["roles"] == ["DATA_ENGINEER", "TENANT_ADMIN"]

    @pytest.mark.unit
    def test_invite_json(self, runner, mock_api_client):
        mock_api_client.post.return_value = {"id": "u1", "invitation_token": "t"}
        result = runner.invoke(cli, ["users", "invite", "--email", "a@x.com", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["id"] == "u1"

    @pytest.mark.unit
    def test_invite_api_error(self, runner, mock_api_client):
        from click import ClickException

        mock_api_client.post.side_effect = ClickException("invalid")
        result = runner.invoke(cli, ["users", "invite", "--email", "a@x.com"])
        assert result.exit_code != 0


class TestUsersRoles:
    @pytest.mark.unit
    def test_roles_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "id": "u1",
            "email": "a@x.com",
            "roles": ["DATA_ENGINEER", "TENANT_ADMIN"],
        }
        result = runner.invoke(cli, ["users", "roles", "u1"])
        assert result.exit_code == 0
        assert "DATA_ENGINEER" in result.output
        assert "TENANT_ADMIN" in result.output

    @pytest.mark.unit
    def test_roles_none(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"id": "u1", "email": "a@x.com", "roles": []}
        result = runner.invoke(cli, ["users", "roles", "u1"])
        assert result.exit_code == 0
        assert "(none)" in result.output

    @pytest.mark.unit
    def test_roles_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"id": "u1", "roles": ["ADMIN"]}
        result = runner.invoke(cli, ["users", "roles", "u1", "--format", "json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["roles"] == ["ADMIN"]
