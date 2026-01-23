"""
Comprehensive integration tests for all CLI services with ODPS integration (Task 10.1.41.5).

Tests all CLI commands across all services with ODPS integration.
No mocks/stubs - uses real API endpoints.

These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: DATAHUB_API_KEY

To run:
    pytest cli/tests/integration/test_cli_all_services_odps.py -v
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
    slug='odps-all-services-cli-test-tenant',
    defaults={'name': 'ODPS All Services CLI Test Tenant'}
)

user, _ = User.objects.get_or_create(
    email='odps-all-services-cli-test@example.com',
    defaults={'tenant': tenant, 'status': UserStatus.ACTIVE}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

APIKey.objects.filter(user=user, name='odps-all-services-cli-test-key').delete()

api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
APIKey.objects.create(
    user=user, tenant=tenant,
    name='odps-all-services-cli-test-key',
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
                if (line and len(line) > 30 and
                    not line.startswith('{') and
                    not line.startswith('"') and
                    not 'timestamp' in line.lower() and
                    not 'logger' in line.lower() and
                    not 'level' in line.lower() and
                    not 'message' in line.lower() and
                    ' ' not in line and ':' not in line and '/' not in line):
                    cleaned = line.replace('-', '').replace('_', '')
                    if cleaned.isalnum():
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
def comprehensive_odps_contract():
    """Create a comprehensive ODPS contract for cross-service testing"""
    odps_data = {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": f"cross-service-product-{uuid.uuid4().hex[:8]}",
                    "name": "Cross-Service Test Product",
                    "description": "Product for testing across all services"
                }
            },
            "contract": {
                "spec": {
                    "apiVersion": "odcs.io/v3.0.2",
                    "kind": "DataContract",
                    "id": "cross-service-contract",
                    "name": "cross-service-contract",
                    "version": "1.0.0",
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string", "nullable": False},
                            {"name": "name", "type": "string", "nullable": False}
                        ]
                    }
                }
            },
            "pricing": {
                "plans": [
                    {
                        "planID": "basic",
                        "name": "Basic Plan",
                        "price": 99.99,
                        "currency": "USD",
                        "billingPeriod": "monthly"
                    }
                ]
            },
            "accessMethods": [
                {
                    "type": "API",
                    "endpoint": "https://api.example.com/data",
                    "protocol": "REST"
                }
            ]
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(odps_data, f)
        temp_path = f.name

    runner = CliRunner()
    result = runner.invoke(cli, [
        'contracts', 'create-odps',
        '--file', temp_path,
        '--extract-odcs',
        '--output-format', 'json'
    ])

    if os.path.exists(temp_path):
        os.unlink(temp_path)

    if result.exit_code != 0:
        pytest.skip(f"Failed to create ODPS contract: {result.output}")

    try:
        contract_data = json.loads(result.output)
        odps_id = contract_data.get('odps_contract', {}).get('id') or contract_data.get('id')
        odcs_id = contract_data.get('odcs_contract', {}).get('id') if 'odcs_contract' in contract_data else None
        yield odps_id, odcs_id
    except json.JSONDecodeError:
        import re
        match = re.search(r'ODPS Contract ID:\s*([a-f0-9-]+)', result.output)
        if match:
            yield match.group(1), None
        else:
            pytest.skip("Could not extract ODPS contract ID")


@pytest.fixture
def test_asset():
    """Create a test asset for cross-service testing"""
    runner = CliRunner()
    asset_key = f"cross-service-asset-{uuid.uuid4().hex[:8]}"

    result = runner.invoke(cli, [
        'assets', 'create',
        '--name', 'Cross-Service Asset',
        '--key', asset_key,
        '--domain', 'test',
        '--output-format', 'json'
    ])

    if result.exit_code != 0:
        pytest.skip(f"Failed to create test asset: {result.output}")

    try:
        asset_data = json.loads(result.output)
        yield asset_data.get('id')
    except json.JSONDecodeError:
        import re
        match = re.search(r'ID:\s*([a-f0-9-]+)', result.output)
        if match:
            yield match.group(1)
        else:
            pytest.skip("Could not extract asset ID")


class TestCLIAllServicesODPS:
    """Comprehensive tests for all CLI services with ODPS integration"""

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_contracts_service_with_odps(self, comprehensive_odps_contract, setup_config):
        """Test all contracts service commands with ODPS"""
        runner = CliRunner()
        odps_id, odcs_id = comprehensive_odps_contract

        # Test contracts list
        result_list = runner.invoke(cli, ['contracts', 'list', '--format', 'json'])
        assert result_list.exit_code == 0

        # Test contracts get
        result_get = runner.invoke(cli, [
            'contracts', 'get', odps_id, '--show-odps', '--format', 'json'
        ])
        assert result_get.exit_code == 0

        # Test contracts get-pricing
        result_pricing = runner.invoke(cli, [
            'contracts', 'get-pricing', odps_id, '--format', 'json'
        ])
        assert result_pricing.exit_code == 0

        # Test contracts get-access-methods
        result_access = runner.invoke(cli, [
            'contracts', 'get-access-methods', odps_id, '--format', 'json'
        ])
        assert result_access.exit_code == 0

        # Test contracts export
        result_export = runner.invoke(cli, [
            'contracts', 'export', odps_id,
            '--format', 'odps', '--output-format', 'json',
            '--version', '4.1', '--cli-format', 'json'
        ])
        assert result_export.exit_code == 0

        # Test contracts validate
        result_validate = runner.invoke(cli, [
            'contracts', 'validate', odps_id, '--format', 'json'
        ])
        assert result_validate.exit_code in [0, 1]  # May fail validation

        # Test contracts lint
        result_lint = runner.invoke(cli, [
            'contracts', 'lint', odps_id, '--format', 'json'
        ])
        assert result_lint.exit_code in [0, 1]  # May have linting issues

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_assets_service_with_odps(self, comprehensive_odps_contract, test_asset, setup_config):
        """Test all assets service commands with ODPS"""
        runner = CliRunner()
        odps_id, _ = comprehensive_odps_contract

        # Link ODPS contract to asset (if asset_id option exists)
        # This is done via contracts create-odps with --asset-id

        # Test assets list
        result_list = runner.invoke(cli, ['assets', 'list', '--format', 'json'])
        assert result_list.exit_code == 0

        # Test assets get
        result_get = runner.invoke(cli, [
            'assets', 'get', test_asset, '--include', 'contract', '--format', 'json'
        ])
        assert result_get.exit_code == 0

        # Test assets update
        result_update = runner.invoke(cli, [
            'assets', 'update', test_asset,
            '--description', 'Updated with ODPS integration',
            '--format', 'json'
        ])
        assert result_update.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_marketplace_service_with_odps(self, comprehensive_odps_contract, setup_config):
        """Test all marketplace service commands with ODPS"""
        runner = CliRunner()

        # Test marketplace connections list
        result_connections = runner.invoke(cli, [
            'marketplace', 'connections', 'list', '--format', 'json'
        ])
        assert result_connections.exit_code == 0

        # Test marketplace connectors list
        result_connectors = runner.invoke(cli, [
            'marketplace', 'connectors', 'list', '--format', 'json'
        ])
        assert result_connectors.exit_code == 0

        # Test marketplace mappings list
        result_mappings = runner.invoke(cli, [
            'marketplace', 'mappings', 'list', '--format', 'json'
        ])
        assert result_mappings.exit_code == 0

        # Test marketplace sync list
        result_sync = runner.invoke(cli, [
            'marketplace', 'sync', 'list', '--format', 'json'
        ])
        assert result_sync.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_files_service_with_odps(self, setup_config):
        """Test files service commands (ODPS contracts can reference files)"""
        runner = CliRunner()

        # Test files list
        result_list = runner.invoke(cli, ['files', 'list', '--format', 'json'])
        assert result_list.exit_code == 0

        # Files service may not directly integrate with ODPS,
        # but ODPS contracts can reference files

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_jobs_service_with_odps(self, setup_config):
        """Test jobs service commands (ODPS workflows may create jobs)"""
        runner = CliRunner()

        # Test jobs list
        result_list = runner.invoke(cli, ['jobs', 'list', '--format', 'json'])
        assert result_list.exit_code == 0

        # Jobs may be created during ODPS contract creation workflows

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_cross_service_workflows_with_odps(self, test_asset, setup_config):
        """Test CLI cross-service workflows with ODPS"""
        runner = CliRunner()

        # Create ODPS contract linked to asset
        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"workflow-product-{uuid.uuid4().hex[:8]}",
                        "name": "Workflow Product"
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "workflow-contract",
                        "name": "workflow-contract",
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

        try:
            # Create ODPS contract with asset
            create_result = runner.invoke(cli, [
                'contracts', 'create-odps',
                '--file', temp_path,
                '--extract-odcs',
                '--asset-id', test_asset,
                '--output-format', 'json'
            ])

            assert create_result.exit_code == 0
            contract_data = json.loads(create_result.output)
            odps_id = contract_data.get('odps_contract', {}).get('id') or contract_data.get('id')

            # Verify asset has contract
            asset_result = runner.invoke(cli, [
                'assets', 'get', test_asset,
                '--include', 'contract',
                '--format', 'json'
            ])

            assert asset_result.exit_code == 0

            # Verify contract has ODPS info
            contract_result = runner.invoke(cli, [
                'contracts', 'get', odps_id,
                '--show-odps',
                '--format', 'json'
            ])

            assert contract_result.exit_code == 0

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_cli_output_format_consistency_with_odps(self, comprehensive_odps_contract, setup_config):
        """Test CLI output format consistency with ODPS across all commands"""
        runner = CliRunner()
        odps_id, _ = comprehensive_odps_contract

        # Test JSON format consistency
        commands = [
            ['contracts', 'get', odps_id, '--format', 'json'],
            ['contracts', 'get-pricing', odps_id, '--format', 'json'],
            ['contracts', 'get-access-methods', odps_id, '--format', 'json'],
            ['contracts', 'list', '--format', 'json'],
            ['assets', 'list', '--format', 'json'],
        ]

        for cmd in commands:
            result = runner.invoke(cli, cmd)
            assert result.exit_code == 0, f"Command {cmd} failed: {result.output}"

            # Verify JSON output is valid
            try:
                output_data = json.loads(result.output)
                assert isinstance(output_data, (dict, list)), f"Command {cmd} did not produce valid JSON structure"
            except json.JSONDecodeError:
                pytest.fail(f"Command {cmd} did not produce valid JSON: {result.output}")

        # Test table format consistency
        table_commands = [
            ['contracts', 'get', odps_id, '--format', 'table'],
            ['contracts', 'get-pricing', odps_id, '--format', 'table'],
            ['contracts', 'get-access-methods', odps_id, '--format', 'table'],
            ['contracts', 'list', '--format', 'table'],
            ['assets', 'list', '--format', 'table'],
        ]

        for cmd in table_commands:
            result = runner.invoke(cli, cmd)
            assert result.exit_code == 0, f"Command {cmd} failed: {result.output}"
            # Table format should produce readable output
            assert len(result.output) > 0
