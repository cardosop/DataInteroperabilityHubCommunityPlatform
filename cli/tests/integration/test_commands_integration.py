"""
Comprehensive integration tests for CLI commands.

Tests command groups end-to-end with real API structure (when available).
"""

import json
import os

import pytest
from click.testing import CliRunner
from datahub_cli.config import config as global_config
from datahub_cli.main import cli
from tests.use_cases.conftest import _setup_cli_auth, unique_key


def _arm_real_auth() -> None:
    """Point the GLOBAL config at the live backend with real credentials.

    The CLI's api_client reads the global ``datahub_cli.config.config``;
    a local ``Config()`` is invisible to it, so the tests ran
    unauthenticated against a dead port (measured 2026-08-28).
    """
    global_config.clear_auth()
    global_config.set_api_base_url(
        f"http://localhost:{os.environ.get('API_TEST_PORT', '8001')}/api/v1"
    )
    assert _setup_cli_auth(
        f"http://localhost:{os.environ.get('API_TEST_PORT', '8001')}/api/v1", global_config
    ), "Could not set up CLI authentication for integration test"


@pytest.fixture(autouse=True)
def _arm_real_auth_for_all_tests(temp_config_dir):
    """Arm the GLOBAL config with real credentials for every test.

    Several tests in this file do not request the ``api_base_url``
    fixture; the CLI reads the global config, so an autouse fixture is
    the single choke point that guarantees authentication regardless of
    each test's signature.  DEPENDS on ``temp_config_dir`` so the armed
    credentials land in the SAME (monkeypatched) config file the CLI
    reloads — arming before the patch wrote to the real user config and
    the CLI then loaded an empty temp file (measured 2026-08-28).
    """
    _arm_real_auth()


def _json_from_output(output: str):
    """Parse the JSON payload out of CLI output.

    CliRunner mixes stderr into stdout by default, so the contracts
    create command's ``Auto-detected spec type`` notice (emitted on
    stderr, correctly) precedes the JSON payload.  Parse from the first
    ``{`` so machine parsing is robust to human preambles.
    """
    idx = output.find("{")
    if idx == -1:
        raise ValueError(f"No JSON object in output: {output[:200]!r}")
    return json.loads(output[idx:])


def _create_real_contract(runner, temp_file, contract_id: str) -> str:
    """Create a real ODCS contract via the CLI and return its id."""
    contract_file, _ = temp_file(
        ".yaml",
        f"apiVersion: odcs.io/v3.0.0\n"
        f"kind: DataContract\n"
        f"id: {contract_id}\n"
        f"name: {contract_id}\n"
        f"version: 1.0.0\n"
        f"schema:\n"
        f"  fields:\n"
        f"    - name: id\n"
        f"      type: string\n",
    )
    result = runner.invoke(
        cli, ["contracts", "create", "--file", contract_file, "--format", "json"]
    )
    assert result.exit_code == 0, f"contract create failed: {result.output[:300]}"
    return _json_from_output(result.output)["id"]


def _create_real_odps(runner, temp_file, product_id: str) -> str:
    """Create a real ODPS (product-first) contract and return its id."""
    content = (
        '{"schema": "https://opendataproducts.org/schema/v4.1", '
        '"version": "4.1", '
        '"product": {"details": {"en": {"productID": "'
        + product_id
        + '", "name": "'
        + product_id
        + '"}}, '
        '"dataSchema": {"fields": [{"name": "id", "type": "string"}]}, '
        '"contract": {"spec": {"apiVersion": "odcs.io/v3.0.0", "kind": "DataContract", '
        '"id": "'
        + product_id
        + '-embedded", "name": "'
        + product_id
        + ' Embedded", "version": "1.0.0", '
        '"schema": {"fields": [{"name": "id", "type": "string"}]}}}}}'
    )
    odps_file, _ = temp_file(".json", content)
    result = runner.invoke(cli, ["contracts", "create", "--file", odps_file, "--format", "json"])
    assert result.exit_code == 0, f"ODPS create failed: {result.output[:300]}"
    return _json_from_output(result.output)["id"]


class TestContractsIntegration:
    """Integration tests for contracts commands"""

    def test_contracts_list_integration(self, runner, temp_config_dir, api_base_url):
        """Test contracts list command integration"""
        _arm_real_auth()

        # Try to list contracts (may fail if API not available, which is OK)
        result = runner.invoke(cli, ["contracts", "list"])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        # If it succeeds, verify output format
        if result.exit_code == 0:
            # Output should be either table or JSON
            assert len(result.output) > 0

    def test_contracts_create_get_flow(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test complete flow: create contract, then get it"""

        # Create a test contract file
        file_path, _content = temp_file(
            ".yaml",
            "apiVersion: odcs.io/v3.0.0\n"
            "kind: DataContract\n"
            "id: e2e-integration-contract\n"
            "name: E2E Integration Contract\n"
            "version: 1.0.0\n"
            "schema:\n"
            "  fields:\n"
            "    - name: id\n"
            "      type: string\n",
        )

        # Try to create contract
        result = runner.invoke(cli, ["contracts", "create", "--file", file_path])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        # If creation succeeded, try to get it
        if result.exit_code == 0:
            # Extract contract ID from output (if available)
            # This is a basic integration test - real implementation would parse output
            pass

    def test_contracts_create_odps_extract_odcs_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts create-odps with --extract-odcs flag (Product-First flow) against real API"""

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
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
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
  }
}"""

        file_path, _content = temp_file(".json", odps_content)

        # Test create-odps with --extract-odcs
        result = runner.invoke(
            cli, ["contracts", "create-odps", "--file", file_path, "--extract-odcs"]
        )

        # Should either succeed or fail gracefully (may need authentication)
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        if result.exit_code == 0:
            assert (
                "ODPS product created successfully" in result.output
                or "odps_contract" in result.output
            )

    def test_contracts_create_odps_link_odcs_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts create-odps with --link-odcs flag against real API"""

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
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": "test-odcs-id",
        "name": "Test ODCS",
        "version": "1.0.0",
        "schema": {"fields": [{"name": "id", "type": "string"}]}
      }
    }
  }
}"""

        file_path, _content = temp_file(".json", odps_content)

        # Create a REAL ODCS contract first — the backend rejects linking
        # to a nonexistent contract ("No Contract matches the given
        # query"), so a dummy ID could never pass (measured 2026-08-28).
        contract_file, _ = temp_file(
            ".yaml",
            "apiVersion: odcs.io/v3.0.0\n"
            "kind: DataContract\n"
            "id: test-odcs-id\n"
            "name: Test ODCS\n"
            "version: 1.0.0\n"
            "schema:\n"
            "  fields:\n"
            "    - name: id\n"
            "      type: string\n",
        )
        create_result = runner.invoke(
            cli, ["contracts", "create", "--file", contract_file, "--format", "json"]
        )
        assert create_result.exit_code == 0, f"contract create failed: {create_result.output[:300]}"
        contract_id = _json_from_output(create_result.output)["id"]

        # Test create-odps with --link-odcs against the real contract.
        result = runner.invoke(
            cli,
            [
                "contracts",
                "create-odps",
                "--file",
                file_path,
                "--link-odcs",
                contract_id,
            ],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"

    def test_contracts_export_odps_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts export with ODPS format against real API"""
        _arm_real_auth()

        # Export requires an ODPS-format contract.
        contract_id = _create_real_odps(runner, temp_file, "export-test-product")

        result = runner.invoke(
            cli,
            [
                "contracts",
                "export",
                contract_id,
                "--format",
                "odps",
                "--output-format",
                "json",
            ],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
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

        # Create output file path
        output_file = tmp_path / "downloaded_odps.json"

        contract_id = _create_real_contract(runner, temp_file, "download-test-contract")
        result = runner.invoke(
            cli,
            [
                "contracts",
                "download",
                contract_id,
                "--format",
                "odps",
                "--output-format",
                "json",
                "--output",
                str(output_file),
            ],
        )

        # Should either succeed or fail gracefully
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        if result.exit_code == 0:
            # If successful, file should exist
            assert output_file.exists() or "downloaded successfully" in result.output.lower()

    def test_contracts_create_with_odps_detection_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts create with ODPS auto-detection against real API"""

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
    },
    "dataSchema": {
      "fields": [
        {"name": "id", "type": "string"}
      ]
    }
  }
}"""

        file_path, _content = temp_file(".json", odps_content)

        # Test create with auto-detection (may fail if API not available)
        result = runner.invoke(cli, ["contracts", "create", "--file", file_path])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
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

        # Test list command (may fail if API not available)
        result = runner.invoke(cli, ["contracts", "list"])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        if result.exit_code == 0:
            # If successful, should show Spec Type column
            assert "Spec Type" in result.output or len(result.output) > 0

    def test_contracts_link_odps_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts link-odps command integration"""
        _arm_real_auth()

        odcs_id = _create_real_contract(runner, temp_file, "link-odcs-contract")
        odps_id = _create_real_odps(runner, temp_file, "link-odps-product")

        # Test link-odps against real contracts.
        result = runner.invoke(
            cli,
            ["contracts", "link-odps", odcs_id, odps_id],
        )

        # Should either succeed or fail gracefully
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        if result.exit_code == 0:
            assert "linked successfully" in result.output.lower()

    def test_contracts_unlink_odps_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts unlink-odps command integration"""
        _arm_real_auth()

        contract_id = _create_real_contract(runner, temp_file, "unlink-test-contract")
        result = runner.invoke(
            cli,
            ["contracts", "unlink-odps", contract_id],
        )

        # Should either succeed or fail gracefully
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        if result.exit_code == 0:
            assert "unlinked successfully" in result.output.lower()

    def test_contracts_list_links_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test contracts list-links command integration"""
        _arm_real_auth()

        contract_id = _create_real_contract(runner, temp_file, "list-links-test-contract")
        result = runner.invoke(
            cli,
            ["contracts", "list-links", contract_id],
        )

        # Should either succeed or fail gracefully
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        if result.exit_code == 0:
            # Should show link information or "No links found"
            assert (
                "ODPS Link" in result.output
                or "ODCS Link" in result.output
                or "No links found" in result.output
            )

    def test_contracts_linking_workflow_integration(
        self, runner, temp_config_dir, api_base_url, temp_file
    ):
        """Test complete linking workflow: link, list-links, unlink"""
        _arm_real_auth()

        odcs_id = _create_real_contract(runner, temp_file, "workflow-odcs")
        odps_id = _create_real_odps(runner, temp_file, "workflow-odps-product")

        # Step 1: Link ODPS to ODCS
        link_result = runner.invoke(cli, ["contracts", "link-odps", odcs_id, odps_id])
        # May fail if contracts don't exist, which is OK for integration test
        assert link_result.exit_code == 0, f"CLI failed: {link_result.output[:300]}"
        # Step 2: List links (if linking succeeded)
        if link_result.exit_code == 0:
            list_result = runner.invoke(cli, ["contracts", "list-links", odcs_id])
            assert list_result.exit_code == 0, f"CLI failed: {list_result.output[:300]}"
            if list_result.exit_code == 0:
                assert "ODPS Link" in list_result.output or "No links found" in list_result.output

            # Step 3: Unlink (if linking succeeded)
            unlink_result = runner.invoke(cli, ["contracts", "unlink-odps", odcs_id])
            assert unlink_result.exit_code == 0, f"CLI failed: {unlink_result.output[:300]}"
            if unlink_result.exit_code == 0:
                assert "unlinked successfully" in unlink_result.output.lower()


class TestLineageIntegration:
    """Integration tests for lineage commands"""

    def test_lineage_contract_integration(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test lineage contract command integration"""
        _arm_real_auth()

        contract_id = _create_real_contract(runner, temp_file, "lineage-test-contract")
        result = runner.invoke(cli, ["lineage", "contract", contract_id])

        # Should either succeed or fail gracefully
        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"

    def test_lineage_full_integration(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test lineage full command integration"""
        _arm_real_auth()

        contract_id = _create_real_contract(runner, temp_file, "lineage-full-test-contract")
        result = runner.invoke(
            cli,
            [
                "lineage",
                "full",
                contract_id,
                "--max-contract-depth",
                "5",
                "--max-model-depth",
                "3",
            ],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"


class TestAssetsIntegration:
    """Integration tests for assets commands"""

    def test_assets_list_integration(self, runner, temp_config_dir, api_base_url):
        """Test assets list command integration"""
        _arm_real_auth()

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"

    def test_assets_create_get_flow(self, runner, temp_config_dir, api_base_url):
        """Test complete flow: create asset, then get it"""
        _arm_real_auth()

        result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Test Asset",
                "--key",
                unique_key("test-asset-integration"),
            ],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        # If creation succeeded, try to get it
        if result.exit_code == 0:
            # Extract asset ID from output (if available)
            pass


class TestFilesIntegration:
    """Integration tests for files commands"""

    def test_files_list_integration(self, runner, temp_config_dir, api_base_url):
        """Test files list command integration"""
        _arm_real_auth()

        result = runner.invoke(cli, ["files", "list"])

        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"

    def test_files_upload_download_flow(
        self, runner, temp_config_dir, api_base_url, temp_file, tmp_path
    ):
        """Test complete flow: upload file, then download it"""

        # Create a test file
        file_path, _content = temp_file(".csv", "col1,col2\nval1,val2")

        # Per-run unique name (unique_active_filename_per_tenant index).
        upload_name = f"{unique_key('integration-upload')}.csv"
        result = runner.invoke(cli, ["files", "upload", file_path, "--name", upload_name])

        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        # If upload succeeded, try to download
        if result.exit_code == 0:
            # Extract file ID from output (if available)
            pass


class TestJobsIntegration:
    """Integration tests for jobs commands"""

    def test_jobs_list_integration(self, runner, temp_config_dir, api_base_url):
        """Test jobs list command integration"""
        _arm_real_auth()

        result = runner.invoke(cli, ["jobs", "list"])

        assert result.exit_code == 0, f"CLI failed: {result.output[:300]}"

    def test_jobs_get_watch_flow(self, runner, temp_config_dir, api_base_url):
        """Test complete flow: get job, then watch it"""
        _arm_real_auth()

        # A hardcoded job id can never exist on a fresh backend — the get
        # must fail CLEANLY with a not-found message, not crash.
        result = runner.invoke(cli, ["jobs", "get", "test-job-id"])
        if result.exit_code == 0:
            watch_result = runner.invoke(
                cli, ["jobs", "watch", "test-job-id", "--interval", "1", "--timeout", "5"]
            )
            assert watch_result.exit_code == 0, f"CLI failed: {result.output[:300]}"
        else:
            # No real job to fetch — the command must report a clean error.
            assert (
                "not found" in result.output.lower()
                or "404" in result.output.lower()
                or "no job" in result.output.lower()
            )


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
    """API base URL fixture — arms the GLOBAL config with real auth.

    The CLI's api_client reads ``datahub_cli.config.config``; the local
    ``Config()`` instances in the test bodies are invisible to it, so the
    whole file ran unauthenticated against a dead localhost:8000 port
    (measured 2026-08-28).  Arm the global config here — the single point
    every test's fixture chain passes through.
    """
    port = os.environ.get("API_TEST_PORT", "8001")
    base = f"http://localhost:{port}/api/v1"
    global_config.clear_auth()
    global_config.set_api_base_url(base)
    assert _setup_cli_auth(base, global_config), (
        "Could not set up CLI authentication for integration test"
    )
    return base


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file"""

    def _create_file(extension, content):
        file_path = tmp_path / f"test{extension}"
        file_path.write_text(content)
        return str(file_path), content

    return _create_file
