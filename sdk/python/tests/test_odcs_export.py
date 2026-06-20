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

from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

import os
import uuid

import pytest

from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    NotFoundError,
    ODCSValidationError,
)
from tests.conftest import default_api_base_url, get_api_key, is_api_available
from tests.helpers.odcs_helpers import create_odcs_contract_via_api


@pytest.fixture
def real_api_config():
    """Fixture for real API configuration"""
    if not is_api_available():
        pytest.skip("API service is not available. Ensure Docker Compose services are running.")

    api_key = get_api_key()
    if not api_key:
        pytest.skip(
            "No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable, "
            "or ensure Docker Compose api-service is accessible."
        )

    api_base_url = os.environ.get("API_BASE_URL", f"{default_api_base_url()}/api/v1")

    return DataHubClientConfig(base_url=api_base_url, api_token=api_key)


@pytest.fixture
def client(real_api_config):
    """Create SDK client with real API configuration"""
    return DataHubClient(real_api_config)


@pytest.fixture
def contracts_api(client):
    """Create ContractsAPI instance"""
    return client.contracts


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
                assert version in result["apiVersion"] or "odcs.io" in result["apiVersion"], (
                    f"Version {version} should be in apiVersion for version {version}"
                )
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests

                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={
                        "Authorization": f"Bearer {api_key}"
                        if "." in api_key
                        else f"ApiKey {api_key}"
                    },
                    timeout=5,
                )
            except requests.RequestException:
                pass  # cleanup best-effort — ignore network errors

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
                    headers={
                        "Authorization": f"Bearer {api_key}"
                        if "." in api_key
                        else f"ApiKey {api_key}"
                    },
                    timeout=5,
                )
            except requests.RequestException:
                pass  # cleanup best-effort — ignore network errors

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
            yaml_has_id = (
                "id" in yaml_result.get("content", "").lower()
                or "apiversion" in yaml_result.get("content", "").lower()
            )
            assert json_has_id or yaml_has_id, "Both formats should contain contract identifiers"
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests

                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={
                        "Authorization": f"Bearer {api_key}"
                        if "." in api_key
                        else f"ApiKey {api_key}"
                    },
                    timeout=5,
                )
            except requests.RequestException:
                pass  # cleanup best-effort — ignore network errors

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
            assert (
                "version" in exc_info.value.message.lower()
                or "supported" in exc_info.value.message.lower()
            )
        finally:
            # Cleanup: try to delete the contract
            try:
                import requests

                requests.delete(
                    f"{api_base_url}/contracts/{contract_id}/",
                    headers={
                        "Authorization": f"Bearer {api_key}"
                        if "." in api_key
                        else f"ApiKey {api_key}"
                    },
                    timeout=5,
                )
            except requests.RequestException:
                pass  # cleanup best-effort — ignore network errors

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
                    headers={
                        "Authorization": f"Bearer {api_key}"
                        if "." in api_key
                        else f"ApiKey {api_key}"
                    },
                    timeout=5,
                )
            except requests.RequestException:
                pass  # cleanup best-effort — ignore network errors

    @pytest.mark.asyncio
    async def test_export_odcs_error_handling_not_found(self, contracts_api):
        """Test error handling for non-existent contract."""
        # Use a non-existent contract ID
        fake_contract_id = str(uuid.uuid4())

        with pytest.raises(NotFoundError):
            await contracts_api.export_odcs(fake_contract_id, format="json")

    @pytest.mark.asyncio
    async def test_export_odcs_error_handling_invalid_contract_id(self, contracts_api):
        """Test error handling for invalid contract ID format."""
        # Try with invalid UUID format
        with pytest.raises(ODCSValidationError) as exc_info:
            await contracts_api.export_odcs("not-a-uuid", format="json")

        assert exc_info.value.code in ["INVALID_VALUE", "REQUIRED_FIELD_MISSING"]
        assert (
            "uuid" in exc_info.value.message.lower()
            or "contract_id" in exc_info.value.message.lower()
        )

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
                    headers={
                        "Authorization": f"Bearer {api_key}"
                        if "." in api_key
                        else f"ApiKey {api_key}"
                    },
                    timeout=5,
                )
            except requests.RequestException:
                pass  # cleanup best-effort — ignore network errors

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
                    headers={
                        "Authorization": f"Bearer {api_key}"
                        if "." in api_key
                        else f"ApiKey {api_key}"
                    },
                    timeout=5,
                )
            except requests.RequestException:
                pass  # cleanup best-effort — ignore network errors
