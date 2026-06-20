"""
Comprehensive E2E tests for Compliance Use Cases.

Tests compliance checks (on dataset, on asset, with custom rules),
compliance reporting (LGPD, GDPR, HIPAA, CCPA, SOX), and access requests
(create, approve, reject).
"""

import tempfile
from pathlib import Path

import pytest
from datahub_cli.main import cli
from tests.use_cases.conftest import unique_key

pytestmark = pytest.mark.mvp


class TestComplianceChecks:
    """E2E tests for compliance check execution"""

    def test_run_compliance_check_on_asset(self, runner, authenticated_config):
        """Test running compliance check on an asset"""
        # First create an asset
        asset_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Compliance Test Asset",
                "--key",
                unique_key("complian"),
            ],
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in asset_result.output:
                lines = asset_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Run compliance check on asset
                compliance_result = runner.invoke(
                    cli, ["compliance", "run", "--asset-id", asset_id, "--scan-mode", "internal"]
                )

                assert compliance_result.exit_code == 0, compliance_result.output
                if compliance_result.exit_code == 0:
                    assert "started successfully" in compliance_result.output.lower()
                    assert "Compliance Run ID:" in compliance_result.output
                    assert "Job ID:" in compliance_result.output

    def test_run_compliance_check_on_dataset(self, runner, authenticated_config):
        """Test that running compliance on a non-existent dataset
        returns a proper 404 error, not a crash."""
        compliance_result = runner.invoke(
            cli,
            [
                "compliance",
                "run",
                "--dataset-id",
                "00000000-0000-0000-0000-000000000000",
                "--scan-mode",
                "internal",
            ],
        )

        # Non-existent dataset → API returns 404 → exit_code=1
        assert compliance_result.exit_code == 1
        lower = compliance_result.output.lower()
        assert "not found" in lower or "failed" in lower

    def test_run_compliance_check_with_custom_regulations(self, runner, authenticated_config):
        """Test running compliance check with custom regulations"""
        # Create asset first
        asset_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Custom Regulations Asset",
                "--key",
                unique_key("custom-r"),
            ],
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in asset_result.output:
                lines = asset_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Run compliance check with specific regulations
                compliance_result = runner.invoke(
                    cli,
                    [
                        "compliance",
                        "run",
                        "--asset-id",
                        asset_id,
                        "--regulations",
                        "GDPR,HIPAA",
                        "--scan-mode",
                        "internal",
                    ],
                )

                assert compliance_result.exit_code == 0, compliance_result.output
                if compliance_result.exit_code == 0:
                    assert "started successfully" in compliance_result.output.lower()
                    assert "Regulations: GDPR,HIPAA" in compliance_result.output

    def test_run_compliance_check_external_scan_only(
        self,
        runner,
        authenticated_config,
    ):
        """Test running external scan-only compliance check.

        File upload requires S3/object-storage. If the upload init
        endpoint rejects the request (storage not configured), we skip.
        """
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
        ) as f:
            f.write("name,email\nJohn Doe,john@example.com\n")
            tmp = f.name

        try:
            upload_result = runner.invoke(
                cli,
                [
                    "files",
                    "upload",
                    tmp,
                ],
            )
            assert upload_result.exit_code == 0, f"File upload failed: {upload_result.output}"

            file_id = None
            for line in upload_result.output.split("\n"):
                if "ID:" in line:
                    file_id = line.split("ID:")[1].strip()
                    break

            assert file_id, "Upload succeeded but no file ID in output"

            compliance_result = runner.invoke(
                cli,
                [
                    "compliance",
                    "run",
                    "--file-id",
                    file_id,
                    "--scan-mode",
                    "external",
                ],
            )
            assert compliance_result.exit_code == 0, (
                f"Compliance run failed: {compliance_result.output}"
            )
            out = compliance_result.output.lower()
            assert "started successfully" in out
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_run_compliance_check_no_resource_id(self, runner, authenticated_config):
        """Test running compliance check without providing resource ID"""
        result = runner.invoke(cli, ["compliance", "run", "--scan-mode", "internal"])

        assert result.exit_code != 0
        assert "at least one" in result.output.lower() or "required" in result.output.lower()

    def test_get_compliance_run_results(self, runner, authenticated_config):
        """Test getting a real compliance run by first creating one."""
        # Create an asset and start a compliance run
        asset_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Compliance Get Asset",
                "--key",
                unique_key("complian"),
            ],
        )
        assert asset_result.exit_code == 0, asset_result.output

        asset_id = None
        for line in asset_result.output.split("\n"):
            if "ID:" in line:
                asset_id = line.split("ID:")[1].strip()
                break
        assert asset_id

        run_result = runner.invoke(
            cli,
            [
                "compliance",
                "run",
                "--asset-id",
                asset_id,
                "--scan-mode",
                "internal",
            ],
        )
        assert run_result.exit_code == 0, f"Compliance run creation failed: {run_result.output}"

        # Extract the run ID from output
        run_id = None
        for line in run_result.output.split("\n"):
            if "Compliance Run ID:" in line:
                run_id = line.split("Compliance Run ID:")[1].strip()
                break

        if run_id:
            result = runner.invoke(
                cli,
                [
                    "compliance",
                    "get",
                    run_id,
                ],
            )
            assert result.exit_code == 0, f"Compliance get failed: {result.output}"

    def test_list_compliance_runs(self, runner, authenticated_config):
        """Test listing compliance runs"""
        result = runner.invoke(cli, ["compliance", "list", "--limit", "10"])

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            # Should either show runs or "No compliance runs found"
            assert "compliance run" in result.output.lower() or "found" in result.output.lower()

    def test_list_compliance_runs_filtered_by_asset(self, runner, authenticated_config):
        """Test listing compliance runs filtered by asset"""
        result = runner.invoke(
            cli,
            [
                "compliance",
                "list",
                "--asset-id",
                "00000000-0000-0000-0000-000000000000",
                "--limit",
                "10",
            ],
        )

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            # Should either show runs or "No compliance runs found"
            assert "compliance run" in result.output.lower() or "found" in result.output.lower()

    def test_list_compliance_runs_filtered_by_status(self, runner, authenticated_config):
        """Test listing compliance runs filtered by status"""
        result = runner.invoke(
            cli, ["compliance", "list", "--status", "SUCCEEDED", "--limit", "10"]
        )

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            # Should either show runs or "No compliance runs found"
            assert "compliance run" in result.output.lower() or "found" in result.output.lower()


class TestComplianceReporting:
    """E2E tests for compliance reporting"""

    def test_generate_gdpr_report(self, runner, authenticated_config):
        """Test generating GDPR compliance report"""
        # Create asset first
        asset_result = runner.invoke(
            cli,
            ["assets", "create", "--name", "GDPR Report Asset", "--key", unique_key("gdpr-rep")],
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in asset_result.output:
                lines = asset_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Generate GDPR report
                report_result = runner.invoke(
                    cli, ["compliance", "report", "--asset-id", asset_id, "--regulation", "GDPR"]
                )

                assert report_result.exit_code == 0, report_result.output
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert (
                        "GDPR" in report_result.output
                        or "compliance run" in report_result.output.lower()
                    )

    def test_generate_hipaa_report(self, runner, authenticated_config):
        """Test generating HIPAA compliance report"""
        # Create asset first
        asset_result = runner.invoke(
            cli,
            ["assets", "create", "--name", "HIPAA Report Asset", "--key", unique_key("hipaa-re")],
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in asset_result.output:
                lines = asset_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Generate HIPAA report
                report_result = runner.invoke(
                    cli, ["compliance", "report", "--asset-id", asset_id, "--regulation", "HIPAA"]
                )

                assert report_result.exit_code == 0, report_result.output
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert (
                        "HIPAA" in report_result.output
                        or "compliance run" in report_result.output.lower()
                    )

    def test_generate_sox_report(self, runner, authenticated_config):
        """Test generating SOX compliance report"""
        # Create asset first
        asset_result = runner.invoke(
            cli, ["assets", "create", "--name", "SOX Report Asset", "--key", unique_key("sox-repo")]
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in asset_result.output:
                lines = asset_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Generate SOX report
                report_result = runner.invoke(
                    cli, ["compliance", "report", "--asset-id", asset_id, "--regulation", "SOX"]
                )

                assert report_result.exit_code == 0, report_result.output
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert (
                        "SOX" in report_result.output
                        or "compliance run" in report_result.output.lower()
                    )

    def test_generate_lgpd_report(self, runner, authenticated_config):
        """Test generating LGPD compliance report"""
        # Create asset first
        asset_result = runner.invoke(
            cli,
            ["assets", "create", "--name", "LGPD Report Asset", "--key", unique_key("lgpd-rep")],
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in asset_result.output:
                lines = asset_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Generate LGPD report
                report_result = runner.invoke(
                    cli, ["compliance", "report", "--asset-id", asset_id, "--regulation", "LGPD"]
                )

                assert report_result.exit_code == 0, report_result.output
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert (
                        "LGPD" in report_result.output
                        or "compliance run" in report_result.output.lower()
                    )

    def test_generate_ccpa_report(self, runner, authenticated_config):
        """Test generating CCPA compliance report"""
        # Create asset first
        asset_result = runner.invoke(
            cli,
            ["assets", "create", "--name", "CCPA Report Asset", "--key", unique_key("ccpa-rep")],
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in asset_result.output:
                lines = asset_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Generate CCPA report
                report_result = runner.invoke(
                    cli, ["compliance", "report", "--asset-id", asset_id, "--regulation", "CCPA"]
                )

                assert report_result.exit_code == 0, report_result.output
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert (
                        "CCPA" in report_result.output
                        or "compliance run" in report_result.output.lower()
                    )

    def test_generate_report_missing_asset_id(self, runner, authenticated_config):
        """Test generating compliance report without asset ID"""
        result = runner.invoke(cli, ["compliance", "report", "--regulation", "GDPR"])

        assert result.exit_code != 0
        assert "required" in result.output.lower() or "asset-id" in result.output.lower()  # noqa: PHASE216-STATIC-ID


class TestAccessRequests:
    """E2E tests for access request management"""

    def test_create_access_request_for_asset(self, runner, authenticated_config):
        """Test creating access request for an asset"""
        # Create asset first
        asset_result = runner.invoke(
            cli,
            ["assets", "create", "--name", "Access Request Asset", "--key", unique_key("access-r")],
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in asset_result.output:
                lines = asset_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Create access request
                request_result = runner.invoke(
                    cli,
                    [
                        "governance",
                        "access-request",
                        "create",
                        "--asset-id",
                        asset_id,
                        "--reason",
                        "Need access for data analysis",
                        "--access-type",
                        "READ",
                    ],
                )

                assert request_result.exit_code == 0, request_result.output
                if request_result.exit_code == 0:
                    assert "created successfully" in request_result.output.lower()
                    assert "Access Request ID:" in request_result.output

    def test_create_access_request_missing_reason(self, runner, authenticated_config):
        """Test creating access request without reason"""
        result = runner.invoke(
            cli,
            [
                "governance",
                "access-request",
                "create",
                "--asset-id",
                "00000000-0000-0000-0000-000000000000",
            ],
        )

        assert result.exit_code != 0
        assert "required" in result.output.lower() or "reason" in result.output.lower()

    def test_create_access_request_no_resource_id(self, runner, authenticated_config):
        """Test creating access request without resource ID"""
        result = runner.invoke(
            cli, ["governance", "access-request", "create", "--reason", "Test reason"]
        )

        assert result.exit_code != 0
        assert "at least one" in result.output.lower() or "required" in result.output.lower()

    def test_get_access_request(self, runner, authenticated_config):
        """Test that getting a non-existent access request
        returns a proper 404 error."""
        result = runner.invoke(
            cli, ["governance", "access-request", "get", "00000000-0000-0000-0000-000000000000"]
        )

        # Non-existent UUID → 404 → exit_code=1
        assert result.exit_code == 1
        lower = result.output.lower()
        assert "not found" in lower or "failed" in lower

    def test_list_access_requests(self, runner, authenticated_config):
        """Test listing access requests"""
        result = runner.invoke(cli, ["governance", "access-request", "list", "--limit", "10"])

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            # Should either show requests or "No access requests found"
            assert "access request" in result.output.lower() or "found" in result.output.lower()

    def test_list_access_requests_filtered_by_status(self, runner, authenticated_config):
        """Test listing access requests filtered by status"""
        result = runner.invoke(
            cli, ["governance", "access-request", "list", "--status", "PENDING", "--limit", "10"]
        )

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            # Should either show requests or "No access requests found"
            assert "access request" in result.output.lower() or "found" in result.output.lower()

    def test_approve_access_request(self, runner, authenticated_config):
        """Test that approving a non-existent access request
        returns a proper 404 error."""
        result = runner.invoke(
            cli, ["governance", "access-request", "approve", "00000000-0000-0000-0000-000000000000"]
        )

        # Non-existent UUID → 404 → exit_code=1
        assert result.exit_code == 1
        lower = result.output.lower()
        assert "not found" in lower or "failed" in lower

    def test_reject_access_request(self, runner, authenticated_config):
        """Test that rejecting a non-existent access request
        returns a proper 404 error."""
        result = runner.invoke(
            cli,
            [
                "governance",
                "access-request",
                "reject",
                "00000000-0000-0000-0000-000000000000",
                "--reason",
                "Access denied due to policy violation",
            ],
        )

        # Non-existent UUID → 404 → exit_code=1
        assert result.exit_code == 1
        lower = result.output.lower()
        assert "not found" in lower or "failed" in lower

    def test_reject_access_request_missing_reason(self, runner, authenticated_config):
        """Test rejecting access request without reason"""
        result = runner.invoke(
            cli, ["governance", "access-request", "reject", "00000000-0000-0000-0000-000000000000"]
        )

        assert result.exit_code != 0
        assert "required" in result.output.lower() or "reason" in result.output.lower()


class TestCompleteComplianceWorkflow:
    """E2E tests for complete compliance workflows"""

    def test_complete_compliance_workflow(self, runner, authenticated_config):
        """Test complete compliance workflow: create asset, run check, generate report"""
        # Create asset
        asset_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Complete Workflow Asset",
                "--key",
                unique_key("complete"),
            ],
        )

        assert asset_result.exit_code == 0, asset_result.output
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if "ID:" in asset_result.output:
                lines = asset_result.output.split("\n")
                for line in lines:
                    if "ID:" in line:
                        asset_id = line.split("ID:")[1].strip()
                        break

            if asset_id:
                # Run compliance check
                compliance_result = runner.invoke(
                    cli,
                    [
                        "compliance",
                        "run",
                        "--asset-id",
                        asset_id,
                        "--regulations",
                        "GDPR,HIPAA",
                        "--scan-mode",
                        "internal",
                    ],
                )

                assert compliance_result.exit_code == 0, compliance_result.output

                # List compliance runs
                list_result = runner.invoke(cli, ["compliance", "list", "--asset-id", asset_id])

                assert list_result.exit_code == 0, list_result.output

                # Generate report (may fail if compliance run not completed yet, which is OK)
                report_result = runner.invoke(
                    cli, ["compliance", "report", "--asset-id", asset_id, "--regulation", "GDPR"]
                )

                assert report_result.exit_code == 0, report_result.output
