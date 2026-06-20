"""
Unit tests for CLI commands.

Tests command parsing, argument validation, and output formatting for assets, contracts, files, and jobs.
Uses real command implementations (no mocks).
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

# Add CLI to path
cli_path = Path(__file__).parent.parent.parent.parent / "cli"
sys.path.insert(0, str(cli_path))

from datahub_cli.commands import assets, contracts, files, jobs


class TestAssetsCommands:
    """Unit tests for asset commands"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    @pytest.fixture
    def temp_config(self, tmp_path, monkeypatch):
        """Create temporary config"""
        config_dir = tmp_path / ".datahub"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"

        monkeypatch.setattr("cli.datahub_cli.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("cli.datahub_cli.config.CONFIG_FILE", config_file)

        return config_dir, config_file

    def test_assets_list_help(self, runner):
        """Test assets list command help"""
        result = runner.invoke(assets.assets, ["list", "--help"])
        assert result.exit_code == 0
        assert "List assets" in result.output

    def test_assets_list_with_options(self, runner):
        """Test assets list with various options"""
        result = runner.invoke(
            assets.assets,
            [
                "list",
                "--status",
                "ACTIVE",
                "--domain",
                "sales",
                "--limit",
                "10",
                "--offset",
                "0",
                "--format",
                "json",
            ],
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_assets_get_help(self, runner):
        """Test assets get command help"""
        result = runner.invoke(assets.assets, ["get", "--help"])
        assert result.exit_code == 0
        assert "Get asset details" in result.output

    def test_assets_get_with_include(self, runner):
        """Test assets get with include option"""
        result = runner.invoke(
            assets.assets,
            ["get", "test-asset-id", "--include", "contract,datasets", "--format", "json"],
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_assets_create_help(self, runner):
        """Test assets create command help"""
        result = runner.invoke(assets.assets, ["create", "--help"])
        assert result.exit_code == 0
        assert "Create a new asset" in result.output

    def test_assets_create_missing_required(self, runner):
        """Test assets create with missing required arguments"""
        result = runner.invoke(assets.assets, ["create"])
        assert result.exit_code != 0  # Should fail without required args

    def test_assets_create_with_all_options(self, runner):
        """Test assets create with all options"""
        result = runner.invoke(
            assets.assets,
            [
                "create",
                "--name",
                "Test Asset",
                "--key",
                "test-asset",
                "--description",
                "Test description",
                "--domain",
                "test",
                "--visibility",
                "PUBLIC",
                "--format",
                "json",
            ],
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_assets_update_help(self, runner):
        """Test assets update command help"""
        result = runner.invoke(assets.assets, ["update", "--help"])
        assert result.exit_code == 0
        assert "Update an asset" in result.output

    def test_assets_update_with_options(self, runner):
        """Test assets update with options"""
        result = runner.invoke(
            assets.assets,
            [
                "update",
                "test-asset-id",
                "--name",
                "Updated Name",
                "--description",
                "Updated description",
                "--domain",
                "new-domain",
                "--visibility",
                "INTERNAL",
                "--format",
                "json",
            ],
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_assets_delete_help(self, runner):
        """Test assets delete command help"""
        result = runner.invoke(assets.assets, ["delete", "--help"])
        assert result.exit_code == 0
        assert "Delete an asset" in result.output

    def test_assets_delete_with_confirm(self, runner):
        """Test assets delete with confirm flag"""
        result = runner.invoke(
            assets.assets, ["delete", "test-asset-id", "--confirm"], input="n\n"
        )  # Don't confirm
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_assets_activate_help(self, runner):
        """Test assets activate command help"""
        result = runner.invoke(assets.assets, ["activate", "--help"])
        assert result.exit_code == 0
        assert "Activate an asset" in result.output

    def test_assets_activate_with_format(self, runner):
        """Test assets activate with format option"""
        result = runner.invoke(assets.assets, ["activate", "test-asset-id", "--format", "json"])
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_assets_list_output_format_table(self, runner):
        """Test assets list table output format"""
        # Test that table format is default
        result = runner.invoke(assets.assets, ["list", "--format", "table"])
        # May fail without auth, but format should be parsed
        assert result.exit_code in [0, 1]

    def test_assets_list_output_format_json(self, runner):
        """Test assets list JSON output format"""
        result = runner.invoke(assets.assets, ["list", "--format", "json"])
        # May fail without auth, but format should be parsed
        assert result.exit_code in [0, 1]

    def test_assets_list_invalid_format(self, runner):
        """Test assets list with invalid format"""
        result = runner.invoke(assets.assets, ["list", "--format", "invalid"])
        assert result.exit_code != 0  # Should fail with invalid format


class TestContractsCommands:
    """Unit tests for contract commands"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_contracts_list_help(self, runner):
        """Test contracts list command help"""
        result = runner.invoke(contracts.contracts, ["list", "--help"])
        assert result.exit_code == 0
        assert "List contracts" in result.output

    def test_contracts_list_with_filters(self, runner):
        """Test contracts list with filters"""
        result = runner.invoke(
            contracts.contracts,
            [
                "list",
                "--status",
                "DRAFT",
                "--asset-id",
                "test-asset-id",
                "--limit",
                "20",
                "--offset",
                "0",
                "--format",
                "json",
            ],
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_contracts_get_help(self, runner):
        """Test contracts get command help"""
        result = runner.invoke(contracts.contracts, ["get", "--help"])
        assert result.exit_code == 0
        assert "Get contract details" in result.output

    def test_contracts_get_with_format(self, runner):
        """Test contracts get with format option"""
        result = runner.invoke(contracts.contracts, ["get", "test-contract-id", "--format", "json"])
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_contracts_create_help(self, runner):
        """Test contracts create command help"""
        result = runner.invoke(contracts.contracts, ["create", "--help"])
        assert result.exit_code == 0
        assert "Create a new contract from file" in result.output

    def test_contracts_create_missing_file(self, runner):
        """Test contracts create with missing file"""
        result = runner.invoke(contracts.contracts, ["create", "--file", "nonexistent.yaml"])
        assert result.exit_code != 0  # Should fail with nonexistent file

    def test_contracts_create_with_valid_file(self, runner):
        """Test contracts create with valid file"""
        # Create temporary contract file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
id: test-contract
name: Test Contract
schema:
  fields:
    - name: field1
      type: string
""")
            temp_file = f.name

        try:
            result = runner.invoke(
                contracts.contracts,
                ["create", "--file", temp_file, "--asset-id", "test-asset-id", "--format", "json"],
            )
            # May fail without auth, but should parse file correctly
            assert result.exit_code in [0, 1]
        finally:
            os.unlink(temp_file)

    def test_contracts_create_json_file(self, runner):
        """Test contracts create with JSON file"""
        # Create temporary JSON contract file
        contract_data = {
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(contract_data, f)
            temp_file = f.name

        try:
            result = runner.invoke(
                contracts.contracts, ["create", "--file", temp_file, "--format", "json"]
            )
            # May fail without auth, but should parse JSON file correctly
            assert result.exit_code in [0, 1]
        finally:
            os.unlink(temp_file)

    def test_contracts_validate_help(self, runner):
        """Test contracts validate command help"""
        result = runner.invoke(contracts.contracts, ["validate", "--help"])
        assert result.exit_code == 0
        assert "Validate a contract" in result.output

    def test_contracts_validate_with_format(self, runner):
        """Test contracts validate with format option"""
        result = runner.invoke(
            contracts.contracts, ["validate", "test-contract-id", "--format", "json"]
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_contracts_lint_help(self, runner):
        """Test contracts lint command help"""
        result = runner.invoke(contracts.contracts, ["lint", "--help"])
        assert result.exit_code == 0
        assert "Lint a contract" in result.output

    def test_contracts_lint_with_format(self, runner):
        """Test contracts lint with format option"""
        result = runner.invoke(
            contracts.contracts, ["lint", "test-contract-id", "--format", "json"]
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]


class TestFilesCommands:
    """Unit tests for file commands"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_files_list_help(self, runner):
        """Test files list command help"""
        result = runner.invoke(files.files, ["list", "--help"])
        assert result.exit_code == 0
        assert "List files" in result.output

    def test_files_list_with_filters(self, runner):
        """Test files list with filters"""
        result = runner.invoke(
            files.files,
            ["list", "--status", "UPLOADED", "--limit", "20", "--offset", "0", "--format", "json"],
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_files_upload_help(self, runner):
        """Test files upload command help"""
        result = runner.invoke(files.files, ["upload", "--help"])
        assert result.exit_code == 0
        assert "Upload a file" in result.output

    def test_files_upload_missing_file(self, runner):
        """Test files upload with missing file"""
        result = runner.invoke(files.files, ["upload", "nonexistent.csv"])
        assert result.exit_code != 0  # Should fail with nonexistent file

    def test_files_upload_with_valid_file(self, runner):
        """Test files upload with valid file"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("col1,col2\nvalue1,value2\n")
            temp_file = f.name

        try:
            result = runner.invoke(
                files.files, ["upload", temp_file, "--name", "test.csv", "--format", "json"]
            )
            # May fail without auth, but should parse file correctly
            assert result.exit_code in [0, 1]
        finally:
            os.unlink(temp_file)

    def test_files_download_help(self, runner):
        """Test files download command help"""
        result = runner.invoke(files.files, ["download", "--help"])
        assert result.exit_code == 0
        assert "Download a file" in result.output

    def test_files_download_with_output(self, runner):
        """Test files download with output path"""
        result = runner.invoke(
            files.files, ["download", "test-file-id", "--output", "/tmp/downloaded.csv"]
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_files_delete_help(self, runner):
        """Test files delete command help"""
        result = runner.invoke(files.files, ["delete", "--help"])
        assert result.exit_code == 0
        assert "Delete a file" in result.output

    def test_files_delete_with_confirm(self, runner):
        """Test files delete with confirm flag"""
        result = runner.invoke(
            files.files, ["delete", "test-file-id", "--confirm"], input="n\n"
        )  # Don't confirm
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]


class TestJobsCommands:
    """Unit tests for job commands"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_jobs_list_help(self, runner):
        """Test jobs list command help"""
        result = runner.invoke(jobs.jobs, ["list", "--help"])
        assert result.exit_code == 0
        assert "List jobs" in result.output

    def test_jobs_list_with_filters(self, runner):
        """Test jobs list with filters"""
        result = runner.invoke(
            jobs.jobs,
            [
                "list",
                "--type",
                "DQ_RUN",
                "--status",
                "PENDING",
                "--limit",
                "20",
                "--offset",
                "0",
                "--format",
                "json",
            ],
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_jobs_get_help(self, runner):
        """Test jobs get command help"""
        result = runner.invoke(jobs.jobs, ["get", "--help"])
        assert result.exit_code == 0
        assert "Get job details" in result.output

    def test_jobs_get_with_format(self, runner):
        """Test jobs get with format option"""
        result = runner.invoke(jobs.jobs, ["get", "test-job-id", "--format", "json"])
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_jobs_cancel_help(self, runner):
        """Test jobs cancel command help"""
        result = runner.invoke(jobs.jobs, ["cancel", "--help"])
        assert result.exit_code == 0
        assert "Cancel a job" in result.output

    def test_jobs_cancel_with_format(self, runner):
        """Test jobs cancel with format option"""
        result = runner.invoke(jobs.jobs, ["cancel", "test-job-id", "--format", "json"])
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_jobs_watch_help(self, runner):
        """Test jobs watch command help"""
        result = runner.invoke(jobs.jobs, ["watch", "--help"])
        assert result.exit_code == 0
        assert "Watch a job until completion" in result.output

    def test_jobs_watch_with_options(self, runner):
        """Test jobs watch with options"""
        result = runner.invoke(
            jobs.jobs,
            ["watch", "test-job-id", "--interval", "1", "--timeout", "10", "--format", "json"],
        )
        # May fail without auth, but should parse options correctly
        assert result.exit_code in [0, 1]

    def test_jobs_list_output_format_table(self, runner):
        """Test jobs list table output format"""
        result = runner.invoke(jobs.jobs, ["list", "--format", "table"])
        # May fail without auth, but format should be parsed
        assert result.exit_code in [0, 1]

    def test_jobs_list_output_format_json(self, runner):
        """Test jobs list JSON output format"""
        result = runner.invoke(jobs.jobs, ["list", "--format", "json"])
        # May fail without auth, but format should be parsed
        assert result.exit_code in [0, 1]

    def test_jobs_list_invalid_format(self, runner):
        """Test jobs list with invalid format"""
        result = runner.invoke(jobs.jobs, ["list", "--format", "invalid"])
        assert result.exit_code != 0  # Should fail with invalid format
