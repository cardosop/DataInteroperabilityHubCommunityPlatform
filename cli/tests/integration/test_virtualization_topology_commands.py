"""
Comprehensive integration tests for Virtualization Topology CLI commands against real API service.

These tests test the virtualization topology CLI commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest cli/tests/integration/test_virtualization_topology_commands.py -v
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
        # Try both localhost and container hostname
        for url in [os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1") + "/", "http://api-service:8000/api/v1/"]:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code < 600:  # Any HTTP response means API is up
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def api_available():
    """Fixture to check if API service is available"""
    available = _check_api_available()
    if not available:
        pytest.skip("API service not available")
    return available


@pytest.fixture(scope="module")
def shared_api_key():
    """
    Module-level fixture that creates a single API key for all tests in this module.
    This avoids race conditions and reduces API calls.
    """
    api_base_url = os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")

    # Check if API key is provided via environment variable
    env_key = os.environ.get('DATAHUB_API_KEY') or os.environ.get('TEST_API_KEY')
    if env_key and env_key.strip():
        # Validate the provided key
        try:
            response = requests.get(
                f"{api_base_url}/virtualization/datasets/",
                headers={'Authorization': f'ApiKey {env_key}', 'Content-Type': 'application/json'},
                timeout=5
            )
            if response.status_code in [200, 201]:
                return env_key.strip()
        except Exception:
            pass  # Will create new key below

    # Create new API key via Django shell
    unique_suffix = f"{int(time.time() * 1000) % 1000000}-{uuid.uuid4().hex[:8]}"

    django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey
from django.db import transaction, connection
import time

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='virtualization-topology-cli-test-tenant',
    defaults={{'name': 'Virtualization Topology CLI Test Tenant'}}
)

# Get or create DATA_PROVIDER role
data_provider_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='DATA_PROVIDER',
    defaults={{"description": "Data Provider"}}
)

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={{"description": "Tenant Administrator"}}
)

# Get or create user
user_email = f'virtualization-topology-cli-test-{unique_suffix}@example.com'
user, _ = User.objects.get_or_create(
    email=user_email,
    defaults={{
        'password': 'pbkdf2_sha256$120000$test$test',
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }}
)

# Assign roles
UserRole.objects.get_or_create(user=user, role=data_provider_role)
UserRole.objects.get_or_create(user=user, role=admin_role)

# Create API key
plaintext_key = APIKey.generate_key()
key_hash = APIKey.hash_key(plaintext_key)
api_key, _ = APIKey.objects.get_or_create(
    tenant=tenant,
    user=user,
    name='Virtualization Topology CLI Test API Key',
    defaults={{'key_hash': key_hash}}
)

# If key already exists, regenerate
if not api_key.key_hash == key_hash:
    plaintext_key = APIKey.generate_key()
    key_hash = APIKey.hash_key(plaintext_key)
    api_key.key_hash = key_hash
    api_key.save()

transaction.commit()

# Output the plaintext key
print(plaintext_key)
"""

    # Use subprocess to run Django shell commands to avoid test database issues
    # This works both inside and outside the container
    django_shell_script_updated = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey
from django.db import transaction, connection
import time

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='virtualization-topology-cli-test-tenant',
    defaults={{'name': 'Virtualization Topology CLI Test Tenant'}}
)

# Get or create DATA_PROVIDER role
data_provider_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='DATA_PROVIDER',
    defaults={{"description": "Data Provider"}}
)

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={{"description": "Tenant Administrator"}}
)

# Get or create user
user_email = f'virtualization-topology-cli-test-{unique_suffix}@example.com'
user, _ = User.objects.get_or_create(
    email=user_email,
    defaults={{
        'password': 'pbkdf2_sha256$120000$test$test',
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }}
)

# Assign roles
UserRole.objects.get_or_create(user=user, role=data_provider_role)
UserRole.objects.get_or_create(user=user, role=admin_role)

# Clean up old test keys
APIKey.objects.filter(
    tenant=tenant,
    user=user,
    name='Virtualization Topology CLI Test API Key'
).delete()

# Create new API key
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='Virtualization Topology CLI Test API Key',
    key_hash=api_key_hash,
    scopes=['virtualization:write', 'virtualization:read']
)

# Force commit
transaction.commit()
connection.ensure_connection()

# Verify key exists with retry logic
max_verify_attempts = 5
verify_key = None
for verify_attempt in range(max_verify_attempts):
    verify_key = APIKey.objects.filter(key_hash=api_key_hash).first()
    if verify_key:
        break
    time.sleep(0.2 * (verify_attempt + 1))

if not verify_key:
    connection.close()
    connection.ensure_connection()
    verify_key = APIKey.objects.filter(key_hash=api_key_hash).first()
    if not verify_key:
        print("ERROR: API key not found after creation", file=__import__('sys').stderr)
        exit(1)

time.sleep(0.3)

# Output the key with clear markers
print("===API_KEY_START===")
print(api_key_value)
print("===API_KEY_END===")
import sys
print("===API_KEY_START===", file=sys.stderr)
print(api_key_value, file=sys.stderr)
print("===API_KEY_END===", file=sys.stderr)
"""

    # Check if we're running inside Docker (api-service container)
    # If so, run Django shell directly via python manage.py shell
    django_paths = ['/app/hub/manage.py', '/app/manage.py']
    django_path = None
    for path in django_paths:
        if os.path.exists(path):
            django_path = path
            break

    if django_path:
        # We're inside the container, run Django shell via subprocess
        try:
            # Use python manage.py shell -c to avoid test database issues
            manage_py_dir = os.path.dirname(django_path)
            result = subprocess.run(
                ['python', 'manage.py', 'shell', '-c', django_shell_script_updated],
                cwd=manage_py_dir,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )

            # Extract API key from output
            output = result.stdout + result.stderr
            import re
            marker_pattern = r'===API_KEY_START===\s*([A-Za-z0-9_-]{20,})\s*===API_KEY_END==='
            match = re.search(marker_pattern, output, re.MULTILINE | re.DOTALL)
            if match:
                api_key = match.group(1).strip()
                if api_key and len(api_key) > 20:
                    return api_key

            # Fallback: look for key-like strings
            key_pattern = r'([A-Za-z0-9_-]{40,})'
            matches = re.findall(key_pattern, output)
            for match in reversed(matches):  # Take the last one (most likely the key)
                if len(match) > 20:
                    return match

            raise ValueError("Could not extract API key from Django shell output")
        except Exception as e:
            pytest.skip(f"Could not create API key via Django shell: {e}")

    # Fallback: try docker compose (for running from host)
    try:
        result = subprocess.run(
            ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell', '-c', django_shell_script],
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        api_key = result.stdout.strip().split('\n')[-1].strip()
        if api_key and len(api_key) > 20:  # Valid API key should be long
            return api_key
    except Exception as e:
        pytest.skip(f"Could not create API key: {e}")

    pytest.skip("Could not create API key")


@pytest.fixture(scope="function")
def runner(shared_api_key):
    """Fixture providing CliRunner with configured API key"""
    runner = CliRunner()
    # Set API key in config
    config.set_api_key(shared_api_key)
    config.set_api_base_url(os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1"))
    return runner


@pytest.fixture(scope="function")
def test_dataset(shared_api_key):
    """
    Create a test virtual dataset for topology tests.
    Returns dataset_id.
    """
    api_base_url = os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")
    headers = {
        'Authorization': f'ApiKey {shared_api_key}',
        'Content-Type': 'application/json'
    }

    dataset_data = {
        'name': f'Topology Test Dataset {uuid.uuid4().hex[:8]}',
        'query': 'SELECT * FROM test_table',
        'query_type': 'SQL',
        'description': 'Test dataset for topology commands'
    }

    try:
        response = requests.post(
            f"{api_base_url}/virtualization/datasets/",
            headers=headers,
            json=dataset_data,
            timeout=10
        )
        if response.status_code == 201:
            dataset_id = response.json().get('id')
            yield dataset_id
            # Cleanup
            try:
                requests.delete(
                    f"{api_base_url}/virtualization/datasets/{dataset_id}/",
                    headers=headers,
                    timeout=10
                )
            except Exception:
                pass
        else:
            pytest.skip(f"Could not create test dataset: {response.status_code} - {response.text}")
    except Exception as e:
        pytest.skip(f"Could not create test dataset: {e}")


class TestVirtualizationTopologyGet:
    """Test virtualization topology get command"""

    def test_topology_get_help(self, runner):
        """Test topology get command help text"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--help'])
        assert result.exit_code == 0
        assert 'Get complete virtualization topology' in result.output
        assert '--include-health-metrics' in result.output or '--no-include-health-metrics' in result.output
        assert '--format' in result.output

    def test_topology_get_success_table_format(self, runner):
        """Test successful topology retrieval in table format"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--format', 'table'])
        assert result.exit_code == 0
        assert 'VIRTUALIZATION TOPOLOGY SUMMARY' in result.output
        assert 'Total Datasets' in result.output
        assert 'VIRTUAL DATASETS' in result.output
        assert 'RELATIONSHIPS' in result.output

    def test_topology_get_success_json_format(self, runner):
        """Test successful topology retrieval in JSON format"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'summary' in data
        assert 'nodes' in data
        assert 'edges' in data
        assert 'metadata' in data

    def test_topology_get_without_health_metrics(self, runner):
        """Test topology get without health metrics"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--no-include-health-metrics', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'summary' in data
        assert 'nodes' in data
        # Health metrics should not be included in nodes
        if data.get('nodes'):
            first_node = data['nodes'][0]
            # Health metrics might still be present but empty, which is OK
            assert 'health_metrics' not in first_node or not first_node.get('health_metrics')

    def test_topology_get_with_health_metrics(self, runner):
        """Test topology get with health metrics"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--include-health-metrics', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'summary' in data
        assert 'nodes' in data

    def test_topology_get_empty_topology(self, runner):
        """Test topology get when no datasets exist"""
        # This test assumes a clean tenant or no datasets
        result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'summary' in data
        assert 'nodes' in data
        assert 'edges' in data
        # Should handle empty topology gracefully
        assert isinstance(data['nodes'], list)
        assert isinstance(data['edges'], list)

    def test_topology_get_authentication_error(self, runner):
        """Test topology get with invalid authentication"""
        # Temporarily set invalid API key
        original_key = config.get_api_key()
        try:
            config.set_api_key('invalid-key-12345')
            result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--format', 'json'])
            assert result.exit_code != 0
            assert 'error' in result.output.lower() or 'unauthorized' in result.output.lower() or 'authentication' in result.output.lower()
        finally:
            if original_key:
                config.set_api_key(original_key)
            else:
                config.clear_auth()


class TestVirtualizationTopologyGetDataset:
    """Test virtualization topology get-dataset command"""

    def test_topology_get_dataset_help(self, runner):
        """Test topology get-dataset command help text"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', '--help'])
        assert result.exit_code == 0
        assert 'Get topology view for a specific virtual dataset' in result.output
        assert 'DATASET_ID' in result.output
        assert '--format' in result.output

    def test_topology_get_dataset_success_table_format(self, runner, test_dataset):
        """Test successful dataset topology retrieval in table format"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', test_dataset, '--format', 'table'])
        assert result.exit_code == 0
        assert 'VIRTUAL DATASET TOPOLOGY' in result.output
        assert 'Dataset Information' in result.output
        assert 'RELATIONSHIPS' in result.output
        assert test_dataset in result.output or test_dataset[:8] in result.output

    def test_topology_get_dataset_success_json_format(self, runner, test_dataset):
        """Test successful dataset topology retrieval in JSON format"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', test_dataset, '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'dataset' in data
        assert 'relationships' in data
        assert data['dataset']['id'] == test_dataset

    def test_topology_get_dataset_not_found(self, runner):
        """Test topology get-dataset with non-existent dataset"""
        fake_dataset_id = str(uuid.uuid4())
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', fake_dataset_id, '--format', 'json'])
        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'not found' in result.output.lower()

    def test_topology_get_dataset_invalid_id_format(self, runner):
        """Test topology get-dataset with invalid ID format"""
        invalid_id = 'not-a-valid-uuid'
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', invalid_id, '--format', 'json'])
        # Should either fail with validation error or handle gracefully
        assert result.exit_code != 0 or 'error' in result.output.lower()

    def test_topology_get_dataset_empty_relationships(self, runner, test_dataset):
        """Test dataset topology with no relationships"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', test_dataset, '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'relationships' in data
        assert isinstance(data['relationships'], list)

    def test_topology_get_dataset_authentication_error(self, runner, test_dataset):
        """Test topology get-dataset with invalid authentication"""
        # Temporarily set invalid API key
        original_key = config.get_api_key()
        try:
            config.set_api_key('invalid-key-12345')
            result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', test_dataset, '--format', 'json'])
            assert result.exit_code != 0
            assert 'error' in result.output.lower() or 'unauthorized' in result.output.lower() or 'authentication' in result.output.lower()
        finally:
            if original_key:
                config.set_api_key(original_key)
            else:
                config.clear_auth()


class TestVirtualizationTopologyErrorHandling:
    """Test error handling for topology commands"""

    def test_topology_get_network_error_handling(self, runner):
        """Test topology get handles network errors gracefully"""
        # Temporarily set invalid API URL
        original_url = config.get_api_base_url()
        try:
            config.set_api_base_url("http://invalid-host:9999/api/v1")
            result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--format', 'json'])
            assert result.exit_code != 0
            assert 'error' in result.output.lower() or 'failed' in result.output.lower()
        finally:
            config.set_api_base_url(original_url)

    def test_topology_get_dataset_network_error_handling(self, runner, test_dataset):
        """Test topology get-dataset handles network errors gracefully"""
        # Temporarily set invalid API URL
        original_url = config.get_api_base_url()
        try:
            config.set_api_base_url("http://invalid-host:9999/api/v1")
            result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', test_dataset, '--format', 'json'])
            assert result.exit_code != 0
            assert 'error' in result.output.lower() or 'failed' in result.output.lower()
        finally:
            config.set_api_base_url(original_url)

    def test_topology_get_missing_argument(self, runner):
        """Test topology get-dataset with missing dataset_id argument"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset'])
        assert result.exit_code != 0
        assert 'Missing argument' in result.output or 'Error' in result.output

    def test_topology_get_invalid_format_option(self, runner):
        """Test topology get with invalid format option"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--format', 'invalid'])
        assert result.exit_code != 0
        assert 'Invalid value' in result.output or 'Error' in result.output

    def test_topology_get_dataset_invalid_format_option(self, runner, test_dataset):
        """Test topology get-dataset with invalid format option"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', test_dataset, '--format', 'invalid'])
        assert result.exit_code != 0
        assert 'Invalid value' in result.output or 'Error' in result.output


class TestVirtualizationTopologyCommandRegistration:
    """Test that topology commands are properly registered"""

    def test_topology_group_exists(self, runner):
        """Test that topology group exists"""
        result = runner.invoke(cli, ['virtualization', 'topology', '--help'])
        assert result.exit_code == 0
        assert 'get' in result.output
        assert 'get-dataset' in result.output

    def test_topology_get_command_exists(self, runner):
        """Test that topology get command exists"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--help'])
        assert result.exit_code == 0

    def test_topology_get_dataset_command_exists(self, runner):
        """Test that topology get-dataset command exists"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', '--help'])
        assert result.exit_code == 0

