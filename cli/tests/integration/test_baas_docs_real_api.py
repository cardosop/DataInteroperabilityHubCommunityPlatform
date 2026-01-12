"""
Integration tests for BaaS documentation commands against real API service.

These tests test BaaS documentation CLI commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest tests/integration/test_baas_docs_real_api.py -v
"""
import pytest
import json
import os
import subprocess
import requests
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


class TestBaaSDocsIntegration:
    """
    Integration tests for BaaS documentation commands using real API service.

    All tests use real API endpoints - no mocks or stubs.
    """

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
    slug='baas-docs-cli-test-tenant',
    defaults={'name': 'BaaS Docs CLI Test Tenant'}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='baas-docs-cli-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Create and assign TENANT_ADMIN role (required for API access)
tenant_admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name="TENANT_ADMIN",
    defaults={"description": "Tenant Administrator"}
)
UserRole.objects.get_or_create(user=user, role=tenant_admin_role)

# Delete existing API key if it exists
APIKey.objects.filter(user=user, name='BaaS Docs CLI Test Key').delete()

# Create new API key
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='BaaS Docs CLI Test Key',
    key_hash=api_key_hash
)

# Print the plaintext key (it's only available at creation time)
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
                # Extract API key from output (should be the last line)
                output_lines = result.stdout.strip().split('\n')
                for line in reversed(output_lines):
                    line = line.strip()
                    if line and len(line) > 20:  # API keys are typically long
                        return line
        except Exception as e:
            print(f"Warning: Could not create API key via Django shell: {e}")

        return None

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_command_group_exists(self):
        """Test that docs command group is registered"""
        runner = CliRunner()
        result = runner.invoke(cli, ['baas', 'docs', '--help'])

        assert result.exit_code == 0
        assert 'Developer portal documentation commands' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_show_default_format(self):
        """Test showing API documentation in default (HTML) format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, ['baas', 'docs', 'show'])

        assert result.exit_code == 0
        assert 'API Documentation' in result.output or 'Data Interoperability Hub' in result.output
        assert '<html>' in result.output or '<!DOCTYPE html>' in result.output
        assert 'OpenAPI' in result.output or 'openapi' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_show_json_format(self):
        """Test showing API documentation in JSON format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'show',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        # Parse JSON output
        output_data = json.loads(result.output)
        assert 'title' in output_data
        assert 'version' in output_data
        assert 'endpoints' in output_data
        assert 'authentication' in output_data
        assert 'rate_limiting' in output_data
        assert 'resources' in output_data
        # Verify endpoint structure
        assert 'openapi_schema' in output_data['endpoints']
        assert 'sdks' in output_data['endpoints']

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_show_html_format(self):
        """Test showing API documentation in HTML format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'show',
            '--format', 'html'
        ])

        assert result.exit_code == 0
        assert '<html>' in result.output or '<!DOCTYPE html>' in result.output
        assert 'API Documentation' in result.output or 'Data Interoperability Hub' in result.output
        assert 'OpenAPI' in result.output or 'openapi' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_show_markdown_format(self):
        """Test showing API documentation in Markdown format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'show',
            '--format', 'markdown'
        ])

        assert result.exit_code == 0
        assert '#' in result.output  # Markdown headers
        assert 'API Documentation' in result.output or 'Data Interoperability Hub' in result.output
        assert 'OpenAPI' in result.output or 'openapi' in result.output.lower()
        assert '##' in result.output  # Sub-headers

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_openapi_json_format(self):
        """Test showing OpenAPI schema in JSON format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'openapi',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        # Parse JSON output
        output_data = json.loads(result.output)
        assert 'openapi' in output_data
        assert 'info' in output_data
        assert 'paths' in output_data
        # Verify it's a valid OpenAPI schema
        assert output_data['openapi'].startswith('3.')

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_openapi_default_format(self):
        """Test showing OpenAPI schema in default (JSON) format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, ['baas', 'docs', 'openapi'])

        assert result.exit_code == 0
        # Parse JSON output
        output_data = json.loads(result.output)
        assert 'openapi' in output_data
        assert 'info' in output_data
        assert 'paths' in output_data

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_openapi_yaml_format(self):
        """Test showing OpenAPI schema in YAML format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'openapi',
            '--format', 'yaml'
        ])

        # YAML format may require PyYAML, so we check for either success or appropriate error
        if result.exit_code == 0:
            # If successful, verify it's YAML format
            assert 'openapi:' in result.output or 'openapi: ' in result.output
            assert 'info:' in result.output
            assert 'paths:' in result.output
        else:
            # If it fails, it should be because PyYAML is not available
            assert 'PyYAML' in result.output or 'yaml' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_sdks_default_format(self):
        """Test showing SDK links in default (table) format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, ['baas', 'docs', 'sdks'])

        assert result.exit_code == 0
        assert 'Language' in result.output or 'SDK' in result.output
        assert 'Python' in result.output or 'python' in result.output.lower()
        assert 'JavaScript' in result.output or 'javascript' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_sdks_table_format(self):
        """Test showing SDK links in table format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'sdks',
            '--format', 'table'
        ])

        assert result.exit_code == 0
        assert 'Language' in result.output or 'SDK' in result.output
        assert 'Python' in result.output or 'python' in result.output.lower()
        assert 'JavaScript' in result.output or 'javascript' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_sdks_json_format(self):
        """Test showing SDK links in JSON format"""
        if not hasattr(self, 'api_key') or not self.api_key:
            pytest.skip("API key not available. Set DATAHUB_API_KEY environment variable or ensure test user exists.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'sdks',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        # Parse JSON output
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)
        # Verify SDK structure
        assert 'python' in output_data or 'javascript' in output_data
        # Check SDK fields
        sdk_key = 'python' if 'python' in output_data else 'javascript'
        sdk_info = output_data[sdk_key]
        assert 'name' in sdk_info
        assert 'language' in sdk_info
        assert 'download_url' in sdk_info
        assert 'install_command' in sdk_info

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_show_invalid_format(self):
        """Test that invalid format option is rejected"""
        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'show',
            '--format', 'invalid'
        ])

        assert result.exit_code != 0
        assert 'Invalid value' in result.output or 'invalid choice' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_openapi_invalid_format(self):
        """Test that invalid format option is rejected"""
        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'openapi',
            '--format', 'invalid'
        ])

        assert result.exit_code != 0
        assert 'Invalid value' in result.output or 'invalid choice' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_docs_sdks_invalid_format(self):
        """Test that invalid format option is rejected"""
        runner = CliRunner()
        result = runner.invoke(cli, [
            'baas', 'docs', 'sdks',
            '--format', 'invalid'
        ])

        assert result.exit_code != 0
        assert 'Invalid value' in result.output or 'invalid choice' in result.output.lower()
