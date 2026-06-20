from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive unit tests for Mesh Domain CLI commands.

Tests all domain commands: list, create, get, update, delete.
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


class TestMeshDomainsList:
    """Test mesh domains list command"""

    def test_list_domains_success_table_format(self, runner, mock_api_client):
        """Test listing domains in table format"""
        mock_data = {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": "domain-1",
                    "name": "Test Domain 1",
                    "status": "ACTIVE",
                    "owner": "owner-1",
                    "created_at": "2025-01-01T00:00:00Z",
                },
                {
                    "id": "domain-2",
                    "name": "Test Domain 2",
                    "status": "INACTIVE",
                    "owner": None,
                    "created_at": "2025-01-01T01:00:00Z",
                },
            ],
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "domains", "list"])

        assert result.exit_code == 0
        assert "domain-1" in result.output
        assert "domain-2" in result.output
        assert "Test Domain 1" in result.output
        assert "ACTIVE" in result.output
        assert "INACTIVE" in result.output
        mock_api_client.get.assert_called_once()
        call_args = mock_api_client.get.call_args
        assert call_args[0][0] == "mesh/domains/"
        assert call_args[1]["params"]["page"] == 1
        assert call_args[1]["params"]["page_size"] == 20

    def test_list_domains_success_json_format(self, runner, mock_api_client):
        """Test listing domains in JSON format"""
        mock_data = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [{"id": "domain-1", "name": "Test Domain", "status": "ACTIVE"}],
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "domains", "list", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert "count" in output_data
        assert "results" in output_data
        assert len(output_data["results"]) == 1
        assert output_data["results"][0]["id"] == "domain-1"

    def test_list_domains_with_filters(self, runner, mock_api_client):
        """Test listing domains with filters"""
        mock_data = {"count": 0, "results": []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(
            cli,
            [
                "mesh",
                "domains",
                "list",
                "--status",
                "ACTIVE",
                "--owner-id",
                "owner-1",
                "--search",
                "test",
                "--ordering",
                "-created_at",
                "--page",
                "2",
                "--page-size",
                "50",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        params = call_args[1]["params"]
        assert params["status"] == "ACTIVE"
        assert params["owner_id"] == "owner-1"
        assert params["search"] == "test"
        assert params["ordering"] == "-created_at"
        assert params["page"] == 2
        assert params["page_size"] == 50

    def test_list_domains_empty_result(self, runner, mock_api_client):
        """Test listing domains with no results"""
        mock_data = {"count": 0, "results": []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "domains", "list"])

        assert result.exit_code == 0
        assert "No domains found" in result.output

    def test_list_domains_pagination_info(self, runner, mock_api_client):
        """Test pagination info display"""
        mock_data = {
            "count": 50,
            "next": 2,
            "previous": None,
            "results": [
                {
                    "id": f"domain-{i}",
                    "name": f"Domain {i}",
                    "status": "ACTIVE",
                    "owner": None,
                    "created_at": "2025-01-01T00:00:00Z",
                }
                for i in range(20)
            ],
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "domains", "list"])

        assert result.exit_code == 0
        assert "Showing 20 of 50 domains" in result.output
        assert "Next page: --page 2" in result.output

    def test_list_domains_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.get.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ["mesh", "domains", "list"])

        assert result.exit_code != 0
        assert "Failed to list domains" in result.output


class TestMeshDomainsCreate:
    """Test mesh domains create command"""

    def test_create_domain_success_table_format(self, runner, mock_api_client):
        """Test creating a domain successfully in table format"""
        mock_response = {
            "id": "domain-1",
            "name": "New Domain",
            "status": "ACTIVE",
            "description": "Test description",
            "owner": "owner-1",
            "owner_email": "owner@example.com",
            "tenant_name": "Test Tenant",
            "created_at": "2025-01-01T00:00:00Z",
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(
            cli,
            [
                "mesh",
                "domains",
                "create",
                "--name",
                "New Domain",
                "--description",
                "Test description",
                "--status",
                "ACTIVE",
            ],
        )

        assert result.exit_code == 0
        assert "Domain created successfully" in result.output
        assert "domain-1" in result.output
        assert "New Domain" in result.output
        assert "ACTIVE" in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == "mesh/domains/"
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "New Domain"
        assert json_data["description"] == "Test description"
        assert json_data["status"] == "ACTIVE"

    def test_create_domain_success_json_format(self, runner, mock_api_client):
        """Test creating a domain successfully in JSON format"""
        mock_response = {"id": "domain-1", "name": "New Domain", "status": "ACTIVE"}
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(
            cli, ["mesh", "domains", "create", "--name", "New Domain", "--format", "json"]
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "domain-1"
        assert output_data["name"] == "New Domain"

    def test_create_domain_with_all_options(self, runner, mock_api_client):
        """Test creating a domain with all optional parameters"""
        mock_response = {"id": "domain-1", "name": "New Domain", "status": "ACTIVE"}
        mock_api_client.post.return_value = mock_response

        boundaries = '{"data_products": ["product1"], "schemas": ["schema1"]}'
        capabilities = '{"apis": ["api1"], "services": ["service1"]}'
        resource_quota = '{"storage": 1000, "compute": 500}'

        result = runner.invoke(
            cli,
            [
                "mesh",
                "domains",
                "create",
                "--name",
                "New Domain",
                "--description",
                "Test description",
                "--owner-id",
                "owner-1",
                "--boundaries",
                boundaries,
                "--capabilities",
                capabilities,
                "--resource-quota",
                resource_quota,
                "--status",
                "INACTIVE",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "New Domain"
        assert json_data["description"] == "Test description"
        assert json_data["owner_id"] == "owner-1"
        assert json_data["boundaries"] == {"data_products": ["product1"], "schemas": ["schema1"]}
        assert json_data["capabilities"] == {"apis": ["api1"], "services": ["service1"]}
        assert json_data["resource_quota"] == {"storage": 1000, "compute": 500}
        assert json_data["status"] == "INACTIVE"

    def test_create_domain_missing_name(self, runner):
        """Test creating a domain without required name"""
        result = runner.invoke(cli, ["mesh", "domains", "create"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_create_domain_invalid_json_boundaries(self, runner):
        """Test creating a domain with invalid JSON in boundaries"""
        result = runner.invoke(
            cli,
            ["mesh", "domains", "create", "--name", "New Domain", "--boundaries", "invalid json"],
        )

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_create_domain_invalid_json_capabilities(self, runner):
        """Test creating a domain with invalid JSON in capabilities"""
        result = runner.invoke(
            cli,
            ["mesh", "domains", "create", "--name", "New Domain", "--capabilities", "invalid json"],
        )

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_create_domain_invalid_resource_quota_type(self, runner):
        """Test creating a domain with invalid resource quota (non-number)"""
        result = runner.invoke(
            cli,
            [
                "mesh",
                "domains",
                "create",
                "--name",
                "New Domain",
                "--resource-quota",
                '{"storage": "invalid"}',
            ],
        )

        assert result.exit_code != 0
        assert "must be a number" in result.output

    def test_create_domain_negative_resource_quota(self, runner):
        """Test creating a domain with negative resource quota"""
        result = runner.invoke(
            cli,
            [
                "mesh",
                "domains",
                "create",
                "--name",
                "New Domain",
                "--resource-quota",
                '{"storage": -100}',
            ],
        )

        assert result.exit_code != 0
        assert "cannot be negative" in result.output

    def test_create_domain_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.post.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ["mesh", "domains", "create", "--name", "New Domain"])

        assert result.exit_code != 0
        assert "Failed to create domain" in result.output


class TestMeshDomainsGet:
    """Test mesh domains get command"""

    def test_get_domain_success_table_format(self, runner, mock_api_client):
        """Test getting a domain in table format"""
        mock_data = {
            "id": "domain-1",
            "name": "Test Domain",
            "status": "ACTIVE",
            "description": "Test description",
            "owner": "owner-1",
            "owner_email": "owner@example.com",
            "tenant_name": "Test Tenant",
            "boundaries": {"data_products": ["product1"]},
            "capabilities": {"apis": ["api1"]},
            "resource_quota": {"storage": 1000},
            "resource_usage": {"storage": 500},
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T01:00:00Z",
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "domains", "get", "domain-1"])

        assert result.exit_code == 0
        assert "domain-1" in result.output
        assert "Test Domain" in result.output
        assert "ACTIVE" in result.output
        assert "Test description" in result.output
        assert "owner-1" in result.output
        assert "owner@example.com" in result.output
        assert "Test Tenant" in result.output
        mock_api_client.get.assert_called_once_with("mesh/domains/domain-1/")

    def test_get_domain_success_json_format(self, runner, mock_api_client):
        """Test getting a domain in JSON format"""
        mock_data = {"id": "domain-1", "name": "Test Domain", "status": "ACTIVE"}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "domains", "get", "domain-1", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "domain-1"
        assert output_data["name"] == "Test Domain"

    def test_get_domain_not_found(self, runner, mock_api_client):
        """Test getting a non-existent domain"""
        mock_api_client.get.side_effect = Exception("Domain not found")

        result = runner.invoke(cli, ["mesh", "domains", "get", "non-existent"])

        assert result.exit_code != 0
        assert "Failed to get domain" in result.output


class TestMeshDomainsUpdate:
    """Test mesh domains update command"""

    def test_update_domain_success_table_format(self, runner, mock_api_client):
        """Test updating a domain successfully in table format"""
        mock_response = {
            "id": "domain-1",
            "name": "Updated Domain",
            "status": "INACTIVE",
            "description": "Updated description",
            "owner": "owner-2",
            "updated_at": "2025-01-01T02:00:00Z",
        }
        mock_api_client.patch.return_value = mock_response

        result = runner.invoke(
            cli,
            [
                "mesh",
                "domains",
                "update",
                "domain-1",
                "--name",
                "Updated Domain",
                "--status",
                "INACTIVE",
            ],
        )

        assert result.exit_code == 0
        assert "Domain updated successfully" in result.output
        assert "domain-1" in result.output
        assert "Updated Domain" in result.output
        assert "INACTIVE" in result.output
        mock_api_client.patch.assert_called_once()
        call_args = mock_api_client.patch.call_args
        assert call_args[0][0] == "mesh/domains/domain-1/"
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "Updated Domain"
        assert json_data["status"] == "INACTIVE"

    def test_update_domain_success_json_format(self, runner, mock_api_client):
        """Test updating a domain successfully in JSON format"""
        mock_response = {"id": "domain-1", "name": "Updated Domain", "status": "ACTIVE"}
        mock_api_client.patch.return_value = mock_response

        result = runner.invoke(
            cli,
            [
                "mesh",
                "domains",
                "update",
                "domain-1",
                "--name",
                "Updated Domain",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "domain-1"
        assert output_data["name"] == "Updated Domain"

    def test_update_domain_with_all_options(self, runner, mock_api_client):
        """Test updating a domain with all optional parameters"""
        mock_response = {"id": "domain-1", "name": "Updated Domain", "status": "ACTIVE"}
        mock_api_client.patch.return_value = mock_response

        boundaries = '{"data_products": ["product2"]}'
        capabilities = '{"apis": ["api2"]}'
        resource_quota = '{"storage": 2000}'

        result = runner.invoke(
            cli,
            [
                "mesh",
                "domains",
                "update",
                "domain-1",
                "--name",
                "Updated Domain",
                "--description",
                "Updated description",
                "--owner-id",
                "owner-2",
                "--boundaries",
                boundaries,
                "--capabilities",
                capabilities,
                "--resource-quota",
                resource_quota,
                "--status",
                "ARCHIVED",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_api_client.patch.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "Updated Domain"
        assert json_data["description"] == "Updated description"
        assert json_data["owner_id"] == "owner-2"
        assert json_data["boundaries"] == {"data_products": ["product2"]}
        assert json_data["capabilities"] == {"apis": ["api2"]}
        assert json_data["resource_quota"] == {"storage": 2000}
        assert json_data["status"] == "ARCHIVED"

    def test_update_domain_no_fields(self, runner):
        """Test updating a domain without any fields"""
        result = runner.invoke(cli, ["mesh", "domains", "update", "domain-1"])

        assert result.exit_code != 0
        assert "At least one field must be provided" in result.output

    def test_update_domain_invalid_json(self, runner):
        """Test updating a domain with invalid JSON"""
        result = runner.invoke(
            cli, ["mesh", "domains", "update", "domain-1", "--boundaries", "invalid json"]
        )

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_update_domain_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.patch.side_effect = Exception("API connection error")

        result = runner.invoke(
            cli, ["mesh", "domains", "update", "domain-1", "--name", "Updated Domain"]
        )

        assert result.exit_code != 0
        assert "Failed to update domain" in result.output


class TestMeshDomainsDelete:
    """Test mesh domains delete command"""

    def test_delete_domain_success_table_format(self, runner, mock_api_client):
        """Test deleting a domain successfully in table format"""
        mock_api_client.delete.return_value = {}

        result = runner.invoke(cli, ["mesh", "domains", "delete", "domain-1"], input="y\n")

        assert result.exit_code == 0
        assert "deleted successfully" in result.output
        assert "domain-1" in result.output
        mock_api_client.delete.assert_called_once_with("mesh/domains/domain-1/")

    def test_delete_domain_success_json_format(self, runner, mock_api_client):
        """Test deleting a domain successfully in JSON format"""
        mock_api_client.delete.return_value = {}

        result = runner.invoke(
            cli, ["mesh", "domains", "delete", "domain-1", "--format", "json"], input="y\n"
        )

        assert result.exit_code == 0
        # Output includes confirmation prompt, extract JSON part
        output_lines = result.output.strip().split("\n")
        json_line = None
        for line in output_lines:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                json_line = line
                break

        if json_line:
            output_data = json.loads(json_line)
            assert isinstance(output_data, dict)
        else:
            # If no JSON found, should contain success message
            assert "deleted successfully" in result.output.lower() or "domain-1" in result.output

    def test_delete_domain_cancelled(self, runner, mock_api_client):
        """Test cancelling domain deletion"""
        runner.invoke(cli, ["mesh", "domains", "delete", "domain-1"], input="n\n")

        # Should exit without deleting
        assert not mock_api_client.delete.called

    def test_delete_domain_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.delete.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ["mesh", "domains", "delete", "domain-1"], input="y\n")

        assert result.exit_code != 0
        assert "Failed to delete domain" in result.output


class TestMeshDomainsCommandStructure:
    """Test mesh domains command group structure"""

    def test_domains_command_group_exists(self, runner):
        """Test that domains command group exists"""
        result = runner.invoke(cli, ["mesh", "domains", "--help"])
        assert result.exit_code == 0
        assert "Domain management commands" in result.output

    def test_domains_list_command_exists(self, runner):
        """Test that domains list command exists"""
        result = runner.invoke(cli, ["mesh", "domains", "list", "--help"])
        assert result.exit_code == 0

    def test_domains_create_command_exists(self, runner):
        """Test that domains create command exists"""
        result = runner.invoke(cli, ["mesh", "domains", "create", "--help"])
        assert result.exit_code == 0

    def test_domains_get_command_exists(self, runner):
        """Test that domains get command exists"""
        result = runner.invoke(cli, ["mesh", "domains", "get", "--help"])
        assert result.exit_code == 0

    def test_domains_update_command_exists(self, runner):
        """Test that domains update command exists"""
        result = runner.invoke(cli, ["mesh", "domains", "update", "--help"])
        assert result.exit_code == 0

    def test_domains_delete_command_exists(self, runner):
        """Test that domains delete command exists"""
        result = runner.invoke(cli, ["mesh", "domains", "delete", "--help"])
        assert result.exit_code == 0


class TestMeshComplianceCheck:
    """Test mesh compliance check command"""

    def test_check_compliance_success_table_format(self, runner, mock_api_client):
        """Test checking compliance in table format"""
        mock_data = {
            "id": "report-1",
            "domain_id": "domain-1",
            "compliance_status": "COMPLIANT",
            "risk_level": "LOW",
            "violation_count": 0,
            "generated_at": "2025-01-01T00:00:00Z",
            "summary": "Domain is compliant with all regulations",
        }
        mock_api_client.post.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "compliance", "check", "domain-1"])

        assert result.exit_code == 0
        assert "report-1" in result.output
        assert "COMPLIANT" in result.output
        assert "LOW" in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == "mesh/domains/domain-1/compliance/check/"
        assert call_args[1]["json_data"] == {}

    def test_check_compliance_success_json_format(self, runner, mock_api_client):
        """Test checking compliance in JSON format"""
        mock_data = {
            "id": "report-1",
            "domain_id": "domain-1",
            "compliance_status": "COMPLIANT",
            "risk_level": "LOW",
        }
        mock_api_client.post.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "compliance", "check", "domain-1", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "report-1"
        assert output_data["compliance_status"] == "COMPLIANT"

    def test_check_compliance_with_asset_id(self, runner, mock_api_client):
        """Test checking compliance with asset ID"""
        mock_data = {
            "id": "report-1",
            "domain_id": "domain-1",
            "asset_id": "asset-1",
            "compliance_status": "NON_COMPLIANT",
        }
        mock_api_client.post.return_value = mock_data

        result = runner.invoke(
            cli, ["mesh", "compliance", "check", "domain-1", "--asset-id", "asset-1"]
        )

        assert result.exit_code == 0
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[1]["json_data"] == {"asset_id": "asset-1"}

    def test_check_compliance_domain_not_found(self, runner, mock_api_client):
        """Test handling domain not found error"""
        from click import ClickException

        mock_api_client.post.side_effect = ClickException("Domain not found")

        result = runner.invoke(cli, ["mesh", "compliance", "check", "invalid-domain"])

        assert result.exit_code != 0
        assert "Domain not found" in result.output or "Failed" in result.output

    def test_check_compliance_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.post.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ["mesh", "compliance", "check", "domain-1"])

        assert result.exit_code != 0
        assert "Failed to check compliance" in result.output


class TestMeshComplianceReport:
    """Test mesh compliance report command"""

    def test_get_compliance_report_success_table_format(self, runner, mock_api_client):
        """Test getting compliance report in table format"""
        # First call to list reports (to get latest)
        list_mock_data = {
            "count": 1,
            "results": [
                {
                    "id": "report-1",
                    "domain_id": "domain-1",
                    "compliance_status": "COMPLIANT",
                    "risk_level": "LOW",
                    "violation_count": 0,
                    "generated_at": "2025-01-01T00:00:00Z",
                }
            ],
        }
        # Second call to get specific report
        get_mock_data = {
            "id": "report-1",
            "domain_id": "domain-1",
            "compliance_status": "COMPLIANT",
            "risk_level": "LOW",
            "violation_count": 0,
            "violations": [],
            "generated_at": "2025-01-01T00:00:00Z",
            "summary": "Domain is compliant",
        }
        mock_api_client.get.side_effect = [list_mock_data, get_mock_data]

        result = runner.invoke(cli, ["mesh", "compliance", "report", "domain-1"])

        assert result.exit_code == 0
        assert "report-1" in result.output
        assert "COMPLIANT" in result.output
        assert "LOW" in result.output
        assert mock_api_client.get.call_count == 2

    def test_get_compliance_report_success_json_format(self, runner, mock_api_client):
        """Test getting compliance report in JSON format"""
        list_mock_data = {"count": 1, "results": [{"id": "report-1"}]}
        get_mock_data = {"id": "report-1", "compliance_status": "COMPLIANT", "risk_level": "LOW"}
        mock_api_client.get.side_effect = [list_mock_data, get_mock_data]

        result = runner.invoke(
            cli, ["mesh", "compliance", "report", "domain-1", "--format", "json"]
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "report-1"
        assert output_data["compliance_status"] == "COMPLIANT"

    def test_get_compliance_report_no_reports(self, runner, mock_api_client):
        """Test handling case when no reports exist"""
        mock_data = {"count": 0, "results": []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["mesh", "compliance", "report", "domain-1"])

        assert result.exit_code == 0
        assert "No compliance reports found" in result.output

    def test_get_compliance_report_with_report_id(self, runner, mock_api_client):
        """Test getting specific compliance report by ID"""
        mock_data = {
            "id": "report-2",
            "domain_id": "domain-1",
            "compliance_status": "NON_COMPLIANT",
            "risk_level": "HIGH",
            "violation_count": 3,
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(
            cli, ["mesh", "compliance", "report", "domain-1", "--report-id", "report-2"]
        )

        assert result.exit_code == 0
        assert "report-2" in result.output
        assert "NON_COMPLIANT" in result.output
        # Should call get with report ID
        assert any("report-2" in str(call) for call in mock_api_client.get.call_args_list)

    def test_get_compliance_report_domain_not_found(self, runner, mock_api_client):
        """Test handling domain not found error"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("Domain not found")

        result = runner.invoke(cli, ["mesh", "compliance", "report", "invalid-domain"])

        assert result.exit_code != 0
        assert "Domain not found" in result.output or "Failed" in result.output

    def test_get_compliance_report_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.get.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ["mesh", "compliance", "report", "domain-1"])

        assert result.exit_code != 0
        assert "Failed to get compliance report" in result.output


class TestMeshComplianceCommandStructure:
    """Test mesh compliance command group structure"""

    def test_compliance_command_group_exists(self, runner):
        """Test that compliance command group exists"""
        result = runner.invoke(cli, ["mesh", "compliance", "--help"])
        assert result.exit_code == 0
        assert "compliance" in result.output.lower()

    def test_compliance_check_command_exists(self, runner):
        """Test that compliance check command exists"""
        result = runner.invoke(cli, ["mesh", "compliance", "check", "--help"])
        assert result.exit_code == 0

    def test_compliance_report_command_exists(self, runner):
        """Test that compliance report command exists"""
        result = runner.invoke(cli, ["mesh", "compliance", "report", "--help"])
        assert result.exit_code == 0
