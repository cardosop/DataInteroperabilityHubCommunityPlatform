# User Guide

Complete guide for users of the Interoperable Data Hub platform.

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Managing Assets](#managing-assets)
4. [Working with Contracts](#working-with-contracts)
5. [Data Quality](#data-quality)
6. [Compliance](#compliance)
7. [Marketplace](#marketplace)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Introduction

The Interoperable Data Hub is a platform for managing data assets, ensuring data quality, compliance, and enabling data sharing through a marketplace.

**Key Features:**

- **Asset Catalog**: Organize and manage your data assets
- **Contract Management**: Define and validate data contracts
- **Data Quality**: Run quality checks on your data
- **Compliance**: Scan data for compliance issues
- **Marketplace**: Share and discover data assets
- **Semantic Layer**: Query data using SPARQL

---

## Getting Started

### Creating an Account

1. Visit the hub registration page
2. Enter your email and password
3. Verify your email address
4. Complete your profile

### Logging In

1. Go to the login page
2. Enter your email and password
3. Click "Log In"

### API Access

For programmatic access, you'll need an API token:

1. Go to **Settings** → **API Tokens**
2. Click **Create Token**
3. Copy and save your token securely

**⚠️ Important**: API tokens are shown only once. Save them securely.

---

## Managing Assets

### Creating an Asset

1. Navigate to **Assets** → **Create Asset**
2. Fill in asset details:
   - **Name**: Asset name
   - **Description**: Asset description
   - **Domain**: Business domain (e.g., marketing, sales)
   - **Tags**: Optional tags for organization
3. Click **Create**

### Uploading Data

1. Go to **Files** → **Upload File**
2. Select your file (CSV, JSON, Parquet, etc.)
3. Wait for upload to complete
4. File will be available for use in datasets

### Creating a Dataset

1. Navigate to **Datasets** → **Create Dataset**
2. Select source file
3. Configure dataset:
   - **Name**: Dataset name
   - **Schema**: Auto-detected or manual
   - **Format**: CSV, JSON, Parquet
4. Click **Create**

### Activating an Asset

Before an asset can be used, it must be activated:

1. Go to **Assets** → Select your asset
2. Click **Activate**
3. Wait for activation to complete
4. Asset status will change to "Active"

---

## Working with Contracts

### Creating a Contract

1. Navigate to **Contracts** → **Create Contract**
2. Choose contract source:
   - **Upload**: Upload contract file (YAML, JSON)
   - **Template**: Use a template
   - **Manual**: Create manually
3. Fill in contract details
4. Click **Create**

### Contract Formats

The hub supports multiple contract formats:

- **ODCS** (Open Data Contract Standard)
- **DataContract.com** format
- **Hub Contract** format

All contracts are automatically normalized to HubContract format, which includes all sections described below.

### Contract Sections

#### Owners

**What are Owners?**

Owners are individuals or teams responsible for the contract. They are the primary contacts for questions, updates, and maintenance of the contract.

**How to Add Owners:**

In your contract, include an `owners` array in the `info` section:

```json
{
  "info": {
    "owners": [
      {
        "name": "Data Platform Team",
        "email": "dataplatform@example.com"
      },
      {
        "name": "John Doe",
        "email": "john.doe@example.com"
      }
    ]
  }
}
```

**Use Cases:**
- Identify who to contact for contract questions
- Track ownership for governance
- Filter contracts by owner
- Send notifications to owners

#### Tags

**What are Tags?**

Tags are labels used to organize and categorize contracts. They help you find and filter contracts by topic, domain, or purpose.

**How to Add Tags:**

Include a `tags` array in the `info` section:

```json
{
  "info": {
    "tags": ["analytics", "sales", "orders", "customer-data"]
  }
}
```

**Use Cases:**
- Organize contracts by business domain (e.g., "sales", "marketing")
- Categorize by data type (e.g., "customer-data", "transaction-data")
- Mark contracts by purpose (e.g., "analytics", "reporting")
- Filter contracts in the UI and API

#### Quality Rules

**What are Quality Rules?**

Quality rules define data quality checks and expectations. They specify what "good" data looks like and how to validate it.

**How to Define Quality Rules:**

Include a `quality` section with `rules` array:

```json
{
  "quality": {
    "default_profile_key": "intake_basic",
    "rules": [
      {
        "rule_id": "not_null_order_id",
        "dimension": "completeness",
        "expression": "order_id IS NOT NULL",
        "severity": "ERROR",
        "field": "order_id"
      },
      {
        "rule_id": "valid_email_format",
        "dimension": "validity",
        "expression": "customer_email LIKE '%@%.%'",
        "severity": "WARNING",
        "field": "customer_email"
      }
    ]
  }
}
```

**Dimensions:**
- `completeness`: Check for missing values
- `validity`: Check data format and constraints
- `consistency`: Check data consistency across fields
- `accuracy`: Check data accuracy against reference data
- `timeliness`: Check data freshness and update frequency

**Severity Levels:**
- `ERROR`: Critical issue that must be fixed
- `WARNING`: Issue that should be addressed
- `INFO`: Informational note

**Use Cases:**
- Define data quality expectations
- Automate quality checks during data ingestion
- Track quality metrics over time
- Filter contracts by quality profile

#### Compliance Policy

**What is Compliance Policy?**

Compliance policy defines data privacy and regulatory compliance requirements. It specifies what personal data is present, which jurisdictions apply, and how data should be handled.

**How to Define Compliance Policy:**

Include a `privacy_compliance` section:

```json
{
  "privacy_compliance": {
    "contains_personal_data": true,
    "personal_data_categories": ["EMAIL", "PHONE", "ADDRESS"],
    "jurisdictions": ["GDPR", "LGPD", "CCPA"],
    "legal_bases": ["CONSENT", "CONTRACT", "LEGAL_OBLIGATION"],
    "retention_policy": {
      "period": "P5Y",
      "notes": "5 years retention after contract end"
    }
  }
}
```

**Personal Data Categories:**
- `EMAIL`: Email addresses
- `PHONE`: Phone numbers
- `ADDRESS`: Physical addresses
- `HEALTH_DATA`: Health information
- `FINANCIAL_DATA`: Financial information
- `LOCATION`: Location data

**Jurisdictions:**
- `GDPR`: General Data Protection Regulation (EU)
- `LGPD`: Lei Geral de Proteção de Dados (Brazil)
- `CCPA`: California Consumer Privacy Act (US)
- `HIPAA`: Health Insurance Portability and Accountability Act (US)
- `SOX`: Sarbanes-Oxley Act (US)

**Legal Bases:**
- `CONSENT`: Data subject has given consent
- `CONTRACT`: Processing necessary for contract performance
- `LEGAL_OBLIGATION`: Processing required by law
- `VITAL_INTERESTS`: Processing necessary to protect vital interests
- `PUBLIC_TASK`: Processing necessary for public task
- `LEGITIMATE_INTERESTS`: Processing necessary for legitimate interests

**Use Cases:**
- Document compliance requirements
- Enable compliance scanning
- Filter contracts by jurisdiction
- Track data retention policies

#### Lifecycle Policy

**What is Lifecycle Policy?**

Lifecycle policy defines data refresh cadence and service level agreements (SLAs). It specifies how often data is updated and what performance guarantees are provided.

**How to Define Lifecycle Policy:**

Include a `lifecycle` section:

```json
{
  "lifecycle": {
    "data_source": "OLTP.orders",
    "refresh_cadence": "DAILY",
    "slas": {
      "availability": "99.0",
      "latency_ms_p95": 5000
    }
  }
}
```

**Refresh Cadence Options:**
- `REAL_TIME`: Data updated in real-time
- `HOURLY`: Data updated hourly
- `DAILY`: Data updated daily
- `WEEKLY`: Data updated weekly
- `MONTHLY`: Data updated monthly
- `ON_DEMAND`: Data updated on demand

**SLA Metrics:**
- `availability`: Availability percentage (e.g., "99.0" for 99%)
- `latency_ms_p95`: 95th percentile latency in milliseconds

**Use Cases:**
- Document data freshness expectations
- Set performance SLAs
- Filter contracts by refresh cadence
- Track data source information

#### Marketplace Policy

**What is Marketplace Policy?**

Marketplace policy defines how the data can be shared and used in the marketplace. It specifies licensing, intended use cases, and restrictions.

**How to Define Marketplace Policy:**

Include a `marketplace` section:

```json
{
  "marketplace": {
    "license_summary": "MIT License",
    "intended_use": ["analytics", "machine_learning", "reporting"],
    "restricted_use": ["resale", "competitive_analysis"]
  }
}
```

**Intended Use Cases:**
- `analytics`: Data analysis and insights
- `machine_learning`: Training ML models
- `reporting`: Business reporting
- `research`: Academic or scientific research
- `development`: Software development and testing

**Restricted Use Cases:**
- `resale`: Reselling the data
- `competitive_analysis`: Using data to compete with the provider
- `marketing`: Direct marketing to individuals
- `surveillance`: Surveillance or tracking

**Use Cases:**
- Define data sharing terms
- Enable marketplace listings
- Control data usage
- Document licensing

#### Field Properties

**What are Field Properties?**

Field properties define the structure, constraints, and semantics of data fields. They specify data types, validation rules, and semantic meaning.

**How to Define Field Properties:**

Include fields in the `schema.fields` array:

```json
{
  "schema": {
    "fields": [
      {
        "name": "order_id",
        "data_type": "string",
        "nullable": false,
        "description": "Unique identifier for the order",
        "semantic_type": "ORDER_ID",
        "format": null,
        "pattern": "^ORD-[0-9]{8}$",
        "enum": null,
        "default": null,
        "min_length": 10,
        "max_length": 20,
        "minimum": null,
        "maximum": null,
        "metadata": {
          "source_system": "OLTP",
          "business_key": true
        }
      }
    ],
    "primary_key": ["order_id"],
    "unique_constraints": [],
    "indexes": [["customer_email"]]
  }
}
```

**Field Properties:**
- `name`: Field name
- `data_type`: Data type (string, integer, number, boolean, date, datetime)
- `nullable`: Whether field can be null
- `description`: Field description
- `semantic_type`: Semantic type (EMAIL, PHONE, ORDER_ID, CURRENCY, DATE, etc.)
- `format`: Format specification (email, uri, date-time, uuid, etc.)
- `pattern`: Regex pattern for validation
- `enum`: Allowed enum values
- `default`: Default value
- `min_length`/`max_length`: String length constraints
- `minimum`/`maximum`: Numeric value constraints
- `metadata`: Additional metadata (key-value pairs)

**Semantic Types:**
- `EMAIL`: Email address
- `PHONE`: Phone number
- `ORDER_ID`: Order identifier
- `CUSTOMER_ID`: Customer identifier
- `CURRENCY`: Currency amount
- `DATE`: Date value
- `TIMESTAMP`: Timestamp value
- `URL`: URL/URI
- `IP_ADDRESS`: IP address

**Use Cases:**
- Define data structure
- Enable schema validation
- Support semantic mapping
- Document field constraints
- Enable field-level quality checks

### Validating a Contract

1. Go to **Contracts** → Select your contract
2. Click **Validate**
3. Review validation results
4. Fix any errors and re-validate

**Validation Status:**
- `VALID`: Contract is valid
- `INVALID`: Contract has errors
- `WARNING_ONLY`: Contract has warnings but no errors
- `ERROR`: Validation error occurred

### Activating a Contract

1. Go to **Contracts** → Select your contract
2. Ensure contract is validated
3. Click **Activate**
4. Contract will be linked to assets

**Activation Requirements:**
- Contract must be validated (`VALID` or `WARNING_ONLY`)
- Contract must be normalized (`NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`)
- If asset has dataset, DQ and compliance status must be `PASS` or `WARN`

---

## Data Quality

### Running a DQ Check

1. Navigate to **Data Quality** → **New Run**
2. Select dataset or asset
3. Configure checks:
   - **Completeness**: Check for missing values
   - **Uniqueness**: Check for duplicates
   - **Validity**: Check data format
   - **Consistency**: Check data consistency
4. Click **Run**
5. Review results

### Understanding DQ Results

DQ results include:

- **Overall Score**: 0-100 quality score
- **Check Results**: Individual check results
- **Issues**: List of data quality issues
- **Recommendations**: Suggestions for improvement

### Fixing DQ Issues

1. Review DQ results
2. Identify issues
3. Fix data source
4. Re-upload data
5. Re-run DQ check

---

## Compliance

### Running a Compliance Scan

1. Navigate to **Compliance** → **New Scan**
2. Select dataset or asset
3. Choose compliance frameworks:
   - **GDPR**: General Data Protection Regulation
   - **CCPA**: California Consumer Privacy Act
   - **HIPAA**: Health Insurance Portability
4. Click **Scan**
5. Review results

### Understanding Compliance Results

Compliance results include:

- **Risk Score**: Overall risk assessment
- **PII Detection**: Personally Identifiable Information found
- **Compliance Status**: Per-framework status
- **Recommendations**: Compliance improvement suggestions

### Addressing Compliance Issues

1. Review compliance results
2. Identify high-risk data
3. Apply data masking or encryption
4. Update data handling procedures
5. Re-run compliance scan

---

## Marketplace

### Creating a Listing

1. Navigate to **Marketplace** → **Create Listing**
2. Select asset to list
3. Configure listing:
   - **Title**: Listing title
   - **Description**: Listing description
   - **Price**: Listing price (if applicable)
   - **Terms**: Usage terms
4. Click **Publish**

### Discovering Assets

1. Go to **Marketplace** → **Browse**
2. Use filters:
   - **Domain**: Business domain
   - **Tags**: Asset tags
   - **Price Range**: Price filter
3. Click on listing to view details

### Placing an Order

1. Find desired asset in marketplace
2. Click **Request Access**
3. Fill in order details
4. Submit order
5. Wait for approval

### Managing Entitlements

1. Go to **Marketplace** → **My Entitlements**
2. View your active entitlements
3. Access entitled assets
4. Download data (if permitted)

---

## Best Practices

### Asset Management

- **Use descriptive names**: Clear, meaningful asset names
- **Add descriptions**: Document asset purpose and usage
- **Use tags**: Organize assets with tags
- **Keep assets updated**: Regularly update asset metadata

### Contract Management

- **Validate early**: Validate contracts before activation
- **Version contracts**: Keep contract versions for tracking
- **Document changes**: Document contract modifications
- **Review regularly**: Periodically review active contracts

### Data Quality

- **Run DQ checks regularly**: Schedule periodic quality checks
- **Fix issues promptly**: Address quality issues quickly
- **Monitor trends**: Track quality scores over time
- **Document exceptions**: Document acceptable quality thresholds

### Compliance

- **Scan before sharing**: Scan data before marketplace listing
- **Review results carefully**: Understand compliance implications
- **Apply recommendations**: Follow compliance recommendations
- **Stay updated**: Keep up with compliance framework changes

### Marketplace

- **Provide clear descriptions**: Help others understand your assets
- **Set appropriate terms**: Define clear usage terms
- **Respond to orders**: Process order requests promptly
- **Maintain listings**: Keep marketplace listings up to date

---

## Troubleshooting

### Common Issues

#### Asset Activation Fails

**Problem**: Asset activation fails with error

**Solutions**:
1. Check asset has required fields
2. Verify dataset is valid
3. Check contract is activated (if required)
4. Review error message for details

#### Contract Validation Fails

**Problem**: Contract validation returns errors

**Solutions**:
1. Review validation errors
2. Check contract format
3. Verify required fields are present
4. Check contract syntax

#### DQ Check Fails

**Problem**: DQ check fails or returns errors

**Solutions**:
1. Verify dataset is accessible
2. Check dataset format
3. Review error logs
4. Contact support if issue persists

#### Compliance Scan Issues

**Problem**: Compliance scan fails or returns unexpected results

**Solutions**:
1. Verify dataset is accessible
2. Check scan configuration
3. Review compliance framework requirements
4. Contact support for clarification

### Getting Help

- **Documentation**: https://docs.hub.example.com
- **Support Email**: support@hub.example.com
- **Community Forum**: https://forum.hub.example.com
- **API Documentation**: https://api.hub.example.com/api-docs/

---

## API Usage

### Using the API

The hub provides a REST API for programmatic access:

**Base URL**: `https://api.hub.example.com/api/v1`

**Authentication**: Include API token in header:
```
Authorization: Bearer your-api-token
```

### Example: Create Asset

```bash
curl -X POST https://api.hub.example.com/api/v1/assets/ \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Asset",
    "description": "Asset description",
    "domain": "marketing"
  }'
```

### SDKs

Official SDKs are available:

- **Python**: `pip install datahub-interoperability`
- **JavaScript**: `npm install @datahub/interoperability-sdk`

See [SDK Documentation](./SDK_DOCUMENTATION.md) for details.

---

## Glossary

- **Asset**: A data asset in the catalog
- **Contract**: Data contract defining data structure and quality
- **Dataset**: A collection of data files
- **DQ**: Data Quality
- **Entitlement**: Permission to access an asset
- **Listing**: Marketplace listing for an asset
- **Order**: Request for asset access
- **PII**: Personally Identifiable Information
- **SPARQL**: Query language for RDF data

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

