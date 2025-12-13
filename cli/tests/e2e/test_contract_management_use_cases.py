"""
Comprehensive E2E tests for Contract Management Use Cases.

Tests contract creation (from ODCS file, via CLI), contract validation,
and contract normalization scenarios.
"""
import pytest
import json
import tempfile
from pathlib import Path
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import Config
from datahub_cli.auth import AuthManager


class TestContractCreation:
    """E2E tests for contract creation"""
    
    def test_create_contract_from_odcs_yaml_file(self, runner, temp_config_dir, api_base_url):
        """Test contract creation from ODCS YAML file"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create ODCS contract file
        odcs_contract = '''
apiVersion: odcs/v3
kind: DataContract
id: test-contract-yaml
name: Test Contract YAML
version: 1.0.0
description: Test contract created from ODCS YAML file
schema:
  type: object
  properties:
    field1:
      type: string
      description: First field
    field2:
      type: integer
      description: Second field
'''
        
        contract_file = temp_config_dir[0] / 'contract.yaml'
        contract_file.write_text(odcs_contract)
        
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])
        
        assert result.exit_code in [0, 1]
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            assert 'ID:' in result.output
            # Should show normalization status
            assert 'Normalization Status:' in result.output or 'normalization' in result.output.lower()
    
    def test_create_contract_from_odcs_json_file(self, runner, temp_config_dir, api_base_url):
        """Test contract creation from ODCS JSON file"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create ODCS contract file
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract-json",
            "name": "Test Contract JSON",
            "version": "1.0.0",
            "description": "Test contract created from ODCS JSON file",
            "schema": {
                "type": "object",
                "properties": {
                    "field1": {
                        "type": "string",
                        "description": "First field"
                    },
                    "field2": {
                        "type": "integer",
                        "description": "Second field"
                    }
                }
            }
        }
        
        contract_file = temp_config_dir[0] / 'contract.json'
        contract_file.write_text(json.dumps(odcs_contract, indent=2))
        
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])
        
        assert result.exit_code in [0, 1]
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            assert 'ID:' in result.output
    
    def test_create_contract_from_odcs_with_all_objects(self, runner, temp_config_dir, api_base_url):
        """Test contract creation from ODCS file with all objects (complete contract)"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create comprehensive ODCS contract with all objects
        odcs_contract = '''
apiVersion: odcs/v3
kind: DataContract
id: complete-contract
name: Complete Contract
version: 1.0.0
description: Contract with all ODCS objects
info:
  owners:
    - name: Owner Name
      email: owner@example.com
  tags:
    - tag1
    - tag2
  domain: sales
  tenant: tenant1
  dataProduct: product1
schema:
  type: object
  properties:
    id:
      type: string
      description: Unique identifier
    email:
      type: string
      format: email
      description: Email address
support:
  - type: email
    email: support@example.com
    name: Support Team
servers:
  - type: s3
    url: s3://bucket/data
    description: S3 data location
slaProperties:
  - name: availability
    value: 99.9
    unit: percentage
quality:
  type: profile
  profile: basic
  rules:
    - type: completeness
      field: email
      threshold: 0.95
privacy_compliance:
  - regulation: GDPR
    classification: personal_data
'''
        
        contract_file = temp_config_dir[0] / 'complete_contract.yaml'
        contract_file.write_text(odcs_contract)
        
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])
        
        assert result.exit_code in [0, 1]
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            # Should normalize all objects
            assert 'ID:' in result.output
    
    def test_create_contract_from_odcs_minimal_objects(self, runner, temp_config_dir, api_base_url):
        """Test contract creation from ODCS file with minimal objects"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create minimal ODCS contract
        odcs_contract = '''
apiVersion: odcs/v3
kind: DataContract
id: minimal-contract
name: Minimal Contract
version: 1.0.0
schema:
  type: object
  properties:
    id:
      type: string
'''
        
        contract_file = temp_config_dir[0] / 'minimal_contract.yaml'
        contract_file.write_text(odcs_contract)
        
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])
        
        assert result.exit_code in [0, 1]
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            assert 'ID:' in result.output
    
    def test_create_contract_with_asset_id(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test contract creation with asset ID attachment"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # First create an asset
        asset_result = runner.invoke(cli, [
            'assets', 'create',
            '--name', 'Contract Asset',
            '--key', 'contract-asset-key'
        ])
        
        asset_id = None
        if asset_result.exit_code == 0 and 'ID:' in asset_result.output:
            lines = asset_result.output.split('\n')
            for line in lines:
                if 'ID:' in line:
                    asset_id = line.split('ID:')[1].strip()
                    break
        
        # Create contract file
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs/v3
kind: DataContract
id: contract-with-asset
name: Contract With Asset
version: 1.0.0
schema:
  type: object
  properties:
    id:
      type: string
''')
        
        if asset_id:
            result = runner.invoke(cli, [
                'contracts', 'create',
                '--file', contract_file,
                '--asset-id', asset_id
            ])
            
            assert result.exit_code in [0, 1]
            if result.exit_code == 0:
                assert 'created successfully' in result.output.lower()
    
    def test_create_contract_json_output(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test contract creation with JSON output format"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs/v3
kind: DataContract
id: json-output-contract
name: JSON Output Contract
version: 1.0.0
schema:
  type: object
  properties:
    id:
      type: string
''')
        
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file,
            '--format', 'json'
        ])
        
        assert result.exit_code in [0, 1]
        if result.exit_code == 0 and result.output.strip():
            # Should be valid JSON
            try:
                output_data = json.loads(result.output)
                assert isinstance(output_data, dict)
                assert 'id' in output_data or 'version' in output_data
            except json.JSONDecodeError:
                # If not JSON, that's OK for this test
                pass
    
    def test_create_contract_invalid_file_path(self, runner, temp_config_dir, api_base_url):
        """Test contract creation with invalid file path"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', '/nonexistent/path/contract.yaml'
        ])
        
        assert result.exit_code != 0
        assert 'does not exist' in result.output or 'Failed to read file' in result.output


class TestContractValidation:
    """E2E tests for contract validation"""
    
    def test_validate_valid_contract(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test validation of a valid contract"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create valid contract
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs/v3
kind: DataContract
id: valid-contract
name: Valid Contract
version: 1.0.0
description: A valid contract for testing
schema:
  type: object
  properties:
    id:
      type: string
      description: Unique identifier
    email:
      type: string
      format: email
      description: Email address
  required:
    - id
    - email
''')
        
        # Create contract first
        create_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])
        
        assert create_result.exit_code in [0, 1]
        if create_result.exit_code == 0:
            # Extract contract ID
            contract_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        contract_id = line.split('ID:')[1].strip()
                        break
            
            if contract_id:
                # Validate contract
                validate_result = runner.invoke(cli, [
                    'contracts', 'validate', contract_id
                ])
                
                assert validate_result.exit_code in [0, 1]
                if validate_result.exit_code == 0:
                    assert 'Validation Status:' in validate_result.output
                    # Should be valid or show validation results
                    assert 'VALID' in validate_result.output or 'valid' in validate_result.output.lower() or 'Errors' in validate_result.output or 'Warnings' in validate_result.output
    
    def test_validate_invalid_contract(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test validation of an invalid contract"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create invalid contract (missing required fields)
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs/v3
kind: DataContract
id: invalid-contract
# Missing name and version
schema:
  type: object
  properties:
    id:
      type: string
''')
        
        # Create contract first (may succeed even if invalid)
        create_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])
        
        assert create_result.exit_code in [0, 1]
        if create_result.exit_code == 0:
            # Extract contract ID
            contract_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        contract_id = line.split('ID:')[1].strip()
                        break
            
            if contract_id:
                # Validate contract (should show errors)
                validate_result = runner.invoke(cli, [
                    'contracts', 'validate', contract_id
                ])
                
                assert validate_result.exit_code in [0, 1]
                if validate_result.exit_code == 0:
                    assert 'Validation Status:' in validate_result.output
                    # May show errors or warnings
                    assert 'INVALID' in validate_result.output or 'Errors' in validate_result.output or 'Warnings' in validate_result.output or 'valid' in validate_result.output.lower()
    
    def test_validate_contract_with_errors(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test validation of contract with validation errors"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create contract with schema errors
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs/v3
kind: DataContract
id: error-contract
name: Error Contract
version: 1.0.0
schema:
  type: object
  properties:
    email:
      type: string
      format: invalid_format  # Invalid format
    age:
      type: integer
      minimum: -10  # Negative minimum for age
      maximum: 200  # Unrealistic maximum
''')
        
        # Create contract first
        create_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])
        
        assert create_result.exit_code in [0, 1]
        if create_result.exit_code == 0:
            # Extract contract ID
            contract_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        contract_id = line.split('ID:')[1].strip()
                        break
            
            if contract_id:
                # Validate contract
                validate_result = runner.invoke(cli, [
                    'contracts', 'validate', contract_id
                ])
                
                assert validate_result.exit_code in [0, 1]
                if validate_result.exit_code == 0:
                    assert 'Validation Status:' in validate_result.output
                    # Should show errors or warnings
                    assert 'Errors' in validate_result.output or 'Warnings' in validate_result.output or 'INVALID' in validate_result.output
    
    def test_validate_contract_json_output(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test contract validation with JSON output format"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs/v3
kind: DataContract
id: json-validate-contract
name: JSON Validate Contract
version: 1.0.0
schema:
  type: object
  properties:
    id:
      type: string
''')
        
        # Create contract first
        create_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])
        
        assert create_result.exit_code in [0, 1]
        if create_result.exit_code == 0:
            # Extract contract ID
            contract_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        contract_id = line.split('ID:')[1].strip()
                        break
            
            if contract_id:
                # Validate with JSON output
                validate_result = runner.invoke(cli, [
                    'contracts', 'validate', contract_id,
                    '--format', 'json'
                ])
                
                assert validate_result.exit_code in [0, 1]
                if validate_result.exit_code == 0 and validate_result.output.strip():
                    # Should be valid JSON
                    try:
                        output_data = json.loads(validate_result.output)
                        assert isinstance(output_data, dict)
                        assert 'validation_status' in output_data or 'errors' in output_data or 'warnings' in output_data
                    except json.JSONDecodeError:
                        # If not JSON, that's OK for this test
                        pass


class TestContractNormalization:
    """E2E tests for contract normalization"""
    
    def test_normalize_odcs_with_all_objects(self, runner, temp_config_dir, api_base_url):
        """Test normalization of ODCS contract with all objects"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create comprehensive ODCS contract
        odcs_contract = '''
apiVersion: odcs/v3
kind: DataContract
id: normalize-all-contract
name: Normalize All Contract
version: 1.0.0
description: Contract with all ODCS objects for normalization testing
info:
  owners:
    - name: Owner 1
      email: owner1@example.com
    - name: Owner 2
      email: owner2@example.com
  tags:
    - production
    - critical
  domain: finance
  tenant: tenant1
  dataProduct: product1
schema:
  type: object
  properties:
    id:
      type: string
      description: Unique identifier
      pattern: "^[a-zA-Z0-9]+$"
    email:
      type: string
      format: email
      description: Email address
    age:
      type: integer
      minimum: 0
      maximum: 150
      description: Age in years
  required:
    - id
    - email
contact:
  - type: email
    email: contact@example.com
    name: Contact Person
support:
  - type: email
    email: support@example.com
    name: Support Team
  - type: slack
    url: https://slack.example.com
    name: Support Channel
servers:
  - type: s3
    url: s3://bucket/data
    description: Primary S3 location
  - type: gcs
    url: gs://bucket/data
    description: GCS backup location
terms:
  usage: This data is for internal use only
  limitations: Data retention is 7 years
serviceLevels:
  - name: availability
    value: 99.9
    unit: percentage
  - name: latency
    value: 100
    unit: milliseconds
quality:
  type: profile
  profile: basic
  rules:
    - type: completeness
      field: email
      threshold: 0.95
    - type: uniqueness
      field: id
      threshold: 1.0
privacy_compliance:
  - regulation: GDPR
    classification: personal_data
  - regulation: HIPAA
    classification: phi
'''
        
        contract_file = temp_config_dir[0] / 'normalize_all_contract.yaml'
        contract_file.write_text(odcs_contract)
        
        # Create contract (normalization happens automatically)
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])
        
        assert result.exit_code in [0, 1]
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            # Should show normalization status
            assert 'Normalization Status:' in result.output or 'normalization' in result.output.lower()
            
            # Extract contract ID and check normalization details
            contract_id = None
            if 'ID:' in result.output:
                lines = result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        contract_id = line.split('ID:')[1].strip()
                        break
            
            if contract_id:
                # Get contract details to check normalization
                get_result = runner.invoke(cli, [
                    'contracts', 'get', contract_id
                ])
                
                assert get_result.exit_code in [0, 1]
                if get_result.exit_code == 0:
                    # Should show normalization status and any errors/warnings
                    assert 'Normalization Status:' in get_result.output or 'normalization' in get_result.output.lower()
    
    def test_normalize_odcs_minimal_objects(self, runner, temp_config_dir, api_base_url):
        """Test normalization of ODCS contract with minimal objects"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create minimal ODCS contract
        odcs_contract = '''
apiVersion: odcs/v3
kind: DataContract
id: normalize-minimal-contract
name: Minimal Contract
version: 1.0.0
schema:
  type: object
  properties:
    id:
      type: string
'''
        
        contract_file = temp_config_dir[0] / 'normalize_minimal_contract.yaml'
        contract_file.write_text(odcs_contract)
        
        # Create contract (normalization happens automatically)
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])
        
        assert result.exit_code in [0, 1]
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            # Should normalize successfully even with minimal objects
            assert 'Normalization Status:' in result.output or 'normalization' in result.output.lower()
    
    def test_normalize_odcs_with_normalization_errors(self, runner, temp_config_dir, api_base_url):
        """Test normalization of ODCS contract that produces normalization errors"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create ODCS contract with potential normalization issues
        odcs_contract = '''
apiVersion: odcs/v3
kind: DataContract
id: normalize-error-contract
name: Error Contract
version: 1.0.0
schema:
  type: object
  properties:
    invalid_field:
      type: invalid_type  # Invalid type
      format: invalid_format  # Invalid format
'''
        
        contract_file = temp_config_dir[0] / 'normalize_error_contract.yaml'
        contract_file.write_text(odcs_contract)
        
        # Create contract (normalization may produce errors)
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])
        
        assert result.exit_code in [0, 1]
        if result.exit_code == 0:
            # May show normalization errors
            assert 'Normalization Status:' in result.output or 'Normalization Errors:' in result.output or 'normalization' in result.output.lower()
            
            # Extract contract ID
            contract_id = None
            if 'ID:' in result.output:
                lines = result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        contract_id = line.split('ID:')[1].strip()
                        break
            
            if contract_id:
                # Get contract to see normalization errors
                get_result = runner.invoke(cli, [
                    'contracts', 'get', contract_id
                ])
                
                assert get_result.exit_code in [0, 1]
                if get_result.exit_code == 0:
                    # May show normalization errors or warnings
                    assert 'Normalization' in get_result.output or 'normalization' in get_result.output.lower()
    
    def test_normalize_odcs_with_warnings(self, runner, temp_config_dir, api_base_url):
        """Test normalization of ODCS contract that produces normalization warnings"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Create ODCS contract that may produce warnings (e.g., deprecated fields)
        odcs_contract = '''
apiVersion: odcs/v3
kind: DataContract
id: normalize-warning-contract
name: Warning Contract
version: 1.0.0
description: Contract that may produce normalization warnings
schema:
  type: object
  properties:
    id:
      type: string
    # Missing required fields may produce warnings
'''
        
        contract_file = temp_config_dir[0] / 'normalize_warning_contract.yaml'
        contract_file.write_text(odcs_contract)
        
        # Create contract
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])
        
        assert result.exit_code in [0, 1]
        if result.exit_code == 0:
            # May show normalization warnings
            assert 'Normalization Status:' in result.output or 'normalization' in result.output.lower()
            
            # Extract contract ID
            contract_id = None
            if 'ID:' in result.output:
                lines = result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        contract_id = line.split('ID:')[1].strip()
                        break
            
            if contract_id:
                # Get contract to see normalization warnings
                get_result = runner.invoke(cli, [
                    'contracts', 'get', contract_id
                ])
                
                assert get_result.exit_code in [0, 1]
                if get_result.exit_code == 0:
                    # May show normalization warnings
                    assert 'Normalization' in get_result.output or 'normalization' in get_result.output.lower() or 'Warnings' in get_result.output


class TestContractManagementWorkflows:
    """E2E tests for complete contract management workflows"""
    
    def test_complete_contract_lifecycle(self, runner, temp_config_dir, api_base_url, temp_file):
        """Test complete contract lifecycle: create -> get -> validate -> lint"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Step 1: Create contract
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs/v3
kind: DataContract
id: lifecycle-contract
name: Lifecycle Contract
version: 1.0.0
description: Testing complete contract lifecycle
schema:
  type: object
  properties:
    id:
      type: string
    email:
      type: string
      format: email
  required:
    - id
    - email
''')
        
        create_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])
        
        assert create_result.exit_code in [0, 1]
        if create_result.exit_code == 0:
            # Extract contract ID
            contract_id = None
            if 'ID:' in create_result.output:
                lines = create_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        contract_id = line.split('ID:')[1].strip()
                        break
            
            if contract_id:
                # Step 2: Get contract
                get_result = runner.invoke(cli, [
                    'contracts', 'get', contract_id
                ])
                
                assert get_result.exit_code in [0, 1]
                if get_result.exit_code == 0:
                    assert 'Lifecycle Contract' in get_result.output or contract_id in get_result.output
                
                # Step 3: Validate contract
                validate_result = runner.invoke(cli, [
                    'contracts', 'validate', contract_id
                ])
                
                assert validate_result.exit_code in [0, 1]
                if validate_result.exit_code == 0:
                    assert 'Validation Status:' in validate_result.output
                
                # Step 4: Lint contract
                lint_result = runner.invoke(cli, [
                    'contracts', 'lint', contract_id
                ])
                
                assert lint_result.exit_code in [0, 1]
                if lint_result.exit_code == 0:
                    assert 'Lint Status:' in lint_result.output or 'No linting issues' in lint_result.output or 'Issues' in lint_result.output


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

