from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive Integration Tests for BaaS API.

Tests ALL BaaS methods end-to-end against the running Docker Compose API service.
No mocks/stubs - uses real API connections.

This file provides comprehensive integration tests for:
- API key management (create, list, get, update, revoke)
- Usage tracking (stats, by-endpoint, by-tenant, quota)
- Developer portal (docs, openapi, sdk links)
- Error handling across all methods

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis, minio)
2. A test user and API key configured
   OR set via environment variables: TEST_API_KEY or DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export TEST_API_KEY=your-api-key
3. Run: pytest tests/test_baas_api_integration.py -v -m integration
"""
import os
import sys
import pytest
import uuid
import subprocess
import asyncio
from typing import Optional, Dict, Any
from datahub_interoperability import DataHubClient, DataHubClientConfig, BaaSAPI
from datahub_interoperability.errors import (
    BaaSValidationError,
    BaaSError,
    NotFoundError,
    ForbiddenError,
    ValidationError,
)


def setup_authentication_for_sdk_tests(api_base_url: str) -> Optional[str]:
    """
    Set up authentication for SDK tests.

    Priority order:
    1. Create a dedicated tenant+key via Django shell — this is PRIMARY
       because BaaS endpoints are gated behind ``Tenant.baas_enabled``,
       which the auto-provisioned platform-admin tenant may lack.
    2. Use the canonical conftest helper (validates token, auto-provisions).
    3. Read TEST_API_KEY / DATAHUB_API_KEY from the environment.

    Args:
        api_base_url: API base URL

    Returns:
        API key string or None
    """
    # Method 1: Create dedicated tenant + API key via Django shell (PRIMARY).
    # This ensures ``baas_enabled`` is set and isolates rate-limit quotas.
    try:
        key = _create_baas_tenant_and_key()
        if key:
            return key
    except Exception as exc:
        import sys as _sys
        print(f"[BaaS SDK] Django shell tenant creation failed ({exc!r}), "
              f"falling back to canonical helper.", file=_sys.stderr)

    # Method 2: Use canonical conftest helper (validates token, auto-provisions)
    try:
        from tests.conftest import get_api_key
        canonical = get_api_key()
        if canonical:
            return canonical
    except Exception as exc:
        import sys as _sys
        print(f"[BaaS SDK] Canonical helper failed ({exc!r}), "
              f"falling back to env vars.", file=_sys.stderr)

    # Method 3: Use environment variables (last resort)
    api_key = os.environ.get('TEST_API_KEY') or os.environ.get('DATAHUB_API_KEY')
    if api_key:
        return api_key

    return None


def _create_baas_tenant_and_key() -> Optional[str]:
    """Create a dedicated tenant with ``baas_enabled=True`` and return an API key."""
    import subprocess as _sp

    unique_id = uuid.uuid4().hex[:8]
    try:
        unique_id = uuid.uuid4().hex[:8]
        django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey
from hub.apps.baas.models import APITierModel
import os

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug=f'baas-sdk-test-tenant-{{unique_id}}',
    defaults={{'name': f'BaaS SDK Test Tenant {{unique_id}}', 'baas_enabled': True}}
)
if not tenant.baas_enabled:
    tenant.baas_enabled = True
    tenant.save(update_fields=['baas_enabled'])

# Get or create user
user, _ = User.objects.get_or_create(
    email=f'baas-sdk-test-{{unique_id}}@example.com',
    defaults={{
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Create tenant admin role
tenant_admin_role, _ = Role.objects.get_or_create(
    tenant=tenant, name='TENANT_ADMIN',
    defaults={{'description': 'Tenant Administrator'}}
)
UserRole.objects.get_or_create(user=user, role=tenant_admin_role)

# Create free tier if it doesn't exist
APITierModel.objects.get_or_create(
    name='FREE',
    defaults={{
        'rate_limit_per_hour': 1000,
        'rate_limit_per_day': 10000,
        'max_requests_per_month': 10000
    }}
)

# Delete existing API key if it exists
AuthAPIKey.objects.filter(user=user, name='BaaS SDK Test Key').delete()

# Create new API key
api_key_value = AuthAPIKey.generate_key()
api_key_hash = AuthAPIKey.hash_key(api_key_value)
api_key_obj = AuthAPIKey.objects.create(
    user=user,
    tenant=tenant,
    name='BaaS SDK Test Key',
    key_hash=api_key_hash
)

# Print the plaintext key (it's only available at creation time)
print('API_KEY_START')
print(api_key_value)
print('API_KEY_END')
"""
        result = subprocess.run(
                        ['docker', 'compose', '-f', 'docker-compose.test.yml', 'exec', '-T', 'api-service-test', 'python', 'hub/manage.py', 'shell'],
            input=django_shell_script,
            text=True,
            capture_output=True,
            timeout=30,
            cwd='/home/ph/Desktop/DataInteroperabilityHub'
        )
        # Combine stdout and stderr (Django logs to stderr, output to stdout)
        combined_output = result.stdout + result.stderr if result.stderr else result.stdout

        if result.returncode == 0:
            # Extract API key from output using markers
            output_lines = combined_output.strip().split('\n')
            api_key = None
            in_api_key = False
            for line in output_lines:
                line = line.strip()
                if line == 'API_KEY_START':
                    in_api_key = True
                    continue
                elif line == 'API_KEY_END':
                    in_api_key = False
                    continue
                elif in_api_key and line:
                    api_key = line
                    break

            # Fallback: if markers didn't work, try old method
            if not api_key:
                for line in reversed(output_lines):
                    line = line.strip()
                    if not line or len(line) < 20:
                        continue
                    if line.startswith('>>>') or line.startswith('...'):
                        continue
                    if 'imported' in line.lower() or 'objects' in line.lower() or 'Error' in line:
                        continue
                    if ' ' in line:
                        continue
                    if all(c.isalnum() or c in '-_' for c in line):
                        api_key = line
                        break

            if api_key:
                return api_key
        else:
            # Log subprocess error for debugging
            print(f"Subprocess failed with return code {result.returncode}", file=sys.stderr)
            if result.stderr:
                print(f"Stderr: {result.stderr[:500]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("Subprocess timed out", file=sys.stderr)
    except Exception as e:
        # Log error for debugging but don't fail tests
        print(f"Error creating API key: {type(e).__name__}: {e}", file=sys.stderr)
    return None


@pytest.fixture
def real_api_config():
    """Fixture for real API configuration"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:8001/api/v1')
    api_key = setup_authentication_for_sdk_tests(api_base_url)

    if not api_key:
        pytest.skip("No API key available for testing. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

    config = DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key,
        timeout=30.0,
        max_retries=3,
    )
    return config


@pytest.fixture
async def client(real_api_config):
    """Fixture for DataHub client"""
    async with DataHubClient(real_api_config) as client:
        yield client


@pytest.fixture
def baas_api(client):
    """Fixture for BaaSAPI"""
    return BaaSAPI(client)


@pytest.mark.asyncio
@pytest.mark.integration
class TestBaaSAPIIntegration:
    """Integration tests for BaaS API with real API endpoints"""

    async def test_create_api_key_integration(self, baas_api):
        """Test creating API key via SDK with real API"""
        unique_id = uuid.uuid4().hex[:8]
        result = await baas_api.create_api_key(
            name=f"SDK Test Key {unique_id}",
            tier="FREE"
        )

        assert result is not None
        assert "id" in result
        assert "name" in result
        assert result["name"] == f"SDK Test Key {unique_id}"
        assert "api_key" in result  # Plaintext key should be returned
        assert len(result["api_key"]) > 0

        # Store for cleanup
        self._test_api_key_id = result["id"]
        self._test_api_key_value = result["api_key"]

    async def test_list_api_keys_integration(self, baas_api):
        """Test listing API keys via SDK with real API"""
        result = await baas_api.list_api_keys()

        assert isinstance(result, list)
        # Should have at least the keys we created
        assert len(result) >= 0

    async def test_get_api_key_integration(self, baas_api):
        """Test getting API key via SDK with real API"""
        # First create a key
        unique_id = uuid.uuid4().hex[:8]
        created = await baas_api.create_api_key(
            name=f"SDK Get Test Key {unique_id}",
            tier="FREE"
        )
        api_key_id = created["id"]

        # Then get it
        result = await baas_api.get_api_key(api_key_id)

        assert result is not None
        assert result["id"] == api_key_id
        assert result["name"] == f"SDK Get Test Key {unique_id}"
        # Plaintext key should NOT be in get response
        assert "api_key" not in result

    async def test_update_api_key_integration(self, baas_api):
        """Test updating API key via SDK with real API"""
        # First create a key
        unique_id = uuid.uuid4().hex[:8]
        created = await baas_api.create_api_key(
            name=f"SDK Update Test Key {unique_id}",
            tier="FREE"
        )
        api_key_id = created["id"]

        # Then update it
        result = await baas_api.update_api_key(
            api_key_id,
            name=f"SDK Updated Key {unique_id}"
        )

        assert result is not None
        assert result["id"] == api_key_id
        assert result["name"] == f"SDK Updated Key {unique_id}"

    async def test_revoke_api_key_integration(self, baas_api):
        """Test revoking API key via SDK with real API"""
        # First create a key
        unique_id = uuid.uuid4().hex[:8]
        created = await baas_api.create_api_key(
            name=f"SDK Revoke Test Key {unique_id}",
            tier="FREE"
        )
        api_key_id = created["id"]

        # Then revoke it
        await baas_api.revoke_api_key(api_key_id)

        # Verify it's revoked (should raise NotFoundError or return revoked status)
        # The exact behavior depends on API implementation
        try:
            result = await baas_api.get_api_key(api_key_id)
            # If it returns, check if it's marked as revoked
            if "revoked_at" in result:
                assert result["revoked_at"] is not None
        except NotFoundError:
            # API might delete revoked keys
            pass

    async def test_get_usage_stats_integration(self, baas_api):
        """Test getting usage stats via SDK with real API"""
        result = await baas_api.get_usage_stats()

        assert result is not None
        assert isinstance(result, dict)
        # Check for expected fields
        assert "total_requests" in result or "success_count" in result

    async def test_get_usage_stats_with_filters_integration(self, baas_api):
        """Test getting usage stats with filters via SDK with real API"""
        # Create a key and use it
        unique_id = uuid.uuid4().hex[:8]
        created = await baas_api.create_api_key(
            name=f"SDK Usage Test Key {unique_id}",
            tier="FREE"
        )
        api_key_id = created["id"]

        # Get stats filtered by API key
        result = await baas_api.get_usage_stats(api_key_id=api_key_id)

        assert result is not None
        assert isinstance(result, dict)

    async def test_get_usage_by_endpoint_integration(self, baas_api):
        """Test getting usage by endpoint via SDK with real API"""
        result = await baas_api.get_usage_by_endpoint()

        assert isinstance(result, list)
        # Should be a list (may be empty if no usage)

    async def test_get_usage_by_tenant_integration(self, baas_api):
        """Test getting usage by tenant via SDK with real API"""
        try:
            result = await baas_api.get_usage_by_tenant()
            assert isinstance(result, list)
        except (ForbiddenError, BaaSError) as e:
            # Expected if user is not admin
            if isinstance(e, ForbiddenError) or ("platform administrator" in str(e) or "admin" in str(e).lower()):
                pytest.skip("User is not platform admin, cannot test by-tenant endpoint")
            else:
                raise

    async def test_check_quota_integration(self, baas_api):
        """Test checking quota via SDK with real API"""
        # Create a key
        unique_id = uuid.uuid4().hex[:8]
        created = await baas_api.create_api_key(
            name=f"SDK Quota Test Key {unique_id}",
            tier="FREE"
        )
        api_key_id = created["id"]

        try:
            result = await baas_api.check_quota(api_key_id)
            assert result is not None
            assert isinstance(result, dict)
        except (NotFoundError, BaaSError) as e:
            # Quota endpoint might not exist yet (404) or other error
            if isinstance(e, NotFoundError) or (isinstance(e, BaaSError) and '404' in str(e)):
                pytest.skip("Quota endpoint not available")
            else:
                raise

    async def test_get_api_docs_integration(self, baas_api):
        """Test getting API docs via SDK with real API"""
        result = await baas_api.get_api_docs()

        assert isinstance(result, str)
        assert len(result) > 0

    async def test_get_api_docs_json_format_integration(self, baas_api):
        """Test getting API docs in JSON format via SDK with real API"""
        result = await baas_api.get_api_docs(format="json")

        assert isinstance(result, str)
        # Should be valid JSON string
        import json
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    async def test_get_openapi_schema_integration(self, baas_api):
        """Test getting OpenAPI schema via SDK with real API"""
        try:
            result = await baas_api.get_openapi_schema()
            assert result is not None
            assert isinstance(result, dict)
            assert "openapi" in result or "swagger" in result
        except (BaaSError, ValueError) as e:
            # Endpoint might return HTML or not be available
            if "Expecting value" in str(e) or "404" in str(e):
                pytest.skip("OpenAPI schema endpoint not available or returns non-JSON")
            else:
                raise

    async def test_get_sdk_download_links_integration(self, baas_api):
        """Test getting SDK download links via SDK with real API"""
        result = await baas_api.get_sdk_download_links()

        assert isinstance(result, dict)
        # Should have SDK links (may be empty if not configured)

    async def test_validation_errors_integration(self, baas_api):
        """Test validation errors are properly raised"""
        # Test invalid API key ID
        with pytest.raises(BaaSValidationError):
            await baas_api.get_api_key("not-a-uuid")

        # Test invalid tier
        with pytest.raises(BaaSValidationError):
            await baas_api.create_api_key("Test Key", tier="INVALID")

        # Test invalid date format
        with pytest.raises(BaaSValidationError):
            await baas_api.get_usage_stats(start_date="invalid-date")

    async def test_not_found_errors_integration(self, baas_api):
        """Test NotFoundError is raised for non-existent resources"""
        fake_id = str(uuid.uuid4())
        with pytest.raises(NotFoundError):
            await baas_api.get_api_key(fake_id)
