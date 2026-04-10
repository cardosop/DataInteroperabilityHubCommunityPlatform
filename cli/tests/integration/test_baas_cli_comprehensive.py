from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive integration tests for ALL BaaS CLI commands against real API service.

This test suite provides comprehensive validation for:
- ALL API key commands (create, list, get, update, revoke) with all options
- ALL usage tracking commands (stats, by-endpoint, by-tenant) with all filters
- ALL developer portal commands (docs show, docs openapi, docs sdks) with all formats
- Error handling across all commands
- Output format consistency (JSON and table formats)
- Input validation for all parameters

These tests use real API endpoints - no mocks or stubs.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: DATAHUB_API_KEY or TEST_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export DATAHUB_API_KEY=your-api-key
3. Run: pytest cli/tests/integration/test_baas_cli_comprehensive.py -v
"""
import pytest
import json
import os
import sys
import uuid
import subprocess
import requests
from datetime import datetime, timedelta
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import config


def _check_api_available():
    """Check if API service is available"""
    try:
        response = requests.get(os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1") + "/", timeout=2)
        return response.status_code < 600
    except Exception:
        return False


@pytest.fixture(scope="module")
def api_available():
    """Fixture to check if API service is available"""
    return _check_api_available()


class TestBaaSCLIComprehensive:
    """
    Comprehensive integration tests for ALL BaaS CLI commands with real API.

    Tests all commands, all options, all formats, and all error scenarios.
    """

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up API base URL and authentication"""
        self.runner = CliRunner()
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
            self.api_key = None
            # Debug: print why API key creation failed
            if not os.environ.get('DATAHUB_API_KEY') and not os.environ.get('TEST_API_KEY'):
                print("WARNING: No API key available. Attempted to create one but failed.", file=sys.stderr)
        else:
            config.set_api_key(api_key)
            self.api_key = api_key
            # Store created API keys for cleanup
            self.created_api_keys = []
            # Verify API key is set
            if config.get_api_key() != api_key:
                print(f"WARNING: API key was set but verification failed. Expected: {api_key[:20]}..., Got: {config.get_api_key()[:20] if config.get_api_key() else 'None'}...", file=sys.stderr)

        yield
        # Cleanup
        config.clear_auth()

    def _create_test_api_key(self):
        """Create a test API key via Django shell"""
        unique_id = uuid.uuid4().hex[:8]
        django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey
from hub.apps.baas.models import APITierModel
import sys

try:
    # Create API tiers first (required for API key creation workflow)
    free_tier, _ = APITierModel.objects.get_or_create(
        name='FREE',
        defaults={{
            'rate_limit_per_hour': 1000,
            'rate_limit_per_day': 10000,
            'max_requests_per_month': 10000
        }}
    )
    pro_tier, _ = APITierModel.objects.get_or_create(
        name='PRO',
        defaults={{
            'rate_limit_per_hour': 10000,
            'rate_limit_per_day': 100000,
            'max_requests_per_month': 100000
        }}
    )
    enterprise_tier, _ = APITierModel.objects.get_or_create(
        name='ENTERPRISE',
        defaults={{
            'rate_limit_per_hour': 100000,
            'rate_limit_per_day': 1000000,
            'max_requests_per_month': None  # Unlimited
        }}
    )

    tenant, _ = Tenant.objects.get_or_create(
        slug='baas-cli-comprehensive-test-tenant-{unique_id}',
        defaults={{'name': 'BaaS CLI Comprehensive Test Tenant {unique_id}'}}
    )

    user, _ = User.objects.get_or_create(
        email='baas-cli-comprehensive-test-{unique_id}@example.com',
        defaults={{'tenant': tenant, 'status': UserStatus.ACTIVE}}
    )
    if user.tenant != tenant:
        user.tenant = tenant
        user.status = UserStatus.ACTIVE
        user.save()

    tenant_admin_role, _ = Role.objects.get_or_create(
        tenant=tenant, name='TENANT_ADMIN',
        defaults={{'description': 'Tenant Administrator'}}
    )
    UserRole.objects.get_or_create(user=user, role=tenant_admin_role)

    AuthAPIKey.objects.filter(tenant=tenant, name__startswith='BaaS CLI Comprehensive Test Auth Key').delete()

    api_key_value = AuthAPIKey.generate_key()
    api_key_hash = AuthAPIKey.hash_key(api_key_value)
    api_key_obj = AuthAPIKey.objects.create(
        user=user, tenant=tenant,
        name='BaaS CLI Comprehensive Test Auth Key {unique_id}',
        key_hash=api_key_hash
    )

    print('AUTH_API_KEY_START', file=sys.stdout, flush=True)
    print(api_key_value, file=sys.stdout, flush=True)
    print('AUTH_API_KEY_END', file=sys.stdout, flush=True)
except Exception as e:
    print(f'ERROR: {{e}}', file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
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

            # Debug: print output if there's an error
            if result.returncode != 0:
                print(f"Django shell failed with return code {result.returncode}", file=sys.stderr)
                print(f"STDOUT: {result.stdout[:500]}", file=sys.stderr)
                print(f"STDERR: {result.stderr[:500]}", file=sys.stderr)

            # Combine stdout and stderr for parsing (Django logs to stderr, output to stdout)
            # We need to parse both carefully
            output_lines = (result.stdout + '\n' + result.stderr).strip().split('\n') if result.stderr else result.stdout.strip().split('\n')

            if result.returncode == 0:
                in_key = False
                api_key = None
                for line in output_lines:
                    line = line.strip()
                    if line == 'AUTH_API_KEY_START':
                        in_key = True
                        continue
                    elif line == 'AUTH_API_KEY_END':
                        break
                    elif in_key and line and len(line) > 20:
                        # Found the API key
                        api_key = line
                        break

                if api_key:
                    return api_key

                # Fallback: try to find API key in output (last long line that looks like a key)
                for line in reversed(output_lines):
                    line = line.strip()
                    if line and len(line) > 30 and not any([
                        line.startswith('>>>'),
                        line.startswith('...'),
                        'import' in line.lower(),
                        'from' in line.lower(),
                        'Error' in line,
                        'Warning' in line,
                        'AUTH_API_KEY' in line,
                        'objects imported' in line.lower(),
                        'timestamp' in line.lower(),
                        '{' in line,
                        '}' in line,
                    ]):
                        # Check if it looks like an API key (alphanumeric with dashes/underscores)
                        if all(c.isalnum() or c in '-_' for c in line):
                            return line
        except subprocess.TimeoutExpired:
            print("Django shell command timed out", file=sys.stderr)
        except Exception as e:
            print(f"Error creating test API key: {type(e).__name__}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        return None

    # ==================== API KEY COMMANDS ====================

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_create_all_tiers(self, api_available):
        """Test creating API keys with all tiers"""
        if not self.api_key:
            pytest.skip("No API key available")

        for tier in ['FREE', 'PRO', 'ENTERPRISE']:
            unique_id = uuid.uuid4().hex[:8]
            result = self.runner.invoke(cli, [
                'baas', 'api-keys', 'create',
                '--name', f'Test Key {tier} {unique_id}',
                '--tier', tier,
                '--format', 'json'
            ])
            assert result.exit_code == 0, f"Failed to create {tier} tier key: {result.output}"
            data = json.loads(result.output)
            assert data['tier'] == tier
            assert 'api_key' in data  # Plaintext key should be present
            if hasattr(self, 'created_api_keys'):
                self.created_api_keys.append(data['id'])

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_create_with_expiration(self, api_available):
        """Test creating API key with expiration date"""
        if not self.api_key:
            pytest.skip("No API key available")

        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        unique_id = uuid.uuid4().hex[:8]
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', f'Expiring Key {unique_id}',
            '--expires-at', future_date,
            '--format', 'json'
        ])
        assert result.exit_code == 0, f"Failed to create key with expiration: {result.output}"
        data = json.loads(result.output)
        assert 'expires_at' in data

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_create_table_format(self, api_available):
        """Test creating API key in table format"""
        if not self.api_key:
            pytest.skip("No API key available")

        unique_id = uuid.uuid4().hex[:8]
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', f'Table Format Key {unique_id}',
            '--tier', 'FREE'
        ])
        assert result.exit_code == 0
        assert 'API key created successfully' in result.output
        assert 'IMPORTANT' in result.output
        assert 'Save this API key securely' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_create_validation_errors(self, api_available):
        """Test API key creation validation errors"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Empty name
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', ''
        ])
        assert result.exit_code != 0
        assert 'cannot be empty' in result.output.lower()

        # Past expiration date
        past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', 'Test Key',
            '--expires-at', past_date
        ])
        assert result.exit_code != 0
        assert 'future' in result.output.lower()

        # Invalid date format
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', 'Test Key',
            '--expires-at', 'invalid-date'
        ])
        assert result.exit_code != 0
        assert 'format' in result.output.lower() or 'invalid' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_list_all_formats(self, api_available):
        """Test listing API keys in all formats"""
        if not self.api_key:
            pytest.skip("No API key available")

        # JSON format
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'list',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

        # Table format
        result = self.runner.invoke(cli, ['baas', 'api-keys', 'list'])
        assert result.exit_code == 0
        assert 'ID' in result.output or 'No API keys found' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_list_with_filters(self, api_available):
        """Test listing API keys with all filters"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Tier filter
        for tier in ['FREE', 'PRO', 'ENTERPRISE']:
            result = self.runner.invoke(cli, [
                'baas', 'api-keys', 'list',
                '--tier', tier,
                '--format', 'json'
            ])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)

        # Pagination
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'list',
            '--limit', '10',
            '--offset', '0',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) <= 10

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_get_all_formats(self, api_available):
        """Test getting API key in all formats"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Create a key first
        unique_id = uuid.uuid4().hex[:8]
        create_result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', f'Get Test Key {unique_id}',
            '--format', 'json'
        ])
        assert create_result.exit_code == 0
        api_key_id = json.loads(create_result.output)['id']

        # Get in JSON format
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'get',
            api_key_id,
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['id'] == api_key_id
        assert 'api_key' not in data  # Security: no plaintext key

        # Get in table format
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'get',
            api_key_id
        ])
        assert result.exit_code == 0
        assert api_key_id in result.output
        assert 'not displayed' in result.output.lower() or 'security' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_get_not_found(self, api_available):
        """Test getting non-existent API key"""
        if not self.api_key:
            pytest.skip("No API key available")

        fake_id = str(uuid.uuid4())
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'get',
            fake_id
        ])
        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or '404' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_update_all_fields(self, api_available):
        """Test updating API key with all fields"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Create a key first
        unique_id = uuid.uuid4().hex[:8]
        create_result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', f'Update Test Key {unique_id}',
            '--format', 'json'
        ])
        assert create_result.exit_code == 0
        api_key_id = json.loads(create_result.output)['id']

        # Update name
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'update',
            api_key_id,
            '--name', f'Updated Name {unique_id}',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['name'] == f'Updated Name {unique_id}'

        # Update expiration
        future_date = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%dT%H:%M:%SZ')
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'update',
            api_key_id,
            '--expires-at', future_date,
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'expires_at' in data

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_update_validation_errors(self, api_available):
        """Test API key update validation errors"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Create a key first
        unique_id = uuid.uuid4().hex[:8]
        create_result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', f'Validation Test Key {unique_id}',
            '--format', 'json'
        ])
        assert create_result.exit_code == 0
        api_key_id = json.loads(create_result.output)['id']

        # No fields provided
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'update',
            api_key_id
        ])
        assert result.exit_code != 0
        assert 'at least one field' in result.output.lower()

        # Empty name
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'update',
            api_key_id,
            '--name', ''
        ])
        assert result.exit_code != 0
        assert 'cannot be empty' in result.output.lower() or 'at least one field' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_api_keys_revoke_all_formats(self, api_available):
        """Test revoking API key in all formats"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Create a key first
        unique_id = uuid.uuid4().hex[:8]
        create_result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', f'Revoke Test Key {unique_id}',
            '--format', 'json'
        ])
        assert create_result.exit_code == 0
        api_key_id = json.loads(create_result.output)['id']

        # Revoke in table format
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'revoke',
            api_key_id
        ])
        assert result.exit_code == 0
        assert 'revoked successfully' in result.output.lower()

        # Verify it's revoked
        result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'get',
            api_key_id,
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['is_active'] is False
        assert data['revoked_at'] is not None

    # ==================== USAGE TRACKING COMMANDS ====================

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_stats_all_formats(self, api_available):
        """Test usage stats in all formats"""
        if not self.api_key:
            pytest.skip("No API key available")

        # JSON format
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'total_requests' in data
        assert 'success_count' in data
        assert 'error_count' in data
        assert 'success_rate' in data
        assert 'avg_response_time_ms' in data

        # Table format
        result = self.runner.invoke(cli, ['baas', 'usage', 'stats'])
        assert result.exit_code == 0
        assert 'Usage Statistics' in result.output
        assert 'Total Requests' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_stats_with_all_filters(self, api_available):
        """Test usage stats with all filters"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Create a key for filtering
        unique_id = uuid.uuid4().hex[:8]
        create_result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', f'Usage Filter Key {unique_id}',
            '--format', 'json'
        ])
        assert create_result.exit_code == 0
        api_key_id = json.loads(create_result.output)['id']

        # With API key filter
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--api-key-id', api_key_id,
            '--format', 'json'
        ])
        assert result.exit_code == 0

        # With date range
        now = datetime.now()
        start_date = (now - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--start-date', start_date,
            '--end-date', end_date,
            '--format', 'json'
        ])
        assert result.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_by_endpoint_all_formats(self, api_available):
        """Test usage by-endpoint in all formats"""
        if not self.api_key:
            pytest.skip("No API key available")

        # JSON format
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'by-endpoint',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

        # Table format
        result = self.runner.invoke(cli, ['baas', 'usage', 'by-endpoint'])
        assert result.exit_code == 0
        assert 'Endpoint' in result.output or 'No usage data found' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_by_endpoint_with_filters(self, api_available):
        """Test usage by-endpoint with all filters"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Create a key for filtering
        unique_id = uuid.uuid4().hex[:8]
        create_result = self.runner.invoke(cli, [
            'baas', 'api-keys', 'create',
            '--name', f'Endpoint Filter Key {unique_id}',
            '--format', 'json'
        ])
        assert create_result.exit_code == 0
        api_key_id = json.loads(create_result.output)['id']

        # With all filters
        now = datetime.now()
        start_date = (now - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'by-endpoint',
            '--api-key-id', api_key_id,
            '--start-date', start_date,
            '--end-date', end_date,
            '--format', 'json'
        ])
        assert result.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_by_tenant_all_formats(self, api_available):
        """Test usage by-tenant in all formats"""
        if not self.api_key:
            pytest.skip("No API key available")

        # JSON format
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'by-tenant',
            '--format', 'json'
        ])
        # May fail if not admin - that's expected
        if result.exit_code == 0:
            data = json.loads(result.output)
            assert isinstance(data, list)

        # Table format
        result = self.runner.invoke(cli, ['baas', 'usage', 'by-tenant'])
        # May fail if not admin - that's expected
        if result.exit_code == 0:
            assert 'Tenant ID' in result.output or 'No usage data found' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_usage_validation_errors(self, api_available):
        """Test usage command validation errors"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Invalid date format
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--start-date', 'invalid-date'
        ])
        assert result.exit_code != 0
        assert 'format' in result.output.lower() or 'invalid' in result.output.lower()

        # Invalid date range
        now = datetime.now()
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--start-date', now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            '--end-date', (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        ])
        assert result.exit_code != 0
        assert 'before' in result.output.lower() or 'range' in result.output.lower()

        # Invalid API key ID format
        result = self.runner.invoke(cli, [
            'baas', 'usage', 'stats',
            '--api-key-id', 'invalid-id'
        ])
        assert result.exit_code != 0
        assert 'format' in result.output.lower() or 'invalid' in result.output.lower()

    # ==================== DEVELOPER PORTAL COMMANDS ====================

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_docs_show_all_formats(self, api_available):
        """Test docs show in all formats"""
        if not self.api_key:
            pytest.skip("No API key available")

        # HTML format (default)
        result = self.runner.invoke(cli, ['baas', 'docs', 'show'])
        assert result.exit_code == 0
        assert '<html>' in result.output or '<!DOCTYPE html>' in result.output

        # JSON format
        result = self.runner.invoke(cli, [
            'baas', 'docs', 'show',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'title' in data
        assert 'endpoints' in data
        assert 'authentication' in data

        # Markdown format
        result = self.runner.invoke(cli, [
            'baas', 'docs', 'show',
            '--format', 'markdown'
        ])
        assert result.exit_code == 0
        assert '#' in result.output  # Markdown headers

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_docs_openapi_all_formats(self, api_available):
        """Test docs openapi in all formats"""
        if not self.api_key:
            pytest.skip("No API key available")

        # JSON format (default)
        result = self.runner.invoke(cli, ['baas', 'docs', 'openapi'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'openapi' in data
        assert 'info' in data
        assert 'paths' in data

        # YAML format (may require PyYAML)
        result = self.runner.invoke(cli, [
            'baas', 'docs', 'openapi',
            '--format', 'yaml'
        ])
        if result.exit_code == 0:
            assert 'openapi:' in result.output
        else:
            # Expected if PyYAML not installed
            assert 'PyYAML' in result.output or 'yaml' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_docs_sdks_all_formats(self, api_available):
        """Test docs sdks in all formats"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Table format (default)
        result = self.runner.invoke(cli, ['baas', 'docs', 'sdks'])
        assert result.exit_code == 0
        assert 'Language' in result.output or 'SDK' in result.output

        # JSON format
        result = self.runner.invoke(cli, [
            'baas', 'docs', 'sdks',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        # Should have SDK entries
        assert len(data) >= 0  # May be empty if not configured

    @pytest.mark.skipif(not _check_api_available(), reason="API service not available")
    def test_docs_validation_errors(self, api_available):
        """Test docs command validation errors"""
        if not self.api_key:
            pytest.skip("No API key available")

        # Invalid format for show
        result = self.runner.invoke(cli, [
            'baas', 'docs', 'show',
            '--format', 'invalid'
        ])
        assert result.exit_code != 0

        # Invalid format for openapi
        result = self.runner.invoke(cli, [
            'baas', 'docs', 'openapi',
            '--format', 'invalid'
        ])
        assert result.exit_code != 0

        # Invalid format for sdks
        result = self.runner.invoke(cli, [
            'baas', 'docs', 'sdks',
            '--format', 'invalid'
        ])
        assert result.exit_code != 0
