# ODPS Examples

Complete engineering-grade examples for ODPS (Open Data Product Standard) in the Data Interoperability Hub.

**Last Updated**: 2026-01-26
**Version**: 1.0.0

## Table of Contents

1. [ODPS 4.1 Example Files](#odps-41-example-files)
2. [ODPS Creation Examples](#odps-creation-examples)
3. [ODPS Linking Examples](#odps-linking-examples)
4. [ODPS Export Examples](#odps-export-examples)
5. [ODPS $ref Examples](#odps-ref-examples)
6. [ODPS Marketplace Examples](#odps-marketplace-examples)

---

## ODPS 4.1 Example Files

### Complete ODPS 4.1 Document

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics-v1",
        "name": "Customer Analytics Dataset",
        "description": "Comprehensive customer analytics data including purchase history, demographics, and behavior patterns",
        "productVersion": "1.0.0",
        "tags": ["analytics", "customer", "e-commerce"],
        "categories": ["Business Intelligence", "Customer Data"]
      },
      "fr": {
        "productID": "customer-analytics-v1",
        "name": "Dataset d'Analyse Client",
        "description": "Données complètes d'analyse client incluant l'historique d'achat, la démographie et les modèles de comportement"
      }
    },
    "contract": {
      "spec": {
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
              "nullable": false,
              "description": "Unique customer identifier"
            },
            {
              "name": "purchase_date",
              "type": "date",
              "nullable": false,
              "description": "Date of purchase"
            },
            {
              "name": "amount",
              "type": "number",
              "nullable": false,
              "description": "Purchase amount in USD"
            },
            {
              "name": "product_category",
              "type": "string",
              "nullable": true,
              "description": "Product category"
            }
          ]
        },
        "quality": {
          "rules": [
            {
              "name": "non_null_customer_id",
              "type": "not_null",
              "field": "customer_id",
              "description": "Customer ID must not be null"
            },
            {
              "name": "positive_amount",
              "type": "greater_than",
              "field": "amount",
              "value": 0,
              "description": "Purchase amount must be positive"
            }
          ]
        },
        "compliance": {
          "rules": [
            {
              "name": "gdpr_compliance",
              "type": "GDPR",
              "description": "GDPR compliance required"
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
          "description": "Basic access to customer analytics data",
          "price": 9.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "1000 records/month",
            "Basic analytics",
            "Email support"
          ]
        },
        {
          "planID": "premium",
          "name": "Premium Plan",
          "description": "Premium access with advanced features",
          "price": 29.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "Unlimited records",
            "Advanced analytics",
            "Priority support",
            "API access"
          ]
        }
      ],
      "accessMethods": {
        "api": {
          "type": "REST_API",
          "endpoint": "https://api.example.com/customer-analytics",
          "protocol": "HTTPS",
          "authentication": "Bearer Token",
          "rateLimit": "1000 requests/hour"
        },
        "download": {
          "type": "FILE_DOWNLOAD",
          "format": "CSV",
          "maxSize": "100MB"
        }
      },
      "paymentGateways": {
        "stripe": {
          "type": "STRIPE",
          "enabled": true,
          "publicKey": "pk_test_..."
        },
        "paypal": {
          "type": "PAYPAL",
          "enabled": true
        }
      },
      "license": {
        "type": "COMMERCIAL",
        "summary": "Commercial license for customer analytics data"
      },
      "intendedUse": [
        "Business Intelligence",
        "Customer Analysis",
        "Marketing Analytics"
      ],
      "restrictedUse": [
        "Resale",
        "Competitive Intelligence"
      ]
    },
    "productStrategy": {
      "objectives": [
        {
          "objectiveID": "obj-1",
          "name": "Increase Revenue",
          "description": "Generate revenue through data product sales",
          "target": "100K USD/year",
          "deadline": "2026-12-31"
        }
      ],
      "strategicAlignment": "Revenue Growth",
      "productKPIs": [
        {
          "kpiID": "kpi-1",
          "name": "Monthly Recurring Revenue",
          "metric": "MRR",
          "target": "10K USD",
          "current": "5K USD"
        },
        {
          "kpiID": "kpi-2",
          "name": "Customer Acquisition",
          "metric": "New Customers",
          "target": "100/month",
          "current": "50/month"
        }
      ]
    }
  }
}
```

### Minimal ODPS 4.1 Document

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "simple-product",
        "name": "Simple Product"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "simple-contract",
        "schema": {
          "fields": [
            {"name": "id", "type": "string"}
          ]
        }
      }
    }
  }
}
```

---

## ODPS Creation Examples

### Product-First Flow Example

**REST API:**

```bash
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"customer-analytics\",\"name\":\"Customer Analytics Dataset\"},\"contract\":{\"spec\":{\"apiVersion\":\"odcs/v3\",\"kind\":\"DataContract\",\"id\":\"customer-analytics-contract\",\"schema\":{\"fields\":[{\"name\":\"customer_id\",\"type\":\"string\"}]}}}}}}",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Python SDK:**

```python
from datahub_interoperability import DataHubClient, Config
import json

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

odps_document = {
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
            "spec": {
                "apiVersion": "odcs/v3",
                "kind": "DataContract",
                "id": "customer-analytics-contract",
                "schema": {
                    "fields": [
                        {"name": "customer_id", "type": "string"},
                        {"name": "purchase_date", "type": "date"},
                        {"name": "amount", "type": "number"}
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
                }
            ]
        }
    }
}

async with DataHubClient(config) as client:
    result = await client.contracts.create_odps(
        original_raw=json.dumps(odps_document),
        extract_odcs=True,
        original_format="JSON",
        resolve_external_refs=True
    )

    print(f"ODPS Contract ID: {result['odps_contract']['id']}")
    print(f"ODCS Contract ID: {result['odcs_contract']['id']}")
    print(f"Workflow Instance ID: {result['workflow_instance_id']}")
```

**CLI:**

```bash
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --resolve-external-refs
```

### Technical-First Flow Example

**Python SDK:**

```python
from hub.apps.contracts.services import ContractService

odcs_document = {
    "apiVersion": "odcs/v3",
    "kind": "DataContract",
    "id": "customer-analytics-contract",
    "schema": {
        "fields": [
            {"name": "customer_id", "type": "string"},
            {"name": "purchase_date", "type": "date"},
            {"name": "amount", "type": "number"}
        ]
    }
}

contract_service = ContractService(
    tenant_id=tenant_id,
    user_id=user_id
)

# Create ODCS contract
odcs_contract = contract_service.create_contract(
    original_raw=json.dumps(odcs_document),
    original_format="JSON",
    original_spec_type="ODCS"
)

# Auto-generate ODPS from ODCS
odps_contract = contract_service.auto_generate_odps_for_odcs(
    odcs_contract_id=str(odcs_contract.id),
    target_odps_version="4.1"
)

print(f"ODCS Contract ID: {odcs_contract.id}")
print(f"ODPS Contract ID: {odps_contract.id}")
```

### Data-First Flow Example

**Python SDK:**

```python
from datahub_interoperability import DataHubClient, Config

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

async with DataHubClient(config) as client:
    # Step 1: Upload file
    file_result = await client.files.upload(
        file_path="customer_data.csv",
        name="customer-data"
    )

    # Step 2: Create asset with auto-generated contracts
    asset = await client.assets.create(
        file_id=file_result["id"],
        name="Customer Analytics Dataset",
        key="customer-analytics",
        auto_generate_contracts=True,
        odps_action="generate",
        auto_activate=True
    )

    print(f"Asset ID: {asset['id']}")
    print(f"ODCS Contract ID: {asset['contracts']['odcs']['id']}")
    print(f"ODPS Contract ID: {asset['contracts']['odps']['id']}")
```

---

## ODPS Linking Examples

### Link ODPS to Existing ODCS

**REST API:**

```bash
curl -X POST "https://api.example.com/api/v1/contracts/{odcs-contract-id}/link-odps/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"linked-product\",\"name\":\"Linked Product\"}}}}",
    "original_format": "JSON"
  }'
```

**Python SDK:**

```python
odps_document = {
    "schema": "https://opendataproducts.org/schema/v4.1",
    "version": "4.1",
    "product": {
        "details": {
            "en": {
                "productID": "linked-product",
                "name": "Linked Product"
            }
        }
    }
}

# Create ODPS and link to existing ODCS
odps_contract = await client.contracts.create_odps(
    original_raw=json.dumps(odps_document),
    link_odcs_id="existing-odcs-contract-id",
    original_format="JSON"
)

print(f"ODPS Contract ID: {odps_contract['id']}")
print(f"Linked to ODCS Contract ID: existing-odcs-contract-id")
```

**CLI:**

```bash
datahub contracts link-odps \
  --odcs-id <odcs-contract-id> \
  --odps-file product.odps.json
```

### Verify Bidirectional Linking

**Python SDK:**

```python
# Get ODPS contract
odps_contract = await client.contracts.get_contract(
    contract_id="odps-contract-id"
)

# Check ODCS link
odcs_link = odps_contract["hub_contract_json"]["extensions"]["x_odps"]["odcs_link"]
print(f"ODPS links to ODCS: {odcs_link}")

# Get ODCS contract
odcs_contract = await client.contracts.get_contract(
    contract_id=odcs_link
)

# Check ODPS link
odps_link = odcs_contract["hub_contract_json"]["extensions"]["x_odps"]["odps_link"]
print(f"ODCS links to ODPS: {odps_link}")
```

---

## ODPS Export Examples

### Export as JSON

**REST API:**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=json&version=4.1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Python SDK:**

```python
odps_json = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="json",
    version="4.1"
)

print(odps_json["content"])
```

**CLI:**

```bash
datahub contracts export <contract-id> \
  --format odps \
  --output-format json \
  --version 4.1
```

### Export as YAML

**REST API:**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&output_format=yaml" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Python SDK:**

```python
odps_yaml = await client.contracts.export_odps(
    contract_id="odps-contract-id",
    format="yaml"
)

print(odps_yaml["content"])
```

**CLI:**

```bash
datahub contracts export <contract-id> \
  --format odps \
  --output-format yaml
```

### Download as File

**REST API:**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/download/?format=odps&output_format=json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o product.odps.json
```

**Python SDK:**

```python
odps_file = await client.contracts.download_odps(
    contract_id="odps-contract-id",
    format="json"
)

with open("product.odps.json", "wb") as f:
    f.write(odps_file)
```

**CLI:**

```bash
datahub contracts download <contract-id> \
  --format odps \
  --output-format json \
  --output product.odps.json
```

---

## ODPS $ref Examples

### Internal Reference Example

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "definitions": {
    "customerSchema": {
      "fields": [
        {"name": "customer_id", "type": "string"},
        {"name": "name", "type": "string"},
        {"name": "email", "type": "string"}
      ]
    }
  },
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset"
      }
    },
    "contract": {
      "spec": {
        "apiVersion": "odcs/v3",
        "kind": "DataContract",
        "id": "customer-analytics-contract",
        "schema": {
          "$ref": "#/definitions/customerSchema"
        }
      }
    }
  }
}
```

### Local Reference Example

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset"
      }
    },
    "contract": {
      "$ref": "./contracts/customer-schema.json"
    }
  }
}
```

**File: `./contracts/customer-schema.json`**

```json
{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "customer-schema",
  "schema": {
    "fields": [
      {"name": "customer_id", "type": "string"},
      {"name": "name", "type": "string"},
      {"name": "email", "type": "string"}
    ]
  }
}
```

### External Reference Example

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset"
      }
    },
    "contract": {
      "$ref": "https://schemas.example.com/data-contracts/customer-v1.json"
    }
  }
}
```

**REST API with External Ref Resolution:**

```bash
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "{\"schema\":\"https://opendataproducts.org/schema/v4.1\",\"version\":\"4.1\",\"product\":{\"details\":{\"en\":{\"productID\":\"customer-analytics\",\"name\":\"Customer Analytics Dataset\"}},\"contract\":{\"$ref\":\"https://schemas.example.com/data-contracts/customer-v1.json\"}}}}",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Python SDK:**

```python
odps_document = {
    "schema": "https://opendataproducts.org/schema/v4.1",
    "version": "4.1",
    "product": {
        "details": {
            "en": {
                "productID": "customer-analytics",
                "name": "Customer Analytics Dataset"
            }
        },
        "contract": {
            "$ref": "https://schemas.example.com/data-contracts/customer-v1.json"
        }
    }
}

result = await client.contracts.create_odps(
    original_raw=json.dumps(odps_document),
    extract_odcs=True,
    original_format="JSON",
    resolve_external_refs=True  # Enable external ref resolution
)
```

---

## ODPS Marketplace Examples

### Complete Marketplace Configuration

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "customer-analytics",
        "name": "Customer Analytics Dataset"
      }
    },
    "marketplace": {
      "pricingPlans": [
        {
          "planID": "free",
          "name": "Free Plan",
          "description": "Free access with limited features",
          "price": 0,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "100 records/month",
            "Basic analytics",
            "Community support"
          ]
        },
        {
          "planID": "basic",
          "name": "Basic Plan",
          "description": "Basic access to customer analytics data",
          "price": 9.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "1000 records/month",
            "Basic analytics",
            "Email support"
          ]
        },
        {
          "planID": "premium",
          "name": "Premium Plan",
          "description": "Premium access with advanced features",
          "price": 29.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "Unlimited records",
            "Advanced analytics",
            "Priority support",
            "API access"
          ]
        },
        {
          "planID": "enterprise",
          "name": "Enterprise Plan",
          "description": "Enterprise access with custom features",
          "price": 99.99,
          "currency": "USD",
          "billingPeriod": "monthly",
          "features": [
            "Unlimited records",
            "Advanced analytics",
            "Dedicated support",
            "API access",
            "Custom integrations",
            "SLA guarantee"
          ]
        }
      ],
      "accessMethods": {
        "api": {
          "type": "REST_API",
          "endpoint": "https://api.example.com/customer-analytics",
          "protocol": "HTTPS",
          "authentication": "Bearer Token",
          "rateLimit": "1000 requests/hour",
          "documentation": "https://docs.example.com/api/customer-analytics"
        },
        "download": {
          "type": "FILE_DOWNLOAD",
          "format": "CSV",
          "maxSize": "100MB",
          "compression": "gzip"
        },
        "streaming": {
          "type": "STREAMING",
          "protocol": "WebSocket",
          "endpoint": "wss://stream.example.com/customer-analytics"
        }
      },
      "paymentGateways": {
        "stripe": {
          "type": "STRIPE",
          "enabled": true,
          "publicKey": "pk_test_...",
          "supportedCurrencies": ["USD", "EUR", "GBP"]
        },
        "paypal": {
          "type": "PAYPAL",
          "enabled": true,
          "supportedCurrencies": ["USD", "EUR"]
        },
        "bank_transfer": {
          "type": "BANK_TRANSFER",
          "enabled": true,
          "instructions": "Contact sales@example.com for bank transfer details"
        }
      },
      "license": {
        "type": "COMMERCIAL",
        "summary": "Commercial license for customer analytics data",
        "terms": "https://example.com/license/customer-analytics"
      },
      "intendedUse": [
        "Business Intelligence",
        "Customer Analysis",
        "Marketing Analytics",
        "Data Science Research"
      ],
      "restrictedUse": [
        "Resale",
        "Competitive Intelligence",
        "Illegal Activities"
      ]
    }
  }
}
```

### Marketplace Integration Example

**Python SDK:**

```python
from datahub_interoperability import DataHubClient, Config

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

odps_document = {
    "schema": "https://opendataproducts.org/schema/v4.1",
    "version": "4.1",
    "product": {
        "details": {
            "en": {
                "productID": "customer-analytics",
                "name": "Customer Analytics Dataset"
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
            ],
            "accessMethods": {
                "api": {
                    "type": "REST_API",
                    "endpoint": "https://api.example.com/customer-analytics"
                }
            },
            "paymentGateways": {
                "stripe": {
                    "type": "STRIPE",
                    "enabled": True
                }
            }
        }
    }
}

async with DataHubClient(config) as client:
    # Create ODPS contract
    result = await client.contracts.create_odps(
        original_raw=json.dumps(odps_document),
        extract_odcs=True,
        original_format="JSON"
    )

    # Sync to marketplace
    marketplace_result = await client.marketplace.sync_product(
        product_id=result["odps_contract"]["id"],
        marketplace_type="SNOWFLAKE"
    )

    print(f"Product synced to marketplace: {marketplace_result['listing_id']}")
```

---

## Additional Resources

- [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md) - Complete ODPS integration guide
- [ODPS Creation Flows](ODPS_CREATION_FLOWS.md) - Detailed creation flow documentation
- [ODPS Migration Guide](ODPS_MIGRATION_GUIDE.md) - Comprehensive migration guide
- [Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md) - Marketplace integration architecture
- [Marketplace Integration User Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md) - User guide for marketplace integrations
- [Marketplace Use Cases](MARKETPLACE_USE_CASES.md) - Marketplace use cases and scenarios
- [API Reference](API_REFERENCE.md) - Complete API documentation

---

**Document Version**: 1.0.0
**Last Updated**: 2026-01-26
**Maintained By**: Data Interoperability Hub Team
