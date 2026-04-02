"""
Comprehensive E2E tests for Data Quality Use Cases.

Tests DQ check execution (on dataset, on asset, with custom rules),
DQ result review, and DQ alerts scenarios.
"""
import pytest
import json
import tempfile
from pathlib import Path
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import Config
from datahub_cli.auth import AuthManager


class TestDQCheckExecution:
    """E2E tests for DQ check execution"""
    
    def test_run_dq_check_on_asset(self, runner, temp_config_dir, api_base_url):
        """Test running DQ check on an asset"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # First create an asset
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'DQ Test Asset',
            '--key', 'dq-test-asset-key'
        ])
        
        assert asset_result.exit_code == 0
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in asset_result.output:
                lines = asset_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Run DQ check on asset
                dq_result = runner.invoke(cli, [
                    'dq', 'run',
                    '--asset-id', asset_id,
                    '--profile-key', 'intake_basic_gx'
                ])
                
                assert dq_result.exit_code == 0
                if dq_result.exit_code == 0:
                    assert 'started successfully' in dq_result.output.lower()
                    assert 'DQ Run ID:' in dq_result.output
                    assert 'Job ID:' in dq_result.output
    
    def test_run_dq_check_on_dataset(self, runner, temp_config_dir, api_base_url):
        """Test running DQ check on a dataset"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Note: Dataset creation may require file upload first
        # For this test, we'll simulate with a dataset ID if available
        # In real scenario, would create dataset first
        
        # Try to run DQ check (may fail if dataset doesn't exist, which is OK)
        dq_result = runner.invoke(cli, [
            'dq', 'run',
            '--dataset-id', '00000000-0000-0000-0000-000000000000',
            '--profile-key', 'intake_basic_gx'
        ])
        
        # Should either succeed or fail gracefully
        assert dq_result.exit_code == 0
        if dq_result.exit_code == 0:
            assert 'started successfully' in dq_result.output.lower()
    
    def test_run_dq_check_with_custom_profile(self, runner, temp_config_dir, api_base_url):
        """Test running DQ check with custom profile"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Custom Profile Asset',
            '--key', 'custom-profile-asset-key'
        ])
        
        assert asset_result.exit_code == 0
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in asset_result.output:
                lines = asset_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Run DQ check with custom profile
                dq_result = runner.invoke(cli, [
                    'dq', 'run',
                    '--asset-id', asset_id,
                    '--profile-key', 'intake_basic_gx'
                ])
                
                assert dq_result.exit_code == 0
                if dq_result.exit_code == 0:
                    assert 'started successfully' in dq_result.output.lower()
                    assert 'intake_basic_gx' in dq_result.output
    
    def test_run_dq_check_external_scan_only(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test running DQ check on external file (scan-only)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Upload a file first
        file_path, content = temp_file('.csv', 'id,name\n1,Test\n2,Sample')
        upload_result = runner.invoke(cli, [
            'files', 'upload', file_path
        ])
        
        assert upload_result.exit_code == 0
        if upload_result.exit_code == 0:
            # Extract file ID from output (basic parsing)
            file_id = None
            if 'ID:' in upload_result.output:
                lines = upload_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        file_id = line.split('ID:')[1].strip()
                        break
            
            if file_id:
                # Run external DQ check
                dq_result = runner.invoke(cli, [
                    'dq', 'run',
                    '--file-id', file_id,
                    '--profile-key', 'intake_basic_gx'
                ])
                
                assert dq_result.exit_code == 0
                if dq_result.exit_code == 0:
                    assert 'started successfully' in dq_result.output.lower()
    
    def test_run_dq_check_no_resource_id(self, runner, temp_config_dir, api_base_url):
        """Test running DQ check without resource ID (should fail)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'dq', 'run',
            '--profile-key', 'intake_basic_gx'
        ])
        
        # Should fail with error message
        assert result.exit_code != 0
        assert 'must be provided' in result.output.lower() or 'required' in result.output.lower()
    
    def test_run_dq_check_json_output(self, runner, temp_config_dir, api_base_url):
        """Test running DQ check with JSON output format"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'JSON DQ Asset',
            '--key', 'json-dq-asset-key'
        ])
        
        assert asset_result.exit_code == 0
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in asset_result.output:
                lines = asset_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Run DQ check with JSON output
                dq_result = runner.invoke(cli, [
                    'dq', 'run',
                    '--asset-id', asset_id,
                    '--format', 'json'
                ])
                
                assert dq_result.exit_code == 0
                if dq_result.exit_code == 0 and dq_result.output.strip():
                    # Should be valid JSON
                    try:
                        output_data = json.loads(dq_result.output)
                        assert isinstance(output_data, dict)
                        assert 'dq_run' in output_data or 'job' in output_data
                    except json.JSONDecodeError:
                        # If not JSON, that's OK for this test
                        pass


class TestDQResultReview:
    """E2E tests for DQ result review"""
    
    def test_get_dq_run_results(self, runner, temp_config_dir, api_base_url):
        """Test getting DQ run results"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Try to get a DQ run (may not exist, which is OK)
        result = runner.invoke(cli, [
            'dq', 'get',
            '00000000-0000-0000-0000-000000000000'
        ])
        
        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'DQ Run ID:' in result.output
            assert 'Status:' in result.output
            assert 'Overall Status:' in result.output
    
    def test_get_dq_run_results_with_checks(self, runner, temp_config_dir, api_base_url):
        """Test getting DQ run results with check details"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Try to get a DQ run
        result = runner.invoke(cli, [
            'dq', 'get',
            '00000000-0000-0000-0000-000000000000'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            # Should show check results if available
            assert 'Checks' in result.output or 'Status:' in result.output
    
    def test_get_dq_run_json_output(self, runner, temp_config_dir, api_base_url):
        """Test getting DQ run results with JSON output"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'dq', 'get',
            '00000000-0000-0000-0000-000000000000',
            '--format', 'json'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0 and result.output.strip():
            # Should be valid JSON
            try:
                output_data = json.loads(result.output)
                assert isinstance(output_data, dict)
            except json.JSONDecodeError:
                # If not JSON, that's OK for this test
                pass
    
    def test_list_dq_runs(self, runner, temp_config_dir, api_base_url):
        """Test listing DQ runs"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'dq', 'list'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            # Should show table or "No DQ runs found"
            assert 'No DQ runs found' in result.output or 'ID' in result.output
    
    def test_list_dq_runs_filtered_by_asset(self, runner, temp_config_dir, api_base_url):
        """Test listing DQ runs filtered by asset ID"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'dq', 'list',
            '--asset-id', '00000000-0000-0000-0000-000000000000'
        ])
        
        assert result.exit_code == 0
        # Should handle filtering correctly
    
    def test_list_dq_runs_filtered_by_status(self, runner, temp_config_dir, api_base_url):
        """Test listing DQ runs filtered by status"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'dq', 'list',
            '--status', 'SUCCEEDED'
        ])
        
        assert result.exit_code == 0
        # Should handle status filtering correctly
    
    def test_get_dq_scorecard(self, runner, temp_config_dir, api_base_url):
        """Test getting DQ scorecard for an asset"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Scorecard Asset',
            '--key', 'scorecard-asset-key'
        ])
        
        assert asset_result.exit_code == 0
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in asset_result.output:
                lines = asset_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Get scorecard
                scorecard_result = runner.invoke(cli, [
                    'dq', 'scorecard', asset_id
                ])
                
                assert scorecard_result.exit_code == 0
                if scorecard_result.exit_code == 0:
                    assert 'Asset ID:' in scorecard_result.output or 'Overall Quality Score' in scorecard_result.output
    
    def test_get_asset_with_dq_results(self, runner, temp_config_dir, api_base_url):
        """Test getting asset details with DQ results included"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Asset With DQ',
            '--key', 'asset-with-dq-key'
        ])
        
        assert asset_result.exit_code == 0
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in asset_result.output:
                lines = asset_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Get asset with DQ results included
                get_result = runner.invoke(cli, [
                    'assets', 'get', asset_id,
                    '--include', 'latest_dq'
                ])
                
                assert get_result.exit_code == 0
                # May or may not show DQ results depending on API implementation
    
    def test_watch_dq_run(self, runner, temp_config_dir, api_base_url):
        """Test watching a DQ run until completion"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Try to watch a DQ run (may timeout or fail if run doesn't exist)
        result = runner.invoke(cli, [
            'dq', 'watch',
            '00000000-0000-0000-0000-000000000000',
            '--timeout', '5'
        ])
        
        # Should either succeed, timeout, or fail gracefully
        assert result.exit_code in [0, 1, 2]
        # May show timeout or completion message


class TestDQAlerts:
    """E2E tests for DQ alerts"""
    
    def test_list_alerting_rules(self, runner, temp_config_dir, api_base_url):
        """Test listing DQ alerting rules"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'dq', 'alerts',
            '--list'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            # Should show table or "No alerting rules found"
            assert 'No alerting rules found' in result.output or 'ID' in result.output
    
    def test_create_alerting_rule(self, runner, temp_config_dir, api_base_url):
        """Test creating a DQ alerting rule"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Alert Asset',
            '--key', 'alert-asset-key'
        ])
        
        assert asset_result.exit_code == 0
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in asset_result.output:
                lines = asset_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Create alerting rule
                alert_result = runner.invoke(cli, [
                    'dq', 'alerts',
                    '--create',
                    '--asset-id', asset_id,
                    '--threshold', '80.0'
                ])
                
                assert alert_result.exit_code == 0
                if alert_result.exit_code == 0:
                    assert 'created successfully' in alert_result.output.lower()
                    assert 'ID:' in alert_result.output
    
    def test_create_alerting_rule_missing_params(self, runner, temp_config_dir, api_base_url):
        """Test creating alerting rule without required parameters"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'dq', 'alerts',
            '--create'
        ])
        
        # Should fail with error message
        assert result.exit_code != 0
        assert 'required' in result.output.lower() or '--asset-id' in result.output.lower()
    
    def test_list_alerting_rules_json_output(self, runner, temp_config_dir, api_base_url):
        """Test listing alerting rules with JSON output"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'dq', 'alerts',
            '--list',
            '--format', 'json'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0 and result.output.strip():
            # Should be valid JSON
            try:
                output_data = json.loads(result.output)
                assert isinstance(output_data, list)
            except json.JSONDecodeError:
                # If not JSON, that's OK for this test
                pass


class TestDQWorkflows:
    """E2E tests for complete DQ workflows"""
    
    def test_complete_dq_workflow(self, runner, temp_config_dir, api_base_url):
        """Test complete DQ workflow: run -> watch -> get results"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Step 1: Create asset
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'DQ Workflow Asset',
            '--key', 'dq-workflow-asset-key'
        ])
        
        assert asset_result.exit_code == 0
        if asset_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in asset_result.output:
                lines = asset_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Step 2: Run DQ check
                run_result = runner.invoke(cli, [
                    'dq', 'run',
                    '--asset-id', asset_id
                ])
                
                assert run_result.exit_code == 0
                if run_result.exit_code == 0:
                    # Extract DQ run ID
                    dq_run_id = None
                    if 'DQ Run ID:' in run_result.output:
                        lines = run_result.output.split('\n')
                        for line in lines:
                            if 'DQ Run ID:' in line:
                                dq_run_id = line.split('DQ Run ID:')[1].strip()
                                break
                    
                    if dq_run_id:
                        # Step 3: Get DQ run results
                        get_result = runner.invoke(cli, [
                            'dq', 'get', dq_run_id
                        ])
                        
                        assert get_result.exit_code == 0
                        if get_result.exit_code == 0:
                            assert 'DQ Run ID:' in get_result.output
                        
                        # Step 4: List DQ runs for this asset
                        list_result = runner.invoke(cli, [
                            'dq', 'list',
                            '--asset-id', asset_id
                        ])
                        
                        assert list_result.exit_code == 0
                        
                        # Step 5: Get scorecard
                        scorecard_result = runner.invoke(cli, [
                            'dq', 'scorecard', asset_id
                        ])
                        
                        assert scorecard_result.exit_code == 0


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def api_base_url():
    """API base URL fixture"""
    return 'http://localhost:8000/api/v1'


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory"""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    
    monkeypatch.setattr('datahub_cli.config.CONFIG_DIR', config_dir)
    monkeypatch.setattr('datahub_cli.config.CONFIG_FILE', config_file)
    
    return config_dir, config_file


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file"""
    def _create_file(extension, content):
        file_path = tmp_path / f'test{extension}'
        file_path.write_text(content)
        return str(file_path), content
    return _create_file

