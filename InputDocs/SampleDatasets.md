# Sample Datasets (MVP)

This document defines a small but representative catalog of **sample datasets**
used to exercise the Interoperable Data Hub end‑to‑end in MVP:

- Ingestion & canonical **HubContract** model
- Semantic mapping & RDF persistence
- Compliance & data quality (DQ) rules
- Lineage, discovery, and access patterns

Each dataset is intentionally **small enough** for local development, but rich
enough to cover realistic scenarios and edge cases.

---

## 1. Conventions

- All sample data is **synthetic** and must not contain real PII.
- Datasets are assumed to live in a tenant‑specific object store prefix, e.g.:

  - `s3://<tenant-bucket>/samples/<dataset-key>/...`

- Each dataset has:
  - a **dataset key** (used in folder and file names),
  - a **primary contract** in `contract_examples/`,
  - an explicit **DQ & compliance profile**.

---

## 2. Dataset: customers_core

**Dataset key:** `customers_core`  
**Shape:** Relational table (CSV / Parquet)  
**Granularity:** 1 row per customer

### 2.1 Purpose

- Exercise a “core golden record” style asset.
- Validate how PII flags, classifications, and retention policies flow through
  contracts, semantic mapping, and compliance rules.

### 2.2 Example schema

| Column          | Type      | Nullable | Description                                 |
|-----------------|-----------|----------|---------------------------------------------|
| customer_id     | string    | false    | Stable customer identifier (business key).  |
| full_name       | string    | false    | Customer full name (PII).                   |
| email           | string    | true     | Email address (PII).                        |
| date_of_birth   | date      | true     | DoB – used for age‑based rules (PII).       |
| country_code    | string    | true     | ISO country code.                           |
| created_at      | timestamp | false    | Record creation time.                       |
| updated_at      | timestamp | true     | Last update time.                           |
| is_active       | boolean   | false    | Active / inactive flag.                     |

### 2.3 DQ expectations

- `customer_id` must be:
  - non‑null,
  - unique,
  - immutable once written (enforced at process level).
- `email` must match a basic email regex when present.
- `country_code` must be in the reference list from `ref_countries` (see below).
- Timestamps must be non‑null and `created_at <= updated_at` when `updated_at`
  is present.

### 2.4 Compliance expectations

- Classified as **CONFIDENTIAL** with `contains_pii = true`.
- Retention policy must be defined in the contract (e.g. 7 years after
  offboarding).
- Access restricted to small set of roles (e.g. Data Engineers, Compliance
  Officers, authorised Consumers).

---

## 3. Dataset: transactions_pii_edge_cases

**Dataset key:** `transactions_pii_edge_cases`  
**Shape:** Relational table (CSV / Parquet)  
**Granularity:** 1 row per financial transaction

### 3.1 Purpose

- Stress‑test compliance and DQ rules on:
  - partial PII,
  - nullable fields,
  - mixed valid and invalid values.
- Provide realistic negative cases for rule evaluation and reporting.

### 3.2 Example schema

| Column          | Type      | Nullable | Description                                          |
|-----------------|-----------|----------|------------------------------------------------------|
| transaction_id  | string    | false    | Unique transaction identifier.                       |
| customer_id     | string    | false    | Foreign key to `customers_core.customer_id`.         |
| amount          | decimal   | false    | Transaction amount (positive or negative).           |
| currency        | string    | false    | ISO 4217 currency code.                              |
| merchant_name   | string    | true     | Free‑text merchant name (may contain “PII‑like” data)|
| card_pan_hash   | string    | true     | Hashed PAN (never raw card number).                  |
| transaction_ts  | timestamp | false    | Transaction time.                                    |
| channel         | string    | true     | e.g. `POS`, `ONLINE`, `MOBILE`.                      |
| metadata        | json      | true     | Semi‑structured extras for edge case testing.        |

### 3.3 DQ expectations

- `transaction_id` is non‑null and unique.
- `amount` must be non‑null and within a configured range
  (e.g. −1,000,000 to +1,000,000).
- `currency` must be one of the allowed values defined in the contract.
- `customer_id` must exist in the `customers_core` dataset for positive‑case
  records; a fraction of rows intentionally violate this for DQ testing.
- A small, controlled percentage of rows intentionally contain:
  - invalid `currency` codes,
  - out‑of‑range `amount` values,
  - missing or malformed timestamps.

### 3.4 Compliance expectations

- Dataset contains **financial transaction data** and is at least
  **INTERNAL / RESTRICTED**.
- `card_pan_hash` is never allowed to contain reversible or raw PAN values.
- Rules check that:
  - any column deemed “sensitive PII” is either absent or stored only in
    hashed / tokenised form,
  - `merchant_name` does not leak “obvious” personal data beyond contracts.

---

## 4. Dataset: ref_countries

**Dataset key:** `ref_countries`  
**Shape:** Small reference table  
**Granularity:** 1 row per country

### 4.1 Purpose

- Provide a simple reference dataset for:
  - foreign‑key style checks from other datasets,
  - semantic mapping of classification / region fields,
  - low‑risk public or internal reference data.

### 4.2 Example schema

| Column          | Type    | Nullable | Description                            |
|-----------------|---------|----------|----------------------------------------|
| country_code    | string  | false    | ISO country code (e.g. `US`, `BR`).    |
| country_name    | string  | false    | English name.                          |
| region          | string  | true     | e.g. `AMER`, `EMEA`, `APAC`.           |
| eu_member       | boolean | true     | Whether the country is in the EU.      |

### 4.3 DQ expectations

- `country_code` is unique, non‑null, and upper‑case.
- No duplicate `(country_code, country_name)` pairs.
- Optional fields (`region`, `eu_member`) may be null for edge cases.

### 4.4 Compliance expectations

- Contains **no PII**; safe as **INTERNAL** or even **PUBLIC** depending on
  tenant policy.
- Used to validate region‑specific rules in other datasets (e.g. EU vs non‑EU).

---

## 5. Dataset: events_application_logs

**Dataset key:** `events_application_logs`  
**Shape:** Append‑only event log (JSON Lines)  
**Granularity:** 1 row per application event

### 5.1 Purpose

- Exercise ingestion and contracts for semi‑structured event data.
- Validate semantic mapping for event‑style models.
- Provide a dataset with **minimal PII** but rich operational metadata.

### 5.2 Example schema (logical)

| Field           | Type      | Nullable | Description                             |
|-----------------|-----------|----------|-----------------------------------------|
| event_id        | string    | false    | Unique event identifier.                |
| event_ts        | timestamp | false    | Event timestamp.                         |
| service_name    | string    | false    | Name of emitting service.               |
| level           | string    | true     | e.g. `INFO`, `WARN`, `ERROR`.           |
| message         | string    | false    | Log message (sanitised, no raw PII).    |
| correlation_id  | string    | true     | Trace / correlation identifier.         |
| attributes      | json      | true     | Key/value bag for structured metadata.  |

### 5.3 DQ expectations

- `event_id` is non‑null; uniqueness is **best‑effort** (event logs may allow
  duplicates).
- `event_ts` must be within a reasonable time window (e.g. last N days) for
  test datasets.
- `attributes` is optional but when present must be valid JSON.

### 5.4 Compliance expectations

- Intended to be **NON‑PII**:
  - Contracts and tests must assert that free‑text fields (e.g. `message`) do
    not contain obvious PII (names, emails).
- Classified as **INTERNAL**; can be shared more broadly than customer or
  transaction data.

---

## 6. contract_examples/ – Sample Contracts

To make the sample datasets immediately usable in the hub, we provide a
`contract_examples/` folder containing example Contracts that align with the
datasets defined above.

### 6.1 Folder structure

```text
contract_examples/
  ├─ customers_core.contract.json
  ├─ transactions_pii_edge_cases.contract.json
  ├─ ref_countries.contract.json
  ├─ events_application_logs.contract.json
  └─ ...
```

- File names SHOULD match the dataset key.
- Each file is a single Contract document in the canonical API shape.

### 6.2 Contract example conventions

Each sample contract:

- References **exactly one** of the datasets defined in this document.
- Uses realistic but safe (non‑PII, anonymised) values for:
  - `name`, `description`, `owner`, `classification`, etc.
- Aligns field definitions with the columns / attributes described for the
  dataset, including:
  - data types,
  - nullable vs required,
  - semantic tags / business terms (where applicable),
  - DQ / compliance annotations (e.g. PII, retention, sensitivity).

**Example skeleton** (fields to be adapted per dataset):

```json
{
  "id": "contract-<dataset-key>-example-1",
  "name": "<Dataset Name> – Example Contract",
  "description": "Sample contract aligned with the <dataset-key> dataset.",
  "hub_contract_version": 1,
  "owner": {
    "team": "example-data-team",
    "contact": "data.owner@example.com"
  },
  "asset": {
    "id": "asset-<dataset-key>",
    "name": "<Dataset Name>",
    "system": "example-system",
    "domain": "example-domain"
  },
  "schema": {
    "fields": [
      {
        "name": "field_1",
        "type": "string",
        "nullable": false,
        "semantic_tags": ["business_key"],
        "dq_rules": []
      },
      {
        "name": "field_2",
        "type": "integer",
        "nullable": true,
        "semantic_tags": [],
        "dq_rules": [
          {
            "rule_id": "non_negative",
            "description": "Value must be >= 0",
            "severity": "WARNING"
          }
        ]
      }
    ]
  },
  "classification": {
    "sensitivity": "INTERNAL",
    "contains_pii": false
  }
}
```

### 6.3 Mapping between datasets and contracts

For each dataset described in this document, there SHOULD be at least one
corresponding contract example:

- **Dataset:** `customers_core`
  - **Contract example(s):** `contract_examples/customers_core.contract.json`
- **Dataset:** `transactions_pii_edge_cases`
  - **Contract example(s):** `contract_examples/transactions_pii_edge_cases.contract.json`
- **Dataset:** `ref_countries`
  - **Contract example(s):** `contract_examples/ref_countries.contract.json`
- **Dataset:** `events_application_logs`
  - **Contract example(s):** `contract_examples/events_application_logs.contract.json`

> **Goal:** any engineer or tester should be able to:
> 1. Pick a dataset from this document.
> 2. Find a matching contract under `contract_examples/`.
> 3. Use that pair directly to exercise ingestion, contract validation,
>    semantic mapping, and compliance / DQ features end‑to‑end.
