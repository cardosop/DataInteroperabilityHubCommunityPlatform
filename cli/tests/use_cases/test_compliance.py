"""
Comprehensive E2E tests for Compliance Use Cases.

Tests compliance checks (on dataset, on asset, with custom rules),
compliance reporting (LGPD, GDPR, HIPAA, CCPA, SOX), and access requests
(create, approve, reject).
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import Config
from datahub_cli.auth import AuthManager


@pytest.fixture
def runner():
    """Create a CLI runner"""
    return CliRunner()


@pytest.fixture
def api_base_url():
    """Get API base URL from environment or use default"""
    return os.getenv('DATAHUB_API_BASE_URL', 'http://localhost:8000/api/v1')


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory"""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    
    # Patch the config paths at module level
    monkeypatch.setattr('datahub_cli.config.CONFIG_DIR', config_dir)
    monkeypatch.setattr('datahub_cli.config.CONFIG_FILE', config_file)
    
    return config_dir, config_file


class TestComplianceChecks:
    """E2E tests for compliance check execution"""
    
    def test_run_compliance_check_on_asset(self, runner, temp_config_dir, api_base_url):
        """Test running compliance check on an asset"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # First create an asset
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Compliance Test Asset',
            '--key', 'compliance-test-asset-key'
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
                # Run compliance check on asset
                compliance_result = runner.invoke(cli, [
                    'compliance', 'run',
                    '--asset-id', asset_id,
                    '--scan-mode', 'internal'
                ])
                
                assert compliance_result.exit_code == 0
                if compliance_result.exit_code == 0:
                    assert 'started successfully' in compliance_result.output.lower()
                    assert 'Compliance Run ID:' in compliance_result.output
                    assert 'Job ID:' in compliance_result.output
    
    def test_run_compliance_check_on_dataset(self, runner, temp_config_dir, api_base_url):
        """Test running compliance check on a dataset"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Try to run compliance check (may fail if dataset doesn't exist, which is OK)
        compliance_result = runner.invoke(cli, [
            'compliance', 'run',
            '--dataset-id', '00000000-0000-0000-0000-000000000000',
            '--scan-mode', 'internal'
        ])
        
        # Should either succeed or fail gracefully
        assert compliance_result.exit_code == 0
        if compliance_result.exit_code == 0:
            assert 'started successfully' in compliance_result.output.lower()
    
    def test_run_compliance_check_with_custom_regulations(self, runner, temp_config_dir, api_base_url):
        """Test running compliance check with custom regulations"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Custom Regulations Asset',
            '--key', 'custom-regulations-asset-key'
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
                # Run compliance check with specific regulations
                compliance_result = runner.invoke(cli, [
                    'compliance', 'run',
                    '--asset-id', asset_id,
                    '--regulations', 'GDPR,HIPAA',
                    '--scan-mode', 'internal'
                ])
                
                assert compliance_result.exit_code == 0
                if compliance_result.exit_code == 0:
                    assert 'started successfully' in compliance_result.output.lower()
                    assert 'Regulations: GDPR,HIPAA' in compliance_result.output
    
    def test_run_compliance_check_external_scan_only(self, runner, temp_config_dir, api_base_url):
        """Test running external scan-only compliance check"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create a test file first
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write('name,email\nJohn Doe,john@example.com\n')
            temp_file = f.name
        
        try:
            # Upload file
            upload_result = runner.invoke(cli, [
                'files', 'upload',
                temp_file
            ])
            
            assert upload_result.exit_code == 0
            if upload_result.exit_code == 0:
                # Extract file ID from output
                file_id = None
                output_lines = upload_result.output.split('\n')
                for line in output_lines:
                    if 'ID:' in line or '"id"' in line.lower():
                        # Try to extract ID
                        if 'ID:' in line:
                            file_id = line.split('ID:')[1].strip()
                        elif '"id"' in line.lower():
                            # JSON output
                            try:
                                json_output = json.loads(upload_result.output)
                                if isinstance(json_output, dict):
                                    file_id = json_output.get('id')
                            except:
                                pass
                        break
                
                if file_id:
                    # Run external scan-only compliance check
                    compliance_result = runner.invoke(cli, [
                        'compliance', 'run',
                        '--file-id', file_id,
                        '--scan-mode', 'external'
                    ])
                    
                    assert compliance_result.exit_code == 0
                    if compliance_result.exit_code == 0:
                        assert 'started successfully' in compliance_result.output.lower()
                        assert 'Scan Mode: external' in compliance_result.output
        finally:
            Path(temp_file).unlink(missing_ok=True)
    
    def test_run_compliance_check_no_resource_id(self, runner, temp_config_dir, api_base_url):
        """Test running compliance check without providing resource ID"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'compliance', 'run',
            '--scan-mode', 'internal'
        ])
        
        assert result.exit_code != 0
        assert 'at least one' in result.output.lower() or 'required' in result.output.lower()
    
    def test_get_compliance_run_results(self, runner, temp_config_dir, api_base_url):
        """Test getting compliance run results"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Try to get a compliance run (may fail if ID doesn't exist, which is OK)
        result = runner.invoke(cli, [
            'compliance', 'get',
            '00000000-0000-0000-0000-000000000000'
        ])
        
        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'Compliance Run ID:' in result.output or 'id' in result.output.lower()
    
    def test_list_compliance_runs(self, runner, temp_config_dir, api_base_url):
        """Test listing compliance runs"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'compliance', 'list',
            '--limit', '10'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            # Should either show runs or "No compliance runs found"
            assert 'compliance run' in result.output.lower() or 'found' in result.output.lower()
    
    def test_list_compliance_runs_filtered_by_asset(self, runner, temp_config_dir, api_base_url):
        """Test listing compliance runs filtered by asset"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'compliance', 'list',
            '--asset-id', '00000000-0000-0000-0000-000000000000',
            '--limit', '10'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            # Should either show runs or "No compliance runs found"
            assert 'compliance run' in result.output.lower() or 'found' in result.output.lower()
    
    def test_list_compliance_runs_filtered_by_status(self, runner, temp_config_dir, api_base_url):
        """Test listing compliance runs filtered by status"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'compliance', 'list',
            '--status', 'COMPLETED',
            '--limit', '10'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            # Should either show runs or "No compliance runs found"
            assert 'compliance run' in result.output.lower() or 'found' in result.output.lower()


class TestComplianceReporting:
    """E2E tests for compliance reporting"""
    
    def test_generate_gdpr_report(self, runner, temp_config_dir, api_base_url):
        """Test generating GDPR compliance report"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'GDPR Report Asset',
            '--key', 'gdpr-report-asset-key'
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
                # Generate GDPR report
                report_result = runner.invoke(cli, [
                    'compliance', 'report',
                    '--asset-id', asset_id,
                    '--regulation', 'GDPR'
                ])
                
                assert report_result.exit_code == 0
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert 'GDPR' in report_result.output or 'compliance run' in report_result.output.lower()
    
    def test_generate_hipaa_report(self, runner, temp_config_dir, api_base_url):
        """Test generating HIPAA compliance report"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'HIPAA Report Asset',
            '--key', 'hipaa-report-asset-key'
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
                # Generate HIPAA report
                report_result = runner.invoke(cli, [
                    'compliance', 'report',
                    '--asset-id', asset_id,
                    '--regulation', 'HIPAA'
                ])
                
                assert report_result.exit_code == 0
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert 'HIPAA' in report_result.output or 'compliance run' in report_result.output.lower()
    
    def test_generate_sox_report(self, runner, temp_config_dir, api_base_url):
        """Test generating SOX compliance report"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'SOX Report Asset',
            '--key', 'sox-report-asset-key'
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
                # Generate SOX report
                report_result = runner.invoke(cli, [
                    'compliance', 'report',
                    '--asset-id', asset_id,
                    '--regulation', 'SOX'
                ])
                
                assert report_result.exit_code == 0
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert 'SOX' in report_result.output or 'compliance run' in report_result.output.lower()
    
    def test_generate_lgpd_report(self, runner, temp_config_dir, api_base_url):
        """Test generating LGPD compliance report"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'LGPD Report Asset',
            '--key', 'lgpd-report-asset-key'
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
                # Generate LGPD report
                report_result = runner.invoke(cli, [
                    'compliance', 'report',
                    '--asset-id', asset_id,
                    '--regulation', 'LGPD'
                ])
                
                assert report_result.exit_code == 0
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert 'LGPD' in report_result.output or 'compliance run' in report_result.output.lower()
    
    def test_generate_ccpa_report(self, runner, temp_config_dir, api_base_url):
        """Test generating CCPA compliance report"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'CCPA Report Asset',
            '--key', 'ccpa-report-asset-key'
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
                # Generate CCPA report
                report_result = runner.invoke(cli, [
                    'compliance', 'report',
                    '--asset-id', asset_id,
                    '--regulation', 'CCPA'
                ])
                
                assert report_result.exit_code == 0
                if report_result.exit_code == 0:
                    # Should show report or indicate no compliance runs
                    assert 'CCPA' in report_result.output or 'compliance run' in report_result.output.lower()
    
    def test_generate_report_missing_asset_id(self, runner, temp_config_dir, api_base_url):
        """Test generating compliance report without asset ID"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'compliance', 'report',
            '--regulation', 'GDPR'
        ])
        
        assert result.exit_code != 0
        assert 'required' in result.output.lower() or 'asset-id' in result.output.lower()


class TestAccessRequests:
    """E2E tests for access request management"""
    
    def test_create_access_request_for_asset(self, runner, temp_config_dir, api_base_url):
        """Test creating access request for an asset"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Access Request Asset',
            '--key', 'access-request-asset-key'
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
                # Create access request
                request_result = runner.invoke(cli, [
                    'governance', 'access-request', 'create',
                    '--asset-id', asset_id,
                    '--reason', 'Need access for data analysis',
                    '--access-type', 'READ'
                ])
                
                assert request_result.exit_code == 0
                if request_result.exit_code == 0:
                    assert 'created successfully' in request_result.output.lower()
                    assert 'Access Request ID:' in request_result.output
    
    def test_create_access_request_missing_reason(self, runner, temp_config_dir, api_base_url):
        """Test creating access request without reason"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'governance', 'access-request', 'create',
            '--asset-id', '00000000-0000-0000-0000-000000000000'
        ])
        
        assert result.exit_code != 0
        assert 'required' in result.output.lower() or 'reason' in result.output.lower()
    
    def test_create_access_request_no_resource_id(self, runner, temp_config_dir, api_base_url):
        """Test creating access request without resource ID"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'governance', 'access-request', 'create',
            '--reason', 'Test reason'
        ])
        
        assert result.exit_code != 0
        assert 'at least one' in result.output.lower() or 'required' in result.output.lower()
    
    def test_get_access_request(self, runner, temp_config_dir, api_base_url):
        """Test getting access request details"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Try to get an access request (may fail if ID doesn't exist, which is OK)
        result = runner.invoke(cli, [
            'governance', 'access-request', 'get',
            '00000000-0000-0000-0000-000000000000'
        ])
        
        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'Access Request ID:' in result.output or 'id' in result.output.lower()
    
    def test_list_access_requests(self, runner, temp_config_dir, api_base_url):
        """Test listing access requests"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'governance', 'access-request', 'list',
            '--limit', '10'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            # Should either show requests or "No access requests found"
            assert 'access request' in result.output.lower() or 'found' in result.output.lower()
    
    def test_list_access_requests_filtered_by_status(self, runner, temp_config_dir, api_base_url):
        """Test listing access requests filtered by status"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'governance', 'access-request', 'list',
            '--status', 'PENDING',
            '--limit', '10'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            # Should either show requests or "No access requests found"
            assert 'access request' in result.output.lower() or 'found' in result.output.lower()
    
    def test_approve_access_request(self, runner, temp_config_dir, api_base_url):
        """Test approving an access request"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Try to approve an access request (may fail if ID doesn't exist or not pending, which is OK)
        result = runner.invoke(cli, [
            'governance', 'access-request', 'approve',
            '00000000-0000-0000-0000-000000000000'
        ])
        
        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'approved successfully' in result.output.lower()
    
    def test_reject_access_request(self, runner, temp_config_dir, api_base_url):
        """Test rejecting an access request"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Try to reject an access request (may fail if ID doesn't exist or not pending, which is OK)
        result = runner.invoke(cli, [
            'governance', 'access-request', 'reject',
            '00000000-0000-0000-0000-000000000000',
            '--reason', 'Access denied due to policy violation'
        ])
        
        # Should either succeed or fail gracefully
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'rejected successfully' in result.output.lower()
    
    def test_reject_access_request_missing_reason(self, runner, temp_config_dir, api_base_url):
        """Test rejecting access request without reason"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'governance', 'access-request', 'reject',
            '00000000-0000-0000-0000-000000000000'
        ])
        
        assert result.exit_code != 0
        assert 'required' in result.output.lower() or 'reason' in result.output.lower()


class TestCompleteComplianceWorkflow:
    """E2E tests for complete compliance workflows"""
    
    def test_complete_compliance_workflow(self, runner, temp_config_dir, api_base_url):
        """Test complete compliance workflow: create asset, run check, generate report"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Complete Workflow Asset',
            '--key', 'complete-workflow-asset-key'
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
                # Run compliance check
                compliance_result = runner.invoke(cli, [
                    'compliance', 'run',
                    '--asset-id', asset_id,
                    '--regulations', 'GDPR,HIPAA',
                    '--scan-mode', 'internal'
                ])
                
                assert compliance_result.exit_code == 0
                
                # List compliance runs
                list_result = runner.invoke(cli, [
                    'compliance', 'list',
                    '--asset-id', asset_id
                ])
                
                assert list_result.exit_code == 0
                
                # Generate report (may fail if compliance run not completed yet, which is OK)
                report_result = runner.invoke(cli, [
                    'compliance', 'report',
                    '--asset-id', asset_id,
                    '--regulation', 'GDPR'
                ])
                
                assert report_result.exit_code == 0

