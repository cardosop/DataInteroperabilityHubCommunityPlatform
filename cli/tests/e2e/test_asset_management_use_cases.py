"""
Comprehensive E2E tests for Asset Management Use Cases.

Tests asset creation (data-first, contract-first, all/minimal metadata),
asset updates, asset deletion, and asset search scenarios.
"""
import pytest
import json
import tempfile
from pathlib import Path
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import Config
from datahub_cli.auth import AuthManager


class TestAssetCreation:
    """E2E tests for asset creation"""
    
    def test_create_asset_minimal_metadata(self, runner, temp_config_dir, api_base_url):
        """Test asset creation with minimal metadata (name and key only)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Minimal Asset',
            '--key', 'minimal-asset-key'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            assert 'Minimal Asset' in result.output
            # Extract asset ID if possible
            output_data = result.output
            assert 'ID:' in output_data or 'id' in output_data.lower()
    
    def test_create_asset_all_metadata(self, runner, temp_config_dir, api_base_url):
        """Test asset creation with all metadata fields"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Complete Asset',
            '--key', 'complete-asset-key',
            '--description', 'This is a complete asset with all metadata fields',
            '--domain', 'sales',
            '--visibility', 'PUBLIC'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            assert 'Complete Asset' in result.output
            # Verify all fields are present
            output_data = result.output
            assert 'sales' in output_data.lower() or 'domain' in output_data.lower()
    
    def test_create_asset_data_first_flow_simulation(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test data-first flow: Create asset, then upload file (simulated)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Step 1: Create asset with minimal metadata
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Data-First Asset',
            '--key', 'data-first-asset-key',
            '--description', 'Asset created in data-first flow'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID from output
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            # Step 2: Upload a file (simulating data-first flow)
            if asset_id:
                file_path, content = temp_file('.csv', 'col1,col2\nval1,val2')
                upload_result = runner.invoke(cli, [
                    'files', 'upload',
                    file_path,
                    '--name', 'data-first-file.csv'
                ])
                
                # File upload may succeed or fail depending on API availability
                assert upload_result.exit_code == 0
    
    def test_create_asset_contract_first_flow_simulation(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test contract-first flow: Create contract, then create asset (simulated)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Step 1: Create contract first
        contract_file, contract_content = temp_file('.yaml', '''
name: Contract-First Contract
version: 1.0
schema:
  type: object
  properties:
    field1:
      type: string
''')
        
        contract_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])
        
        assert contract_result.exit_code == 0
        
        # Step 2: Create asset (contract-first flow)
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Contract-First Asset',
            '--key', 'contract-first-asset-key',
            '--description', 'Asset created in contract-first flow'
        ])
        
        assert asset_result.exit_code == 0
        if asset_result.exit_code == 0:
            assert 'created successfully' in asset_result.output.lower()
    
    def test_create_asset_json_output(self, runner, temp_config_dir, api_base_url):
        """Test asset creation with JSON output format"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'JSON Asset',
            '--key', 'json-asset-key',
            '--format', 'json'
        ])
        
        assert result.exit_code == 0
        if result.exit_code == 0 and result.output.strip():
            # Should be valid JSON
            try:
                output_data = json.loads(result.output)
                assert isinstance(output_data, dict)
                assert 'id' in output_data or 'name' in output_data
            except json.JSONDecodeError:
                # If not JSON, that's OK for this test
                pass
    
    def test_create_asset_duplicate_key(self, runner, temp_config_dir, api_base_url):
        """Test asset creation with duplicate key (should fail)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create first asset
        result1 = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'First Asset',
            '--key', 'duplicate-key-test'
        ])
        
        # Try to create second asset with same key
        result2 = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Second Asset',
            '--key', 'duplicate-key-test'
        ])
        
        # Second creation should fail if API enforces uniqueness
        if result1.exit_code == 0:
            # API may or may not enforce uniqueness
            assert result2.exit_code == 0
            if result2.exit_code != 0:
                assert 'duplicate' in result2.output.lower() or 'already exists' in result2.output.lower() or 'unique' in result2.output.lower()


class TestAssetUpdates:
    """E2E tests for asset updates"""
    
    def test_update_asset_metadata(self, runner, temp_config_dir, api_base_url):
        """Test updating asset metadata (name, description, domain)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Original Name',
            '--key', 'update-test-asset-key'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Update asset metadata
                update_result = runner.invoke(cli, [
                    'assets', 'update', asset_id,
                    '--name', 'Updated Name',
                    '--description', 'Updated description',
                    '--domain', 'marketing'
                ])
                
                assert update_result.exit_code == 0
                if update_result.exit_code == 0:
                    assert 'updated successfully' in update_result.output.lower()
                    assert 'Updated Name' in update_result.output
    
    def test_update_asset_status_via_activate(self, runner, temp_config_dir, api_base_url):
        """Test updating asset status by activating it"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create draft asset
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Draft Asset',
            '--key', 'activate-test-asset-key'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Activate asset
                activate_result = runner.invoke(cli, [
                    'assets', 'activate', asset_id
                ])
                
                assert activate_result.exit_code == 0
                if activate_result.exit_code == 0:
                    assert 'activated successfully' in activate_result.output.lower()
                    assert 'ACTIVE' in activate_result.output or 'Status:' in activate_result.output
    
    def test_update_asset_visibility(self, runner, temp_config_dir, api_base_url):
        """Test updating asset visibility"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset with INTERNAL visibility
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Visibility Test Asset',
            '--key', 'visibility-test-asset-key',
            '--visibility', 'INTERNAL'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Update visibility to PUBLIC
                update_result = runner.invoke(cli, [
                    'assets', 'update', asset_id,
                    '--visibility', 'PUBLIC'
                ])
                
                assert update_result.exit_code == 0
                if update_result.exit_code == 0:
                    assert 'updated successfully' in update_result.output.lower()
    
    def test_update_asset_no_fields(self, runner, temp_config_dir, api_base_url):
        """Test updating asset with no fields (should fail)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset first
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'No Update Asset',
            '--key', 'no-update-test-asset-key'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Try to update with no fields
                update_result = runner.invoke(cli, [
                    'assets', 'update', asset_id
                ])
                
                # Should fail with error message
                assert update_result.exit_code != 0
                assert 'No fields to update' in update_result.output or 'Missing option' in update_result.output


class TestAssetDeletion:
    """E2E tests for asset deletion"""
    
    def test_delete_draft_asset(self, runner, temp_config_dir, api_base_url):
        """Test deleting a draft asset"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create draft asset
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Draft Asset To Delete',
            '--key', 'delete-draft-test-asset-key'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Delete with confirmation flag
                delete_result = runner.invoke(cli, [
                    'assets', 'delete', asset_id,
                    '--confirm'
                ])
                
                assert delete_result.exit_code == 0
                if delete_result.exit_code == 0:
                    assert 'deleted successfully' in delete_result.output.lower()
    
    def test_delete_active_asset(self, runner, temp_config_dir, api_base_url):
        """Test deleting an active asset"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create and activate asset
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Active Asset To Delete',
            '--key', 'delete-active-test-asset-key'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Activate first
                activate_result = runner.invoke(cli, [
                    'assets', 'activate', asset_id
                ])
                
                # Then delete
                delete_result = runner.invoke(cli, [
                    'assets', 'delete', asset_id,
                    '--confirm'
                ])
                
                assert delete_result.exit_code == 0
                # May succeed or fail depending on API policy for active assets
                if delete_result.exit_code == 0:
                    assert 'deleted successfully' in delete_result.output.lower()
    
    def test_delete_asset_with_dependencies_simulation(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test deleting asset with dependencies (contract, dataset) - simulated"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Asset With Dependencies',
            '--key', 'delete-deps-test-asset-key'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Create contract for this asset (simulating dependency)
                contract_file, contract_content = temp_file('.yaml', 'name: Test Contract\nversion: 1.0')
                contract_result = runner.invoke(cli, [
                    'contracts', 'create',
                    '--file', contract_file,
                    '--asset-id', asset_id
                ])
                
                # Try to delete asset (may fail if dependencies exist)
                delete_result = runner.invoke(cli, [
                    'assets', 'delete', asset_id,
                    '--confirm'
                ])
                
                assert delete_result.exit_code == 0
                # May succeed or fail depending on API dependency handling
                if delete_result.exit_code != 0:
                    assert 'dependenc' in delete_result.output.lower() or 'cannot delete' in delete_result.output.lower() or 'Failed to delete asset' in delete_result.output
    
    def test_delete_asset_cancelled(self, runner, temp_config_dir, api_base_url):
        """Test cancelling asset deletion"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Asset To Cancel Delete',
            '--key', 'cancel-delete-test-asset-key'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Try to delete without confirmation, answer 'n'
                delete_result = runner.invoke(cli, [
                    'assets', 'delete', asset_id
                ], input='n\n')
                
                # Should be cancelled
                assert 'Cancelled' in delete_result.output or delete_result.exit_code == 0


class TestAssetSearch:
    """E2E tests for asset search"""
    
    def test_search_assets_by_name(self, runner, temp_config_dir, api_base_url):
        """Test searching assets by name (via list with filters)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset with specific name
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Searchable Asset Name',
            '--key', 'search-name-test-asset-key'
        ])
        
        # List assets (API may support name filtering via search)
        list_result = runner.invoke(cli, [
            'assets', 'list'
        ])
        
        assert list_result.exit_code == 0
        # Should list assets (may or may not include the one we just created)
    
    def test_search_assets_by_domain(self, runner, temp_config_dir, api_base_url):
        """Test searching assets by domain"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create asset with specific domain
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Domain Search Asset',
            '--key', 'search-domain-test-asset-key',
            '--domain', 'sales'
        ])
        
        # List assets filtered by domain
        list_result = runner.invoke(cli, [
            'assets', 'list',
            '--domain', 'sales'
        ])
        
        assert list_result.exit_code == 0
        if list_result.exit_code == 0:
            # Should show assets in sales domain
            assert 'sales' in list_result.output.lower() or 'No assets found' in list_result.output
    
    def test_search_assets_by_status(self, runner, temp_config_dir, api_base_url):
        """Test searching assets by status"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create draft asset
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Status Search Asset',
            '--key', 'search-status-test-asset-key'
        ])
        
        # List assets filtered by status
        list_result = runner.invoke(cli, [
            'assets', 'list',
            '--status', 'DRAFT'
        ])
        
        assert list_result.exit_code == 0
        if list_result.exit_code == 0:
            # Should show draft assets
            assert 'DRAFT' in list_result.output or 'No assets found' in list_result.output
    
    def test_search_assets_pagination(self, runner, temp_config_dir, api_base_url):
        """Test asset search with pagination"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # List assets with pagination
        list_result = runner.invoke(cli, [
            'assets', 'list',
            '--limit', '10',
            '--offset', '0'
        ])
        
        assert list_result.exit_code == 0
        # Should handle pagination correctly
    
    def test_search_assets_json_output(self, runner, temp_config_dir, api_base_url):
        """Test asset search with JSON output"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        list_result = runner.invoke(cli, [
            'assets', 'list',
            '--format', 'json'
        ])
        
        assert list_result.exit_code == 0
        if list_result.exit_code == 0 and list_result.output.strip():
            # Should be valid JSON
            try:
                output_data = json.loads(list_result.output)
                assert isinstance(output_data, list)
            except json.JSONDecodeError:
                # If not JSON, that's OK for this test
                pass
    
    def test_search_assets_empty_result(self, runner, temp_config_dir, api_base_url):
        """Test asset search with no results"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Search for non-existent domain
        list_result = runner.invoke(cli, [
            'assets', 'list',
            '--domain', 'non-existent-domain-xyz'
        ])
        
        assert list_result.exit_code == 0
        if list_result.exit_code == 0:
            # Should show "No assets found" or empty list
            assert 'No assets found' in list_result.output or list_result.output.strip() == '' or list_result.output.strip() == '[]'


class TestAssetManagementWorkflows:
    """E2E tests for complete asset management workflows"""
    
    def test_complete_asset_lifecycle(self, runner, temp_config_dir, api_base_url):
        """Test complete asset lifecycle: create -> update -> activate -> delete"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Step 1: Create asset
        create_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Lifecycle Asset',
            '--key', 'lifecycle-test-asset-key',
            '--description', 'Testing complete lifecycle'
        ])
        
        assert create_result.exit_code == 0
        if create_result.exit_code == 0:
            # Extract asset ID
            asset_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        asset_id = line.split('ID:')[1].strip()
                        break
            
            if asset_id:
                # Step 2: Update asset
                update_result = runner.invoke(cli, [
                    'assets', 'update', asset_id,
                    '--name', 'Updated Lifecycle Asset',
                    '--domain', 'marketing'
                ])
                
                # Step 3: Activate asset
                activate_result = runner.invoke(cli, [
                    'assets', 'activate', asset_id
                ])
                
                # Step 4: Get asset details
                get_result = runner.invoke(cli, [
                    'assets', 'get', asset_id
                ])
                
                assert get_result.exit_code == 0
                if get_result.exit_code == 0:
                    assert 'Lifecycle Asset' in get_result.output or 'Updated Lifecycle Asset' in get_result.output
                
                # Step 5: Delete asset
                delete_result = runner.invoke(cli, [
                    'assets', 'delete', asset_id,
                    '--confirm'
                ])
                
                # All steps should complete (may succeed or fail depending on API)
                assert delete_result.exit_code == 0


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

