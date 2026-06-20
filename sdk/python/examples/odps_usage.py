"""
ODPS (Open Data Product Standard) Usage Examples

This module demonstrates comprehensive usage of ODPS functionality in the DataHub Interoperability SDK.
"""

import asyncio
import os

from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    NotFoundError,
    ODPSExportError,
    ODPSLinkingError,
    ODPSValidationError,
    ValidationError,
)

# Example ODPS 4.1 document with comprehensive marketplace features
EXAMPLE_ODPS_41 = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics-premium",
        "name": "Customer Analytics Premium",
        "description": "Comprehensive customer analytics data product with advanced features",
        "category": "Analytics",
        "tags": ["customer", "analytics", "premium"]
      },
      "fi": {
        "productID": "customer-analytics-premium",
        "name": "Asiakasanalyysi Premium",
        "description": "Kattava asiakasanalyysi-tuote edistyksellisillä ominaisuuksilla"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "customer-analytics-contract",
        "schema": {
          "fields": [
            {"name": "customer_id", "type": "string", "required": true},
            {"name": "customer_name", "type": "string", "required": true},
            {"name": "purchase_history", "type": "array", "required": false},
            {"name": "lifetime_value", "type": "number", "required": false}
          ]
        },
        "quality": {
          "freshness": {
            "maxAge": "PT1H"
          },
          "completeness": {
            "threshold": 0.95
          }
        }
      }
    },
    "marketplace": {
      "pricingPlans": [
        {
          "planID": "basic",
          "name": "Basic Plan",
          "description": "Access to basic customer data",
          "price": 9.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": ["basic_access", "api_access"]
        },
        {
          "planID": "premium",
          "name": "Premium Plan",
          "description": "Full access with advanced analytics",
          "price": 29.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": ["full_access", "api_access", "advanced_analytics", "priority_support"]
        }
      ],
      "accessMethods": {
        "api": {
          "type": "REST",
          "endpoint": "https://api.example.com/v1/customer-analytics",
          "authentication": "API_KEY",
          "rateLimit": {
            "requests": 1000,
            "period": "PT1H"
          }
        },
        "download": {
          "type": "FILE",
          "format": "CSV",
          "maxSize": "1GB"
        }
      },
      "paymentGateways": {
        "stripe": {
          "enabled": true,
          "publicKey": "pk_test_..."
        },
        "paypal": {
          "enabled": true
        }
      }
    },
    "productStrategy": {
      "objectives": [
        "Increase customer retention",
        "Improve data quality",
        "Expand market reach"
      ],
      "targetAudience": ["data analysts", "business intelligence teams"],
      "valueProposition": "Comprehensive customer insights with real-time updates"
    }
  }
}"""


async def example_create_odps_product_first(client: DataHubClient):
    """
    Example: Create ODPS contract using Product-First flow.

    This flow automatically extracts the ODCS contract from the ODPS product.contract field.
    """
    print("\n=== Example: Create ODPS (Product-First Flow) ===")

    try:
        result = await client.contracts.create_odps(
            original_raw=EXAMPLE_ODPS_41,
            extract_odcs=True,  # Automatically extract ODCS from ODPS
            original_format="JSON",
            odps_version="4.1",
        )

        odps_contract = result["odps_contract"]
        odcs_contract = result["odcs_contract"]

        print(f"✓ Created ODPS contract: {odps_contract['id']}")
        print(f"  Status: {odps_contract['status']}")
        print(f"  Spec Type: {odps_contract['original_spec_type']}")
        print(f"  Spec Version: {odps_contract['original_spec_version']}")

        print(f"✓ Created ODCS contract: {odcs_contract['id']}")
        print(f"  Status: {odcs_contract['status']}")

        if "workflow_instance_id" in result:
            print(f"✓ Workflow instance: {result['workflow_instance_id']}")

        return odps_contract["id"], odcs_contract["id"]

    except ODPSValidationError as e:
        print(f"✗ ODPS validation error: {e.message}")
        print(f"  Error code: {e.code}")
        print(f"  Field path: {e.field_path}")
        if e.expected:
            print(f"  Expected: {e.expected}")
        if e.actual:
            print(f"  Actual: {e.actual}")
        raise
    except ValidationError as e:
        print(f"✗ Validation error: {e.message}")
        if e.details:
            print(f"  Details: {e.details}")
        raise
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        raise


async def example_create_odps_link_flow(client: DataHubClient, existing_odcs_id: str):
    """
    Example: Create ODPS contract using Link flow.

    This flow links a new ODPS contract to an existing ODCS contract.
    """
    print("\n=== Example: Create ODPS (Link Flow) ===")

    # Simplified ODPS for linking (no contract spec needed)
    odps_content = """{
      "schema": "https://opendataproducts.org/schema/v4.1",
      "version": "4.1",
      "product": {
        "details": {
          "en": {
            "productID": "linked-product",
            "name": "Linked Data Product",
            "description": "ODPS contract linked to existing ODCS"
          }
        },
        "marketplace": {
          "pricingPlans": [
            {
              "planID": "standard",
              "name": "Standard Plan",
              "price": 19.99,
              "currency": "USD",
              "billingPeriod": "monthly"
            }
          ]
        }
      }
    }"""

    try:
        odps_contract = await client.contracts.create_odps(
            original_raw=odps_content,
            link_odcs_id=existing_odcs_id,
            original_format="JSON",
        )

        print(f"✓ Created ODPS contract: {odps_contract['id']}")
        print(f"  Status: {odps_contract['status']}")
        print(f"  Linked to ODCS: {existing_odcs_id}")

        return odps_contract["id"]

    except ODPSValidationError as e:
        print(f"✗ ODPS validation error: {e.message}")
        print(f"  Error code: {e.code}")
        raise
    except NotFoundError as e:
        print(f"✗ ODCS contract not found: {e.message}")
        raise
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        raise


async def example_export_odps(client: DataHubClient, odps_contract_id: str):
    """
    Example: Export ODPS contract in different formats.
    """
    print("\n=== Example: Export ODPS Contract ===")

    try:
        # Export as JSON
        print("Exporting as JSON...")
        odps_json = await client.contracts.export_odps(
            contract_id=odps_contract_id,
            format="json",
            version="4.1",
        )

        if isinstance(odps_json, dict):
            print("✓ Exported ODPS JSON")
            print(f"  Schema: {odps_json.get('schema')}")
            print(f"  Version: {odps_json.get('version')}")
            if "product" in odps_json:
                product_details = odps_json["product"].get("details", {}).get("en", {})
                print(f"  Product: {product_details.get('name')}")
        else:
            print("✓ Exported ODPS JSON (string)")

        # Export as YAML
        print("\nExporting as YAML...")
        odps_yaml = await client.contracts.export_odps(
            contract_id=odps_contract_id,
            format="yaml",
        )

        if isinstance(odps_yaml, dict) and "content" in odps_yaml:
            print(f"✓ Exported ODPS YAML ({len(odps_yaml['content'])} characters)")
        else:
            print("✓ Exported ODPS YAML")

        return odps_json

    except ODPSExportError as e:
        print(f"✗ ODPS export error: {e.message}")
        if e.context:
            print(f"  Context: {e.context}")
        raise
    except NotFoundError as e:
        print(f"✗ Contract not found: {e.message}")
        raise
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        raise


async def example_download_odps(client: DataHubClient, odps_contract_id: str):
    """
    Example: Download ODPS contract as file.
    """
    print("\n=== Example: Download ODPS Contract ===")

    try:
        # Download as JSON file
        odps_file = await client.contracts.download_odps(
            contract_id=odps_contract_id,
            format="json",
        )

        print(f"✓ Downloaded ODPS file ({len(odps_file)} bytes)")

        # Save to file
        output_path = "odps_contract.json"
        with open(output_path, "wb") as f:
            f.write(odps_file)

        print(f"✓ Saved to {output_path}")

        return odps_file

    except ODPSExportError as e:
        print(f"✗ ODPS download error: {e.message}")
        raise
    except NotFoundError as e:
        print(f"✗ Contract not found: {e.message}")
        raise
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        raise


async def example_odps_helper_methods(client: DataHubClient, odps_contract_id: str):
    """
    Example: Use ODPS helper methods to extract specific data.
    """
    print("\n=== Example: ODPS Helper Methods ===")

    try:
        # Get contract
        contract = await client.contracts.get(odps_contract_id)

        # Check if it's an ODPS contract
        if not client.contracts.is_odps_contract(contract):
            print("✗ Contract is not an ODPS contract")
            return

        print("✓ Contract is an ODPS contract")

        # Get ODPS version
        version = client.contracts.get_odps_version(contract)
        print(f"✓ ODPS version: {version}")

        # Get pricing plans
        pricing_plans = client.contracts.get_pricing_plans(contract)
        if pricing_plans:
            print(f"✓ Found {len(pricing_plans)} pricing plan(s):")
            for plan in pricing_plans:
                print(
                    f"  - {plan.get('name')} ({plan.get('planID')}): ${plan.get('price')} {plan.get('currency')}/{plan.get('billingPeriod')}"
                )
        else:
            print("  No pricing plans found")

        # Get access methods
        access_methods = client.contracts.get_access_methods(contract)
        if access_methods:
            print(f"✓ Found {len(access_methods)} access method(s):")
            for method_name, method_config in access_methods.items():
                method_type = method_config.get("type", "unknown")
                print(f"  - {method_name}: {method_type}")
                if "endpoint" in method_config:
                    print(f"    Endpoint: {method_config['endpoint']}")
        else:
            print("  No access methods found")

        # Get payment gateways
        payment_gateways = client.contracts.get_payment_gateways(contract)
        if payment_gateways:
            print(f"✓ Found {len(payment_gateways)} payment gateway(s):")
            for gateway_name, gateway_config in payment_gateways.items():
                enabled = gateway_config.get("enabled", False)
                status = "enabled" if enabled else "disabled"
                print(f"  - {gateway_name}: {status}")
        else:
            print("  No payment gateways found")

        # Get product strategy (ODPS 4.1+)
        product_strategy = client.contracts.get_product_strategy(contract)
        if product_strategy:
            print("✓ Product strategy found:")
            if "objectives" in product_strategy:
                print(f"  Objectives: {', '.join(product_strategy['objectives'])}")
            if "targetAudience" in product_strategy:
                print(f"  Target audience: {', '.join(product_strategy['targetAudience'])}")
        else:
            print("  No product strategy found")

        # Get product details (English)
        product_details_en = client.contracts.get_product_details(contract, lang="en")
        if product_details_en:
            print("✓ Product details (EN):")
            print(f"  ID: {product_details_en.get('productID')}")
            print(f"  Name: {product_details_en.get('name')}")
            print(f"  Description: {product_details_en.get('description', 'N/A')[:100]}...")
        else:
            print("  No English product details found")

        # Get product details (Finnish)
        product_details_fi = client.contracts.get_product_details(contract, lang="fi")
        if product_details_fi:
            print("✓ Product details (FI):")
            print(f"  Name: {product_details_fi.get('name')}")
        else:
            print("  No Finnish product details found")

    except NotFoundError as e:
        print(f"✗ Contract not found: {e.message}")
        raise
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        raise


async def example_odps_filtering(client: DataHubClient):
    """
    Example: Filter contracts using ODPS-specific filters.
    """
    print("\n=== Example: ODPS Filtering ===")

    try:
        # Filter by spec type (ODPS)
        print("Filtering by spec_type='ODPS'...")
        odps_contracts = await client.contracts.list(spec_type="ODPS")
        print(f"✓ Found {odps_contracts['count']} ODPS contract(s)")

        # Filter by ODPS version
        print("\nFiltering by odps_version='4.1'...")
        odps_41_contracts = await client.contracts.list(odps_version="4.1")
        print(f"✓ Found {odps_41_contracts['count']} ODPS 4.1 contract(s)")

        # Filter ODCS contracts with ODPS links
        print("\nFiltering ODCS contracts with ODPS links...")
        linked_odcs = await client.contracts.list(has_odps_link=True)
        print(f"✓ Found {linked_odcs['count']} ODCS contract(s) with ODPS links")

        # Filter ODCS contracts without ODPS links
        print("\nFiltering ODCS contracts without ODPS links...")
        unlinked_odcs = await client.contracts.list(has_odps_link=False)
        print(f"✓ Found {unlinked_odcs['count']} ODCS contract(s) without ODPS links")

        # Combine multiple filters
        print("\nCombining multiple filters...")
        filtered = await client.contracts.list(
            spec_type="ODPS",
            odps_version="4.1",
            page=1,
            page_size=10,
        )
        print(f"✓ Found {filtered['count']} matching contract(s)")
        if filtered["results"]:
            print("  Sample contracts:")
            for contract in filtered["results"][:3]:
                print(
                    f"    - {contract['id']}: {contract.get('original_spec_type')} v{contract.get('original_spec_version')}"
                )

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        raise


async def example_odps_linking(client: DataHubClient, odps_contract_id: str, odcs_contract_id: str):
    """
    Example: Link and unlink ODPS contracts to/from ODCS contracts.
    """
    print("\n=== Example: ODPS Linking ===")

    try:
        # Link ODPS to ODCS
        print(f"Linking ODPS {odps_contract_id} to ODCS {odcs_contract_id}...")
        linked_odps = await client.contracts.link_odps_to_odcs(
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
        )
        print(f"✓ Linked ODPS {linked_odps['id']} to ODCS")

        # Get linked contracts
        print("\nGetting linked contracts...")
        links = await client.contracts.get_linked_contracts(
            contract_id=odps_contract_id,
        )
        if links.get("odcs_link"):
            print(f"✓ ODCS link: {links['odcs_link']}")
        if links.get("odps_link"):
            print(f"✓ ODPS link: {links['odps_link']}")

        # Unlink ODPS from ODCS
        print(f"\nUnlinking ODPS from ODCS {odcs_contract_id}...")
        await client.contracts.unlink_odps_from_odcs(
            odcs_contract_id=odcs_contract_id,
        )
        print("✓ Unlinked successfully")

    except ODPSLinkingError as e:
        print(f"✗ ODPS linking error: {e.message}")
        if e.details:
            print(f"  Details: {e.details}")
        raise
    except NotFoundError as e:
        print(f"✗ Contract not found: {e.message}")
        raise
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        raise


async def example_odps_error_handling(client: DataHubClient):
    """
    Example: Handle ODPS-specific errors.
    """
    print("\n=== Example: ODPS Error Handling ===")

    # Invalid ODPS content (missing required fields)
    invalid_odps = """{
      "schema": "https://opendataproducts.org/schema/v4.1",
      "version": "4.1"
    }"""

    try:
        await client.contracts.create_odps(
            original_raw=invalid_odps,
            extract_odcs=True,
        )
        print("✗ Should have raised an error")
    except ODPSValidationError as e:
        print("✓ Caught ODPS validation error:")
        print(f"  Message: {e.message}")
        print(f"  Error code: {e.code}")
        if e.field_path:
            print(f"  Field path: {e.field_path}")
        if e.expected:
            print(f"  Expected: {e.expected}")
        if e.actual:
            print(f"  Actual: {e.actual}")

    # Invalid contract ID format
    try:
        await client.contracts.export_odps(
            contract_id="invalid-uuid",
            format="json",
        )
        print("✗ Should have raised an error")
    except ODPSValidationError as e:
        print("\n✓ Caught ODPS validation error for invalid UUID:")
        print(f"  Message: {e.message}")
        print(f"  Error code: {e.code}")

    # Invalid format
    try:
        await client.contracts.export_odps(
            contract_id="123e4567-e89b-12d3-a456-426614174000",
            format="xml",  # Invalid format
        )
        print("✗ Should have raised an error")
    except ODPSValidationError as e:
        print("\n✓ Caught ODPS validation error for invalid format:")
        print(f"  Message: {e.message}")
        print(f"  Error code: {e.code}")


async def main():
    """Main example function"""
    # Initialize client
    config = DataHubClientConfig(
        base_url=os.getenv("DATAHUB_BASE_URL", "http://localhost:8000/api/v1"),
        api_token=os.getenv("DATAHUB_API_TOKEN"),
        enable_logging=True,
    )

    async with DataHubClient(config) as client:
        print("=" * 60)
        print("ODPS Usage Examples")
        print("=" * 60)

        # Example 1: Create ODPS (Product-First flow)
        try:
            odps_id, odcs_id = await example_create_odps_product_first(client)

            # Example 2: Export ODPS
            await example_export_odps(client, odps_id)

            # Example 3: Download ODPS
            await example_download_odps(client, odps_id)

            # Example 4: ODPS helper methods
            await example_odps_helper_methods(client, odps_id)

            # Example 5: ODPS filtering
            await example_odps_filtering(client)

            # Example 6: ODPS linking
            await example_odps_linking(client, odps_id, odcs_id)

        except Exception as e:
            print(f"\n⚠ Skipping dependent examples due to error: {e}")

        # Example 7: Error handling (always runs)
        await example_odps_error_handling(client)

        print("\n" + "=" * 60)
        print("Examples completed")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
