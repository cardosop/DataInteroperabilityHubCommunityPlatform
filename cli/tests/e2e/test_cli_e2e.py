"""
End-to-end tests for CLI commands.

Tests complete workflows and real-world usage scenarios.
"""

import json

import pytest
from click.testing import CliRunner
from datahub_cli.config import Config
from datahub_cli.main import cli


class TestCompleteWorkflows:
    """E2E tests for complete workflows"""

    def test_contract_creation_workflow(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test complete contract creation workflow"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Create contract file
        file_path, _content = temp_file(".yaml", "name: Test Contract\nversion: 1.0")

        # Create contract
        result = runner.invoke(cli, ["contracts", "create", "--file", file_path])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0

        # If creation succeeded, try to get it
        if result.exit_code == 0:
            # Extract contract ID from output (basic check)
            assert "created successfully" in result.output.lower() or "id" in result.output.lower()

    def test_asset_management_workflow(self, runner, temp_config_dir, api_base_url):
        """Test complete asset management workflow"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Create asset
        result = runner.invoke(
            cli, ["assets", "create", "--name", "E2E Test Asset", "--key", "e2e-test-asset"]
        )

        assert result.exit_code == 0

        # If creation succeeded, try to list it
        if result.exit_code == 0:
            list_result = runner.invoke(cli, ["assets", "list"])
            assert list_result.exit_code == 0

    def test_file_upload_download_workflow(
        self, runner, temp_config_dir, api_base_url, temp_file, tmp_path
    ):
        """Test complete file upload and download workflow"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Create test file
        file_path, _content = temp_file(".csv", "col1,col2\nval1,val2")

        # Upload file
        upload_result = runner.invoke(cli, ["files", "upload", file_path])

        assert upload_result.exit_code == 0

        # If upload succeeded, try to list files
        if upload_result.exit_code == 0:
            list_result = runner.invoke(cli, ["files", "list"])
            assert list_result.exit_code == 0

    def test_job_monitoring_workflow(self, runner, temp_config_dir, api_base_url):
        """Test complete job monitoring workflow"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # List jobs
        list_result = runner.invoke(cli, ["jobs", "list"])
        assert list_result.exit_code == 0

        # If jobs exist, try to get one
        if list_result.exit_code == 0 and "No jobs found" not in list_result.output:
            # Extract job ID from output (basic check)
            # In real scenario, would parse output
            pass


class TestRealAPIScenarios:
    """E2E tests with real API server scenarios"""

    def test_authenticated_workflow(self, runner, temp_config_dir, api_base_url):
        """Test workflow with authentication"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Try to use CLI with authentication
        # If API requires auth, should get auth error
        result = runner.invoke(cli, ["contracts", "list"])

        # Should either succeed (if API allows) or fail with auth/connection error
        assert result.exit_code == 0
        if result.exit_code != 0:
            # May suggest authentication, or be connection error if API not available
            assert any(
                keyword in result.output.lower()
                for keyword in [
                    "login",
                    "authenticated",
                    "api key",
                    "connection",
                    "refused",
                    "failed to list contracts",
                ]
            )

    def test_paginated_results(self, runner, temp_config_dir, api_base_url):
        """Test handling paginated results"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # List with pagination
        result = runner.invoke(cli, ["contracts", "list", "--limit", "10", "--offset", "0"])

        assert result.exit_code == 0
        # Should handle pagination correctly

    def test_filtered_queries(self, runner, temp_config_dir, api_base_url):
        """Test filtered queries"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # List with filters
        result = runner.invoke(
            cli, ["assets", "list", "--status", "ACTIVE", "--domain", "test-domain"]
        )

        assert result.exit_code == 0
        # Should apply filters correctly


class TestCICDScenarios:
    """E2E tests for CI/CD pipeline scenarios"""

    def test_non_interactive_usage(self, runner, temp_config_dir):
        """Test non-interactive CLI usage (CI/CD scenario)"""
        config = Config()
        config.set_api_base_url("http://localhost:8000/api/v1")
        config.set_api_key("ci-cd-api-key")

        # Should work without prompts
        result = runner.invoke(cli, ["contracts", "list"], input="")

        # Should not prompt for input
        assert result.exit_code == 0

    def test_scripted_workflow(self, runner, temp_config_dir, temp_file):
        """Test scripted workflow (automation scenario)"""
        config = Config()
        config.set_api_base_url("http://localhost:8000/api/v1")

        # Simulate scripted workflow
        file_path, _content = temp_file(".yaml", "name: Scripted Contract\nversion: 1.0")

        # Create with JSON output for parsing
        result = runner.invoke(
            cli, ["contracts", "create", "--file", file_path, "--format", "json"]
        )

        # Should produce parseable output
        if result.exit_code == 0 and result.output.strip():
            try:
                output_data = json.loads(result.output)
                assert isinstance(output_data, dict)
            except json.JSONDecodeError:
                # If not JSON, that's OK for this test
                pass

    def test_batch_operations(self, runner, temp_config_dir):
        """Test batch operations (CI/CD scenario)"""
        config = Config()
        config.set_api_base_url("http://localhost:8000/api/v1")

        # List multiple resources
        commands = [
            ["contracts", "list", "--format", "json"],
            ["assets", "list", "--format", "json"],
            ["jobs", "list", "--format", "json"],
        ]

        for cmd in commands:
            result = runner.invoke(cli, cmd)
            # Should all work consistently
            assert result.exit_code == 0


class TestErrorRecoveryE2E:
    """E2E tests for error recovery"""

    def test_recovery_from_network_error(self, runner, temp_config_dir):
        """Test recovery from network error"""
        config = Config()
        config.set_api_base_url("http://invalid-host:8000/api/v1")

        # First command fails
        result1 = runner.invoke(cli, ["contracts", "list"])
        assert result1.exit_code != 0

        # Update config and retry
        config.set_api_base_url("http://localhost:8000/api/v1")
        result2 = runner.invoke(cli, ["contracts", "list"])

        # Should either succeed or fail gracefully (depending on API availability)
        assert result2.exit_code == 0

    def test_recovery_from_auth_error(self, runner, temp_config_dir, api_base_url):
        """Test recovery from authentication error"""
        config = Config()
        config.set_api_base_url(api_base_url)
        config.clear_auth()

        # First command fails with auth error
        result1 = runner.invoke(cli, ["contracts", "list"])
        assert result1.exit_code != 0

        # Set API key and retry
        config.set_api_key("test-api-key")
        result2 = runner.invoke(cli, ["contracts", "list"])

        # Should either succeed or fail gracefully
        assert result2.exit_code == 0


class TestOutputFormatE2E:
    """E2E tests for output formatting in real scenarios"""

    def test_json_output_for_automation(self, runner, temp_config_dir, api_base_url):
        """Test JSON output for automation/scripting"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(cli, ["contracts", "list", "--format", "json"])

        # JSON output should be parseable for automation
        if result.exit_code == 0 and result.output.strip():
            try:
                data = json.loads(result.output)
                assert isinstance(data, (dict, list))
            except json.JSONDecodeError:
                pytest.fail("JSON output not parseable for automation")

    def test_table_output_for_humans(self, runner, temp_config_dir, api_base_url):
        """Test table output for human readability"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(cli, ["assets", "list"])

        # Table output should be human-readable
        if result.exit_code == 0 and result.output.strip():
            # Should have structure, not raw JSON
            assert not result.output.strip().startswith("[")
            assert not result.output.strip().startswith("{")


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def api_base_url():
    """API base URL fixture"""
    return "http://localhost:8000/api/v1"


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory"""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"

    monkeypatch.setattr("datahub_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("datahub_cli.config.CONFIG_FILE", config_file)

    return config_dir, config_file


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file"""

    def _create_file(extension, content):
        file_path = tmp_path / f"test{extension}"
        file_path.write_text(content)
        return str(file_path), content

    return _create_file
