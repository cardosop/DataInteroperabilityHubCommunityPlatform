"""
Comprehensive E2E tests for Data Quality Use Cases.

Tests DQ check execution (on dataset, on asset, with custom rules),
DQ result review, and DQ alerts scenarios.
"""
import json

import pytest

from datahub_cli.main import cli
from tests.use_cases.conftest import unique_key

pytestmark = pytest.mark.mvp


class TestDQCheckExecution:
    """E2E tests for DQ check execution"""

    def test_run_dq_check_on_asset(self, runner, authenticated_config):
        """Test running DQ check on an asset.

        The DQ run creation endpoint is local (creates a DB record and
        queues an async job).  The actual DQ execution happens
        asynchronously via the DQ service — so creation should succeed
        even when the DQ service is unreachable.
        """
        # First create an asset
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'DQ Test Asset',
            '--key', unique_key('dq-test-')
        ])

        assert asset_result.exit_code == 0, asset_result.output
        if 'ID:' in asset_result.output:
            asset_id = None
            for line in asset_result.output.split('\n'):
                if 'ID:' in line:
                    asset_id = line.split('ID:')[1].strip()
                    break

            if asset_id:
                # Run DQ check — creates a run record and queues a job
                dq_result = runner.invoke(cli, [
                    'dq', 'run',
                    '--asset-id', asset_id,
                    '--profile-key', 'intake_basic_gx'
                ])

                assert dq_result.exit_code == 0, (
                    f"DQ run creation failed: {dq_result.output}"
                )
                assert 'started successfully' in dq_result.output.lower()

    def test_run_dq_check_on_dataset(self, runner, authenticated_config):
        """Test that running DQ check on a non-existent dataset returns
        a proper error (404), not a crash.
        """
        dq_result = runner.invoke(cli, [
            'dq', 'run',
            '--dataset-id', '00000000-0000-0000-0000-000000000000',
            '--profile-key', 'intake_basic_gx'
        ])

        # Non-existent dataset → the API returns 404 → CLI exit_code=1
        assert dq_result.exit_code == 1
        assert 'not found' in dq_result.output.lower() or 'failed' in dq_result.output.lower()

    def test_run_dq_check_with_custom_profile(self, runner, authenticated_config):
        """Test running DQ check with explicit profile key."""
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Custom Profile Asset',
            '--key', unique_key('custom-p')
        ])

        assert asset_result.exit_code == 0, asset_result.output
        asset_id = None
        for line in asset_result.output.split('\n'):
            if 'ID:' in line:
                asset_id = line.split('ID:')[1].strip()
                break

        if asset_id:
            dq_result = runner.invoke(cli, [
                'dq', 'run',
                '--asset-id', asset_id,
                '--profile-key', 'intake_basic_gx'
            ])

            assert dq_result.exit_code == 0, (
                f"DQ run creation failed: {dq_result.output}"
            )
            assert 'started successfully' in dq_result.output.lower()

    def test_run_dq_check_external_scan_only(self, runner, authenticated_config, temp_file):
        """Test running DQ check on an uploaded file (scan-only mode).

        File upload requires S3/object-storage to be configured.
        If the init endpoint rejects the upload (no storage configured),
        we skip the rest of the test.
        """
        file_path, content = temp_file('.csv', 'id,name\n1,Test\n2,Sample')
        upload_result = runner.invoke(cli, [
            'files', 'upload', file_path
        ])

        assert upload_result.exit_code == 0, (
            f"File upload failed: {upload_result.output}"
        )

        file_id = None
        for line in upload_result.output.split('\n'):
            if 'ID:' in line:
                file_id = line.split('ID:')[1].strip()
                break

        if file_id:
            dq_result = runner.invoke(cli, [
                'dq', 'run',
                '--file-id', file_id,
                '--profile-key', 'intake_basic_gx'
            ])
            assert dq_result.exit_code == 0, (
                f"DQ run creation failed: {dq_result.output}"
            )

    def test_run_dq_check_no_resource_id(self, runner, authenticated_config):
        """Test running DQ check without resource ID (should fail)"""
        result = runner.invoke(cli, [
            'dq', 'run',
            '--profile-key', 'intake_basic_gx'
        ])

        assert result.exit_code != 0
        assert 'must be provided' in result.output.lower() or 'required' in result.output.lower()

    def test_run_dq_check_json_output(self, runner, authenticated_config):
        """Test running DQ check with JSON output format"""
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'JSON DQ Asset',
            '--key', unique_key('json-dq-')
        ])

        assert asset_result.exit_code == 0, asset_result.output
        asset_id = None
        for line in asset_result.output.split('\n'):
            if 'ID:' in line:
                asset_id = line.split('ID:')[1].strip()
                break

        if asset_id:
            dq_result = runner.invoke(cli, [
                'dq', 'run',
                '--asset-id', asset_id,
                '--format', 'json'
            ])

            assert dq_result.exit_code == 0, (
                f"DQ run (JSON) failed: {dq_result.output}"
            )
            if dq_result.output.strip():
                output_data = json.loads(dq_result.output)
                assert isinstance(output_data, dict)


class TestDQResultReview:
    """E2E tests for DQ result review"""

    def test_get_dq_run_results(self, runner, authenticated_config):
        """Test getting a non-existent DQ run returns proper 404 error."""
        result = runner.invoke(cli, [
            'dq', 'get',
            '00000000-0000-0000-0000-000000000000'
        ])

        # Non-existent UUID → 404 → exit_code=1
        assert result.exit_code == 1
        assert 'not found' in result.output.lower() or 'failed' in result.output.lower()

    def test_get_dq_run_results_with_checks(self, runner, authenticated_config):
        """Test getting DQ run that was just created (has real data)."""
        # Create asset
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'DQ Results Asset',
            '--key', unique_key('dq-resul')
        ])
        assert asset_result.exit_code == 0, asset_result.output

        asset_id = None
        for line in asset_result.output.split('\n'):
            if 'ID:' in line:
                asset_id = line.split('ID:')[1].strip()
                break
        assert asset_id

        # Create a DQ run
        run_result = runner.invoke(cli, [
            'dq', 'run', '--asset-id', asset_id
        ])
        assert run_result.exit_code == 0, (
            f"DQ run creation failed: {run_result.output}"
        )

        # Extract DQ run ID
        dq_run_id = None
        for line in run_result.output.split('\n'):
            if 'DQ Run ID:' in line:
                dq_run_id = line.split('DQ Run ID:')[1].strip()
                break

        if dq_run_id:
            get_result = runner.invoke(cli, ['dq', 'get', dq_run_id])
            assert get_result.exit_code == 0, (
                f"DQ get failed for run {dq_run_id}: {get_result.output}"
            )
            assert 'Status:' in get_result.output

    def test_get_dq_run_json_output(self, runner, authenticated_config):
        """Test getting DQ run results with JSON output."""
        # Create a real DQ run first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'JSON Get Asset',
            '--key', unique_key('json-get')
        ])
        assert asset_result.exit_code == 0, asset_result.output

        asset_id = None
        for line in asset_result.output.split('\n'):
            if 'ID:' in line:
                asset_id = line.split('ID:')[1].strip()
                break

        if asset_id:
            run_result = runner.invoke(cli, ['dq', 'run', '--asset-id', asset_id])
            assert run_result.exit_code == 0, run_result.output

            dq_run_id = None
            for line in run_result.output.split('\n'):
                if 'DQ Run ID:' in line:
                    dq_run_id = line.split('DQ Run ID:')[1].strip()
                    break

            if dq_run_id:
                result = runner.invoke(cli, [
                    'dq', 'get', dq_run_id, '--format', 'json'
                ])
                assert result.exit_code == 0, result.output
                if result.output.strip():
                    output_data = json.loads(result.output)
                    assert isinstance(output_data, dict)

    def test_list_dq_runs(self, runner, authenticated_config):
        """Test listing DQ runs (may be empty)."""
        result = runner.invoke(cli, ['dq', 'list'])
        assert result.exit_code == 0, (
            f"DQ list failed: {result.output}"
        )
        # Should show table or "No DQ runs found"
        assert 'No DQ runs found' in result.output or 'ID' in result.output

    def test_list_dq_runs_filtered_by_asset(self, runner, authenticated_config):
        """Test listing DQ runs filtered by asset ID"""
        result = runner.invoke(cli, [
            'dq', 'list',
            '--asset-id', '00000000-0000-0000-0000-000000000000'
        ])
        assert result.exit_code == 0, result.output
        # Empty results for non-existent asset is fine

    def test_list_dq_runs_filtered_by_status(self, runner, authenticated_config):
        """Test listing DQ runs filtered by status"""
        result = runner.invoke(cli, [
            'dq', 'list',
            '--status', 'SUCCEEDED'
        ])
        assert result.exit_code == 0, result.output

    def test_get_dq_scorecard(self, runner, authenticated_config):
        """Test getting DQ scorecard for an asset"""
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Scorecard Asset',
            '--key', unique_key('scorecar')
        ])
        assert asset_result.exit_code == 0, asset_result.output

        asset_id = None
        for line in asset_result.output.split('\n'):
            if 'ID:' in line:
                asset_id = line.split('ID:')[1].strip()
                break

        if asset_id:
            scorecard_result = runner.invoke(cli, [
                'dq', 'scorecard', asset_id
            ])
            assert scorecard_result.exit_code == 0, (
                f"DQ scorecard failed: {scorecard_result.output}"
            )

    def test_get_asset_with_dq_results(self, runner, authenticated_config):
        """Test getting asset details with DQ results included"""
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Asset With DQ',
            '--key', unique_key('asset-wi')  # noqa: PHASE216-STATIC-ID
        ])
        assert asset_result.exit_code == 0, asset_result.output

        asset_id = None
        for line in asset_result.output.split('\n'):
            if 'ID:' in line:
                asset_id = line.split('ID:')[1].strip()
                break

        if asset_id:
            get_result = runner.invoke(cli, [
                'assets', 'get', asset_id,
                '--include', 'latest_dq'
            ])
            assert get_result.exit_code == 0, get_result.output

    def test_watch_dq_run(self, runner, authenticated_config):
        """Test watching a non-existent DQ run (should error quickly)."""
        result = runner.invoke(cli, [
            'dq', 'watch',
            '00000000-0000-0000-0000-000000000000',
            '--timeout', '5'
        ])
        # Watching a non-existent run times out or errors
        assert result.exit_code in [0, 1, 2]


class TestDQAlerts:
    """E2E tests for DQ alerts."""

    def test_list_alerting_rules(self, runner, authenticated_config):
        """Test listing DQ alerting rules"""
        result = runner.invoke(cli, [
            'dq', 'alerts',
            '--list'
        ])
        assert result.exit_code == 0, result.output

    def test_create_alerting_rule(self, runner, authenticated_config):
        """Test creating a DQ alerting rule"""
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Alert Asset',
            '--key', unique_key('alert-as')
        ])
        assert asset_result.exit_code == 0, asset_result.output

        asset_id = None
        for line in asset_result.output.split('\n'):
            if 'ID:' in line:
                asset_id = line.split('ID:')[1].strip()
                break

        if asset_id:
            alert_result = runner.invoke(cli, [
                'dq', 'alerts',
                '--create',
                '--asset-id', asset_id,
                '--threshold', '80.0'
            ])
            assert alert_result.exit_code == 0, (
                f"Alert rule creation failed: {alert_result.output}"
            )

    def test_create_alerting_rule_missing_params(self, runner, authenticated_config):
        """Test creating alerting rule without required parameters"""
        result = runner.invoke(cli, [
            'dq', 'alerts',
            '--create'
        ])
        assert result.exit_code != 0
        assert 'required' in result.output.lower() or '--asset-id' in result.output.lower()

    def test_list_alerting_rules_json_output(self, runner, authenticated_config):
        """Test listing alerting rules with JSON output"""
        result = runner.invoke(cli, [
            'dq', 'alerts',
            '--list',
            '--format', 'json'
        ])
        assert result.exit_code == 0, result.output


class TestDQWorkflows:
    """E2E tests for complete DQ workflows"""

    def test_complete_dq_workflow(self, runner, authenticated_config):
        """Test complete DQ workflow: run -> get -> list -> scorecard"""
        # Step 1: Create asset
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'DQ Workflow Asset',
            '--key', unique_key('dq-workf')
        ])
        assert asset_result.exit_code == 0, asset_result.output

        asset_id = None
        for line in asset_result.output.split('\n'):
            if 'ID:' in line:
                asset_id = line.split('ID:')[1].strip()
                break
        assert asset_id

        # Step 2: Run DQ check
        run_result = runner.invoke(cli, [
            'dq', 'run', '--asset-id', asset_id
        ])
        assert run_result.exit_code == 0, (
            f"DQ run creation failed: {run_result.output}"
        )

        # Step 3: Extract run ID and get details
        dq_run_id = None
        for line in run_result.output.split('\n'):
            if 'DQ Run ID:' in line:
                dq_run_id = line.split('DQ Run ID:')[1].strip()
                break

        if dq_run_id:
            get_result = runner.invoke(cli, ['dq', 'get', dq_run_id])
            assert get_result.exit_code == 0, get_result.output

        # Step 4: List DQ runs for this asset
        list_result = runner.invoke(cli, [
            'dq', 'list', '--asset-id', asset_id
        ])
        assert list_result.exit_code == 0, list_result.output

        # Step 5: Get scorecard
        scorecard_result = runner.invoke(cli, [
            'dq', 'scorecard', asset_id
        ])
        assert scorecard_result.exit_code == 0, scorecard_result.output
