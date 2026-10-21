# ODPS Integration Guide

## Overview
The Open Data Product Specification (ODPS) integration allows tenants to describe their data products using the ODPS standard and serve them through the Data Interoperability Hub catalog.

## Setup

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="your-api-key")
client.contracts.create_odps_document(
    name="My Data Product",
    description="Describes sales data for Q4",
    tenant_id="...",
)
```

## Endpoint patterns
All ODPS endpoints use standardized patterns:
- `/api/v1/contracts/odps/` — CRUD for ODPS documents
- `/api/v1/contracts/odps/{id}/validate/` — validate an ODPS document

```bash
curl -X POST "/api/v1/contracts/odps/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Data Product", "version": "1.0.0"}'
```
