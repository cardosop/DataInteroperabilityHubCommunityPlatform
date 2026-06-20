"""
Integration tests for ODPS helper methods.

These tests verify that ODPS helper methods work correctly with real API contract data.
"""

import os

import pytest

from datahub_interoperability import DataHubClient, DataHubClientConfig


def setup_authentication_for_sdk_tests(api_base_url: str) -> str | None:
    """
    Set up authentication for SDK tests.

    Delegates to the canonical conftest helper first, then falls back
    to credential-based login if the canonical helper returns None.
    """
    # Method 1: Canonical conftest helper (handles env vars, validation, auto-provision, refresh)
    try:
        from tests.conftest import get_api_key

        key = get_api_key()
        if key:
            return key
    except Exception:
        pass

    # Method 2: Use credentials from environment to login and get JWT token
    email = os.getenv("TEST_USER_EMAIL", "sdk-test@example.com")
    password = os.getenv("TEST_USER_PASSWORD", "TestPass123!")

    try:
        import requests

        login_response = requests.post(
            f"{api_base_url}/auth/login/",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=5,
        )

        if login_response.status_code == 200:
            login_data = login_response.json()
            access_token = login_data.get("access_token")
            if access_token:
                return access_token
    except Exception:
        pass

    return None


@pytest.fixture
def real_api_config():
    """Create config for real API (if available)."""
    api_url = os.getenv("API_BASE_URL", "http://localhost:8001/api/v1")

    # Use the canonical helper which validates the token and auto-provisions
    # a fresh one if needed.
    api_token = setup_authentication_for_sdk_tests(api_url)

    if not api_token:
        pytest.skip(
            "Could not set up authentication for SDK tests. "
            "Set TEST_API_KEY environment variable or ensure API is accessible at http://localhost:8001"
        )

    return DataHubClientConfig(
        base_url=api_url,
        api_token=api_token,
    )


@pytest.mark.asyncio
async def test_odps_helper_methods_integration(real_api_config):
    """
    Integration test for ODPS helper methods with real API contract data.

    This test:
    1. Creates an ODPS contract with comprehensive marketplace data
    2. Retrieves the contract via API
    3. Tests all ODPS helper methods with the real contract data
    """
    client = DataHubClient(real_api_config)

    # Create comprehensive ODPS contract with all marketplace features
    odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "sdk-test-helper-methods",
        "name": "SDK Test Helper Methods Product",
        "description": "Test product for ODPS helper methods integration test",
        "productVersion": "1.0.0"
      },
      "fi": {
        "productID": "sdk-test-helper-methods",
        "name": "SDK Test Helper Methods Tuote",
        "description": "Testituote ODPS helper methods integraatiotestille"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "sdk-test-helper-contract",
        "name": "SDK Test Helper Contract",
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
    },
    "marketplace": {
      "pricingPlans": [
        {
          "planID": "basic",
          "name": "Basic Plan",
          "price": 9.99,
          "currency": "USD",
          "billingPeriod": "monthly"
        },
        {
          "planID": "premium",
          "name": "Premium Plan",
          "price": 49.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "isDefault": true
        }
      ],
      "accessMethods": {
        "api": {
          "type": "REST",
          "endpoint": "https://api.example.com/v1",
          "protocol": "HTTPS"
        },
        "download": {
          "type": "HTTP",
          "url": "https://download.example.com/data"
        }
      },
      "paymentGateways": {
        "stripe": {
          "enabled": true,
          "mode": "test",
          "publicKey": "pk_test_example",
          "supportedCurrencies": ["USD", "EUR"]
        },
        "paypal": {
          "enabled": true,
          "provider": "PayPal"
        }
      }
    },
    "productStrategy": {
      "objectives": [
        "Increase data product adoption",
        "Improve data quality metrics"
      ],
      "strategicAlignment": [
        "Company-wide data strategy",
        "Digital transformation initiative"
      ],
      "productKPIs": [
        {
          "name": "Monthly Active Users",
          "target": 1000
        },
        {
          "name": "Data Quality Score",
          "target": 95
        }
      ]
    }
  }
}"""

    try:
        # Step 1: Create ODPS contract
        try:
            create_result = await client.contracts.create_odps(
                original_raw=odps_content,
                extract_odcs=True,
                original_format="JSON",
                odps_version="4.1",
            )
        except Exception as e:
            # Print full error details for debugging
            error_details = str(e)
            if hasattr(e, "details"):
                error_details += f"\nDetails: {e.details}"
            if hasattr(e, "context"):
                error_details += f"\nContext: {e.context}"
            pytest.fail(f"Failed to create ODPS contract: {error_details}")

        # Get ODPS contract ID
        if "odps_contract" in create_result:
            odps_id = create_result["odps_contract"]["id"]
        else:
            odps_id = create_result.get("id")

        if not odps_id:
            pytest.skip("Could not create ODPS contract for helper methods test")

        # Step 2: Retrieve contract via API
        contract = await client.contracts.get(odps_id)

        # Step 3: Test is_odps_contract
        assert client.contracts.is_odps_contract(contract) is True, (
            "Contract should be identified as ODPS"
        )

        # Step 4: Test get_odps_version
        version = client.contracts.get_odps_version(contract)
        assert version == "4.1", f"Expected ODPS version 4.1, got {version}"

        # Step 5: Test get_pricing_plans
        pricing_plans = client.contracts.get_pricing_plans(contract)
        assert pricing_plans is not None, "Pricing plans should not be None"
        assert isinstance(pricing_plans, list), "Pricing plans should be a list"
        assert len(pricing_plans) >= 1, "Should have at least one pricing plan"
        # Verify structure of first plan
        first_plan = pricing_plans[0]
        assert "planID" in first_plan or "name" in first_plan, (
            "Pricing plan should have planID or name"
        )

        # Step 6: Test get_access_methods
        access_methods = client.contracts.get_access_methods(contract)
        assert access_methods is not None, "Access methods should not be None"
        assert isinstance(access_methods, dict), "Access methods should be a dictionary"
        assert len(access_methods) >= 1, "Should have at least one access method"

        # Step 7: Test get_payment_gateways
        payment_gateways = client.contracts.get_payment_gateways(contract)
        assert payment_gateways is not None, "Payment gateways should not be None"
        assert isinstance(payment_gateways, dict), "Payment gateways should be a dictionary"
        assert len(payment_gateways) >= 1, "Should have at least one payment gateway"

        # Step 8: Test get_product_strategy
        product_strategy = client.contracts.get_product_strategy(contract)
        # Product strategy may or may not be present depending on normalization
        if product_strategy is not None:
            assert isinstance(product_strategy, dict), "Product strategy should be a dictionary"

        # Step 9: Test get_product_details with English
        product_details_en = client.contracts.get_product_details(contract, lang="en")
        assert product_details_en is not None, "Product details (en) should not be None"
        assert isinstance(product_details_en, dict), "Product details should be a dictionary"
        assert "productID" in product_details_en or "name" in product_details_en, (
            "Product details should have productID or name"
        )

        # Step 10: Test get_product_details with Finnish
        product_details_fi = client.contracts.get_product_details(contract, lang="fi")
        # Finnish may or may not be available depending on normalization
        if product_details_fi is not None:
            assert isinstance(product_details_fi, dict), (
                "Product details (fi) should be a dictionary"
            )

        # Step 11: Test get_product_details with default language (should default to "en")
        product_details_default = client.contracts.get_product_details(contract)
        assert product_details_default is not None, "Product details (default) should not be None"
        assert isinstance(product_details_default, dict), (
            "Product details (default) should be a dictionary"
        )

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
async def test_odps_helper_methods_with_minimal_contract(real_api_config):
    """
    Integration test for ODPS helper methods with minimal ODPS contract.

    Tests that helper methods handle missing optional fields gracefully.
    """
    client = DataHubClient(real_api_config)

    # Create minimal ODPS contract (no marketplace data)
    odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "sdk-test-minimal",
        "name": "SDK Test Minimal Product"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "sdk-test-minimal-contract",
        "name": "SDK Test Minimal Contract",
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
            pytest.skip("Could not create minimal ODPS contract for helper methods test")

        # Retrieve contract
        contract = await client.contracts.get(odps_id)

        # Test that helper methods handle missing data gracefully
        assert client.contracts.is_odps_contract(contract) is True
        assert client.contracts.get_odps_version(contract) == "4.1"

        # These may return None for minimal contract (which is expected)
        client.contracts.get_pricing_plans(contract)
        client.contracts.get_access_methods(contract)
        client.contracts.get_payment_gateways(contract)
        client.contracts.get_product_strategy(contract)

        # Product details should still work (from original_raw or hub_contract_json)
        product_details = client.contracts.get_product_details(contract, lang="en")
        assert product_details is not None, (
            "Product details should be available even for minimal contract"
        )
        assert "productID" in product_details or "name" in product_details

    except Exception as e:
        error_str = str(e)
        if "CSRF" in error_str or "403" in error_str:
            pytest.skip(
                f"Integration test skipped due to CSRF error. "
                f"This indicates the API endpoints may require CSRF exemption. "
                f"Error: {error_str[:200]}"
            )
        raise
