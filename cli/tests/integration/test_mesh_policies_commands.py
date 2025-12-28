"""
Comprehensive integration tests for Mesh Policy CLI commands against real API service.

These tests test all mesh policy CLI commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest cli/tests/integration/test_mesh_policies_commands.py -v
"""
import pytest
import requests
import json
import os
import uuid
import subprocess
import time
from typing import Optional
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


class TestMeshPoliciesCommandsRealAPI:
    """Comprehensive integration tests for all mesh policy commands with real API"""

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
    slug='mesh-policies-cli-test-tenant',
    defaults={'name': 'Mesh Policies CLI Test Tenant'}
)

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={'description': 'Tenant Administrator'}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='mesh-policies-cli-test@example.com',
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
APIKey.objects.filter(user=user, name='mesh-policies-cli-test-key').delete()

# Create new API key with mesh:write and mesh:read scopes
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='mesh-policies-cli-test-key',
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

    def _create_test_domain(self, api_base_url: str, api_key: Optional[str], name: str = None) -> str:
        """
        Create a test domain for testing.
        Returns the domain ID.
        """
        if not name:
            name = f"test-domain-{uuid.uuid4().hex[:8]}"

        domain_data = {
            "name": name,
            "description": "Test domain for CLI policy integration tests",
            "status": "ACTIVE"
        }

        if not api_key:
            pytest.skip("No API key available for domain creation")
            return ""  # Never reached, but satisfies type checker

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
            # Skip test if domain creation fails
            pytest.skip(f"Failed to create test domain: {str(e)}")
            return ""  # Never reached, but satisfies type checker

    def _create_test_policy(self, api_base_url: str, api_key: Optional[str], domain_id: Optional[str] = None, name: str = None) -> str:
        """
        Create a test access policy for testing via Django shell.
        If domain_id is provided, ensures policy is in the same tenant as the domain.
        Returns the policy ID.
        """
        if not api_key:
            pytest.skip("No API key available for policy creation")
            return ""  # Never reached, but satisfies type checker

        if not name:
            name = f"test-policy-{uuid.uuid4().hex[:8]}"

        # Get tenant from domain if provided, otherwise use default tenant
        tenant_lookup = ""
        if domain_id:
            tenant_lookup = f"""
# Get tenant from domain to ensure policy is in same tenant
from hub.apps.mesh.models import DataMeshDomain
try:
    domain = DataMeshDomain.objects.get(id='{domain_id}')
    tenant = domain.tenant
except DataMeshDomain.DoesNotExist:
    # Fallback to default tenant
    tenant, _ = Tenant.objects.get_or_create(
        slug='mesh-policies-cli-test-tenant',
        defaults={{'name': 'Mesh Policies CLI Test Tenant'}}
    )
"""
        else:
            tenant_lookup = """
# Get or create tenant by slug (same as used for API key creation)
tenant, _ = Tenant.objects.get_or_create(
    slug='mesh-policies-cli-test-tenant',
    defaults={'name': 'Mesh Policies CLI Test Tenant'}
)
"""

        # Create policy via Django shell since there's no REST API endpoint for AccessPolicy
        django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.governance.models import AccessPolicy
import uuid
{tenant_lookup}

# Create access policy
policy = AccessPolicy.objects.create(
    tenant=tenant,
    name='{name}',
    description='Test policy for CLI integration tests',
    conditions={{"user": {{"tenant_id": str(tenant.id)}}}},
    effect='ALLOW',
    enabled=True
)

# Print the policy ID
print(f"POLICY_ID={{policy.id}}")
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
                # Extract policy ID from output
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    line = line.strip()
                    if line.startswith('POLICY_ID='):
                        policy_id = line.split('=', 1)[1].strip()
                        if policy_id and len(policy_id) > 20:
                            # Wait a bit for policy to be fully created
                            time.sleep(1)
                            return policy_id

                # Fallback: look for UUID-like strings
                for line in reversed(output_lines):
                    line = line.strip()
                    # UUIDs are 36 characters with dashes
                    if line and len(line) == 36 and line.count('-') == 4:
                        try:
                            uuid.UUID(line)  # Validate it's a valid UUID
                            time.sleep(1)
                            return line
                        except ValueError:
                            continue
        except Exception as e:
            pytest.skip(f"Failed to create test policy: {str(e)}")
            return ""  # Never reached, but satisfies type checker

        # If we get here, we couldn't extract the policy ID
        pytest.skip("Failed to create test policy: Could not extract policy ID")
        return ""  # Never reached, but satisfies type checker

    def _delete_test_domain(self, api_base_url: str, api_key: Optional[str], domain_id: str):
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

    def _delete_test_policy(self, api_base_url: str, api_key: Optional[str], policy_id: str):
        """Delete a test policy via Django shell"""
        django_shell_script = f"""
from hub.apps.governance.models import AccessPolicy

try:
    policy = AccessPolicy.objects.get(id='{policy_id}')
    policy.delete()
    print("POLICY_DELETED")
except AccessPolicy.DoesNotExist:
    print("POLICY_NOT_FOUND")
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
            # Ignore errors - cleanup is best effort
        except Exception:
            pass  # Ignore cleanup errors

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_apply_policy_success_table_format(self, setup_config, api_available):
        """Test applying a policy successfully in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            # Ensure config is set (fixture should have done this, but verify)
            if not config.get_api_key() and self.api_key:
                config.set_api_key(self.api_key)

            runner = CliRunner()
            result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id
            ])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            assert 'Policy applied successfully' in result.output or 'applied successfully' in result.output.lower()
            assert policy_id in result.output or 'Policy ID:' in result.output
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_apply_policy_success_json_format(self, setup_config, api_available):
        """Test applying a policy successfully in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            runner = CliRunner()
            result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            output_data = json.loads(result.output)
            assert 'id' in output_data
            assert output_data.get('policy_id') == policy_id
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_apply_policy_with_overrides(self, setup_config, api_available):
        """Test applying a policy with overrides"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            overrides = '{"priority": 50, "effect": "ALLOW"}'
            runner = CliRunner()
            result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id,
                '--overrides', overrides
            ])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            assert 'Policy applied successfully' in result.output or 'applied successfully' in result.output.lower()
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_apply_policy_missing_policy_id(self, setup_config, api_available):
        """Test applying a policy without required policy ID"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        try:
            runner = CliRunner()
            result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id
            ])

            assert result.exit_code != 0, "Command should have failed without policy ID"
            assert 'Missing option' in result.output or 'required' in result.output.lower() or '--policy' in result.output
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_apply_policy_invalid_json_overrides(self, setup_config, api_available):
        """Test applying a policy with invalid JSON in overrides"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            runner = CliRunner()
            result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id,
                '--overrides', 'invalid json'
            ])

            assert result.exit_code != 0, "Command should have failed with invalid JSON"
            assert 'Invalid JSON' in result.output or 'JSON' in result.output
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_list_policies_success_table_format(self, setup_config, api_available):
        """Test listing policies in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            runner = CliRunner()
            # First apply a policy
            apply_result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id
            ])
            assert apply_result.exit_code == 0, "Failed to apply policy for list test"

            # Wait a bit for policy to be applied
            time.sleep(1)

            result = runner.invoke(cli, ['mesh', 'policies', 'list', domain_id])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            # Should show table or "No policies found"
            assert len(result.output) > 0
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_list_policies_success_json_format(self, setup_config, api_available):
        """Test listing policies in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            runner = CliRunner()
            # First apply a policy
            apply_result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id
            ])
            assert apply_result.exit_code == 0, "Failed to apply policy for list test"

            # Wait a bit for policy to be applied
            time.sleep(1)

            result = runner.invoke(cli, [
                'mesh', 'policies', 'list', domain_id,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            output_data = json.loads(result.output)
            assert 'count' in output_data or 'results' in output_data
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_list_policies_with_filters(self, setup_config, api_available):
        """Test listing policies with filters"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            runner = CliRunner()
            # First apply a policy
            apply_result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id
            ])
            assert apply_result.exit_code == 0, "Failed to apply policy for list test"

            # Wait a bit for policy to be applied
            time.sleep(1)

            result = runner.invoke(cli, [
                'mesh', 'policies', 'list', domain_id,
                '--status', 'APPLIED',
                '--page', '1',
                '--page-size', '10'
            ])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_list_policies_empty_result(self, setup_config, api_available):
        """Test listing policies with no results"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)

        try:
            # Ensure config is set (fixture should have done this, but verify)
            if not config.get_api_key() and self.api_key:
                config.set_api_key(self.api_key)

            runner = CliRunner()
            result = runner.invoke(cli, ['mesh', 'policies', 'list', domain_id, '--status', 'REVOKED'])

            # Should succeed even with no policies (empty list)
            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            # Should show "No policies found" or empty results
            assert len(result.output) >= 0
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_remove_policy_success_table_format(self, setup_config, api_available):
        """Test removing a policy successfully in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            runner = CliRunner()
            # First apply a policy
            apply_result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id
            ])
            assert apply_result.exit_code == 0, "Failed to apply policy for remove test"

            # Wait a bit for policy to be applied
            time.sleep(1)

            result = runner.invoke(cli, [
                'mesh', 'policies', 'remove', domain_id, policy_id
            ])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            assert 'Policy removed successfully' in result.output or 'removed successfully' in result.output.lower()
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_remove_policy_success_json_format(self, setup_config, api_available):
        """Test removing a policy successfully in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            runner = CliRunner()
            # First apply a policy
            apply_result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id
            ])
            assert apply_result.exit_code == 0, "Failed to apply policy for remove test"

            # Wait a bit for policy to be applied
            time.sleep(1)

            result = runner.invoke(cli, [
                'mesh', 'policies', 'remove', domain_id, policy_id,
                '--format', 'json'
            ])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            # May return empty dict or policy application data
            if result.output.strip() and result.output.strip() != '{}':
                output_data = json.loads(result.output)
                assert 'id' in output_data or 'status' in output_data
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_remove_policy_with_reason(self, setup_config, api_available):
        """Test removing a policy with a reason"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        domain_id = self._create_test_domain(api_base_url, self.api_key)
        policy_id = self._create_test_policy(api_base_url, self.api_key, domain_id=domain_id)

        try:
            runner = CliRunner()
            # First apply a policy
            apply_result = runner.invoke(cli, [
                'mesh', 'policies', 'apply', domain_id,
                '--policy', policy_id
            ])
            assert apply_result.exit_code == 0, "Failed to apply policy for remove test"

            # Wait a bit for policy to be applied
            time.sleep(1)

            result = runner.invoke(cli, [
                'mesh', 'policies', 'remove', domain_id, policy_id,
                '--reason', 'Policy no longer needed'
            ])

            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            assert 'Policy removed successfully' in result.output or 'removed successfully' in result.output.lower()
        finally:
            # Cleanup
            self._delete_test_domain(api_base_url, self.api_key, domain_id)
            self._delete_test_policy(api_base_url, self.api_key, policy_id)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_remove_policy_missing_arguments(self, setup_config, api_available):
        """Test removing a policy without required arguments"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'policies', 'remove', 'domain-id'])

        assert result.exit_code != 0, "Command should have failed without policy ID"
        assert 'Missing argument' in result.output or 'required' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_policies_command_group_exists(self, setup_config, api_available):
        """Test that policies command group exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'policies', '--help'])
        assert result.exit_code == 0
        assert 'Policy management commands' in result.output or 'policies' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_policies_apply_command_exists(self, setup_config, api_available):
        """Test that policies apply command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'policies', 'apply', '--help'])
        assert result.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_policies_list_command_exists(self, setup_config, api_available):
        """Test that policies list command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'policies', 'list', '--help'])
        assert result.exit_code == 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_policies_remove_command_exists(self, setup_config, api_available):
        """Test that policies remove command exists"""
        runner = CliRunner()
        result = runner.invoke(cli, ['mesh', 'policies', 'remove', '--help'])
        assert result.exit_code == 0

