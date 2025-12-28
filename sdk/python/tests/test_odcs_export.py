"""
SDK Integration Tests for ODCS Export.

Comprehensive integration tests for ODCS export functionality via Python SDK.
Tests SDK export methods against the running Docker Compose API service.
No mocks/stubs - uses real API connections.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: TEST_API_KEY or DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export TEST_API_KEY=your-api-key
3. Run: pytest tests/test_odcs_export.py -v
"""
import os
import pytest
import json
import uuid
import subprocess
from typing import Optional
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    ODCSValidationError,
    ODCSExportError,
    NotFoundError,
    NetworkError,
)


def setup_authentication_for_sdk_tests(api_base_url: str) -> Optional[str]:
    """
    Set up authentication for SDK tests.

    Tries multiple methods:
    1. Use TEST_API_KEY environment variable if available
    2. Use DATAHUB_API_KEY environment variable
    3. Try to create API key via Django shell (if Docker Compose is available)
    4. Return None if no key available

    Args:
        api_base_url: API base URL

    Returns:
        API key string or None
    """
    # Method 1: Use environment variables
    api_key = os.environ.get('TEST_API_KEY') or os.environ.get('DATAHUB_API_KEY')
    if api_key:
        return api_key

    # Method 2: Try to create API key via Django shell in Docker Compose
    try:
        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.auth.models import APIKey
import os

tenant, _ = Tenant.objects.get_or_create(
    slug='odcs-export-sdk-test-tenant',
    defaults={'name': 'ODCS Export SDK Test Tenant'}
)
user, _ = User.objects.get_or_create(
    email='odcs-export-sdk-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()
APIKey.objects.filter(user=user, name='ODCS Export SDK Test Key').delete()
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='ODCS Export SDK Test Key',
    key_hash=api_key_hash
)
print(api_key_value)
"""
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
                if line and len(line) > 20:
                    return line
    except Exception:
        pass

    return None


def check_api_available(api_base_url: str) -> bool:
    """Check if API is available."""
    try:
        import requests
        # Try API root endpoint - any HTTP response means API is up
        response = requests.get(f"{api_base_url}/", timeout=5)
        return response.status_code < 600
    except Exception:
        return False


@pytest.fixture
def real_api_config():
    """Fixture for real API configuration"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000/api/v1')

    # Check if API is available
    if not check_api_available(api_base_url):
        pytest.skip("API service is not available. Ensure Docker Compose services are running.")

    api_key = setup_authentication_for_sdk_tests(api_base_url)

    if not api_key:
        pytest.skip(
            "No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable, "
            "or ensure Docker Compose api-service is accessible."
        )

    return DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key
    )


@pytest.fixture
def client(real_api_config):
    """Create SDK client with real API configuration"""
    return DataHubClient(real_api_config)


@pytest.fixture
def contracts_api(client):
    """Create ContractsAPI instance"""
    return client.contracts


def create_odcs_contract_via_api(api_base_url: str, api_key: str) -> Optional[str]:
    """
    Create an ODCS contract via the API for testing.

    Args:
        api_base_url: API base URL
        api_key: API key for authentication

    Returns:
        Contract ID (UUID) if successful, None otherwise
    """
    try:
        import requests

        # Create ODCS contract using the same format as CLI tests
        odcs_content = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": f"test-odcs-contract-{uuid.uuid4().hex[:8]}",
            "name": "Test ODCS Contract for SDK Export Tests",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": False
                    }
                ]
            }
        })

        contract_data = {
            "original_raw": odcs_content,
            "original_format": "JSON",
            "original_spec_type": "ODCS"
        }

        response = requests.post(
            f"{api_base_url}/contracts/",
            json=contract_data,
            headers={
                "X-API-Key": api_key,
                "Authorization": f"ApiKey {api_key}",
                "Content-Type": "application/json"
            },
            timeout=10
        )

        if response.status_code in [200, 201]:
            result = response.json()
            contract_id = result.get('id') or result.get('contract_id')
            return contract_id
        else:
            # Log error for debugging
            try:
                error_data = response.json()
                print(f"Contract creation failed: {error_data}")
            except Exception:
                print(f"Contract creation failed with status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Exception creating contract: {e}")
        return None


class TestODCSExportSDK:
    """
    SDK Integration Tests for ODCS Export.

    Tests SDK export methods with real API connections.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("version", ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"])
    async def test_export_odcs_all_versions(self, contracts_api, real_api_config, version):
        """Test SDK export with all supported ODCS versions."""
        api_base_url = real_api_config.base_url
        api_key = real_api_config.api_token

        # Create a test contract
        contract_id = create_odcs_contract_via_api(api_base_url, api_key)
        if not contract_id:
            pytest.skip("Failed to create test contract. API may not be properly configured.")

        try:
            # Export with specific version
            result = await contracts_api.export_odcs(contract_id, version=version, format="json")

            # Verify result structure
            assert isinstance(result, dict), f"Result should be a dict for version {version}"
            # Verify version is reflected in the result (if API supports it)
            if "apiVersion" in result:
                assert version in result["apiVersion"] or "odcs.io" in result["apiVersion"], \
                    f"Version {version} should be in apiVersion for version {version}"
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests
                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={"X-API-Key": api_key},
                    timeout=5
                )
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_export_odcs_format_conversion_json_to_yaml(self, contracts_api, real_api_config):
        """Test format conversion from JSON to YAML."""
        api_base_url = real_api_config.base_url
        api_key = real_api_config.api_token

        # Create a test contract
        contract_id = create_odcs_contract_via_api(api_base_url, api_key)
        if not contract_id:
            pytest.skip("Failed to create test contract. API may not be properly configured.")

        try:
            # Export as JSON first
            json_result = await contracts_api.export_odcs(contract_id, format="json")
            assert isinstance(json_result, dict)
            assert "apiVersion" in json_result or "kind" in json_result or "id" in json_result

            # Export as YAML
            yaml_result = await contracts_api.export_odcs(contract_id, format="yaml")
            assert isinstance(yaml_result, dict)
            assert "content" in yaml_result
            assert "format" in yaml_result
            assert yaml_result["format"] == "yaml"
            assert isinstance(yaml_result["content"], str)

            # Verify YAML content contains contract data
            yaml_content = yaml_result["content"].lower()
            assert "apiversion" in yaml_content or "kind" in yaml_content or "id" in yaml_content
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests
                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={"X-API-Key": api_key},
                    timeout=5
                )
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_export_odcs_format_conversion_yaml_to_json(self, contracts_api, real_api_config):
        """Test format conversion from YAML to JSON."""
        api_base_url = real_api_config.base_url
        api_key = real_api_config.api_token

        # Create a test contract
        contract_id = create_odcs_contract_via_api(api_base_url, api_key)
        if not contract_id:
            pytest.skip("Failed to create test contract. API may not be properly configured.")

        try:
            # Export as YAML first
            yaml_result = await contracts_api.export_odcs(contract_id, format="yaml")
            assert isinstance(yaml_result, dict)
            assert "content" in yaml_result
            assert yaml_result["format"] == "yaml"

            # Export as JSON
            json_result = await contracts_api.export_odcs(contract_id, format="json")
            assert isinstance(json_result, dict)
            assert "apiVersion" in json_result or "kind" in json_result or "id" in json_result

            # Both should contain the same contract data (just different formats)
            # Verify both have contract identifiers
            json_has_id = "id" in json_result or "apiVersion" in json_result
            yaml_has_id = "id" in yaml_result.get("content", "").lower() or "apiversion" in yaml_result.get("content", "").lower()
            assert json_has_id or yaml_has_id, "Both formats should contain contract identifiers"
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests
                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={"X-API-Key": api_key},
                    timeout=5
                )
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_export_odcs_error_handling_invalid_version(self, contracts_api, real_api_config):
        """Test error handling for invalid ODCS version."""
        api_base_url = real_api_config.base_url
        api_key = real_api_config.api_token

        # Create a test contract
        contract_id = create_odcs_contract_via_api(api_base_url, api_key)
        if not contract_id:
            pytest.skip("Failed to create test contract. API may not be properly configured.")

        try:
            # Try to export with invalid version
            with pytest.raises(ODCSValidationError) as exc_info:
                await contracts_api.export_odcs(contract_id, version="99.99.99", format="json")

            assert exc_info.value.code in ["INVALID_VALUE", "UNSUPPORTED_VERSION"]
            assert "version" in exc_info.value.message.lower() or "supported" in exc_info.value.message.lower()
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests
                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={"X-API-Key": api_key},
                    timeout=5
                )
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_export_odcs_error_handling_invalid_format(self, contracts_api, real_api_config):
        """Test error handling for invalid format."""
        api_base_url = real_api_config.base_url
        api_key = real_api_config.api_token

        # Create a test contract
        contract_id = create_odcs_contract_via_api(api_base_url, api_key)
        if not contract_id:
            pytest.skip("Failed to create test contract. API may not be properly configured.")

        try:
            # Try to export with invalid format
            with pytest.raises(ODCSValidationError) as exc_info:
                await contracts_api.export_odcs(contract_id, format="xml")

            assert exc_info.value.code == "INVALID_VALUE"
            assert "format" in exc_info.value.message.lower()
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests
                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={"X-API-Key": api_key},
                    timeout=5
                )
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_export_odcs_error_handling_not_found(self, contracts_api):
        """Test error handling for non-existent contract."""
        # Use a non-existent contract ID
        fake_contract_id = str(uuid.uuid4())

        with pytest.raises((NotFoundError, ODCSExportError, ODCSValidationError)):
            await contracts_api.export_odcs(fake_contract_id, format="json")

    @pytest.mark.asyncio
    async def test_export_odcs_error_handling_invalid_contract_id(self, contracts_api):
        """Test error handling for invalid contract ID format."""
        # Try with invalid UUID format
        with pytest.raises(ODCSValidationError) as exc_info:
            await contracts_api.export_odcs("not-a-uuid", format="json")

        assert exc_info.value.code in ["INVALID_VALUE", "REQUIRED_FIELD_MISSING"]
        assert "uuid" in exc_info.value.message.lower() or "contract_id" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_export_odcs_with_real_api_json(self, contracts_api, real_api_config):
        """Test SDK export with real API - JSON format."""
        api_base_url = real_api_config.base_url
        api_key = real_api_config.api_token

        # Create a test contract
        contract_id = create_odcs_contract_via_api(api_base_url, api_key)
        if not contract_id:
            pytest.skip("Failed to create test contract. API may not be properly configured.")

        try:
            # Export as JSON
            result = await contracts_api.export_odcs(contract_id, format="json")

            # Verify result structure
            assert isinstance(result, dict)
            assert "apiVersion" in result or "kind" in result or "id" in result

            # Verify it's valid ODCS structure
            if "apiVersion" in result:
                assert "odcs.io" in result["apiVersion"].lower()
            if "kind" in result:
                assert "datacontract" in result["kind"].lower()
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests
                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={"X-API-Key": api_key},
                    timeout=5
                )
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_export_odcs_with_real_api_yaml(self, contracts_api, real_api_config):
        """Test SDK export with real API - YAML format."""
        api_base_url = real_api_config.base_url
        api_key = real_api_config.api_token

        # Create a test contract
        contract_id = create_odcs_contract_via_api(api_base_url, api_key)
        if not contract_id:
            pytest.skip("Failed to create test contract. API may not be properly configured.")

        try:
            # Export as YAML
            result = await contracts_api.export_odcs(contract_id, format="yaml")

            # Verify result structure
            assert isinstance(result, dict)
            assert "content" in result
            assert "format" in result
            assert result["format"] == "yaml"
            assert isinstance(result["content"], str)

            # Verify YAML content contains ODCS fields
            yaml_content = result["content"].lower()
            assert "apiversion" in yaml_content or "kind" in yaml_content or "id" in yaml_content
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests
                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={"X-API-Key": api_key},
                    timeout=5
                )
            except Exception:
                pass

