from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive integration tests for Mesh Topology CLI commands against real API service.

These tests test all mesh topology CLI commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest cli/tests/integration/test_mesh_topology_commands.py -v
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
        response = requests.get(os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1") + "/", timeout=2)
        return response.status_code < 600  # Any HTTP response means API is up
    except Exception:
        return False


@pytest.fixture(scope="module")
def api_available():
    """Fixture to check if API service is available"""
    return _check_api_available()


class TestMeshTopologyCommandsRealAPI:
    """Comprehensive integration tests for all mesh topology commands with real API"""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up API base URL to point to Docker Compose service"""
        # Use the running Docker Compose API service
        api_base_url = os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")
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
    slug='mesh-topology-cli-test-tenant',
    defaults={'name': 'Mesh Topology CLI Test Tenant'}
)

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={'description': 'Tenant Administrator'}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='mesh-topology-cli-test@example.com',
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
APIKey.objects.filter(user=user, name='mesh-topology-cli-test-key').delete()

# Create new API key with mesh:write and mesh:read scopes
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='mesh-topology-cli-test-key',
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
                    # API keys are typically long strings with dashes/underscores
                    if len(line) > 40 and (line.replace('-', '').replace('_', '').isalnum()):
                        return line

            return None
        except Exception as e:
            print(f"Failed to create test API key: {e}")
            return None

    def _create_test_domain(self, name_suffix=None):
        """Create a test domain via API"""
        if not self.api_key:
            return None

        if name_suffix is None:
            name_suffix = str(uuid.uuid4())[:8]

        domain_name = f"topology-test-domain-{name_suffix}"
        api_base_url = config.get_api_base_url()

        domain_data = {
            "name": domain_name,
            "description": "Test domain for topology CLI integration tests",
            "status": "ACTIVE"
        }

        try:
            response = requests.post(
                f"{api_base_url}/mesh/domains/",
                json=domain_data,
                headers={"Authorization": f"ApiKey {self.api_key}"},
                timeout=30
            )
            if response.status_code not in [200, 201]:
                print(f"Failed to create domain: {response.status_code} - {response.text}")
                return None

            domain_response = response.json()
            domain_id = domain_response.get("id")
            if not domain_id:
                print("Failed to get domain ID from response.")
                return None

            # Wait a bit for domain to be fully created
            time.sleep(1)

            return {'id': str(domain_id), 'name': domain_name}
        except Exception as e:
            print(f"Failed to create test domain: {e}")
            return None

    def _delete_test_domain(self, domain_id):
        """Delete a test domain via API"""
        if not self.api_key:
            return False

        api_base_url = config.get_api_base_url()
        try:
            response = requests.delete(
                f"{api_base_url}/mesh/domains/{domain_id}/",
                headers={"Authorization": f"ApiKey {self.api_key}"},
                timeout=30
            )
            # 204 or 404 is OK (already deleted)
            return response.status_code in [200, 204, 404]
        except Exception:
            return False

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_topology_success_table_format(self, api_available):
        """Test getting topology in table format with real API"""
        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user can be created.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'topology', 'get', '--format', 'table'])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'MESH TOPOLOGY SUMMARY' in result.output or 'Total Domains' in result.output or 'No domains found' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_topology_success_json_format(self, api_available):
        """Test getting topology in JSON format with real API"""
        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user can be created.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'topology', 'get', '--format', 'json'])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"

        # Parse JSON output
        try:
            output_data = json.loads(result.output)
            assert 'summary' in output_data or 'nodes' in output_data or 'edges' in output_data or 'metadata' in output_data
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {result.output}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_topology_without_health_metrics(self, api_available):
        """Test getting topology without health metrics with real API"""
        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user can be created.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'topology', 'get', '--no-include-health-metrics', '--format', 'json'])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"

        # Parse JSON output
        try:
            output_data = json.loads(result.output)
            # Should still have structure even without health metrics
            assert isinstance(output_data, dict)
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {result.output}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_topology_with_health_metrics(self, api_available):
        """Test getting topology with health metrics with real API"""
        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user can be created.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'topology', 'get', '--include-health-metrics', '--format', 'json'])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"

        # Parse JSON output
        try:
            output_data = json.loads(result.output)
            assert isinstance(output_data, dict)
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {result.output}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_domain_topology_success_table_format(self, api_available):
        """Test getting domain topology in table format with real API"""
        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user can be created.")

        # Create a test domain
        test_domain = self._create_test_domain()
        if not test_domain:
            pytest.skip("Failed to create test domain")

        assert test_domain is not None  # Type assertion for linter
        domain_id = test_domain['id']
        domain_name = test_domain['name']

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['mesh', 'topology', 'get-domain', domain_id, '--format', 'table'])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            assert 'DOMAIN TOPOLOGY' in result.output or domain_id in result.output or domain_name in result.output
        finally:
            # Cleanup
            self._delete_test_domain(domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_domain_topology_success_json_format(self, api_available):
        """Test getting domain topology in JSON format with real API"""
        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user can be created.")

        # Create a test domain
        test_domain = self._create_test_domain()
        if not test_domain:
            pytest.skip("Failed to create test domain")

        assert test_domain is not None  # Type assertion for linter
        domain_id = test_domain['id']

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['mesh', 'topology', 'get-domain', domain_id, '--format', 'json'])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"

            # Parse JSON output
            try:
                output_data = json.loads(result.output)
                assert 'domain' in output_data or 'relationships' in output_data or 'health_metrics' in output_data
                # Verify domain ID matches
                if 'domain' in output_data and 'id' in output_data['domain']:
                    assert str(output_data['domain']['id']) == domain_id
            except json.JSONDecodeError:
                pytest.fail(f"Output is not valid JSON: {result.output}")
        finally:
            # Cleanup
            self._delete_test_domain(domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_domain_topology_not_found(self, api_available):
        """Test getting topology for non-existent domain with real API"""
        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user can be created.")

        runner = CliRunner()
        fake_domain_id = str(uuid.uuid4())
        result = runner.invoke(cli, ['mesh', 'topology', 'get-domain', fake_domain_id, '--format', 'json'])

        assert result.exit_code != 0, "Command should fail for non-existent domain"
        assert 'not found' in result.output.lower() or 'failed' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_topology_with_domains(self, api_available):
        """Test getting topology when domains exist with real API"""
        if not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user can be created.")

        # Create test domains
        test_domain1 = self._create_test_domain('1')
        test_domain2 = self._create_test_domain('2')

        if not test_domain1 or not test_domain2:
            pytest.skip("Failed to create test domains")

        assert test_domain1 is not None and test_domain2 is not None  # Type assertion for linter
        domain_id1 = test_domain1['id']
        domain_id2 = test_domain2['id']

        try:
            # Wait a bit for topology to update
            time.sleep(2)

            runner = CliRunner()
            result = runner.invoke(cli, ['mesh', 'topology', 'get', '--format', 'json'])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"

            # Parse JSON output
            try:
                output_data = json.loads(result.output)
                assert 'summary' in output_data
                assert 'nodes' in output_data
                assert 'edges' in output_data

                # Check that our domains are in the topology
                node_ids = [str(node.get('id', '')) for node in output_data.get('nodes', [])]
                assert domain_id1 in node_ids or domain_id2 in node_ids
            except json.JSONDecodeError:
                pytest.fail(f"Output is not valid JSON: {result.output}")
        finally:
            # Cleanup
            self._delete_test_domain(domain_id1)
            self._delete_test_domain(domain_id2)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_topology_command_structure(self, api_available):
        """Test that topology commands are properly registered"""
        runner = CliRunner()

        # Test topology group exists
        result = runner.invoke(cli, ['mesh', 'topology', '--help'])
        assert result.exit_code == 0
        assert 'Topology management commands' in result.output

        # Test get command exists
        result = runner.invoke(cli, ['mesh', 'topology', 'get', '--help'])
        assert result.exit_code == 0
        assert 'Get complete data mesh topology' in result.output

        # Test get-domain command exists
        result = runner.invoke(cli, ['mesh', 'topology', 'get-domain', '--help'])
        assert result.exit_code == 0
        assert 'Get topology view for a specific domain' in result.output

