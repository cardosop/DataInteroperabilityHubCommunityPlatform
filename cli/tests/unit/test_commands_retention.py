"""
Unit tests for Retention CLI commands.

Tests: list-policies, create-policy, update-policy, delete-policy, sweep-status.
"""

import json

from datahub_cli.main import cli


class TestRetentionListPolicies:
    """Test list-policies command"""

    def test_list_policies(self, runner, mock_api_client):
        """Test listing retention policies"""
        mock_api_client.get.return_value = {
            "results": [
                {
                    "id": "rp-1",
                    "event_type": "SEARCH_PERFORMED",
                    "retention_days": 30,
                    "description": "Search audit retention",
                }
            ],
            "count": 1,
        }

        result = runner.invoke(cli, ["retention", "list-policies"])

        assert result.exit_code == 0
        assert "SEARCH_PERFORMED" in result.output
        assert "30" in result.output

    def test_list_policies_json(self, runner, mock_api_client):
        """Test listing in JSON format"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["retention", "list-policies", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "results" in data

    def test_list_policies_error(self, runner, mock_api_client):
        """Test list handles API error"""
        mock_api_client.get.side_effect = Exception("DB error")

        result = runner.invoke(cli, ["retention", "list-policies"])

        assert result.exit_code == 1


class TestRetentionCreatePolicy:
    """Test create-policy command"""

    def test_create_policy(self, runner, mock_api_client):
        """Test creating a retention policy"""
        mock_api_client.post.return_value = {
            "id": "rp-new",
            "event_type": "SEARCH_PERFORMED",
            "retention_days": 60,
        }

        result = runner.invoke(
            cli,
            [
                "retention",
                "create-policy",
                "--event-type",
                "SEARCH_PERFORMED",
                "--retention-days",
                "60",
                "--description",
                "Extended retention for search",
            ],
        )

        assert result.exit_code == 0
        assert "rp-new" in result.output
        mock_api_client.post.assert_called_once_with(
            "audit/event-retention-policies/",
            data={
                "event_type": "SEARCH_PERFORMED",
                "retention_days": 60,
                "description": "Extended retention for search",
            },
        )

    def test_create_policy_error(self, runner, mock_api_client):
        """Test create handles API error"""
        mock_api_client.post.side_effect = Exception("Conflict")

        result = runner.invoke(
            cli,
            [
                "retention",
                "create-policy",
                "--event-type",
                "SEARCH_PERFORMED",
                "--retention-days",
                "30",
            ],
        )

        assert result.exit_code == 1


class TestRetentionUpdatePolicy:
    """Test update-policy command"""

    def test_update_policy(self, runner, mock_api_client):
        """Test updating a retention policy"""
        mock_api_client.patch.return_value = {"id": "rp-1", "retention_days": 90}

        result = runner.invoke(
            cli, ["retention", "update-policy", "--policy-id", "rp-1", "--retention-days", "90"]
        )

        assert result.exit_code == 0
        assert "90" in result.output


class TestRetentionDeletePolicy:
    """Test delete-policy command"""

    def test_delete_policy(self, runner, mock_api_client):
        """Test deleting a retention policy"""
        result = runner.invoke(cli, ["retention", "delete-policy", "--policy-id", "rp-1"])

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        mock_api_client.delete.assert_called_once_with("audit/event-retention-policies/rp-1/")


class TestRetentionSweepStatus:
    """Test sweep-status command"""

    def test_sweep_status(self, runner, mock_api_client):
        """Test getting sweep status"""
        mock_api_client.get.return_value = {
            "results": [{"id": "evt-1", "event_type": "SEARCH_PERFORMED"}]
        }

        result = runner.invoke(cli, ["retention", "sweep-status"])

        assert result.exit_code == 0
        assert "sweep" in result.output.lower()
