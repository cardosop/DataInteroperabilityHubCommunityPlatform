from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive integration tests for Virtualization Datasets CLI commands against real API service.

These tests test the virtualization datasets CLI commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest tests/integration/test_virtualization_datasets_commands.py -v
"""
import pytest
import requests
import json
import os
import uuid
import subprocess
import time
import re
import tempfile
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
    slug='virtualization-datasets-cli-test-tenant',
    defaults={{'name': 'Virtualization Datasets CLI Test Tenant'}}
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
user, _ = User.objects.get_or_create(
    email='virtualization-datasets-cli-test@example.com',
    defaults={{
        "tenant": tenant,
        "status": UserStatus.ACTIVE
    }}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Assign roles
UserRole.objects.get_or_create(user=user, role=data_provider_role)
UserRole.objects.get_or_create(user=user, role=admin_role)

# Clean up old test keys
APIKey.objects.filter(user=user, name__startswith='virtualization-datasets-cli-test-key').delete()

# Create new API key
unique_key_name = f'virtualization-datasets-cli-test-key-{unique_suffix}'
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name=unique_key_name,
    key_hash=api_key_hash,
    scopes=['virtualization:write', 'virtualization:read']
)

# Force commit with multiple strategies for maximum reliability
transaction.commit()
connection.ensure_connection()

# Verify key exists with retry logic (database might need time to commit)
max_verify_attempts = 5
verify_key = None
for verify_attempt in range(max_verify_attempts):
    verify_key = APIKey.objects.filter(key_hash=api_key_hash).first()
    if verify_key:
        break
    time.sleep(0.2 * (verify_attempt + 1))  # Increasing delays: 0.2s, 0.4s, 0.6s, 0.8s, 1.0s

if not verify_key:
    # Last attempt with fresh connection
    connection.close()
    connection.ensure_connection()
    verify_key = APIKey.objects.filter(key_hash=api_key_hash).first()
    if not verify_key:
        print("ERROR: API key not found after creation", file=__import__('sys').stderr)
        exit(1)

# Additional delay to ensure commit is fully propagated
time.sleep(0.3)

# Output the key with clear markers
print("===API_KEY_START===")
print(api_key_value)
print("===API_KEY_END===")
# Also print to stderr for robustness
import sys
print("===API_KEY_START===", file=sys.stderr)
print(api_key_value, file=sys.stderr)
print("===API_KEY_END===", file=sys.stderr)
"""

    # Execute Django shell script
    max_retries = 3
    api_key = None

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell'],
                input=django_shell_script,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                cwd='/home/ph/Desktop/DataInteroperabilityHub'
            )

            # Extract API key from output using multiple strategies
            output = result.stdout + result.stderr

            # Strategy 1: Look for markers
            marker_pattern = r'===API_KEY_START===\s*([A-Za-z0-9_-]{20,})\s*===API_KEY_END==='
            match = re.search(marker_pattern, output, re.MULTILINE | re.DOTALL)
            if match:
                api_key = match.group(1).strip()

            # Strategy 2: Look for key-like strings (20+ alphanumeric/dash/underscore chars)
            if not api_key:
                key_pattern = r'([A-Za-z0-9_-]{20,})'
                matches = re.findall(key_pattern, output)
                # Filter out common false positives
                for potential_key in matches:
                    if (len(potential_key) >= 20 and
                        not potential_key.startswith('virtualization-datasets-cli-test') and
                        'error' not in potential_key.lower() and
                        'traceback' not in potential_key.lower()):
                        api_key = potential_key
                        break

            if api_key and len(api_key) >= 20:
                # Validate the key works with robust retry logic
                api_key = api_key.strip()
                max_validation_attempts = 8
                validation_delay = 0.5

                for validation_attempt in range(max_validation_attempts):
                    try:
                        # Exponential backoff with cap
                        wait_time = validation_delay * (validation_attempt + 1)
                        if wait_time > 2.0:
                            wait_time = 2.0
                        if validation_attempt > 0:
                            time.sleep(wait_time)

                        response = requests.get(
                            f"{api_base_url}/virtualization/datasets/",
                            headers={'Authorization': f'ApiKey {api_key}', 'Content-Type': 'application/json'},
                            timeout=5
                        )

                        if response.status_code in [200, 201]:
                            # Key is valid, return it
                            return api_key
                        elif response.status_code == 401:
                            # Key not valid yet, continue retrying
                            if validation_attempt < max_validation_attempts - 1:
                                continue
                        elif response.status_code == 429:
                            # Rate limited, wait longer
                            retry_after = response.headers.get('Retry-After', '2')
                            try:
                                wait_time = float(retry_after) + 0.5
                            except ValueError:
                                wait_time = 2.5
                            if validation_attempt < max_validation_attempts - 1:
                                time.sleep(wait_time)
                                continue
                    except requests.exceptions.RequestException:
                        # Network error, retry
                        if validation_attempt < max_validation_attempts - 1:
                            continue
                    except Exception as e:
                        # Other error, log and retry
                        if validation_attempt < max_validation_attempts - 1:
                            continue

                # If validation failed but we have a key, return it anyway
                # The test will fail with a clear error if it's truly invalid
                # This handles cases where the database commit takes longer than expected
                return api_key

        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                time.sleep(1.0)
                continue
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.0)
                continue
            print(f"Error creating API key: {e}", file=__import__('sys').stderr)

    # If we couldn't create a key, raise an error
    pytest.skip("Could not create or validate API key for integration tests")


class TestVirtualizationDatasetsCommandsRealAPI:
    """Comprehensive integration tests for virtualization datasets commands with real API"""

    @pytest.fixture(autouse=True)
    def setup_config(self, shared_api_key):
        """
        Set up API base URL and API key for each test.
        Uses the module-level shared_api_key fixture to avoid race conditions.
        """
        # Use the running Docker Compose API service
        api_base_url = os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")
        config.set_api_base_url(api_base_url)

        # Use the shared API key from the module-level fixture
        api_key = shared_api_key

        if not api_key or not api_key.strip():
            self.api_key = None
            yield
            return

        # Strip whitespace
        api_key = api_key.strip()

        # Validate API key format
        if not api_key or len(api_key) < 20 or not all(c.isalnum() or c in '-_' for c in api_key):
            self.api_key = None
            yield
            return

        # Clear any existing tokens first
        if 'access_token' in config._config:
            del config._config['access_token']
        if 'refresh_token' in config._config:
            del config._config['refresh_token']
        config._save()

        # Set environment variables FIRST
        os.environ['DATAHUB_API_KEY'] = api_key
        os.environ['TEST_API_KEY'] = api_key

        # Also set in config file as fallback
        config._config['api_key'] = api_key
        config._save()

        # Reload config to ensure it's read correctly
        config._load()

        # Verify tokens are cleared and API key is set
        if config.get_access_token():
            # Force clear any remaining tokens
            config._config.pop('access_token', None)
            config._config.pop('refresh_token', None)
            config._save()
            config._load()

        # Store for use in test methods
        self.api_key = api_key

        yield

        # Cleanup - only clear tokens, not API key (it's shared across tests)
        if 'access_token' in config._config:
            del config._config['access_token']
        if 'refresh_token' in config._config:
            del config._config['refresh_token']
        config._save()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_list_command(self, setup_config, api_available):
        """Test datasets list command"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        # Test list command with JSON output
        result = runner.invoke(cli, [
            'virtualization', 'datasets', 'list',
            '--format', 'json',
            '--page-size', '10'
        ])

        assert result.exit_code == 0, f"List command failed: {result.output}"
        output_data = json.loads(result.output)
        assert 'results' in output_data or isinstance(output_data, list)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_list_with_filters(self, setup_config, api_available):
        """Test datasets list command with filters"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        # Test list command with status filter
        result = runner.invoke(cli, [
            'virtualization', 'datasets', 'list',
            '--status', 'DRAFT',
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"List with filter failed: {result.output}"

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_create_and_get_command(self, setup_config, api_available):
        """Test complete flow: create dataset, then get it"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        # Create a test dataset definition
        dataset_data = {
            'name': f'test-dataset-{uuid.uuid4().hex[:8]}',
            'description': 'Test virtual dataset for CLI integration tests',
            'query': 'SELECT * FROM test_table',
            'query_type': 'SQL',
            'version': '1.0.0',
            'status': 'DRAFT'
        }

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(dataset_data, f)
            temp_file = f.name

        try:
            # Ensure API key is available
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                config._load()

            # Create dataset
            result = runner.invoke(cli, [
                'virtualization', 'datasets', 'create',
                '--file', temp_file,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Create failed: {result.output}"
            create_output = json.loads(result.output)
            assert 'id' in create_output
            dataset_id = create_output['id']
            assert create_output['name'] == dataset_data['name']

            # Get dataset
            result = runner.invoke(cli, [
                'virtualization', 'datasets', 'get',
                dataset_id,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Get failed: {result.output}"
            get_output = json.loads(result.output)
            assert get_output['id'] == dataset_id
            assert get_output['name'] == dataset_data['name']

            # Cleanup: Delete dataset
            result = runner.invoke(cli, [
                'virtualization', 'datasets', 'delete',
                dataset_id
            ], input='y\n')

            assert result.exit_code == 0, f"Delete failed: {result.output}"
        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_update_command(self, setup_config, api_available):
        """Test update dataset command"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        # Create a test dataset first
        dataset_data = {
            'name': f'test-dataset-{uuid.uuid4().hex[:8]}',
            'description': 'Test virtual dataset for update test',
            'query': 'SELECT * FROM test_table',
            'query_type': 'SQL',
            'status': 'DRAFT'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(dataset_data, f)
            create_file = f.name

        try:
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                config._load()

            # Create dataset
            result = runner.invoke(cli, [
                'virtualization', 'datasets', 'create',
                '--file', create_file,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Create failed: {result.output}"
            create_output = json.loads(result.output)
            dataset_id = create_output['id']

            # Update dataset
            update_data = {
                'description': 'Updated description',
                'status': 'ACTIVE'
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(update_data, f)
                update_file = f.name

            try:
                result = runner.invoke(cli, [
                    'virtualization', 'datasets', 'update',
                    dataset_id,
                    '--file', update_file,
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"Update failed: {result.output}"
                update_output = json.loads(result.output)
                assert update_output['id'] == dataset_id
                assert update_output['status'] == 'ACTIVE'

                # Cleanup
                result = runner.invoke(cli, [
                    'virtualization', 'datasets', 'delete',
                    dataset_id
                ], input='y\n')

                assert result.exit_code == 0, f"Delete failed: {result.output}"
            finally:
                os.unlink(update_file)
        finally:
            os.unlink(create_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_list_table_format(self, setup_config, api_available):
        """Test datasets list command with table format"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        result = runner.invoke(cli, [
            'virtualization', 'datasets', 'list',
            '--format', 'table',
            '--page-size', '5'
        ])

        assert result.exit_code == 0, f"List table format failed: {result.output}"
        # Table format should contain headers
        assert 'ID' in result.output or 'No virtual datasets found' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_create_invalid_file(self, setup_config, api_available):
        """Test create command with invalid file"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        # Test with non-existent file
        result = runner.invoke(cli, [
            'virtualization', 'datasets', 'create',
            '--file', '/nonexistent/file.json'
        ])

        assert result.exit_code != 0, "Should fail with non-existent file"
        assert 'not found' in result.output.lower() or 'does not exist' in result.output.lower() or 'File not found' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_create_invalid_json(self, setup_config, api_available):
        """Test create command with invalid JSON"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        # Create file with invalid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{ invalid json }')
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'virtualization', 'datasets', 'create',
                '--file', temp_file
            ])

            assert result.exit_code != 0, "Should fail with invalid JSON"
            assert 'invalid json' in result.output.lower() or 'JSON' in result.output
        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_create_missing_required_fields(self, setup_config, api_available):
        """Test create command with missing required fields"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        # Create file missing required fields
        incomplete_data = {
            'description': 'Missing required fields'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_data, f)
            temp_file = f.name

        try:
            result = runner.invoke(cli, [
                'virtualization', 'datasets', 'create',
                '--file', temp_file
            ])

            assert result.exit_code != 0, "Should fail with missing required fields"
            assert 'name' in result.output.lower() or 'required' in result.output.lower()
        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_get_nonexistent(self, setup_config, api_available):
        """Test get command with nonexistent dataset ID"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        fake_id = str(uuid.uuid4())
        result = runner.invoke(cli, [
            'virtualization', 'datasets', 'get',
            fake_id
        ])

        assert result.exit_code != 0, "Should fail with nonexistent ID"
        assert 'not found' in result.output.lower() or '404' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_datasets_list_pagination(self, setup_config, api_available):
        """Test datasets list command with pagination"""
        if not self.api_key:
            pytest.skip("API key not available")

        runner = CliRunner()

        result = runner.invoke(cli, [
            'virtualization', 'datasets', 'list',
            '--page', '1',
            '--page-size', '5',
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"List with pagination failed: {result.output}"
        output_data = json.loads(result.output)
        # Should have pagination info
        assert 'count' in output_data or 'results' in output_data

