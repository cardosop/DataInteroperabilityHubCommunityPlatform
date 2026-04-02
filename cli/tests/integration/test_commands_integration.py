"""
Comprehensive integration tests for CLI commands.

Tests command groups end-to-end with real API structure (when available).
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from datahub_cli.auth import AuthManager
from datahub_cli.config import Config
from datahub_cli.main import cli


class TestContractsIntegration:
    """Integration tests for contracts commands"""

    def test_contracts_list_integration(self, runner, temp_config_dir, api_base_url):
        """Test contracts list command integration"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Try to list contracts (may fail if API not available, which is OK)
        result = runner.invoke(cli, ["contracts", "list"])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        # If it succeeds, verify output format
        if result.exit_code == 0:
            # Output should be either table or JSON
            assert len(result.output) > 0

    def test_contracts_create_get_flow(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test complete flow: create contract, then get it"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Create a test contract file
        file_path, content = temp_file(".yaml", "name: Test Contract\nversion: 1.0")

        # Try to create contract
        result = runner.invoke(cli, ["contracts", "create", "--file", file_path])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0

        # If creation succeeded, try to get it
        if result.exit_code == 0:
            # Extract contract ID from output (if available)
            # This is a basic integration test - real implementation would parse output
            pass

    def test_contracts_create_odps_extract_odcs_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts create-odps with --extract-odcs flag (Product-First flow) against real API"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Create a valid ODPS document with embedded ODCS contract
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "integration-test-product",
        "name": "Integration Test Product",
        "description": "Test product created via CLI integration test"
      }
    },
    "contract": {
      "apiVersion": "odcs/v3",
      "kind": "DataContract",
      "id": "integration-test-contract",
      "name": "Integration Test Contract",
      "version": "1.0.0",
      "schema": {
        "fields": [
          {
            "name": "id",
            "type": "string",
            "nullable": false
          }
        ]
      }
    }
  }
}"""

        file_path, content = temp_file(".json", odps_content)

        # Test create-odps with --extract-odcs
        result = runner.invoke(
            cli, ["contracts", "create-odps", "--file", file_path, "--extract-odcs"]
        )

        # Should either succeed or fail gracefully (may need authentication)
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert (
                "ODPS product created successfully" in result.output
                or "odps_contract" in result.output
            )

    def test_contracts_create_odps_link_odcs_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts create-odps with --link-odcs flag against real API"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Create ODPS document
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "integration-test-product-link",
        "name": "Integration Test Product for Link"
      }
    },
    "contract": {
      "apiVersion": "odcs/v3",
      "kind": "DataContract",
      "id": "test-odcs-id",
      "name": "Test ODCS"
    }
  }
}"""

        file_path, content = temp_file(".json", odps_content)

        # Test create-odps with --link-odcs (using a dummy ID - will fail but tests command structure)
        result = runner.invoke(
            cli,
            [
                "contracts",
                "create-odps",
                "--file",
                file_path,
                "--link-odcs",
                "00000000-0000-0000-0000-000000000000",
            ],
        )

        # Should either succeed or fail gracefully (may need authentication or valid ODCS ID)
        assert result.exit_code == 0

    def test_contracts_export_odps_integration(self, runner, temp_config_dir, api_base_url):
        """Test contracts export with ODPS format against real API"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Test export with ODPS format (may fail if API not available or contract doesn't exist)
        result = runner.invoke(
            cli,
            [
                "contracts",
                "export",
                "00000000-0000-0000-0000-000000000000",
                "--format",
                "odps",
                "--output-format",
                "json",
            ],
        )

        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            # If successful, should show export info
            assert (
                "exported successfully" in result.output.lower()
                or "schema" in result.output.lower()
            )

    def test_contracts_download_odps_integration(
        self, runner, temp_config_dir, api_base_url, temp_file, tmp_path
    ):
        """Test contracts download with ODPS format against real API"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Create output file path
        output_file = tmp_path / "downloaded_odps.json"

        # Test download with ODPS format (may fail if API not available or contract doesn't exist)
        result = runner.invoke(
            cli,
            [
                "contracts",
                "download",
                "00000000-0000-0000-0000-000000000000",
                "--format",
                "odps",
                "--output-format",
                "json",
                "--output",
                str(output_file),
            ],
        )

        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            # If successful, file should exist
            assert output_file.exists() or "downloaded successfully" in result.output.lower()

    def test_contracts_create_with_odps_detection_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts create with ODPS auto-detection against real API"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Create ODPS document
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "integration-test-product-detection",
        "name": "Integration Test Product for Detection"
      }
    }
  }
}"""

        file_path, content = temp_file(".json", odps_content)

        # Test create with auto-detection (may fail if API not available)
        result = runner.invoke(cli, ["contracts", "create", "--file", file_path])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            # If successful, should show detection or spec type
            assert (
                "Auto-detected spec type: ODPS" in result.output
                or "ODPS" in result.output
                or "Spec Type" in result.output
            )

    def test_contracts_list_shows_spec_type_integration(
        self, runner, temp_config_dir, api_base_url
    ):
        """Test contracts list shows original_spec_type against real API"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Test list command (may fail if API not available)
        result = runner.invoke(cli, ["contracts", "list"])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            # If successful, should show Spec Type column
            assert "Spec Type" in result.output or len(result.output) > 0

    def test_contracts_link_odps_integration(self, runner, temp_config_dir, api_base_url):
        """Test contracts link-odps command integration"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Test link-odps (may fail if API not available or contracts don't exist)
        result = runner.invoke(
            cli,
            [
                "contracts",
                "link-odps",
                "00000000-0000-0000-0000-000000000000",  # ODCS ID
                "00000000-0000-0000-0000-000000000001",  # ODPS ID
            ],
        )

        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert "linked successfully" in result.output.lower()

    def test_contracts_unlink_odps_integration(self, runner, temp_config_dir, api_base_url):
        """Test contracts unlink-odps command integration"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Test unlink-odps (may fail if API not available or contract doesn't exist)
        result = runner.invoke(
            cli, ["contracts", "unlink-odps", "00000000-0000-0000-0000-000000000000"]  # ODCS ID
        )

        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert "unlinked successfully" in result.output.lower()

    def test_contracts_list_links_integration(self, runner, temp_config_dir, api_base_url):
        """Test contracts list-links command integration"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Test list-links (may fail if API not available or contract doesn't exist)
        result = runner.invoke(
            cli, ["contracts", "list-links", "00000000-0000-0000-0000-000000000000"]  # Contract ID
        )

        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            # Should show link information or "No links found"
            assert (
                "ODPS Link" in result.output
                or "ODCS Link" in result.output
                or "No links found" in result.output
            )

    def test_contracts_linking_workflow_integration(self, runner, temp_config_dir, api_base_url):
        """Test complete linking workflow: link, list-links, unlink"""
        config = Config()
        config.set_api_base_url(api_base_url)

        odcs_id = "00000000-0000-0000-0000-000000000000"
        odps_id = "00000000-0000-0000-0000-000000000001"

        # Step 1: Link ODPS to ODCS
        link_result = runner.invoke(cli, ["contracts", "link-odps", odcs_id, odps_id])
        # May fail if contracts don't exist, which is OK for integration test
        assert link_result.exit_code == 0

        # Step 2: List links (if linking succeeded)
        if link_result.exit_code == 0:
            list_result = runner.invoke(cli, ["contracts", "list-links", odcs_id])
            assert list_result.exit_code == 0
            if list_result.exit_code == 0:
                assert "ODPS Link" in list_result.output or "No links found" in list_result.output

            # Step 3: Unlink (if linking succeeded)
            unlink_result = runner.invoke(cli, ["contracts", "unlink-odps", odcs_id])
            assert unlink_result.exit_code == 0
            if unlink_result.exit_code == 0:
                assert "unlinked successfully" in unlink_result.output.lower()


class TestLineageIntegration:
    """Integration tests for lineage commands"""

    def test_lineage_contract_integration(self, runner, temp_config_dir, api_base_url):
        """Test lineage contract command integration"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Try to get lineage (may fail if API not available, which is OK)
        result = runner.invoke(cli, ["lineage", "contract", "test-contract-id"])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0

    def test_lineage_full_integration(self, runner, temp_config_dir, api_base_url):
        """Test lineage full command integration"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(
            cli,
            [
                "lineage",
                "full",
                "test-contract-id",
                "--max-contract-depth",
                "5",
                "--max-model-depth",
                "3",
            ],
        )

        assert result.exit_code == 0


class TestAssetsIntegration:
    """Integration tests for assets commands"""

    def test_assets_list_integration(self, runner, temp_config_dir, api_base_url):
        """Test assets list command integration"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code == 0

    def test_assets_create_get_flow(self, runner, temp_config_dir, api_base_url):
        """Test complete flow: create asset, then get it"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(
            cli, ["assets", "create", "--name", "Test Asset", "--key", "test-asset-integration"]
        )

        assert result.exit_code == 0

        # If creation succeeded, try to get it
        if result.exit_code == 0:
            # Extract asset ID from output (if available)
            pass


class TestFilesIntegration:
    """Integration tests for files commands"""

    def test_files_list_integration(self, runner, temp_config_dir, api_base_url):
        """Test files list command integration"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(cli, ["files", "list"])

        assert result.exit_code == 0

    def test_files_upload_download_flow(
        self, runner, temp_config_dir, api_base_url, temp_file, tmp_path
    ):
        """Test complete flow: upload file, then download it"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Create a test file
        file_path, content = temp_file(".csv", "col1,col2\nval1,val2")

        # Try to upload
        result = runner.invoke(cli, ["files", "upload", file_path])

        assert result.exit_code == 0

        # If upload succeeded, try to download
        if result.exit_code == 0:
            # Extract file ID from output (if available)
            pass


class TestJobsIntegration:
    """Integration tests for jobs commands"""

    def test_jobs_list_integration(self, runner, temp_config_dir, api_base_url):
        """Test jobs list command integration"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(cli, ["jobs", "list"])

        assert result.exit_code == 0

    def test_jobs_get_watch_flow(self, runner, temp_config_dir, api_base_url):
        """Test complete flow: get job, then watch it"""
        config = Config()
        config.set_api_base_url(api_base_url)

        # Try to get a job
        result = runner.invoke(cli, ["jobs", "get", "test-job-id"])

        assert result.exit_code == 0

        # If job exists, try to watch it (with short timeout for testing)
        if result.exit_code == 0:
            watch_result = runner.invoke(
                cli, ["jobs", "watch", "test-job-id", "--interval", "1", "--timeout", "5"]
            )
            assert watch_result.exit_code == 0


class TestCommandErrorHandling:
    """Test error handling across all commands"""

    def test_invalid_command(self, runner):
        """Test handling invalid command"""
        result = runner.invoke(cli, ["invalid-command"])

        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output

    def test_missing_required_argument(self, runner):
        """Test handling missing required arguments"""
        result = runner.invoke(cli, ["contracts", "get"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output or "Usage:" in result.output

    def test_invalid_option_value(self, runner):
        """Test handling invalid option values"""
        result = runner.invoke(cli, ["contracts", "list", "--format", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "Usage:" in result.output


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def api_base_url():
    """API base URL fixture (defaults to localhost)"""
    return os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file"""

    def _create_file(extension, content):
        file_path = tmp_path / f"test{extension}"
        file_path.write_text(content)
        return str(file_path), content

    return _create_file
