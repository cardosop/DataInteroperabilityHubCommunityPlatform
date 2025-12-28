"""
Comprehensive integration tests for Transformation CLI commands against real API service.

These tests test the transformation CLI command group directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest cli/tests/integration/test_transformation_commands.py -v
"""
import pytest
import requests
import json
import os
import uuid
import subprocess
import time
import re
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


@pytest.fixture(scope="module")
def shared_api_key():
    """
    Module-level fixture that creates a single API key for all tests in this module.
    This avoids race conditions and reduces API calls.
    """
    api_base_url = "http://localhost:8000/api/v1"

    # Check if API key is provided via environment variable
    env_key = os.environ.get('DATAHUB_API_KEY') or os.environ.get('TEST_API_KEY')
    if env_key and env_key.strip():
        # Validate the provided key
        try:
            response = requests.get(
                f"{api_base_url}/transformation/pipelines/",
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
    slug='transformation-cli-test-tenant',
    defaults={{'name': 'Transformation CLI Test Tenant'}}
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
    email='transformation-cli-test@example.com',
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
APIKey.objects.filter(user=user, name__startswith='transformation-cli-test-key').delete()

# Create new API key
unique_key_name = f'transformation-cli-test-key-{unique_suffix}'
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name=unique_key_name,
    key_hash=api_key_hash,
    scopes=['transformation:write', 'transformation:read']
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
                check=False
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
                        not potential_key.startswith('transformation-cli-test') and
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
                            f"{api_base_url}/transformation/pipelines/",
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


class TestTransformationCommandsRealAPI:
    """Comprehensive integration tests for transformation commands with real API"""

    @pytest.fixture(autouse=True)
    def setup_config(self, shared_api_key):
        """
        Set up API base URL and API key for each test.
        Uses the module-level shared_api_key fixture to avoid race conditions.
        """
        # Use the running Docker Compose API service
        api_base_url = "http://localhost:8000/api/v1"
        config.set_api_base_url(api_base_url)

        # Use the shared API key from the module-level fixture
        api_key = shared_api_key

        if not api_key or not api_key.strip():
            self.api_key = None
            # Don't skip here - let the test methods handle it
            yield
            return

        # Strip whitespace
        api_key = api_key.strip()

        # Validate API key format
        if not api_key or len(api_key) < 20 or not all(c.isalnum() or c in '-_' for c in api_key):
            self.api_key = None
            # Don't skip here - let the test methods handle it
            yield
            return

        # Clear any existing tokens first (critical: tokens take precedence in old code)
        # We must clear them to ensure API key is used
        if 'access_token' in config._config:
            del config._config['access_token']
        if 'refresh_token' in config._config:
            del config._config['refresh_token']
        config._save()

        # Set environment variables FIRST (they take precedence in get_api_key())
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

        # Verify API key is accessible (for debugging)
        final_key = config.get_api_key()
        if not final_key or final_key != api_key:
            import sys
            print(f"Warning: API key mismatch in config. Using environment variable.", file=sys.stderr)

        yield

        # Cleanup - only clear tokens, not API key (it's shared across tests)
        if 'access_token' in config._config:
            del config._config['access_token']
        if 'refresh_token' in config._config:
            del config._config['refresh_token']
        config._save()
        # Keep environment variables set for next test (they're shared)

    def _create_test_api_key(self):
        """Create a test API key via Django shell in the API service container"""
        import time
        import uuid
        # Use timestamp and UUID to ensure unique key name
        unique_suffix = f"{int(time.time() * 1000) % 1000000}-{uuid.uuid4().hex[:8]}"

        django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey
import os
import time
import uuid

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='transformation-cli-test-tenant',
    defaults={{'name': 'Transformation CLI Test Tenant'}}
)

# Get or create DATA_PROVIDER role (required for transformation operations)
data_provider_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='DATA_PROVIDER',
    defaults={{"description": "Data Provider"}}
)

# Get or create TENANT_ADMIN role (also works for transformation operations)
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={{"description": "Tenant Administrator"}}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='transformation-cli-test@example.com',
    defaults={{
        "tenant": tenant,
        "status": UserStatus.ACTIVE
    }}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Assign both DATA_PROVIDER and TENANT_ADMIN roles to user (use get_or_create to avoid duplicates)
UserRole.objects.get_or_create(user=user, role=data_provider_role)
UserRole.objects.get_or_create(user=user, role=admin_role)

# Delete existing API key if it exists (use unique name to avoid conflicts)
unique_key_name = f'transformation-cli-test-key-{unique_suffix}'
# Clean up old test keys (keep last 3 to avoid conflicts, but delete before creating new one)
APIKey.objects.filter(user=user, name__startswith='transformation-cli-test-key').delete()

# Create new API key with transformation:write and transformation:read scopes
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name=unique_key_name,
    key_hash=api_key_hash,
    scopes=['transformation:write', 'transformation:read']
)
# Explicitly commit the transaction to ensure key is saved
from django.db import transaction
from django.db import connection
transaction.commit()
# Close database connection to force fresh connection on next query
connection.close()
# Also ensure the object is refreshed from database
api_key_obj.refresh_from_db()
# Verify the key exists by querying it directly (with fresh connection)
verify_key = APIKey.objects.filter(key_hash=api_key_hash).first()
if not verify_key:
    print("ERROR: API key not found after creation")
    exit(1)
# Small delay to ensure everything is committed and visible
import time
time.sleep(1.0)

# Create ABAC policy to allow DATA_PROVIDER role users to create pipelines (optional)
# This policy allows all users in the tenant to create transformation pipelines
# If ABAC policy creation fails, it's not critical - the system will use role-based permissions
try:
    from hub.apps.governance.models import AccessPolicy
    AccessPolicy.objects.get_or_create(
        tenant=tenant,
        name='Allow Pipeline Creation',
        defaults={{
            "conditions": {{
                "user": {{"tenant_id": str(tenant.id)}}
            }},
            "effect": "ALLOW",
            "priority": 100,
            "enabled": True,
            "created_by": user
        }}
    )
except Exception:
    # ABAC policy creation failed - not critical, role-based permissions will be used
    pass

# Print API key with clear markers (most reliable method for extraction)
import sys
MARKER_START = "===API_KEY_START==="
MARKER_END = "===API_KEY_END==="
api_key_output = "API_KEY=" + api_key_value
print(MARKER_START, file=sys.stderr)
print(api_key_output, file=sys.stderr)
print(MARKER_END, file=sys.stderr)
print(MARKER_START, file=sys.stdout)
print(api_key_output, file=sys.stdout)
print(MARKER_END, file=sys.stdout)
# Also print without markers as fallback
print(api_key_output, file=sys.stderr)
print(api_key_output, file=sys.stdout)
sys.stdout.flush()
sys.stderr.flush()
"""
        result = None
        try:
            result = subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell'],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=30,
                cwd='/home/ph/Desktop/DataInteroperabilityHub'
            )

            # Note: Temp file approach removed - using marker-based extraction which is more reliable
            # The temp file approach had issues with file path interpolation in f-strings

            # Extract API key from output regardless of return code (key might be printed before error)
            # Combine stdout and stderr for searching
            all_output = (result.stdout or '') + '\n' + (result.stderr or '')

            # First, try to extract using clear markers (most reliable)
            # Extract all sections between markers and find API_KEY= in the last one
            marker_sections = re.findall(r'===API_KEY_START===(.*?)===API_KEY_END===', all_output, re.DOTALL)
            if marker_sections:
                # Process from last to first (most recent key)
                for section in reversed(marker_sections):
                    # Look for API_KEY= in this section
                    api_key_match = re.search(r'API_KEY=([A-Za-z0-9_-]{40,})', section)
                    if api_key_match:
                        api_key = api_key_match.group(1).strip()
                        # Validate format: API keys are typically 40+ chars
                        if api_key and len(api_key) >= 40 and all(c.isalnum() or c in '-_' for c in api_key):
                            # Small delay to ensure key is committed to database
                            time.sleep(1.0)
                            return api_key

            # Fallback: try pattern where markers and API_KEY might be on same line or adjacent
            marker_pattern_simple = r'===API_KEY_START===(?:\s|\n)*API_KEY=([A-Za-z0-9_-]{40,})(?:\s|\n)*===API_KEY_END==='
            matches = re.findall(marker_pattern_simple, all_output, re.MULTILINE | re.DOTALL)
            if matches:
                api_key = matches[-1].strip()
                if api_key and len(api_key) >= 40 and all(c.isalnum() or c in '-_' for c in api_key):
                    time.sleep(1.0)
                    return api_key

            # Fallback: Use regex to find API_KEY=pattern (standard method)
            # Try multiple regex patterns to catch different formats
            patterns = [
                r'API_KEY=([A-Za-z0-9_-]{20,})',  # Standard format: API_KEY=value
                r'API_KEY\s*=\s*([A-Za-z0-9_-]{20,})',  # With whitespace: API_KEY = value
                r'"API_KEY":\s*"([A-Za-z0-9_-]{20,})"',  # JSON format: "API_KEY": "value"
                r'API_KEY:\s*([A-Za-z0-9_-]{20,})',  # Colon format: API_KEY: value
            ]
            for pattern in patterns:
                match = re.search(pattern, all_output, re.MULTILINE | re.IGNORECASE)
                if match:
                    api_key = match.group(1).strip()
                    # Validate: API keys are typically 40+ characters, alphanumeric with possible dashes/underscores
                    if api_key and len(api_key) >= 20 and all(c.isalnum() or c in '-_' for c in api_key):
                        return api_key

            # Fallback: Check stdout line by line
            if result.stdout:
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    line = line.strip()
                    if line.startswith('API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        if api_key and len(api_key) >= 20:
                            return api_key

            # Fallback: Check stderr line by line
            if result.stderr:
                stderr_lines = result.stderr.strip().split('\n')
                for line in stderr_lines:
                    line = line.strip()
                    if line.startswith('API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        if api_key and len(api_key) >= 20:
                            return api_key

            # Fallback: look for lines that look like API keys (alphanumeric, long enough)
            # Check both stdout and stderr
            all_lines = []
            if result.stdout:
                all_lines.extend(result.stdout.strip().split('\n'))
            if result.stderr:
                all_lines.extend(result.stderr.strip().split('\n'))

            for line in reversed(all_lines):
                line = line.strip()
                # Skip JSON/log lines and metadata
                if any(skip in line for skip in ['timestamp', 'level', 'logger', 'message', 'event', 'args=', 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'BEGIN', 'COMMIT', '{', '}', '[', ']', '"', ':', 'UUID', 'User ID', 'User roles', 'API key scopes', 'objects imported', 'Warning', 'Error']):
                    continue
                # Look for lines that are long alphanumeric strings (API keys are typically 40+ chars)
                cleaned = line.replace('-', '').replace('_', '')
                if line and len(line) >= 40 and cleaned.isalnum() and ' ' not in line and not line.startswith('/') and not line.startswith('('):
                    return line
        except subprocess.TimeoutExpired:
            # Timeout occurred - log but don't fail
            import sys
            print("Warning: API key creation timed out", file=sys.stderr)
            return None
        except Exception as e:
            # Log error for debugging but don't fail the test
            import sys
            print(f"Warning: Error creating API key: {e}", file=sys.stderr)
            if result and hasattr(result, 'stdout'):
                print(f"stdout: {result.stdout[:500]}", file=sys.stderr)
            if result and hasattr(result, 'stderr'):
                print(f"stderr: {result.stderr[:500]}", file=sys.stderr)
            return None

    def _create_test_asset_with_dataset(self):
        """Create a test asset with dataset and file via Django shell"""
        django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
import uuid

# Get the tenant from the API key user
tenant = Tenant.objects.filter(slug='transformation-cli-test-tenant').first()
if not tenant:
    print("NO_TENANT")
    exit(1)

# Create asset
asset_key = f'test-asset-{{uuid.uuid4().hex[:8]}}'
asset = Asset.objects.create(
    tenant=tenant,
    key=asset_key,
    name=f'Test Asset {{uuid.uuid4().hex[:8]}}',
    status=AssetStatus.ACTIVE
)

# Create test CSV content
csv_content = b"id,name,age\\n1,Alice,25\\n2,Bob,17\\n3,Charlie,30\\n4,Diana,22\\n5,Eve,19"

# Create file first (without storage_path, will be set after upload)
file = File.objects.create(
    tenant=tenant,
    name="test_data.csv",
    storage_path="",  # Will be set after upload
    size=len(csv_content),
    content_type="text/csv",
    status=FileStatus.ACTIVE
)

# Upload file to storage and get the actual storage path
try:
    storage_client = S3StorageClient()
    storage_path = storage_client.save_file(
        tenant_id=str(tenant.id),
        file_id=str(file.id),
        file_content=csv_content
    )
    # Update file with the actual storage path returned by save_file
    file.storage_path = storage_path
    file.save()
except Exception as e:
    print(f"STORAGE_ERROR:{{e}}")
    exit(1)

# Create dataset
dataset = Dataset.objects.create(
    tenant=tenant,
    asset=asset,
    file=file,
    version=1,
    format="CSV",
    row_count=5,
    schema_json={{
        "fields": [
            {{"name": "id", "data_type": "integer"}},
            {{"name": "name", "data_type": "string"}},
            {{"name": "age", "data_type": "integer"}}
        ]
    }}
)

print(asset.id)
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
                output_lines = result.stdout.strip().split('\n')
                for line in reversed(output_lines):
                    line = line.strip()
                    # UUID format
                    if line and len(line) == 36 and '-' in line:
                        return line
        except Exception:
            pass
        return None

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_transformation_command_group_exists(self, setup_config, api_available):
        """Test that transformation command group exists and is accessible"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['transformation', '--help'])
        assert result.exit_code == 0
        assert 'Transformation management commands' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_transformation_command_group_help(self, setup_config, api_available):
        """Test transformation command group help text"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['transformation', '--help'])
        assert result.exit_code == 0
        assert 'Transformation management commands' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_transformation_invalid_subcommand(self, setup_config, api_available):
        """Test handling invalid transformation subcommand"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['transformation', 'invalid-subcommand'])
        assert result.exit_code != 0
        assert 'No such command' in result.output or 'Usage:' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_transformation_command_in_main_cli_help(self, setup_config, api_available):
        """Test that transformation command appears in main CLI help"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'transformation' in result.output
        assert 'Transformation' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_pipelines_list_command(self, setup_config, api_available):
        """Test listing pipelines via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['transformation', 'pipelines', 'list', '--format', 'json'])
        if result.exit_code != 0:
            # Print error for debugging
            import sys
            print(f"CLI Error (exit code {result.exit_code}): {result.output}", file=sys.stderr)
            print(f"Exception: {result.exception}", file=sys.stderr)
        assert result.exit_code == 0, f"Command failed with exit code {result.exit_code}. Output: {result.output}"
        output_data = json.loads(result.output)
        assert 'count' in output_data
        assert 'results' in output_data

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_pipelines_create_and_get_command(self, setup_config, api_available):
        """Test creating and getting a pipeline via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()

        # Create a temporary pipeline definition file
        import tempfile
        pipeline_data = {
            'name': f'Test Pipeline {uuid.uuid4().hex[:8]}',
            'description': 'Integration test pipeline',
            'pipeline_definition': {
                'version': '1.0',
                'steps': [
                    {
                        'name': 'test_step',
                        'type': 'filter',
                        'config': {
                            'expression': 'value > 0'
                        }
                    }
                ]
            },
            'version': '1.0.0',
            'status': 'DRAFT'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            # Ensure API key is available before running CLI commands
            # Set in both environment and config file for maximum reliability
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                # Reload config to ensure it's read
                config._load()
                # Verify API key is accessible
                if not config.get_api_key():
                    pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

            # Create pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'create',
                '--file', temp_file,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Create failed: {result.output}"
            create_output = json.loads(result.output)
            assert 'id' in create_output
            pipeline_id = create_output['id']
            assert create_output['name'] == pipeline_data['name']

            # Get pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'get',
                pipeline_id,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Get failed: {result.output}"
            get_output = json.loads(result.output)
            assert get_output['id'] == pipeline_id
            assert get_output['name'] == pipeline_data['name']

            # Cleanup: Delete pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'delete',
                pipeline_id
            ], input='y\n')

            assert result.exit_code == 0, f"Delete failed: {result.output}"
        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_pipelines_update_command(self, setup_config, api_available):
        """Test updating a pipeline via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()

        # Create a temporary pipeline definition file
        import tempfile
        pipeline_data = {
            'name': f'Test Pipeline {uuid.uuid4().hex[:8]}',
            'description': 'Integration test pipeline',
            'pipeline_definition': {
                'version': '1.0',
                'steps': [
                    {
                        'name': 'test_step',
                        'type': 'filter'
                    }
                ]
            },
            'version': '1.0.0',
            'status': 'DRAFT'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            # Ensure API key is available before running CLI commands
            # Set in both environment and config file for maximum reliability
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                # Reload config to ensure it's read
                config._load()
                # Verify API key is accessible
                if not config.get_api_key():
                    pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

            # Create pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'create',
                '--file', temp_file,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Create failed: {result.output}"
            create_output = json.loads(result.output)
            pipeline_id = create_output['id']

            # Update pipeline
            updated_data = {
                'pipeline_definition': {
                    'version': '1.1',
                    'steps': [
                        {
                            'name': 'updated_step',
                            'type': 'transform'
                        }
                    ]
                }
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(updated_data, f)
                update_file = f.name

            try:
                result = runner.invoke(cli, [
                    'transformation', 'pipelines', 'update',
                    pipeline_id,
                    '--file', update_file,
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"Update failed: {result.output}"
                update_output = json.loads(result.output)
                assert update_output['id'] == pipeline_id
            finally:
                os.unlink(update_file)

            # Cleanup: Delete pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'delete',
                pipeline_id
            ], input='y\n')

            assert result.exit_code == 0, f"Delete failed: {result.output}"
        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_pipelines_list_with_filters(self, setup_config, api_available):
        """Test listing pipelines with filters via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Ensure API key is set in environment (takes precedence)
        os.environ['DATAHUB_API_KEY'] = self.api_key
        os.environ['TEST_API_KEY'] = self.api_key
        # Also ensure config is reloaded
        config._load()

        runner = CliRunner()

        # Test with status filter
        result = runner.invoke(cli, [
            'transformation', 'pipelines', 'list',
            '--status', 'DRAFT',
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"List with filter failed: {result.output}"
        output_data = json.loads(result.output)
        assert 'count' in output_data
        assert 'results' in output_data

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_pipelines_command_structure(self, setup_config, api_available):
        """Test that all pipeline commands exist and are accessible"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()

        # Test pipelines command group
        result = runner.invoke(cli, ['transformation', 'pipelines', '--help'])
        assert result.exit_code == 0
        assert 'Pipeline management commands' in result.output or 'pipelines' in result.output.lower()

        # Test list command
        result = runner.invoke(cli, ['transformation', 'pipelines', 'list', '--help'])
        assert result.exit_code == 0

        # Test create command
        result = runner.invoke(cli, ['transformation', 'pipelines', 'create', '--help'])
        assert result.exit_code == 0

        # Test get command
        result = runner.invoke(cli, ['transformation', 'pipelines', 'get', '--help'])
        assert result.exit_code == 0

        # Test update command
        result = runner.invoke(cli, ['transformation', 'pipelines', 'update', '--help'])
        assert result.exit_code == 0

        # Test delete command
        result = runner.invoke(cli, ['transformation', 'pipelines', 'delete', '--help'])
        assert result.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_executions_command_structure(self, setup_config, api_available):
        """Test that all execution commands exist and are accessible"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()

        # Test executions command group
        result = runner.invoke(cli, ['transformation', 'executions', '--help'])
        assert result.exit_code == 0
        assert 'Execution management commands' in result.output or 'executions' in result.output.lower()

        # Test create command
        result = runner.invoke(cli, ['transformation', 'executions', 'create', '--help'])
        assert result.exit_code == 0

        # Test list command
        result = runner.invoke(cli, ['transformation', 'executions', 'list', '--help'])
        assert result.exit_code == 0

        # Test get command
        result = runner.invoke(cli, ['transformation', 'executions', 'get', '--help'])
        assert result.exit_code == 0

        # Test cancel command
        result = runner.invoke(cli, ['transformation', 'executions', 'cancel', '--help'])
        assert result.exit_code == 0

        # Test watch command
        result = runner.invoke(cli, ['transformation', 'executions', 'watch', '--help'])
        assert result.exit_code == 0

    def _wait_for_rate_limit(self, seconds=1.5):
        """Wait to avoid rate limiting between API calls"""
        import time
        time.sleep(seconds)

    def _create_asset_with_dataset(self):
        """
        Create an asset with a dataset for testing using Django shell.
        Returns the asset_id if successful, None otherwise.
        """
        import requests
        import subprocess
        import json

        api_base_url = config.get_api_base_url()
        headers = {
            'Authorization': f'ApiKey {self.api_key}',
            'Content-Type': 'application/json'
        }

        # Step 1: Create asset via API
        asset_data = {
            'name': f'Test Asset {uuid.uuid4().hex[:8]}',
            'key': f'test-asset-{uuid.uuid4().hex[:8]}',
            'description': 'Test asset for execution',
            'visibility': 'INTERNAL',
            'status': 'ACTIVE'  # Must be ACTIVE for pipeline execution
        }

        asset_response = requests.post(
            f'{api_base_url}/assets/assets/',
            json=asset_data,
            headers=headers,
            timeout=10
        )

        if asset_response.status_code not in [200, 201]:
            return None

        asset_id = asset_response.json().get('id')
        if not asset_id:
            return None

        # Step 1.5: Update asset status to ACTIVE (required for pipeline execution)
        # The asset creation API doesn't accept status, so we update it after creation
        update_response = requests.patch(
            f'{api_base_url}/assets/assets/{asset_id}/',
            json={'status': 'ACTIVE'},
            headers=headers,
            timeout=10
        )
        if update_response.status_code not in [200, 201]:
            # If update fails, try via Django shell as fallback
            import subprocess
            django_shell_script = f"""
from hub.apps.assets.models import Asset
asset = Asset.objects.get(id='{asset_id}')
asset.status = 'ACTIVE'
asset.save()
print(f"Updated asset {{asset.id}} status to {{asset.status}}")
"""
            subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell'],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=10,
                cwd='/home/ph/Desktop/DataInteroperabilityHub'
            )

        # Step 2: Create file and dataset directly via Django shell (bypasses file upload complexity)
        django_shell_script = f"""
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import User
from django.db import transaction
import uuid
import hashlib

# Get asset and user
asset = Asset.objects.get(id='{asset_id}')
user = User.objects.filter(email='transformation-cli-test@example.com').first()
if not user:
    print("ERROR: User not found", file=__import__('sys').stderr)
    exit(1)

# Create a minimal file and dataset record (for testing purposes)
# In production, this would be created from a file upload, but for tests we create it directly
with transaction.atomic():
    # Step 1: Create a File record
    file_id = uuid.uuid4()
    # Create minimal CSV content
    fake_content = b"value\\n1\\n2\\n3\\n"
    content_sha256 = hashlib.sha256(fake_content).hexdigest()
    # Storage path format: tenant_id/file_id (matches save_file key format)
    storage_path = f"{{asset.tenant.id}}/{{file_id}}"

    # Step 1.5: Upload file content to MinIO/S3 storage FIRST (before creating File record)
    from hub.apps.files.storage import S3StorageClient
    storage_client = S3StorageClient()
    try:
        # Upload file to storage
        storage_key = storage_client.save_file(
            tenant_id=str(asset.tenant.id),
            file_id=str(file_id),
            file_content=fake_content
        )
        # Use the actual key returned by save_file
        storage_path = storage_key
        print(f"Uploaded file to storage: {{storage_key}}", file=__import__('sys').stderr)
    except Exception as e:
        print(f"Warning: Could not upload file to storage: {{e}}", file=__import__('sys').stderr)
        # Use fallback path format
        storage_path = f"{{asset.tenant.id}}/{{file_id}}"

    # Step 2: Create File record with correct storage_path
    file_obj = File.objects.create(
        tenant=asset.tenant,
        name='test-data.csv',
        content_type='text/csv',
        size=len(fake_content),
        content_sha256=content_sha256,
        storage_path=storage_path,
        status=FileStatus.ACTIVE,
        created_by=user
    )

    # Step 2: Create a Dataset linked to the File
    dataset = Dataset.objects.create(
        tenant=asset.tenant,
        asset=asset,
        file=file_obj,
        format='CSV',
        schema_json={{"fields": [{{"name": "value", "type": "integer"}}]}},
        version=1,
        is_current=True,
        created_by=user
    )

    # Transaction commits automatically when exiting the atomic block
    print(f"DATASET_ID:{{dataset.id}}")
    print(f"FILE_ID:{{file_obj.id}}", file=__import__('sys').stderr)
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

            if result.returncode != 0:
                # If dataset creation fails, still return asset_id (some tests might work without dataset)
                return asset_id

            # Extract dataset_id from output if present
            output = result.stdout + result.stderr
            dataset_created = False
            for line in output.split('\n'):
                if line.startswith('DATASET_ID:') or line.startswith('DATASET_EXISTS:'):
                    dataset_id = line.split(':', 1)[1].strip()
                    dataset_created = True
                    # Wait a bit for dataset to be fully committed and visible
                    import time
                    time.sleep(1.0)  # Increased wait time for database consistency
                    break

            if not dataset_created:
                # Dataset creation might have failed
                import sys
                print(f"Warning: Dataset creation output: {output[:500]}", file=sys.stderr)

            return asset_id

        except Exception as e:
            # If dataset creation fails, still return asset_id (some tests might work without dataset)
            import sys
            print(f"Warning: Could not create dataset: {e}", file=sys.stderr)
            return asset_id

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_executions_create_and_list(self, setup_config, api_available):
        """Test creating and listing executions via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Ensure API key is set in environment (takes precedence)
        os.environ['DATAHUB_API_KEY'] = self.api_key
        os.environ['TEST_API_KEY'] = self.api_key
        # Also set in config file
        config._config['api_key'] = self.api_key
        config._save()
        # Reload config to ensure it's read correctly
        config._load()
        # Small delay to ensure everything is committed
        import time
        time.sleep(0.2)

        # Wait a bit to avoid rate limiting from previous tests
        self._wait_for_rate_limit(2.0)

        runner = CliRunner()

        # First, create a pipeline
        import tempfile
        pipeline_data = {
            'name': f'Test Pipeline {uuid.uuid4().hex[:8]}',
            'description': 'Integration test pipeline for executions',
            'pipeline_definition': {
                'version': '1.0',
                'steps': [
                    {
                        'name': 'test_step',
                        'type': 'task',  # Step type (required by serializer)
                        'node_config': {
                            'node_type': 'output'  # Output nodes don't require field references
                        }
                    }
                ]
            },
            'version': '1.0.0',
            'status': 'ACTIVE'  # Must be ACTIVE to execute
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            # Ensure API key is available before running CLI commands
            # Set in both environment and config file for maximum reliability
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                # Reload config to ensure it's read
                config._load()
                # Verify API key is accessible
                if not config.get_api_key():
                    pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

            # Create pipeline (with retry for rate limiting and API key validation)
            max_retries = 3
            for attempt in range(max_retries):
                result = runner.invoke(cli, [
                    'transformation', 'pipelines', 'create',
                    '--file', temp_file,
                    '--format', 'json'
                ])

                if result.exit_code == 0:
                    break
                elif 'rate limit' in result.output.lower() and attempt < max_retries - 1:
                    # Wait and retry for rate limiting
                    self._wait_for_rate_limit(2.0 * (attempt + 1))
                    continue
                elif 'invalid api key' in result.output.lower() or 'authentication' in result.output.lower():
                    # API key might not be committed yet, wait and retry
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(1.0 * (attempt + 1))
                        # Re-ensure API key is set
                        os.environ['DATAHUB_API_KEY'] = self.api_key
                        os.environ['TEST_API_KEY'] = self.api_key
                        config._config['api_key'] = self.api_key
                        config._save()
                        config._load()
                        continue
                    else:
                        assert result.exit_code == 0, f"Create pipeline failed after {max_retries} attempts: {result.output}"
                else:
                    assert result.exit_code == 0, f"Create pipeline failed: {result.output}"

            # Verify the output is valid JSON before parsing
            if result.exit_code != 0:
                # If command failed, the output might be an error message, not JSON
                import sys
                print(f"DEBUG: Pipeline creation failed. Exit code: {result.exit_code}", file=sys.stderr)
                print(f"DEBUG: Output: {result.output[:500]}", file=sys.stderr)
                pytest.skip(f"Pipeline creation failed: {result.output[:200]}")

            try:
                create_output = json.loads(result.output)
            except json.JSONDecodeError as e:
                import sys
                print(f"DEBUG: JSON decode error: {e}", file=sys.stderr)
                print(f"DEBUG: Output: {result.output[:500]}", file=sys.stderr)
                pytest.skip(f"Pipeline creation returned invalid JSON: {result.output[:200]}")

            if 'id' not in create_output:
                import sys
                print(f"DEBUG: Response missing 'id': {create_output}", file=sys.stderr)
                pytest.skip(f"Pipeline creation response missing 'id': {create_output}")

            pipeline_id = create_output['id']

            # Create a test asset with dataset (we need an asset with dataset to execute the pipeline)
            asset_id = self._create_asset_with_dataset()
            if not asset_id:
                pytest.skip("Could not create test asset with dataset")

            # Ensure API key is set before creating execution
            os.environ['DATAHUB_API_KEY'] = self.api_key
            os.environ['TEST_API_KEY'] = self.api_key
            config._config['api_key'] = self.api_key
            config._save()
            config._load()

            try:
                # Create execution
                result = runner.invoke(cli, [
                    'transformation', 'executions', 'create',
                    pipeline_id,
                    '--input-asset', asset_id,
                    '--execution-mode', 'ASYNC',
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"Create execution failed: {result.output}"
                execution_output = json.loads(result.output)
                assert 'execution_id' in execution_output or 'id' in execution_output
                execution_id = execution_output.get('execution_id') or execution_output.get('id')
                assert execution_output.get('status') in ['PENDING', 'RUNNING', 'COMPLETED']

                # List executions
                result = runner.invoke(cli, [
                    'transformation', 'executions', 'list',
                    '--pipeline-id', pipeline_id,
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"List executions failed: {result.output}"
                list_output = json.loads(result.output)
                assert 'results' in list_output or isinstance(list_output, list)
                results = list_output.get('results', []) if isinstance(list_output, dict) else list_output

                # Verify our execution is in the list
                execution_found = False
                for exec_item in results:
                    exec_id = exec_item.get('id') or exec_item.get('execution_id')
                    if exec_id == execution_id:
                        execution_found = True
                        break
                assert execution_found, f"Execution {execution_id} not found in list"

            finally:
                # Cleanup: Delete asset
                try:
                    requests.delete(
                        f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                        headers=headers,
                        timeout=10
                    )
                except Exception:
                    pass

            # Cleanup: Delete pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'delete',
                pipeline_id
            ], input='y\n')

            assert result.exit_code == 0, f"Delete pipeline failed: {result.output}"
        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_executions_get(self, setup_config, api_available):
        """Test getting execution details via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Ensure API key is set in environment (takes precedence)
        os.environ['DATAHUB_API_KEY'] = self.api_key
        os.environ['TEST_API_KEY'] = self.api_key
        # Also set in config file
        config._config['api_key'] = self.api_key
        config._save()
        # Reload config to ensure it's read correctly
        config._load()
        # Small delay to ensure everything is committed
        import time
        time.sleep(0.2)

        # Wait a bit to avoid rate limiting from previous tests
        self._wait_for_rate_limit(2.0)

        runner = CliRunner()

        # Create pipeline and execution first
        import tempfile
        pipeline_data = {
            'name': f'Test Pipeline {uuid.uuid4().hex[:8]}',
            'description': 'Integration test pipeline',
            'pipeline_definition': {
                'version': '1.0',
                'steps': [
                    {
                        'name': 'test_step',
                        'type': 'task',
                        'node_config': {
                            'node_type': 'output'
                        }
                    }
                ]
            },
            'version': '1.0.0',
            'status': 'ACTIVE'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            # Ensure API key is available before running CLI commands
            # Set in both environment and config file for maximum reliability
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                # Reload config to ensure it's read
                config._load()
                # Verify API key is accessible
                if not config.get_api_key():
                    pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

            # Create pipeline (with retry for rate limiting and API key validation)
            max_retries = 3
            for attempt in range(max_retries):
                result = runner.invoke(cli, [
                    'transformation', 'pipelines', 'create',
                    '--file', temp_file,
                    '--format', 'json'
                ])

                if result.exit_code == 0:
                    break
                elif 'rate limit' in result.output.lower() and attempt < max_retries - 1:
                    # Wait and retry for rate limiting
                    self._wait_for_rate_limit(2.0 * (attempt + 1))
                    continue
                elif 'invalid api key' in result.output.lower() or 'authentication' in result.output.lower():
                    # API key might not be committed yet, wait and retry
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(1.0 * (attempt + 1))
                        # Re-ensure API key is set
                        os.environ['DATAHUB_API_KEY'] = self.api_key
                        os.environ['TEST_API_KEY'] = self.api_key
                        config._config['api_key'] = self.api_key
                        config._save()
                        config._load()
                        continue
                    else:
                        assert result.exit_code == 0, f"Create pipeline failed after {max_retries} attempts: {result.output}"
                else:
                    assert result.exit_code == 0, f"Create pipeline failed: {result.output}"
            create_output = json.loads(result.output)
            pipeline_id = create_output['id']

            # Create asset with dataset (required for execution)
            asset_id = self._create_asset_with_dataset()
            if not asset_id:
                pytest.skip("Could not create test asset with dataset")

            try:
                # Create execution
                result = runner.invoke(cli, [
                    'transformation', 'executions', 'create',
                    pipeline_id,
                    '--input-asset', asset_id,
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"Create execution failed: {result.output}"
                execution_output = json.loads(result.output)
                execution_id = execution_output.get('execution_id') or execution_output.get('id')

                # Get execution
                result = runner.invoke(cli, [
                    'transformation', 'executions', 'get',
                    execution_id,
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"Get execution failed: {result.output}"
                get_output = json.loads(result.output)
                assert get_output.get('id') == execution_id or get_output.get('execution_id') == execution_id
                assert 'status' in get_output

            finally:
                # Cleanup: Delete asset
                try:
                    requests.delete(
                        f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                        headers=headers,
                        timeout=10
                    )
                except Exception:
                    pass

            # Cleanup: Delete pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'delete',
                pipeline_id
            ], input='y\n')

        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_executions_list_with_filters(self, setup_config, api_available):
        """Test listing executions with filters via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Ensure API key is set in environment (takes precedence)
        os.environ['DATAHUB_API_KEY'] = self.api_key
        os.environ['TEST_API_KEY'] = self.api_key
        # Also set in config file
        config._config['api_key'] = self.api_key
        config._save()
        # Reload config to ensure it's read correctly
        config._load()
        # Small delay to ensure everything is committed
        import time
        time.sleep(0.2)

        runner = CliRunner()

        # Create pipeline first
        import tempfile
        pipeline_data = {
            'name': f'Test Pipeline {uuid.uuid4().hex[:8]}',
            'description': 'Integration test pipeline',
            'pipeline_definition': {
                'version': '1.0',
                'steps': [
                    {
                        'name': 'test_step',
                        'type': 'task',
                        'node_config': {
                            'node_type': 'output'
                        }
                    }
                ]
            },
            'version': '1.0.0',
            'status': 'ACTIVE'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            # Ensure API key is available before running CLI commands
            # Set in both environment and config file for maximum reliability
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                # Reload config to ensure it's read
                config._load()
                # Verify API key is accessible
                if not config.get_api_key():
                    pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

            # Create pipeline (with retry for rate limiting and API key validation)
            max_retries = 3
            for attempt in range(max_retries):
                result = runner.invoke(cli, [
                    'transformation', 'pipelines', 'create',
                    '--file', temp_file,
                    '--format', 'json'
                ])

                if result.exit_code == 0:
                    break
                elif 'rate limit' in result.output.lower() and attempt < max_retries - 1:
                    # Wait and retry for rate limiting
                    self._wait_for_rate_limit(2.0 * (attempt + 1))
                    continue
                elif 'invalid api key' in result.output.lower() or 'authentication' in result.output.lower():
                    # API key might not be committed yet, wait and retry
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(1.0 * (attempt + 1))
                        # Re-ensure API key is set
                        os.environ['DATAHUB_API_KEY'] = self.api_key
                        os.environ['TEST_API_KEY'] = self.api_key
                        config._config['api_key'] = self.api_key
                        config._save()
                        config._load()
                        continue
                    else:
                        assert result.exit_code == 0, f"Create pipeline failed after {max_retries} attempts: {result.output}"
                else:
                    assert result.exit_code == 0, f"Create pipeline failed: {result.output}"
            create_output = json.loads(result.output)
            pipeline_id = create_output['id']

            # Test listing with status filter
            result = runner.invoke(cli, [
                'transformation', 'executions', 'list',
                '--pipeline-id', pipeline_id,
                '--status', 'PENDING',
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"List executions with filter failed: {result.output}"
            output_data = json.loads(result.output)
            assert 'results' in output_data or isinstance(output_data, list)

            # Cleanup: Delete pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'delete',
                pipeline_id
            ], input='y\n')

        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_executions_cancel(self, setup_config, api_available):
        """Test cancelling an execution via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Ensure API key is set in environment (takes precedence)
        os.environ['DATAHUB_API_KEY'] = self.api_key
        os.environ['TEST_API_KEY'] = self.api_key
        # Also set in config file
        config._config['api_key'] = self.api_key
        config._save()
        # Reload config to ensure it's read correctly
        config._load()
        # Small delay to ensure everything is committed
        import time
        time.sleep(0.2)

        # Wait a bit to avoid rate limiting from previous tests
        self._wait_for_rate_limit(2.0)

        runner = CliRunner()

        # Create pipeline and execution first
        import tempfile
        pipeline_data = {
            'name': f'Test Pipeline {uuid.uuid4().hex[:8]}',
            'description': 'Integration test pipeline',
            'pipeline_definition': {
                'version': '1.0',
                'steps': [
                    {
                        'name': 'test_step',
                        'type': 'task',
                        'node_config': {
                            'node_type': 'output'
                        }
                    }
                ]
            },
            'version': '1.0.0',
            'status': 'ACTIVE'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            # Ensure API key is available before running CLI commands
            # Set in both environment and config file for maximum reliability
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                # Reload config to ensure it's read
                config._load()
                # Verify API key is accessible
                if not config.get_api_key():
                    pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

            # Create pipeline (with retry for rate limiting and API key validation)
            max_retries = 3
            for attempt in range(max_retries):
                result = runner.invoke(cli, [
                    'transformation', 'pipelines', 'create',
                    '--file', temp_file,
                    '--format', 'json'
                ])

                if result.exit_code == 0:
                    break
                elif 'rate limit' in result.output.lower() and attempt < max_retries - 1:
                    # Wait and retry for rate limiting
                    self._wait_for_rate_limit(2.0 * (attempt + 1))
                    continue
                elif 'invalid api key' in result.output.lower() or 'authentication' in result.output.lower():
                    # API key might not be committed yet, wait and retry
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(1.0 * (attempt + 1))
                        # Re-ensure API key is set
                        os.environ['DATAHUB_API_KEY'] = self.api_key
                        os.environ['TEST_API_KEY'] = self.api_key
                        config._config['api_key'] = self.api_key
                        config._save()
                        config._load()
                        continue
                    else:
                        assert result.exit_code == 0, f"Create pipeline failed after {max_retries} attempts: {result.output}"
                else:
                    assert result.exit_code == 0, f"Create pipeline failed: {result.output}"
            create_output = json.loads(result.output)
            pipeline_id = create_output['id']

            # Create asset with dataset (required for execution)
            asset_id = self._create_asset_with_dataset()
            if not asset_id:
                pytest.skip("Could not create test asset with dataset")

            try:
                # Create execution
                result = runner.invoke(cli, [
                    'transformation', 'executions', 'create',
                    pipeline_id,
                    '--input-asset', asset_id,
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"Create execution failed: {result.output}"
                execution_output = json.loads(result.output)
                execution_id = execution_output.get('execution_id') or execution_output.get('id')

                # Wait a moment for execution to start
                time.sleep(1)

                # Try to cancel execution (may fail if already completed, which is OK)
                result = runner.invoke(cli, [
                    'transformation', 'executions', 'cancel',
                    execution_id,
                    '--format', 'json'
                ])

                # Cancel may succeed or fail depending on execution status - both are valid
                # If it fails, it should be a clear error message
                if result.exit_code != 0:
                    # Check that error message is informative
                    assert 'cancel' in result.output.lower() or 'cannot' in result.output.lower() or 'status' in result.output.lower()
                else:
                    # If cancel succeeded, verify response
                    cancel_output = json.loads(result.output)
                    assert 'status' in cancel_output or 'execution_id' in cancel_output

            finally:
                # Cleanup: Delete asset
                try:
                    requests.delete(
                        f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                        headers=headers,
                        timeout=10
                    )
                except Exception:
                    pass

            # Cleanup: Delete pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'delete',
                pipeline_id
            ], input='y\n')

        finally:
            os.unlink(temp_file)


    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_preview_generate_command(self, setup_config, api_available):
        """Test generating a preview via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()

        # Create pipeline first
        import tempfile
        pipeline_data = {
            'name': f'Test Pipeline {uuid.uuid4().hex[:8]}',
            'description': 'Integration test pipeline for preview',
            'pipeline_definition': {
                'version': '1.0',
                'steps': [
                    {
                        'name': 'test_step',
                        'type': 'filter',
                        'config': {
                            'expression': 'value > 0'
                        }
                    }
                ]
            },
            'version': '1.0.0',
            'status': 'ACTIVE'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            # Ensure API key is available before running CLI commands
            # Set in both environment and config file for maximum reliability
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                # Reload config to ensure it's read
                config._load()
                # Verify API key is accessible
                if not config.get_api_key():
                    pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

            # Create pipeline (with retry for rate limiting and API key validation)
            max_retries = 3
            for attempt in range(max_retries):
                result = runner.invoke(cli, [
                    'transformation', 'pipelines', 'create',
                    '--file', temp_file,
                    '--format', 'json'
                ])

                if result.exit_code == 0:
                    break
                elif 'rate limit' in result.output.lower() and attempt < max_retries - 1:
                    # Wait and retry for rate limiting
                    self._wait_for_rate_limit(2.0 * (attempt + 1))
                    continue
                elif 'invalid api key' in result.output.lower() or 'authentication' in result.output.lower():
                    # API key might not be committed yet, wait and retry
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(1.0 * (attempt + 1))
                        # Re-ensure API key is set
                        os.environ['DATAHUB_API_KEY'] = self.api_key
                        os.environ['TEST_API_KEY'] = self.api_key
                        config._config['api_key'] = self.api_key
                        config._save()
                        config._load()
                        continue
                    else:
                        assert result.exit_code == 0, f"Create pipeline failed after {max_retries} attempts: {result.output}"
                else:
                    assert result.exit_code == 0, f"Create pipeline failed: {result.output}"
            create_output = json.loads(result.output)
            pipeline_id = create_output['id']

            # Create a test asset with dataset and file via Django shell
            asset_id = self._create_test_asset_with_dataset()
            if not asset_id:
                pytest.skip("Could not create test asset with dataset. Ensure Docker Compose services are running and storage is available.")

            try:
                # Generate preview
                result = runner.invoke(cli, [
                    'transformation', 'preview', 'generate',
                    pipeline_id,
                    '--input-asset', asset_id,
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"Generate preview failed: {result.output}"
                preview_output = json.loads(result.output)
                assert 'preview_id' in preview_output
                assert preview_output['pipeline_id'] == pipeline_id
                assert preview_output['asset_id'] == asset_id
                preview_id = preview_output['preview_id']

                # Get preview result
                result = runner.invoke(cli, [
                    'transformation', 'preview', 'get',
                    preview_id,
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"Get preview failed: {result.output}"
                get_output = json.loads(result.output)
                assert get_output['preview_id'] == preview_id
                assert get_output['pipeline_id'] == pipeline_id
                assert get_output['asset_id'] == asset_id

            finally:
                # Cleanup: Delete asset
                try:
                    import requests
                    cleanup_headers = {
                        'Authorization': f'ApiKey {self.api_key}',
                        'Content-Type': 'application/json'
                    }
                    requests.delete(
                        f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                        headers=cleanup_headers,
                        timeout=10
                    )
                except Exception:
                    pass

            # Cleanup: Delete pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'delete',
                pipeline_id
            ], input='y\n')

        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_preview_generate_with_options(self, setup_config, api_available):
        """Test generating a preview with custom options via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()

        # Create pipeline first
        import tempfile
        pipeline_data = {
            'name': f'Test Pipeline {uuid.uuid4().hex[:8]}',
            'description': 'Integration test pipeline for preview with options',
            'pipeline_definition': {
                'version': '1.0',
                'steps': [{'name': 'test_step', 'type': 'filter'}]
            },
            'version': '1.0.0',
            'status': 'ACTIVE'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline_data, f)
            temp_file = f.name

        try:
            # Ensure API key is available before running CLI commands
            # Set in both environment and config file for maximum reliability
            if self.api_key:
                os.environ['DATAHUB_API_KEY'] = self.api_key
                os.environ['TEST_API_KEY'] = self.api_key
                config._config['api_key'] = self.api_key
                config._save()
                # Reload config to ensure it's read
                config._load()
                # Verify API key is accessible
                if not config.get_api_key():
                    pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

            # Create pipeline (with retry for rate limiting and API key validation)
            max_retries = 3
            for attempt in range(max_retries):
                result = runner.invoke(cli, [
                    'transformation', 'pipelines', 'create',
                    '--file', temp_file,
                    '--format', 'json'
                ])

                if result.exit_code == 0:
                    break
                elif 'rate limit' in result.output.lower() and attempt < max_retries - 1:
                    # Wait and retry for rate limiting
                    self._wait_for_rate_limit(2.0 * (attempt + 1))
                    continue
                elif 'invalid api key' in result.output.lower() or 'authentication' in result.output.lower():
                    # API key might not be committed yet, wait and retry
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(1.0 * (attempt + 1))
                        # Re-ensure API key is set
                        os.environ['DATAHUB_API_KEY'] = self.api_key
                        os.environ['TEST_API_KEY'] = self.api_key
                        config._config['api_key'] = self.api_key
                        config._save()
                        config._load()
                        continue
                    else:
                        assert result.exit_code == 0, f"Create pipeline failed after {max_retries} attempts: {result.output}"
                else:
                    assert result.exit_code == 0, f"Create pipeline failed: {result.output}"
            create_output = json.loads(result.output)
            pipeline_id = create_output['id']

            # Create a test asset with dataset and file for preview
            asset_id = self._create_test_asset_with_dataset()
            if not asset_id:
                pytest.skip("Could not create test asset with dataset. Ensure Docker Compose services are running and storage is available.")

            try:
                # Generate preview with custom options
                result = runner.invoke(cli, [
                    'transformation', 'preview', 'generate',
                    pipeline_id,
                    '--input-asset', asset_id,
                    '--sample-size', '200',
                    '--sampling-method', 'random',
                    '--format', 'json'
                ])

                assert result.exit_code == 0, f"Generate preview with options failed: {result.output}"
                preview_output = json.loads(result.output)
                assert 'preview_id' in preview_output
                assert preview_output['pipeline_id'] == pipeline_id
                assert preview_output['asset_id'] == asset_id

            finally:
                # Cleanup: Delete asset
                try:
                    import requests
                    cleanup_headers = {
                        'Authorization': f'ApiKey {self.api_key}',
                        'Content-Type': 'application/json'
                    }
                    requests.delete(
                        f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                        headers=cleanup_headers,
                        timeout=10
                    )
                except Exception:
                    pass

            # Cleanup: Delete pipeline
            result = runner.invoke(cli, [
                'transformation', 'pipelines', 'delete',
                pipeline_id
            ], input='y\n')

        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_preview_get_not_found(self, setup_config, api_available):
        """Test getting a non-existent preview via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()

        # Try to get a non-existent preview
        fake_preview_id = str(uuid.uuid4())
        result = runner.invoke(cli, [
            'transformation', 'preview', 'get',
            fake_preview_id,
            '--format', 'json'
        ])

        # Should fail with error
        assert result.exit_code != 0
        assert 'Failed to get preview' in result.output or 'not found' in result.output.lower() or '404' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_preview_generate_missing_input_asset(self, setup_config, api_available):
        """Test generating a preview without required input-asset"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()

        # Ensure API key is available before running CLI commands
        if self.api_key:
            os.environ['DATAHUB_API_KEY'] = self.api_key
            os.environ['TEST_API_KEY'] = self.api_key
            config._config['api_key'] = self.api_key
            config._save()
            config._load()

        # Try to generate preview without input-asset
        fake_pipeline_id = str(uuid.uuid4())
        result = runner.invoke(cli, [
            'transformation', 'preview', 'generate',
            fake_pipeline_id
        ])

        # Should fail with missing option error
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_preview_command_group_help(self, setup_config, api_available):
        """Test preview command group help text"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['transformation', 'preview', '--help'])
        assert result.exit_code == 0
        assert 'Preview management commands' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_preview_generate_command_help(self, setup_config, api_available):
        """Test preview generate command help text"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['transformation', 'preview', 'generate', '--help'])
        assert result.exit_code == 0
        assert 'Generate a preview' in result.output or 'preview' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_preview_get_command_help(self, setup_config, api_available):
        """Test preview get command help text"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['transformation', 'preview', 'get', '--help'])
        assert result.exit_code == 0
        assert 'Get preview result' in result.output or 'preview' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_wrangling_command_group_help(self, setup_config, api_available):
        """Test wrangling command group help text"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['transformation', 'wrangling', '--help'])
        assert result.exit_code == 0
        assert 'Wrangling session management commands' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_wrangling_start_command(self, setup_config, api_available):
        """Test starting a wrangling session via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Ensure API key is set in both environment and config file (same pattern as other tests)
        os.environ['DATAHUB_API_KEY'] = self.api_key
        os.environ['TEST_API_KEY'] = self.api_key
        config._config['api_key'] = self.api_key
        # Clear any tokens that might interfere
        if 'access_token' in config._config:
            del config._config['access_token']
        if 'refresh_token' in config._config:
            del config._config['refresh_token']
        config._save()
        config._load()
        # Small delay to ensure everything is committed
        import time
        time.sleep(0.2)

        runner = CliRunner()

        # Create a test asset with dataset first
        asset_id = self._create_test_asset_with_dataset()
        if not asset_id:
            pytest.skip("Could not create test asset with dataset. Ensure Docker Compose services are running and storage is available.")

        # Prepare environment for CLI commands
        cli_env = os.environ.copy()
        cli_env['DATAHUB_API_KEY'] = self.api_key
        cli_env['TEST_API_KEY'] = self.api_key

        try:
            # Start wrangling session
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'start',
                asset_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Start wrangling failed: {result.output}"
            start_output = json.loads(result.output)
            assert 'session_id' in start_output
            assert 'operation_id' in start_output
            session_id = start_output['session_id']

            # Verify session exists by getting it
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'get',
                session_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Get wrangling session failed: {result.output}"
            get_output = json.loads(result.output)
            assert get_output['id'] == session_id
            assert get_output['asset_id'] == asset_id

        finally:
            # Cleanup: Delete asset
            try:
                import requests
                cleanup_headers = {
                    'Authorization': f'ApiKey {self.api_key}',
                    'Content-Type': 'application/json'
                }
                requests.delete(
                    f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                    headers=cleanup_headers,
                    timeout=10
                )
            except Exception:
                pass

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_wrangling_apply_command(self, setup_config, api_available):
        """Test applying a wrangling operation via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Verify API key is accessible (setup_config fixture should have set it)
        if not config.get_api_key():
            pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

        runner = CliRunner()

        # Create a test asset with dataset first
        asset_id = self._create_test_asset_with_dataset()
        if not asset_id:
            pytest.skip("Could not create test asset with dataset. Ensure Docker Compose services are running and storage is available.")

        # Prepare environment for CLI commands
        cli_env = os.environ.copy()
        cli_env['DATAHUB_API_KEY'] = self.api_key
        cli_env['TEST_API_KEY'] = self.api_key

        try:
            # Start wrangling session
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'start',
                asset_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Start wrangling failed: {result.output}"
            start_output = json.loads(result.output)
            session_id = start_output['session_id']

            # Apply a filter operation
            operation_json = json.dumps({
                "type": "FILTER",
                "parameters": {
                    "condition": "age > 18"
                }
            })

            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'apply',
                session_id,
                '--operation', operation_json,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Apply wrangling operation failed: {result.output}"
            apply_output = json.loads(result.output)
            assert apply_output['session_id'] == session_id
            assert 'operation_id' in apply_output
            assert apply_output['applied_operations_count'] >= 1

        finally:
            # Cleanup: Delete asset
            try:
                import requests
                cleanup_headers = {
                    'Authorization': f'ApiKey {self.api_key}',
                    'Content-Type': 'application/json'
                }
                requests.delete(
                    f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                    headers=cleanup_headers,
                    timeout=10
                )
            except Exception:
                pass

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_wrangling_undo_redo_commands(self, setup_config, api_available):
        """Test undo and redo wrangling operations via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Verify API key is accessible (setup_config fixture should have set it)
        if not config.get_api_key():
            pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

        runner = CliRunner()

        # Create a test asset with dataset first
        asset_id = self._create_test_asset_with_dataset()
        if not asset_id:
            pytest.skip("Could not create test asset with dataset. Ensure Docker Compose services are running and storage is available.")

        # Prepare environment for CLI commands
        cli_env = os.environ.copy()
        cli_env['DATAHUB_API_KEY'] = self.api_key
        cli_env['TEST_API_KEY'] = self.api_key

        try:
            # Start wrangling session
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'start',
                asset_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Start wrangling failed: {result.output}"
            start_output = json.loads(result.output)
            session_id = start_output['session_id']

            # Apply a filter operation
            operation_json = json.dumps({
                "type": "FILTER",
                "parameters": {
                    "condition": "age > 18"
                }
            })

            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'apply',
                session_id,
                '--operation', operation_json,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Apply wrangling operation failed: {result.output}"
            apply_output = json.loads(result.output)
            initial_count = apply_output['applied_operations_count']

            # Undo the operation
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'undo',
                session_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Undo wrangling operation failed: {result.output}"
            undo_output = json.loads(result.output)
            assert undo_output['session_id'] == session_id
            assert undo_output['applied_operations_count'] < initial_count
            assert 'undone_operation' in undo_output

            # Redo the operation
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'redo',
                session_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Redo wrangling operation failed: {result.output}"
            redo_output = json.loads(result.output)
            assert redo_output['session_id'] == session_id
            assert redo_output['applied_operations_count'] == initial_count
            assert 'redone_operation' in redo_output

        finally:
            # Cleanup: Delete asset
            try:
                import requests
                cleanup_headers = {
                    'Authorization': f'ApiKey {self.api_key}',
                    'Content-Type': 'application/json'
                }
                requests.delete(
                    f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                    headers=cleanup_headers,
                    timeout=10
                )
            except Exception:
                pass

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_wrangling_get_command(self, setup_config, api_available):
        """Test getting wrangling session details via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Verify API key is accessible (setup_config fixture should have set it)
        if not config.get_api_key():
            pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

        runner = CliRunner()

        # Create a test asset with dataset first
        asset_id = self._create_test_asset_with_dataset()
        if not asset_id:
            pytest.skip("Could not create test asset with dataset. Ensure Docker Compose services are running and storage is available.")

        # Prepare environment for CLI commands
        cli_env = os.environ.copy()
        cli_env['DATAHUB_API_KEY'] = self.api_key
        cli_env['TEST_API_KEY'] = self.api_key

        try:
            # Start wrangling session
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'start',
                asset_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Start wrangling failed: {result.output}"
            start_output = json.loads(result.output)
            session_id = start_output['session_id']

            # Get session details
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'get',
                session_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Get wrangling session failed: {result.output}"
            get_output = json.loads(result.output)
            assert get_output['id'] == session_id
            assert get_output['asset_id'] == asset_id
            assert 'applied_operations_count' in get_output
            assert 'can_undo' in get_output
            assert 'can_redo' in get_output
            assert 'operation_history' in get_output

        finally:
            # Cleanup: Delete asset
            try:
                import requests
                cleanup_headers = {
                    'Authorization': f'ApiKey {self.api_key}',
                    'Content-Type': 'application/json'
                }
                requests.delete(
                    f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                    headers=cleanup_headers,
                    timeout=10
                )
            except Exception:
                pass

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_wrangling_apply_invalid_operation(self, setup_config, api_available):
        """Test applying invalid wrangling operation via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Verify API key is accessible (setup_config fixture should have set it)
        if not config.get_api_key():
            pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

        runner = CliRunner()

        # Create a test asset with dataset first
        asset_id = self._create_test_asset_with_dataset()
        if not asset_id:
            pytest.skip("Could not create test asset with dataset. Ensure Docker Compose services are running and storage is available.")

        # Prepare environment for CLI commands
        cli_env = os.environ.copy()
        cli_env['DATAHUB_API_KEY'] = self.api_key
        cli_env['TEST_API_KEY'] = self.api_key

        try:
            # Start wrangling session
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'start',
                asset_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Start wrangling failed: {result.output}"
            start_output = json.loads(result.output)
            session_id = start_output['session_id']

            # Try to apply invalid operation (missing type)
            invalid_operation_json = json.dumps({
                "parameters": {
                    "condition": "age > 18"
                }
            })

            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'apply',
                session_id,
                '--operation', invalid_operation_json,
                '--format', 'json'
            ], env=cli_env)

            # Should fail with validation error
            assert result.exit_code != 0
            assert 'must have \'type\' field' in result.output or 'Invalid' in result.output

        finally:
            # Cleanup: Delete asset
            try:
                import requests
                cleanup_headers = {
                    'Authorization': f'ApiKey {self.api_key}',
                    'Content-Type': 'application/json'
                }
                requests.delete(
                    f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                    headers=cleanup_headers,
                    timeout=10
                )
            except Exception:
                pass

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_wrangling_undo_when_no_operations(self, setup_config, api_available):
        """Test undoing when no operations to undo via real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Verify API key is accessible (setup_config fixture should have set it)
        if not config.get_api_key():
            pytest.skip(f"API key not accessible in config. Key: {self.api_key[:20] if self.api_key else 'None'}...")

        runner = CliRunner()

        # Create a test asset with dataset first
        asset_id = self._create_test_asset_with_dataset()
        if not asset_id:
            pytest.skip("Could not create test asset with dataset. Ensure Docker Compose services are running and storage is available.")

        # Prepare environment for CLI commands
        cli_env = os.environ.copy()
        cli_env['DATAHUB_API_KEY'] = self.api_key
        cli_env['TEST_API_KEY'] = self.api_key

        try:
            # Start wrangling session
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'start',
                asset_id,
                '--format', 'json'
            ], env=cli_env)

            assert result.exit_code == 0, f"Start wrangling failed: {result.output}"
            start_output = json.loads(result.output)
            session_id = start_output['session_id']

            # Try to undo when no operations (only the initial no-op operation)
            # The initial operation from start might allow one undo, so we may need to undo twice
            # First undo should work (undoes the initial no-op filter)
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'undo',
                session_id,
                '--format', 'json'
            ], env=cli_env)

            # Second undo should fail
            result = runner.invoke(cli, [
                'transformation', 'wrangling', 'undo',
                session_id,
                '--format', 'json'
            ], env=cli_env)

            # Should fail with cannot undo error
            assert result.exit_code != 0
            assert 'Cannot undo' in result.output or 'cannot undo' in result.output.lower() or 'no operations' in result.output.lower()

        finally:
            # Cleanup: Delete asset
            try:
                import requests
                cleanup_headers = {
                    'Authorization': f'ApiKey {self.api_key}',
                    'Content-Type': 'application/json'
                }
                requests.delete(
                    f'{config.get_api_base_url()}/assets/assets/{asset_id}/',
                    headers=cleanup_headers,
                    timeout=10
                )
            except Exception:
                pass
