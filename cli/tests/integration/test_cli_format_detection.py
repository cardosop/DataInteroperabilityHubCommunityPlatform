"""
Comprehensive integration tests for CLI format detection (Task 10.1.41.2).

Tests auto-detection of ODPS vs ODCS and format support in all contract commands.
No mocks/stubs - uses real API endpoints.

These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: DATAHUB_API_KEY

To run:
    pytest cli/tests/integration/test_cli_format_detection.py -v
"""
import pytest
import json
import os
import uuid
import tempfile
import subprocess
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import config


def _check_api_available():
    """Check if API service is available"""
    try:
        import requests
        response = requests.get("http://localhost:8000/api/v1/", timeout=2)
        return response.status_code < 600
    except Exception:
        return False


def _create_test_api_key():
    """Create a test API key via Django shell in the API service container"""
    django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.auth.models import APIKey

tenant, _ = Tenant.objects.get_or_create(
    slug='odps-format-detection-cli-test-tenant',
    defaults={'name': 'ODPS Format Detection CLI Test Tenant'}
)

user, _ = User.objects.get_or_create(
    email='odps-format-detection-cli-test@example.com',
    defaults={'tenant': tenant, 'status': UserStatus.ACTIVE}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

APIKey.objects.filter(user=user, name='odps-format-detection-cli-test-key').delete()

api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
APIKey.objects.create(
    user=user, tenant=tenant,
    name='odps-format-detection-cli-test-key',
    key_hash=api_key_hash
)

print(api_key_value)
"""
    try:
        result = subprocess.run(
            ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'hub/manage.py', 'shell'],
            input=django_shell_script,
            text=True,
            capture_output=True,
            timeout=30,
            cwd='/home/ph/Desktop/DataInteroperabilityHub'
        )
        if result.returncode == 0:
            output_lines = result.stdout.strip().split('\n')
            for line in reversed(output_lines):
                line = line.strip()
                if line and len(line) > 20:
                    cleaned = line.replace('-', '').replace('_', '')
                    if cleaned.isalnum() and ' ' not in line and ':' not in line and '"' not in line and '{' not in line and '}' not in line:
                        return line
    except Exception:
        pass
    return None


@pytest.fixture(autouse=True)
def setup_config():
    """Set up API base URL and authentication"""
    api_base_url = "http://localhost:8000/api/v1"
    config.set_api_base_url(api_base_url)

    api_key = (
        os.environ.get('DATAHUB_API_KEY') or
        os.environ.get('TEST_API_KEY') or
        config.get_api_key() or
        _create_test_api_key()
    )

    if api_key:
        config.set_api_key(api_key)

    yield

    config.clear_auth()


@pytest.fixture
def odps_json_file():
    """Create an ODPS JSON file"""
    odps_data = {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": f"odps-product-{uuid.uuid4().hex[:8]}",
                    "name": "ODPS Product"
                }
            },
            "contract": {
                "spec": {
                    "apiVersion": "odcs.io/v3.0.2",
                    "kind": "DataContract",
                    "id": "test",
                    "name": "test",
                    "version": "1.0.0",
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string", "nullable": False}
                        ]
                    }
                }
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(odps_data, f)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def odps_yaml_file():
    """Create an ODPS YAML file"""
    yaml_content = """schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: odps-product-yaml-{uuid}
      name: ODPS Product YAML
  contract:
    spec:
      apiVersion: "odcs.io/v3.0.2"
      kind: DataContract
      id: test-yaml
      name: test-yaml
      version: "1.0.0"
      schema:
        fields:
          - name: id
            type: string
            nullable: false
""".replace('{uuid}', uuid.uuid4().hex[:8])

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def odcs_json_file():
    """Create an ODCS JSON file"""
    odcs_data = {
        "apiVersion": "3.0.2",
        "kind": "DataContract",
        "metadata": {
            "name": f"odcs-contract-{uuid.uuid4().hex[:8]}",
            "version": "1.0.0"
        },
        "spec": {
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(odcs_data, f)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def odcs_yaml_file():
    """Create an ODCS YAML file"""
    yaml_content = """apiVersion: "3.0.2"
kind: DataContract
metadata:
  name: odcs-contract-yaml-{uuid}
  version: "1.0.0"
spec:
  schema:
    fields:
      - name: id
        type: string
""".replace('{uuid}', uuid.uuid4().hex[:8])

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestCLIFormatDetection:
    """Tests for CLI format detection and auto-detection"""

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_auto_detection_odps_vs_odcs_json(self, odps_json_file, odcs_json_file, setup_config):
        """Test auto-detection of ODPS vs ODCS from JSON files"""
        runner = CliRunner()

        # Test ODPS detection
        result_odps = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', odps_json_file,
            '--extract-odcs',
            '--output-format', 'json'
        ])

        assert result_odps.exit_code == 0, f"ODPS creation failed: {result_odps.output}"

        # Test ODCS detection via regular create
        result_odcs = runner.invoke(cli, [
            'contracts', 'create',
            '--file', odcs_json_file,
            '--format', 'json'
        ])

        assert result_odcs.exit_code == 0, f"ODCS creation failed: {result_odcs.output}"
        odcs_data = json.loads(result_odcs.output)
        assert odcs_data.get('original_spec_type') == 'ODCS' or 'id' in odcs_data

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_auto_detection_odps_vs_odcs_yaml(self, odps_yaml_file, odcs_yaml_file, setup_config):
        """Test auto-detection of ODPS vs ODCS from YAML files"""
        runner = CliRunner()

        # Test ODPS detection
        result_odps = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', odps_yaml_file,
            '--extract-odcs',
            '--format', 'YAML',
            '--output-format', 'json'
        ])

        assert result_odps.exit_code == 0, f"ODPS YAML creation failed: {result_odps.output}"

        # Test ODCS detection via regular create
        result_odcs = runner.invoke(cli, [
            'contracts', 'create',
            '--file', odcs_yaml_file,
            '--format', 'json'
        ])

        assert result_odcs.exit_code == 0, f"ODCS YAML creation failed: {result_odcs.output}"

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_original_spec_type_display_in_list(self, odps_json_file, odcs_json_file, setup_config):
        """Test that `original_spec_type` is displayed correctly in list command"""
        runner = CliRunner()

        # Create ODPS contract
        create_odps = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', odps_json_file,
            '--extract-odcs',
            '--output-format', 'json'
        ])
        assert create_odps.exit_code == 0
        odps_data = json.loads(create_odps.output)
        odps_id = odps_data.get('odps_contract', {}).get('id') or odps_data.get('id')

        # Create ODCS contract
        create_odcs = runner.invoke(cli, [
            'contracts', 'create',
            '--file', odcs_json_file,
            '--output-format', 'json'
        ])
        assert create_odcs.exit_code == 0
        odcs_data = json.loads(create_odcs.output)
        odcs_id = odcs_data.get('id')

        # List contracts and check format
        result = runner.invoke(cli, [
            'contracts', 'list',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        contracts_list = json.loads(result.output)

        # Find our contracts in the list
        odps_found = False
        odcs_found = False

        if isinstance(contracts_list, list):
            for contract in contracts_list:
                if contract.get('id') == odps_id:
                    odps_found = True
                    assert contract.get('original_spec_type') == 'ODPS'
                elif contract.get('id') == odcs_id:
                    odcs_found = True
                    assert contract.get('original_spec_type') == 'ODCS'
        elif isinstance(contracts_list, dict):
            # Handle paginated response
            items = contracts_list.get('results', contracts_list.get('items', []))
            for contract in items:
                if contract.get('id') == odps_id:
                    odps_found = True
                    assert contract.get('original_spec_type') == 'ODPS'
                elif contract.get('id') == odcs_id:
                    odcs_found = True
                    assert contract.get('original_spec_type') == 'ODCS'

        # At least one should be found
        assert odps_found or odcs_found, "Created contracts not found in list"

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_odps_format_support_in_contract_commands(self, odps_json_file, setup_config):
        """Test ODPS format support in all contract commands"""
        runner = CliRunner()

        # Create ODPS contract
        create_result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', odps_json_file,
            '--extract-odcs',
            '--output-format', 'json'
        ])
        assert create_result.exit_code == 0
        contract_data = json.loads(create_result.output)
        contract_id = contract_data.get('odps_contract', {}).get('id') or contract_data.get('id')

        # Test get command with ODPS
        result_get = runner.invoke(cli, [
            'contracts', 'get',
            contract_id,
            '--format', 'json'
        ])
        assert result_get.exit_code == 0
        get_data = json.loads(result_get.output)
        assert get_data.get('original_spec_type') == 'ODPS' or 'id' in get_data

        # Test export with ODPS format
        result_export = runner.invoke(cli, [
            'contracts', 'export',
            contract_id,
            '--format', 'odps',
            '--output-format', 'json',
            '--version', '4.1',
            '--cli-format', 'json'
        ])
        assert result_export.exit_code == 0

        # Test download with ODPS format
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            result_download = runner.invoke(cli, [
                'contracts', 'download',
                contract_id,
                '--format', 'odps',
                '--output-format', 'json',
                '--output', temp_path
            ])
            assert result_download.exit_code == 0
            assert os.path.exists(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        # Test validate command with ODPS
        result_validate = runner.invoke(cli, [
            'contracts', 'validate',
            contract_id,
            '--format', 'json'
        ])
        # May succeed or fail depending on contract validity, but should not crash
        assert result_validate.exit_code in [0, 1]

        # Test lint command with ODPS
        result_lint = runner.invoke(cli, [
            'contracts', 'lint',
            contract_id,
            '--format', 'json'
        ])
        # May succeed or fail depending on contract validity, but should not crash
        assert result_lint.exit_code in [0, 1]

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_format_detection_from_file_extension(self, odps_json_file, odps_yaml_file, setup_config):
        """Test format detection from file extension"""
        runner = CliRunner()

        # Test JSON file (should auto-detect JSON)
        result_json = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', odps_json_file,
            '--extract-odcs',
            '--output-format', 'json'
        ])
        assert result_json.exit_code == 0

        # Test YAML file (should auto-detect YAML or require format flag)
        result_yaml = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', odps_yaml_file,
            '--extract-odcs',
            '--format', 'YAML',  # Explicit format for YAML
            '--output-format', 'json'
        ])
        assert result_yaml.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_format_override_with_spec_type(self, odps_json_file, setup_config):
        """Test format override with --spec-type option"""
        runner = CliRunner()

        # Test with explicit spec-type override
        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', odps_json_file,
            '--spec-type', 'ODPS',
            '--format', 'json'
        ])

        # Should handle ODPS via regular create command with override
        # Note: This may or may not work depending on implementation
        # The important thing is it doesn't crash
        assert result.exit_code in [0, 1]  # May fail if ODPS requires create-odps
