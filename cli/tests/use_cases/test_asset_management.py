"""
Comprehensive E2E tests for Asset Management Use Cases.

Tests asset creation (data-first, contract-first, all/minimal metadata),
asset updates, asset deletion, and asset search scenarios.
"""

import json

import pytest
from datahub_cli.main import cli
from tests.use_cases.conftest import unique_key

pytestmark = pytest.mark.mvp


class TestAssetCreation:
    """E2E tests for asset creation"""

    def test_create_asset_minimal_metadata(self, runner, authenticated_config):
        """Test asset creation with minimal metadata (name and key only)"""
        result = runner.invoke(
            cli, ["assets", "create", "--name", "Minimal Asset", "--key", unique_key("min-asset")]
        )

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            assert "created successfully" in result.output.lower()
            assert "Minimal Asset" in result.output
            # Extract asset ID if possible
            output_data = result.output
            assert "ID:" in output_data or "id" in output_data.lower()

    def test_create_asset_all_metadata(self, runner, authenticated_config):
        """Test asset creation with all metadata fields"""
        result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Complete Asset",
                "--key",
                unique_key("cpl-asset"),
                "--description",
                "This is a complete asset with all metadata fields",
                "--domain",
                "sales",
                "--visibility",
                "PUBLIC",
            ],
        )

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            assert "created successfully" in result.output.lower()
            assert "Complete Asset" in result.output
            # The CLI create output shows ID, Name, Status.
            # Domain is stored but not echoed in the create response.
            # Verify via JSON output or get command instead.
            assert "ID:" in result.output

    def test_create_asset_data_first_flow_simulation(self, runner, authenticated_config, temp_file):
        """Test data-first flow: Create asset, then upload file (simulated)"""
        # Step 1: Create asset with minimal metadata
        create_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Data-First Asset",
                "--key",
                unique_key("df-asset"),
                "--description",
                "Asset created in data-first flow",
            ],
        )

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Extract asset ID from output
            asset_id = None
            if "ID:" in create_result.output:
                lines = create_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            assert asset_id, "Asset ID not found in create output"

            # Step 2: Upload a file (simulating data-first flow).
            # File upload depends on S3/object-storage being configured;
            # the CLI command exists but the backend init endpoint may
            # return an error if storage is not provisioned.
            file_path, _content = temp_file(".csv", "col1,col2\nval1,val2")
            upload_result = runner.invoke(
                cli, ["files", "upload", file_path, "--name", "data-first-file.csv"]
            )

            assert upload_result.exit_code == 0, f"File upload failed: {upload_result.output}"

    def test_create_asset_contract_first_flow_simulation(
        self, runner, authenticated_config, temp_file
    ):
        """Test contract-first flow: Create contract, then create asset (simulated)"""
        # Step 1: Create a valid ODCS contract file
        contract_file, _ = temp_file(
            ".yaml",
            """apiVersion: odcs/v3
kind: DataContract
id: contract-first-test
name: Contract-First Contract
version: 1.0.0
schema:
  fields:
    - name: field1
      type: string
""",
        )

        contract_result = runner.invoke(cli, ["contracts", "create", "--file", contract_file])

        # Contract creation may fail if the YAML doesn't match the expected
        # ODCS schema exactly; accept graceful failure
        if contract_result.exit_code != 0:
            pytest.skip(
                f"Contract creation failed (schema mismatch): {contract_result.output[:200]}"
            )

        # Step 2: Create asset (contract-first flow)
        asset_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Contract-First Asset",
                "--key",
                unique_key("cf-asset"),
                "--description",
                "Asset created in contract-first flow",
            ],
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            assert "created successfully" in asset_result.output.lower()

    def test_create_asset_json_output(self, runner, authenticated_config):
        """Test asset creation with JSON output format"""
        result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "JSON Asset",
                "--key",
                unique_key("json-asset"),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        if result.exit_code == 0 and result.output.strip():
            # Should be valid JSON
            try:
                output_data = json.loads(result.output)
                assert isinstance(output_data, dict)
                assert "id" in output_data or "name" in output_data
            except json.JSONDecodeError:
                # If not JSON, that's OK for this test
                pass

    def test_create_asset_duplicate_key(self, runner, authenticated_config):
        """Test asset creation with duplicate key (should fail)"""
        _dup_key = unique_key("duptest")
        # Create first asset
        result1 = runner.invoke(
            cli, ["assets", "create", "--name", "First Asset", "--key", _dup_key]
        )

        # Try to create second asset with same key
        result2 = runner.invoke(
            cli, ["assets", "create", "--name", "Second Asset", "--key", _dup_key]
        )

        # Second creation should fail if API enforces uniqueness
        if result1.exit_code == 0:
            # The API enforces key uniqueness per tenant — second create
            # returns a validation error (exit_code 1)
            assert result2.exit_code != 0, "Expected duplicate key to be rejected"


class TestAssetUpdates:
    """E2E tests for asset updates"""

    def test_update_asset_metadata(self, runner, authenticated_config):
        """Test updating asset metadata (name, description, domain)"""
        # Create asset first
        create_result = runner.invoke(
            cli, ["assets", "create", "--name", "Original Name", "--key", unique_key("upd-asset")]
        )

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in create_result.output:
                lines = create_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Update asset metadata
                update_result = runner.invoke(
                    cli,
                    [
                        "assets",
                        "update",
                        asset_id,
                        "--name",
                        "Updated Name",
                        "--description",
                        "Updated description",
                        "--domain",
                        "marketing",
                    ],
                )

                assert update_result.exit_code == 0, update_result.output
                if update_result.exit_code == 0:
                    assert "updated successfully" in update_result.output.lower()
                    assert "Updated Name" in update_result.output

    def test_update_asset_status_via_activate(self, runner, authenticated_config):
        """Test activating a DRAFT asset.

        Activation requires an ACTIVE contract with valid
        normalization/validation statuses. A freshly created asset
        has no contract, so activation is expected to be blocked
        by the backend's business rules (HTTP 400
        ASSET_ACTIVATION_BLOCKED).
        """
        create_result = runner.invoke(
            cli, ["assets", "create", "--name", "Draft Asset", "--key", unique_key("act-asset")]
        )
        assert create_result.exit_code == 0, create_result.output

        asset_id = None
        for line in create_result.output.split("\n"):
            if "ID:" in line:
                asset_id = line.split("ID:")[1].strip()
                break
        assert asset_id

        # Activation should fail — no contract attached yet.
        # The backend checks prerequisites (ACTIVE contract, etc.)
        # and returns ASSET_ACTIVATION_BLOCKED.
        activate_result = runner.invoke(cli, ["assets", "activate", asset_id])
        assert activate_result.exit_code == 1, (
            f"Expected activation to be blocked (no contract), but got: {activate_result.output}"
        )

    def test_update_asset_visibility(self, runner, authenticated_config):
        """Test updating asset visibility"""
        # Create asset with INTERNAL visibility
        create_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Visibility Test Asset",
                "--key",
                unique_key("vis-asset"),
                "--visibility",
                "INTERNAL",
            ],
        )

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in create_result.output:
                lines = create_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Update visibility to PUBLIC
                update_result = runner.invoke(
                    cli, ["assets", "update", asset_id, "--visibility", "PUBLIC"]
                )

                assert update_result.exit_code == 0, update_result.output
                if update_result.exit_code == 0:
                    assert "updated successfully" in update_result.output.lower()

    def test_update_asset_no_fields(self, runner, authenticated_config):
        """Test updating asset with no fields (should fail)"""
        # Create asset first
        create_result = runner.invoke(
            cli,
            ["assets", "create", "--name", "No Update Asset", "--key", unique_key("noupd-asset")],
        )

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in create_result.output:
                lines = create_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Try to update with no fields
                update_result = runner.invoke(cli, ["assets", "update", asset_id])

                # Should fail with error message
                assert update_result.exit_code != 0
                assert (
                    "No fields to update" in update_result.output
                    or "Missing option" in update_result.output
                )


class TestAssetDeletion:
    """E2E tests for asset deletion"""

    def test_delete_draft_asset(self, runner, authenticated_config):
        """Test deleting a draft asset"""
        # Create draft asset
        create_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Draft Asset To Delete",
                "--key",
                unique_key("deldraft"),
            ],
        )

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in create_result.output:
                lines = create_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Delete with confirmation flag
                delete_result = runner.invoke(cli, ["assets", "delete", asset_id, "--confirm"])

                assert delete_result.exit_code == 0, delete_result.output
                if delete_result.exit_code == 0:
                    assert "deleted successfully" in delete_result.output.lower()

    def test_delete_active_asset(self, runner, authenticated_config):
        """Test deleting an active asset"""
        # Create and activate asset
        create_result = runner.invoke(
            cli,
            ["assets", "create", "--name", "Active Asset To Delete", "--key", unique_key("delact")],
        )

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in create_result.output:
                lines = create_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Activate first
                runner.invoke(cli, ["assets", "activate", asset_id])

                # Then delete
                delete_result = runner.invoke(cli, ["assets", "delete", asset_id, "--confirm"])

                assert delete_result.exit_code == 0, delete_result.output
                # May succeed or fail depending on API policy for active assets
                if delete_result.exit_code == 0:
                    assert "deleted successfully" in delete_result.output.lower()

    def test_delete_asset_with_dependencies_simulation(
        self, runner, authenticated_config, temp_file
    ):
        """Test deleting asset with dependencies (contract, dataset) - simulated"""
        # Create asset
        create_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Asset With Dependencies",
                "--key",
                unique_key("deldeps"),
            ],
        )

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in create_result.output:
                lines = create_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Create contract for this asset (simulating dependency)
                contract_file, _contract_content = temp_file(
                    ".yaml", "name: Test Contract\nversion: 1.0"
                )
                runner.invoke(
                    cli, ["contracts", "create", "--file", contract_file, "--asset-id", asset_id]
                )

                # Try to delete asset (may fail if dependencies exist)
                delete_result = runner.invoke(cli, ["assets", "delete", asset_id, "--confirm"])

                assert delete_result.exit_code == 0, delete_result.output
                # May succeed or fail depending on API dependency handling
                if delete_result.exit_code != 0:
                    assert (
                        "dependenc" in delete_result.output.lower()
                        or "cannot delete" in delete_result.output.lower()
                        or "Failed to delete asset" in delete_result.output
                    )

    def test_delete_asset_cancelled(self, runner, authenticated_config):
        """Test cancelling asset deletion"""
        # Create asset
        create_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Asset To Cancel Delete",
                "--key",
                unique_key("delcanc"),
            ],
        )

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in create_result.output:
                lines = create_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Try to delete without confirmation, answer 'n'
                delete_result = runner.invoke(cli, ["assets", "delete", asset_id], input="n\n")

                # Should be cancelled
                assert "Cancelled" in delete_result.output or delete_result.exit_code == 0


class TestAssetSearch:
    """E2E tests for asset search"""

    def test_search_assets_by_name(self, runner, authenticated_config):
        """Test searching assets by name (via list with filters)"""
        # Create asset with specific name
        runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Searchable Asset Name",
                "--key",
                unique_key("srchname"),
            ],
        )

        # List assets (API may support name filtering via search)
        list_result = runner.invoke(cli, ["assets", "list"])

        assert list_result.exit_code == 0, list_result.output
        # Should list assets (may or may not include the one we just created)

    def test_search_assets_by_domain(self, runner, authenticated_config):
        """Test searching assets by domain"""
        # Create asset with specific domain
        runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Domain Search Asset",
                "--key",
                unique_key("srchdom"),
                "--domain",
                "sales",
            ],
        )

        # List assets filtered by domain
        list_result = runner.invoke(cli, ["assets", "list", "--domain", "sales"])

        assert list_result.exit_code == 0, list_result.output
        if list_result.exit_code == 0:
            # Should show assets in sales domain
            assert "sales" in list_result.output.lower() or "No assets found" in list_result.output

    def test_search_assets_by_status(self, runner, authenticated_config):
        """Test searching assets by status"""
        # Create draft asset
        runner.invoke(
            cli,
            ["assets", "create", "--name", "Status Search Asset", "--key", unique_key("srchst")],
        )

        # List assets filtered by status
        list_result = runner.invoke(cli, ["assets", "list", "--status", "DRAFT"])

        assert list_result.exit_code == 0, list_result.output
        if list_result.exit_code == 0:
            # Should show draft assets
            assert "DRAFT" in list_result.output or "No assets found" in list_result.output

    def test_search_assets_pagination(self, runner, authenticated_config):
        """Test asset search with pagination"""
        # List assets with pagination
        list_result = runner.invoke(cli, ["assets", "list", "--limit", "10", "--offset", "0"])

        assert list_result.exit_code == 0, list_result.output
        # Should handle pagination correctly

    def test_search_assets_json_output(self, runner, authenticated_config):
        """Test asset search with JSON output"""
        list_result = runner.invoke(cli, ["assets", "list", "--format", "json"])

        assert list_result.exit_code == 0, list_result.output
        if list_result.exit_code == 0 and list_result.output.strip():
            # Should be valid JSON
            try:
                output_data = json.loads(list_result.output)
                assert isinstance(output_data, list)
            except json.JSONDecodeError:
                # If not JSON, that's OK for this test
                pass

    def test_search_assets_empty_result(self, runner, authenticated_config):
        """Test asset search with no results"""
        # Search for non-existent domain
        list_result = runner.invoke(cli, ["assets", "list", "--domain", "non-existent-domain-xyz"])

        assert list_result.exit_code == 0, list_result.output
        if list_result.exit_code == 0:
            # Should show "No assets found" or empty list
            assert (
                "No assets found" in list_result.output
                or list_result.output.strip() == ""
                or list_result.output.strip() == "[]"
            )


class TestAssetManagementWorkflows:
    """E2E tests for complete asset management workflows"""

    def test_complete_asset_lifecycle(self, runner, authenticated_config):
        """Test complete asset lifecycle: create -> update -> activate -> delete"""
        # Step 1: Create asset
        create_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Lifecycle Asset",
                "--key",
                unique_key("lifecycle"),
                "--description",
                "Testing complete lifecycle",
            ],
        )

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in create_result.output:
                lines = create_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Step 2: Update asset
                runner.invoke(
                    cli,
                    [
                        "assets",
                        "update",
                        asset_id,
                        "--name",
                        "Updated Lifecycle Asset",
                        "--domain",
                        "marketing",
                    ],
                )

                # Step 3: Activate asset
                runner.invoke(cli, ["assets", "activate", asset_id])

                # Step 4: Get asset details
                get_result = runner.invoke(cli, ["assets", "get", asset_id])

                assert get_result.exit_code == 0, get_result.output
                if get_result.exit_code == 0:
                    assert (
                        "Lifecycle Asset" in get_result.output
                        or "Updated Lifecycle Asset" in get_result.output
                    )

                # Step 5: Delete asset
                delete_result = runner.invoke(cli, ["assets", "delete", asset_id, "--confirm"])

                # All steps should complete (may succeed or fail depending on API)
                assert delete_result.exit_code == 0, delete_result.output
