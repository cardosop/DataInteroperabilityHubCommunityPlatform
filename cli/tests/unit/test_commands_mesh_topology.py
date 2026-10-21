from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive unit tests for Mesh Topology CLI commands.

Tests all topology commands: get, get-domain.
"""
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from datahub_cli.main import cli


@pytest.fixture
def runner():
    """Create CLI runner"""
    return CliRunner()


@pytest.fixture
def mock_api_client():
    """Mock API client for testing"""
    with patch("datahub_cli.commands.mesh.api_client") as mock_client:
        yield mock_client


class TestMeshTopologyGet:
    """Test mesh topology get command"""

    def test_get_topology_success_table_format(self, runner, mock_api_client):
        """Test getting topology in table format"""
        mock_data = {
            "summary": {
                "total_domains": 2,
                "active_domains": 2,
                "total_relationships": 1,
                "average_health_score": 85.5,
            },
            "metadata": {
                "tenant_id": "tenant-1",
                "domain_count": 2,
                "relationship_count": 1,
                "generated_at": "2025-01-01T00:00:00Z",
            },
            "nodes": [
                {
                    "id": "domain-1",
                    "name": "Test Domain 1",
                    "status": "ACTIVE",
                    "health_metrics": {"health_score": 90.0, "compliance_status": "COMPLIANT"},
                },
                {
                    "id": "domain-2",
                    "name": "Test Domain 2",
                    "status": "ACTIVE",
                    "health_metrics": {"health_score": 81.0, "compliance_status": "COMPLIANT"},
                },
            ],
            "edges": [
                {"source": "domain-1", "target": "domain-2", "type": "SHARED_POLICY", "weight": 5}
            ],
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get"])

        assert result.exit_code == 0
        assert "MESH TOPOLOGY SUMMARY" in result.output
        assert "Total Domains: 2" in result.output
        assert "Active Domains: 2" in result.output
        assert "Total Relationships: 1" in result.output
        assert "Average Health Score: 85.50" in result.output
        assert "DOMAINS" in result.output
        assert "domain-1" in result.output
        assert "Test Domain 1" in result.output
        assert "RELATIONSHIPS" in result.output
        assert "SHARED_POLICY" in result.output
        mock_api_client.get.assert_called_once()
        call_args = mock_api_client.get.call_args
        assert call_args[0][0] == "mesh/topology/"
        assert call_args[1]["params"]["include_health_metrics"] == "true"

    def test_get_topology_success_json_format(self, runner, mock_api_client):
        """Test getting topology in JSON format"""
        mock_data = {
            "summary": {
                "total_domains": 1,
                "active_domains": 1,
                "total_relationships": 0,
                "average_health_score": 90.0,
            },
            "metadata": {
                "tenant_id": "tenant-1",
                "domain_count": 1,
                "relationship_count": 0,
                "generated_at": "2025-01-01T00:00:00Z",
            },
            "nodes": [{"id": "domain-1", "name": "Test Domain", "status": "ACTIVE"}],
            "edges": [],
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert "summary" in output_data
        assert "nodes" in output_data
        assert "edges" in output_data
        assert "metadata" in output_data
        assert output_data["summary"]["total_domains"] == 1

    def test_get_topology_without_health_metrics(self, runner, mock_api_client):
        """Test getting topology without health metrics"""
        mock_data = {
            "summary": {"total_domains": 0, "active_domains": 0, "total_relationships": 0},
            "metadata": {"tenant_id": "tenant-1", "domain_count": 0, "relationship_count": 0},
            "nodes": [],
            "edges": [],
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get", "--no-include-health-metrics"])

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once()
        call_args = mock_api_client.get.call_args
        assert call_args[1]["params"]["include_health_metrics"] == "false"

    def test_get_topology_empty_topology(self, runner, mock_api_client):
        """Test getting topology with no domains"""
        mock_data = {
            "summary": {
                "total_domains": 0,
                "active_domains": 0,
                "total_relationships": 0,
                "average_health_score": None,
            },
            "metadata": {
                "tenant_id": "tenant-1",
                "domain_count": 0,
                "relationship_count": 0,
                "generated_at": "2025-01-01T00:00:00Z",
            },
            "nodes": [],
            "edges": [],
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get"])

        assert result.exit_code == 0
        assert "Total Domains: 0" in result.output
        assert "No domains found." in result.output
        assert "No relationships found." in result.output

    def test_get_topology_with_null_health_score(self, runner, mock_api_client):
        """Test topology with null health score"""
        mock_data = {
            "summary": {
                "total_domains": 1,
                "active_domains": 1,
                "total_relationships": 0,
                "average_health_score": None,
            },
            "metadata": {
                "tenant_id": "tenant-1",
                "domain_count": 1,
                "relationship_count": 0,
                "generated_at": "2025-01-01T00:00:00Z",
            },
            "nodes": [
                {
                    "id": "domain-1",
                    "name": "Test Domain",
                    "status": "ACTIVE",
                    "health_metrics": None,
                }
            ],
            "edges": [],
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get"])

        assert result.exit_code == 0
        assert "Average Health Score: N/A" in result.output
        assert "N/A" in result.output  # Health score for domain

    def test_get_topology_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.get.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ["mesh", "topology", "get"])

        assert result.exit_code != 0
        assert "Failed to get topology" in result.output

    def test_get_topology_click_exception(self, runner, mock_api_client):
        """Test handling ClickException from API client"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("Authentication failed")

        result = runner.invoke(cli, ["mesh", "topology", "get"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output


class TestMeshTopologyGetDomain:
    """Test mesh topology get-domain command"""

    def test_get_domain_topology_success_table_format(self, runner, mock_api_client):
        """Test getting domain topology in table format"""
        domain_id = "domain-1"
        mock_data = {
            "domain": {
                "id": domain_id,
                "name": "Test Domain",
                "status": "ACTIVE",
                "description": "Test Description",
                "owner_id": "owner-1",
                "created_at": "2025-01-01T00:00:00Z",
            },
            "relationships": [
                {"source": domain_id, "target": "domain-2", "type": "SHARED_POLICY", "weight": 5},
                {"source": "domain-3", "target": domain_id, "type": "DATA_SHARING", "weight": 3},
            ],
            "health_metrics": {
                "health_score": 90.0,
                "compliance_status": "COMPLIANT",
                "violations_count": 0,
            },
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get-domain", domain_id])

        assert result.exit_code == 0
        assert "DOMAIN TOPOLOGY" in result.output
        assert f"Domain ID: {domain_id}" in result.output
        assert "Name: Test Domain" in result.output
        assert "Status: ACTIVE" in result.output
        assert "Description: Test Description" in result.output
        assert "Owner ID: owner-1" in result.output
        assert "HEALTH METRICS" in result.output
        assert "Health Score: 90.00" in result.output
        assert "Compliance Status: COMPLIANT" in result.output
        assert "Violations Count: 0" in result.output
        assert "RELATIONSHIPS" in result.output
        assert "SHARED_POLICY" in result.output
        assert "DATA_SHARING" in result.output
        mock_api_client.get.assert_called_once_with(f"mesh/topology/{domain_id}/")

    def test_get_domain_topology_success_json_format(self, runner, mock_api_client):
        """Test getting domain topology in JSON format"""
        domain_id = "domain-1"
        mock_data = {
            "domain": {"id": domain_id, "name": "Test Domain", "status": "ACTIVE"},
            "relationships": [],
            "health_metrics": {"health_score": 85.0},
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(
            cli, ["mesh", "topology", "get-domain", domain_id, "--format", "json"]
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert "domain" in output_data
        assert "relationships" in output_data
        assert "health_metrics" in output_data
        assert output_data["domain"]["id"] == domain_id

    def test_get_domain_topology_no_relationships(self, runner, mock_api_client):
        """Test getting domain topology with no relationships"""
        domain_id = "domain-1"
        mock_data = {
            "domain": {"id": domain_id, "name": "Test Domain", "status": "ACTIVE"},
            "relationships": [],
            "health_metrics": {"health_score": 90.0},
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get-domain", domain_id])

        assert result.exit_code == 0
        assert "No relationships found." in result.output

    def test_get_domain_topology_no_health_metrics(self, runner, mock_api_client):
        """Test getting domain topology with no health metrics"""
        domain_id = "domain-1"
        mock_data = {
            "domain": {"id": domain_id, "name": "Test Domain", "status": "ACTIVE"},
            "relationships": [],
            "health_metrics": None,
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get-domain", domain_id])

        assert result.exit_code == 0
        assert "No health metrics available." in result.output

    def test_get_domain_topology_null_health_score(self, runner, mock_api_client):
        """Test domain topology with null health score"""
        domain_id = "domain-1"
        mock_data = {
            "domain": {"id": domain_id, "name": "Test Domain", "status": "ACTIVE"},
            "relationships": [],
            "health_metrics": {"health_score": None, "compliance_status": "UNKNOWN"},
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get-domain", domain_id])

        assert result.exit_code == 0
        assert "Health Score: N/A" in result.output

    def test_get_domain_topology_missing_optional_fields(self, runner, mock_api_client):
        """Test domain topology with missing optional fields"""
        domain_id = "domain-1"
        mock_data = {
            "domain": {"id": domain_id, "name": "Test Domain", "status": "ACTIVE"},
            "relationships": [],
            "health_metrics": {"health_score": 90.0},
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get-domain", domain_id])

        assert result.exit_code == 0
        # Should not crash when optional fields are missing
        assert "Domain ID:" in result.output
        assert "Name: Test Domain" in result.output

    def test_get_domain_topology_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        domain_id = "domain-1"
        mock_api_client.get.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ["mesh", "topology", "get-domain", domain_id])

        assert result.exit_code != 0
        assert "Failed to get domain topology" in result.output

    def test_get_domain_topology_not_found(self, runner, mock_api_client):
        """Test handling domain not found error"""
        domain_id = "non-existent-domain"
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("API error (NOT_FOUND): Domain not found")

        result = runner.invoke(cli, ["mesh", "topology", "get-domain", domain_id])

        assert result.exit_code != 0
        assert "Domain not found" in result.output

    def test_get_domain_topology_click_exception(self, runner, mock_api_client):
        """Test handling ClickException from API client"""
        domain_id = "domain-1"
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("Authentication failed")

        result = runner.invoke(cli, ["mesh", "topology", "get-domain", domain_id])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output


class TestMeshTopologyCommandStructure:
    """Test mesh topology command group structure"""

    def test_topology_command_group_exists(self, runner):
        """Test that topology command group exists"""
        result = runner.invoke(cli, ["mesh", "topology", "--help"])
        assert result.exit_code == 0
        assert "Topology management commands" in result.output

    def test_topology_get_command_exists(self, runner):
        """Test that topology get command exists"""
        result = runner.invoke(cli, ["mesh", "topology", "get", "--help"])
        assert result.exit_code == 0
        assert "Get complete data mesh topology" in result.output

    def test_topology_get_domain_command_exists(self, runner):
        """Test that topology get-domain command exists"""
        result = runner.invoke(cli, ["mesh", "topology", "get-domain", "--help"])
        assert result.exit_code == 0
        assert "Get topology view for a specific domain" in result.output

    def test_topology_get_command_format_option(self, runner):
        """Test that format option exists for get command"""
        result = runner.invoke(cli, ["mesh", "topology", "get", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "json" in result.output
        assert "table" in result.output

    def test_topology_get_domain_command_format_option(self, runner):
        """Test that format option exists for get-domain command"""
        result = runner.invoke(cli, ["mesh", "topology", "get-domain", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "json" in result.output
        assert "table" in result.output

    def test_topology_get_command_health_metrics_option(self, runner):
        """Test that include-health-metrics option exists for get command"""
        result = runner.invoke(cli, ["mesh", "topology", "get", "--help"])
        assert result.exit_code == 0
        assert (
            "--include-health-metrics" in result.output
            or "--no-include-health-metrics" in result.output
        )


class TestMeshTopologyOutputFormatting:
    """Test output formatting for topology commands"""

    def test_get_topology_table_formatting_with_long_names(self, runner, mock_api_client):
        """Test table formatting handles long domain names"""
        mock_data = {
            "summary": {
                "total_domains": 1,
                "active_domains": 1,
                "total_relationships": 0,
                "average_health_score": 90.0,
            },
            "metadata": {
                "tenant_id": "tenant-1",
                "domain_count": 1,
                "relationship_count": 0,
                "generated_at": "2025-01-01T00:00:00Z",
            },
            "nodes": [
                {
                    "id": "domain-1",
                    "name": "A" * 50,  # Very long name
                    "status": "ACTIVE",
                    "health_metrics": {"health_score": 90.0},
                }
            ],
            "edges": [],
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get"])

        assert result.exit_code == 0
        # Should truncate long names
        assert (
            ".." in result.output
            or len([line for line in result.output.split("\n") if "A" * 50 in line]) == 0
        )

    def test_get_domain_topology_table_formatting(self, runner, mock_api_client):
        """Test table formatting for domain topology"""
        domain_id = "domain-1"
        mock_data = {
            "domain": {
                "id": domain_id,
                "name": "Test Domain",
                "status": "ACTIVE",
                "description": "Test Description",
                "owner_id": "owner-1",
                "created_at": "2025-01-01T00:00:00Z",
            },
            "relationships": [
                {"source": domain_id, "target": "domain-2", "type": "SHARED_POLICY", "weight": 5}
            ],
            "health_metrics": {
                "health_score": 90.0,
                "compliance_status": "COMPLIANT",
                "violations_count": 0,
            },
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "topology", "get-domain", domain_id])

        assert result.exit_code == 0
        # Check that table structure is present
        assert "DOMAIN TOPOLOGY" in result.output
        assert "HEALTH METRICS" in result.output
        assert "RELATIONSHIPS" in result.output
        # Check that headers are present
        assert "Source Domain ID" in result.output or "Source" in result.output
        assert "Target Domain ID" in result.output or "Target" in result.output
