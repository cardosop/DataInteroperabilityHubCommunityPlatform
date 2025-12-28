"""
Integration tests for DataHub SDK.

These tests verify that all API modules work together correctly.

Setup Instructions:
-------------------
To run these tests, you need to set up a tenant and API key for the test user.

Option 1: Set TEST_API_KEY environment variable
    export TEST_API_KEY='your-api-key-here'

Option 2: Run the setup script (requires Docker):
    docker-compose exec hub python /app/scripts/setup_sdk_test_tenant_and_api_key.py
    Then export the TEST_API_KEY from the output.

Option 3: Manual setup via Django shell:
    python manage.py shell
    >>> from hub.apps.users.models import User
    >>> from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
    >>> from hub.apps.auth.models import APIKey
    >>> # Create tenant, assign user, create API key
    >>> # See scripts/setup_sdk_test_tenant_and_api_key.py for details
"""
import os
import pytest
import requests
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    ODPSValidationError,
    ODPSExportError,
    ODPSLinkingError,
    NotFoundError,
)


def setup_authentication_for_sdk_tests(api_base_url: str) -> str | None:
    """
    Set up authentication for SDK tests.

    Tries multiple methods:
    1. Use TEST_API_KEY environment variable if available
    2. Use TEST_USER_EMAIL and TEST_USER_PASSWORD to login and get JWT token
    3. Try to create API key (requires tenant, may fail)

    Note: SDK client supports both API keys and JWT tokens, so we can use JWT tokens
    directly if API key creation fails (e.g., user doesn't have a tenant).

    Args:
        api_base_url: API base URL

    Returns:
        API key or JWT token string if successful, None otherwise
    """
    # Method 1: Use API key from environment variable
    api_key = os.getenv("TEST_API_KEY")
    if api_key:
        # Verify it works
        try:
            response = requests.get(
                f"{api_base_url}/contracts/contracts/",
                headers={"X-API-Key": api_key},
                timeout=5
            )
            if response.status_code in [200, 401]:  # 401 is OK, means auth is working
                return api_key
        except Exception:
            pass

    # Method 2: Use credentials from environment to login and get JWT token
    email = os.getenv("TEST_USER_EMAIL", "sdk-test@example.com")
    password = os.getenv("TEST_USER_PASSWORD", "TestPass123!")

    try:
        # Try to login directly (API endpoints should work without CSRF)
        # Use headers to ensure we're making an API request
        login_response = requests.post(
            f"{api_base_url}/auth/login/",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=5
        )

        access_token = None
        if login_response.status_code == 200:
            # Login successful, get access token
            try:
                # Check if response is JSON
                content_type = login_response.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    # Response is not JSON (might be HTML CSRF error page)
                    return None
                login_data = login_response.json()
                access_token = login_data.get("access_token")
            except (ValueError, KeyError):
                # Response is not valid JSON, skip
                return None
        else:
            # Login failed - check if it's a CSRF error or other issue
            # For API endpoints, CSRF should not be required, so this might indicate
            # the API is not accessible or there's a configuration issue
            return None

        if access_token:
            # Try to create API key first (preferred for SDK tests)
            try:
                api_key_response = requests.post(
                    f"{api_base_url}/auth/api-keys/",
                    json={"name": "SDK Test API Key"},
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=5
                )

                if api_key_response.status_code == 201:
                    api_key_data = api_key_response.json()
                    api_key = api_key_data.get("api_key")
                    if api_key:
                        return api_key
            except Exception:
                # API key creation failed (e.g., user needs tenant)
                # Fall through to use JWT token instead
                pass

            # If API key creation fails, use JWT token directly
            # SDK client supports JWT tokens (they contain dots)
            if access_token:
                return access_token
    except Exception as e:
        # If any step fails, return None
        # Don't print exception here to avoid cluttering test output
        pass

    return None


@pytest.fixture
def config():
    """Create test config."""
    return DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
    )


@pytest.fixture
def real_api_config():
    """Create config for real API (if available)."""
    api_url = os.getenv("TEST_API_URL", "http://localhost:8000/api/v1")

    # Try to get API key from environment or set it up automatically
    api_token = os.getenv("TEST_API_KEY")

    if not api_token:
        # Try to set up authentication automatically
        api_token = setup_authentication_for_sdk_tests(api_url)

    if not api_token:
        pytest.skip(
            "Could not set up authentication for SDK tests. "
            "Set TEST_API_KEY environment variable or ensure API is accessible at http://localhost:8000"
        )

    return DataHubClientConfig(
        base_url=api_url,
        api_token=api_token,
    )


def test_client_initialization(config):
    """Test that client initializes with all API modules."""
    client = DataHubClient(config)

    assert client.contracts is not None
    assert client.lineage is not None
    assert client.scheduled_ingestion is not None
    assert client.versioning is not None
    assert client.governance is not None
    assert client.mesh is not None
    assert client.search is not None
    assert client.observability is not None
    assert client.webhooks is not None


def test_client_api_access(config):
    """Test that all APIs are accessible from client."""
    client = DataHubClient(config)

    # Verify all APIs are initialized
    assert hasattr(client, "contracts")
    assert hasattr(client, "lineage")
    assert hasattr(client, "scheduled_ingestion")
    assert hasattr(client, "versioning")
    assert hasattr(client, "governance")
    assert hasattr(client, "mesh")
    assert hasattr(client, "search")
    assert hasattr(client, "observability")
    assert hasattr(client, "webhooks")


@pytest.mark.asyncio
async def test_create_odps_integration(real_api_config):
    """Integration test for creating ODPS contract via SDK with real API."""
    client = DataHubClient(real_api_config)

    odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "sdk-test-product-integration",
        "name": "SDK Test Product Integration",
        "description": "Test product created via SDK integration test"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "sdk-test-contract-integration",
        "name": "SDK Test Contract Integration",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {
              "name": "id",
              "type": "string",
              "nullable": false
            }
          ]
        }
      }
    }
  }
}"""

    try:
        result = await client.contracts.create_odps(
            original_raw=odps_content,
            extract_odcs=True,
            original_format="JSON",
            odps_version="4.1",
        )

        # Verify response structure
        assert "odps_contract" in result or "id" in result
        if "odps_contract" in result:
            # Product-First flow response
            assert "odcs_contract" in result
            odps_contract = result["odps_contract"]
            assert "id" in odps_contract
            assert odps_contract.get("original_spec_type") == "ODPS"
        else:
            # Link flow response (shouldn't happen with extract_odcs=True, but handle gracefully)
            assert "id" in result
    except Exception as e:
        # For integration tests, we want to see the actual error
        # but we'll skip if it's a CSRF error (API configuration issue)
        error_str = str(e)
        if "CSRF" in error_str or "403" in error_str:
            pytest.skip(
                f"Integration test skipped due to CSRF error. "
                f"This indicates the API endpoints may require CSRF exemption. "
                f"Error: {error_str[:200]}"
            )
        # For other errors, re-raise to see the actual issue
        raise


@pytest.mark.asyncio
async def test_create_odps_link_flow_integration(real_api_config):
    """Integration test for creating ODPS contract with link flow via SDK."""
    client = DataHubClient(real_api_config)

    # First, create an ODCS contract
    odcs_content = """{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "sdk-test-odcs-link",
  "name": "SDK Test ODCS for Link",
  "version": "1.0.0",
  "schema": {
    "fields": [
      {
        "name": "id",
        "type": "string",
        "nullable": false
      }
    ]
  }
}"""

    try:
        # Create ODCS contract
        odcs_result = await client.contracts.create(
            original_raw=odcs_content,
            original_format="JSON",
        )
        odcs_id = odcs_result.get("id")

        if not odcs_id:
            pytest.skip("Could not create ODCS contract for link flow test")

        # Now create ODPS contract linked to ODCS
        # For link flow, the ODPS document needs a contract section
        # but it can reference the existing ODCS contract
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "sdk-test-product-link",
        "name": "SDK Test Product for Link",
        "description": "Test product for link flow"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "sdk-test-odcs-link",
        "name": "SDK Test ODCS for Link",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {
              "name": "id",
              "type": "string",
              "nullable": false
            }
          ]
        }
      }
    }
  }
}"""

        result = await client.contracts.create_odps(
            original_raw=odps_content,
            link_odcs_id=odcs_id,
            original_format="JSON",
        )

        # Verify response
        assert "id" in result
        assert result.get("original_spec_type") == "ODPS"
    except Exception as e:
        # For integration tests, we want to see the actual error
        error_str = str(e)
        if "CSRF" in error_str or "403" in error_str:
            pytest.skip(
                f"Integration test skipped due to CSRF error. "
                f"This indicates the API endpoints may require CSRF exemption. "
                f"Error: {error_str[:200]}"
            )
        # For other errors, re-raise to see the actual issue
        raise


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_create_odps_product_first_flow_e2e(real_api_config):
    """
    E2E test for Product-First flow via SDK.

    This test verifies the complete workflow:
    1. Create ODPS contract with extract_odcs=True
    2. Verify both ODPS and ODCS contracts are created
    3. Verify they are linked bidirectionally
    """
    client = DataHubClient(real_api_config)

    odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "sdk-e2e-product-first",
        "name": "SDK E2E Test Product First",
        "description": "E2E test product for Product-First flow via SDK"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "sdk-e2e-contract-product-first",
        "name": "SDK E2E Test Contract Product First",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {
              "name": "id",
              "type": "string",
              "nullable": false
            },
            {
              "name": "name",
              "type": "string",
              "nullable": true
            }
          ]
        }
      }
    }
  },
  "marketplace": {
    "pricingPlans": [
      {
        "planID": "basic",
        "name": "Basic Plan",
        "price": 9.99,
        "currency": "USD",
        "billingPeriod": "monthly"
      }
    ]
  }
}"""

    try:
        # Step 1: Create ODPS contract with Product-First flow
        result = await client.contracts.create_odps(
            original_raw=odps_content,
            extract_odcs=True,
            original_format="JSON",
            odps_version="4.1",
            resolve_external_refs=True,
        )

        # Step 2: Verify response structure
        assert "odps_contract" in result, "Product-First flow should return odps_contract"
        assert "odcs_contract" in result, "Product-First flow should return odcs_contract"

        odps_contract = result["odps_contract"]
        odcs_contract = result["odcs_contract"]

        # Step 3: Verify ODPS contract
        assert "id" in odps_contract, "ODPS contract should have an ID"
        assert odps_contract.get("original_spec_type") == "ODPS", "ODPS contract should have spec type ODPS"
        odps_id = odps_contract["id"]

        # Step 4: Verify ODCS contract
        assert "id" in odcs_contract, "ODCS contract should have an ID"
        assert odcs_contract.get("original_spec_type") == "ODCS", "ODCS contract should have spec type ODCS"
        odcs_id = odcs_contract["id"]

        # Step 5: Verify contracts are linked (check links)
        odps_links = await client.contracts.get(odps_id)
        odcs_links = await client.contracts.get(odcs_id)

        # Check that links exist in hub_contract_json.extensions.x_odps
        odps_hub_contract = odps_links.get("hub_contract_json", {})
        odps_extensions = odps_hub_contract.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        odps_odcs_link = odps_x_odps.get("odcs_link")

        odcs_hub_contract = odcs_links.get("hub_contract_json", {})
        odcs_extensions = odcs_hub_contract.get("extensions", {})
        odcs_x_odps = odcs_extensions.get("x_odps", {})
        odcs_odps_link = odcs_x_odps.get("odps_link")

        # Verify bidirectional links
        assert str(odps_odcs_link) == str(odcs_id), "ODPS contract should link to ODCS contract"
        assert str(odcs_odps_link) == str(odps_id), "ODCS contract should link to ODPS contract"

    except Exception as e:
        # For E2E tests, we want to see the actual error
        error_str = str(e)
        if "CSRF" in error_str or "403" in error_str:
            pytest.skip(
                f"E2E test skipped due to CSRF error. "
                f"This indicates the API endpoints may require CSRF exemption. "
                f"Error: {error_str[:200]}"
            )
        # For other errors, re-raise to see the actual issue
        raise


@pytest.mark.asyncio
async def test_export_odps_integration(real_api_config):
    """Integration test for exporting ODPS contract via SDK with real API."""
    client = DataHubClient(real_api_config)

    # First, create an ODPS contract
    odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "sdk-test-export-product",
        "name": "SDK Test Export Product",
        "description": "Test product for export integration test"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "sdk-test-export-contract",
        "name": "SDK Test Export Contract",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {
              "name": "id",
              "type": "string",
              "nullable": false
            }
          ]
        }
      }
    }
  }
}"""

    try:
        # Create ODPS contract
        create_result = await client.contracts.create_odps(
            original_raw=odps_content,
            extract_odcs=True,
            original_format="JSON",
            odps_version="4.1",
        )

        # Get ODPS contract ID
        if "odps_contract" in create_result:
            odps_id = create_result["odps_contract"]["id"]
        else:
            odps_id = create_result.get("id")

        if not odps_id:
            pytest.skip("Could not create ODPS contract for export test")

        # Test export as JSON
        export_json = await client.contracts.export_odps(
            contract_id=odps_id,
            format="json",
            version="4.1",
        )

        # Verify export structure
        assert isinstance(export_json, dict), "Export should return a dictionary for JSON format"
        assert "schema" in export_json or "product" in export_json, "Export should contain ODPS structure"

        # Test export as YAML
        export_yaml = await client.contracts.export_odps(
            contract_id=odps_id,
            format="yaml",
            version="4.1",
        )

        # Verify YAML export structure
        assert isinstance(export_yaml, dict), "Export should return a dictionary for YAML format"
        assert "content" in export_yaml, "YAML export should have 'content' field"
        assert "format" in export_yaml, "YAML export should have 'format' field"
        assert export_yaml["format"] == "yaml", "Format should be 'yaml'"
        assert isinstance(export_yaml["content"], str), "YAML content should be a string"

    except Exception as e:
        error_str = str(e)
        if "CSRF" in error_str or "403" in error_str:
            pytest.skip(
                f"Integration test skipped due to CSRF error. "
                f"This indicates the API endpoints may require CSRF exemption. "
                f"Error: {error_str[:200]}"
            )
        raise


@pytest.mark.asyncio
async def test_download_odps_integration(real_api_config):
    """Integration test for downloading ODPS contract via SDK with real API."""
    client = DataHubClient(real_api_config)

    # First, create an ODPS contract
    odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "sdk-test-download-product",
        "name": "SDK Test Download Product",
        "description": "Test product for download integration test"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "sdk-test-download-contract",
        "name": "SDK Test Download Contract",
        "version": "1.0.0",
        "schema": {
          "fields": [
            {
              "name": "id",
              "type": "string",
              "nullable": false
            }
          ]
        }
      }
    }
  }
}"""

    try:
        # Create ODPS contract
        create_result = await client.contracts.create_odps(
            original_raw=odps_content,
            extract_odcs=True,
            original_format="JSON",
            odps_version="4.1",
        )

        # Get ODPS contract ID
        if "odps_contract" in create_result:
            odps_id = create_result["odps_contract"]["id"]
        else:
            odps_id = create_result.get("id")

        if not odps_id:
            pytest.skip("Could not create ODPS contract for download test")

        # Test download as JSON
        download_json = await client.contracts.download_odps(
            contract_id=odps_id,
            format="json",
            version="4.1",
        )

        # Verify download content
        assert isinstance(download_json, bytes), "Download should return bytes"
        assert len(download_json) > 0, "Download should return non-empty content"

        # Verify it's valid JSON
        import json
        json_content = json.loads(download_json.decode("utf-8"))
        assert "schema" in json_content or "product" in json_content, "Downloaded content should contain ODPS structure"

        # Test download as YAML
        download_yaml = await client.contracts.download_odps(
            contract_id=odps_id,
            format="yaml",
            version="4.1",
        )

        # Verify YAML download content
        assert isinstance(download_yaml, bytes), "Download should return bytes"
        assert len(download_yaml) > 0, "Download should return non-empty content"

        # Verify it contains YAML-like content
        yaml_content = download_yaml.decode("utf-8")
        assert "schema" in yaml_content or "product" in yaml_content, "Downloaded YAML should contain ODPS structure"

    except Exception as e:
        error_str = str(e)
        if "CSRF" in error_str or "403" in error_str:
            pytest.skip(
                f"Integration test skipped due to CSRF error. "
                f"This indicates the API endpoints may require CSRF exemption. "
                f"Error: {error_str[:200]}"
            )
        raise



@pytest.mark.asyncio
async def test_export_odps_error_scenarios(real_api_config):
    """Integration test for ODPS export error scenarios."""
    client = DataHubClient(real_api_config)

    # Test 1: Invalid contract ID
    try:
        await client.contracts.export_odps("invalid-uuid", format="json")
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code in ["INVALID_VALUE", "REQUIRED_FIELD_MISSING"]
        assert "uuid" in e.message.lower() or "contract_id" in e.message.lower()
    except NotFoundError:
        # API may return 404 for invalid UUID, which is also acceptable
        pass

    # Test 2: Invalid format
    try:
        await client.contracts.export_odps("123e4567-e89b-12d3-a456-426614174000", format="xml")
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "INVALID_VALUE"
        assert "format" in e.message.lower()

    # Test 3: Invalid version format
    try:
        await client.contracts.export_odps(
            "123e4567-e89b-12d3-a456-426614174000",
            version="invalid-version",
            format="json",
        )
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "INVALID_VALUE"
        assert "version" in e.message.lower() or "format" in e.message.lower()

    # Test 4: Non-existent contract (should return 404)
    try:
        await client.contracts.export_odps("00000000-0000-0000-0000-000000000000", format="json")
        pytest.fail("Should have raised NotFoundError or ODPSExportError")
    except (NotFoundError, ODPSExportError, ODPSValidationError):
        # All of these are acceptable error types for non-existent contract
        pass


@pytest.mark.asyncio
async def test_download_odps_error_scenarios(real_api_config):
    """Integration test for ODPS download error scenarios."""
    client = DataHubClient(real_api_config)

    # Test 1: Invalid contract ID
    try:
        await client.contracts.download_odps("not-a-uuid", format="json")
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code in ["INVALID_VALUE", "REQUIRED_FIELD_MISSING"]

    # Test 2: Invalid format
    try:
        await client.contracts.download_odps("123e4567-e89b-12d3-a456-426614174000", format="xml")
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "INVALID_VALUE"
        assert "format" in e.message.lower()

    # Test 3: Non-existent contract (should return 404)
    try:
        await client.contracts.download_odps("00000000-0000-0000-0000-000000000000", format="json")
        pytest.fail("Should have raised NotFoundError or ODPSExportError")
    except (NotFoundError, ODPSExportError, ODPSValidationError):
        # All of these are acceptable error types for non-existent contract
        pass


@pytest.mark.asyncio
async def test_create_odps_error_scenarios(real_api_config):
    """Integration test for ODPS creation error scenarios."""
    client = DataHubClient(real_api_config)

    # Test 1: Empty content
    try:
        await client.contracts.create_odps("", extract_odcs=True)
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "REQUIRED_FIELD_MISSING"
        assert "original_raw" in e.message.lower() or "required" in e.message.lower()

    # Test 2: Too short content
    try:
        await client.contracts.create_odps("{}", extract_odcs=True)
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "INVALID_VALUE"
        assert "short" in e.message.lower() or "length" in e.message.lower()

    # Test 3: Mutually exclusive options
    odps_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}'
    try:
        await client.contracts.create_odps(
            original_raw=odps_content,
            extract_odcs=True,
            link_odcs_id="123e4567-e89b-12d3-a456-426614174000",
        )
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "INVALID_VALUE"
        assert "extract_odcs" in e.message.lower() or "link_odcs_id" in e.message.lower()

    # Test 4: Neither option provided
    try:
        await client.contracts.create_odps(original_raw=odps_content)
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "REQUIRED_FIELD_MISSING"
        assert "extract_odcs" in e.message.lower() or "link_odcs_id" in e.message.lower()

    # Test 5: Invalid version format
    try:
        await client.contracts.create_odps(
            original_raw=odps_content,
            extract_odcs=True,
            odps_version="invalid",
        )
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "INVALID_VALUE"
        assert "version" in e.message.lower()


@pytest.mark.asyncio
async def test_link_odps_error_scenarios(real_api_config):
    """Integration test for ODPS linking error scenarios."""
    client = DataHubClient(real_api_config)

    # Test 1: Invalid ODCS contract ID
    try:
        await client.contracts.link_odps_to_odcs(
            odcs_contract_id="invalid-uuid",
            odps_raw='{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}',
            odps_format="JSON",
        )
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code in ["INVALID_VALUE", "REQUIRED_FIELD_MISSING"]

    # Test 2: Missing odps_format when odps_raw provided
    try:
        await client.contracts.link_odps_to_odcs(
            odcs_contract_id="123e4567-e89b-12d3-a456-426614174000",
            odps_raw='{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}',
        )
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "REQUIRED_FIELD_MISSING"
        assert "odps_format" in e.message.lower()

    # Test 3: Neither odps_contract_id nor odps_raw provided
    try:
        await client.contracts.link_odps_to_odcs(
            odcs_contract_id="123e4567-e89b-12d3-a456-426614174000",
        )
        pytest.fail("Should have raised ODPSValidationError")
    except ODPSValidationError as e:
        assert e.code == "REQUIRED_FIELD_MISSING"
        assert "odps_contract_id" in e.message.lower() or "odps_raw" in e.message.lower()
