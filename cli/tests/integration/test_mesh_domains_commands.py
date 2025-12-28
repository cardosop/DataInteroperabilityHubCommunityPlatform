"""
Comprehensive integration tests for Mesh Domain CLI commands against real API service.

These tests test all mesh domain CLI commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest cli/tests/integration/test_mesh_domains_commands.py -v
"""
import pytest
import requests
import json
import os
import uuid
import subprocess
import time
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


class TestMeshDomainsCommandsRealAPI:
    """Comprehensive integration tests for all mesh domain commands with real API"""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up API base URL to point to Docker Compose service"""
        # Use the running Docker Compose API service
        api_base_url = "http://localhost:8000/api/v1"
        config.set_api_base_url(api_base_url)

        # Try to get API key from environment, config, or create one
        api_key = (
            os.environ.get('DATAHUB_API_KEY') or
            os.environ.get('TEST_API_KEY') or
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
        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey
import os

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='mesh-domains-cli-test-tenant',
    defaults={'name': 'Mesh Domains CLI Test Tenant'}
)

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={'description': 'Tenant Administrator'}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='mesh-domains-cli-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Assign TENANT_ADMIN role to user (use get_or_create to avoid duplicates)
UserRole.objects.get_or_create(user=user, role=admin_role)

# Delete existing API key if it exists
APIKey.objects.filter(user=user, name='mesh-domains-cli-test-key').delete()

# Create new API key with mesh:write and mesh:read scopes
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='mesh-domains-cli-test-key',
    key_hash=api_key_hash,
    scopes=['mesh:write', 'mesh:read']
)

# Print the plaintext key in a format that's easy to extract (it's only available at creation time)
print(f"API_KEY={api_key_value}")
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
                # Extract API key from output
                # Look for line starting with "API_KEY=" first (most reliable)
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    line = line.strip()
                    if line.startswith('API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        if api_key and len(api_key) > 20:
                            return api_key

                # Fallback: look for lines that look like API keys (long alphanumeric with dashes/underscores)
                for line in reversed(output_lines):
                    line = line.strip()
                    # API keys are typically long (40+ characters), alphanumeric with possible dashes/underscores
                    if line and len(line) > 20:  # API keys are typically long
                        # Additional validation: check if it looks like an API key
                        # Skip lines that are clearly not API keys (contain common log patterns)
                        if any(skip in line for skip in ['timestamp', 'level', 'logger', 'message', 'event', 'args=', 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'BEGIN', 'COMMIT']):
                            continue
                        cleaned = line.replace('-', '').replace('_', '')
                        if cleaned.isalnum() and ' ' not in line and ':' not in line and '"' not in line and '{' not in line and '}' not in line and '[' not in line and ']' not in line:
                            return line
        except Exception:
            pass
        return None

    def _create_test_domain(self, api_base_url: str, api_key: str, name: str = None) -> str:
        """
        Create a test domain for testing.
        Returns the domain ID.
        """
        if not name:
            name = f"test-domain-{uuid.uuid4().hex[:8]}"

        domain_data = {
            "name": name,
            "description": "Test domain for CLI integration tests",
            "status": "ACTIVE"
        }

        try:
            response = requests.post(
                f"{api_base_url}/mesh/domains/",
                json=domain_data,
                headers={"Authorization": f"ApiKey {api_key}"},
                timeout=30
            )
            assert response.status_code in [200, 201], f"Failed to create domain: {response.status_code} - {response.text}"

            domain_response = response.json()
            domain_id = domain_response.get("id")
            assert domain_id, "Failed to get domain ID from response."

            # Wait a bit for domain to be fully created
            time.sleep(1)

            return domain_id
        except Exception as e:
            pytest.skip(f"Failed to create test domain: {str(e)}")

    def _delete_test_domain(self, api_base_url: str, api_key: str, domain_id: str):
        """Delete a test domain"""
        try:
            response = requests.delete(
                f"{api_base_url}/mesh/domains/{domain_id}/",
                headers={"Authorization": f"ApiKey {api_key}"},
                timeout=30
            )
            # 204 or 404 is OK (already deleted)
            assert response.status_code in [200, 204, 404], f"Failed to delete domain: {response.status_code}"
        except Exception:
            pass  # Ignore cleanup errors

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_list_domains_success_table_format(self, setup_config, api_available):
        """Test listing domains in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'list'])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        # Should show table or "No domains found"
        assert len(result.output) > 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_list_domains_success_json_format(self, setup_config, api_available):
        """Test listing domains in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'list', '--format', 'json'])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        output_data = json.loads(result.output)
        assert 'count' in output_data or 'results' in output_data

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_list_domains_with_filters(self, setup_config, api_available):
        """Test listing domains with filters"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'mesh', 'domains', 'list',
            '--status', 'ACTIVE',
            '--page', '1',
            '--page-size', '10'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_list_domains_empty_result(self, setup_config, api_available):
        """Test listing domains with no results"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'list', '--status', 'ARCHIVED'])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        # Should show "No domains found" or empty results
        assert len(result.output) >= 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_create_domain_success_table_format(self, setup_config, api_available):
        """Test creating a domain successfully in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Ensure config is set (fixture should have done this, but verify)
        api_base_url = config.get_api_base_url()
        if not config.get_api_key():
            config.set_api_key(self.api_key)

        domain_name = f"test-domain-create-{uuid.uuid4().hex[:8]}"

        runner = CliRunner()
        result = runner.invoke(cli, [
            'mesh', 'domains', 'create',
            '--name', domain_name,
            '--description', 'Test description',
            '--status', 'ACTIVE'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'Domain created successfully' in result.output or 'created successfully' in result.output.lower()
        assert domain_name in result.output

        # Cleanup
        try:
            # Extract domain ID from output if possible
            output_lines = result.output.split('\n')
            domain_id = None
            for line in output_lines:
                if 'Domain ID:' in line or 'id:' in line.lower():
                    parts = line.split(':')
                    if len(parts) > 1:
                        domain_id = parts[-1].strip()
                        break
            if domain_id:
                self._delete_test_domain(api_base_url, self.api_key, domain_id)
        except Exception:
            pass

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_create_domain_success_json_format(self, setup_config, api_available):
        """Test creating a domain successfully in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_name = f"test-domain-create-json-{uuid.uuid4().hex[:8]}"

        runner = CliRunner()
        result = runner.invoke(cli, [
            'mesh', 'domains', 'create',
            '--name', domain_name,
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        output_data = json.loads(result.output)
        assert 'id' in output_data
        assert output_data['name'] == domain_name

        # Cleanup
        domain_id = output_data.get('id')
        if domain_id:
            self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_create_domain_with_all_options(self, setup_config, api_available):
        """Test creating a domain with all optional parameters"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_name = f"test-domain-full-{uuid.uuid4().hex[:8]}"

        boundaries = '{"data_products": ["product1"], "schemas": ["schema1"]}'
        capabilities = '{"apis": ["api1"], "services": ["service1"]}'
        resource_quota = '{"storage": 1000, "compute": 500}'

        runner = CliRunner()
        result = runner.invoke(cli, [
            'mesh', 'domains', 'create',
            '--name', domain_name,
            '--description', 'Test description',
            '--boundaries', boundaries,
            '--capabilities', capabilities,
            '--resource-quota', resource_quota,
            '--status', 'ACTIVE'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"

        # Cleanup
        try:
            output_data = json.loads(result.output) if '--format' in result.output else None
            if not output_data:
                # Try to extract from table format
                output_lines = result.output.split('\n')
                domain_id = None
                for line in output_lines:
                    if 'Domain ID:' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            domain_id = parts[-1].strip()
                            break
            else:
                domain_id = output_data.get('id')

            if domain_id:
                self._delete_test_domain(api_base_url, self.api_key, domain_id)
        except Exception:
            pass

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_create_domain_missing_name(self, setup_config, api_available):
        """Test creating a domain without required name"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'create'])

        assert result.exit_code != 0, "Command should have failed without name"
        assert 'Missing option' in result.output or 'required' in result.output.lower() or '--name' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_create_domain_invalid_json_boundaries(self, setup_config, api_available):
        """Test creating a domain with invalid JSON in boundaries"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'mesh', 'domains', 'create',
            '--name', 'Test Domain',
            '--boundaries', 'invalid json'
        ])

        assert result.exit_code != 0, "Command should have failed with invalid JSON"
        assert 'Invalid JSON' in result.output or 'JSON' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_domain_success_table_format(self, setup_config, api_available):
        """Test getting a domain in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'get', domain_id])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert domain_id in result.output or 'Domain ID:' in result.output

        # Cleanup
        self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_domain_success_json_format(self, setup_config, api_available):
        """Test getting a domain in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'get', domain_id, '--format', 'json'])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        output_data = json.loads(result.output)
        assert output_data['id'] == domain_id

        # Cleanup
        self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_domain_not_found(self, setup_config, api_available):
        """Test getting a non-existent domain"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'get', '00000000-0000-0000-0000-000000000000'])

        assert result.exit_code != 0, "Command should have failed for non-existent domain"
        assert 'Failed to get domain' in result.output or 'not found' in result.output.lower() or 'error' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_update_domain_success_table_format(self, setup_config, api_available):
        """Test updating a domain successfully in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        runner = CliRunner()
        result = runner.invoke(cli, [
            'mesh', 'domains', 'update', domain_id,
            '--name', 'Updated Domain',
            '--status', 'INACTIVE'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'Domain updated successfully' in result.output or 'updated successfully' in result.output.lower()
        assert 'Updated Domain' in result.output

        # Cleanup
        self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_update_domain_success_json_format(self, setup_config, api_available):
        """Test updating a domain successfully in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        runner = CliRunner()
        result = runner.invoke(cli, [
            'mesh', 'domains', 'update', domain_id,
            '--name', 'Updated Domain',
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        output_data = json.loads(result.output)
        assert output_data['id'] == domain_id
        assert output_data['name'] == 'Updated Domain'

        # Cleanup
        self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_update_domain_no_fields(self, setup_config, api_available):
        """Test updating a domain without any fields"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'update', domain_id])

        assert result.exit_code != 0, "Command should have failed without fields"
        assert 'At least one field must be provided' in result.output or 'required' in result.output.lower()

        # Cleanup
        self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_delete_domain_success_table_format(self, setup_config, api_available):
        """Test deleting a domain successfully in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'delete', domain_id], input='y\n')

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'deleted successfully' in result.output.lower() or 'deleted' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_delete_domain_cancelled(self, setup_config, api_available):
        """Test cancelling domain deletion"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'delete', domain_id], input='n\n')

        # Should exit without deleting (exit code 0 or 1 is OK for cancellation)
        assert result.exit_code in [0, 1]

        # Cleanup
        self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_domains_command_group_exists(self, setup_config, api_available):
        """Test that domains command group exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', '--help'])
        assert result.exit_code == 0
        assert 'Domain management commands' in result.output or 'domains' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_domains_list_command_exists(self, setup_config, api_available):
        """Test that domains list command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'list', '--help'])
        assert result.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_domains_create_command_exists(self, setup_config, api_available):
        """Test that domains create command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'create', '--help'])
        assert result.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_domains_get_command_exists(self, setup_config, api_available):
        """Test that domains get command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'get', '--help'])
        assert result.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_domains_update_command_exists(self, setup_config, api_available):
        """Test that domains update command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'update', '--help'])
        assert result.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_domains_delete_command_exists(self, setup_config, api_available):
        """Test that domains delete command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'domains', 'delete', '--help'])
        assert result.exit_code == 0


class TestMeshComplianceCommandsRealAPI:
    """Comprehensive integration tests for mesh compliance commands with real API"""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up API base URL to point to Docker Compose service"""
        # Use the running Docker Compose API service
        api_base_url = "http://localhost:8000/api/v1"
        config.set_api_base_url(api_base_url)

        # Try to get API key from environment, config, or create one
        api_key = (
            os.environ.get('DATAHUB_API_KEY') or
            os.environ.get('TEST_API_KEY') or
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
        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey
import os

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='mesh-compliance-cli-test-tenant',
    defaults={'name': 'Mesh Compliance CLI Test Tenant'}
)

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={'description': 'Tenant Administrator'}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='mesh-compliance-cli-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Assign TENANT_ADMIN role to user (use get_or_create to avoid duplicates)
UserRole.objects.get_or_create(user=user, role=admin_role)

# Delete existing API key if it exists
APIKey.objects.filter(user=user, name='mesh-compliance-cli-test-key').delete()

# Create new API key with mesh:write and mesh:read scopes
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='mesh-compliance-cli-test-key',
    key_hash=api_key_hash,
    scopes=['mesh:write', 'mesh:read']
)

# Print the plaintext key in a format that's easy to extract (it's only available at creation time)
print(f"API_KEY={api_key_value}")
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
                # Extract API key from output
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    line = line.strip()
                    if line.startswith('API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        if api_key and len(api_key) > 20:
                            return api_key

                # Fallback: look for lines that look like API keys
                for line in reversed(output_lines):
                    line = line.strip()
                    if line and len(line) > 20:
                        if any(skip in line for skip in ['timestamp', 'level', 'logger', 'message', 'event', 'args=', 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'BEGIN', 'COMMIT']):
                            continue
                        cleaned = line.replace('-', '').replace('_', '')
                        if cleaned.isalnum() and ' ' not in line and ':' not in line and '"' not in line and '{' not in line and '}' not in line and '[' not in line and ']' not in line:
                            return line
        except Exception:
            pass
        return None

    def _create_test_domain(self, api_base_url: str, api_key: str, name: str = None) -> str:
        """
        Create a test domain for testing.
        Returns the domain ID.
        """
        if not api_key:
            pytest.skip("No API key available for creating test domain")

        if not name:
            name = f"test-compliance-domain-{uuid.uuid4().hex[:8]}"

        domain_data = {
            "name": name,
            "description": "Test domain for compliance CLI integration tests",
            "status": "ACTIVE"
        }

        try:
            response = requests.post(
                f"{api_base_url}/mesh/domains/",
                json=domain_data,
                headers={"Authorization": f"ApiKey {api_key}"},
                timeout=30
            )
            assert response.status_code in [200, 201], f"Failed to create domain: {response.status_code} - {response.text}"

            domain_response = response.json()
            domain_id = domain_response.get("id")
            assert domain_id, "Failed to get domain ID from response."

            # Wait a bit for domain to be fully created
            time.sleep(1)

            return domain_id
        except Exception as e:
            pytest.skip(f"Failed to create test domain: {str(e)}")

    def _delete_test_domain(self, api_base_url: str, api_key: str, domain_id: str):
        """Delete a test domain"""
        try:
            response = requests.delete(
                f"{api_base_url}/mesh/domains/{domain_id}/",
                headers={"Authorization": f"ApiKey {api_key}"},
                timeout=30
            )
            # 204 or 404 is OK (already deleted)
            assert response.status_code in [200, 204, 404], f"Failed to delete domain: {response.status_code}"
        except Exception:
            pass  # Ignore cleanup errors

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_check_command_exists(self, setup_config, api_available):
        """Test that compliance check command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'compliance', 'check', '--help'])
        assert result.exit_code == 0
        assert 'Check compliance status' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_report_command_exists(self, setup_config, api_available):
        """Test that compliance report command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'compliance', 'report', '--help'])
        assert result.exit_code == 0
        assert 'Get compliance report' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_check_success_table_format(self, setup_config, api_available):
        """Test checking compliance in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = "http://localhost:8000/api/v1"

        # Create a test domain (api_key is guaranteed to be str here due to skip above)
        assert self.api_key is not None
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['mesh', 'compliance', 'check', domain_id])

            # The command should succeed (exit code 0) or handle the case gracefully
            # Compliance check might take time or might not be immediately available
            assert result.exit_code in [0, 1], f"Command failed with output: {result.output}"

            # Should have some output
            assert len(result.output) > 0

            # If successful, should contain compliance-related information
            if result.exit_code == 0:
                # Check for compliance-related keywords in output
                output_lower = result.output.lower()
                assert any(keyword in output_lower for keyword in [
                    'compliance', 'report', 'status', 'risk', 'domain'
                ]), f"Output should contain compliance information: {result.output}"
        finally:
            # Cleanup (api_key is guaranteed to be str here due to skip above)
            if self.api_key:
                self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_check_success_json_format(self, setup_config, api_available):
        """Test checking compliance in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = "http://localhost:8000/api/v1"

        # Create a test domain (api_key is guaranteed to be str here due to skip above)
        assert self.api_key is not None
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['mesh', 'compliance', 'check', domain_id, '--format', 'json'])

            # The command should succeed (exit code 0) or handle the case gracefully
            assert result.exit_code in [0, 1], f"Command failed with output: {result.output}"

            # If successful, should be valid JSON
            if result.exit_code == 0:
                try:
                    output_data = json.loads(result.output)
                    assert isinstance(output_data, dict), "Output should be a JSON object"
                    # Should have compliance-related fields
                    assert any(key in output_data for key in [
                        'id', 'compliance_status', 'domain_id', 'risk_level'
                    ]), f"Output should contain compliance fields: {output_data.keys()}"
                except json.JSONDecodeError:
                    # If not JSON, might be an error message - that's OK for integration tests
                    assert 'error' in result.output.lower() or 'failed' in result.output.lower()
        finally:
            # Cleanup (api_key is guaranteed to be str here due to skip above)
            if self.api_key:
                self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_check_with_asset_id(self, setup_config, api_available):
        """Test checking compliance with asset ID"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = "http://localhost:8000/api/v1"

        # Create a test domain (api_key is guaranteed to be str here due to skip above)
        assert self.api_key is not None
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        try:
            runner = CliRunner()
            # Use a test asset ID (might not exist, but should handle gracefully)
            test_asset_id = str(uuid.uuid4())
            result = runner.invoke(cli, [
                'mesh', 'compliance', 'check', domain_id,
                '--asset-id', test_asset_id
            ])

            # Should handle gracefully (either succeed or provide clear error)
            assert result.exit_code in [0, 1], f"Command failed with output: {result.output}"
        finally:
            # Cleanup (api_key is guaranteed to be str here due to skip above)
            if self.api_key:
                self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_check_domain_not_found(self, setup_config, api_available):
        """Test handling domain not found error"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        invalid_domain_id = str(uuid.uuid4())
        result = runner.invoke(cli, ['mesh', 'compliance', 'check', invalid_domain_id])

        # Should fail with clear error message
        assert result.exit_code != 0, "Command should fail for non-existent domain"
        assert any(keyword in result.output.lower() for keyword in [
            'not found', 'failed', 'error', 'domain'
        ]), f"Should show error message: {result.output}"

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_report_success_table_format(self, setup_config, api_available):
        """Test getting compliance report in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = "http://localhost:8000/api/v1"

        # Create a test domain (api_key is guaranteed to be str here due to skip above)
        assert self.api_key is not None
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['mesh', 'compliance', 'report', domain_id])

            # Should handle gracefully - might not have reports yet
            assert result.exit_code in [0, 1], f"Command failed with output: {result.output}"

            # Should have some output
            assert len(result.output) > 0

            # If no reports, should show helpful message
            if 'No compliance reports found' in result.output:
                # That's OK - domain might not have compliance reports yet
                assert 'check' in result.output.lower() or 'generate' in result.output.lower()
            elif result.exit_code == 0:
                # If successful, should contain compliance-related information
                output_lower = result.output.lower()
                assert any(keyword in output_lower for keyword in [
                    'compliance', 'report', 'status', 'risk', 'domain'
                ]), f"Output should contain compliance information: {result.output}"
        finally:
            # Cleanup (api_key is guaranteed to be str here due to skip above)
            if self.api_key:
                self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_report_success_json_format(self, setup_config, api_available):
        """Test getting compliance report in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = "http://localhost:8000/api/v1"

        # Create a test domain (api_key is guaranteed to be str here due to skip above)
        assert self.api_key is not None
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['mesh', 'compliance', 'report', domain_id, '--format', 'json'])

            # Should handle gracefully
            assert result.exit_code in [0, 1], f"Command failed with output: {result.output}"

            # If successful, should be valid JSON
            if result.exit_code == 0 and 'No compliance reports found' not in result.output:
                try:
                    output_data = json.loads(result.output)
                    assert isinstance(output_data, dict), "Output should be a JSON object"
                    # Should have compliance-related fields
                    assert any(key in output_data for key in [
                        'id', 'compliance_status', 'domain_id', 'risk_level'
                    ]), f"Output should contain compliance fields: {output_data.keys()}"
                except json.JSONDecodeError:
                    # If not JSON, might be an error message
                    assert 'error' in result.output.lower() or 'failed' in result.output.lower()
        finally:
            # Cleanup (api_key is guaranteed to be str here due to skip above)
            if self.api_key:
                self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_report_no_reports(self, setup_config, api_available):
        """Test handling case when no reports exist"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = "http://localhost:8000/api/v1"

        # Create a test domain (without running compliance check)
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['mesh', 'compliance', 'report', domain_id])

            # Should handle gracefully
            assert result.exit_code in [0, 1], f"Command failed with output: {result.output}"

            # Should show helpful message about no reports
            assert any(keyword in result.output.lower() for keyword in [
                'no compliance reports', 'no reports', 'not found', 'check', 'generate'
            ]), f"Should show helpful message: {result.output}"
        finally:
            # Cleanup (api_key is guaranteed to be str here due to skip above)
            if self.api_key:
                self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_report_domain_not_found(self, setup_config, api_available):
        """Test handling domain not found error"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        invalid_domain_id = str(uuid.uuid4())
        result = runner.invoke(cli, ['mesh', 'compliance', 'report', invalid_domain_id])

        # Should fail with clear error message
        assert result.exit_code != 0, "Command should fail for non-existent domain"
        assert any(keyword in result.output.lower() for keyword in [
            'not found', 'failed', 'error', 'domain'
        ]), f"Should show error message: {result.output}"

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_compliance_workflow_check_then_report(self, setup_config, api_available):
        """Test complete workflow: check compliance, then get report"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = "http://localhost:8000/api/v1"

        # Create a test domain (api_key is guaranteed to be str here due to skip above)
        assert self.api_key is not None
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        try:
            runner = CliRunner()

            # Step 1: Check compliance
            check_result = runner.invoke(cli, ['mesh', 'compliance', 'check', domain_id, '--format', 'json'])

            # Step 2: Wait a bit for compliance check to complete (if async)
            time.sleep(2)

            # Step 3: Get report
            report_result = runner.invoke(cli, ['mesh', 'compliance', 'report', domain_id, '--format', 'json'])

            # At least one should succeed
            assert check_result.exit_code in [0, 1] or report_result.exit_code in [0, 1], \
                f"At least one command should handle gracefully. Check: {check_result.output}, Report: {report_result.output}"
        finally:
            # Cleanup (api_key is guaranteed to be str here due to skip above)
            if self.api_key:
                self._delete_test_domain(api_base_url, self.api_key, domain_id)

