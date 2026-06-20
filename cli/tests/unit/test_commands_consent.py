"""
Unit tests for Consent CLI commands.

Tests: purposes (list, create, delete), records (list, create), dashboard.
"""

from datahub_cli.main import cli


class TestConsentPurposes:
    """Test consent purposes subcommands"""

    def test_list_purposes(self, runner, mock_api_client):
        """Test listing consent purposes"""
        mock_api_client.get.return_value = {
            "results": [{"id": "p-1", "name": "Marketing", "required": False}]
        }

        result = runner.invoke(cli, ["consent", "purposes", "list"])

        assert result.exit_code == 0
        assert "Marketing" in result.output
        mock_api_client.get.assert_called_once_with("consent/consent-purposes/")

    def test_create_purpose(self, runner, mock_api_client):
        """Test creating a consent purpose"""
        mock_api_client.post.return_value = {"id": "p-2", "name": "Analytics"}

        result = runner.invoke(
            cli,
            [
                "consent",
                "purposes",
                "create",
                "--name",
                "Analytics",
                "--description",
                "Usage analytics",
                "--required",
            ],
        )

        assert result.exit_code == 0
        assert "Analytics" in result.output
        mock_api_client.post.assert_called_once_with(
            "consent/consent-purposes/",
            json={"name": "Analytics", "description": "Usage analytics", "required": True},
        )

    def test_delete_purpose(self, runner, mock_api_client):
        """Test deleting a consent purpose with confirmation"""
        result = runner.invoke(cli, ["consent", "purposes", "delete", "p-1", "--confirm"])

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        mock_api_client.delete.assert_called_once_with("consent/consent-purposes/p-1/")

    def test_delete_purpose_without_confirm(self, runner, mock_api_client):
        """Test deleting without --confirm raises error"""
        result = runner.invoke(cli, ["consent", "purposes", "delete", "p-1"])

        assert result.exit_code != 0
        assert "--confirm" in result.output


class TestConsentRecords:
    """Test consent records subcommands"""

    def test_list_records(self, runner, mock_api_client):
        """Test listing consent records"""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["consent", "records", "list"])

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with("consent/consent-records/")

    def test_create_record_granted(self, runner, mock_api_client):
        """Test creating a granted consent record"""
        mock_api_client.post.return_value = {"id": "cr-1", "granted": True}

        result = runner.invoke(
            cli, ["consent", "records", "create", "--purpose-id", "p-1", "--granted"]
        )

        assert result.exit_code == 0
        mock_api_client.post.assert_called_once_with(
            "consent/consent-records/", json={"purpose_id": "p-1", "granted": True}
        )

    def test_create_record_denied(self, runner, mock_api_client):
        """Test creating a denied consent record"""
        mock_api_client.post.return_value = {"id": "cr-2", "granted": False}

        result = runner.invoke(
            cli, ["consent", "records", "create", "--purpose-id", "p-1", "--denied"]
        )

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]["json"]["granted"] is False


class TestConsentDashboard:
    """Test consent dashboard command"""

    def test_dashboard(self, runner, mock_api_client):
        """Test consent dashboard"""
        mock_api_client.get.return_value = {"overall_compliance": "85%"}

        result = runner.invoke(cli, ["consent", "dashboard"])

        assert result.exit_code == 0
        assert "85%" in result.output
        mock_api_client.get.assert_called_once_with("consent/consent-dashboard/")
