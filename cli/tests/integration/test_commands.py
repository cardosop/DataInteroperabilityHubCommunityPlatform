"""
Unit tests for CLI command parsing and output formatting.

These tests verify CLI command parsing, argument handling, and output formatting.
For integration tests with real API services, see test_commands_real_api.py
"""

import pytest
from click.testing import CliRunner
from datahub_cli.commands import assets, contracts, files, jobs
from datahub_cli.commands import config as config_cmd


class TestAssetsCommands:
    """Unit tests for asset command parsing and formatting"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_assets_list_help(self, runner):
        """Test assets list command help"""
        result = runner.invoke(assets.assets, ["list", "--help"])
        assert result.exit_code == 0

    def test_assets_get_help(self, runner):
        """Test assets get command help"""
        result = runner.invoke(assets.assets, ["get", "--help"])
        assert result.exit_code == 0

    def test_assets_create_help(self, runner):
        """Test assets create command help"""
        result = runner.invoke(assets.assets, ["create", "--help"])
        assert result.exit_code == 0

    def test_assets_create_missing_required(self, runner):
        """Test assets create with missing required arguments"""
        result = runner.invoke(assets.assets, ["create"])
        assert result.exit_code != 0  # Should fail without required args


class TestContractsCommands:
    """Unit tests for contract command parsing and formatting"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_contracts_list_help(self, runner):
        """Test contracts list command help"""
        result = runner.invoke(contracts.contracts, ["list", "--help"])
        assert result.exit_code == 0

    def test_contracts_get_help(self, runner):
        """Test contracts get command help"""
        result = runner.invoke(contracts.contracts, ["get", "--help"])
        assert result.exit_code == 0

    def test_contracts_create_help(self, runner):
        """Test contracts create command help"""
        result = runner.invoke(contracts.contracts, ["create", "--help"])
        assert result.exit_code == 0


class TestFilesCommands:
    """Unit tests for file command parsing and formatting"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_files_list_help(self, runner):
        """Test files list command help"""
        result = runner.invoke(files.files, ["list", "--help"])
        assert result.exit_code == 0

    def test_files_upload_help(self, runner):
        """Test files upload command help"""
        result = runner.invoke(files.files, ["upload", "--help"])
        assert result.exit_code == 0


class TestJobsCommands:
    """Unit tests for job command parsing and formatting"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_jobs_list_help(self, runner):
        """Test jobs list command help"""
        result = runner.invoke(jobs.jobs, ["list", "--help"])
        assert result.exit_code == 0

    def test_jobs_get_help(self, runner):
        """Test jobs get command help"""
        result = runner.invoke(jobs.jobs, ["get", "--help"])
        assert result.exit_code == 0


class TestConfigCommands:
    """Integration tests for config commands"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_config_get(self, runner, temp_config_dir):
        """Test config get command"""
        from datahub_cli.config import config

        config.set("test_key", "test_value")

        result = runner.invoke(config_cmd.config_cmd, ["get", "test_key"])
        assert result.exit_code == 0
        assert "test_value" in result.output

    def test_config_set(self, runner, temp_config_dir):
        """Test config set command"""
        from datahub_cli.config import config

        result = runner.invoke(config_cmd.config_cmd, ["set", "test_key", "test_value"])
        assert result.exit_code == 0
        assert config.get("test_key") == "test_value"
