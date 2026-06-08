"""Unit tests for ``datahub federated-import`` commands (284.A.4)."""
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
    monkeypatch.setattr("datahub_cli.commands.federated_import.api_client", mock)
    return mock


class TestProvidersList:
    @pytest.mark.unit
    def test_list_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "providers": [
                {"id": "snowflake_marketplace", "name": "Snowflake Marketplace", "credential_type": "snowflake_warehouse"},
                {"id": "aws_data_exchange", "name": "AWS Data Exchange", "credential_type": "aws_data_exchange"},
            ],
            "count": 2,
        }
        result = runner.invoke(cli, ["federated-import", "providers", "list"])
        assert result.exit_code == 0
        assert "snowflake_marketplace" in result.output
        assert "AWS Data Exchange" in result.output

    @pytest.mark.unit
    def test_list_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "providers": [{"id": "snowflake_marketplace", "name": "Snowflake Marketplace"}],
            "count": 1,
        }
        result = runner.invoke(cli, ["federated-import", "providers", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["id"] == "snowflake_marketplace"

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"providers": [], "count": 0}
        result = runner.invoke(cli, ["federated-import", "providers", "list"])
        assert result.exit_code == 0
        assert "No providers available" in result.output

    @pytest.mark.unit
    def test_list_api_error(self, runner, mock_api_client):
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("down")
        result = runner.invoke(cli, ["federated-import", "providers", "list"])
        assert result.exit_code != 0


class TestImportCreate:
    @pytest.mark.unit
    def test_create_success(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.status_code = 201
        mock_resp.text = "{}"
        mock_resp.json.return_value = {
            "id": "job-1",
            "status": "PENDING",
            "provider_id": "snowflake_marketplace",
            "data_strategy": "METADATA_ONLY",
        }
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli,
            [
                "federated-import", "import", "create",
                "--provider-id", "snowflake_marketplace",
                "--credential-ref", "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
            ],
        )
        assert result.exit_code == 0
        assert "job-1" in result.output
        assert "PENDING" in result.output

    @pytest.mark.unit
    def test_create_json(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.status_code = 201
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"id": "job-1", "status": "PENDING"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli,
            [
                "federated-import", "import", "create",
                "--provider-id", "snowflake_marketplace",
                "--credential-ref", "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "job-1"

    @pytest.mark.unit
    def test_create_missing_provider(self, runner, mock_api_client):
        result = runner.invoke(
            cli,
            [
                "federated-import", "import", "create",
                "--credential-ref", "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
            ],
        )
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_create_missing_credential(self, runner, mock_api_client):
        result = runner.invoke(
            cli,
            [
                "federated-import", "import", "create",
                "--provider-id", "snowflake_marketplace",
            ],
        )
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_create_with_data_strategy(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.status_code = 201
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"id": "job-1", "status": "PENDING", "data_strategy": "DOWNLOAD_ALL"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli,
            [
                "federated-import", "import", "create",
                "--provider-id", "snowflake_marketplace",
                "--credential-ref", "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                "--data-strategy", "DOWNLOAD_ALL",
            ],
        )
        assert result.exit_code == 0
        assert "DOWNLOAD_ALL" in result.output

    @pytest.mark.unit
    def test_create_api_error(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.status_code = 403
        mock_resp.text = '{"detail": "Federated import disabled"}'
        mock_resp.json.return_value = {"detail": "Federated import disabled"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli,
            [
                "federated-import", "import", "create",
                "--provider-id", "snowflake_marketplace",
                "--credential-ref", "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
            ],
        )
        assert result.exit_code != 0


class TestImportStatus:
    @pytest.mark.unit
    def test_status_table(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "id": "job-1",
            "type": "FEDERATED_IMPORT",
            "status": "RUNNING",
            "created_at": "2026-05-17T10:00:00Z",
        }
        result = runner.invoke(cli, ["federated-import", "import", "status", "job-1"])
        assert result.exit_code == 0
        assert "job-1" in result.output
        assert "RUNNING" in result.output

    @pytest.mark.unit
    def test_status_json(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"id": "job-1", "status": "COMPLETED"}
        result = runner.invoke(cli, ["federated-import", "import", "status", "job-1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "COMPLETED"

    @pytest.mark.unit
    def test_status_with_timestamps(self, runner, mock_api_client):
        mock_api_client.get.return_value = {
            "id": "job-1",
            "type": "FEDERATED_IMPORT",
            "status": "COMPLETED",
            "created_at": "2026-05-17T10:00:00Z",
            "updated_at": "2026-05-17T10:05:00Z",
            "completed_at": "2026-05-17T10:05:00Z",
        }
        result = runner.invoke(cli, ["federated-import", "import", "status", "job-1"])
        assert result.exit_code == 0
        assert "Updated" in result.output
        assert "Completed" in result.output


class TestImportCancel:
    @pytest.mark.unit
    def test_cancel_confirmed(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"id": "job-1", "status": "CANCELLED"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli,
            ["federated-import", "import", "cancel", "job-1", "--confirm"],
        )
        assert result.exit_code == 0
        assert "CANCELLED" in result.output

    @pytest.mark.unit
    def test_cancel_json(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"id": "job-1", "status": "CANCELLED"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli,
            ["federated-import", "import", "cancel", "job-1", "--confirm", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "CANCELLED"

    @pytest.mark.unit
    def test_cancel_aborted(self, runner, mock_api_client):
        result = runner.invoke(
            cli,
            ["federated-import", "import", "cancel", "job-1"],
            input="n",
        )
        assert result.exit_code == 0
        assert "Aborted" in result.output

    @pytest.mark.unit
    def test_cancel_api_error(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.status_code = 409
        mock_resp.text = '{"detail": "Job already terminal"}'
        mock_resp.json.return_value = {"detail": "Job already terminal"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli,
            ["federated-import", "import", "cancel", "job-1", "--confirm"],
        )
        assert result.exit_code != 0
        assert "409" in result.output
