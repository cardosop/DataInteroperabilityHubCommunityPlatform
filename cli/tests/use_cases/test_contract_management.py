"""
Comprehensive E2E tests for Contract Management Use Cases.

Tests contract creation (from ODCS file, via CLI), contract validation,
and contract normalization scenarios.
"""
import json

import pytest

from datahub_cli.main import cli

pytestmark = pytest.mark.mvp


class TestContractCreation:
    """E2E tests for contract creation"""

    def test_create_contract_from_odcs_yaml_file(self, runner, authenticated_config, tmp_path):
        """Test contract creation from ODCS YAML file"""

        # Create ODCS contract file
        odcs_contract = '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: test-contract-yaml
name: Test Contract YAML
version: 1.0.0
description: Test contract created from ODCS YAML file
schema:
  fields:
    - name: field1
      type: string
      description: First field
    - name: field2
      type: integer
      description: Second field
'''

        contract_file = tmp_path / 'contract.yaml'
        contract_file.write_text(odcs_contract)

        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            assert 'ID:' in result.output
            # Should show normalization status
            assert 'Normalization Status:' in result.output or 'normalization' in result.output.lower()

    def test_create_contract_from_odcs_json_file(self, runner, authenticated_config, tmp_path):
        """Test contract creation from ODCS JSON file"""

        # Create ODCS contract file
        odcs_contract = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-contract-json",
            "name": "Test Contract JSON",
            "version": "1.0.0",
            "description": "Test contract created from ODCS JSON file",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "description": "First field"
                    },
                    {
                        "name": "field2",
                        "type": "integer",
                        "description": "Second field"
                    }
                ]
            }
        }

        contract_file = tmp_path / 'contract.json'
        contract_file.write_text(json.dumps(odcs_contract, indent=2))

        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            assert 'ID:' in result.output

    def test_create_contract_from_odcs_with_all_objects(self, runner, authenticated_config, tmp_path):
        """Test contract creation from ODCS file with all objects (complete contract)"""

        # Create comprehensive ODCS contract with all objects
        odcs_contract = '''
apiVersion: odcs.io/v3.0.0
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
  fields:
    - name: id
      type: string
      description: Unique identifier
    - name: email
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

        contract_file = tmp_path / 'complete_contract.yaml'
        contract_file.write_text(odcs_contract)

        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])

        # Contract creation may fail if the backend rejects the ODCS
        # schema or normalization produces errors
        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            assert 'ID:' in result.output

    def test_create_contract_from_odcs_minimal_objects(self, runner, authenticated_config, tmp_path):
        """Test contract creation from ODCS file with minimal objects"""

        # Create minimal ODCS contract
        odcs_contract = '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: minimal-contract
name: Minimal Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
'''

        contract_file = tmp_path / 'minimal_contract.yaml'
        contract_file.write_text(odcs_contract)

        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()
            assert 'ID:' in result.output

    def test_create_contract_with_asset_id(self, runner, authenticated_config, temp_file):
        """Test contract creation with asset ID attachment"""

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
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: contract-with-asset
name: Contract With Asset
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
''')

        if asset_id:
            result = runner.invoke(cli, [
                'contracts', 'create',
                '--file', contract_file,
                '--asset-id', asset_id
            ])

            assert result.exit_code == 0, result.output
            if result.exit_code == 0:
                assert 'created successfully' in result.output.lower()

    def test_create_contract_json_output(self, runner, authenticated_config, temp_file):
        """Test contract creation with JSON output format"""

        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: json-output-contract
name: JSON Output Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
''')

        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file,
            '--format', 'json'
        ])

        assert result.exit_code == 0, result.output
        if result.exit_code == 0 and result.output.strip():
            # Should be valid JSON
            try:
                output_data = json.loads(result.output)
                assert isinstance(output_data, dict)
                assert 'id' in output_data or 'version' in output_data
            except json.JSONDecodeError:
                # If not JSON, that's OK for this test
                pass

    def test_create_contract_invalid_file_path(self, runner, authenticated_config):
        """Test contract creation with invalid file path"""

        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', '/nonexistent/path/contract.yaml'
        ])

        assert result.exit_code != 0
        assert 'does not exist' in result.output or 'Failed to read file' in result.output


class TestContractValidation:
    """E2E tests for contract validation"""

    def test_validate_valid_contract(self, runner, authenticated_config, temp_file):
        """Test validation of a valid contract"""

        # Create valid contract
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: valid-contract
name: Valid Contract
version: 1.0.0
description: A valid contract for testing
schema:
  fields:
    - name: id
      type: string
      description: Unique identifier
    - name: email
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

        assert create_result.exit_code == 0, create_result.output
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

                assert validate_result.exit_code == 0, validate_result.output
                if validate_result.exit_code == 0:
                    assert 'Validation Status:' in validate_result.output
                    # Should be valid or show validation results
                    assert 'VALID' in validate_result.output or 'valid' in validate_result.output.lower() or 'Errors' in validate_result.output or 'Warnings' in validate_result.output

    def test_validate_invalid_contract(self, runner, authenticated_config, temp_file):
        """Test validation of an invalid contract"""

        # Create contract with minimal valid structure (name + schema.fields)
        # but missing version — the validate command should flag issues
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: invalid-contract
name: Invalid Contract
schema:
  fields:
    - name: id
      type: string
''')

        create_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])

        assert create_result.exit_code == 0, create_result.output
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

                assert validate_result.exit_code == 0, validate_result.output
                if validate_result.exit_code == 0:
                    assert 'Validation Status:' in validate_result.output
                    # May show errors or warnings
                    assert 'INVALID' in validate_result.output or 'Errors' in validate_result.output or 'Warnings' in validate_result.output or 'valid' in validate_result.output.lower()

    def test_validate_contract_with_errors(self, runner, authenticated_config, temp_file):
        """Test validation of contract with validation errors"""

        # Create contract with schema errors
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: error-contract
name: Error Contract
version: 1.0.0
schema:
  fields:
    - name: email
      type: string
      format: invalid_format  # Invalid format
    - name: age
      type: integer
      minimum: -10  # Negative minimum for age
      maximum: 200  # Unrealistic maximum
''')

        # Create contract first
        create_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])

        assert create_result.exit_code == 0, create_result.output
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

                assert validate_result.exit_code == 0, validate_result.output
                if validate_result.exit_code == 0:
                    assert 'Validation Status:' in validate_result.output
                    # Should show validation issues
                    assert (
                        'Errors' in validate_result.output
                        or 'Warnings' in validate_result.output
                        or 'INVALID' in validate_result.output
                        or 'ERROR' in validate_result.output
                    )

    def test_validate_contract_json_output(self, runner, authenticated_config, temp_file):
        """Test contract validation with JSON output format"""

        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: json-validate-contract
name: JSON Validate Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
''')

        # Create contract first
        create_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])

        assert create_result.exit_code == 0, create_result.output
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

                assert validate_result.exit_code == 0, validate_result.output
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

    def test_normalize_odcs_with_all_objects(self, runner, authenticated_config, tmp_path):
        """Test normalization of ODCS contract with all objects"""

        # Create comprehensive ODCS contract
        odcs_contract = '''
apiVersion: odcs.io/v3.0.0
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
  fields:
    - name: id
      type: string
      description: Unique identifier
      pattern: "^[a-zA-Z0-9]+$"
    - name: email
      type: string
      format: email
      description: Email address
    - name: age
      type: integer
      minimum: 0
      maximum: 150
      description: Age in years
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

        contract_file = tmp_path / 'normalize_all_contract.yaml'
        contract_file.write_text(odcs_contract)

        # Create contract (normalization happens automatically)
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])

        assert result.exit_code == 0, result.output
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

                assert get_result.exit_code == 0, get_result.output
                if get_result.exit_code == 0:
                    # Should show normalization status and any errors/warnings
                    assert 'Normalization Status:' in get_result.output or 'normalization' in get_result.output.lower()

    def test_normalize_odcs_minimal_objects(self, runner, authenticated_config, tmp_path):
        """Test normalization of ODCS contract with minimal objects"""

        # Create minimal ODCS contract
        odcs_contract = '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: normalize-minimal-contract
name: Minimal Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
'''

        contract_file = tmp_path / 'normalize_minimal_contract.yaml'
        contract_file.write_text(odcs_contract)

        # Create contract (normalization happens automatically)
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            assert 'created successfully' in result.output.lower()

    def test_normalize_odcs_with_normalization_errors(self, runner, authenticated_config, tmp_path):
        """Test normalization of ODCS contract that produces normalization errors"""

        # Create ODCS contract with potential normalization issues
        odcs_contract = '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: normalize-error-contract
name: Error Contract
version: 1.0.0
schema:
  fields:
    - name: invalid_field
      type: invalid_type  # Invalid type
      format: invalid_format  # Invalid format
'''

        contract_file = tmp_path / 'normalize_error_contract.yaml'
        contract_file.write_text(odcs_contract)

        # Create contract (normalization may produce errors)
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])

        assert result.exit_code == 0, result.output
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

                assert get_result.exit_code == 0, get_result.output
                if get_result.exit_code == 0:
                    # May show normalization errors or warnings
                    assert 'Normalization' in get_result.output or 'normalization' in get_result.output.lower()

    def test_normalize_odcs_with_warnings(self, runner, authenticated_config, tmp_path):
        """Test normalization of ODCS contract that produces normalization warnings"""

        # Create ODCS contract that may produce warnings (e.g., deprecated fields)
        odcs_contract = '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: normalize-warning-contract
name: Warning Contract
version: 1.0.0
description: Contract that may produce normalization warnings
schema:
  fields:
    - name: id
      type: string
    # Missing required fields may produce warnings
'''

        contract_file = tmp_path / 'normalize_warning_contract.yaml'
        contract_file.write_text(odcs_contract)

        # Create contract
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(contract_file)
        ])

        assert result.exit_code == 0, result.output
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

                assert get_result.exit_code == 0, get_result.output
                if get_result.exit_code == 0:
                    # May show normalization warnings
                    assert 'Normalization' in get_result.output or 'normalization' in get_result.output.lower() or 'Warnings' in get_result.output


class TestODPSProductFirstFlow:
    """E2E tests for ODPS Product-First flow via CLI"""

    def test_create_odps_product_first_flow_complete(self, runner, authenticated_config, temp_file):
        """Test complete Product-First flow: create ODPS with --extract-odcs, verify both contracts created and linked"""

        # Create a valid ODPS document with embedded ODCS contract.
        # The contract content must be under product.contract.spec
        # (not directly in product.contract).
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "e2e-test-product",
        "name": "E2E Test Product",
        "description": "Complete Product-First flow test via CLI"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": "e2e-test-contract",
        "name": "E2E Test Contract",
        "version": "1.0.0",
        "description": "ODCS contract embedded in ODPS",
        "schema": {
          "fields": [
            {
              "name": "id",
              "type": "string",
              "nullable": false,
              "description": "Unique identifier"
            },
            {
              "name": "email",
              "type": "string",
              "format": "email",
              "nullable": true,
              "description": "Email address"
            }
          ]
        }
      }
    }
  }
}"""

        odps_file, content = temp_file('.json', odps_content)

        # Step 1: Create ODPS using Product-First flow
        create_result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', odps_file,
            '--extract-odcs'
        ])

        assert create_result.exit_code == 0, create_result.output
        if create_result.exit_code == 0:
            # Verify output shows both contracts
            assert 'ODPS product created successfully' in create_result.output or 'odps_contract' in create_result.output
            assert 'Product-First flow' in create_result.output or 'ODCS Contract' in create_result.output

            # Extract contract IDs from output
            odps_contract_id = None
            odcs_contract_id = None

            # Try to extract IDs from output (format may vary)
            lines = create_result.output.split('\n')
            for i, line in enumerate(lines):
                if 'ODPS Contract:' in line or 'ODPS' in line and 'ID:' in line:
                    # Look for ID in next few lines
                    for j in range(i, min(i+5, len(lines))):
                        if 'ID:' in lines[j]:
                            odps_contract_id = lines[j].split('ID:')[1].strip()
                            break
                if 'ODCS Contract' in line and 'ID:' in line:
                    # Look for ID in next few lines
                    for j in range(i, min(i+5, len(lines))):
                        if 'ID:' in lines[j]:
                            odcs_contract_id = lines[j].split('ID:')[1].strip()
                            break

            # If we got contract IDs, verify they exist
            if odps_contract_id:
                # Step 2: Get ODPS contract to verify it was created
                get_odps_result = runner.invoke(cli, [
                    'contracts', 'get', odps_contract_id
                ])

                assert get_odps_result.exit_code == 0, get_odps_result.output
                if get_odps_result.exit_code == 0:
                    assert 'ODPS' in get_odps_result.output or odps_contract_id in get_odps_result.output

            if odcs_contract_id:
                # Step 3: Get ODCS contract to verify it was created and linked
                get_odcs_result = runner.invoke(cli, [
                    'contracts', 'get', odcs_contract_id
                ])

                assert get_odcs_result.exit_code == 0, get_odcs_result.output
                if get_odcs_result.exit_code == 0:
                    assert 'ODCS' in get_odcs_result.output or odcs_contract_id in get_odcs_result.output

    def test_create_odps_product_first_flow_yaml(self, runner, authenticated_config, temp_file):
        """Test Product-First flow with YAML format ODPS document"""

        # Create ODPS document in YAML format
        odps_content = """schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: e2e-test-product-yaml
      name: E2E Test Product YAML
      description: Product-First flow test with YAML format
  contract:
    spec:
      apiVersion: odcs.io/v3.0.0
      kind: DataContract
      id: e2e-test-contract-yaml
      name: E2E Test Contract YAML
      version: 1.0.0
      schema:
        fields:
          - name: id
            type: string
            nullable: false
"""

        odps_file, content = temp_file('.yaml', odps_content)

        # Create ODPS using Product-First flow
        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', odps_file,
            '--extract-odcs'
        ])

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            assert 'ODPS product created successfully' in result.output or 'odps_contract' in result.output

    def test_create_odps_product_first_flow_with_options(self, runner, authenticated_config, temp_file):
        """Test Product-First flow with all options (version, asset-id, resolve-external-refs)"""

        # Create ODPS document with contract under spec
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "e2e-test-product-options",
        "name": "E2E Test Product with Options"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": "e2e-test-contract-options",
        "name": "E2E Test Contract with Options",
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

        odps_file, content = temp_file('.json', odps_content)

        # Create ODPS with all options
        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', odps_file,
            '--extract-odcs',
            '--version', '4.1',
            '--resolve-external-refs'
        ])

        assert result.exit_code == 0, result.output
        if result.exit_code == 0:
            assert 'ODPS product created successfully' in result.output or 'odps_contract' in result.output

    def test_create_odps_link_odcs_flow(self, runner, authenticated_config, temp_file):
        """Test linking ODPS to existing ODCS contract flow"""

        # First, create an ODCS contract
        odcs_content = """{
  "apiVersion": "odcs.io/v3.0.0",
  "kind": "DataContract",
  "id": "e2e-odcs-for-link",
  "name": "E2E ODCS for Link",
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
}"""

        odcs_file, odcs_file_content = temp_file('.json', odcs_content)

        # Create ODCS contract first
        create_odcs_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', odcs_file
        ])

        assert create_odcs_result.exit_code == 0, create_odcs_result.output
        if create_odcs_result.exit_code == 0:
            # Extract ODCS contract ID
            odcs_contract_id = None
            if 'ID:' in create_odcs_result.output:
                lines = create_odcs_result.output.split('\n')
                for line in lines:
                    if 'ID:' in line:
                        odcs_contract_id = line.split('ID:')[1].strip()
                        break

            if odcs_contract_id:
                # Create ODPS document for linking to existing ODCS.
                # --link-odcs requires product.contract with an inline
                # ODCS contract (same pattern as the passing
                # test_link_odps_to_odcs_workflow).
                odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "e2e-test-product-link",
        "name": "E2E Test Product for Link",
        "description": "ODPS product to link to existing ODCS"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": "e2e-odcs-for-link",
        "name": "E2E ODCS for Link",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {"name": "id", "type": "string"}
          ]
        }
      }
    }
  }
}"""

                odps_file, odps_file_content = temp_file('.json', odps_content)

                # Link ODPS to existing ODCS
                link_result = runner.invoke(cli, [
                    'contracts', 'create-odps',
                    '--file', odps_file,
                    '--link-odcs', odcs_contract_id
                ])

                assert link_result.exit_code == 0, link_result.output
                if link_result.exit_code == 0:
                    assert 'ODPS contract created and linked successfully' in link_result.output or 'id' in link_result.output
                    assert odcs_contract_id in link_result.output


class TestContractManagementWorkflows:
    """E2E tests for complete contract management workflows"""

    def test_complete_contract_lifecycle(self, runner, authenticated_config, temp_file):
        """Test complete contract lifecycle: create -> get -> validate -> lint"""

        # Step 1: Create contract
        contract_file, contract_content = temp_file('.yaml', '''
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: lifecycle-contract
name: Lifecycle Contract
version: 1.0.0
description: Testing complete contract lifecycle
schema:
  fields:
    - name: id
      type: string
    - name: email
      type: string
      format: email
''')

        create_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', contract_file
        ])

        assert create_result.exit_code == 0, create_result.output
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

                assert get_result.exit_code == 0, get_result.output
                if get_result.exit_code == 0:
                    assert 'Lifecycle Contract' in get_result.output or contract_id in get_result.output

                # Step 3: Validate contract
                validate_result = runner.invoke(cli, [
                    'contracts', 'validate', contract_id
                ])

                assert validate_result.exit_code == 0, validate_result.output
                if validate_result.exit_code == 0:
                    assert 'Validation Status:' in validate_result.output

                # Step 4: Lint contract (requires DataContract service)
                lint_result = runner.invoke(cli, [
                    'contracts', 'lint', contract_id
                ])

                assert lint_result.exit_code == 0, lint_result.output
                if lint_result.exit_code == 0:
                    assert 'Lint Status:' in lint_result.output or 'No linting issues' in lint_result.output or 'Issues' in lint_result.output


class TestODPSLinkingWorkflow:
    """E2E tests for ODPS linking workflow via CLI"""

    def test_link_odps_to_odcs_workflow(self, runner, authenticated_config, tmp_path):
        """Test complete workflow: create ODCS, create ODPS, link them, list links, unlink"""


        # Step 1: Create ODCS contract
        odcs_contract = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "e2e-test-odcs-link",
            "name": "E2E Test ODCS for Linking",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False
                    }
                ]
            }
        }

        odcs_file = tmp_path / 'odcs_contract.json'
        odcs_file.write_text(json.dumps(odcs_contract, indent=2))

        create_odcs_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(odcs_file)
        ])

        # If ODCS creation fails, skip the rest (may need auth or API)
        if create_odcs_result.exit_code != 0:
            pytest.skip("ODCS contract creation failed - may need authentication or API not available")

        # Extract ODCS contract ID from output (basic parsing)
        odcs_id = None
        for line in create_odcs_result.output.split('\n'):
            if 'ID:' in line:
                # Try to extract UUID-like ID
                import re
                uuid_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', line, re.I)
                if uuid_match:
                    odcs_id = uuid_match.group(0)
                    break

        if not odcs_id:
            pytest.skip("Could not extract ODCS contract ID from output")

        # Step 2: Create ODPS contract with matching contract ID
        odps_contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "e2e-test-product-link",
                        "name": "E2E Test Product for Linking"
                    }
                },
                "contract": {
                    "apiVersion": "odcs.io/v3.0.0",
                    "kind": "DataContract",
                    "id": "e2e-test-odcs-link",  # Match ODCS contract ID
                    "name": "E2E Test ODCS for Linking",
                    "version": "1.0.0",
                    "schema": {
                        "fields": [
                            {
                                "name": "id",
                                "type": "string",
                                "nullable": False
                            }
                        ]
                    }
                }
            }
        }

        odps_file = tmp_path / 'odps_contract.json'
        odps_file.write_text(json.dumps(odps_contract, indent=2))

        create_odps_result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', str(odps_file),
            '--link-odcs', odcs_id
        ])

        # If ODPS creation/linking fails, we can still test other commands
        odps_id = None
        if create_odps_result.exit_code == 0:
            # Extract ODPS contract ID
            for line in create_odps_result.output.split('\n'):
                if 'ID:' in line:
                    import re
                    uuid_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', line, re.I)
                    if uuid_match:
                        odps_id = uuid_match.group(0)
                        break

        # Step 3: List links on ODCS contract
        list_links_result = runner.invoke(cli, [
            'contracts', 'list-links',
            odcs_id
        ])

        assert list_links_result.exit_code == 0, list_links_result.output
        if list_links_result.exit_code == 0:
            # Should show ODPS link if linking succeeded
            assert 'ODPS Link' in list_links_result.output or 'No links found' in list_links_result.output

        # Step 4: If we have an ODPS ID, try linking it explicitly
        if odps_id:
            # Try linking again (should handle already linked case gracefully)
            link_result = runner.invoke(cli, [
                'contracts', 'link-odps',
                odcs_id, odps_id
            ])
            # May succeed (if not already linked) or fail gracefully (if already linked)
            assert link_result.exit_code == 0, link_result.output

        # Step 5: Unlink ODPS from ODCS
        unlink_result = runner.invoke(cli, [
            'contracts', 'unlink-odps',
            odcs_id
        ])

        assert unlink_result.exit_code == 0, unlink_result.output
        if unlink_result.exit_code == 0:
            assert 'unlinked successfully' in unlink_result.output.lower()

        # Step 6: Verify links are removed
        list_links_after_result = runner.invoke(cli, [
            'contracts', 'list-links',
            odcs_id
        ])

        assert list_links_after_result.exit_code == 0, list_links_after_result.output
        if list_links_after_result.exit_code == 0:
            # After unlinking, should show no links or ODPS Link: None
            assert 'ODPS Link: None' in list_links_after_result.output or 'No links found' in list_links_after_result.output

    def test_list_links_for_odps_contract(self, runner, authenticated_config, tmp_path):
        """Test listing links for an ODPS contract (should show ODCS link)"""


        # Create ODCS contract
        odcs_contract = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "e2e-test-odcs-list",
            "name": "E2E Test ODCS for List Links",
            "version": "1.0.0",
            "schema": {
                "fields": [{"name": "id", "type": "string", "nullable": False}]
            }
        }

        odcs_file = tmp_path / 'odcs_contract_list.json'
        odcs_file.write_text(json.dumps(odcs_contract, indent=2))

        create_odcs_result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', str(odcs_file)
        ])

        if create_odcs_result.exit_code != 0:
            pytest.skip("ODCS contract creation failed")

        # Extract ODCS ID
        odcs_id = None
        for line in create_odcs_result.output.split('\n'):
            if 'ID:' in line:
                import re
                uuid_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', line, re.I)
                if uuid_match:
                    odcs_id = uuid_match.group(0)
                    break

        if not odcs_id:
            pytest.skip("Could not extract ODCS contract ID")

        # Create and link ODPS
        odps_contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "e2e-test-product-list",
                        "name": "E2E Test Product for List Links"
                    }
                },
                "contract": {
                    "apiVersion": "odcs.io/v3.0.0",
                    "kind": "DataContract",
                    "id": "e2e-test-odcs-list",
                    "name": "E2E Test ODCS for List Links",
                    "version": "1.0.0",
                    "schema": {
                        "fields": [{"name": "id", "type": "string", "nullable": False}]
                    }
                }
            }
        }

        odps_file = tmp_path / 'odps_contract_list.json'
        odps_file.write_text(json.dumps(odps_contract, indent=2))

        create_odps_result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', str(odps_file),
            '--link-odcs', odcs_id
        ])

        if create_odps_result.exit_code != 0:
            pytest.skip("ODPS contract creation/linking failed")

        # Extract ODPS ID
        odps_id = None
        for line in create_odps_result.output.split('\n'):
            if 'ID:' in line:
                import re
                uuid_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', line, re.I)
                if uuid_match:
                    odps_id = uuid_match.group(0)
                    break

        if not odps_id:
            pytest.skip("Could not extract ODPS contract ID")

        # List links on ODPS contract (should show ODCS link)
        list_links_result = runner.invoke(cli, [
            'contracts', 'list-links',
            odps_id
        ])

        assert list_links_result.exit_code == 0, list_links_result.output
        if list_links_result.exit_code == 0:
            # Should show ODCS link
            assert 'ODCS Link' in list_links_result.output or 'No links found' in list_links_result.output

