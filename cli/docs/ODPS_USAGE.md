# ODPS (Open Data Product Standard) CLI Usage Guide

Complete guide for using ODPS commands in the DataHub CLI.

## Table of Contents

1. [Overview](#overview)
2. [ODPS Concepts](#odps-concepts)
3. [Creating ODPS Contracts](#creating-odps-contracts)
4. [ODPS Linking](#odps-linking)
5. [ODPS Information Commands](#odps-information-commands)
6. [ODPS Export and Download](#odps-export-and-download)
7. [Workflow Patterns](#workflow-patterns)
8. [Troubleshooting](#troubleshooting)

## Overview

The DataHub CLI provides comprehensive support for ODPS (Open Data Product Standard) contracts. ODPS is a marketplace-focused standard that complements ODCS (Open Data Contract Standard) by adding product information, pricing plans, access methods, and payment gateways.

### Key Features

- **Product-First Flow**: Create ODPS products with embedded ODCS contracts
- **Linking**: Link ODPS contracts to existing ODCS contracts
- **Information Retrieval**: Get pricing plans, access methods, and marketplace data
- **Export/Download**: Export contracts in ODPS format

## ODPS Concepts

### ODPS vs ODCS

- **ODCS (Open Data Contract Standard)**: Technical specification focusing on data schema, quality, and compliance
- **ODPS (Open Data Product Standard)**: Marketplace specification focusing on product information, pricing, and access methods

### ODPS Structure

ODPS contracts contain:
- **Product Details**: Name, description, product ID
- **Marketplace Data**: Pricing plans, access methods, payment gateways
- **Contract Reference**: Link to ODCS contract (technical specification)

## Creating ODPS Contracts

### Product-First Flow

The Product-First flow automatically extracts and creates an ODCS contract from the ODPS product's embedded contract.

```bash
# Create ODPS product with embedded ODCS contract
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs

# With asset ID
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --asset-id <asset-id>

# From YAML file
datahub contracts create-odps \
  --file product.odps.yaml \
  --extract-odcs
```

**Example ODPS File** (`product.odps.json`):
```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset",
        "description": "Comprehensive customer analytics data"
      }
    },
    "contract": {
      "apiVersion": "odcs/v3",
      "kind": "DataContract",
      "id": "customer-analytics-contract",
      "name": "Customer Analytics Contract",
      "version": "1.0.0",
      "schema": {
        "fields": [
          {
            "name": "customer_id",
            "type": "string",
            "nullable": false
          },
          {
            "name": "purchase_amount",
            "type": "decimal",
            "nullable": true
          }
        ]
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
          "type": "REST API",
          "endpoint": "https://api.example.com/v1/products/customer-analytics",
          "protocol": "HTTPS"
        },
        "download": {
          "type": "File Download",
          "url": "https://download.example.com/customer-analytics.zip"
        }
      }
    }
  }
}
```

### Link Flow

Create an ODPS contract and link it to an existing ODCS contract.

```bash
# Create ODPS and link to existing ODCS contract
datahub contracts create-odps \
  --file product.odps.json \
  --link-odcs <odcs-contract-id>
```

**When to Use Link Flow**:
- You already have an ODCS contract created
- You want to add marketplace information to an existing technical contract
- You're working with separate technical and marketplace teams

## ODPS Linking

### Link ODPS to ODCS

```bash
# Link existing ODPS contract to existing ODCS contract
datahub contracts link-odps <odcs-contract-id> <odps-contract-id>
```

### Unlink ODPS from ODCS

```bash
# Unlink ODPS contract from ODCS contract
datahub contracts unlink-odps <odcs-contract-id>
```

### List Contract Links

```bash
# View all links for a contract
datahub contracts list-links <contract-id>

# Output shows:
# - ODPS Link: <odps-contract-id> (if contract is ODCS)
# - ODCS Link: <odcs-contract-id> (if contract is ODPS)
```

## ODPS Information Commands

### Get Contract with ODPS Information

Display contract details including ODPS marketplace data.

```bash
# Get contract with ODPS information
datahub contracts get <odps-contract-id> --show-odps

# Output includes:
# - Basic contract information
# - ODPS Information section:
#   - Pricing Plans (count, details)
#   - Access Methods (count, details)
#   - Payment Gateways (if configured)
```

**Example Output**:
```
ID: 0c48da60-1312-4fc5-b106-b08eaebb58f0
Version: 1
Status: ACTIVE
Spec Type: ODPS
Format: JSON
Normalization Status: NORMALIZED_OK

================================================================================
ODPS Information
================================================================================

Pricing Plans (2):
  1. Basic Plan
     Price: 9.99 USD
     Billing: monthly
  2. Premium Plan
     Price: 49.99 USD
     Billing: monthly
     Default: Yes

Access Methods (2):
  - api
    Type: REST API
    Endpoint: https://api.example.com/v1/products/customer-analytics
    Protocol: HTTPS
  - download
    Type: File Download
```

### Get Pricing Plans

Retrieve pricing information for an ODPS contract.

```bash
# Get pricing plans (table format)
datahub contracts get-pricing <odps-contract-id>

# Get pricing plans (JSON format)
datahub contracts get-pricing <odps-contract-id> --format json
```

**Example Output (Table)**:
```
Pricing Plans for Contract: 0c48da60-1312-4fc5-b106-b08eaebb58f0
================================================================================

Plan 1:
  Plan ID: basic
  Name: Basic Plan
  Price: 9.99 USD
  Billing Period: monthly

Plan 2:
  Plan ID: premium
  Name: Premium Plan
  Price: 49.99 USD
  Billing Period: monthly
  Default: Yes
```

**Example Output (JSON)**:
```json
{
  "contract_id": "0c48da60-1312-4fc5-b106-b08eaebb58f0",
  "pricing_plans": [
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
  ]
}
```

### Get Access Methods

Retrieve access method information for an ODPS contract.

```bash
# Get access methods (table format)
datahub contracts get-access-methods <odps-contract-id>

# Get access methods (JSON format)
datahub contracts get-access-methods <odps-contract-id> --format json
```

**Example Output (Table)**:
```
Access Methods for Contract: 0c48da60-1312-4fc5-b106-b08eaebb58f0
================================================================================

API:
  type: REST API
  endpoint: https://api.example.com/v1/products/customer-analytics
  protocol: HTTPS

DOWNLOAD:
  type: File Download
  url: https://download.example.com/customer-analytics.zip
```

## ODPS Export and Download

### Export ODPS Contract

Export a contract in ODPS format for sharing or backup.

```bash
# Export as ODPS JSON
datahub contracts export <contract-id> \
  --format odps \
  --output-format json

# Export as ODPS YAML
datahub contracts export <contract-id> \
  --format odps \
  --output-format yaml

# Export with specific ODPS version
datahub contracts export <contract-id> \
  --format odps \
  --output-format json \
  --version 4.1
```

### Download ODPS Contract

Download a contract as an ODPS file.

```bash
# Download as ODPS JSON file
datahub contracts download <contract-id> \
  --format odps \
  --output-format json \
  --output product.odps.json

# Download as ODPS YAML file
datahub contracts download <contract-id> \
  --format odps \
  --output-format yaml \
  --output product.odps.yaml
```

## Workflow Patterns

### Pattern 1: Product-First Workflow

Best for: Creating new products with both technical and marketplace specifications.

```bash
# 1. Create ODPS product with embedded ODCS contract
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --asset-id <asset-id>

# Output:
# ODPS Contract: <odps-id>
# ODCS Contract: <odcs-id>

# 2. View ODPS marketplace information
datahub contracts get <odps-id> --show-odps

# 3. Get pricing details
datahub contracts get-pricing <odps-id>

# 4. Get access methods
datahub contracts get-access-methods <odps-id>
```

### Pattern 2: Link Workflow

Best for: Adding marketplace information to existing technical contracts.

```bash
# 1. Create ODCS contract (technical specification)
datahub contracts create --file technical-spec.odcs.yaml

# 2. Create ODPS contract and link to ODCS
datahub contracts create-odps \
  --file marketplace-product.odps.json \
  --link-odcs <odcs-contract-id>

# 3. Verify the link
datahub contracts list-links <odcs-contract-id>

# 4. View marketplace information
datahub contracts get <odps-contract-id> --show-odps
```

### Pattern 3: Manual Linking

Best for: Linking existing ODPS and ODCS contracts.

```bash
# 1. Create ODCS contract
datahub contracts create --file technical.odcs.yaml

# 2. Create ODPS contract (without linking)
datahub contracts create-odps \
  --file product.odps.json \
  --link-odcs <temporary-odcs-id>  # Use a placeholder or skip

# 3. Manually link them
datahub contracts link-odps <odcs-id> <odps-id>

# 4. Verify link
datahub contracts list-links <odcs-id>
```

### Pattern 4: Information Retrieval Workflow

Best for: Querying ODPS marketplace information.

```bash
# 1. Get full ODPS information
datahub contracts get <odps-contract-id> --show-odps

# 2. Get specific pricing information
datahub contracts get-pricing <odps-contract-id> --format json

# 3. Get specific access methods
datahub contracts get-access-methods <odps-contract-id> --format json

# 4. Export for analysis
datahub contracts export <odps-contract-id> \
  --format odps \
  --output-format json \
  --cli-format json > product-analysis.json
```

## Troubleshooting

### Common Issues

#### Issue: "CSRF verification failed" when creating ODPS contracts

**Solution**: Ensure you're using API key authentication:
```bash
datahub config set api_key your-api-key-here
```

#### Issue: "Could not extract contract ID from output"

**Solution**: Use JSON format to get structured output:
```bash
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --output-format json
```

#### Issue: "No pricing plans found"

**Possible Causes**:
1. Contract is not an ODPS contract (check `original_spec_type`)
2. ODPS contract doesn't have marketplace data
3. Normalization didn't preserve pricing plans

**Solution**: Check contract type and normalization status:
```bash
datahub contracts get <contract-id>
# Look for: Spec Type: ODPS
# Look for: Normalization Status: NORMALIZED_OK
```

#### Issue: "No access methods found"

**Possible Causes**:
1. Contract is not an ODPS contract
2. ODPS contract doesn't have access methods defined
3. Access methods weren't preserved during normalization

**Solution**: Verify contract has access methods in original_raw or hub_contract_json.

### Best Practices

1. **Always specify format explicitly** when creating ODPS contracts:
   ```bash
   datahub contracts create-odps --file product.odps.json --extract-odcs
   ```

2. **Use JSON format for automation**:
   ```bash
   datahub contracts get-pricing <id> --format json | jq '.pricing_plans'
   ```

3. **Verify links after creation**:
   ```bash
   datahub contracts list-links <contract-id>
   ```

4. **Export before making changes**:
   ```bash
   datahub contracts export <id> --format odps --output-format json > backup.json
   ```

## Command Reference

### ODPS Creation Commands

| Command | Description | Required Options |
|---------|-------------|------------------|
| `create-odps` | Create ODPS contract | `--file`, `--extract-odcs` OR `--link-odcs` |
| `create-odps` | Create ODPS from YAML | `--file`, `--extract-odcs`, `--format YAML` |
| `create-odps` | Create with version | `--file`, `--extract-odcs`, `--version 4.1` |

### ODPS Linking Commands

| Command | Description | Arguments |
|---------|-------------|-----------|
| `link-odps` | Link ODPS to ODCS | `<odcs-id> <odps-id>` |
| `unlink-odps` | Unlink ODPS from ODCS | `<odcs-id>` |
| `list-links` | List contract links | `<contract-id>` |

### ODPS Information Commands

| Command | Description | Options |
|---------|-------------|---------|
| `get --show-odps` | Show ODPS information | `--show-odps`, `--format json\|table` |
| `get-pricing` | Get pricing plans | `--format json\|table` |
| `get-access-methods` | Get access methods | `--format json\|table` |

### ODPS Export Commands

| Command | Description | Options |
|---------|-------------|---------|
| `export --format odps` | Export as ODPS | `--format odps`, `--output-format json\|yaml`, `--version` |
| `download --format odps` | Download as ODPS file | `--format odps`, `--output-format json\|yaml`, `--output` |

## Additional Resources

- [ODPS Specification](https://opendataproducts.org/)
- [ODCS Specification](https://opendatacontracts.org/)
- [CLI README](../README.md)
- [API Documentation](../../docs/API_REFERENCE.md)

