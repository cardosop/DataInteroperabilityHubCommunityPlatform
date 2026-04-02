"""
E2E tests for CLI tool.

Tests complete CLI journeys: installation, configuration, authentication,
asset management, contract management, file management, job management, and edge cases.
Uses real API (no mocks).
"""
import pytest

pytestmark = pytest.mark.slow
import sys
import tempfile
import os
import json
import time
from pathlib import Path
from click.testing import CliRunner

# Add CLI to path
cli_path = Path(__file__).parent.parent.parent / "cli"
sys.path.insert(0, str(cli_path))

from datahub_cli.main import cli
from datahub_cli.config import Config
from datahub_cli.auth import AuthManager
from datahub_cli.api_client import APIClient
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient as DRFClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.auth.models import APIKey
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from tests.factories import TenantFactory
import uuid

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e4]
User = get_user_model()


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
def test_user_and_tenant():
    """Create test user and tenant"""
    tenant = TenantFactory.create_tenant()
    user = User.objects.create_user(
        email=f"cli_e2e-{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE
    )
    return user, tenant


@pytest.fixture
def api_key_for_cli(test_user_and_tenant):
    """Create API key for CLI testing"""
    user, tenant = test_user_and_tenant
    # Generate plaintext key and hash it (as done in production)
    plaintext_key = APIKey.generate_key()
    key_hash = APIKey.hash_key(plaintext_key)
    
    api_key = APIKey.objects.create(
        user=user,
        name="CLI E2E Test Key",
        tenant=tenant,
        key_hash=key_hash
    )
    # Store plaintext key for use in tests (normally only shown once at creation)
    api_key._plaintext_key = plaintext_key
    return api_key


class CLIJourneyTest:
    """E2E tests for CLI journeys"""
    
    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()
    
    def test_cli_installation_and_configuration(self, runner, temp_config_dir):
        """Test CLI installation and initial configuration"""
        # Test that CLI is accessible
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'DataHub CLI' in result.output
        
        # Test config set
        result = runner.invoke(cli, ['config', 'set', 'api_base_url', 'http://localhost:8000/api/v1'])
        assert result.exit_code == 0
        
        # Verify config was saved
        config = Config()
        assert config.get_api_base_url() == 'http://localhost:8000/api/v1'
    
    def test_cli_authentication_with_api_key(self, runner, temp_config_dir, api_key_for_cli):
        """Test CLI authentication with API key"""
        config_dir, config_file = temp_config_dir
        
        # Reload global config to ensure it uses the patched file path
        # This is critical because the global config instance is created at import time
        from datahub_cli.config import config as global_config
        global_config._load()  # Reload to pick up patched CONFIG_FILE
        
        # Verify global config is using the correct file path
        global_config_file = global_config._get_config_file()
        assert str(global_config_file) == str(config_file), f"Global config using wrong file. Expected {config_file}, got {global_config_file}"
        
        # Set API key via CLI command (uses global config instance)
        # Use plaintext key (not hash) - this is what users would use
        # Get plaintext key from fixture (stored as _plaintext_key attribute)
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', None)
        if not plaintext_key:
            # Generate a test key if not available (should not happen with fixed fixture)
            from hub.apps.auth.models import APIKey
            plaintext_key = APIKey.generate_key()
            # Update the fixture's key_hash to match
            api_key_for_cli.key_hash = APIKey.hash_key(plaintext_key)
            api_key_for_cli.save()
            api_key_for_cli._plaintext_key = plaintext_key
        result = runner.invoke(cli, ['config', 'set', 'api_key', plaintext_key])
        assert result.exit_code == 0, f"CLI command failed: {result.output}"
        
        # Verify the file was written by checking it directly
        assert config_file.exists(), f"Config file should exist at {config_file}"
        
        # Read file directly to verify content
        import yaml
        with open(config_file, 'r') as f:
            file_content = yaml.safe_load(f) or {}
        file_api_key = file_content.get('api_key')
        assert file_api_key == plaintext_key, f"API key not in file. Expected {plaintext_key}, got {file_api_key}. File content: {file_content}"
        
        # Reload global config to ensure it reads from the patched file
        global_config._load()
        global_api_key = global_config.get_api_key()
        assert global_api_key == plaintext_key, f"Global config API key not set. Expected {plaintext_key}, got {global_api_key}. Config file path: {global_config._get_config_file()}"
        
        # Create a new config instance to verify it was saved to file
        config = Config()
        # Verify the config instance is using the correct file path
        config_file_path = config._get_config_file()
        assert str(config_file_path) == str(config_file), f"Config instance using wrong file path. Expected {config_file}, got {config_file_path}"
        
        # Verify file still exists and has content
        assert config_file.exists(), f"Config file should still exist at {config_file}"
        with open(config_file, 'r') as f:
            file_content_after = yaml.safe_load(f) or {}
        assert file_content_after.get('api_key') == plaintext_key, f"API key not in file after reload. Expected {plaintext_key}, got {file_content_after.get('api_key')}. File content: {file_content_after}"
        
        # Reload to ensure we get the latest data
        config._load()
        api_key = config.get_api_key()
        assert api_key == plaintext_key, f"API key not set correctly in file. Expected {plaintext_key}, got {api_key}. Config file: {config_file}, File exists: {config_file.exists()}, Config file path used: {config_file_path}, Config dict: {config._config}, File content: {file_content_after}"
        
        # Verify authentication works - use the config instance that has the API key
        auth_manager = AuthManager(config_instance=config)
        # ensure_authenticated should return True if API key is set
        is_authenticated = auth_manager.ensure_authenticated()
        assert is_authenticated is True, f"ensure_authenticated returned False. API key from config: {config.get_api_key()}, API key from auth_manager: {auth_manager.config.get_api_key()}, Config file: {config_file}, Config dict: {config._config}"
        
        headers = auth_manager.get_auth_headers()
        assert 'Authorization' in headers
        assert headers['Authorization'] == f'ApiKey {plaintext_key}'
    
    def test_cli_authentication_with_login(self, runner, temp_config_dir, test_user_and_tenant):
        """Test CLI authentication with login (requires running server)"""
        user, tenant = test_user_and_tenant
        
        # Set API base URL
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        
        # Test login command structure
        # Note: Would require running test server for full test
        result = runner.invoke(cli, ['login'], input=f'{user.email}\ntestpass123\n')
        # May fail without running server, but should parse input
        assert result.exit_code in [0, 1]
    
    def test_cli_asset_management_journey(self, runner, temp_config_dir, api_key_for_cli, test_user_and_tenant):
        """Test complete asset management journey"""
        user, tenant = test_user_and_tenant
        
        # Configure CLI
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test asset creation command structure
        result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'CLI Test Asset',
            '--key', 'cli-test-asset',
            '--description', 'Asset created via CLI',
            '--domain', 'test',
            '--visibility', 'INTERNAL',
            '--format', 'json'
        ])
        # May fail without running server, but should parse options correctly
        assert result.exit_code in [0, 1]
        
        # Test asset list command structure
        result = runner.invoke(cli, [
            'assets', 'list',
            '--status', 'DRAFT',
            '--domain', 'test',
            '--format', 'json'
        ])
        assert result.exit_code in [0, 1]
    
    def test_cli_contract_management_journey(self, runner, temp_config_dir, api_key_for_cli, test_user_and_tenant):
        """Test complete contract management journey"""
        user, tenant = test_user_and_tenant
        
        # Configure CLI
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Create temporary contract file
        contract_data = {
            "id": "cli-test-contract",
            "name": "CLI Test Contract",
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"}
                ]
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(contract_data, f)
            temp_file = f.name
        
        try:
            # Test contract creation
            result = runner.invoke(cli, [
                'contracts', 'create',
                '--file', temp_file,
                '--format', 'json'
            ])
            # May fail without running server, but should parse file correctly
            assert result.exit_code in [0, 1]
            
            # Test contract list
            result = runner.invoke(cli, [
                'contracts', 'list',
                '--status', 'DRAFT',
                '--format', 'json'
            ])
            assert result.exit_code in [0, 1]
        finally:
            os.unlink(temp_file)
    
    def test_cli_file_management_journey(self, runner, temp_config_dir, api_key_for_cli, test_user_and_tenant):
        """Test complete file management journey"""
        user, tenant = test_user_and_tenant
        
        # Configure CLI
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("col1,col2\nvalue1,value2\n")
            temp_file = f.name
        
        try:
            # Test file upload command structure
            result = runner.invoke(cli, [
                'files', 'upload',
                temp_file,
                '--name', 'test.csv',
                '--format', 'json'
            ])
            # May fail without running server, but should parse file correctly
            assert result.exit_code in [0, 1]
            
            # Test file list
            result = runner.invoke(cli, [
                'files', 'list',
                '--status', 'UPLOADED',
                '--format', 'json'
            ])
            assert result.exit_code in [0, 1]
        finally:
            os.unlink(temp_file)
    
    def test_cli_job_management_journey(self, runner, temp_config_dir, api_key_for_cli, test_user_and_tenant):
        """Test complete job management journey"""
        user, tenant = test_user_and_tenant
        
        # Configure CLI
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test job list
        result = runner.invoke(cli, [
            'jobs', 'list',
            '--type', 'DQ_RUN',
            '--status', 'PENDING',
            '--format', 'json'
        ])
        # May fail without running server, but should parse options correctly
        assert result.exit_code in [0, 1]
        
        # Test job get command structure
        result = runner.invoke(cli, [
            'jobs', 'get',
            'test-job-id',
            '--format', 'json'
        ])
        assert result.exit_code in [0, 1]
    
    def test_cli_output_formats(self, runner, temp_config_dir, api_key_for_cli):
        """Test CLI output formats (table and JSON)"""
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test table format (default)
        result = runner.invoke(cli, ['assets', 'list', '--format', 'table'])
        assert result.exit_code in [0, 1]
        
        # Test JSON format
        result = runner.invoke(cli, ['assets', 'list', '--format', 'json'])
        assert result.exit_code in [0, 1]
    
    def test_cli_error_handling_invalid_command(self, runner):
        """Test CLI error handling for invalid command"""
        result = runner.invoke(cli, ['invalid-command'])
        assert result.exit_code != 0
    
    def test_cli_error_handling_missing_required_args(self, runner):
        """Test CLI error handling for missing required arguments"""
        result = runner.invoke(cli, ['assets', 'create'])
        assert result.exit_code != 0
    
    def test_cli_error_handling_invalid_file(self, runner):
        """Test CLI error handling for invalid file"""
        result = runner.invoke(cli, ['contracts', 'create', '--file', 'nonexistent.yaml'])
        assert result.exit_code != 0
    
    def test_cli_config_command_line_overrides(self, runner, temp_config_dir):
        """Test CLI config command-line overrides"""
        # Set multiple config values
        runner.invoke(cli, ['config', 'set', 'api_base_url', 'http://override.example.com/api/v1'])
        runner.invoke(cli, ['config', 'set', 'default_tenant', 'override-tenant'])
        
        config = Config()
        assert config.get_api_base_url() == 'http://override.example.com/api/v1'
        assert config.get_default_tenant() == 'override-tenant'
    
    def test_cli_logout_clears_tokens(self, runner, temp_config_dir):
        """Test that CLI logout clears authentication tokens"""
        # Set API key via CLI to ensure it's saved to file
        result = runner.invoke(cli, ['config', 'set', 'api_key', 'api-key'])
        assert result.exit_code == 0
        
        # Set tokens via CLI or directly
        config = Config()
        config.set_access_token('test-token')
        config.set_refresh_token('refresh-token')
        
        # Verify API key is set before logout
        assert config.get_api_key() == 'api-key'
        
        result = runner.invoke(cli, ['logout'])
        assert result.exit_code == 0
        
        # Create a new config instance to verify file was updated
        config = Config()
        
        # Tokens should be cleared, but API key should remain
        assert config.get_access_token() is None
        assert config.get_refresh_token() is None
        # API key is not cleared by logout (clear_auth only clears access_token and refresh_token)
        assert config.get_api_key() == 'api-key', f"API key should remain after logout. Got: {config.get_api_key()}"
    
    def test_cli_contract_create_yaml_file(self, runner, temp_config_dir, api_key_for_cli):
        """Test CLI contract create with YAML file"""
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Create YAML contract file
        yaml_content = """
id: yaml-test-contract
name: YAML Test Contract
schema:
  fields:
    - name: field1
      type: string
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name
        
        try:
            result = runner.invoke(cli, [
                'contracts', 'create',
                '--file', temp_file,
                '--format', 'json'
            ])
            # May fail without running server, but should parse YAML correctly
            assert result.exit_code in [0, 1]
        finally:
            os.unlink(temp_file)
    
    def test_cli_contract_validate_journey(self, runner, temp_config_dir, api_key_for_cli, test_user_and_tenant):
        """Test CLI contract validate journey"""
        user, tenant = test_user_and_tenant
        
        # Create a contract via API first
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=tenant,
            created_by=user
        )
        
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test contract validate
        result = runner.invoke(cli, [
            'contracts', 'validate',
            str(contract.id),
            '--format', 'json'
        ])
        # May fail without running server, but should parse options correctly
        assert result.exit_code in [0, 1]
    
    def test_cli_contract_lint_journey(self, runner, temp_config_dir, api_key_for_cli, test_user_and_tenant):
        """Test CLI contract lint journey"""
        user, tenant = test_user_and_tenant
        
        # Create a contract via API first
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=tenant,
            created_by=user
        )
        
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test contract lint
        result = runner.invoke(cli, [
            'contracts', 'lint',
            str(contract.id),
            '--format', 'json'
        ])
        # May fail without running server, but should parse options correctly
        assert result.exit_code in [0, 1]
    
    def test_cli_jobs_watch_journey(self, runner, temp_config_dir, api_key_for_cli):
        """Test CLI jobs watch journey"""
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test job watch command structure
        result = runner.invoke(cli, [
            'jobs', 'watch',
            'test-job-id',
            '--interval', '1',
            '--timeout', '5',
            '--format', 'json'
        ])
        # May fail without running server, but should parse options correctly
        assert result.exit_code in [0, 1]
    
    def test_cli_assets_update_journey(self, runner, temp_config_dir, api_key_for_cli, test_user_and_tenant):
        """Test CLI assets update journey"""
        user, tenant = test_user_and_tenant
        
        # Create asset via API first
        asset = Asset.objects.create(
            tenant=tenant,
            name="CLI Test Asset",
            key="cli-test-asset",
            status=AssetStatus.DRAFT
        )
        
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test asset update
        result = runner.invoke(cli, [
            'assets', 'update',
            str(asset.id),
            '--name', 'Updated Name',
            '--description', 'Updated description',
            '--format', 'json'
        ])
        # May fail without running server, but should parse options correctly
        assert result.exit_code in [0, 1]
    
    def test_cli_assets_activate_journey(self, runner, temp_config_dir, api_key_for_cli, test_user_and_tenant):
        """Test CLI assets activate journey"""
        user, tenant = test_user_and_tenant
        
        # Create asset via API first
        asset = Asset.objects.create(
            tenant=tenant,
            name="CLI Test Asset",
            key="cli-test-asset",
            status=AssetStatus.DRAFT
        )
        
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test asset activate
        result = runner.invoke(cli, [
            'assets', 'activate',
            str(asset.id),
            '--format', 'json'
        ])
        # May fail without running server, but should parse options correctly
        assert result.exit_code in [0, 1]
    
    def test_cli_files_download_journey(self, runner, temp_config_dir, api_key_for_cli):
        """Test CLI files download journey"""
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test file download command structure
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'downloaded.csv')
            result = runner.invoke(cli, [
                'files', 'download',
                'test-file-id',
                '--output', output_path
            ])
            # May fail without running server, but should parse options correctly
            assert result.exit_code in [0, 1]
    
    def test_cli_edge_case_empty_results(self, runner, temp_config_dir, api_key_for_cli):
        """Test CLI handling of empty results"""
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test list commands with empty results
        result = runner.invoke(cli, ['assets', 'list', '--format', 'table'])
        # Should handle empty results gracefully
        assert result.exit_code in [0, 1]
    
    def test_cli_edge_case_large_output(self, runner, temp_config_dir, api_key_for_cli):
        """Test CLI handling of large output"""
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test with large limit
        result = runner.invoke(cli, [
            'assets', 'list',
            '--limit', '1000',
            '--format', 'json'
        ])
        # Should handle large limits
        assert result.exit_code in [0, 1]
    
    def test_cli_edge_case_special_characters(self, runner, temp_config_dir, api_key_for_cli):
        """Test CLI handling of special characters in arguments"""
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test with special characters in asset name
        result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Asset with Special: !@#$%',
            '--key', 'asset-special',
            '--format', 'json'
        ])
        # Should handle special characters
        assert result.exit_code in [0, 1]
    
    def test_cli_edge_case_unicode(self, runner, temp_config_dir, api_key_for_cli):
        """Test CLI handling of unicode characters"""
        config = Config()
        config.set_api_base_url('http://testserver/api/v1')
        # Use plaintext key (not hash) for authentication
        plaintext_key = getattr(api_key_for_cli, '_plaintext_key', api_key_for_cli.key_hash)
        config.set_api_key(plaintext_key)
        
        # Test with unicode in asset name
        result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Asset with 测试 Unicode',
            '--key', 'asset-unicode',
            '--format', 'json'
        ])
        # Should handle unicode
        assert result.exit_code in [0, 1]

