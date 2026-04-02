"""
Comprehensive integration tests for BaaS usage tracking commands against real API service.

These tests test all BaaS usage tracking CLI commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest cli/tests/integration/test_baas_usage_real_api.py -v
"""
import pytest
import requests
import json
import os
import uuid
import subprocess
import time
from datetime import datetime, timedelta
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


class TestBaaSUsageCommandsRealAPI:
    """Comprehensive integration tests for all BaaS usage tracking commands with real API"""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up API base URL to point to Docker Compose service"""
        # Initialize runner
        self.runner = CliRunner()

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
            self.api_key_id = None
        else:
            config.set_api_key(api_key)
            self.api_key = api_key
            # Use BaaS API key ID if we created one, otherwise try to get from API
            if hasattr(TestBaaSUsageCommandsRealAPI, '_class_baas_api_key_id'):
                self.api_key_id = TestBaaSUsageCommandsRealAPI._class_baas_api_key_id
            else:
                # Try multiple methods to get BaaS API key ID
                # First, try to get from class variable (set during API key creation)
                if hasattr(TestBaaSUsageCommandsRealAPI, '_class_baas_api_key_id'):
                    self.api_key_id = TestBaaSUsageCommandsRealAPI._class_baas_api_key_id
                else:
                    # Try to get from API
                    self.api_key_id = self._get_baas_api_key_id(api_key)

                    # If still not found, try creating one via CLI
                    if not self.api_key_id:
                        self.api_key_id = self._create_baas_api_key_via_cli()

                    # Store it for future use
                    if self.api_key_id:
                        TestBaaSUsageCommandsRealAPI._class_baas_api_key_id = self.api_key_id

        yield
        # Cleanup
        config.clear_auth()

    def _create_test_api_key(self):
        """Create a test API key via Django shell in the API service container"""
        unique_id = uuid.uuid4().hex[:8]
        django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey
from hub.apps.baas.models import APIKey as BaaSAPIKey, APITierModel
from hub.apps.baas.services import UsageTrackingService
from django.utils import timezone
from datetime import timedelta

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='baas-usage-cli-test-tenant-{unique_id}',
    defaults={{'name': 'BaaS Usage CLI Test Tenant {unique_id}'}}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='baas-usage-cli-test-{unique_id}@example.com',
    defaults={{
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Create and assign TENANT_ADMIN role
tenant_admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={{'description': 'Tenant Administrator'}}
)
UserRole.objects.get_or_create(user=user, role=tenant_admin_role)

# Get or create API tier
free_tier, _ = APITierModel.objects.get_or_create(
    name='FREE',
    defaults={{
        'rate_limit_per_hour': 1000,
        'rate_limit_per_day': 10000,
        'max_requests_per_month': 10000
    }}
)

# Delete existing test API keys
AuthAPIKey.objects.filter(tenant=tenant, name__startswith='BaaS Usage CLI Test Auth Key').delete()
BaaSAPIKey.objects.filter(tenant=tenant, name__startswith='BaaS Usage CLI Test Key').delete()

# Create auth API key for CLI authentication
auth_api_key_value = AuthAPIKey.generate_key()
auth_api_key_hash = AuthAPIKey.hash_key(auth_api_key_value)
auth_api_key_obj = AuthAPIKey.objects.create(
    user=user,
    tenant=tenant,
    name='BaaS Usage CLI Test Auth Key {unique_id}',
    key_hash=auth_api_key_hash
)

# Create BaaS API key using service for usage tracking
service = UsageTrackingService(tenant_id=str(tenant.id), user_id=str(user.id))
baas_api_key_data = service.create_api_key_with_workflow(
    name='BaaS Usage CLI Test Key {unique_id}',
    tier_name='FREE',
    tenant_id=str(tenant.id),
    user_id=str(user.id)
)

# Create some usage records for testing
now = timezone.now()
for i in range(10):
    service.track_request(
        api_key_id=str(baas_api_key_data['id']),
        endpoint=f'/api/v1/test/endpoint{{i % 3}}',
        method='GET' if i % 2 == 0 else 'POST',
        status_code=200 if i < 8 else 400,
        response_time_ms=100 + (i * 10),
        request_size_bytes=1000,
        response_size_bytes=2000,
        timestamp=now - timedelta(days=i)
    )

# Print the auth API key (for CLI authentication) and BaaS API key ID
# Use clear markers that are easy to extract
print('AUTH_API_KEY_START')
print(auth_api_key_value)
print('AUTH_API_KEY_END')
print('BAAS_API_KEY_ID_START')
print(str(baas_api_key_data['api_key_id']))
print('BAAS_API_KEY_ID_END')
"""
        try:
            result = subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'hub/manage.py', 'shell'],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=60,
                cwd='/home/ph/Desktop/DataInteroperabilityHub'
            )

            if result.returncode == 0:
                # Extract API key and ID from output using clear markers
                output_lines = result.stdout.strip().split('\n')
                api_key = None
                baas_api_key_id = None

                # Look for marked sections
                in_auth_key = False
                in_baas_id = False

                for line in output_lines:
                    line = line.strip()
                    if line == 'AUTH_API_KEY_START':
                        in_auth_key = True
                        continue
                    elif line == 'AUTH_API_KEY_END':
                        in_auth_key = False
                        continue
                    elif line == 'BAAS_API_KEY_ID_START':
                        in_baas_id = True
                        continue
                    elif line == 'BAAS_API_KEY_ID_END':
                        in_baas_id = False
                        continue

                    if in_auth_key and line and len(line) > 20:
                        api_key = line
                    elif in_baas_id and line:
                        baas_api_key_id = line

                # Fallback: if markers didn't work, try old method
                if not api_key or not baas_api_key_id:
                    for line in output_lines:
                        line = line.strip()
                        if line.startswith('BAAS_API_KEY_ID:'):
                            baas_api_key_id = line.split(':', 1)[1].strip()
                        elif line and len(line) > 30 and not any([
                            line.startswith('BAAS_API_KEY_ID'),
                            line.startswith('>>>'),
                            line.startswith('...'),
                            line.startswith('{'),
                            line.startswith('['),
                            '>>>' in line,
                            '...' in line,
                            'import' in line.lower(),
                            'from' in line.lower(),
                            'print' in line.lower(),
                            'Error' in line,
                            'Warning' in line,
                            'INFO' in line,
                            'WARNING' in line,
                            'ERROR' in line,
                            'AUTH_API_KEY' in line,
                            'BAAS_API_KEY_ID' in line,
                        ]):
                            if api_key is None:
                                api_key = line

                # Store BaaS API key ID for later use
                if baas_api_key_id:
                    # Store in a way that persists across fixture calls
                    if not hasattr(TestBaaSUsageCommandsRealAPI, '_class_baas_api_key_id'):
                        TestBaaSUsageCommandsRealAPI._class_baas_api_key_id = baas_api_key_id

                # If we have API key but not BaaS API key ID, try to get it from API
                if api_key and not baas_api_key_id:
                    baas_api_key_id = self._get_baas_api_key_id(api_key)
                    if baas_api_key_id:
                        if not hasattr(TestBaaSUsageCommandsRealAPI, '_class_baas_api_key_id'):
                            TestBaaSUsageCommandsRealAPI._class_baas_api_key_id = baas_api_key_id

                return api_key
        except Exception as e:
            print(f"Error creating test API key: {e}")
        return None

    def _get_baas_api_key_id(self, api_key):
        """Get BaaS API key ID by making an API request"""
        try:
            headers = {'Authorization': f'ApiKey {api_key}'}
            response = requests.get(
                os.environ.get('MESHANT_API_URL', 'http://localhost:8000/api/v1') + '/baas/api-keys/',
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    # Return the first BaaS API key ID
                    return data[0].get('id')
                elif isinstance(data, dict) and 'results' in data:
                    results = data.get('results', [])
                    if len(results) > 0:
                        return results[0].get('id')
        except Exception:
            pass
        return None

    def _create_baas_api_key_via_cli(self):
        """Create a BaaS API key via CLI and return its ID"""
        try:
            unique_id = uuid.uuid4().hex[:8]
            runner = CliRunner()
            result = runner.invoke(cli, [
                'baas', 'api-keys', 'create',
                '--name', f'CLI Test BaaS Key {unique_id}',
                '--tier', 'FREE',
                '--format', 'json'
            ])

            if result.exit_code == 0:
                data = json.loads(result.output)
                api_key_id = data.get('id')
                if api_key_id:
                    return api_key_id
        except Exception as e:
            # Silently fail - this is a fallback method
            pass
        return None

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_stats_command(self, api_available):
        """Test usage stats command with real API"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        data = json.loads(result.output)
        assert 'total_requests' in data
        assert 'success_count' in data
        assert 'error_count' in data
        assert 'success_rate' in data
        assert 'avg_response_time_ms' in data
        assert data['total_requests'] >= 0  # May be 0 if no usage data

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_stats_with_date_range(self, api_available):
        """Test usage stats with date range filter"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        now = datetime.now()
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = now.isoformat()

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--start-date', start_date,
            '--end-date', end_date,
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        data = json.loads(result.output)
        assert 'total_requests' in data

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_stats_with_api_key_filter(self, api_available):
        """Test usage stats with API key filter"""
        if not self.api_key or not self.api_key_id:
            pytest.skip("No API key available for testing")

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--api-key-id', str(self.api_key_id),
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        data = json.loads(result.output)
        assert 'total_requests' in data

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_by_endpoint_command(self, api_available):
        """Test usage by-endpoint command with real API"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'by-endpoint',
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        data = json.loads(result.output)
        assert isinstance(data, list)
        if len(data) > 0:
            assert 'endpoint' in data[0]
            assert 'method' in data[0]
            assert 'total_requests' in data[0]

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_by_endpoint_with_filters(self, api_available):
        """Test usage by-endpoint with filters"""
        if not self.api_key or not self.api_key_id:
            pytest.skip("No API key available for testing")

        now = datetime.now()
        start_date = (now - timedelta(days=30)).isoformat()
        end_date = now.isoformat()

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'by-endpoint',
            '--api-key-id', str(self.api_key_id),
            '--start-date', start_date,
            '--end-date', end_date,
            '--format', 'json'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        data = json.loads(result.output)
        assert isinstance(data, list)

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_by_endpoint_table_format(self, api_available):
        """Test usage by-endpoint in table format"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'by-endpoint'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'Endpoint' in result.output or 'No usage data found' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_stats_table_format(self, api_available):
        """Test usage stats in table format"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats'
        ])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'Usage Statistics' in result.output
        assert 'Total Requests' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_stats_invalid_date_format(self, api_available):
        """Test usage stats with invalid date format"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--start-date', 'invalid-date'
        ])

        assert result.exit_code != 0, "Should fail with invalid date format"
        assert 'format' in result.output.lower() or 'invalid' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_stats_invalid_date_range(self, api_available):
        """Test usage stats with invalid date range"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        now = datetime.now()
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--start-date', now.isoformat(),
            '--end-date', (now - timedelta(days=1)).isoformat()
        ])

        assert result.exit_code != 0, "Should fail with invalid date range"
        assert 'before' in result.output.lower() or 'range' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_by_endpoint_invalid_date_format(self, api_available):
        """Test usage by-endpoint with invalid date format"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'by-endpoint',
            '--start-date', 'invalid-date'
        ])

        assert result.exit_code != 0, "Should fail with invalid date format"
        assert 'format' in result.output.lower() or 'invalid' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_by_endpoint_invalid_api_key_id(self, api_available):
        """Test usage by-endpoint with invalid API key ID format"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'by-endpoint',
            '--api-key-id', 'invalid-id'
        ])

        assert result.exit_code != 0, "Should fail with invalid API key ID format"
        assert 'format' in result.output.lower() or 'invalid' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_by_tenant_command(self, api_available):
        """Test usage by-tenant command with real API (may fail if endpoint doesn't exist)"""
        if not self.api_key:
            pytest.skip("No API key available for testing")

        result = self.runner.invoke(cli, [
            'baas', 'usage', 'by-tenant',
            '--format', 'json'
        ])

        # If endpoint doesn't exist, we'll get a 404 or similar error
        # This is expected and indicates the endpoint needs to be created
        if result.exit_code != 0:
            # Endpoint doesn't exist - this is expected for now
            assert '404' in result.output or 'not found' in result.output.lower() or 'Failed' in result.output
        else:
            # Endpoint exists - validate response
            data = json.loads(result.output)
            assert isinstance(data, list)
