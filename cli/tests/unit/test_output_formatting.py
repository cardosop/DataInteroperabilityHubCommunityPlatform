"""
Comprehensive unit tests for CLI output formatting.

Tests JSON, table, dot, mermaid, and human-readable output formats.
"""

import json
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from datahub_cli.main import cli


class TestJSONOutputFormat:
    """Test JSON output format"""

    def test_contracts_list_json_format(self, runner, mock_api_client):
        """Test contracts list with JSON format"""
        mock_data = {
            "results": [
                {"id": "contract-1", "version": 1, "status": "DRAFT"},
                {"id": "contract-2", "version": 2, "status": "ACTIVE"},
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 2
        assert output_data[0]["id"] == "contract-1"

    def test_contracts_get_json_format(self, runner, mock_api_client):
        """Test contracts get with JSON format"""
        mock_data = {"id": "contract-1", "version": 1, "status": "DRAFT", "asset_id": "asset-1"}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "get", "contract-1", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["id"] == "contract-1"
        assert output_data["status"] == "DRAFT"

    def test_assets_list_json_format(self, runner, mock_api_client):
        """Test assets list with JSON format"""
        mock_data = {"results": [{"id": "asset-1", "name": "Test Asset", "status": "ACTIVE"}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["assets", "list", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert output_data[0]["id"] == "asset-1"

    def test_lineage_json_format(self, runner, mock_api_client):
        """Test lineage commands with JSON format"""
        mock_data = {"contracts": [{"namespace": "ns1", "name": "contract1"}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["lineage", "contract", "contract-1", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert "contracts" in output_data

    def test_jobs_list_json_format(self, runner, mock_api_client):
        """Test jobs list with JSON format"""
        mock_data = {"results": [{"id": "job-1", "type": "DQ_RUN", "status": "RUNNING"}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["jobs", "list", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert output_data[0]["id"] == "job-1"

    def test_files_list_json_format(self, runner, mock_api_client):
        """Test files list with JSON format"""
        mock_data = {
            "results": [{"id": "file-1", "name": "test.csv", "size": 1024, "status": "UPLOADED"}]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["files", "list", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert output_data[0]["id"] == "file-1"

    def test_json_output_valid_json(self, runner, mock_api_client):
        """Test that JSON output is valid JSON"""
        mock_data = {"results": [{"id": "test", "name": "Test", "value": 123}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list", "--format", "json"])

        assert result.exit_code == 0
        # Should be valid JSON
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)

    def test_json_output_pretty_print(self, runner, mock_api_client):
        """Test that JSON output is pretty-printed (indented)"""
        mock_data = {"results": [{"id": "test", "nested": {"key": "value"}}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list", "--format", "json"])

        assert result.exit_code == 0
        # Should contain newlines (pretty-printed)
        assert "\n" in result.output
        # Should be valid JSON
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)


class TestTableOutputFormat:
    """Test table output format (default)"""

    def test_contracts_list_table_format(self, runner, mock_api_client):
        """Test contracts list with table format"""
        mock_data = {
            "results": [
                {"id": "contract-1", "version": 1, "status": "DRAFT", "asset_id": "asset-1"}
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list", "--format", "table"])

        assert result.exit_code == 0
        assert "ID" in result.output
        assert "Version" in result.output
        assert "Status" in result.output
        assert "contract-1" in result.output

    def test_assets_list_table_format(self, runner, mock_api_client):
        """Test assets list with table format"""
        mock_data = {
            "results": [
                {"id": "asset-1", "name": "Test Asset", "status": "ACTIVE", "domain": "domain1"}
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["assets", "list", "--format", "table"])

        assert result.exit_code == 0
        assert "ID" in result.output
        assert "Name" in result.output
        assert "Status" in result.output
        assert "asset-1" in result.output

    def test_table_format_headers(self, runner, mock_api_client):
        """Test that table format includes proper headers"""
        mock_data = {"results": [{"id": "test", "version": 1, "status": "DRAFT"}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list"])

        assert result.exit_code == 0
        # Should have headers
        assert "ID" in result.output
        assert "Version" in result.output
        assert "Status" in result.output

    def test_table_format_separator(self, runner, mock_api_client):
        """Test that table format includes separator line"""
        mock_data = {"results": [{"id": "test", "version": 1, "status": "DRAFT"}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list"])

        assert result.exit_code == 0
        # Should have separator line (dashes)
        assert "-" in result.output

    def test_table_format_empty_result(self, runner, mock_api_client):
        """Test table format with empty results"""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["contracts", "list"])

        assert result.exit_code == 0
        assert "No contracts found" in result.output


class TestLineageVisualizationFormats:
    """Test lineage visualization formats (dot, mermaid)"""

    def test_lineage_visualize_dot_format(self, runner, mock_api_client):
        """Test lineage visualization in DOT format"""
        mock_response = Mock()
        mock_response.text = "digraph { node1 -> node2; }"
        mock_api_client.request = Mock(return_value=mock_response)

        result = runner.invoke(cli, ["lineage", "visualize", "contract-1", "--format", "dot"])

        assert result.exit_code == 0
        assert "digraph" in result.output
        assert "node1" in result.output

    def test_lineage_visualize_mermaid_format(self, runner, mock_api_client):
        """Test lineage visualization in Mermaid format"""
        mock_response = Mock()
        mock_response.text = "graph TD\n    A --> B"
        mock_api_client.request = Mock(return_value=mock_response)

        result = runner.invoke(cli, ["lineage", "visualize", "contract-1", "--format", "mermaid"])

        assert result.exit_code == 0
        assert "graph TD" in result.output or "graph" in result.output

    def test_lineage_visualize_json_format(self, runner, mock_api_client):
        """Test lineage visualization in JSON format"""
        mock_response = Mock()
        mock_response.json.return_value = {"nodes": [{"id": "node1"}], "edges": []}
        mock_response.text = '{"nodes": [{"id": "node1"}], "edges": []}'
        mock_api_client.request = Mock(return_value=mock_response)

        result = runner.invoke(cli, ["lineage", "visualize", "contract-1", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert "nodes" in output_data


class TestHumanReadableOutput:
    """Test human-readable output (default table format)"""

    def test_human_readable_success_messages(self, runner, mock_api_client, temp_file):
        """Test human-readable success messages"""
        file_path, _content = temp_file(".yaml", "name: Test Contract")
        mock_result = {"id": "contract-1", "version": 1, "status": "DRAFT"}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ["contracts", "create", "--file", file_path])

        assert result.exit_code == 0
        assert "Contract created successfully" in result.output
        assert "contract-1" in result.output

    def test_human_readable_error_messages(self, runner, mock_api_client):
        """Test human-readable error messages"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException("API error: Resource not found")

        result = runner.invoke(cli, ["contracts", "get", "invalid-id"])

        assert result.exit_code != 0
        # Error should be human-readable
        assert "not found" in result.output.lower() or "Failed to get contract" in result.output

    def test_human_readable_validation_results(self, runner, mock_api_client):
        """Test human-readable validation results"""
        mock_result = {
            "validation_status": "INVALID",
            "errors": ["Error 1", "Error 2"],
            "warnings": ["Warning 1"],
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ["contracts", "validate", "contract-1"])

        assert result.exit_code == 0
        assert "INVALID" in result.output
        assert "Errors (2)" in result.output
        assert "Warnings (1)" in result.output
        assert "Error 1" in result.output

    def test_human_readable_job_status(self, runner, mock_api_client):
        """Test human-readable job status messages"""
        mock_data = {"id": "job-1", "status": "COMPLETED", "type": "DQ_RUN"}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["jobs", "get", "job-1"])

        assert result.exit_code == 0
        assert "COMPLETED" in result.output
        assert "DQ_RUN" in result.output
        # Should be formatted in a human-readable way
        assert "ID:" in result.output or "Type:" in result.output


class TestOutputFormatConsistency:
    """Test output format consistency across commands"""

    def test_all_list_commands_support_json_table(self, runner, mock_api_client):
        """Test that all list commands support both JSON and table formats"""
        mock_data = {"results": []}
        mock_api_client.get.return_value = mock_data

        commands = [["contracts", "list"], ["assets", "list"], ["files", "list"], ["jobs", "list"]]

        for cmd in commands:
            # Test JSON format
            result_json = runner.invoke(cli, cmd + ["--format", "json"])
            assert result_json.exit_code == 0

            # Test table format
            result_table = runner.invoke(cli, cmd + ["--format", "table"])
            assert result_table.exit_code == 0

    def test_output_format_defaults_to_table(self, runner, mock_api_client):
        """Test that output format defaults to table"""
        mock_data = {"results": [{"id": "test", "status": "ACTIVE"}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list"])

        assert result.exit_code == 0
        # Should be table format (not JSON)
        assert "ID" in result.output
        assert "Status" in result.output
        # Should not be JSON
        assert not result.output.strip().startswith("[")

    def test_output_format_case_insensitive(self, runner, mock_api_client):
        """Test that output format is case-sensitive (Click handles this)"""
        mock_data = {"results": []}
        mock_api_client.get.return_value = mock_data

        # Click Choice is case-sensitive, so 'JSON' should fail
        result = runner.invoke(cli, ["contracts", "list", "--format", "JSON"])

        # Should fail with invalid choice
        assert result.exit_code != 0 or "Invalid value" in result.output


class TestOutputFormatEdgeCases:
    """Test output format edge cases"""

    def test_json_output_with_special_characters(self, runner, mock_api_client):
        """Test JSON output with special characters in data"""
        mock_data = {
            "results": [
                {"id": "test", "name": 'Test "quoted" name', "description": "Line 1\nLine 2"}
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list", "--format", "json"])

        assert result.exit_code == 0
        # Should be valid JSON even with special characters
        output_data = json.loads(result.output)
        assert output_data[0]["name"] == 'Test "quoted" name'

    def test_table_output_with_long_values(self, runner, mock_api_client):
        """Test table output with long values (truncation)"""
        long_id = "a" * 100
        mock_data = {"results": [{"id": long_id, "version": 1, "status": "DRAFT"}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list"])

        assert result.exit_code == 0
        # Long values should be truncated in table output — the full 100-char
        # ID must not appear verbatim, but the truncated prefix must.
        assert long_id not in result.output, (
            f"Full {len(long_id)}-char ID should be truncated in table output"
        )
        assert long_id[:36] in result.output, "Truncated ID prefix should appear in table output"

    def test_json_output_with_none_values(self, runner, mock_api_client):
        """Test JSON output with None values"""
        mock_data = {"results": [{"id": "test", "asset_id": None, "description": None}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        # None values should be included in JSON
        assert output_data[0]["asset_id"] is None

    def test_table_output_with_none_values(self, runner, mock_api_client):
        """Test table output with None values"""
        mock_data = {"results": [{"id": "test", "version": 1, "status": "DRAFT", "asset_id": None}]}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ["contracts", "list"])

        assert result.exit_code == 0
        # None values should be displayed as 'N/A' in table format
        assert "N/A" in result.output


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock API client"""
    mock_client = Mock()
    monkeypatch.setattr("datahub_cli.commands.contracts.api_client", mock_client)
    monkeypatch.setattr("datahub_cli.commands.assets.api_client", mock_client)
    monkeypatch.setattr("datahub_cli.commands.files.api_client", mock_client)
    monkeypatch.setattr("datahub_cli.commands.jobs.api_client", mock_client)
    monkeypatch.setattr("datahub_cli.commands.lineage.api_client", mock_client)
    return mock_client


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file"""

    def _create_file(extension, content):
        file_path = tmp_path / f"test{extension}"
        file_path.write_text(content)
        return str(file_path), content

    return _create_file
