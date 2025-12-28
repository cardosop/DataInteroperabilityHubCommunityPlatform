"""
Integration tests for ODCS export commands against real API service.

These tests test the CLI export commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest tests/integration/test_odcs_export.py -v
"""
import pytest
import requests
import json
import os
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import config


def _check_api_available():
    """Check if API service is available"""
    try:
        response = requests.get("http://localhost:8000/api/v1/", timeout=2)
        return response.status_code < 600  # Any HTTP response means API is up
    except Exception:
        return False


@pytest.fixture(scope="module")
def api_available():
    """Fixture to check if API service is available"""
    return _check_api_available()


class TestODCSExportIntegration:
    """Integration tests for ODCS export commands with real API"""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up API base URL to point to Docker Compose service"""
        # Use the running Docker Compose API service
        api_base_url = "http://localhost:8000/api/v1"
        config.set_api_base_url(api_base_url)

        # Try to get API key from environment, config, or create one
        api_key = (
            os.environ.get('DATAHUB_API_KEY') or
            config.get_api_key() or
            self._create_test_api_key()
        )

        if not api_key:
            # If we can't get/create an API key, tests will skip with helpful message
            self.api_key = None
        else:
            config.set_api_key(api_key)
            self.api_key = api_key

        yield
        # Cleanup
        config.clear_auth()

    def _create_test_api_key(self):
        """Create a test API key via Django shell in the API service container"""
        import subprocess

        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.auth.models import APIKey
import os

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='odcs-export-cli-test-tenant',
    defaults={'name': 'ODCS Export CLI Test Tenant'}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='odcs-export-cli-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Delete existing API key if it exists
APIKey.objects.filter(user=user, name='ODCS Export CLI Test Key').delete()

# Create new API key
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='ODCS Export CLI Test Key',
    key_hash=api_key_hash
)
print(api_key_value)
"""

        try:
            result = subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell'],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=30,
                cwd='/home/ph/Desktop/DataInteroperabilityHub'
            )

            if result.returncode == 0:
                # Extract API key from output (should be the last line)
                output_lines = result.stdout.strip().split('\n')
                for line in reversed(output_lines):
                    line = line.strip()
                    if line and len(line) > 20:  # API keys are typically long
                        return line
        except Exception as e:
            # If docker compose exec fails, that's OK - tests will skip
            pass

        return None

    @pytest.fixture
    def runner(self):
        """CLI runner fixture"""
        return CliRunner()

    def _get_auth_headers(self):
        """Get authentication headers for HTTP requests"""
        return {
            'Authorization': f'ApiKey {self.api_key}',
            'Content-Type': 'application/json'
        }

    def _create_odcs_contract_via_api(self, contract_id, api_version="odcs.io/v3.0.2"):
        """
        Create an ODCS contract via HTTP request to the live server.

        Returns the created contract data as a dict.
        """
        odcs_content = json.dumps({
            "apiVersion": api_version,
            "kind": "DataContract",
            "id": contract_id,
            "name": f"CLI Test Contract {contract_id}",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": True
                    }
                ]
            }
        })

        # URL structure: /api/v1/contracts/ (as per API documentation)
        url = "http://localhost:8000/api/v1/contracts/"
        data = {
            'original_raw': odcs_content,
            'original_format': 'JSON',
            'original_spec_type': 'ODCS'
        }

        try:
            response = requests.post(url, json=data, headers=self._get_auth_headers(), timeout=10)
            if response.status_code == 401 or response.status_code == 403:
                pytest.skip(f"Authentication failed (status {response.status_code}). Set DATAHUB_API_KEY environment variable.")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # If it's an authentication error, skip with helpful message
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code in [401, 403]:
                    pytest.skip(f"Authentication failed. Set DATAHUB_API_KEY environment variable.")
            pytest.skip(f"API request failed: {e}")

    def test_export_odcs_all_versions_json(self, runner, api_available):
        """Test exporting ODCS with all supported versions as JSON"""
        if not api_available:
            pytest.skip("API service not available")

        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY or ensure docker compose is running.")

        supported_versions = ['3.0.2', '3.0.1', '3.0.0', '3.0.0-preview', '2.2.2']

        for version in supported_versions:
            contract_id = f"cli-test-odcs-export-{version.replace('.', '-').replace('-preview', 'preview')}"
            api_version = f"odcs.io/v{version}"

            # Create contract via API
            contract_data = self._create_odcs_contract_via_api(contract_id, api_version)
            if not contract_data:
                pytest.skip("Could not create test contract")

            contract_id_actual = contract_data['id']

            # Test export with ODCS format and version
            result = runner.invoke(cli, [
                'contracts', 'export', contract_id_actual,
                '--format', 'odcs',
                '--version', version,
                '--output-format', 'json',
                '--cli-format', 'json'
            ])

            assert result.exit_code == 0, f"Failed for version {version}: {result.output}"
            # Should contain ODCS content
            assert 'apiVersion' in result.output or 'odcs' in result.output.lower() or 'kind' in result.output

    def test_export_odcs_all_versions_yaml(self, runner, api_available):
        """Test exporting ODCS with all supported versions as YAML"""
        if not api_available:
            pytest.skip("API service not available")

        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY or ensure docker compose is running.")

        supported_versions = ['3.0.2', '3.0.1', '3.0.0', '3.0.0-preview', '2.2.2']

        for version in supported_versions:
            contract_id = f"cli-test-odcs-export-yaml-{version.replace('.', '-').replace('-preview', 'preview')}"
            api_version = f"odcs.io/v{version}"

            # Create contract via API
            contract_data = self._create_odcs_contract_via_api(contract_id, api_version)
            if not contract_data:
                pytest.skip("Could not create test contract")

            contract_id_actual = contract_data['id']

            # Test export with ODCS format, version, and YAML output
            result = runner.invoke(cli, [
                'contracts', 'export', contract_id_actual,
                '--format', 'odcs',
                '--version', version,
                '--output-format', 'yaml',
                '--cli-format', 'table'
            ])

            assert result.exit_code == 0, f"Failed for version {version}: {result.output}"
            # Should show export success or contain ODCS content
            assert 'exported successfully' in result.output.lower() or 'apiVersion' in result.output.lower() or 'odcs' in result.output.lower()

    def test_export_odcs_format_conversion_json_to_yaml(self, runner, api_available):
        """Test exporting ODCS with format conversion from JSON to YAML"""
        if not api_available:
            pytest.skip("API service not available")

        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY or ensure docker compose is running.")

        contract_id = "cli-test-odcs-format-conv-json-yaml"

        # Create contract via API
        contract_data = self._create_odcs_contract_via_api(contract_id, "odcs.io/v3.0.2")
        if not contract_data:
            pytest.skip("Could not create test contract")

        contract_id_actual = contract_data.get('id') or contract_id

        # Test export with JSON input, YAML output
        result = runner.invoke(cli, [
            'contracts', 'export', contract_id_actual,
            '--format', 'odcs',
            '--version', '3.0.2',
            '--output-format', 'yaml',
            '--cli-format', 'json'
        ])

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        # Should return YAML content
        assert 'apiVersion' in result.output or 'kind' in result.output or 'odcs' in result.output.lower()

    def test_export_odcs_format_conversion_yaml_to_json(self, runner, api_available):
        """Test exporting ODCS with format conversion from YAML to JSON"""
        if not api_available:
            pytest.skip("API service not available")

        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY or ensure docker compose is running.")

        contract_id = "cli-test-odcs-format-conv-yaml-json"

        # Create contract via API
        contract_data = self._create_odcs_contract_via_api(contract_id, "odcs.io/v3.0.2")
        if not contract_data:
            pytest.skip("Could not create test contract")

        contract_id_actual = contract_data.get('id') or contract_id

        # Test export with YAML input, JSON output
        result = runner.invoke(cli, [
            'contracts', 'export', contract_id_actual,
            '--format', 'odcs',
            '--version', '3.0.2',
            '--output-format', 'json',
            '--cli-format', 'table'
        ])

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        # Should show export success or contain JSON content
        assert 'exported successfully' in result.output.lower() or 'apiVersion' in result.output or 'odcs' in result.output.lower()

    def test_export_odcs_error_handling_invalid_version(self, runner, api_available):
        """Test error handling for invalid ODCS version"""
        if not api_available:
            pytest.skip("API service not available")

        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY or ensure docker compose is running.")

        contract_id = "cli-test-odcs-error-invalid-version"

        # Create contract via API
        contract_data = self._create_odcs_contract_via_api(contract_id, "odcs.io/v3.0.2")
        if not contract_data:
            pytest.skip("Could not create test contract")

        contract_id_actual = contract_data.get('id') or contract_id

        # Test export with invalid version (should fail validation before API call)
        result = runner.invoke(cli, [
            'contracts', 'export', contract_id_actual,
            '--format', 'odcs',
            '--version', 'invalid-version'
        ])

        assert result.exit_code != 0, "Should fail with invalid version"
        assert 'Invalid ODCS version format' in result.output or 'invalid' in result.output.lower()

    def test_export_odcs_error_handling_unsupported_version(self, runner, api_available):
        """Test error handling for unsupported ODCS version"""
        if not api_available:
            pytest.skip("API service not available")

        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY or ensure docker compose is running.")

        contract_id = "cli-test-odcs-error-unsupported-version"

        # Create contract via API
        contract_data = self._create_odcs_contract_via_api(contract_id, "odcs.io/v3.0.2")
        if not contract_data:
            pytest.skip("Could not create test contract")

        contract_id_actual = contract_data.get('id') or contract_id

        # Test export with unsupported version (should fail validation before API call)
        result = runner.invoke(cli, [
            'contracts', 'export', contract_id_actual,
            '--format', 'odcs',
            '--version', '99.99.99'
        ])

        assert result.exit_code != 0, "Should fail with unsupported version"
        assert 'not supported' in result.output.lower()

    def test_export_odcs_error_handling_nonexistent_contract(self, runner, api_available):
        """Test error handling for nonexistent contract"""
        if not api_available:
            pytest.skip("API service not available")

        # Test export with nonexistent contract ID
        result = runner.invoke(cli, [
            'contracts', 'export', '00000000-0000-0000-0000-000000000000',
            '--format', 'odcs',
            '--version', '3.0.2'
        ])

        # Should fail with not found error
        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or 'error' in result.output.lower() or 'failed' in result.output.lower()

    def test_export_odcs_with_version_table_output(self, runner, api_available):
        """Test ODCS export with version showing table output format"""
        if not api_available:
            pytest.skip("API service not available")

        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY or ensure docker compose is running.")

        contract_id = "cli-test-odcs-table-output"

        # Create contract via API
        contract_data = self._create_odcs_contract_via_api(contract_id, "odcs.io/v3.0.2")
        if not contract_data:
            pytest.skip("Could not create test contract")

        contract_id_actual = contract_data.get('id') or contract_id

        # Test export with table output format
        result = runner.invoke(cli, [
            'contracts', 'export', contract_id_actual,
            '--format', 'odcs',
            '--version', '3.0.2',
            '--output-format', 'json',
            '--cli-format', 'table'
        ])

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        # Should show export info in table format
        assert 'exported successfully' in result.output.lower() or 'Contract ID' in result.output
        assert 'ODCS Version: 3.0.2' in result.output or '3.0.2' in result.output
        assert 'Format: odcs' in result.output or 'odcs' in result.output.lower()

    def test_export_odcs_without_version_uses_default(self, runner, api_available):
        """Test ODCS export without version parameter uses default"""
        if not api_available:
            pytest.skip("API service not available")

        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY or ensure docker compose is running.")

        contract_id = "cli-test-odcs-no-version"

        # Create contract via API
        contract_data = self._create_odcs_contract_via_api(contract_id, "odcs.io/v3.0.2")
        if not contract_data:
            pytest.skip("Could not create test contract")

        contract_id_actual = contract_data.get('id') or contract_id

        # Test export without version parameter
        result = runner.invoke(cli, [
            'contracts', 'export', contract_id_actual,
            '--format', 'odcs',
            '--output-format', 'json'
        ])

        # Should succeed (API will use default or detected version)
        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        assert 'apiVersion' in result.output or 'odcs' in result.output.lower() or 'exported successfully' in result.output.lower()

    def test_export_odcs_preview_version(self, runner, api_available):
        """Test ODCS export with preview version"""
        if not api_available:
            pytest.skip("API service not available")

        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY or ensure docker compose is running.")

        contract_id = "cli-test-odcs-preview"

        # Create contract via API with preview version
        contract_data = self._create_odcs_contract_via_api(contract_id, "odcs.io/v3.0.0-preview")
        if not contract_data:
            pytest.skip("Could not create test contract")

        contract_id_actual = contract_data['id']

        # Test export with preview version
        result = runner.invoke(cli, [
            'contracts', 'export', contract_id_actual,
            '--format', 'odcs',
            '--version', '3.0.0-preview',
            '--output-format', 'json'
        ])

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        assert 'apiVersion' in result.output or 'odcs' in result.output.lower() or 'exported successfully' in result.output.lower()
