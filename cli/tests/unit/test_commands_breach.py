"""
Unit tests for Breach CLI commands.

Tests: create, list, get, update-status, sla commands.
"""

import json

from datahub_cli.main import cli


class TestBreachCreate:
    """Test breach create command"""

    def test_create_breach_success(self, runner, mock_api_client):
        """Test creating a breach incident successfully"""
        mock_api_client.post.return_value = {
            "id": "breach-1",
            "status": "OPEN",
            "sla_level": "STANDARD",
            "notification_deadline": "2026-01-15T00:00:00Z",
        }

        result = runner.invoke(
            cli,
            ["breach", "create", "--title", "Data leak", "--description", "Personal data exposed"],
        )

        assert result.exit_code == 0
        assert "breach-1" in result.output
        mock_api_client.post.assert_called_once()

    def test_create_breach_json_format(self, runner, mock_api_client):
        """Test creating breach with JSON output"""
        mock_api_client.post.return_value = {"id": "breach-2", "status": "OPEN"}

        result = runner.invoke(
            cli,
            ["breach", "create", "--title", "Test", "--description", "Desc", "--format", "json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "breach-2"

    def test_create_breach_with_all_options(self, runner, mock_api_client):
        """Test creating breach with all optional fields"""
        mock_api_client.post.return_value = {"id": "breach-3", "status": "OPEN"}

        result = runner.invoke(
            cli,
            [
                "breach",
                "create",
                "--title",
                "Critical breach",
                "--description",
                "Full description",
                "--sla-level",
                "CRITICAL",
                "--affected-categories",
                "PII,financial",
                "--affected-count",
                "1000",
                "--discovered-at",
                "2026-01-01T00:00:00Z",
                "--notification-deadline",
                "2026-01-04T00:00:00Z",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        payload = call_args[1]["data"]
        assert payload["sla_level"] == "CRITICAL"
        assert payload["affected_subjects_count"] == 1000

    def test_create_breach_api_error(self, runner, mock_api_client):
        """Test create handles API error"""
        mock_api_client.post.side_effect = Exception("Internal error")

        result = runner.invoke(
            cli, ["breach", "create", "--title", "Test", "--description", "Desc"]
        )

        assert result.exit_code == 1
        assert "Error" in result.output


class TestBreachList:
    """Test breach list command"""

    def test_list_breaches(self, runner, mock_api_client):
        """Test listing breach incidents"""
        mock_api_client.get.return_value = {
            "results": [
                {"id": "breach-1", "status": "OPEN", "sla_level": "STANDARD", "title": "Test"}
            ],
            "count": 1,
        }

        result = runner.invoke(cli, ["breach", "list"])

        assert result.exit_code == 0
        assert "breach-1" in result.output

    def test_list_breaches_json_format(self, runner, mock_api_client):
        """Test listing breaches in JSON"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["breach", "list", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "results" in data

    def test_list_breaches_with_filters(self, runner, mock_api_client):
        """Test listing with status and SLA filters"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(
            cli, ["breach", "list", "--status", "OPEN", "--sla-level", "HIGH", "--page", "2"]
        )

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once()
        call_args = mock_api_client.get.call_args
        assert call_args[1]["params"]["status"] == "OPEN"
        assert call_args[1]["params"]["sla_level"] == "HIGH"


class TestBreachGet:
    """Test breach get command"""

    def test_get_breach(self, runner, mock_api_client):
        """Test getting breach details"""
        mock_api_client.get.return_value = {
            "id": "breach-1",
            "title": "Test",
            "status": "OPEN",
            "sla_level": "STANDARD",
            "description": "Details",
        }

        result = runner.invoke(cli, ["breach", "get", "--incident-id", "breach-1"])

        assert result.exit_code == 0
        assert "Test" in result.output
        mock_api_client.get.assert_called_once_with("governance/breach-incidents/breach-1/")


class TestBreachUpdateStatus:
    """Test breach update-status command"""

    def test_update_status(self, runner, mock_api_client):
        """Test updating breach status"""
        mock_api_client.patch.return_value = {"status": "RESOLVED"}

        result = runner.invoke(
            cli,
            [
                "breach",
                "update-status",
                "--incident-id",
                "breach-1",
                "--status",
                "RESOLVED",
                "--resolution-note",
                "Issue fixed",
            ],
        )

        assert result.exit_code == 0
        assert "RESOLVED" in result.output
        mock_api_client.patch.assert_called_once_with(
            "governance/breach-incidents/breach-1/status/",
            data={"status": "RESOLVED", "notes": "Issue fixed"},
        )


class TestBreachSLA:
    """Test breach SLA command"""

    def test_sla_status(self, runner, mock_api_client):
        """Test getting SLA status"""
        mock_api_client.get.return_value = {
            "id": "breach-1",
            "sla_level": "CRITICAL",
            "status": "OPEN",
            "notification_deadline": "2026-01-04T00:00:00Z",
        }

        result = runner.invoke(cli, ["breach", "sla", "--incident-id", "breach-1"])

        assert result.exit_code == 0
        assert "CRITICAL" in result.output
